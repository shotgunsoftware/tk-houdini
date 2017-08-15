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
        #
        # The issue, ultimately, is that the ssl bundled with H16
        # does not provide the _create_default_https_context function,
        # which is called by the httplib that comes with system Python
        # on CentOS 7.x, which itself is used by httplib2, which is used
        # by shotgun_api3. The end result is that shotgun_api3 fails on
        # connect when the address is https with an AttributeError.
        import ssl
        if not hasattr(ssl, "_create_default_https_context"):
            # Add the submodule containing httplib to sys.path so that
            # the next time it's imported it'll come from there instead
            # of the system Python install.
            plugins_path = os.path.dirname(plugin_root_path)
            packages_path = os.path.join(
                os.path.dirname(plugins_path),
                "python",
                "packages",
            )

            sys.path.insert(0, packages_path)

            # Clear httplib if it's already been imported.
            if "httplib" in sys.modules:
                del sys.modules["httplib"]
            if "urllib2" in sys.modules:
                del sys.modiles["urllib2"]

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

# In case we cleared httplib/urllib2 from sys.modules during plugin startup,
# we will import it here in the global scope. That will ensure that
# we have httplib coming from the correct module after we've potentially
# manipulated sys.path.
import httplib
import urllib2

