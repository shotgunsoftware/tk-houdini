# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import sys
import xml.etree.ElementTree as ET

g_menu_item_script = os.path.join(os.path.dirname(__file__), "menu_action.py")

# #3716 Fixes UNC problems with menus. Prefix '\' are otherwise concatenated to a single character, therefore using '/' instead.
g_menu_item_script = g_menu_item_script.replace('\\', '/')


class MenuGenerator(object):
    def __init__(self, engine):
        self._engine = engine

    def callback_map(self):
        """ Create a mapping from ids to command callbacks """
        map = {}

        # add context menu defaults
        map["tk.jump_to_sg"] = self._jump_to_sg
        map["tk.jump_to_fs"] = self._jump_to_fs

        # add for all commands
        for (cmd_name, cmd_details) in self._engine.commands.items():
            cmd = AppCommand(cmd_name, cmd_details)
            map[cmd.get_id()] = cmd.callback

        return map

    def create_menu(self, fname):
        """ Create the Shotgun Menu """
        root = ET.Element("mainMenu")
        menubar = ET.SubElement(root, "menuBar")
        submenu = self._menuNode(menubar, "Shotgun", "tk.shotgun")
        node = ET.SubElement(submenu, "insertBefore")
        node.text = "help_menu"

        # make sure the Help menu still comes last
        modify = ET.SubElement(menubar, "modifyItem")
        modify.set("id", "help_menu")
        ET.SubElement(modify, "insertAfter")

        # context menu
        ctx = self._engine.context

        if ctx.entity is None:
            ctx_name = "%s" % ctx.project["name"]
        elif ctx.step is None and ctx.task is None:
            # entity only
            # e.g. Shot ABC_123
            ctx_name = "%s %s" % (ctx.entity["type"], ctx.entity["name"])
        else:
            # we have either step or task
            task_step = None
            if ctx.step:
                task_step = ctx.step.get("name")
            if ctx.task:
                task_step = ctx.task.get("name")

            # e.g. [Lighting, Shot ABC_123]
            ctx_name = "%s, %s %s" % (task_step, ctx.entity["type"], ctx.entity["name"])

        # create the menu object
        ctx_menu = self._menuNode(submenu, ctx_name, "tk.context")
        self._itemNode(ctx_menu, "Jump to Shotgun", "tk.jump_to_sg")
        self._itemNode(ctx_menu, "Jump to File System", "tk.jump_to_fs")
        ET.SubElement(ctx_menu, "separatorItem")

        # menu for each command
        menu_items = []
        for (cmd_name, cmd_details) in self._engine.commands.items():
            menu_items.append(AppCommand(cmd_name, cmd_details))

        # favorites
        ET.SubElement(submenu, "separatorItem")
        for fav in self._engine.get_setting("menu_favourites"):
            app_instance_name = fav["app_instance"]
            menu_name = fav["name"]

            for cmd in menu_items:
                if cmd.get_app_instance_name() == app_instance_name and cmd.name == menu_name:
                    cmd.favourite = True
                    self._itemNode(submenu, cmd.name, cmd.get_id())

        # everything else
        ET.SubElement(submenu, "separatorItem")
        commands_by_app = {}
        for cmd in menu_items:
            if cmd.get_type() == "context_menu":
                self._itemNode(ctx_menu, cmd.name, cmd.get_id())
            else:
                app_name = cmd.get_app_name()
                if app_name is None:
                    app_name = "Other Items"
                commands_by_app.setdefault(app_name, []).append(cmd)

        for app_name in sorted(commands_by_app.keys()):
            cmds = commands_by_app[app_name]
            if len(cmds) > 1:
                menu = self._menuNode(submenu, app_name, "tk.%s" % app_name.lower())
                for cmd in cmds:
                    self._itemNode(menu, cmd.name, cmd.get_id())
            else:
                if not cmds[0].favourite:
                    self._itemNode(submenu, cmds[0].name, cmds[0].get_id())

        # and write out the final xml
        xmldir = os.path.dirname(fname)
        if not os.path.exists(xmldir):
            os.makedirs(xmldir)
        doc = ET.ElementTree(root)
        doc.write(fname, encoding="UTF-8")

    def _menuNode(self, parent, label, id):
        menu = ET.SubElement(parent, "subMenu")
        menu.set("id", id)
        node = ET.SubElement(menu, "label")
        node.text = label
        return menu

    def _itemNode(self, parent, label, id):
        item = ET.SubElement(parent, "scriptItem")
        node = ET.SubElement(item, "label")
        node.text = label
        node = ET.SubElement(item, "scriptPath")
        node.text = g_menu_item_script
        node = ET.SubElement(item, "scriptArgs")
        node.text = id
        return item

    def _jump_to_sg(self):
        """
        Jump from context to Sg
        """
        from tank.platform.qt import QtCore, QtGui
        url = self._engine.context.shotgun_url
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))

    def _jump_to_fs(self):
        """
        Jump from context to Fs
        """
        paths = self._engine.context.filesystem_locations
        for disk_location in paths:
            # get the setting
            system = sys.platform

            # run the app
            if system == "linux2":
                cmd = 'xdg-open "%s"' % disk_location
            elif system == "darwin":
                cmd = 'open "%s"' % disk_location
            elif system == "win32":
                cmd = 'cmd.exe /C start "Folder" "%s"' % disk_location
            else:
                raise Exception("Platform '%s' is not supported." % system)

            exit_code = os.system(cmd)
            if exit_code != 0:
                self._engine.log_error("Failed to launch '%s'!" % cmd)


class AppCommand(object):
    """ Wraps around a single command that you get from engine.commands """
    def __init__(self, name, command_dict):
        self.name = name
        self.properties = command_dict["properties"]
        self.callback = command_dict["callback"]
        self.favourite = False

    def get_app_name(self):
        if "app" in self.properties:
            return self.properties["app"].display_name
        return None

    def get_app_instance_name(self):
        if "app" not in self.properties:
            return None

        app_instance = self.properties["app"]
        engine = app_instance.engine

        for (app_instance_name, app_instance_obj) in engine.apps.items():
            if app_instance_obj == app_instance:
                return app_instance_name

        return None

    def get_id(self):
        title_trans = ''.join(chr(c) if chr(c).isupper() or chr(c).islower() else '_' for c in range(256))
        return "tk.app.%s.%s" % (
            self.get_app_instance_name(),
            self.name.translate(title_trans).lower(),
        )

    def get_documentation_url_str(self):
        if "app" in self.properties:
            app = self.properties["app"]
            doc_url = app.documentation_url
            return doc_url

        return None

    def get_type(self):
        return self.properties.get("type", "default")
