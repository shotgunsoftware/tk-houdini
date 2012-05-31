
# std libs
import sys

# houdini libs
import hou

# tank libs
import tank

def main():  
    engine = tank.platform.current_engine()
    engine.apps['tk_houdini_publish'].snapshot_handler.snapshot_as()
# end def main

if __name__ in ('__main__', '__builtin__') :
    main()
# end if
