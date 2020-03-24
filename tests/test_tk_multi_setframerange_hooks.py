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


class TestFrameRangeHooks(TestHooks):
    """
    Tests the tk-multi-setframerange hooks.
    """

    def setUp(self):
        super(TestFrameRangeHooks, self).setUp()
        # Now get the app and run the reset operation.
        self.app = self.engine.apps["tk-multi-setframerange"]

    def test_get_frame_range(self):
        """
        Ensures that the frame range can be gathered correctly from Houdini by the hook.
        We can use the app's API for this.
        """
        # Set the frame range so that we can test that we get the same range back, let not rely on the default range
        # in case it differs from setup to setup.
        start = 10
        end = 115
        hou.playbar.setPlaybackRange(start, end)

        cur_start, cur_end = self.app.get_current_frame_range()

        self.assertEqual(start, cur_start)
        self.assertEqual(end, cur_end)

    def test_set_frame_range(self):
        """
        Ensures that the frame range is set correctly by the hook. We can use the app's API for this.
        """
        # Set the frame range so that we can test that we get the same range back, let not rely on the default range
        # in case it differs from setup to setup.
        start = 20
        end = 95

        self.app.set_frame_range(start, end)

        # Check that the playback range has been updated
        cur_start, cur_end = hou.playbar.playbackRange()
        self.assertEqual(start, cur_start)
        self.assertEqual(end, cur_end)

        # Check that the global range has been updated.
        cur_global_start, cur_global_end = hou.playbar.frameRange()
        self.assertEqual(start, cur_global_start)
        self.assertEqual(end, cur_global_end)
