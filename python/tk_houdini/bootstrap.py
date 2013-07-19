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

        # include our directories in the HOUDINI_PATH
        if 'HOUDINI_PATH' in os.environ:
            old_path = os.environ['HOUDINI_PATH'].rstrip(';&')
            new_path = "%s;%s;%s" % (tmpdir, engine_startup, old_path)
        else:
            new_path = "%s;%s" % (tmpdir, engine_startup)
        os.environ['HOUDINI_PATH'] = "%s;&" % new_path
    except:
        # had an error, clean up the tmp dir
        shutil.rmtree(tmpdir)
        raise
