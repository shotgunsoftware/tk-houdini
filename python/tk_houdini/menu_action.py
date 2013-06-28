#
# Copyright (c) 2013 Shotgun Software, Inc
# ----------------------------------------------------
#
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
