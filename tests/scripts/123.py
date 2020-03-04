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
import inspect
import os
import sys
import hou

current_file_path = os.path.abspath(inspect.getsourcefile(lambda: 0))

sys.path.append(os.path.join(os.path.dirname(current_file_path), ".."))

import run_tests  # noqa

hou.exit(exit_code=0, suppress_save_prompt=True)
