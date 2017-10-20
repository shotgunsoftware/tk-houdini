# Copyright (c) 2017 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import hou
import sgtk

HookBaseClass = sgtk.get_hook_baseclass()

# A dict of dicts organized by category, type and output file parm
_HOUDINI_OUTPUTS = {
    # rops
    hou.ropNodeTypeCategory(): {
        "alembic": "filename",    # alembic cache
        "comp": "copoutput",      # composite
        "ifd": "vm_picture",      # mantra render node
        "opengl": "picture",      # opengl render
        "wren": "wr_picture",     # wren wireframe
    },
}


class HoudiniSessionCollector(HookBaseClass):
    """
    Collector that operates on the current houdini session. Should inherit from
    the basic collector hook.
    """

    @property
    def settings(self):
        """
        Dictionary defining the settings that this collector expects to receive
        through the settings parameter in the process_current_session and
        process_file methods.

        A dictionary on the following form::

            {
                "Settings Name": {
                    "type": "settings_type",
                    "default": "default_value",
                    "description": "One line description of the setting"
            }

        The type string should be one of the data types that toolkit accepts as
        part of its environment configuration.
        """

        # grab any base class settings
        collector_settings = super(HoudiniSessionCollector, self).settings or {}

        # settings specific to this collector
        houdini_session_settings = {
            "Work Template": {
                "type": "template",
                "default": None,
                "description": "Template path for artist work files. Should "
                               "correspond to a template defined in "
                               "templates.yml. If configured, is made available"
                               "to publish plugins via the collected item's "
                               "properties. ",
            },
        }

        # update the base settings with these settings
        collector_settings.update(houdini_session_settings)

        return collector_settings

    def process_current_session(self, settings, parent_item):
        """
        Analyzes the current Houdini session and parents a subtree of items
        under the parent_item passed in.

        :param dict settings: Configured settings for this collector
        :param parent_item: Root item instance
        """
        # create an item representing the current houdini session
        item = self.collect_current_houdini_session(settings, parent_item)

        # remember if we collect any alembic/mantra nodes
        self._alembic_nodes_collected = False
        self._mantra_nodes_collected = False

        # methods to collect tk alembic/mantra nodes if the app is installed
        self.collect_tk_alembicnodes(item)
        self.collect_tk_mantranodes(item)

        # collect other, non-toolkit outputs to present for publishing
        self.collect_node_outputs(item)

    def collect_current_houdini_session(self, settings, parent_item):
        """
        Creates an item that represents the current houdini session.

        :param dict settings: Configured settings for this collector
        :param parent_item: Parent Item instance

        :returns: Item of type houdini.session
        """

        publisher = self.parent

        # get the path to the current file
        path = hou.hipFile.path()

        # determine the display name for the item
        if path:
            file_info = publisher.util.get_file_path_components(path)
            display_name = file_info["filename"]
        else:
            display_name = "Current Houdini Session"

        # create the session item for the publish hierarchy
        session_item = parent_item.create_item(
            "houdini.session",
            "Houdini File",
            display_name
        )

        # get the icon path to display for this item
        icon_path = os.path.join(
            self.disk_location,
            os.pardir,
            "icons",
            "houdini.png"
        )
        session_item.set_icon_from_path(icon_path)

        # if a work template is defined, add it to the item properties so that
        # it can be used by attached publish plugins
        work_template_setting = settings.get("Work Template")
        if work_template_setting:
            work_template = publisher.engine.get_template_by_name(
                work_template_setting.value)

            # store the template on the item for use by publish plugins. we
            # can't evaluate the fields here because there's no guarantee the
            # current session path won't change once the item has been created.
            # the attached publish plugins will need to resolve the fields at
            # execution time.
            session_item.properties["work_template"] = work_template
            self.logger.debug(
                "Work template defined for Houdini collection.")

        self.logger.info("Collected current Houdini session")
        return session_item

    def collect_node_outputs(self, parent_item):
        """
        Creates items for known output nodes

        :param parent_item: Parent Item instance
        """

        for node_category in _HOUDINI_OUTPUTS:
            for node_type in _HOUDINI_OUTPUTS[node_category]:

                if node_type == "alembic" and self._alembic_nodes_collected:
                    self.logger.debug(
                        "Skipping regular alembic node collection since tk "
                        "alembic nodes were collected. "
                    )
                    continue

                if node_type == "ifd" and self._mantra_nodes_collected:
                    self.logger.debug(
                        "Skipping regular mantra node collection since tk "
                        "mantra nodes were collected. "
                    )
                    continue

                path_parm_name = _HOUDINI_OUTPUTS[node_category][node_type]

                # get all the nodes for the category and type
                nodes = hou.nodeType(node_category, node_type).instances()

                # iterate over each node
                for node in nodes:

                    # get the evaluated path parm value
                    path = node.parm(path_parm_name).eval()

                    # ensure the output path exists
                    if not os.path.exists(path):
                        continue

                    self.logger.info(
                        "Processing %s node: %s" % (node_type, node.path()))

                    # allow the base class to collect and create the item. it
                    # should know how to handle the output path
                    item = super(HoudiniSessionCollector, self)._collect_file(
                        parent_item,
                        path,
                        frame_sequence=True
                    )

                    # the item has been created. update the display name to
                    # include the node path to make it clear to the user how it
                    # was collected within the current session.
                    item.name = "%s (%s)" % (item.name, node.path())

    def collect_tk_alembicnodes(self, parent_item):
        """
        Checks for an installed `tk-houdini-alembicnode` app. If installed, will
        search for instances of the node in the current session and create an
        item for each one with an output on disk.

        :param parent_item: The item to parent new items to.
        """

        publisher = self.parent
        engine = publisher.engine

        alembicnode_app = engine.apps.get("tk-houdini-alembicnode")
        if not alembicnode_app:
            self.logger.debug(
                "The tk-houdini-alembicnode app is not installed. "
                "Will not attempt to collect those nodes."
            )
            return

        try:
            tk_alembic_nodes = alembicnode_app.get_nodes()
        except AttributeError, e:
            self.logger.warning(
                "Unable to query the session for tk-houdini-alembicnode "
                "instances. It looks like perhaps an older version of the "
                "app is in use which does not support querying the nodes. "
                "Consider updating the app to allow publishing their outputs."
            )
            return

        # retrieve the work file template defined by the app. we'll set this
        # on the collected alembicnode items for use during publishing.
        work_template = alembicnode_app.get_work_file_template()

        for node in tk_alembic_nodes:

            out_path = alembicnode_app.get_output_path(node)

            if not os.path.exists(out_path):
                continue

            self.logger.info(
                "Processing sgtk_alembic node: %s" % (node.path(),))

            # allow the base class to collect and create the item. it
            # should know how to handle the output path
            item = super(HoudiniSessionCollector, self)._collect_file(
                parent_item, out_path)

            # the item has been created. update the display name to
            # include the node path to make it clear to the user how it
            # was collected within the current session.
            item.name = "%s (%s)" % (item.name, node.path())

            if work_template:
                item.properties["work_template"] = work_template

            self._alembic_nodes_collected = True

    def collect_tk_mantranodes(self, parent_item):
        """
        Checks for an installed `tk-houdini-mantranode` app. If installed, will
        search for instances of the node in the current session and create an
        item for each one with an output on disk.

        :param parent_item: The item to parent new items to.
        """

        publisher = self.parent
        engine = publisher.engine

        mantranode_app = engine.apps.get("tk-houdini-mantranode")
        if not mantranode_app:
            self.logger.debug(
                "The tk-houdini-mantranode app is not installed. "
                "Will not attempt to collect those nodes."
            )
            return

        try:
            tk_mantra_nodes = mantranode_app.get_nodes()
        except AttributeError, e:
            self.logger.warning(
                "Unable to query the session for tk-houdini-mantranode "
                "instances. It looks like perhaps an older version of the "
                "app is in use which does not support querying the nodes. "
                "Consider updating the app to allow publishing their outputs."
            )
            return

        # retrieve the work file template defined by the app. we'll set this
        # on the collected alembicnode items for use during publishing.
        work_template = mantranode_app.get_work_file_template()

        for node in tk_mantra_nodes:

            out_path = mantranode_app.get_output_path(node)

            if not os.path.exists(out_path):
                continue

            self.logger.info(
                "Processing sgtk_mantra node: %s" % (node.path(),))

            # allow the base class to collect and create the item. it
            # should know how to handle the output path
            item = super(HoudiniSessionCollector, self)._collect_file(
                parent_item,
                out_path,
                frame_sequence=True
            )

            # the item has been created. update the display name to
            # include the node path to make it clear to the user how it
            # was collected within the current session.
            item.name = "%s (%s)" % (item.name, node.path())

            if work_template:
                item.properties["work_template"] = work_template

            self._mantra_nodes_collected = True
