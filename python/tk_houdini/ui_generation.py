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

    def __init__(self, engine, commands):
        self._engine = engine
        self._commands = commands

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
        node.text = '"%s"' % (g_menu_item_script,)
        node = ET.SubElement(item, "scriptArgs")
        node.text = id
        return item

class AppCommandsPanelHandler(AppCommandsUI):
    """Creates panels and installs them into the session."""

    def __init__(self, engine, commands, panel_commands):
        """Initialize the panel handler.

        :param engine: The currently running engine.
        :param commands: A list of commands as `AppCommand` objects.
        :param panel_commands: A list of panels as `AppCommand` objects.

        Note: We currently expect a menu command to be registered for each
        panel. We use the menu command to glean the necessary information 
        to display the panel in the UI. So for each `AppCommand` in the
        `panel_commands` list, there should be a corresponding menu
        `AppCommand` for the panel in the `commands` param.

        """

        self._panel_commands = panel_commands
        super(AppCommandsPanelHandler, self).__init__(engine, commands)

    def create_panels(self, panels_file):
        """Create the registered panels."""        

        import hou

        # this code builds an xml file that defines panel interfaces to be
        # read by houdini. The xml should look something like this:
        #
        # <?xml version='1.0' encoding='UTF-8'?>
        # <pythonPanelDocument>
        #   <interface help_url="http://..." icon="/path/to/icon.png" 
        #     label="My Panel" name="my_panel">
        #     <script>
        #       <![CDATA[PYTHON CODE HERE]]>
        #     </script>
        #     <help>"help string"</help>
        #   </interface>
        #   <interfacesMenu type="toolbar">
        #     <interfaceItem name="my_panel" />
        #   </interfacesMenu>
        #   <interfacesMenu type="panetab">
        #     <interfaceItem name="my_panel" />
        #   </interfacesMenu>
        # </pythonPanelDocument>
        #
        # There will be an <interface> tag for each panel being created.
        # the <interfaceItem> tags tell the toolbar and panetab menus to 
        # display the panel. Each panel will have an <interfaceItem> tag
        # for the "toolbar" and "panetab" menus.

        root = ET.Element("pythonPanelDocument")

        # get the cmds that launch panels so we can get additional info
        # about the panels when we need it.
        cmds_by_panel_callback = {}
        for cmd in self._commands:
            if not cmd.get_type() == "panel":
                continue
            cmds_by_panel_callback[cmd.callback] = cmd

        for panel_cmd in self._panel_commands:

            if not panel_cmd.callback in cmds_by_panel_callback:
                # currently we rely on a menu command to be registered 
                # for each panel in order to get the information we need
                # to display the panel in the UI. If there is no corresponding
                # command, don't show the panel.
                continue

            launch_cmd = cmds_by_panel_callback[panel_cmd.callback]

            icon = panel_cmd.get_icon() or launch_cmd.get_icon()

            interface = ET.SubElement(root, "interface")
            interface.set('name', panel_cmd.name)
            interface.set('label', launch_cmd.name)
            if icon:
                interface.set('icon', launch_cmd.get_icon())

            doc_url = panel_cmd.get_documentation_url_str() or \
                launch_cmd.get_documentation_url_str()
            if not doc_url:
                doc_url = ""
            interface.set('help_url', doc_url)

            script = ET.SubElement(interface, "script")
            script.text = "CDATA_START" + \
                _g_panel_script % (icon, launch_cmd.name, panel_cmd.name) + \
                "CDATA_END"

            desc = panel_cmd.get_description() or launch_cmd.get_description()
            if not desc:
                desc = ""

            panel_help = ET.SubElement(interface, "help")
            panel_help.text = "CDATA_START" + desc + "CDATA_END"
            panel_help.text = desc

            # add the panel to the panetab and toolbar menus

            toolbar_menu = ET.SubElement(root, "interfacesMenu")
            toolbar_menu.set('type', 'toolbar')

            toolbar_menu_item = ET.SubElement(toolbar_menu,
                'interfaceItem')
            toolbar_menu_item.set('name', panel_cmd.name)

            panetab_menu = ET.SubElement(root, "interfacesMenu")
            panetab_menu.set('type', 'panetab')

            panetab_menu_item = ET.SubElement(panetab_menu,
                'interfaceItem')
            panetab_menu_item.set('name', panel_cmd.name)

        full_xml = ET.tostring(root, encoding="UTF-8")
        full_xml = full_xml.replace("CDATA_START", "<![CDATA[")
        full_xml = full_xml.replace("CDATA_END", "]]>")

        panels_dir = os.path.dirname(panels_file)
        if not os.path.exists(panels_dir):
            os.makedirs(panels_dir)

        with open(panels_file, "w") as panels_file_handle:
            panels_file_handle.write(full_xml)

        # install the panels
        hou.pypanel.installFile(panels_file)

        # NOTE: at this point, the panel interfaces are installed. In Houdini
        # 15, the 'panetab' menu setting in the xml file will cause the panels
        # to appear like all the other panels in the pane menu. In versions
        # prior to 15, the panel interfaces are only available in the Python
        # Panel. Because of this, in Houdini 15, a user will have access to the
        # registered panels immediately and everyone else will need to click 
        # the menu item or shelf button to show a panel.

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

        :param engine: The engine to return registered commands for

        NOTE: This method currently returns additional panel commands that are
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

def get_registered_panels(engine):
    """Returns a list of AppCommands for the engine's registered panels.

        :param engine: The engine to return registered panel commands for
    """

    panels = []
    for (panel_name, panel_details) in engine.panels.items():
        panels.append(AppCommand(panel_name, panel_details))
    return panels

def get_wrapped_panel_widget(engine, widget_class, bundle, title):
    """Returns a wrapped widget for use in a houdini python panel.

    :param engine: The engine instance.
    :param widget_class: The widget class to wrap.
    :param bundle: The bundle associated with the panel being wrapped.
    :param title: The title to display for this panel.

    Here we subclass the panel widget in order to hijack the first paint event.
    There, we force clear the parent's stylesheet and reset the widget with the
    bundled stylesheet if there is one. This prevents houdini's parenting from
    cramping the panel's style. We also filter for change events to detect when
    something else attempts to change the style so we can force it back to the
    bundled style. The first paint event isn't sufficient for panels saved in
    desktops, but detecting style change seems to do the trick.

    """

    from tank.platform.qt import QtCore

    # the wrapper
    class PanelWrapper(widget_class):
    
        def __init__(self, *args, **kwargs):
            super(PanelWrapper, self).__init__(*args, **kwargs)
            self._stylesheet_applied = False
            self._changing_stylesheet = False
            self.installEventFilter(self)
    
        def eventFilter(self, obj, event):

            # style change, we need to re-apply our own style
            if event.type() == QtCore.QEvent.StyleChange:
                if not self._changing_stylesheet:
                    self._stylesheet_applied = False

            # if we're about to paint, see if we need to re-apply the style
            elif event.type() == QtCore.QEvent.Paint:
                if not self._stylesheet_applied:
                    self._apply_stylesheet()

            return False

        def _apply_stylesheet(self):

            self._changing_stylesheet = True
            try:
                if self.parent():
                    self.parent().setStyleSheet("")
                engine._apply_external_styleshet(bundle, self)
            except Exception:
                engine.log_warning(
                    "Unable to re-apply stylesheet for panel: %s" % (title,)
                )
            finally:
                self._changing_stylesheet = False
            self._stylesheet_applied = True

    return PanelWrapper()

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

# The code that is stored in the python panel interfaces. 
_g_panel_script = \
"""
from PySide import QtGui

from tank.platform.qt import QtCore

class NoPanelWidget(QtGui.QWidget):
    
    def __init__(self, msg, error=None):
    
        super(NoPanelWidget, self).__init__()

        sg_icon_path = '%s'
        sg_icon = QtGui.QLabel()

        try:
            sg_pixmap = QtGui.QPixmap(sg_icon_path).scaledToWidth(64, QtCore.Qt.SmoothTransformation)
            sg_icon.setPixmap(sg_pixmap)
        except:
            pass

        msg_lbl = QtGui.QLabel(msg) 
        msg_lbl.setWordWrap(True)

        if error:
            error_txt = QtGui.QTextEdit(error)
            error_txt.setReadOnly(True)

        h_layout = QtGui.QHBoxLayout()
        h_layout.setSpacing(5)
        h_layout.addWidget(sg_icon)
        h_layout.addWidget(msg_lbl)
        h_layout.setStretchFactor(msg_lbl, 10)
    
        v_layout = QtGui.QVBoxLayout(self)
        v_layout.setContentsMargins(10, 10, 10, 10)
        v_layout.setSpacing(15)
        v_layout.addStretch()
        v_layout.addLayout(h_layout)
        if error:
            v_layout.addWidget(error_txt)
        v_layout.addStretch()

def createInterface():

    try:
        import tank.platform.engine
    except ImportError:    
        return NoPanelWidget(
            "It looks like you're running Houdini outside of a Shotgun "
            "context. Next time you launch Houdini from within a Shotgun "
            "context, you will see the '%s' here."
        )

    try:
        engine = tank.platform.engine.current_engine()
        panel_info = engine.get_panel_info('%s')
        panel_widget = engine.get_wrapped_panel_widget(
            engine,
            panel_info['widget_class'],
            panel_info['bundle'],
            panel_info['title'],
        )
    except Exception:
        import traceback
        return NoPanelWidget(
            "There was a problem loading this panel! The error message "
            "is provided below.",
            error=traceback.format_exc()
        )

    pane_tab = kwargs["paneTab"]
    if pane_tab:
        pane_tab.setLabel(panel_info['title'])
        pane_tab.setName(panel_info['id'])

    return panel_widget

"""

