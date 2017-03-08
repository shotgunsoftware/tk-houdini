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

def plugin_startup():

    # construct the path to the plugin root's folder.
    #      plugins/basic/python2.Xlibs/pythonrc.py
    #      -------------|
    # this part ^

    # use inspect to get the current file path since attempts to access
    # __file__ result in a NameError.
    current_file_path = os.path.abspath(
        inspect.getsourcefile(lambda: 0)
    )

    current_dir_path = os.path.dirname(current_file_path)
    plugin_root_path = os.path.dirname(current_dir_path)

    # the plugin python path will be just below the root level. add it to
    # sys.path
    plugin_python_path = os.path.join(plugin_root_path, "python")
    sys.path.insert(0, plugin_python_path)

    # now that the path is there, we can import the plugin bootstrap logic
    try:
        from tk_houdini_basic import plugin_bootstrap
        plugin_bootstrap.bootstrap(plugin_root_path)
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

plugin_startup()
