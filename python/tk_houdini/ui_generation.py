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
import re
import sys
import xml.etree.ElementTree as ET

g_menu_item_script = os.path.join(os.path.dirname(__file__), "menu_action.py")

# #3716 Fixes UNC problems with menus. Prefix '\' are otherwise concatenated to a single character, therefore using '/' instead.
g_menu_item_script = g_menu_item_script.replace("\\", "/")


class AppCommandsUI(object):
    """Base class for interface elements that trigger command actions."""

    def __init__(self, engine, commands=None):
        self._engine = engine
        self._commands = commands

        if self._commands is None:
            self._commands = get_registered_commands(engine)

    def _get_context_name(self):
        """Returns a display name for the current context"""

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
            ctx_name = "%s, %s %s" % (
                task_step, ctx.entity["type"], ctx.entity["name"])

        return ctx_name


class AppCommandsMenu(AppCommandsUI):

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

        # create the menu object
        ctx_name = self._get_context_name()
        ctx_menu = self._menuNode(submenu, ctx_name, "tk.context")
        ET.SubElement(ctx_menu, "separatorItem")

        # favorites
        ET.SubElement(submenu, "separatorItem")
        for fav in self._engine.get_setting("menu_favourites"):
            app_instance_name = fav["app_instance"]
            menu_name = fav["name"]

            for cmd in self._commands:
                if cmd.get_app_instance_name() == app_instance_name and cmd.name == menu_name:
                    cmd.favourite = True
                    self._itemNode(submenu, cmd.name, cmd.get_id())

        # everything else
        ET.SubElement(submenu, "separatorItem")
        commands_by_app = {}
        for cmd in self._commands:
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


class AppCommandsShelf(AppCommandsUI):

    def __init__(self, engine, commands=None, name='Shotgun', label='Shotgun'):
        """Initialize the shotgun commands shelf.

            engine:
                The engine driving the integration (required)

            commands:
                Optional commands to display in the shelf. If not
                      supplied, pulled from the engine's registered commands

            name:
                The houdini internal name for the shelf

            label:
                The display name for the shelf in the shelf tab
        """

        super(AppCommandsShelf, self).__init__(engine, commands)

        self._name = name
        self._label = label

    def create_shelf(self, shelf_file):
        """Creates a Shotgun shelf with a tool button for each command.

            shelf_file:
                The xml file where the shelf definition will be written
        """

        import hou

        # On windows it is necessary to create a blank the xml file before
        # creating the shelf.
        shelf_dir = os.path.dirname(shelf_file)
        if not os.path.exists(shelf_dir):
            os.makedirs(shelf_dir)
        
        root = ET.Element("shelfDocument")
        doc = ET.ElementTree(root)
        doc.write(shelf_file, encoding="UTF-8")

        # see if there's already a shelf.
        shelf = hou.shelves.shelves().get(self._name, None)
        if shelf:
            # existing shelf. point it to the new shelf file for this session
            self._engine.log_debug("Using existing shelf.")
            self._engine.log_debug("  Setting shelf file: %s" % shelf_file)
            shelf.setFilePath(shelf_file)
        else:
            self._engine.log_debug("Creating new shelf: %s" % self._name)
            shelf = hou.shelves.newShelf(
                file_path=shelf_file,
                name=self._name,
                label=self._label
            )

        shelf_tools = []
        cmds_by_app = {}

        # add the context menu tools first, then organize them by app name.
        for cmd in self._commands:
            if cmd.get_type() == "context_menu":
                tool = self.create_tool(shelf_file, cmd)
                shelf_tools.append(tool)
            else:
                app_name = cmd.get_app_name()
                if app_name is None:
                    app_name = "Other Items"
                cmds_by_app.setdefault(app_name, []).append(cmd)

        # create tools for the remaining commands
        for app_name in sorted(cmds_by_app.keys()):
            for cmd in cmds_by_app[app_name]:
                tool = self.create_tool(shelf_file, cmd)
                shelf_tools.append(tool)

        shelf.setTools(shelf_tools)

        # TODO: Currently there doesn't appear to be a way to add the sg shelf
        # to an existing shelf set programmatiaclly. Will be following up with
        # sesi to see what they recommend. If there is a way, this is probably
        # where the shelf would need to be added.

    def create_tool(self, shelf_file, cmd):
        """Create a new shelf tool.

            cmd:
                The AppCommand to create a shelf tool for.

            shelf_file:
                The shelf file to write the tool definition to.
        """

        import hou

        self._engine.log_debug("Creating tool: %s" % cmd.name)
        tool = hou.shelves.newTool(
            file_path=shelf_file,
            name=cmd.name.replace(" ", "_"),
            label=cmd.name,
            script=_g_launch_script % cmd.get_id(),
            help=cmd.get_description(),
            help_url=cmd.get_documentation_url_str(),
            icon=cmd.get_icon()
        )
        # NOTE: there seems to be a bug in houdini where the 'help' does
        # not display in the tool's tooltip even though the tool's help
        # string is clearly populated in the tool when you edit it in the
        # ui.

        return tool

    def destroy_shelf(self):
        """Destroy the shelf and all of its tools."""

        import hou

        shelf = hou.shelves.shelves().get(self._name, None)

        # shelf wasn't found for some reason
        if not shelf:
            return

        # get rid of all the tools on the shelf
        self.destroy_tools()

        self._engine.log_debug("Destroying shelf: %s" % shelf.name())
        shelf.destroy()

    def destroy_tools(self):
        """Destroy the tools on the shelf, leaving a blank shelf."""

        import hou

        shelf = hou.shelves.shelves().get(self._name, None)

        # shelf wasn't found for some reason
        if not shelf:
            return

        # destroy all the tools on the shelf to be safe
        for tool in shelf.tools():
            self._engine.log_debug("Destroying tool: %s" % tool.name())
            tool.destroy()

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

    def get_description(self):
        if "description" in self.properties:
            return self.properties["description"]
        return None

    def get_icon(self):
        if "icon" in self.properties:

            # houdini required "/" for UNC paths instead of "\\". 
            icon_path = self.properties["icon"].replace("\\", "/")

            return icon_path
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
            return str(doc_url)

        return None

    def get_type(self):
        return self.properties.get("type", "default")

def get_registered_commands(engine):
    """Returns a list of AppCommands for the engine's registered commands.

        engine: The engine to return registered commands for

        NOTE: This method currently returns additional commands that are
        not registered, but always present in the shotgun menu and shelves.
        Those commands are:

            "Jump to Shotgun"
            "Jump to File System"
    """

    # ---- build a couple of "always present" commands

    sg_icon = os.path.join(engine.disk_location, "resources",
        "shotgun_logo.png")

    jump_to_sg_cmd = AppCommand(
        name="Jump to Shotgun",
        command_dict={
         'properties': {
          'description': "Open the current Shotgun context in your web browser.",
          'icon': sg_icon.replace("\\", "/"), # account for UNC path
          'type': "context_menu",
         },
         'callback':lambda: _jump_to_sg(engine),
        },
    )

    fs_icon = os.path.join(engine.disk_location, "resources",
        "shotgun_folder.png")

    jump_to_fs_cmd = AppCommand(
        name="Jump to File System",
        command_dict={
         'properties': {
          'icon': fs_icon.replace("\\", "/"), # account for UNC path
          'description': "Open the current Shotgun context in your file browser.",
          'type': "context_menu",
         },
         'callback': lambda: _jump_to_fs(engine),
        },
    )

    commands = [jump_to_sg_cmd, jump_to_fs_cmd]

    for (cmd_name, cmd_details) in engine.commands.items():
        commands.append(AppCommand(cmd_name, cmd_details))
    return commands

# -----------------------------------------------------------------------------
# internal:

def _jump_to_sg(engine):
    """
    Jump from context to Sg
    """
    from tank.platform.qt import QtCore, QtGui
    url = engine.context.shotgun_url
    QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))


def _jump_to_fs(engine):
    """
    Jump from context to Fs
    """
    paths = engine.context.filesystem_locations
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
            engine.log_error("Failed to launch '%s'!" % cmd)


# The code that executes when a shelf button is clicked.  This is pulled from
# menu_action.py. Maybe there's a good way to share this rather than
# duplicating the logic?
_g_launch_script = \
"""
import hou
import tank.platform.engine

engine = tank.platform.engine.current_engine()
if engine is None or not hasattr(engine, 'launch_command'):
    msg = "Shotgun: Houdini engine is not loaded."
    if hou.isUIAvailable():
        hou.ui.displayMessage(msg)
    else:
        print msg
else:
    engine.launch_command('%s')
"""

