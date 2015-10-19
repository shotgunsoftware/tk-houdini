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

        self.log_debug("%s: Initializing..." % self)

        if hou.applicationVersion()[0] < 12:
            raise tank.TankError("Your version of Houdini is not supported. Currently, Toolkit only supports version 12+")

        # keep track of if a UI exists
        self._ui_enabled = hasattr(hou, 'ui')

        # add our built-in pyside to the python path when on windows
        if sys.platform == "win32":
            py_ver = sys.version_info[0:2]
            if py_ver == (2, 6):
                pyside_path = os.path.join(self.disk_location, "resources", "pyside112_py26_win64")
                sys.path.append(pyside_path)
            elif py_ver == (2, 7):
                pyside_path = os.path.join(self.disk_location, "resources", "pyside121_py27_win64")
                sys.path.append(pyside_path)
            else:
                self.log_warning("PySide not bundled for python %d.%d" % (py_ver[0], py_ver[1]))

    def post_app_init(self):
        """
        Init that runs after all apps have been loaded.
        """

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

                menu = tk_houdini.AppCommandsMenu(self, commands)
                if not os.path.exists(menu_file):
                    # just create the xml for the menus
                    menu.create_menu(menu_file)

            if commands and enable_sg_shelf:

                # setup houdini shelf
                self._shelf = tk_houdini.AppCommandsShelf(self, commands)

                # cleans up any old tools on an existing shelf -- just in case.
                # we currently can't programmatically add a shelf to an
                # existing shelf set, so for now we just leave the shelf and
                # add/remove tools.
                self._shelf.destroy_tools() 

                shelf_file = os.path.join(xml_tmp_dir, 'sg_shelf.xml')
                self._shelf.create_shelf(shelf_file)

            # Get the list of registered commands to build panels for. The
            # commands returned are AppCommand objects defined in
            # tk_houdini.ui_generation
            panel_commands = tk_houdini.get_registered_panels(self)
 
            if commands and panel_commands:
                self._panels_file = os.path.join(xml_tmp_dir, 'sg_panels.pypanel')
                panels = tk_houdini.AppCommandsPanels(self, commands, 
                    panel_commands)
                panels.create_panels(self._panels_file)

            # Figure out the tmp OP Library path for this session
            oplibrary_path = os.environ[bootstrap.g_temp_env].replace("\\", "/")

            # Setup the OTLs that need to be loaded for the Toolkit apps
            self._load_otls(oplibrary_path)

        # startup Qt
        from tank.platform.qt import QtGui
        from tank.platform.qt import QtCore

        app = QtGui.QApplication.instance()
        if app is None:
            # create the QApplication
            sys.argv[0] = "Shotgun"
            app = QtGui.QApplication(sys.argv)
            app.setQuitOnLastWindowClosed(False)
            app.setApplicationName(sys.argv[0])

            # tell QT to interpret C strings as utf-8
            utf8 = QtCore.QTextCodec.codecForName("utf-8")
            QtCore.QTextCodec.setCodecForCStrings(utf8)

            # set the stylesheet
            self._initialize_dark_look_and_feel()

        tk_houdini.python_qt_houdini.exec_(app)

    def destroy_engine(self):
        """
        Engine shutdown.
        """
        
        self.log_debug("%s: Destroying..." % self)

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
            
    def log_debug(self, msg):
        """
        Debug logging
        """        
        if self.get_setting("debug_logging", False):
            print "Shotgun Debug: %s" % msg

    def log_info(self, msg):
        """
        Info logging
        """        
        print "Shotgun: %s" % msg

    def log_error(self, msg):
        """
        Error logging
        """        
        print "Shotgun Error: %s" % msg

    def log_warning(self, msg):
        """
        Warning logging
        """        
        print "Shotgun Warning: %s" % msg

    ############################################################################
    # panel interfaces
    ############################################################################

    def get_panel_info(self, requested_panel_id):
        """Get info dict for the panel with the supplied id."""

        for (panel_id, panel_dict) in self.panels.items():
            if not panel_id == requested_panel_id:
                continue

            # for now, we set a state flag to tell show_panel that we really
            # just need an instance of the widget. this is what the panel
            # interfaces will call to display their contents.
            self._panel_info_request = True
            self.log_debug("Retrieving panel widget for %s" % panel_id)
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
                hou.log_warning(
                    "Unable to find interface for panel '%s' in file: %s" % 
                    (panel_id, self._panels_file))

            if panel_interface:
                # the options to create a named panel on the far right of the
                # UI doesn't seem to be present in python. so hscript it is!
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
            self.log_error("No callback found for id: %s" % cmd_id)
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
        if ver > (15, 0, 252):
            return True

        return False

        # NOTE: there is an outstanding bug at SESI to backport a fix to make
        # setInterface work properly in houdini 14. If that goes through, we'll
        # be able to make embedded panels work in houdini 14 too.

    ############################################################################
    # UI Handling
    ############################################################################

    def _define_qt_base(self):
        """
        Defines QT implementation for the engine. Checks for pyside then pyqt.
        """
        # proxy class used when QT does not exist on the system.
        # this will raise an exception when any QT code tries to use it
        class QTProxy(object):
            def __getattr__(self, name):
                raise tank.TankError("Looks like you are trying to run an App that uses a QT "
                                     "based UI, however the Houdini engine could not find a PyQt "
                                     "or PySide installation in your python system path. We "
                                     "recommend that you install PySide if you want to "
                                     "run UI applications from Houdini.")

        base = {"qt_core": QTProxy(), "qt_gui": QTProxy(), "dialog_base": None}
        self._ui_type = None

        if not self._ui_type:
            try:
                from PySide import QtCore, QtGui
                import PySide

                # Some old versions of PySide don't include version information
                # so add something here so that we can use PySide.__version__ 
                # later without having to check!
                if not hasattr(PySide, "__version__"):
                    PySide.__version__ = "<unknown>"

                base["qt_core"] = QtCore
                base["qt_gui"] = QtGui
                base["dialog_base"] = QtGui.QDialog
                self.log_debug("Successfully initialized PySide '%s' located in %s."
                               % (PySide.__version__, PySide.__file__))
                self._ui_type = "PySide"
            except ImportError:
                pass
            except Exception, e:
                import traceback
                self.log_warning("Error setting up pyside. Pyside based UI "
                                 "support will not be available: %s" % e)
                self.log_debug(traceback.format_exc())

        if not self._ui_type:
            try:
                from PyQt4 import QtCore, QtGui
                import PyQt4

                # hot patch the library to make it work with pyside code
                QtCore.Signal = QtCore.pyqtSignal
                QtCore.Slot = QtCore.pyqtSlot
                QtCore.Property = QtCore.pyqtProperty
                base["qt_core"] = QtCore
                base["qt_gui"] = QtGui
                base["dialog_base"] = QtGui.QDialog
                self.log_debug("Successfully initialized PyQt '%s' located in %s."
                               % (QtCore.PYQT_VERSION_STR, PyQt4.__file__))
                self._ui_type = "PyQt"
            except ImportError:
                pass
            except Exception, e:
                import traceback
                self.log_warning("Error setting up PyQt. PyQt based UI support "
                                 "will not be available: %s" % e)
                self.log_debug(traceback.format_exc())

        return base


    def _create_dialog(self, title, bundle, widget, parent):
        """
        Overriden from the base Engine class - create a TankQDialog with the specified widget 
        embedded.
        
        :param title: The title of the window
        :param bundle: The app, engine or framework object that is associated with this window
        :param widget: A QWidget instance to be embedded in the newly created dialog.
        :param parent: The parent QWidget for the dialog
        """
        # call the base implementation to create the dialog:
        dialog = tank.platform.Engine._create_dialog(self, title, bundle, widget, parent)

        # raise and activate the dialog:
        dialog.raise_()
        dialog.activateWindow()

        # special case to get windows to raise the dialog
        if sys.platform == "win32":
            ctypes.pythonapi.PyCObject_AsVoidPtr.restype = ctypes.c_void_p
            ctypes.pythonapi.PyCObject_AsVoidPtr.argtypes = [ctypes.py_object]
            if self._ui_type == "PySide":
                hwnd = ctypes.pythonapi.PyCObject_AsVoidPtr(dialog.winId())
            elif self._ui_type == "PyQt":
                hwnd = ctypes.pythonapi.PyCObject_AsVoidPtr(dialog.winId().ascobject())
            else:
                raise NotImplementedError("Unsupported ui type: %s" % self._ui_type)
            ctypes.windll.user32.SetActiveWindow(hwnd)

        return dialog

    def show_modal(self, title, bundle, widget_class, *args, **kwargs):
        """
        Launches a modal dialog. Overridden from base class.
        """
        from tank.platform.qt import QtCore, QtGui
        
        if not self._ui_type:
            self.log_error("Cannot show dialog %s! No QT support appears to exist in this engine. "
                           "In order for the houdini engine to run UI based apps, either pyside "
                           "or PyQt needs to be installed in your system." % title)
            return
        
        # In houdini, the script editor runs in a custom thread. Any commands executed here
        # which are calling UI functionality may cause problems with QT. Check that we are
        # running in the main thread
        if QtCore.QThread.currentThread() != QtGui.QApplication.instance().thread():
            self.execute_in_main_thread(self.log_error, "Error creating dialog: You can only launch UIs "
                                        "in the main thread. Try using the execute_in_main_thread() method.")
            return        

        # create the dialog:
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
        
        if not self._ui_type:
            self.log_error("Cannot show dialog %s! No QT support appears to exist in this engine. "
                           "In order for the houdini engine to run UI based apps, either pyside "
                           "or PyQt needs to be installed in your system." % title)
            return
        
        # In houdini, the script editor runs in a custom thread. Any commands executed here
        # which are calling UI functionality may cause problems with QT. Check that we are
        # running in the main thread
        if QtCore.QThread.currentThread() != QtGui.QApplication.instance().thread():
            self.execute_in_main_thread(self.log_error, "Error creating dialog: You can only launch UIs "
                                        "in the main thread. Try using the execute_in_main_thread() method.")
            return

        # create the dialog:
        dialog, widget = self._create_dialog_with_widget(title, bundle, widget_class, *args, **kwargs)

        # show the dialog:
        dialog.show()
        
        # lastly, return the instantiated widget
        return widget



