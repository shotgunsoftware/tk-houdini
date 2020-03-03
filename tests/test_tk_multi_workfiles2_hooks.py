# Copyright (c) 2019 Shotgun Software Inc.
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

# Required so that the SHOTGUN_HOME env var will be set
from tank_test.tank_test_base import setUpModule  # noqa

from test_hooks_base import TestHooks

import sgtk


class TestWorkfiles2Hooks(TestHooks):
    """
    Tests the workfiles2 hooks.
    """

    def setUp(self):
        super(TestWorkfiles2Hooks, self).setUp()

        # Now get the app and run the reset operation.
        self.app = self.engine.apps["tk-multi-workfiles2"]
        self.scene_operation = self.app.import_module(
            "tk_multi_workfiles"
        ).scene_operation

    # def test_reset(self):
    #     sgtk.platform.change_context(self._asset_task_ctx)

    def test_reset(self):

        # Create a temporary scene file, so we can test the reset works.
        created_file = self._create_file("temp.hip")
        # Make sure the scene file we created matches what Houdini believes to be the scene file.
        self.assertEqual(hou.hipFile.name(), created_file)

        result = self.scene_operation.reset_current_scene(
            self.app, self.scene_operation.NEW_FILE_ACTION, self.engine.context
        )
        self.assertTrue(result)
        # When we reset the file name should be untitled.hip
        self.assertEqual(hou.hipFile.name(), "untitled.hip")

    def test_get_current_path(self):

        # Create a temporary scene file, so we can test the reset works.
        created_file = self._create_file("temp.hip")
        # Make sure the scene file we created matches what Houdini believes to be the scene file.
        self.assertEqual(hou.hipFile.name(), created_file)

        result = self.scene_operation.get_current_path(
            self.app, self.scene_operation.NEW_FILE_ACTION, self.engine.context
        )
        self.assertEqual(hou.hipFile.name(), result)

    def test_prepare_new_scene(self):
        # The Houdini hook doesn't implement any code for the prepare_new_scene operation, so
        # it should just return None and not fail.
        result = self.scene_operation.prepare_new_scene(
            self.app, self.scene_operation.NEW_FILE_ACTION, self.engine.context
        )
        self.assertEqual(result, None)

    def test_save_file(self):
        save_path = self._get_new_file_path("cat.hip")

        # test saving a new file.
        result = self.scene_operation.save_file(
            self.app,
            self.scene_operation.NEW_FILE_ACTION,
            self.engine.context,
            path=save_path,
        )
        self.assertEqual(result, save_path)
        self.assertEqual(result, hou.hipFile.name())

        # Now test saving over the same file.
        self.scene_operation.save_file(
            self.app, self.scene_operation.NEW_FILE_ACTION, self.engine.context
        )
