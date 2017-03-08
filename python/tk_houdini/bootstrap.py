# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import shutil
import sys
import tempfile
import traceback

################################################################################
# constants defining environment variables used during bootstrap

# Name of the env variable that stores the temp directory where .xml files are
# written to defined menus, shelves and python panels for the SG integration.
g_temp_env = "TK_HOUDINI_TMP"

# Name of the env variable that stores the serialized context used durring
# classit toolkit bootstrap
g_sgtk_context_env = "TANK_CONTEXT"

# Name of the env variable that stores the name the engine instance name for
# classic toolkit bootstrap
g_sgtk_engine_env = "TANK_ENGINE"

# Name of the file to open after bootstrap
g_sgtk_file_to_open_env = "TANK_FILE_TO_OPEN"

################################################################################
# methods for bootstrapping toolkit within houdini

def bootstrap(tank, context):
    """
    Interface for older versions of tk-multi-launchapp.

    This is deprecated and now replaced with the ``startup.py`` file and
    ``SoftwareLauncher`` interface.

    Prepares the environment for a tk-houdini bootstrap. This method is
    called directly from the tk-multi-launchapp.
    """

    # get the necessary environment variable for launch
    env = get_classic_startup_env()

    # update the environment with the classic startup vars
    os.environ.update(env)


def bootstrap_classic():
    """
    This method initiates the classic toolkit bootstrap.

    This is accomplished by extracting engine and context information from the
    environment and then calling sgtk.platform.start_engine().
    """

    try:
        import sgtk
    except ImportError:
        bootstrap_exception("Failed to import 'sgtk'!")
        return

    # ensure the engine name and context are defined in the environment
    for env_var in [g_sgtk_context_env, g_sgtk_engine_env]:
        if env_var not in os.environ:
            bootstrap_exception(
                "Toolkit bootstrap is missing a required env variable: %s" %
                (env_var)
            )
            return

    # extract the engine and context from the environment
    engine_name = os.environ.get(g_sgtk_engine_env)
    try:
        context = sgtk.context.deserialize(os.environ.get(g_sgtk_context_env))
    except Exception, e:
        bootstrap_exception(
            "Toolkit bootstrap failed to extract the current context from the "
            "environment! The Shotgun integration will be disabled. Details: "
            "%s" % (e,))
        return

    # now do the classic engine startup
    try:
        engine = sgtk.platform.start_engine(engine_name, context.sgtk, context)
    except Exception, e:
        bootstrap_exception(
            "Toolkit bootstrap failed to start the engine: %s" % (e,)
        )
        return

    # see if the environment includes a file to be opened after bootstrap
    file_to_open = os.environ.get(g_sgtk_file_to_open_env)
    if file_to_open:
        # importing here since we don't need hou unless loading a file
        import hou
        hou.hipFile.load(file_to_open)

    # clean env vars. note, we don't clean the temp dir env variable since it is
    # used by the engine to know where to write the shelf/menu .xml files
    for env_var in [g_sgtk_context_env, g_sgtk_engine_env, g_sgtk_file_to_open_env]:
        if env_var in os.environ:
            del os.environ[env_var]


def bootstrap_exception(error_msg):
    """
    Shows an error message if there is a problem during bootstrap.
    """

    # this file can be imported before houdini is up and running, but this
    # method should only be called during a houdini session
    import hou

    # get a full stack trace
    details = traceback.format_exc()

    if hou.isUIAvailable():
        # we have a UI, show the error in a popup dialog
        hou.ui.displayMessage(error_msg, details=details)
    else:
        # no UI, just print to stdout
        print error_msg
        print details


################################################################################
# utility methods for populating the environment prior to bootstrap

def get_classic_startup_env():
    """
    Returns a dict of key/value pairs representing the environment variables
    needed to launch houdini and startup toolkit in classic mode.
    """

    # Add the classic startup directory for the engine (2 levels up from this
    # file). This directory, in the engine root, includes the pythonrc.py files
    # within python2.6libs and python2.7libs directories once on HOUDINI_PATH,
    # houdini will execute the appropriate file at startup
    startup_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "classic_startup"
    )
    startup_path = os.path.normpath(startup_path)

    # update the houdini path with the engine startup path
    return _get_env([startup_path])


def get_plugin_startup_env(plugin_names):
    """
    Returns a dict of key/value pairs representing the environment variables
    needed to launch houdini with the supplied plugins.
    """

    # for each plugin provided, construct a list of corresponding plugin startup
    # paths.
    startup_paths = []

    for plugin_name in plugin_names:

        # Each plugin should have the standard pythonX.Xlibs/pythonrc.py folders
        # at the top-level which houdini will execute at startup time.
        plugin_startup_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "plugins",
            plugin_name,
        )
        plugin_startup_path = os.path.normpath(plugin_startup_path)

        # if the path exists, add it to the list of startup paths
        if os.path.exists(plugin_startup_path):
            startup_paths.append(plugin_startup_path)

    return _get_env(startup_paths)


################################################################################
# helper methods for the methods above

def _get_env(startup_paths):
    """
    This method represents the common behavior for preparing an environment for
    houdini launch. It populates and returns a dictionary with all the necessary
    keys for starting the engine. The supplied startup paths will differ based
    on the startup mode (classic or plugin).
    """

    env = {}

    # setup a path for the engine to write out its menu file
    tk_houdini_temp_dir = tempfile.mkdtemp(prefix='tk-houdini')

    # set env var to point engine at temp path
    env[g_temp_env] = tk_houdini_temp_dir

    # This allows Qt to load, but I think it makes Houdini unstable...
    env['OBJC_DISABLE_GC'] = 'YES'

    # construct the houdini path. this isn't as simple as prepending these paths
    # since we have to account for some legacy behavior and houdini weirdness
    # when it comes to the expected path separator. see the _build_houdini_path
    # method for additional details.
    try:
        # supply a single list of startup paths which is the temp directory plus
        # the supplied startup paths
        env["HOUDINI_PATH"] = _build_houdini_path(
            [tk_houdini_temp_dir] + startup_paths
        )
    except:
        # had an error, clean up the tmp dir
        shutil.rmtree(tk_houdini_temp_dir)
        raise

    return env


def _build_houdini_path(startup_paths):
    """
    Given some paths, construct an updated houdini path.

    This method preserves the existing HOUDINI_PATH and prepends the supplied
    startup paths. It also appends the special `&` default path if it is not
    already included.
    """

    hou_path_str = os.environ.get("HOUDINI_PATH")

    # default to using the OS-specific path separator. windows should always use
    # semicolon since colon is the drive separator.
    path_sep = os.pathsep

    if hou_path_str:

        # It turns out Houdini allows HOUDINI_PATH to be separated by semicolons
        # on any OS, so the tk engine has always supported and assumed
        # semicolons regardless of the current OS. Some clients on POSIX OSs
        # however, who define HOUDINI_PATH in their env prior to tk engine
        # bootstrap, use colons as the path separator. This is completely valid
        # and matches the POSIX convention.

        if sys.platform is not "win32":
            # for non-windows OS, see if semicolon is in use
            if ";" in hou_path_str:
                # already using semi-colons, continue using semicolons. this
                # will allow clients relying on the legacy engine behavior to
                # continue without making any changes.
                path_sep = ";"

        hou_path_str = hou_path_str.rstrip(path_sep)
        hou_paths = hou_path_str.split(path_sep)
    else:
        hou_paths = []

    # paths to prepend that are not already in the houdini path. these paths
    # include the temp directory which is typically where the engine will write
    # .xml files for menu/shelf/panel definitions. in addition, startup paths
    # are added depending on the startup mode. in classic mode, this will be the
    # engine's root level startup directory which includes code to start the
    # engine. in plugin mode, this will be a list of paths for each plugin's
    # startup path.
    prepend_paths = startup_paths
    prepend_paths = [p for p in prepend_paths if not p in hou_paths]

    new_paths = prepend_paths
    new_paths.extend(hou_paths)

    # append the ampersand if it's not already in the paths
    if not "&" in hou_paths:
        new_paths.append("&")

    return path_sep.join(new_paths)
