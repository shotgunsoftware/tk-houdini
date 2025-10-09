
# Houdini engine tests

This folder contains unit tests that can run inside Houdini to validate that
parts of the Toolkit integration is working as expected.

## Requirements

* Houdini software installed and properly licensed

* [pyenv](https://github.com/pyenv/pyenv) installed and configured

  > **Note**
  >
  > Houdini provides its own Python interpreter: `hython`.
  > This interpreter even ships the `venv` module!
  >
  > Unfortunately, bootstrapping a Python virtual environment from this module is
  > unstable across Houdini versions and Operating Systems.
  >
  > So we prefer using **pyenv**.



* Clone the following repositories in the same common folder as this one
  (`tk-houdini`):

  * tk-core
  * tk-framework-qtwidgets
  * tk-framework-shotgunutils
  * tk-framework-widget
  * tk-houdini-alembicnode
  * tk-multi-loader2
  * tk-multi-setframerange
  * tk-multi-workfiles2
  * tk-multi-snapshot

  > **Important**
  >
  > Also make sure those repos are up to date!


## Prepare the testing environment and run the tests

Run the following instructions from a terminal, from inside the `tk-houdini`
folder.

> [!Note]
> On Windows, use a "Command Prompt" session. Not a PowerShell one!

1. Select the Houdini version to test, identify its installation folder and
   Python version:

    *   Linux
          ```bash
        /opt/hfs20.0.751/bin/hython -V
        ```

    *   macOS:
        ```bash
        /Applications/Houdini/Houdini20.0.751/Frameworks/Houdini.framework/Versions/Current/Resources/bin/hython -V
        ```

    *  Windows:
        ```batch
        "C:\Program Files\Side Effects Software\Houdini 20.0.751\bin\hython" -V
        ```

1.  Verify you have an equivalent Python version installed (`major.minor`).
    ```bash
    pyenv versions
    ```

    If not , install one with `pyenv install 3.10....`.

    > **Important**
    >
    > Each Houdini version ships a specific Python version. The testing
    > environment mjust be initialized with the same Python version or the tests
    > **will not run.**


1.  Select the Python version to use with pyenv
    ```bash
    pyenv local 3.11.10
    ```

1.  Create a Python virtual environment

    ```bash
    pyenv exec python -m venv --clear venv
    ```

1.  Install all dependencies needed for the test:

      * Linux or macOS:
        ```bash
        venv/bin/python -m pip install -U -r tests/requirements.txt
        ```


      * Windows:
        ```batch
        venv\Scripts\python -m pip install -U -r tests/requirements.txt
        ```

1.  Set the `HOUDINI_PATH` env var to point to this test folder:

      * Linux or macOS:
        ```bash
        export HOUDINI_PATH="${PWD}/tests;&"
        ```


      * Windows:
        ```batch
        set "HOUDINI_PATH=%CD%\tests;&"
        ```

    > **Note**
    >
    > Make sure you include the `;&` at the end and wrap the value in quotes.

1.  Run the test inside a **hython** session (without the UI)

    *   Linux
          ```bash
        /opt/hfs20.0.751/bin/hython
        ```

    *   macOS:
        ```bash
        /Applications/Houdini/Houdini20.0.751/Frameworks/Houdini.framework/Versions/Current/Resources/bin/hython
        ```

    *  Windows:
        ```batch
        "C:\Program Files\Side Effects Software\Houdini 20.0.751\bin\hython"
        ```

1. Run the tests insides a **Houdini Fx** session (with the UI)

    *   Linux
        ```bash
        /opt/hfs20.0.751/bin/houdini
        ```

    * Linux or macOS:
      ```bash
      /Applications/Houdini/Houdini18.0.392/Houdini\ FX\ 18.0.392.app/Contents/MacOS/houdini
      ```

    * Windows:
      ```batch
      "C:\Program Files\Side Effects Software\Houdini 19.0.720\bin\houdini"
      ```

    It should then run the tests and dump the output to the shell and then close
    Houdini automatically.

Validate that all tests passed. Also pay attention to any error or warning
reported!
