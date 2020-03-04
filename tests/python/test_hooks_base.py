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

from tank_test.tank_test_base import TankTestBase, setUpModule


class TestHooks(TankTestBase):
    """
    Tests the hooks of all apps.
    """

    def setUp(self):
        """
        Set up the configuration and start the engine.
        """
        # TODO: add clean up for files created.
        super(TestHooks, self).setUp()
        self.setup_fixtures()

        # Cleanup the scene before the test run so we don't get polluted with
        # the current scene content.
        self._reset_scene()
        # Always cleanup the scene after tests have run to have a clean slate.
        self.addCleanup(self._reset_scene)

        # Create an asset with a concept task.
        self._asset = self.mockgun.create(
            "Asset",
            {"code": "my_asset", "sg_asset_type": "Character", "project": self.project},
        )
        self._step = self.mockgun.create(
            "Step", {"code": "Concept", "short_name": "concept"}
        )
        self._task = self.mockgun.create(
            "Task",
            {
                "content": "Concept Art",
                "project": self.project,
                "step": self._step,
                "entity": self._asset,
            },
        )
        self._asset_task_ctx = self.create_context(self._task)

        # Start the engine and ensure it is destroyed
        self.engine = sgtk.platform.start_engine(
            "tk-houdini", self.tk, self._asset_task_ctx
        )
        self.addCleanup(self.engine.destroy)

    def _reset_scene(self):
        """
        Reset the current scene without prompting the user.
        """
        hou.hipFile.clear(suppress_save_prompt=True)

    def create_context(self, entity):
        """
        Create a context for the given entity and user.

        This method will also create the sandbox for that user.
        """
        context = self.tk.context_from_entity(entity["type"], entity["id"])

        self.tk.create_filesystem_structure(entity["type"], entity["id"])
        return context

    def _get_new_file_path(self, template, filename, version=1):
        """
        Returns a path generated from a template.
        """
        template = self.tk.templates[template]

        # Use the context to resolve as many of the template fields as possible.
        fields = self.engine.context.as_template_fields(template)

        # Manually resolve the remaining fields that can't be figured out automatically from context.
        fields["name"] = filename
        fields["version"] = version

        # Resolve the template path using the field values.
        return template.apply_fields(fields)

    def _create_file(self, filename, template="work_path"):
        """
        Create a file in the project folder. By default it will create file matching the `work_path`
        template unless a template is specified.
        """

        file_path = self._get_new_file_path(template, filename)
        hou.hipFile.save(file_name=file_path, save_to_recent_files=True)

        self.assertTrue(os.path.exists(file_path))
        return file_path
