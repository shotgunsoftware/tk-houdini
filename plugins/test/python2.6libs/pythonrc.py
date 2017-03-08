# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
This file is loaded automatically by Houdini at startup.
"""

# The simplest of plugins for testing.

import hou
import sgtk

message = "Toolkit test plugin!"
details = "Current engine: %s" % (sgtk.platform.current_engine(),)

if hou.isUIAvailable():
    hou.ui.displayMessage(message, details=details)
else:
    print message
    print details
