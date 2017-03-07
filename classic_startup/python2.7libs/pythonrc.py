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


def classic_startup():

    # use inspect to get the current file path since attempts to access
    # __file__ result in a NameError.
    current_file_path = os.path.abspath(
        inspect.getsourcefile(lambda: 0)
    )

    # construct the path to the engine's python directory and add it to sys
    # path. this provides us access to the bootstrap module which contains
    # helper methods for constructing the proper environment based on the
    # bootstrap scanario. For this file, the python directory is 3 levels up.
    tk_houdini_python_path = \
        os.path.abspath(
            os.path.join(
                current_file_path,
                "..",
                "..",
                "..",
                "python",
            )
        )

    # add to the system path
    sys.path.insert(0, tk_houdini_python_path)

    # now that the path is there, we can import the classic bootstrap logic
    try:
        from tk_houdini import bootstrap
        bootstrap.bootstrap_classic()
    except Exception, e:
        import traceback
        stack_trace = traceback.format_exc()

        message = "Shotgun Toolkit Error: %s" % (e,)
        details = "Error stack trace:\n\n%s" % (stack_trace)

        import hou
        if hou.isUIAvailable():
            hou.ui.displayMessage(message, details=details)
        else:
            print message
            print details


classic_startup()
