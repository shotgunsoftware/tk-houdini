#
# Copyright (c) 2013 Shotgun Software, Inc
# ----------------------------------------------------
#
"""
A Houdini engine for Tank.
"""
import os
import sys
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
        from PySide import QtGui
        app = QtGui.QApplication.instance()
        if app is None:
            # create the QApplication
            sys.argv[0] = 'Shotgun'
            app = QtGui.QApplication(sys.argv)
            QtGui.QApplication.setStyle("cleanlooks")
            app.setQuitOnLastWindowClosed(False)
            app.setApplicationName(sys.argv[0])

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
        print str(msg)

    def log_info(self, msg):
        print str(msg)

    def log_error(self, msg):
        self._display_message(msg)
        print str(msg)

    def log_warning(self, msg):
        print str(msg)


