#
# Copyright (c) 2013 Shotgun Software, Inc
# ----------------------------------------------------
#
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
    def init_engine(self):
        self.log_debug("%s: Initializing..." % self)

        # add platform specific paths to sys.path
        path_setting = {
            'darwin': 'mac_additional_syspath',
            'linux': 'linux_additional_syspath',
            'linux2': 'linux_additional_syspath',
            'win32': 'windows_additional_syspath',
        }[sys.platform]
        paths_to_add = self.get_setting(path_setting)
        if paths_to_add:
            sys.path.extend(paths_to_add.split(':'))

        # add our built-in pyside to the python path when on windows            
        if sys.platform == "win32":
            pyside_path = os.path.join(self.disk_location, "resources","pyside112_py26_win64")
            sys.path.append(pyside_path)

        self.__created_qt_dialogs = []

    def post_app_init(self):
        tk_houdini = self.import_module("tk_houdini")
        bootstrap = tk_houdini.bootstrap

        if bootstrap.g_temp_env in os.environ:
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

        # startup PySide
        from PySide import QtGui, QtCore
        app = QtGui.QApplication.instance()
        if app is None:
            # create the QApplication
            sys.argv[0] = 'Shotgun'
            app = QtGui.QApplication(sys.argv)
            QtGui.QApplication.setStyle("cleanlooks")
            app.setQuitOnLastWindowClosed(False)
            app.setApplicationName(sys.argv[0])

            # tell QT to interpret C strings as utf-8
            utf8 = QtCore.QTextCodec.codecForName("utf-8")
            QtCore.QTextCodec.setCodecForCStrings(utf8)

            # set the stylesheet
            resources = os.path.join(os.path.dirname(__file__), "resources")
            css_file = os.path.join(resources, "dark.css")
            f = open(css_file)
            css = f.read()
            f.close()
            app.setStyleSheet(css)
        tk_houdini.pyside_houdini.exec_(app)

    def destroy_engine(self):
        self.log_debug("%s: Destroying..." % self)

        tk_houdini = self.import_module("tk_houdini")
        bootstrap = tk_houdini.bootstrap
        if bootstrap.g_temp_env in os.environ:
            # clean up and keep on going
            shutil.rmtree(os.environ[bootstrap.g_temp_env])

    def _create_dialog(self, title, bundle, obj):
        from tank.platform.qt import tankqdialog

        dialog = tankqdialog.TankQDialog(title, bundle, obj, None)
        dialog.raise_()
        dialog.activateWindow()

        # get windows to raise the dialog
        if sys.platform == "win32":
            ctypes.pythonapi.PyCObject_AsVoidPtr.restype = ctypes.c_void_p
            ctypes.pythonapi.PyCObject_AsVoidPtr.argtypes = [ctypes.py_object]
            hwnd = ctypes.pythonapi.PyCObject_AsVoidPtr(dialog.winId())
            ctypes.windll.user32.SetActiveWindow(hwnd)

        return dialog

    def show_modal(self, title, bundle, widget_class, *args, **kwargs):
        obj = widget_class(*args, **kwargs)
        dialog = self._create_dialog(title, bundle, obj)
        status = dialog.exec_()
        return status, obj

    def show_dialog(self, title, bundle, widget_class, *args, **kwargs):
        obj = widget_class(*args, **kwargs)
        dialog = self._create_dialog(title, bundle, obj)
        self.__created_qt_dialogs.append(dialog)
        dialog.show()
        return obj

    def _display_message(self, msg):
        if hou.isUIAvailable():
            hou.ui.displayMessage(str(msg))
        else:
            print str(msg)

    def launch_command(self, cmd_id):
        callback = self._callback_map.get(cmd_id)
        if callback is None:
            self.log_error("No callback found for id: %s" % cmd_id)
            return
        callback()

    def log_debug(self, msg):
        if self.get_setting("debug_logging", False):
            print "Shotgun Debug: %s" % msg

    def log_info(self, msg):
        print "Shotgun: %s" % msg

    def log_error(self, msg):
        self._display_message(msg)
        print "Shotgun Error: %s" % msg

    def log_warning(self, msg):
        print str(msg)


