# Copyright (c) 2019 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import pytest
import hou

# Required so that the SHOTGUN_HOME env var will be set
from tank_test.tank_test_base import setUpModule  # noqa

from test_hooks_base import TestHooks
from sgtk.util import ShotgunPath


class TestWorkfiles2Hooks(TestHooks):
    """
    Tests the workfiles2 hooks.
    """

    def setUp(self):
        super(TestWorkfiles2Hooks, self).setUp()

        if not self.engine.has_ui:
            self.tearDown()
            pytest.skip("Requires a UI.")

        # Now get the app and run the reset operation.
        self.app = self.engine.apps["tk-multi-workfiles2"]
        self.scene_operation = self.app.import_module(
            "tk_multi_workfiles"
        ).scene_operation

    def test_reset(self):
        """
        Tests the scene operation hooks reset operation.
        """
        # Create a temporary scene file, so we can test the reset works.
        created_file = self._create_file("temp")
        # Make sure the scene file we created matches what Houdini believes to be the scene file.
        self.assertEqual(
            ShotgunPath.from_current_os_path(hou.hipFile.name()),
            ShotgunPath.from_current_os_path(created_file),
        )

        result = self.scene_operation.reset_current_scene(
            self.app, self.scene_operation.NEW_FILE_ACTION, self.engine.context
        )
        self.assertTrue(result)
        # When we reset the file name should be untitled.hip
        self.assertEqual(
            ShotgunPath.from_current_os_path(hou.hipFile.name()),
            ShotgunPath.from_current_os_path("untitled.hip"),
        )

    def test_get_current_path(self):
        """
        Tests the scene operation hooks current_path operation.
        """

        # Create a temporary scene file, so we can test that we can get the current path to it.
        created_file = self._create_file("temp")
        # Make sure the scene file we created matches what Houdini believes to be the scene file.
        self.assertEqual(hou.hipFile.name(), created_file)

        result = self.scene_operation.get_current_path(
            self.app, self.scene_operation.NEW_FILE_ACTION, self.engine.context
        )
        self.assertEqual(
            ShotgunPath.from_current_os_path(hou.hipFile.name()),
            ShotgunPath.from_current_os_path(result),
        )

    def test_prepare_new_scene(self):
        """
        Tests the scene operation hooks prepare_new operation.
        The Houdini hook doesn't implement any code for the prepare_new_scene operation, so
        it should just return None and not fail.
        """

        result = self.scene_operation.prepare_new_scene(
            self.app, self.scene_operation.NEW_FILE_ACTION, self.engine.context
        )
        self.assertEqual(result, None)

    def test_save_file(self):
        """
        Tests the scene operation hooks save operation.
        """

        save_path = self._get_new_file_path("work_path", "cat")

        # test saving a new file.
        self.scene_operation.save_file(
            self.app,
            self.scene_operation.NEW_FILE_ACTION,
            self.engine.context,
            path=save_path,
        )
        self.assertEqual(
            ShotgunPath.from_current_os_path(save_path),
            ShotgunPath.from_current_os_path(hou.hipFile.name()),
        )

        # Now test saving over the same file.
        self.scene_operation.save_file(
            self.app, self.scene_operation.NEW_FILE_ACTION, self.engine.context
        )

    def test_open_file(self):
        """
        Tests the scene operation hooks open operation.
        """

        created_file = self._create_file("dog")

        # Reset the scene so it is empty in preparation for opening the file we just saved.
        self._reset_scene()

        self.scene_operation.open_file(
            self.app,
            self.scene_operation.NEW_FILE_ACTION,
            self.engine.context,
            created_file,
            1,
            False,
        )

        self.assertEqual(
            ShotgunPath.from_current_os_path(created_file),
            ShotgunPath.from_current_os_path(hou.hipFile.name()),
        )
