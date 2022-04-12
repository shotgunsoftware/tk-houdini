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
import hou

import sgtk

# Required so that the SHOTGUN_HOME env var will be set
from tank_test.tank_test_base import setUpModule  # noqa

from test_hooks_base import TestHooks
from sgtk.util import ShotgunPath


class TestLoadingOtls(TestHooks):
    """
    Tests the loading Houdini otl files from apps.
    """

    def setUp(self):
        super(TestLoadingOtls, self).setUp()

    def __check_paths(self, houdini_version, expected_folders):
        """
        Checks that the expected folders are gathered for the correct Houdini version.
        :param houdini_version: The version of Houdini as a tuple of three ints.
        :param expected_folders: The list of paths that we expect want to compare against the engine generated ones.
        :return:
        """
        # Change what the engine thinks the Houdini version is.
        self.engine._houdini_version = houdini_version
        # Ask the engine for the otl paths.
        paths_from_engine = self.engine._get_otl_paths(self.app_otl_folder)
        # We would always expect to get the root otl folder returned.
        expected_folders.insert(0, self.app_otl_folder)

        # Handle forward and backwards slashes so that the comparison doesn't care.
        sanitized_paths_from_engine = [
            ShotgunPath.from_current_os_path(path) for path in paths_from_engine
        ]
        sanitized_expected_paths = [
            ShotgunPath.from_current_os_path(path) for path in expected_folders
        ]

        self.assertEqual(
            sanitized_paths_from_engine,
            sanitized_expected_paths,
            "Houdini version number was: v%s.%s.%s" % houdini_version,
        )

    def _make_folder(self, folder_name):
        """
        Makes a folder in the app's otl folder with the provided name.
        :param folder_name:
        :return:
        """
        sgtk.util.filesystem.ensure_folder_exists(
            os.path.join(self.app_otl_folder, folder_name)
        )

    def test_otl_paths(self):
        """
        This tests that the engine will gather the appropriate otl paths from an app path.
        This doesn't test the actual installing of an otl in Houdini, but it does cover the most complicated
        part of the process.
        :return:
        """

        # First test that when no version folders exist it only gathers the otls folder.
        self.app_otl_folder = os.path.join(self.tank_temp, "test_app", "otls")
        os.makedirs(self.app_otl_folder)
        # This folder should not be gathered
        self._make_folder("test")
        # These version folders don't have the right format so shouldn't be gathered.
        self._make_folder("v16")
        self._make_folder("v16.0")
        self._make_folder("v16.0.0x")
        self._make_folder("dv16.0.0")
        self._make_folder("16.0.0")
        # Now check that only the otls folder was returned.
        self.__check_paths((17, 0, 0), [])

        self._make_folder("v14.x.x")
        self._make_folder("v16.x.x")
        self._make_folder("v18.x.x")
        self._make_folder("v19.5.x")
        self._make_folder("v19.6.19")
        self._make_folder("v20.0.0")
        # Test it picks the exact or next lowest version folder testing major version numbers specifically
        self.__check_paths(
            (17, 1, 1),
            [os.path.join(self.app_otl_folder, "v16.x.x")],
        )
        self.__check_paths(
            (18, 0, 0),
            [os.path.join(self.app_otl_folder, "v18.x.x")],
        )
        self.__check_paths(
            (18, 1, 134),
            [os.path.join(self.app_otl_folder, "v18.x.x")],
        )
        # Test it picks the exact or next lowest version folder testing minor version numbers specifically
        self.__check_paths(
            (19, 6, 10),
            [os.path.join(self.app_otl_folder, "v19.5.x")],
        )
        # Test it picks the exact or next lowest version folder testing patch version numbers specifically
        self.__check_paths(
            (19, 6, 20),
            [os.path.join(self.app_otl_folder, "v19.6.19")],
        )
        self.__check_paths(
            (20, 1, 2),
            [os.path.join(self.app_otl_folder, "v20.0.0")],
        )

    def test_otls_installed(self):
        """
        Checks that the otls file get installed correctly in Houdini, and that Houdini
        reports them as installed.
        """
        # The alembic app is added and it should have installed two otl files,
        # check that Houdini recognizes this.
        alembic_app = self.engine.apps["tk-houdini-alembicnode"]
        otl_path = self.engine._safe_path_join(alembic_app.disk_location, "otls")

        # The alembic node should have version folders, so remove root folder from the list,
        # and check that we have one path left which will be the version folder.
        otl_paths = self.engine._get_otl_paths(otl_path)
        otl_paths.remove(otl_path)
        self.assertTrue(len(otl_paths) == 1)

        # Now check both otls were installed in Houdini.
        sanitized_loaded_files = [
            ShotgunPath.from_current_os_path(path) for path in hou.hda.loadedFiles()
        ]
        self.assertTrue(
            ShotgunPath.from_current_os_path(
                os.path.join(otl_paths[0], "sgtk_alembic.otl")
            )
            in sanitized_loaded_files
        )
        self.assertTrue(
            ShotgunPath.from_current_os_path(
                os.path.join(otl_paths[0], "sgtk_alembic_sop.otl")
            )
            in sanitized_loaded_files
        )
