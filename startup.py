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

from sgtk.platform import SoftwareLauncher, SoftwareVersion, LaunchInformation


class HoudiniLauncher(SoftwareLauncher):
    """
    Handles launching Houdini executables. Automatically starts up a tk-houdini
    engine with the current context in the new session of Houdini.
    """

    # A lookup to map an executable name to a product. This is critical for
    # windows and linux where the product does not show up in the path.
    EXECUTABLE_TO_PRODUCT = {
        "houdini": "houdini",
        "hescape": "houdini",
        "happrentice": "houdini apprentice",
        "houdinicore": "houdini core",
        "houdinifx": "houdini fx",
        "hindie": "houdini indie",
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
    # of the supported operating systems. The templates can are used for both
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
            "C:\\Program Files\\Side Effects Software\\Houdini {version}\\bin\\{executable}.exe",
        ],
        "linux": [
            # example path: /opt/hfs14.0.444/bin/houdinifx
            "/opt/hfs{version}/bin/{executable}",
        ]
    }

    def scan_software(self, versions=None, products=None):
        """
        Performs a scan for software installations.

        :param list versions: List of strings representing versions to search
            for. If set to None, search for all versions.

        :param list products: List of strings representing products to search
            for. If set to None, search for all versions.

        :returns: List of :class:`SoftwareVersion` instances
        """

        self.logger.debug("Scanning for Houdini versions...")
        self.logger.debug("Version constraints: %s" % (versions,))
        self.logger.debug("Product constraints: %s" % (products,))

        # use the bundled icon
        icon_path = os.path.join(
            self.disk_location,
            "resources",
            "houdini_logo.png"
        )
        self.logger.debug("Using icon path: %s" % (icon_path,))

        if sys.platform not in ["darwin", "win32", "linux"]:
            self.logger.debug("Houdini not supported on this platform.")
            return []

        # all the executable templates for the current OS
        match_templates = self.EXECUTABLE_MATCH_TEMPLATES[sys.platform]

        # all the executables matching the supplied filters.
        software_versions = []

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

            regex_pattern = match_template

            if sys.platform == "win32":
                # on windows make sure we double escape the path separators
                # prior to matching to prevent evaluation as regex components.
                regex_pattern = regex_pattern.replace("\\", "\\\\")

            # construct the regex string to extract the components
            regex_pattern = regex_pattern.format(**self.COMPONENT_REGEX_LOOKUP)

            # accumulate the software version objects to return. this will
            # include the head/tail anchors in the regex
            regex_pattern = "^%s$" % (regex_pattern,)

            self.logger.debug(
                "Matching components against regex: %s" % (regex_pattern,))

            # compile the regex
            executable_regex = re.compile(regex_pattern, re.IGNORECASE)

            # now that we have a list of matching executables on disk we can
            # extract the component pieces to see if they match the supplied
            # version/product constraints. iterate over each executable found
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

                # version filter.
                if versions and executable_version:

                    # TODO: is supported, minimum version check

                    if executable_version not in versions:
                        self.logger.debug(
                            "'%s' does not match the version constraint" % (
                                executable_version,
                            )
                        )
                        continue

                # product filter
                if products and executable_product:

                    if executable_product not in products:
                        # the matched product product doesn't match
                        self.logger.debug(
                            "'%s' does not match the product constraint" % (
                                executable_product,
                            )
                        )
                        continue

                # no executable product. we don't recognize this product
                if not executable_product:
                    self.logger.debug("This product is unrecognized. Skipping.")
                    continue

                # if we're here then we know the version is valid or there is
                # no version filter. we also know that the product is a match or
                # there is no product filter. we can safely create a software
                # version instance to return

                executable_display = executable_product.replace("Houdini", "")
                display_name = "%s %s" % (executable_display, executable_version)
                # Either we don't have a version constraint list of this
                # version matches one of the constraints. Add this to the
                # list of SW versions to return.
                software_versions.append(
                    SoftwareVersion(
                        executable_version,
                        executable_product,
                        display_name,
                        executable_path,
                        icon_path
                    )
                )
                self.logger.debug("Filter match: %s" % (display_name,))

        return software_versions

    def prepare_launch(self, exec_path, args, file_to_open=None):
        """
        Prepares the given software for launch

        :param str exec_path: Path to DCC executable to launch

        :param str args: Command line arguments as strings

        :param str file_to_open: (optional) Full path name of a file to open on
            launch

        :returns: :class:`LaunchInformation` instance
        """

        tk_houdini_python_path = os.path.join(
            self.disk_location,
            "python",
        )

        sys.path.insert(0, tk_houdini_python_path)
        from tk_houdini import bootstrap

        # determine all environment variables
        required_env = bootstrap.compute_environment()

        # Add std context and site info to the env
        std_env = self.get_standard_plugin_environment()
        required_env.update(std_env)

        return LaunchInformation(exec_path, args, required_env)










