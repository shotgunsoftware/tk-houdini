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
        
        tk_houdini = self.import_module("tk_houdini")
        bootstrap = tk_houdini.bootstrap

        if bootstrap.g_temp_env in os.environ:
            if self.has_ui:
                # setup houdini menus
                menu_file = os.path.join(os.environ[bootstrap.g_temp_env], 'MainMenuCommon')

                # as of houdini 12.5 add .xml
                if hou.applicationVersion() > (12, 5, 0):
                    menu_file = menu_file + ".xml"

                menu = tk_houdini.MenuGenerator(self)
                if not os.path.exists(menu_file):
                    # just create the xml for the menus
                    menu.create_menu(menu_file)

                # get map of id to callback
                self._callback_map = menu.callback_map()

            # Figure out the tmp OP Library path for this session
            oplibrary_path = os.environ[bootstrap.g_temp_env].replace("\\", "/")

            # Setup the OTLs that need to be loaded for the Toolkit apps
            self._load_otls(oplibrary_path)

        if self.has_ui:
            # startup Qt
            from tank.platform.qt import QtGui
            from tank.platform.qt import QtCore

            app = QtGui.QApplication.instance()
            if app is None:
                # create the QApplication
                sys.argv[0] = 'Shotgun'
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



