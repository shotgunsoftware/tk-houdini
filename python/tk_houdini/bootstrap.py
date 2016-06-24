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
import tempfile

import tank.platform.engine as tank_engine


g_temp_env = 'TK_HOUDINI_TMP'


def bootstrap(tank, context):
    # setup a path for the engine to write out its menu file
    tmpdir = tempfile.mkdtemp(prefix='tk-houdini')
    try:
        # set env var to point engine at temp HOUDINI_PATH path
        os.environ[g_temp_env] = tmpdir

        # This allows Qt to load, but I think it makes Houdini unstable...
        os.environ['OBJC_DISABLE_GC'] = 'YES'

        # place in path for static startup files
        engine_startup = os.path.join(os.path.dirname(__file__), "..", "..", "startup")
        engine_startup = os.path.normpath(engine_startup)

        # note: not using sgtk.util.environment.prepend_path_to_env_var since
        # houdini respects semicolons as delimiters in all cases.
        hou_path_str = os.environ.get("HOUDINI_PATH")
        if hou_path_str:
            hou_path_str = hou_path_str.rstrip(";")
            hou_paths = hou_path_str.split(";")
        else:
            hou_paths = []

        # paths to prepend that are not already in the houdini path
        prepend_paths = [tmpdir, engine_startup]
        prepend_paths = [p for p in prepend_paths if not p in hou_paths]

        new_paths = prepend_paths
        new_paths.extend(hou_paths)

        # append the ampersand if it's not already in the paths
        if not "&" in hou_paths:
            new_paths.append("&")

        os.environ["HOUDINI_PATH"] = ";".join(new_paths)
    except:
        # had an error, clean up the tmp dir
        shutil.rmtree(tmpdir)
        raise
