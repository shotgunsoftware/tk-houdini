
# std libs
import sys

# houdini libs
import hou

# tank libs
import tank

def main():  
    engine = tank.engine()
    engine.apps['sg_houdinipub'].snapshot_handler.snapshot_as()
# end def main

if __name__ in ('__main__', '__builtin__') :
    main()
# end if
