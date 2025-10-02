
# Running Houdini engine tests

To run these tests, you need to do the following (tested on Mac)



We recommand using pyenv TODO link

If not, adjust commands

> [!Important]
> Houdini should have a valid license enabled.


## Prepare the testing environment

From a terminal, from inside the tk-houdini folder:

1.  Create a Python virtual environment
    ```bash
    pyenv local 3.9.12
    ```

    > **NOTE**
    >
    > Select a pyenv version that matches the version of Houdini you are testing
    > (`major.minor`).
    >
    > Each Houdini version ships a specific Python version. The testing
    > environment mjust be initialized with the same Python version or the tests
    > will not run.
    >
    > **IMPORTANT**: before switching ..... TODO - suffix venv folder name with (`major.minor`) so better

1.  Create a Python virtual environment
    ```bash
    pyenv exec python venv
    ```

1.  Activate the virtual environment

      * Linux or macOS:
        ```bash
        source venv/bin/activate
        ```

      * Windows:
        ```batch
        venv/Scripts/activate
        ```

1.  Install all dependencies needed for the test:
    ```bash
    pip install -U -r tests/requirements.txt
    ```

## Run the tests

The following commands need to be run in a terminal but not necesarly from the tk-houdini folder.

For Windows, use a "Command Prompt" session. Not a PowerShell one.

1.  Set the `HOUDINI_PATH` env var to point to this test folder:

      * Linux or macOS:
        ```bash
        export HOUDINI_PATH="${HOME}/git/tk-houdini/tests;&"
        ```

      * Windows:
        ```batch
        set "HOUDINI_PATH=%USERPROFILE%\git\tk-houdini\tests;&"
        ```

        > [!NOTE]
        > Make sure you include the `;&` at the end and wrap the value in quotes.
        > 

1.  Run the test without UI.

    *   Linux or macOS:
        ```bash
        /Applications/Houdini/Houdini19.0.720/Frameworks/Houdini.framework/Versions/Current/Resources/bin/hython
        ```

    *  Windows:
        ```batch
        "C:\Program Files\Side Effects Software\Houdini 19.0.720\bin\hython.exe"
        ```


2. Run the tests with the full Houdini UI
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
