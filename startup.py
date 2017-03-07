# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import glob
import os
import re
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

    # Glob strings to insert into the executable template paths when globbing
    # for executables and bundles on disk. Globbing is admittedly limited in
    # terms of specific match strings, but if we need to introduce more precise
    # match strings later, we can do it in one place rather than each of the
    # template paths defined below.
    COMPONENT_GLOB_LOOKUP = {
        "version": "*",
        "product": "*",
        "executable": "*",
        "version_back": "*",
    }

    # Named regex strings to insert into the executable template paths when
    # matching against supplied versions and products. Similar to the glob
    # strings, these allow us to alter the regex matching for any of the
    # variable components of the path in one place
    COMPONENT_REGEX_LOOKUP = {
        "version": "(?P<version>[\d.]+)",
        "product": "(?P<product>[\w\s]+)",
        "executable": "(?P<executable>[\w]+)",
        "version_back": "(?P=version)",
    }

    # This dictionary defines a list of executable template strings for each
    # of the supported operating systems. The templates are used for both
    # globbing and regex matches by replacing the named format placeholders
    # with an appropriate glob or regex string. As Side FX adds modifies the
    # install path on a given OS for a new release, a new template will need
    # to be added here.
    # TODO: check hou 16 on windows/linux
    EXECUTABLE_MATCH_TEMPLATES = {
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
        return "15.0"

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
            self.logger.info("Launch plugins: %s" % (launch_plugins,))
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

        self.logger.info("Launch environment: %s" % (required_env,))

        return LaunchInformation(exec_path, args, required_env)

    def _scan_software(self):
        """
        Scan the filesystem for all houdini executables.

        :return: A list of :class:`SoftwareVersion` objects.
        """

        self.logger.debug("Scanning for Houdini executables...")

        # use the bundled engine icon
        icon_path = os.path.join(
            self.disk_location,
            "icon_256.png"
        )
        self.logger.debug("Using icon path: %s" % (icon_path,))

        # all the executable templates for the current OS
        match_templates = self.EXECUTABLE_MATCH_TEMPLATES.get(sys.platform, [])

        # all the discovered executables
        all_sw_versions = []

        for match_template in match_templates:

            # build the glob pattern by formatting the template for globbing
            glob_pattern = match_template.format(**self.COMPONENT_GLOB_LOOKUP)
            self.logger.debug(
                "Globbing for executable matching: %s ..." % (glob_pattern,)
            )

            # now match against files on disk
            executable_paths = glob.glob(glob_pattern)

            self.logger.debug("Found %s matches" % (len(executable_paths),))

            if not executable_paths:
                # no matches. move on to the next template
                continue

            # construct the regex string to extract the components
            regex_pattern = match_template.format(**self.COMPONENT_REGEX_LOOKUP)

            # accumulate the software version objects to return. this will
            # include the head/tail anchors in the regex
            regex_pattern = "^%s$" % (regex_pattern,)

            self.logger.debug(
                "Matching components against regex: %s" % (regex_pattern,))

            # compile the regex
            executable_regex = re.compile(regex_pattern, re.IGNORECASE)

            # now that we have a list of matching executables on disk we can
            # extract the component pieces. iterate over each executable found
            # for the glob pattern and find matched components via the regex
            for executable_path in executable_paths:

                self.logger.debug("Processing path: %s" % (executable_path,))

                match = executable_regex.match(executable_path)

                if not match:
                    self.logger.debug("Path did not match regex.")
                    continue

                # extract the components (default to None if not included)
                executable_version = match.groupdict().get("version")
                executable_product = match.groupdict().get("product")
                executable_name = match.groupdict().get("executable")

                # we need a product to match against. If that isn't provided,
                # then an executable name should be available. We can map that
                # to the proper product.
                if not executable_product:
                    executable_product = \
                        self.EXECUTABLE_TO_PRODUCT.get(executable_name)

                # no executable product. we don't recognize this product
                if not executable_product:
                    self.logger.debug("This product is unrecognized. Skipping.")
                    continue

                all_sw_versions.append(
                    SoftwareVersion(
                        executable_version,
                        executable_product,
                        executable_path,
                        icon_path
                    )
                )

        return all_sw_versions

