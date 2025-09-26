# Copyright (c) 2019 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import sys

__file__ = os.path.abspath(__file__)

tests_folder = os.path.abspath(os.path.dirname(__file__))
repo_root = os.path.dirname(tests_folder)

venv_folder = "venv_py3"

# Activate the virtual environment required to run test tests in Houdini.
activate_this_py = os.path.join(
    repo_root,
    venv_folder,
    "Scripts" if sys.platform == "win32" else "bin",
    "activate_this.py",
)

with open(activate_this_py, "rt") as f:
    exec(f.read(), {"__file__": activate_this_py})


import pytest

# We need to patch a couple of things to make pytest and argparse happy.
# argparse doesn't like it when argv is empty.
args = [
    "--capture=no",
    "--cov",
    "--cov-config=.coveragerc",
    "--cov-report=html",
    "--verbose",
    # "--ignore=**/venv_py3/**",
    # "--ignore-glob=**/venv_py3/**",
    '-s',
    "tests", # Folder to run tests from
]

current_dir = os.getcwd()
# It appears the path specified inside coveragerc is relative
# to the current working directly and not the test root,
# so we're going to change the current directory.
os.chdir(repo_root)
# pytest expects the arguments and not the name of the executable
# to be passed in.
pytest.main(args)
