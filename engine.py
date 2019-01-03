# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
A Houdini engine for Tank.
"""

import os
import sys
import ctypes
import shutil
import time

import sgtk

import hou


class HoudiniEngine(sgtk.platform.Engine):
    """
    Houdini Engine implementation
    """
    _pane_cache = dict()

    @property
    def host_info(self):
        """
        :returns: A {"name": application name, "version": application version}
                  dictionary with informations about the application hosting this
                  engine.

        References:
        latest: http://www.sidefx.com/docs/houdini/hom/hou/applicationVersion
        """
        host_info = {"name": "houdini", "version": "unknown"}

        if hasattr(hou, "applicationVersionString"):
            host_info["version"] = hou.applicationVersionString()
        else:
            # Fallback to older way
            host_info["version"] = ".".join([str(v) for v in hou.applicationVersion()])

        if hasattr(hou, "applicationName"):
            host_info["name"] = hou.applicationName()

        return host_info

    ############################################################################
    # init and basic properties
    ############################################################################
        
    def init_engine(self):
        """
        Main initialization entry point.
        """        

        self.logger.debug("%s: Initializing..." % self)

        if hou.applicationVersion()[0] < 14:
            raise sgtk.TankError(
                "Your version of Houdini is not supported. Currently, Toolkit "
                "only supports version 14+."
            )

        # keep track of if a UI exists
        self._ui_enabled = hasattr(hou, 'ui')

    def pre_app_init(self):
        """
        Called at startup, but after QT has been initialized.
        """
        if not self._ui_enabled:
            return

        if hou.applicationVersion()[0] >= 15:
            # In houdini 15+, we can use the dynamic menus and shelf api to
            # properly handle cases where a file is loaded outside of a SG
            # context. Make sure the timer that looks for current file changes
            # is running.
            tk_houdini = self.import_module("tk_houdini")
            if self.get_setting("automatic_context_switch", True):
                tk_houdini.ensure_file_change_timer_running()

    def post_app_init(self):
        """
        Init that runs after all apps have been loaded.
        """

        from sgtk.platform.qt import QtCore

        if not self.has_ui:
            # no UI. everything after this requires the UI!
            return
        
        tk_houdini = self.import_module("tk_houdini")
        bootstrap = tk_houdini.bootstrap

        if bootstrap.g_temp_env in os.environ:

            commands = None
            enable_sg_menu = self.get_setting("enable_sg_menu", True)
            enable_sg_shelf = self.get_setting("enable_sg_shelf", True)

            # menu and/or shelf definitions will be written here
            xml_tmp_dir = os.environ[bootstrap.g_temp_env]

            if enable_sg_menu or enable_sg_shelf:

                # get the list of registered commands to supply to the menu
                # and/or shelf. The commands returned are AppCommand objects
                # defined in tk_houdini.ui_generation
                commands = tk_houdini.get_registered_commands(self)

                # populate a callback map. this is a map of command ids to a
                # corresponding callback. these are used by the menu and shelf
                # for executing installed app commands. 
                self._callback_map = \
                    dict((cmd.get_id(), cmd.callback) for cmd in commands)

            if commands and enable_sg_menu:

                # setup houdini menus
                menu_file = self._safe_path_join(xml_tmp_dir, "MainMenuCommon")

                # as of houdini 12.5 add .xml
                if hou.applicationVersion() > (12, 5, 0):
                    menu_file = menu_file + ".xml"

                # keep the reference to the menu handler for convenience so
                # that we can access it from the menu scripts when they get
                # ahold of the current engine.
                self._menu = tk_houdini.AppCommandsMenu(self, commands)
                if not os.path.exists(menu_file):
                    # just create the xml for the menus
                    self._menu.create_menu(menu_file)

            if commands and enable_sg_shelf:
                def _setup_shelf():
                    # setup houdini shelf
                    self._shelf = tk_houdini.AppCommandsShelf(self, commands)

                    # cleans up any old tools on an existing shelf -- just in case.
                    # we currently can't programmatically add a shelf to an
                    # existing shelf set, so for now we just leave the shelf and
                    # add/remove tools.
                    self._shelf.destroy_tools()
                    shelf_file = self._safe_path_join(xml_tmp_dir, "sg_shelf.xml")
                    self._shelf.create_shelf(shelf_file)

                # We have a problem specific to Windows where Houdini takes a really
                # long time to launch when Toolkit is being used. This it related to
                # the shelf population logic being called here. What's odd is that it's
                # not this logic that's slow (it runs in less than 1 second), but
                # running it causes Houdini to pause for some time after it's executed.
                # Deferring it one event loop cycle via a QTimer gives us the same end
                # result, but without the hang. It's probably safe to do it this way on
                # all OSes, but since we don't see the problem on Linux or OS X,
                # there's no sense in changing the behavior for those operating systems.
                if sys.platform.startswith("win"):
                    QtCore.QTimer.singleShot(1, _setup_shelf)
                else:
                    _setup_shelf()

            if commands and self._panels_supported():

                # Get the list of registered commands to build panels for. The
                # commands returned are AppCommand objects defined in
                # tk_houdini.ui_generation
                panel_commands = tk_houdini.get_registered_panels(self)

                # expose the wrapped panel method on the engine so that the 
                # panels can call it directly
                self.get_wrapped_panel_widget = \
                    tk_houdini.get_wrapped_panel_widget
    
                if panel_commands:
                    self._panels_file = self._safe_path_join(xml_tmp_dir,
                        "sg_panels.pypanel")
                    panels = tk_houdini.AppCommandsPanelHandler(self, commands,
                        panel_commands)
                    panels.create_panels(self._panels_file)

            # Figure out the tmp OP Library path for this session
            oplibrary_path = os.environ[bootstrap.g_temp_env].replace("\\", "/")

            # Setup the OTLs that need to be loaded for the Toolkit apps
            def _load_otls():
                self._load_otls(oplibrary_path)

            # We have the same problem here on Windows that we have above with
            # the population of the shelf. If we defer the execution of the otl
            # loading by an event loop cycle, Houdini loads up quickly.
            if sys.platform.startswith("win"):
                QtCore.QTimer.singleShot(1, _load_otls)
            else:
                _load_otls()

        # tell QT to interpret C strings as utf-8
        utf8 = QtCore.QTextCodec.codecForName("utf-8")
        QtCore.QTextCodec.setCodecForCStrings(utf8)
        self.logger.debug("set utf-8 codec for widget text")

        # Typically we only call this method for engines which don't have a
        # well defined styling. Houdini appears to use stylesheets to handle
        # its styling which it conflicts with the toolkit strategy of using a
        # dark QStyle underneath with additional stylesheets on top, allowing
        # the qss to be minimized. Calling this method applies a global style,
        # palette, and default stylesheet which, in addition to some
        # workarounds when parenting toolkit widgets, allows for the
        # consistent, intended look and feel of the toolkit widgets.
        # Surprisingly, calling this does not seem to have any affect on
        # houdini itself, despite the global nature of the method.
        #
        # NOTE: Except for 16+. It's no longer safe and causes lots of styling
        # problems in Houdini's UI globally.
        if hou.applicationVersion() < (16, 0, 0):
            self.logger.debug("Houdini < 16 detected: applying dark look and feel.")
            self._initialize_dark_look_and_feel()

        # Run a series of app instance commands at startup.
        self._run_app_instance_commands()

    def destroy_engine(self):
        """
        Engine shutdown.
        """
        
        self.logger.debug("%s: Destroying..." % self)

        if hasattr(self, "_shelf") and self._shelf:
            # there doesn't appear to be a way to programmatically add a shelf
            # to an existing shelf set. in order to enable context switching,
            # just delete the tools. that'll allow the engine restart to add
            # tools to the existing shelf
            self._shelf.destroy_tools()

        tk_houdini = self.import_module("tk_houdini")
        bootstrap = tk_houdini.bootstrap
        if bootstrap.g_temp_env in os.environ:
            # clean up and keep on going
            shutil.rmtree(os.environ[bootstrap.g_temp_env])

    @property
    def has_ui(self):
        """
        Detect and return if houdini is running in batch mode
        """
        return self._ui_enabled

    def _emit_log_message(self, handler, record):
        """
        Called by the engine whenever a new log message is available. All log
        messages from the toolkit logging namespace will be passed to this
        method.
        """

        # call out to handler to format message in a standard way
        msg_str = handler.format(record)

        # display message
        print msg_str

    ############################################################################
    # panel interfaces
    ############################################################################

    def get_panel_info(self, requested_panel_id):
        """Get info dict for the panel with the supplied id.
        
        :param int requested_panel_id: The id of the panel to get info for
        :return: A dictionary of information about the panel
        :rtype: dict
        
        The dictionary returned will include keys: 'id', 'title', 'bundle',
        widget_class', 'args', and 'kwargs'. The values of those keys
        will be the values supplied to the `show_panel` method by the panel's
        callback method.

        """

        for (panel_id, panel_dict) in self.panels.items():
            if not panel_id == requested_panel_id:
                continue

            # Typically the panel callback would be used to actually show the
            # panel, and it would be triggered from a menu/shelf. In houdini
            # however, we need to pre-build a python script to embed into a
            # python panel definition. In order for that script to get the
            # information it needs to construct the proper panel widget, it
            # needs information that is only available when `show_panel` is
            # called via the callback. So, we set a flag that `show_panel` can
            # use to short-circuit and return the info needed.
            self._panel_info_request = True
            self.logger.debug("Retrieving panel widget for %s" % panel_id)
            panel_info = panel_dict['callback']()
            del self._panel_info_request
            return panel_info

        return None

    def show_panel(self, panel_id, title, bundle, widget_class, *args,
        **kwargs):
        """Show the panel matching the supplied args. 

        Will first try to locate an existing instance of the panel. If it 
        exists, it will make it current. If it can't find an existing panel,
        it will create a new one.

        If the panel can't be created for some reason, the widget will be 
        displayed as a dialog.
        
        :param panel_id: Unique id to associate with the panel - normally this
            is a string obtained via the register_panel() call.
        :param title: The title of the window
        :param bundle: The app, engine or framework object that is associated
            with this window 
        :param widget_class: The class of the UI to be
        constructed. This must derive from QWidget.
        
        Additional parameters specified will be passed through to the
        widget_class constructor.
        """

        # check to see if we just need to return the widget itself. Since we
        # don't really have information about the panel outside of this call,
        # we use a special flag to know when the info is needed and return it.
        if hasattr(self, '_panel_info_request') and self._panel_info_request:
            return {
                'id': panel_id,
                'title': title,
                'bundle': bundle,
                'widget_class': widget_class,
                'args': args,
                'kwargs': kwargs,
            }

        # try to locate the pane in the desktop and make it the current tab. 
        for pane_tab in hou.ui.curDesktop().paneTabs():
            if pane_tab.name() == panel_id:
                pane_tab.setIsCurrentTab()
                return

            # A secondary check is to look at a cache we hold mapping the title
            # of the panel to a pane tab that already exists. We use the title
            # here instead of the panel id because it's the only bit of information
            # we have reliable access to from all of the various methods of
            # showing pane tabs in Houdini.
            if pane_tab.name() == self._pane_cache.get(title):
                pane_tab.setIsCurrentTab()
                return

        # panel support differs between 14/15. 
        if self._panels_supported():

            # if it can't be located, try to create a new tab and set the
            # interface.
            panel_interface = None
            try:
                for interface in hou.pypanel.interfacesInFile(self._panels_file):
                    if interface.name() == panel_id:
                        panel_interface = interface
                        break
            except hou.OperationFailed:
                # likely due to panels file not being a valid file, missing, etc. 
                # hopefully not the case, but try to continue gracefully.
                self.logger.warning(
                    "Unable to find interface for panel '%s' in file: %s" % 
                    (panel_id, self._panels_file))

            if panel_interface:
                # the options to create a named panel on the far right of the
                # UI doesn't seem to be present in python. so hscript it is!
                # Here's the docs for the hscript command:
                #     https://www.sidefx.com/docs/houdini14.0/commands/pane
                hou.hscript("pane -S -m pythonpanel -o -n %s" % panel_id)
                panel = hou.ui.curDesktop().findPaneTab(panel_id)

                # different calls to set the python panel interface in Houdini
                # 14/15
                if hou.applicationVersion()[0] >= 15:
                    panel.setActiveInterface(panel_interface)
                else:
                    # if SESI puts in a fix for setInterface, then panels
                    # will work for houini 14. will just need to update
                    # _panels_supported() to add the proper version. and 
                    # remove this comment. 
                    panel.setInterface(panel_interface)

                # turn off the python panel toolbar to make the tk panels look
                # more integrated. should be all good so just return
                panel.showToolbar(False)
                return

        # if we're here, then showing as a panel was unsuccesful or not
        # supported. Just show it as a dialog.
        self.show_dialog(title, bundle, widget_class, *args, **kwargs)

    ############################################################################
    # internal methods
    ############################################################################

    def launch_command(self, cmd_id):
        """
        Internal helper used by the engine to execute a command from the menu.
        This method is for internal use only and not meant to be called from external applications!
        """        
        callback = self._callback_map.get(cmd_id)
        if callback is None:
            self.logger.error("No callback found for id: %s" % cmd_id)
            return
        callback()

    def _safe_path_join(self, *args):
        """
        Joins elements into a path. On OSX or Linux, this will be the same as using
        os.path.join directly. On Windows, backslash separators will be replaced by
        forward slashes. Earlier releases of H17 will crash if given backslash
        delimited paths on Windows.

        :returns: A forward-slash-delimited path.
        :rtype: str
        """
        return os.path.join(*args).replace(os.path.sep, "/")

    def _load_otls(self, oplibrary_path):
        """
        Load any OTLs provided by applications.

        Look in any application folder for a otls subdirectory and load any .otl
        file from there.
        """
        for app in self.apps.values():
            otl_path = self._safe_path_join(app.disk_location, 'otls')
            if not os.path.exists(otl_path):
                continue

            for filename in os.listdir(otl_path):
                if os.path.splitext(filename)[-1] == '.otl':
                    path = self._safe_path_join(otl_path, filename).replace(os.path.sep, "/")
                    hou.hda.installFile(path, oplibrary_path, True)

    def _panels_supported(self):
        """
        Returns True if panels are supported for current Houdini version.
        """
        
        ver = hou.applicationVersion()
    
        # first version where saving python panel in desktop was fixed
        if sys.platform.startswith("darwin"):
            # We have some serious painting problems with Python panes in
            # H16 that are specific to OS X. We have word out to SESI, and
            # are waiting to hear back from them as to how we might be able
            # to proceed. Until that is sorted out, though, we're going to
            # have to disable panel support on OS X for H16. Our panel apps
            # appear to function just fine in dialog mode.
            #
            # Update: H17 resolves some of the issues, but we still have problems
            # with item delegates not rendering consistently in the Shotgun Panel's
            # entity views.
            if ver >= (16, 0, 0):
                return False

        if ver >= (15, 0, 272):
            return True

        return False

        # NOTE: there is an outstanding bug at SESI to backport a fix to make
        # setInterface work properly in houdini 14. If that goes through, we'll
        # be able to make embedded panels work in houdini 14 too.

    def _run_app_instance_commands(self):
        """
        Runs the series of app instance commands listed in the 'run_at_startup'
        setting of the environment configuration yaml file.
        """

        # Build a dictionary mapping app instance names to dictionaries of
        # commands they registered with the engine.
        app_instance_commands = {}
        for (cmd_name, value) in self.commands.iteritems():
            app_instance = value["properties"].get("app")
            if app_instance:
                # Add entry 'command name: command function' to the command
                # dictionary of this app instance.
                cmd_dict = app_instance_commands.setdefault(
                    app_instance.instance_name, {})
                cmd_dict[cmd_name] = value["callback"]

        # build a list of commands to run and then execute them all at once
        # after houdini's UI has finished loading.
        commands_to_run = []

        # Run the series of app instance commands listed in the 'run_at_startup'
        # setting.
        for app_setting_dict in self.get_setting("run_at_startup", []):

            app_instance_name = app_setting_dict["app_instance"]

            # Menu name of the command to run or '' to run all commands of the
            # given app instance.
            setting_cmd_name = app_setting_dict["name"]

            # Retrieve the command dictionary of the given app instance.
            cmd_dict = app_instance_commands.get(app_instance_name)

            if cmd_dict is None:
                self.log_warning(
                    "%s configuration setting 'run_at_startup' requests app "
                    "'%s' that is not installed." %
                    (self.name, app_instance_name))
            else:
                if not setting_cmd_name:
                    # add commands to the list for the given app instance.
                    for (cmd_name, cmd_function) in cmd_dict.iteritems():
                        self.log_debug(
                            "%s startup running app '%s' command '%s'." %
                            (self.name, app_instance_name, cmd_name)
                        )
                        commands_to_run.append((cmd_name, cmd_function))
                else:
                    # add commands whose name is listed in the 'run_at_startup'
                    # setting.
                    cmd_function = cmd_dict.get(setting_cmd_name)
                    if cmd_function:
                        self.log_debug(
                            "%s startup running app '%s' command '%s'." %
                            (self.name, app_instance_name, setting_cmd_name)
                        )
                        commands_to_run.append((setting_cmd_name, cmd_function))
                    else:
                        known_commands = ", ".join(
                            "'%s'" % name for name in cmd_dict)
                        self.log_warning(
                            "%s configuration setting 'run_at_startup' "
                            "requests app '%s' unknown command '%s'. Known "
                            "commands: %s" % (
                                self.name,
                                app_instance_name,
                                setting_cmd_name,
                                known_commands
                            )
                        )

        # no commands to run. just bail
        if not commands_to_run:
            return

        # here we wrap the commands to run in a single function we can hand over
        # to houdini as an event loop callback. This will run when houdini is
        # idle which should be after the UI loads up.
        def run_when_idle():
            # We don't want to spin forever, so if we don't find a usable parent
            # that's visible within 5 seconds, we'll just go ahead and run the
            # commands.
            timeout_secs = 5.0

            if (time.time() - run_when_idle._start_time) < timeout_secs:
                # We want to try to wait for our top-level parent to become visible
                # before we run our commands, if possible.
                parent_window = self._get_dialog_parent()
                if self._get_dialog_parent() is None or not parent_window.isVisible():
                    return

            for (cmd_name, command) in commands_to_run:
                # iterate over all the commands and execute them.
                self.log_debug("Executing startup command: %s" % (cmd_name,))
                command()

            # have the function unregister itself. it does this by looping over
            # all the registered callbacks and finding itself by looking for a
            # special attribute that is added below (just before registering it
            # as an event loop callback).
            for callback in hou.ui.eventLoopCallbacks():
                if hasattr(callback, "tk_houdini_startup_commands"):
                    hou.ui.removeEventLoopCallback(callback)

        # add the special attribute that the function will look use to find
        # and unregister itself when executed.
        run_when_idle.tk_houdini_startup_commands = True
        run_when_idle._start_time = time.time()

        # add the function as an event loop callback
        hou.ui.addEventLoopCallback(run_when_idle)

    ############################################################################
    # UI Handling
    ############################################################################

    def _get_engine_qss_file(self):
        """
        Returns the engine's style.qss file path.
        """
        from sgtk.platform import constants
        return self._safe_path_join(
            self.disk_location,
            constants.BUNDLE_STYLESHEET_FILE,
        )

    def _get_engine_root_path(self):
        """
        Returns the path to the directory containing this engine.py.
        """
        # Handle the Windows situation where __file__ is going to contain backslash
        # delimiters.
        return "/".join(os.path.dirname(__file__).split(os.path.sep))

    def _create_dialog(self, title, bundle, widget, parent):
        """
        Overriden from the base Engine class - create a TankQDialog with the specified widget 
        embedded.
        
        :param title: The title of the window
        :param bundle: The app, engine or framework object that is associated with this window
        :param widget: A QWidget instance to be embedded in the newly created dialog.
        :param parent: The parent QWidget for the dialog
        """

        from sgtk.platform.qt import QtCore

        # call the base implementation to create the dialog:
        dialog = sgtk.platform.Engine._create_dialog(self, title, bundle, widget, parent)

        if dialog.parent():
            # parenting crushes the dialog's style. This seems to work to reset
            # the style to the dark look and feel in preparation for the
            # re-application below. See the comment about initializing the dark
            # look and feel above.
            #
            # We can only do this in Houdini 15.x or older. With the switch to
            # Qt5/PySide2 in H16, enough has changed in Houdini's styling that
            # we break its styling in a few places if we zero out the main window's
            # stylesheet. We're now compensating for the problems that arise in
            # the engine's style.qss.
            if hou.applicationVersion() < (16, 0, 0):
                dialog.parent().setStyleSheet("")

            # This will ensure our dialogs don't fall behind Houdini's main
            # window when they lose focus.
            if sys.platform.startswith("darwin"):
                dialog.setWindowFlags(
                    dialog.windowFlags() | QtCore.Qt.Tool)
        else:
            # no parent found, so style should be ok. this is probably,
            # hopefully, a rare case, but since our logic for identifying the
            # top-level widget to parent to makes some potentially flawed
            # assumptions, we should account for this case. set window flag to
            # be on top so that it doesn't duck under the houdini window when
            # shown (typicaly for windows)
            dialog.setWindowFlags(
                dialog.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)

        # A bit of a hack here, which goes along with the disabling of panel support
        # for H16 on OS X. Because of that, we are also having to treat the panel
        # differently here for styling purposes. Houdini's styling affects it less,
        # because a significant portion of the shotgun panel is explicitly styled.
        # As such, we need to just accept what it provides and not worry about
        # any engine-level styling.
        #
        # TODO: Remove this when we re-enable panel support in H16 on OS X.
        #
        # We also have custom styling in the publish2 app, and then on top of that
        # we fix some houdini-specific styling issues with it in the engine's
        # style.qss. So we'll treat this similarly to the way we treat the panel
        # and combine the two into a single, unified stylesheet for the dialog
        # and widget.
        engine_root_path = self._get_engine_root_path()

        if bundle.name in ["tk-multi-shotgunpanel", "tk-multi-publish2"]:
            if bundle.name == "tk-multi-shotgunpanel":
                self._apply_external_styleshet(bundle, dialog)

            # Styling in H16+ is very different than in earlier versions of
            # Houdini. The result is that we have to be more careful about
            # behavior concerning stylesheets, because we might bleed into
            # Houdini itself if we change qss on parent objects or make use
            # of QStyles on the QApplication.
            #
            # Below, we're combining the engine-level qss with whatever is
            # already assigned to the widget. This means that the engine
            # styling is helping patch holes in any app- or framework-level
            # qss that might have already been applied.
            if hou.applicationVersion()[0] >= 16:
                # We don't apply the engine's style.qss to the dialog for the panel,
                # but we do for the publisher. This will make sure that the tank
                # dialog's header and info slide-out widget is properly styled. The
                # panel app doesn't show that stuff, so we don't need to worry about
                # it.
                if bundle.name == "tk-multi-publish2":
                    self._apply_external_styleshet(self, dialog)

                qss_file = self._get_engine_qss_file()
                with open(qss_file, "rt") as f:
                    qss_data = f.read()
                    qss_data = self._resolve_sg_stylesheet_tokens(qss_data)
                    qss_data = qss_data.replace("{{ENGINE_ROOT_PATH}}", engine_root_path)
                    widget.setStyleSheet(widget.styleSheet() + qss_data)
                    widget.update()
        else:
            # manually re-apply any bundled stylesheet to the dialog if we are older
            # than H16. In 16 we inherited styling problems and need to rely on the
            # engine level qss only.
            #
            # If we're in 16+, we also need to apply the engine-level qss.
            if hou.applicationVersion()[0] >= 16:
                self._apply_external_styleshet(self, dialog)
                qss = dialog.styleSheet()
                qss = qss.replace("{{ENGINE_ROOT_PATH}}", engine_root_path)
                dialog.setStyleSheet(qss)
                dialog.update()

            if hou.applicationVersion()[0] < 16:
                self._apply_external_styleshet(bundle, dialog)

        # raise and activate the dialog:
        dialog.raise_()
        dialog.activateWindow()

        # special case to get windows to raise the dialog
        if sys.platform == "win32":
            # Anything beyond 16.5.481 bundles a PySide2 version that gives us
            # a usable hwnd directly. We also check to make sure this is Qt5,
            # since SideFX still offers Qt4/PySide builds of modern Houdinis.
            if hou.applicationVersion() >= (16, 5, 481) and QtCore.__version__.startswith("5."):
                hwnd = dialog.winId()
            else:
                ctypes.pythonapi.PyCObject_AsVoidPtr.restype = ctypes.c_void_p
                ctypes.pythonapi.PyCObject_AsVoidPtr.argtypes = [ctypes.py_object]
                hwnd = ctypes.pythonapi.PyCObject_AsVoidPtr(dialog.winId())
            ctypes.windll.user32.SetActiveWindow(hwnd)

        return dialog

    def show_modal(self, title, bundle, widget_class, *args, **kwargs):
        """
        Launches a modal dialog. Overridden from base class.
        """
        from sgtk.platform.qt import QtCore, QtGui
        
        # In houdini, the script editor runs in a custom thread. Any commands executed here
        # which are calling UI functionality may cause problems with QT. Check that we are
        # running in the main thread
        if QtCore.QThread.currentThread() != QtGui.QApplication.instance().thread():
            self.execute_in_main_thread(self.logger.error, "Error creating dialog: You can only launch UIs "
                                        "in the main thread. Try using the execute_in_main_thread() method.")
            return        

        dialog, widget = self._create_dialog_with_widget(title, bundle, widget_class, *args, **kwargs)

        # I don't have an answer to why this does what it does. We have
        # a situation in H16 where some aspects of our widgets can't be
        # styled...the changes just don't have any impact. However, if
        # we re-apply the parent's stylesheet, unchanged, after we show
        # our dialog, those styling changes we've applied either as part
        # of the app's style.qss, or tk-houdini's, everything sticks the
        # way it should.
        if hou.applicationVersion() >= (16, 0, 0):
            dialog.parent().setStyleSheet(dialog.parent().styleSheet())

        # finally launch it, modal state
        status = dialog.exec_()
        
        # lastly, return the instantiated widget
        return (status, widget)

    def show_dialog(self, title, bundle, widget_class, *args, **kwargs):
        """
        Shows a modeless dialog. Overridden from base class.
        """        
        from sgtk.platform.qt import QtCore, QtGui
        
        # In houdini, the script editor runs in a custom thread. Any commands executed here
        # which are calling UI functionality may cause problems with QT. Check that we are
        # running in the main thread
        if QtCore.QThread.currentThread() != QtGui.QApplication.instance().thread():
            self.execute_in_main_thread(self.logger.error, "Error creating dialog: You can only launch UIs "
                                        "in the main thread. Try using the execute_in_main_thread() method.")
            return

        # create the dialog:
        dialog, widget = self._create_dialog_with_widget(title, bundle, widget_class, *args, **kwargs)

        # show the dialog:
        dialog.show()

        # I don't have an answer to why this does what it does. We have
        # a situation in H16 where some aspects of our widgets can't be
        # styled...the changes just don't have any impact. However, if
        # we re-apply the parent's stylesheet, unchanged, after we show
        # our dialog, those styling changes we've applied either as part
        # of the app's style.qss, or tk-houdini's, everything sticks the
        # way it should.
        if hou.applicationVersion() >= (16, 0, 0):
            dialog.parent().setStyleSheet(dialog.parent().styleSheet())
        
        # lastly, return the instantiated widget
        return widget

    def save_as(self):
        """
        Open a file dialog to choose a file path to save the current session to
        """

        from sgtk.platform.qt import QtGui

        # houdini doesn't appear to have a "save as" dialog accessible via
        # python. so open our own Qt file dialog.
        file_dialog = QtGui.QFileDialog(
            parent=self._get_dialog_parent(),
            caption="Save As",
            directory=hou.hipFile.path(),
            filter="Houdini Files (*.hip, *.hipnc)"
        )
        file_dialog.setLabelText(QtGui.QFileDialog.Accept, "Save")
        file_dialog.setLabelText(QtGui.QFileDialog.Reject, "Cancel")
        file_dialog.setOption(QtGui.QFileDialog.DontResolveSymlinks)
        file_dialog.setOption(QtGui.QFileDialog.DontUseNativeDialog)
        if not file_dialog.exec_():
            return
        path = file_dialog.selectedFiles()[0]
        hou.hipFile.save(file_name=path)

    def _get_dialog_parent(self):
        """
        Get the QWidget parent for all dialogs created through show_dialog &
        show_modal.
        """

        from sgtk.platform.qt import QtGui

        parent = None

        # newer versions have access to main window
        if hasattr(hou, "qt") and hasattr(hou.ui, "mainWindow"):
            parent = hou.qt.mainWindow()
        elif hasattr(hou, "ui") and hasattr(hou.ui, "mainQtWindow"):
            parent = hou.ui.mainQtWindow()

        # older versions do not...
        else:

            # attempt to find the houdini main window for parenting. The default
            # implementation in tk-core uses the activeWindow which can be None
            # and can also be an already open toolkit dialog.
            app = QtGui.QApplication.instance()
            for widget in app.topLevelWidgets():

                # try to get a hold of the main window. it seems to be the only
                # one with windowIconText set. There should be a better way to
                # do this.
                if (widget.isWindow() and
                        not isinstance(widget, QtGui.QDialog) and
                        widget.windowIconText()):
                    parent = widget

        self.logger.debug(
            "Found top level widget %s for dialog parenting" % (parent,))
        return parent

