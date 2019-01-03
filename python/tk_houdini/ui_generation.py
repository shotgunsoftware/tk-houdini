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

# Make sure we always give Houdini forward-slash-delimited paths. There is
# a crash bug in early releases of H17 on Windows when it's given backslash
# paths to read.
g_menu_item_script = os.path.join(
    os.path.dirname(__file__),
    "menu_action.py"
).replace(os.path.sep, "/")

# #3716 Fixes UNC problems with menus. Prefix '\' are otherwise concatenated to a single character, therefore using '/' instead.
g_menu_item_script = g_menu_item_script.replace("\\", "/")

# global used to indicate that the file change time has been initialized and
# started
g_file_change_timer = None

# stores the path of the current file for use by the file change timeout callback
g_current_file = None

class AppCommandsUI(object):
    """Base class for interface elements that trigger command actions."""

    def __init__(self, engine, commands):
        self._engine = engine
        self._commands = commands

    def _get_context_name(self):
        """Returns a display name for the current context"""

        # these objects don't persist across context switches, so we should
        # only need to construct the context name once. if the engine is
        # changed to not do a full restart on context switch, then this will
        # not be the case.
        if not hasattr(self, '_context_name'):
            self._context_name = str(self._engine.context)

        return self._context_name

    def _group_commands(self):
        """ This method provides a consistent method for organizing commands.

        Used by the menu and shelf classes to collect the registered commands
        into groups. The method returns a tuple with the first item being
        a list of context-specific commands, the second item is a dictionary
        of commands organized by the app name, and the third item is a list
        of favourite commands as defined in the settings.

        """

        # should only need to group them once. this object won't persist across
        # context switches. if the engine changes to not do a full restart on
        # context switch, then this will need to change.
        if not hasattr(self, '_grouped_commands'):

            favourite_cmds = []
            context_cmds = []
            cmds_by_app = {}

            # favourites
            for fav in self._engine.get_setting("menu_favourites"):
                app_instance_name = fav["app_instance"]
                menu_name = fav["name"]

                for cmd in self._commands:
                    if (cmd.get_app_instance_name() == app_instance_name and \
                        cmd.name == menu_name):
                        cmd.favourite = True
                        favourite_cmds.append(cmd)

            # this is how the original, static menu logic worked for grouping
            # commands in the Shotgun menu in houdini. it was moved here so
            # that it could be used by the dynamic menu in houdini 15+ as well
            # as the Shotgun shelf.  Basically, make a list of context-based
            # commands and a dictionary of app-specific commands organized by
            # app name.
            for cmd in self._commands:
                if cmd.get_type() == "context_menu":
                    context_cmds.append(cmd)
                else:
                    app_name = cmd.get_app_name()
                    if app_name is None:
                        app_name = "Other Items"
                    cmds_by_app.setdefault(app_name, []).append(cmd)

            self._engine.logger.debug("Grouped registered commands.")
            self._grouped_commands = (context_cmds, cmds_by_app, favourite_cmds)

        return self._grouped_commands

class AppCommandsMenu(AppCommandsUI):

    def __init__(self, engine, commands):
        super(AppCommandsMenu, self).__init__(engine, commands)

        # this will hold an exception raised during menu creation for dynamic
        # menus. having this allows for the ability to display a clickable 
        # error message in the menu rather than relying on houdini to display
        # a scarier looking error dialog.
        self._menu_error = None

        # used by the dynamic menu to map an additional, non-registered command
        # back to a callback. See additional comments in the
        # _get_context_commands method.
        self._context_menu_item_id = None

    def create_menu(self, xml_path):
        """ Create the Shotgun Menu """

        import hou

        # houdini 15+ allows for dynamic menu creation, so do that if possible.
        # otherwise, fallback to the static menu
        if hou.applicationVersion()[0] >= 15:
            self._engine.logger.debug("Constructing dynamic Shotgun menu.")
            self._create_dynamic_menu(xml_path)
        else:
            self._engine.logger.debug("Constructing static Shotgun menu.")
            self._create_static_menu(xml_path)

    def _get_context_commands(self):
        """This method returns a modified list of context commands.
        
        This is called directly as a part of the dynamic menu generation code
        as houdini builds submenus when the user clicks on the top-level
        Shotgun menu. This should execute quickly.
        
        """

        # only need to do this once since the menu object doesn't persist
        # across context switches. using the cached values is important since
        # the dynamic menu is rebuilt on each click.
        if not hasattr(self, '_context_commands'):

            # get the registered commands, grouped in the usual way.
            (context_cmds, cmds_by_app, favourite_cmds) = self._group_commands()

            # ideally we'd mimic the static menu and have a context item 
            # that contained a submenu with context-specific commands. this
            # doesn't seem to be possible with the dynamic menus, so instead
            # we create an extra command in the "Current Context" menu that 
            # has the context name and, when clicked, opens the context in
            # Shotgun in the browser. 
            context_cmd = AppCommand(
                name=self._get_context_name(),
                command_dict={
                 'properties': {
                  'description': "Displays the current context, jumps to SG.",
                  'type': "context_menu",
                 },
                 'callback': lambda: None,
                },
            )

            # the context command won't be available in the callback map of
            # the engine since it isn't registered. we don't want to register
            # it because it is specific to the dynamic menu. 
            self._context_menu_item_id = context_cmd.get_id()

            # create the full list
            cmds = [context_cmd]
            cmds.extend(context_cmds)

            self._engine.logger.debug(
                "Collected context commands for dynamic menu.")
            self._context_commands = cmds

        return self._context_commands

    def _get_commands_by_app(self):
        """This method returns a flattened list of registered app commands.
        
        This is called directly as a part of the dynamic menu generation code
        as houdini builds submenus when the user clicks on the top-level
        Shotgun menu. This should execute quickly.
        
        """

        # only need to do this once since the menu object doesn't persist
        # across context switches. using the cached values is important since
        # the dynamic menu is rebuilt on each click.
        if not hasattr(self, '_commands_by_app'):

            (context_cmds, cmds_by_app, favourite_cmds) = self._group_commands()

            cmds = favourite_cmds

            # get the grouped commands, then flatten it out into a list
            for app_name in cmds_by_app.keys():
                for cmd in cmds_by_app[app_name]:
                    if not cmd.favourite:
                        cmds.append(cmd)

            self._engine.logger.debug("Collected app commands for dynamic menu.")
            self._commands_by_app = cmds

        return self._commands_by_app

    def _build_shotgun_menu_item(self):
        """Constructs a top-level "Shotgun" menu.
        
        Same logic for both the static and dynamic menu.

        :returns: tuple containing the root element and the shotgun menu item
        
        """

        root = ET.Element("mainMenu")
        menubar = ET.SubElement(root, "menuBar")
        shotgun_menu = self._menuNode(menubar, "Shotgun", "tk.shotgun")
        insert_before = ET.SubElement(shotgun_menu, "insertBefore")
        insert_before.text = "help_menu"

        # make sure the Help menu still comes last
        modify_item = ET.SubElement(menubar, "modifyItem")
        modify_item.set("id", "help_menu")
        ET.SubElement(modify_item, "insertAfter")

        return (root, shotgun_menu)

    def _create_dynamic_menu(self, xml_path):
        """Construct the dynamic Shotgun menu for toolkit in Houdini 15+.
        
        :param xml_path: The path to the xml file to store the menu definitions 
        
        """

        # documentation on the dynamic menu xml tags can be found here:
        # http://www.sidefx.com/docs/houdini15.0/basics/config_menus
        
        # build the Shotgun menu
        (root, shotgun_menu) = self._build_shotgun_menu_item()
        
        # add the context menu
        context_menu = self._menuNode(shotgun_menu, "Current Context",
            "tk.context.menu")
        ET.SubElement(shotgun_menu, "separatorItem")

        context_dynamic_menu = ET.SubElement(context_menu,
            "scriptMenuStripDynamic")
        context_dynamic_menu.set("id", "tk.context_dynamic_menu")

        # here we build an element that stores a python script for returning
        # the ids and names of context menu items. the code is executed each
        # time the menu is built.
        context_dynamic_menu_contents = ET.SubElement(context_dynamic_menu,
            "contentsScriptCode")
        context_dynamic_menu_contents.text = \
            "CDATA_START" + \
                _g_dynamic_menu_names % ('_get_context_commands',) + \
            "CDATA_END"

        # this element defines a python script that has access to the id of the
        # menu selected by the user (as defined in the previous element).  this
        # script uses the id to determine the command and callback execute.
        context_dynamic_menu_script = ET.SubElement(context_dynamic_menu,
            "scriptCode")
        context_dynamic_menu_script.text = \
            "CDATA_START" + _g_dynamic_menu_script + "CDATA_END"

        main_dynamic_menu = ET.SubElement(shotgun_menu,
            "scriptMenuStripDynamic")
        main_dynamic_menu.set("id", "tk.main_dynamic_menu")

        # similar to the dynamic context menu. this time we format the python
        # script to call the method to return the app specific commands.
        main_dynamic_menu_contents = ET.SubElement(main_dynamic_menu,
            "contentsScriptCode")
        main_dynamic_menu_contents.text = \
            "CDATA_START" + \
                _g_dynamic_menu_names % ('_get_commands_by_app',) + \
            "CDATA_END"

        # same script as the context menu for mapping ids to callbacks for
        # execution
        main_dynamic_menu_script = ET.SubElement(main_dynamic_menu,
            "scriptCode")
        main_dynamic_menu_script.text = \
            "CDATA_START" + _g_dynamic_menu_script + "CDATA_END"

        # format the xml and write it to disk
        xml = _format_xml(ET.tostring(root, encoding="UTF-8"))
        _write_xml(xml, xml_path)
        self._engine.logger.debug("Dynamic menu written to: %s" % (xml_path,))

    def _create_static_menu(self, xml_path):
        """Construct the static Shotgun menu for older versions of Houdini.
        
        :param xml_path: The path to the xml file to store the menu definitions 

        """

        # documentation on the static menu xml tags can be found here:
        # http://www.sidefx.com/docs/houdini15.0/basics/config_menus

        # build the Shotgun menu
        (root, shotgun_menu) = self._build_shotgun_menu_item()
        
        # create the menu object
        ctx_name = self._get_context_name()
        ctx_menu = self._menuNode(shotgun_menu, ctx_name, "tk.context")
        ET.SubElement(ctx_menu, "separatorItem")

        (context_cmds, cmds_by_app, favourite_cmds) = self._group_commands()

        # favourites
        ET.SubElement(shotgun_menu, "separatorItem")
        for cmd in favourite_cmds:
            self._itemNode(shotgun_menu, cmd.name, cmd.get_id())

        # everything else
        ET.SubElement(shotgun_menu, "separatorItem")

        # add the context menu items
        for cmd in context_cmds:
            self._itemNode(ctx_menu, cmd.name, cmd.get_id())
            
        # build the main app-centric menu
        for app_name in sorted(cmds_by_app.keys()):
            cmds = cmds_by_app[app_name]
            if len(cmds) > 1:
                menu = self._menuNode(shotgun_menu, app_name,
                    "tk.%s" % app_name.lower())
                for cmd in cmds:
                    self._itemNode(menu, cmd.name, cmd.get_id())
            else:
                if not cmds[0].favourite:
                    self._itemNode(shotgun_menu, cmds[0].name, cmds[0].get_id())

        # format the xml and write it to disk
        xml = _format_xml(ET.tostring(root, encoding="UTF-8"))
        _write_xml(xml, xml_path)
        self._engine.logger.debug("Static menu written to: %s" % (xml_path,))

    def _menuNode(self, parent, label, id):
        """Constructs a submenu for the supplied parent."""

        menu = ET.SubElement(parent, "subMenu")
        menu.set("id", id)
        node = ET.SubElement(menu, "label")
        node.text = label
        return menu

    def _itemNode(self, parent, label, id):
        """Constructs a static menu item for the supplied parent.

        Adds the script path and args which houdini uses as the callback.

        """

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

        for panel_cmd in self._panel_commands:
            panel_info = self._engine.get_panel_info(panel_cmd.name)

            interface = ET.SubElement(root, "interface")
            interface.set('name', panel_cmd.name)
            interface.set('label', panel_info["title"])

            icon = panel_cmd.get_icon()
            if icon:
                interface.set('icon', icon)

            doc_url = panel_cmd.get_documentation_url_str()
            if not doc_url:
                doc_url = ""
            interface.set('help_url', doc_url)

            script = ET.SubElement(interface, "script")
            script_code = _g_panel_script % (
                icon,
                panel_info["title"],
                panel_cmd.name
            )
            script.text = "CDATA_START" + script_code + "CDATA_END"

            desc = panel_cmd.get_description()
            if not desc:
                desc = ""

            panel_help = ET.SubElement(interface, "help")
            panel_help.text = "CDATA_START" + desc + "CDATA_END"
            panel_help.text = desc

            # add the panel to the panetab and toolbar menus
            panetab_menu = ET.SubElement(interface, "includeInPaneTabMenu")
            panetab_menu.set("menu_position", "300")
            panetab_menu.set("create_separator", "false")

            toolbar_menu = ET.SubElement(interface, "includeInToolbarMenu")
            toolbar_menu.set("menu_position", "300")
            toolbar_menu.set("create_separator", "false")

        xml = _format_xml(ET.tostring(root, encoding="UTF-8"))
        _write_xml(xml, panels_file)
        self._engine.logger.debug("Panels written to: %s" % panels_file)

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
            self._engine.logger.debug("Using existing shelf.")
            self._engine.logger.debug("  Setting shelf file: %s" % shelf_file)
            shelf.setFilePath(shelf_file)
        else:
            self._engine.logger.debug("Creating new shelf: %s" % self._name)
            shelf = hou.shelves.newShelf(
                file_path=shelf_file,
                name=self._name,
                label=self._label
            )

        shelf_tools = []
        cmds_by_app = {}

        (context_cmds, cmds_by_app, favourite_cmds) = self._group_commands()

        # add the context menu tools first
        for cmd in context_cmds:
            tool = self.create_tool(shelf_file, cmd)
            shelf_tools.append(tool)

        # now add the favourites
        for cmd in favourite_cmds:
            tool = self.create_tool(shelf_file, cmd)
            shelf_tools.append(tool)

        # create tools for the remaining commands
        for app_name in sorted(cmds_by_app.keys()):
            for cmd in cmds_by_app[app_name]:
                if not cmd.favourite:
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

        self._engine.logger.debug("Creating tool: %s" % cmd.name)
        tool = hou.shelves.newTool(
            file_path=shelf_file,
            name=cmd.name.replace(" ", "_"),
            label=cmd.name,
            script=_g_launch_script % cmd.get_id(),
            #help=cmd.get_description(),
            #help_url=cmd.get_documentation_url_str(),
            icon=cmd.get_icon()
        )
        # NOTE: there seems to be a bug in houdini where the 'help' does
        # not display in the tool's tooltip even though the tool's help
        # string is clearly populated in the tool when you edit it in the
        # ui. It is also causing popup errors related to getParsedTooltip
        # in some builds. Leaving it commented out until this is fixed by
        # SESI.
        # NOTE: Commenting out help_url due to apparent Houdini bug whereby
        # empty url results in a ValueError on first mouseover. zd37814

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

        self._engine.logger.debug("Destroying shelf: %s" % shelf.name())
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
            self._engine.logger.debug("Destroying tool: %s" % tool.name())
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

        icon_path = None

        if "icon" in self.properties:
            icon_path = self.properties["icon"]
        elif "app" in self.properties:
            icon_path = self.properties["app"].descriptor.get_icon_256()

        if icon_path:
            # houdini required "/" for UNC paths instead of "\\".
            icon_path = icon_path.replace("\\", "/")

        return icon_path

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

    commands = []

    sg_icon = engine._safe_path_join(engine.disk_location, "resources",
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

    commands.append(jump_to_sg_cmd)

    if engine.context.filesystem_locations:
        # Only show the jump to fs command if there are folders on disk.

        fs_icon = engine._safe_path_join(engine.disk_location, "resources",
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

        commands.append(jump_to_fs_cmd)

    for (cmd_name, cmd_details) in engine.commands.items():
        commands.append(AppCommand(cmd_name, cmd_details))
    return commands


def ensure_file_change_timer_running():
    """
    Ensures a timer is running to periodically check for current file change.

    """

    # do nothing if it is already running
    global g_file_change_timer
    if g_file_change_timer:
        return

    import hou
    import sgtk
    from sgtk.platform.qt import QtCore

    global g_current_file
    g_current_file = hou.hipFile.path()

    # start up a timer to execute a callback to check for current file changes
    g_file_change_timer = QtCore.QTimer()
    g_file_change_timer.timeout.connect(_on_file_change_timeout)
    g_file_change_timer.start(1000)


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
                    self.apply_stylesheet()

            return False

        def apply_stylesheet(self):
            import hou
            self._changing_stylesheet = True
            try:
                # This is only safe in pre-H16. If we do this in 16 it destroys
                # some styling in Houdini itself.
                if self.parent() and hou.applicationVersion() < (16, 0, 0):
                    self.parent().setStyleSheet("")

                engine._apply_external_styleshet(bundle, self)

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
                if hou.applicationVersion() >= (16, 0, 0):
                    qss_file = engine._get_engine_qss_file()
                    with open(qss_file, "rt") as f:
                        qss_data = f.read()
                        qss_data = engine._resolve_sg_stylesheet_tokens(qss_data)
                        qss_data = qss_data.replace("{{ENGINE_ROOT_PATH}}", engine._get_engine_root_path())
                        self.setStyleSheet(self.styleSheet() + qss_data)
                        self.update()

                    # We have some funky qss behavior in H16 that requires us to
                    # kick the parent's stylesheet by reassigning it as is. Not
                    # sure what causes the problem, but this does resolve it. The
                    # original symptoms were some widgets not changing after applying
                    # the engine's stylesheet, while others did.
                    if self.parent():
                        self.parent().setStyleSheet(self.parent().styleSheet())
            except Exception, e:
                engine.logger.warning(
                    "Unable to re-apply stylesheet for panel: %s %s" % (title, e)
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
            engine.logger.error("Failed to launch '%s'!" % cmd)

def _format_xml(xml):
    """Do any required formatting. Typically before writing to disk."""

    # the xml etree API doesn't seem to have a good way to deal with 
    # CDATA. As a workaround for the menus and shelves, we throw in a string
    # we can replace before writing to disk. Do the replacement here.
    formatted_xml = xml.replace("CDATA_START", "<![CDATA[")
    formatted_xml = formatted_xml.replace("CDATA_END", "]]>")

    return formatted_xml

def _on_file_change_timeout():
    """
    Checks to see if the current file has changed. If it has, try to set the
    new context for the file.
    """

    import hou
    cur_file = hou.hipFile.path()

    global g_current_file
    if cur_file == g_current_file:
        # the current file is the same as it was last time. no file change,
        # no need to proceed
        return

    # update the current file global so that the next timeout won't do anything
    # it isn't supposed to
    g_current_file = cur_file

    # if the file name is untitled.hip, don't automatically destroy the engine.
    # allow the user to continue working in the same context
    file_name = os.path.split(cur_file)[-1]
    if file_name.lower() == "untitled.hip":
        return

    import sgtk
    cur_engine = None

    # attempt to get the current engine and context
    try:
        cur_engine = sgtk.platform.current_engine()
        cur_context = cur_engine.context
        engine_name = cur_engine.name
    except Exception, e:
        engine_name = "tk-houdini"
        cur_context = None

    try:
        tk = sgtk.tank_from_path(cur_file)
    except sgtk.TankError, e:
        # Unable to get tk api instance from the path. won't be able to get a
        # new context. if there is an engine running, destroy it.
        if cur_engine:
            cur_engine.destroy()
        return

    # get the new context from the file
    new_context = tk.context_from_path(cur_file, cur_context)

    # if the contexts are the same, either the user has not changed context or
    # the context change has already been handled, for example by workfiles2
    if cur_context == new_context:
        return

    # try to create new engine
    try:
        if cur_engine:
            sgtk.platform.change_context(new_context)
        else:
            sgtk.platform.start_engine(engine_name, tk, new_context)
    except sgtk.TankEngineInitError, e:
        msg = (
            "There was a problem starting a new instance of the '%s' engine "
            "for context '%s'\n"
            "Error: %s" % (engine_name, new_context, e)
        )
        hou.ui.displayMessage(msg, severity=hou.severityType.Error)
        return

def _write_xml(xml, xml_path):
    """Write the full element tree to the supplied xml file.

    :param string xml: The xml to write to disk
    :param string xml_path: The path to write the xml. 

    Also ensures the directory exists before writing the file.
    
    """

    # ensure the directory exists
    xml_dir = os.path.dirname(xml_path)
    if not os.path.exists(xml_dir):
        os.makedirs(xml_dir)

    # write the xml file
    with open(xml_path, "w") as xml_file_handle:
        xml_file_handle.write(xml)


# -----------------------------------------------------------------------------
# template strings used to populate menu, shelf, and panel scripts

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
from sgtk.platform.qt import QtCore, QtGui

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
            "context, you will see the '%s' panel here."
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
        panel_widget.apply_stylesheet()
    except Exception:
        import traceback
        return NoPanelWidget(
            "There was a problem loading this panel! The error message "
            "is provided below.",
            error=traceback.format_exc()
        )

    pane_tab = kwargs["paneTab"]

    # it appears that sometimes the pane_tab available here is not the one 
    # we're interested in. sometimes it is not set and sometimes it is a 
    # different tab all together. so just check to make sure it is set and 
    # make sure it has the 'setLabel' method available. that at least implies
    # that it is a python panel 
    if pane_tab and hasattr(pane_tab, 'setLabel'):
        title = panel_info.get('title')
        if title:
            pane_tab.setLabel(title)

            # We're caching here based on title, because it's the
            # bit of information we have that's reliably available
            # from all of the various methods of showing this
            # pane tab. We cache the pane tab's name so that if a
            # second invokation of showing this particular panel is
            # triggered, we just show that panel rather than opening
            # a second instance.
            engine._pane_cache[title] = pane_tab.name()

    return panel_widget

"""

# this template is used when building the dynamic menu. it has one placeholder
# for a method to return a list of commands. when executed, this code uses that
# list of commands to populate the Shotgun menu in houdini. houdini expects a
# list of the form [menu_id1, menu_label1, menu_id2, menu_label2, ...]. some
# effort is made to recover gracefully from errors encountered when building
# the dynamic menu. For additional information, see the houdini docs for the
# dynamic menus: http://www.sidefx.com/docs/houdini15.0/basics/config_menus
_g_dynamic_menu_names = \
"""
engine = None
menu_items = []
try:
    import tank.platform.engine
    engine = tank.platform.engine.current_engine()
    if engine:
        # the commands to display in this menu
        cmds = engine._menu.%s()
        # build the list that houdini expects
        for cmd in cmds:
            menu_items.extend([cmd.get_id(), cmd.name])
    else:
        menu_items.extend(["tk.houdini.menu.no.shotgun", "Toolkit is disabled - Click for details"])
except Exception as e:
    import traceback
    error = traceback.format_exc()
    if engine:
        # store the exception on the menu object for display in the callback
        engine._menu._menu_error = Exception(str(e) + ". " + error)
    # just give houdini a special error item for the menu
    menu_items.extend(
        ["tk.houdini.menu.error", "Menu Error. Click for Details..."])
else:
    if engine:
        engine._menu._menu_error = None
finally:
    return menu_items
"""

# this template is used when executing items in the dynamic menu. kwargs are
# available when this runs to access the id selected by the user. the id is 
# used to map back to a callback for the associated command. For additional
# information, see the houdini docs for the dynamic menus:
# http://www.sidefx.com/docs/houdini15.0/basics/config_menus
_g_dynamic_menu_script = \
"""
import hou
engine = None
try:
    import tank.platform.engine
    # get the selected menu id
    command_id = kwargs["selectedtoken"]
    engine = tank.platform.engine.current_engine()
    # special id if there is no shotgun context/engine
    if command_id == "tk.houdini.menu.no.shotgun":
        msg = (
            "It appears as though you are not currenly working in a Shotgun "
            "context. There is no Shotgun for Houdini Engine running so no "
            "menu or shelf items are available. In order to restart the Shotgun "
            "integration, please close and reopen Houdini or choose a file "
            "from your Shotgun project in the 'Recent Files' menu. If you "
            "believe this to be an error, please contact your support team."
        )
        hou.ui.displayMessage(msg, severity=hou.severityType.Warning)
    # special id if errors occured and they clicked for more info
    if command_id == "tk.houdini.menu.error":
        # try to locate the exception on the menu object and raise it
        if engine._menu._menu_error:
            raise engine._menu._menu_error
        # no stored exception, tell the user to look in the shell
        else:
            raise Exception("The error message should show up in your shell.")
    # the special context item. launch the context in browser
    if command_id == engine._menu._context_menu_item_id:
        from tank.platform.qt import QtCore, QtGui
        url = engine.context.shotgun_url
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))
    # should be a registered command. launch it
    else:
        engine.launch_command(command_id)
except Exception as e:
    # handle any exceptions raised during menu building
    msg = "An error occured building the Shotgun menu...\\n\\n%s" % (e,)
    if engine:
        hou.ui.displayMessage(msg, severity=hou.severityType.Error)
    else:
        print msg
"""

