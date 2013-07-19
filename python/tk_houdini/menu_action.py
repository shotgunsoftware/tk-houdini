# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import sys

import hou

import tank.platform.engine


def error(msg):
    if hou.isUIAvailable():
        hou.ui.displayMessage(msg)
    else:
        print msg


cmd_id = sys.argv[1]
engine = tank.platform.engine.current_engine()

if engine is None or not hasattr(engine, 'launch_command'):
    error("Shotgun: Houdini engine is not loaded")
else:
    engine.launch_command(cmd_id)
