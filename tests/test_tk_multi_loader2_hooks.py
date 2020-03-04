# Copyright (c) 2019 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import hou

# Required so that the SHOTGUN_HOME env var will be set
from tank_test.tank_test_base import setUpModule  # noqa

from test_hooks_base import TestHooks


class TestLoader2Hooks(TestHooks):
    """
    Tests the loader2 hooks.
    """

    def setUp(self):
        super(TestLoader2Hooks, self).setUp()

        # Now get the app and run the reset operation.
        self.app = self.engine.apps["tk-multi-loader2"]

        action_manager_module = self.app.import_module(
            "tk_multi_loader"
        ).loader_action_manager
        self.action_manager = action_manager_module.LoaderActionManager()

    def _generate_actions_for_execution(self, file_path, publish_type, action):
        """
        Generates a list containing one action, in a format that the Loader would usually create internally.
        """
        sg_data = {
            "id": 1,
            "published_file_type": {"type": "PublishedFileType", "name": publish_type},
            "path": {
                "name": "test.hip",
                "url": "file://%s" % file_path,
                "local_storage": {"type": "LocalStorage", "id": 1, "name": "primary"},
                "local_path": file_path,
                "content_type": None,
                "type": "Attachment",
                "id": 1,
                "link_type": "local",
            },
        }
        return [{"sg_publish_data": sg_data, "name": action, "params": None}]

    def _publish_type_actions(self, publish_type):
        """
        Runs the Loader's get actions hook, generating actions for the passed PublishedFileType.
        """
        publish = {
            "published_file_type": {"type": "PublishedFileType", "name": publish_type}
        }
        return self.action_manager._get_actions_for_publish(
            publish, self.action_manager.UI_AREA_MAIN
        )

    def _generate_actions(self, publish_type, action):
        """
        Checks that given a PublishedFileType, it will generate an action that matches the passed action.
        """
        # Test that given a PublishedFileType it will generate a single action for import
        actions = self._publish_type_actions(publish_type)
        self.assertTrue(len(actions) == 1)
        self.assertTrue(actions[0]["name"] == action)

    def test_generate_actions(self):
        """
        Tests that the various default Houdini Loader actions a generated when passed a PublishedFile with the
        appropriate PublishedFileType.
        """
        tests = [
            ("Alembic Cache", "import"),
            ("Houdini Scene", "merge"),
            ("Image", "file_cop"),
        ]
        for pub_type, action in tests:
            # Check that for each Publish type it will generate a single action with the passed name.
            self._generate_actions(pub_type, action)

    def test_execute_merge_action(self):
        """
        Tests merging in a Houdini file action.
        """
        # Create a node in the current scene.
        hou.node("/obj").createNode("geo", "sphere_1")

        # Make sure the node was created.
        self.assertNotEqual(hou.node("/obj/sphere_1"), None)
        # Now save the scene in a file we can later merge in
        file_path = self._create_file("robot")

        # Reset the scene so that we won't get a pop up asking if we want to save changes, when we merge.
        self._reset_scene()

        actions = self._generate_actions_for_execution(
            file_path, "Houdini Scene", "merge"
        )

        self.app.execute_hook_method(
            "actions_hook", "execute_multiple_actions", actions=actions
        )
        # Check the node now exists in the scene
        self.assertNotEqual(hou.node("/obj/sphere_1"), None)

    # TODO: write tests for the import and file_cop actions. Currently these don't work on startup as they require
    #  access to the Houdini panels which are not available on startup with the 123.py
