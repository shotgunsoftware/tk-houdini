
# std libs
import sys

# houdini libs
import hou

# tank libs
import tank

def main():
    engine = tank.engine()
    engine.apps['sg_set_frame_range'].set_frame_range()
# end def main

if __name__ in ('__main__', '__builtin__') :
    main()
# end if
