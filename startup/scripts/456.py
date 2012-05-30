"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

This file is loaded automatically by Houdini at startup.
It sets up the tank context and prepares the Tank Houdini engine.

"""


import os
import sys

import hou

def bootstrap_tank():
    try:
        import tank
    except ImportError:
        msg = "Could not import Tank!"
        if hou.isUIAvailable():
            hou.ui.displayMessage(msg)
        else:
            sys.stdout.write(msg)
        # end if 
        return
    # end try

    if not "TANK_HOUDINI_ENGINE" in os.environ:
        return
    # end if

    engine_name = os.environ.get("TANK_HOUDINI_ENGINE")
    file_to_open = os.environ.get("TANK_HOUDINI_FILE_TO_OPEN") 
    project_root = os.environ.get("TANK_HOUDINI_PROJECT_ROOT")
    entity_id = int(os.environ.get("TANK_HOUDINI_ENTITY_ID", 0))
    entity_type = os.environ.get("TANK_HOUDINI_ENTITY_TYPE")
    
    # get the file path from houdini to see if 
    file_loading_path = hou.hipFile.path()
    file_loading_name = os.path.basename(file_loading_path)

    try:
        if file_to_open:
            ctx = tank.platform.Context.from_path(file_to_open)
        elif project_root and file_loading_name == 'untitled.hip':
            ctx = tank.platform.Context.from_entity(project_root, entity_type, entity_id)
        elif file_loading_name != 'untitled.hip':
            engine = tank.platform.current_engine()
            if engine:
                engine.destroy()
            # end if 
            ctx = tank.platform.Context.from_path(file_loading_path)
        else:
            engine = tank.platform.current_engine()
            if engine:
                engine.destroy()
            # end if
            raise RuntimeError('No information data available to create a Context.')
        # end if
    except Exception, exp:
        msg = "Could not determine the Tank Context! Disabling Tank for now. Details: %s" % exp
        if hou.isUIAvailable():
            hou.ui.displayMessage(msg)
        else:
            sys.stdout.write(msg)
        # end if
        return
    # end try

    try:
        engine = tank.platform.start_engine(engine_name, ctx)
    except tank.TankEngineInitError, e:
        msg = "The Tank Engine could not start! Tank will be disabled. Details: %s" % exp
        if hou.isUIAvailable():
            hou.ui.displayMessage(msg)
        else:
            sys.stdout.write(msg)
        # end if
    # end try

    # remove from env so that they wont affect the nuke that is initalized on a
    # file->new. or file->open
    def delEnvVar(*args):
        for var in args:
            if var in os.environ:
                del os.environ[var]
            # end if
        # end for
    # end def delEnvVar 

    delEnvVar(
        "TANK_HOUDINI_FILE_TO_OPEN",
        "TANK_HOUDINI_PROJECT_ROOT",
        "TANK_HOUDINI_ENTITY_ID",
        "TANK_HOUDINI_ENTITY_TYPE"
    )
# end def bootstrap

bootstrap_tank()
