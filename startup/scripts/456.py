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
        return

    if not "TANK_HOUDINI_ENGINE" in os.environ:
        return

    engine_name = os.environ.get("TANK_HOUDINI_ENGINE")
    file_to_open = os.environ.get("TANK_HOUDINI_FILE_TO_OPEN") 
    project_root = os.environ.get("TANK_HOUDINI_PROJECT_ROOT")
    entity_id = int(os.environ.get("TANK_HOUDINI_ENTITY_ID", 0))
    entity_type = os.environ.get("TANK_HOUDINI_ENTITY_TYPE")
    
    # get the file path from houdini to see if 
    file_loading_path = hou.hipFile.path()
    file_loading_name = os.path.basename(file_loading_path)

    try:
        tk = tank.Tank(project_root)
    except Exception, e:
        msg = "The Tank API could not be initialized! Tank will be disabled. Details: %s" % e
        if hou.isUIAvailable():
            hou.ui.displayMessage(msg)
        else:
            sys.stdout.write(msg)
        return

    try:
        if file_to_open:
            ctx = tk.context_from_path(file_to_open)
        elif project_root and file_loading_name == 'untitled.hip':
            ctx = tk.context_from_entity(entity_type, entity_id)

        elif file_loading_name != 'untitled.hip':
            engine = tank.platform.current_engine()
            if engine:
                engine.destroy()
            ctx = tk.context_from_path(file_loading_path)

        else:
            engine = tank.platform.current_engine()
            if engine:
                engine.destroy()
            raise RuntimeError('No information data available to create a Context.')

    except Exception, exp:
        msg = "Could not determine the Tank Context! Disabling Tank for now. Details: %s" % exp
        if hou.isUIAvailable():
            hou.ui.displayMessage(msg)
        else:
            sys.stdout.write(msg)
        return

    try:
        engine = tank.platform.start_engine(engine_name, tk, ctx)
    except Exception, exp: #tank.TankEngineInitError
        msg = "The Tank Engine could not start! Tank will be disabled. Details: %s" % exp
        if hou.isUIAvailable():
            hou.ui.displayMessage(msg)
        else:
            sys.stdout.write(msg)


    # remove from env so that they wont affect the nuke that is initalized on a
    # file->new. or file->open
    def delEnvVar(*args):
        for var in args:
            if var in os.environ:
                del os.environ[var]


    delEnvVar(
        "TANK_HOUDINI_FILE_TO_OPEN",
        "TANK_HOUDINI_PROJECT_ROOT",
        "TANK_HOUDINI_ENTITY_ID",
        "TANK_HOUDINI_ENTITY_TYPE"
    )

bootstrap_tank()
