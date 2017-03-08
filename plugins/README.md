# Houdini Toolkit Plugins

The Houdini engine supports the ability to run one or more plugins at startup
time. This is made possible by the `launch_builtin_plugins` setting where a list
of plugin names can be defined. The `basic` plugin handles bootstrapping
toolkit. Plugins that run after can assume that the Shotgun engine for Houdini
is up and running. See the `test` plugin as an example of a simple plugin that
can run after toolkit is bootstrapped.

## Plugin Structure

Houdini Toolkit plugins should include the Houdini standard
`pythonX.Xlibs/pythonrc.py` files within the plugin root. This allows the plugin
root directory to be added to `HOUDINI_PATH` prior to launch by either the
engine itself via the launch app (zero config) or by a studio (toolkit as a
stand alone plugin). Once on `HOUDINI_PATH`, these files are executed
automatically by Houdini.

Toolkit plugins should include both `python2.6libs` and `python2.7libs` folders
in order to support both current and legacy Houdini versions. The `pythonrc.py`
files in these folders should be identicial, and should call shared code in
the plugin's `python` folder to keep the code duplication to a minimum.

For more information on these standard Houdini files,
[http://www.sidefx.com/docs/houdini/hom/locations](see the official documentation).


