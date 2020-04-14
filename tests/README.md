
# Running Houdini engine tests

To run these tests, you need to do the following (tested on Mac)

1. From a terminal, create a virtual environment (using `virtualenv`) at `tests/venv_py2` or `tests/venv_py3` depending on the version of python you are testing. To create a virtual env for python 3 do something like this: `virtualenv --python=/Users/username/.pyenv/versions/3.7.6/bin/python3 venv_py3`
2. Execute `source venv_py2|3/bin/activate` on mac, or on Windows cd into `venv_py2|3/bin` and run `activate.bat`.
3. Install all dependencies needed for the test: `pip install -r requirements.txt`.

4. In the command line, set the `HOUDINI_PATH` env var to point to this test folder: `export HOUDINI_PATH="/Users/philips1/source_code/tk-houdini/tests;&"` on Mac, or `set "HOUDINI_PATH=E:\code\tk-houdini\tests;&"` on Windows, (make sure you include the `;&` at the end and wrap the value in quotes.)
5. Launch Houdini via the same terminal you set the env var in, eg: `/Applications/Houdini/Houdini18.0.392/Houdini\ FX\ 18.0.392.app/Contents/MacOS/houdini`. It should then run the tests and dump the output to the shell and then close Houdini automatically.
  To run the tests via hython (to test without a UI) do everything the same, but instead of calling the Houdini app call hython: `/Applications/Houdini/Houdini18.0.348/Frameworks/Houdini.framework/Versions/18.0/Resources/bin/hython`.
