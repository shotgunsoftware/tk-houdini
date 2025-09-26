
# Running Houdini engine tests

To run these tests, you need to do the following (tested on Mac)

> [!NOTE]
> You need to use the same Python version as the Houdini you want to test (`major.minor`)
> 

Make sure `virtualenv` is available.


> [!Important]
> Houdini should have a valid license enabled.


## Prepare the testing environment

From a terminal, from inside the tk-houdini folder:

1.  Create a Python virtual environment
    ```bash
    virtualenv --python=/Users/username/.pyenv/versions/3.7.6/bin/python3 venv_py3
    ```

1.  Activate the virtual environment.
    ```bash
    source venv_py3/bin/activate
    ```

1.  Install all dependencies needed for the test:
    ```bash
    pip install -U -r tests/requirements.txt
    ```

## Run the tests

From a terminal:

1.  Set the `HOUDINI_PATH` env var to point to this test folder:

      * Linux or macOS:
        ```bash
        export HOUDINI_PATH="/Users/philips1/source_code/tk-houdini/tests;&"
        ```

      * Windows:
        ```batch
        set "HOUDINI_PATH=E:\code\tk-houdini\tests;&"
        ```

        > [!NOTE]
        > Make sure you include the `;&` at the end and wrap the value in quotes.
        > 

1. Launch Houdini via the same terminal you set the env var in. 
      * Linux or macOS:
        ```bash
        /Applications/Houdini/Houdini18.0.392/Houdini\ FX\ 18.0.392.app/Contents/MacOS/houdini
        ```

      * Windows:
        ```batch
        "C:\Program Files\Side Effects Software\Houdini 19.0.720\bin\houdini.exe"
        ```

It should then run the tests and dump the output to the shell and then close
Houdini automatically.

## Testing the Houdini engine without the UI

Using the same environment defined previously, we can run the tests that don't
require the Houdini UI by calling the `hython` binary instead:


*   Linux or macOS:
    ```bash
    /Applications/Houdini/Houdini19.0.720/Frameworks/Houdini.framework/Versions/Current/Resources/bin/hython
    ```

*  Windows:
    ```batch
    "C:\Program Files\Side Effects Software\Houdini 19.0.720\bin\hython.exe"
    ```
