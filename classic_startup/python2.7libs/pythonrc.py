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

    # We need to check to make sure we don't have an incompatibility
    # between httplib and Houdini's bundled ssl.py. This is a problem
    # on some Linux distros (CentOS 7.x) with H16. We also then had to
    # package the urllib2 library that is compatible with our bundled
    # httplib.
    if sys.platform.startswith("linux") and sys.version.startswith("2.7.5"):
        # We can check to see if ssl has the function we know that
        # system httplib is likely to require. If it doesn't have it,
        # then we need to force the use of our bundled httplib before
        # we let the bootstrap happen.
        import ssl
        if not hasattr(ssl, "_create_default_https_context"):
            # Clear httplib if it's already been imported.
            if "httplib" in sys.modules:
                del sys.modules["httplib"]
            if "urllib2" in sys.modules:
                del sys.modules["urllib2"]

            # Add the submodule containing httplib to sys.path so that
            # the next time it's imported it'll come from there instead
            # of the system Python install.
            packages_path = os.path.join(tk_houdini_python_path, "packages")
            sys.path.insert(0, packages_path)

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

# In case we cleared httplib/urllib2 from sys.modules during plugin startup,
# we will import it here in the global scope. That will ensure that
# we have httplib coming from the correct module after we've potentially
# manipulated sys.path.
import httplib
import urllib2

