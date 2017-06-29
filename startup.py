# Copyright (c) 2016 Shotgun Software Inc.
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

import sgtk
from sgtk.platform import SoftwareLauncher, SoftwareVersion, LaunchInformation


class HoudiniLauncher(SoftwareLauncher):
    """
    Handles launching Houdini executables. Automatically starts up a tk-houdini
    engine with the current context in the new session of Houdini.
    """

    # A lookup to map an executable name to a product. This is critical for
    # windows and linux where the product does not show up in the path.
    EXECUTABLE_TO_PRODUCT = {
        "houdini": "Houdini",
        "hescape": "Houdini",
        "happrentice": "Houdini Apprentice",
        "houdinicore": "Houdini Core",
        "houdinifx": "Houdini FX",
        "hindie": "Houdini Indie",

    }

    # Named regex strings to insert into the executable template paths when
    # matching against supplied versions and products. Similar to the glob
    # strings, these allow us to alter the regex matching for any of the
    # variable components of the path in one place
    COMPONENT_REGEX_LOOKUP = {
        "version": "[\d.]+",
        "product": "[\w\s]+",
        "executable": "[\w]+",
        "version_back": "[\d.]+",
    }

    # This dictionary defines a list of executable template strings for each
    # of the supported operating systems. The templates are used for both
    # globbing and regex matches by replacing the named format placeholders
    # with an appropriate glob or regex string. As Side FX adds modifies the
    # install path on a given OS for a new release, a new template will need
    # to be added here.
    EXECUTABLE_TEMPLATES = {
        "darwin": [
            # /Applications/Houdini 15.5.565/Houdini.app
            "/Applications/Houdini {version}/{product}.app",

            # /Applications/Houdini/Houdini16.0.504.20/Houdini Core 16.0.504.20.app
            "/Applications/Houdini/Houdini{version}/{product} {version_back}.app",
        ],
        "win32": [
            # C:\Program Files\Side Effects Software\Houdini 15.5.565\bin\houdinifx.exe
            "C:/Program Files/Side Effects Software/Houdini {version}/bin/{executable}.exe",
        ],
        "linux2": [
            # example path: /opt/hfs14.0.444/bin/houdinifx
            "/opt/hfs{version}/bin/{executable}",
        ]
    }

    @property
    def minimum_supported_version(self):
        """The minimum supported Houdini version."""
        return "14.0"

    def prepare_launch(self, exec_path, args, file_to_open=None):
        """
        Prepares the given software for launch

        :param str exec_path: Path to DCC executable to launch

        :param str args: Command line arguments as strings

        :param str file_to_open: (optional) Full path name of a file to open on
            launch

        :returns: :class:`LaunchInformation` instance
        """

        # construct the path to the engine's python directory and add it to sys
        # path. this provides us access to the bootstrap module which contains
        # helper methods for constructing the proper environment based on the
        # bootstrap scanario.
        tk_houdini_python_path = os.path.join(
            self.disk_location,
            "python",
        )
        sys.path.insert(0, tk_houdini_python_path)

        from tk_houdini import bootstrap

        # Check the engine settings to see whether any plugins have been
        # specified to load.
        launch_plugins = self.get_setting("launch_builtin_plugins")
        if launch_plugins:

            # Prepare the launch environment with variables required by the
            # plugin bootstrap.
            self.logger.debug("Launch plugins: %s" % (launch_plugins,))
            required_env = bootstrap.get_plugin_startup_env(launch_plugins)

            # Add context and site info
            required_env.update(self.get_standard_plugin_environment())

        else:

            # pull the env var names from the bootstrap module
            engine_env = bootstrap.g_sgtk_engine_env
            context_env = bootstrap.g_sgtk_context_env

            # Prepare the launch environment with variables required by the
            # classic bootstrap.
            required_env = bootstrap.get_classic_startup_env()
            required_env[engine_env] = self.engine_name
            required_env[context_env] = sgtk.context.serialize(self.context)

        # populate the file to open env. Note this env variable name existed
        # pre software launch setup.
        if file_to_open:
            file_to_open_env = bootstrap.g_sgtk_file_to_open_env
            required_env[file_to_open_env] = file_to_open

        self.logger.debug("Launch environment: %s" % (required_env,))

        return LaunchInformation(exec_path, args, required_env)

    def scan_software(self):
        """
        Scan the filesystem for houdini executables.

        :return: A list of :class:`SoftwareVersion` objects.
        """

        self.logger.debug("Scanning for Houdini executables...")

        supported_sw_versions = []
        for sw_version in self._find_software():
            (supported, reason) = self._is_supported(sw_version)
            if supported:
                supported_sw_versions.append(sw_version)
            else:
                self.logger.debug(
                    "SoftwareVersion %s is not supported: %s" %
                    (sw_version, reason)
                )

        return supported_sw_versions

    def _find_software(self):

        # use the bundled engine icon
        icon_path = os.path.join(
            self.disk_location,
            "icon_256.png"
        )
        self.logger.debug("Using icon path: %s" % (icon_path,))

        # all the executable templates for the current OS
        executable_templates = self.EXECUTABLE_TEMPLATES.get(sys.platform, [])

        # all the discovered executables
        sw_versions = []

        for executable_template in executable_templates:

            self.logger.debug("Processing template %s.", executable_template)

            executable_matches = self._glob_and_match(
                executable_template,
                self.COMPONENT_REGEX_LOOKUP
            )

            # Extract all products from that executable.
            for (executable_path, key_dict) in executable_matches:

                # extract the matched keys form the key_dict (default to None if
                # not included)
                executable_version = key_dict.get("version")
                executable_product = key_dict.get("product")
                executable_name = key_dict.get("executable")

                # we need a product to match against. If that isn't provided,
                # then an executable name should be available. We can map that
                # to the proper product.
                if not executable_product:
                    executable_product = \
                        self.EXECUTABLE_TO_PRODUCT.get(executable_name)

                # only include the products that are covered in the EXECUTABLE_TO_PRODUCT dict
                if executable_product is None or executable_product not in self.EXECUTABLE_TO_PRODUCT.values():
                    self.logger.debug(
                        "Product '%s' is unrecognized. Skipping." %
                        (executable_product,)
                    )
                    continue

                sw_versions.append(
                    SoftwareVersion(
                        executable_version,
                        executable_product,
                        executable_path,
                        icon_path
                    )
                )

        return sw_versions
