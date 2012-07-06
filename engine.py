#
# Copyright (c) 2012 Shotgun Software, Inc
# ----------------------------------------------------
#

"""
A Houdini engine for Tank.

"""

# tank libs
import tank

# application libs
import hou

class HoudiniEngine(tank.platform.Engine):
    def init_engine(self):
        self.log_debug("%s: Initializing..." % self)

        if len(self.context.entity_locations) == 0:
            raise tank.TankError("No folders on disk are associated with the current context. The Houdini "
                            "engine requires a context which exists on disk in order to run "
                            "correctly.")

    def destroy_engine(self):
        self.log_debug("%s: Destroying..." % self)

    def _display_message(self, msg):
        if hou.isUIAvailable():
            hou.ui.displayMessage(str(msg))
        else:
            print str(msg)

    def log_debug(self, msg):
        print str(msg)

    def log_info(self, msg):
        print str(msg)

    def log_error(self, msg):
        self._display_message(msg)
        print str(msg)

    def log_warning(self, msg):
        print str(msg)


