"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

A Houdini engine for Tank.

"""

# std libs
import os
import sys
import pickle
import logging
import platform
import textwrap

# tank libs
import tank

# application libs
import hou

CONSOLE_OUTPUT_WIDTH = 120

class HoudiniEngine(tank.platform.Engine):
    def init_engine(self):
        self.log_debug("%s: Initializing..." % self)
        
        # now check that there is a location on disk which corresponds to the context
        # for the houdini engine (because it for example sets the houdini project)
        if len(self.context.entity_locations) == 0:
            # Try to create path for the context.
            tank.platform.schema.create_filesystem_structure(self.shotgun,
                                                           self.context.project_root,
                                                           self.context.entity["type"],
                                                           self.context.entity["id"])
            if len(self.context.entity_locations) == 0:
                raise tank.TankError("No folders on disk are associated with the current context. The Houdini "
                    "engine requires a context which exists on disk in order to run correctly.")
        # end if
    # end def init_engine
    
    def destroy_engine(self):
        self.log_debug('%s: Destroying...' % self)
    # end def destroy_engine

    def _display_message(self, msg):
        if hou.isUIAvailable():
            hou.ui.displayMessage(str(msg))
        else:
            sys.stdout.write(str(msg)+'\n')
        # end
    # end def _display_message

    def log_debug(self, msg):
        sys.stdout.write(str(msg)+'\n')
    # ene def log_debug

    def log_info(self, msg):
        sys.stdout.write(str(msg)+'\n')
    # ene def log_info

    def log_error(self, msg):
        self._display_message(msg)
        sys.stdout.write(str(msg)+'\n')
        
    def log_warning(self, msg):
        sys.stdout.write(str(msg)+'\n')
    # ene def log_warning
# end class HoudiniEngine

    
        
    
        
