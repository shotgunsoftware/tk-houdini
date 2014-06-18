# Copyright (c) 2013 Shotgun Software Inc.
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
It sets up the tank context and prepares the Tank Houdini engine.
"""
import os
import traceback

import hou


def exception(msg):
    details = traceback.format_exc()
    if hou.isUIAvailable():
        hou.ui.displayMessage(msg, details=details)
    else:
        print msg
        print details


def bootstrap_tank():
    try:
        import tank
    except ImportError:
        exception("Could not import Tank!")
        return

    if not "TANK_ENGINE" in os.environ:
        exception("Tank: Missing required environment variable TANK_ENGINE.")
        return

    engine_name = os.environ.get("TANK_ENGINE")
    try:
        context = tank.context.deserialize(os.environ.get("TANK_CONTEXT"))
    except Exception, e:
        exception("Tank: Could not create context! Tank will be disabled.  Details: %s" % e)

    try:
        engine = tank.platform.start_engine(engine_name, context.tank, context)
    except Exception, e:
        exception("Tank: Could not start engine: %s" % e)

    file_to_open = os.environ.get("TANK_FILE_TO_OPEN")
    if file_to_open:
        hou.hipFile.load(file_to_open)

    # clean up temp env vars
    for var in ["TANK_ENGINE", "TANK_CONTEXT", "TANK_FILE_TO_OPEN"]:
        if var in os.environ:
            del os.environ[var]

bootstrap_tank()
