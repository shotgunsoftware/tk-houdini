# Copyright (c) 2020 Shotgun Software Inc.
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
It's called 123 because this is what Houdini looks for an runs on startup.
You can also have a 456, the difference being, that 123 is run when Houdini
starts with out a scene file, and 456 is run whenever a scene file is opened.
"""
import inspect
import os
import sys
import hou

current_file_path = os.path.abspath(inspect.getsourcefile(lambda: 0))

sys.path.append(os.path.join(os.path.dirname(current_file_path), ".."))

# Importing this will run the tests.
import run_tests  # noqa

# Shut Houdini down after the tests have run.
hou.exit(exit_code=0, suppress_save_prompt=True)
