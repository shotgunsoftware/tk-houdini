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
from sgtk.util import ShotgunPath


class TestSnapShotHooks(TestHooks):
    """
    Tests the tk-multi-snapshot hooks.
    """

    def setUp(self):
        super(TestSnapShotHooks, self).setUp()

        # Now get the app and run the reset operation.
        self.app = self.engine.apps["tk-multi-snapshot"]

    def test_create_snapshot(self):
        """
        Tests getting the current work path and saving a snapshot, using the snapshot app's API.
        """
        # This tests both the saving an getting of the current work path operations in the scene operations hook.

        self._create_file("ufo")

        from sgtk.platform.qt import QtGui

        if self.engine.has_ui:
            thumbnail = QtGui.QPixmap(100, 100)
            thumbnail.fill(QtGui.QColor("red"))
        else:
            thumbnail = None

        # This will trigger the scene operations hook to be called twice, for a current_path, and save operation.
        snapshot_path = self.app.snapshot("my comment", thumbnail)
        self.assertTrue(os.path.exists(snapshot_path))

    def test_load_snapshot(self):
        """
        Tests loading a snapshot, there is no API method for this, so we are calling internal app functions.
        """
        # Create a file for the test to load.
        file_path = self._create_file("banana")
        # Reset the scene so it won't prompt the test to save.
        self._reset_scene()

        handler = self.app.tk_multi_snapshot.Snapshot(self.app)
        handler._do_scene_operation("open", file_path)
        # Now check that the file Houdini has open is the same as the one we originally saved.
        self.assertEqual(
            ShotgunPath.from_current_os_path(file_path),
            ShotgunPath.from_current_os_path(hou.hipFile.name()),
        )
