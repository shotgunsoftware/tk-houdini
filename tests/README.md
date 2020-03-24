
# Running Houdini engine tests

To run these tests, you need to do the following (tested on Mac)

1. From a terminal, create a virtual environment (using `virtualenv`) at `tests/venv_py2` or `tests/venv_py3` depending on the version of python you are testing. To create a virtual env for python 3 do something like this: `virtualenv --python=/Users/username/.pyenv/versions/3.7.6/bin/python3 venv_py3`
2. Execute `source venv_py2|3/bin/activate`.
3. Install all dependencies needed for the test: `pip install -r requirements.txt`.

4. In the command line, set the `HOUDINI_PATH` env var to point to this test folder: `export HOUDINI_PATH="/Users/philips1/source_code/tk-houdini/tests;&"` (make sure you include the `;&` at the end and wrap the value in quotes.)
5. Launch Houdini via the same terminal you set the env var in, eg: `/Applications/Houdini/Houdini18.0.392/Houdini\ FX\ 18.0.392.app/Contents/MacOS/houdini`. It should then run the tests and dump the output to the shell and then close Houdini automatically.
