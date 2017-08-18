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

import tank

import hou


class HoudiniEngine(tank.platform.Engine):
    """
    Houdini Engine implementation
    """
    
    ############################################################################
    # init and basic properties
    ############################################################################
        
    def init_engine(self):
        """
        Main initialization entry point.
        """        

        self.logger.debug("%s: Initializing..." % self)

        if hou.applicationVersion()[0] < 14:
            raise tank.TankError(
                "Your version of Houdini is not supported. Currently, Toolkit "
                "only supports version 14+."
            )

        try:
            hou_ver_str = ".".join([str(v) for v in hou.applicationVersion()])
            self.log_user_attribute_metric("Houdini version", hou_ver_str)
        except:
            # ignore all errors. ex: using a core that doesn't support metrics
            pass

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

        from tank.platform.qt import QtCore

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
                menu_file = os.path.join(xml_tmp_dir, "MainMenuCommon")

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

                # setup houdini shelf
                self._shelf = tk_houdini.AppCommandsShelf(self, commands)

                # cleans up any old tools on an existing shelf -- just in case.
                # we currently can't programmatically add a shelf to an
                # existing shelf set, so for now we just leave the shelf and
                # add/remove tools.
                self._shelf.destroy_tools() 

                shelf_file = os.path.join(xml_tmp_dir, "sg_shelf.xml")
                self._shelf.create_shelf(shelf_file)

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
                    self._panels_file = os.path.join(xml_tmp_dir,
                        "sg_panels.pypanel")
                    panels = tk_houdini.AppCommandsPanelHandler(self, commands,
                        panel_commands)
                    panels.create_panels(self._panels_file)

            # Figure out the tmp OP Library path for this session
            oplibrary_path = os.environ[bootstrap.g_temp_env].replace("\\", "/")

            # Setup the OTLs that need to be loaded for the Toolkit apps
            self._load_otls(oplibrary_path)

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

    def _load_otls(self, oplibrary_path):
        """
        Load any OTLs provided by applications.

        Look in any application folder for a otls subdirectory and load any .otl
        file from there.
        """
        for app in self.apps.values():
            otl_path = os.path.join(app.disk_location, 'otls')
            if not os.path.exists(otl_path):
                continue

            for filename in os.listdir(otl_path):
                if os.path.splitext(filename)[-1] == '.otl':
                    path = os.path.join(otl_path, filename).replace("\\", "/")
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

    def _create_dialog(self, title, bundle, widget, parent):
        """
        Overriden from the base Engine class - create a TankQDialog with the specified widget 
        embedded.
        
        :param title: The title of the window
        :param bundle: The app, engine or framework object that is associated with this window
        :param widget: A QWidget instance to be embedded in the newly created dialog.
        :param parent: The parent QWidget for the dialog
        """

        from tank.platform.qt import QtCore

        # call the base implementation to create the dialog:
        dialog = tank.platform.Engine._create_dialog(self, title, bundle, widget, parent)

        if dialog.parent():
            # parenting crushes the dialog's style. This seems to work to reset
            # the style to the dark look and feel in preparation for the
            # re-application below. See the comment about initializing the dark
            # look and feel above.
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
        if bundle.name == "tk-multi-shotgunpanel":
            self._apply_external_styleshet(bundle, dialog)
        else:
            # manually re-apply any bundled stylesheet to the dialog if we are older
            # than H16. In 16 we inherited styling problems and need to rely on the
            # engine level qss only.
            #
            # If we're in 16+, we also need to apply the engine-level qss.
            if hou.applicationVersion()[0] >= 16:
                self._apply_external_styleshet(self, dialog)

            if hou.applicationVersion()[0] < 16:
                self._apply_external_styleshet(bundle, dialog)

        # raise and activate the dialog:
        dialog.raise_()
        dialog.activateWindow()

        # special case to get windows to raise the dialog
        if sys.platform == "win32":
            ctypes.pythonapi.PyCObject_AsVoidPtr.restype = ctypes.c_void_p
            ctypes.pythonapi.PyCObject_AsVoidPtr.argtypes = [ctypes.py_object]
            hwnd = ctypes.pythonapi.PyCObject_AsVoidPtr(dialog.winId())
            ctypes.windll.user32.SetActiveWindow(hwnd)

        return dialog

    def show_modal(self, title, bundle, widget_class, *args, **kwargs):
        """
        Launches a modal dialog. Overridden from base class.
        """
        from tank.platform.qt import QtCore, QtGui
        
        # In houdini, the script editor runs in a custom thread. Any commands executed here
        # which are calling UI functionality may cause problems with QT. Check that we are
        # running in the main thread
        if QtCore.QThread.currentThread() != QtGui.QApplication.instance().thread():
            self.execute_in_main_thread(self.logger.error, "Error creating dialog: You can only launch UIs "
                                        "in the main thread. Try using the execute_in_main_thread() method.")
            return        

        dialog, widget = self._create_dialog_with_widget(title, bundle, widget_class, *args, **kwargs)

        # finally launch it, modal state
        status = dialog.exec_()
        
        # lastly, return the instantiated widget
        return (status, widget)

    def show_dialog(self, title, bundle, widget_class, *args, **kwargs):
        """
        Shows a modeless dialog. Overridden from base class.
        """        
        from tank.platform.qt import QtCore, QtGui
        
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
        
        # lastly, return the instantiated widget
        return widget

    def save_as(self):
        """
        Open a file dialog to choose a file path to save the current session to
        """

        from tank.platform.qt import QtGui

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

        from tank.platform.qt import QtGui

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

