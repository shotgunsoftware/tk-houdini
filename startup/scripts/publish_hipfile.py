# std libs
import sys

# houdini libs
import hou

# tank libs
import tank

def main():  
    engine = tank.engine()
    engine.apps['sg_houdinipub'].hipfile_publish_handler.publish_ui()
# end def main

if __name__ in ('__main__', '__builtin__') :
    main()
# end if

