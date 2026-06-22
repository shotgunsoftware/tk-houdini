# -
# *****************************************************************************
# Copyright 2026 Autodesk, Inc. All rights reserved.
#
# These coded instructions, statements, and computer programs contain
# unpublished proprietary information written by Autodesk, Inc. and are
# protected by Federal copyright law. They may not be disclosed to third
# parties or copied or duplicated in any form, in whole or in part, without
# the prior written consent of Autodesk, Inc.
# *****************************************************************************
#

from __future__ import annotations  # needed for python 3.9 support

import os

from tank import LogManager
from tank.flowam.host import FlowHost
from tank_vendor.flow_integration_sdk.dependency import DependencyData
from tank_vendor.flow_integration_sdk.utils import (
    cleanpath,
    fileext,
    trace,
)

import hou


class HoudiniHost(FlowHost):
    """Houdini implementation of FlowHost interface.
    This is a collection of required capabilities to support Flow AM integration.
    """

    logger = LogManager.get_logger("MayaHost")

    #: The schema name associated with Houdini workfiles
    WORKFILE_TYPE = "type.workfile.hou"
    #: Houdini file extensions
    FILE_TYPES = ["hip", "hipnc"]
    #: Export file types
    EXPORT_TYPES = ["abc"]
    #: Houdini file mime types
    MIME_TYPES = {
        "hip": "application/vnd.houdini.hip",
        "hipnc": "application/vnd.houdini.hipnc",
    }

    # ------------------------------------------
    # BASE CLASS INTERFACE
    # ------------------------------------------

    def __init__(self, context):

        self.logger.info("Doing HoudiniHost initialization...")

        super().__init__(context)

        # Add callbacks for relevant Houdini events
        hou.hipFile.addEventCallback(self._on_file_event)

    @trace
    def current_file(self) -> str:
        """Return current open file path in dcc."""
        return cleanpath(hou.hipFile.path())

    @trace
    def new_scene(self, force: bool = True) -> str:
        """Start new scene in Houdini.

        Args:
            force: If true, force action even if there are unsaved changes.

        Returns:
            True if new scene is opened, False if operation is cancelled.
        """
        # NOTE: Houdini automatically handles warning for unsaved changes
        #       with options "Save and New", "Discard and New" and "Cancel".
        return hou.hipFile.clear(suppress_save_prompt=force)

    @trace
    def open_file(self, file_path: str) -> bool:
        """Open given file path in Houdini.

        Args:
            file_path: Full path to Maya scene file to be opened.

        Returns:
            True if file is opened, False on error or if operation is cancelled.
        """
        # NOTE: Houdini automatically handles warning for unsaved changes
        #       with options "Save and Open", "Discard and Open" and "Cancel".
        hou.hipFile.load(file_path, ignore_load_warnings=True)
        return True

    @trace
    def save_file(self, file_path: str):
        """Save the current scene to the specified file path.

        Args:
            file_path: Absolute local path to save file.

        Raises:
            ValueError
        """
        ext = fileext(file_path)
        if ext not in self.FILE_TYPES:
            raise ValueError(f'Invalid native file extension "{ext}" provided.')

        hou.hipFile.save(file_path)

    @trace
    def export(self, file_path: str) -> None:
        """Export current scene to file path specified and file type
        designated by file extension.

        Args:
            file_path: Absolute local path to export file.

        Raises:
            ValueError
            RuntimeError
        """
        ext = fileext(file_path)
        if ext not in self.EXPORT_TYPES:
            raise ValueError(f'Export type "{ext}" is not supported.')

        if ext == "abc":
            self._export_alembic(file_path)

    @trace
    def dialog(
        self,
        title: str,
        msg: str,
        buttons: list[str] | None = None,
        default: int = 0,
        cancel: int | None = None,
        no_ui_option: int | None = None,
    ) -> int:
        """Pop up a dialog in the dcc.

        Args:
            title: Title of dialog window.
            msg: Message to be displayed.
            buttons: List of strings denoting buttons to be added to dialog.
            default: Index of default button. Invalid indices will be ignored and no default
                     action will be set. In this case, if multiple choices are available,
                     user will not be able to choose action by hitting <enter>.
            cancel: Index of cancel button. If not specified, and multiple choices are
                    available, user will not be able to exit the dialog via close button.
            no_ui_option: If Houdini is running without UI, this option will automatically be returned.
                          If None, use default value.

        Returns:
            The index of the button selected by user.
        """
        if not hou.isUIAvailable():
            # Houdini is running without UI, return default behaviour
            return no_ui_option if no_ui_option is not None else default

        buttons = buttons or ["OK"]
        kwargs = {
            "title": title,
            "text": msg,
            "buttons": buttons,
            "default_choice": default,
        }
        if cancel is not None:
            kwargs["close_choice"] = cancel

        return hou.ui.displayMessage(**kwargs)

    @trace
    def file_dialog(
        self,
        title: str,
        starting_dir: str = "",
        folder_mode: bool = False,
        file_type: str = "",
        multi_select: bool = False,
    ) -> list[str]:
        """Invoke a file dialog for selecting one or more file paths.

        Args:
            title: Title of dialog.
            starting_dir: Starting location of dialog.
            folder_mode: If True, dialog will browse folders instead of files.
            file_type: Extension of file type to filter for.
                         Applicable only when browsing files.
            multi_select: If True, allow multiple selection of files.

        Returns:
            A list of file/directory paths.
            If multi_select = False, the return value will be a list of size 1.
            If user cancels or dialog couldn't be shown, list will be empty.
            If Houdini is running without a GUI, empty list is returned.
        """
        if not hou.isUIAvailable():
            # Houdini is running without UI
            return []

        if folder_mode:
            hou_file_type = hou.fileType.Directory
        else:
            hou_file_type = hou.fileType.Any

        file_filter = f"*.{file_type}" if file_type else ""

        result = hou.ui.selectFile(
            title=title,
            start_directory=starting_dir,
            file_type=hou_file_type,
            pattern=file_filter,
            multiple_select=multi_select,
        )
        if not result:
            return []
        if multi_select:
            # Multiple paths are returned as a semi-colon delimited string
            # with extra spaces in between
            result = [path.strip() for path in result.split(";")]
        else:
            result = [result]
        return result

    @trace
    def copy_to_clipboard(self, text: str) -> bool:
        """Copy given text to clipboard.

        Args:
            text: Text to be copied.

        Returns:
            True on success.
        """
        if hou.isUIAvailable():
            hou.ui.copyTextToClipboard(text)
            return True
        else:
            return False

    @trace
    def get_dependency_tree(self, must_exist: bool = True) -> DependencyData:
        """Return a DependencyData object which is the root of the
        dependency tree for the scene.

        Args:
            must_exist: Only return dependencies that can be found on disk.
        """
        dependencies = self._get_sop_dependencies(must_exist=must_exist)
        dependencies.sort()
        root = DependencyData(dependencies=dependencies)
        for d in dependencies:
            d.parent = root
        return root

    @trace
    def update_dependency(
        self,
        dep: DependencyData,
        file_path: str,
    ) -> DependencyData:
        """Update an existing reference to point to given file in current scene.

        Args:
            dep: DependencyData node which identifies the dependency to be updated.
            file_path: New path to set dependency to.

        Returns:
            DependencyData object.
            NOTE: This will be an isolated node, not including sub-dependency info.

        Raises:
            RuntimeError
        """
        node_handle = dep.node_handle
        node = hou.node(node_handle)
        if node is None:
            msg = "Error updating dependency. "
            msg += f"Invalid node path provided: {node_handle}."
            raise RuntimeError(msg)

        ref_path = file_path
        if node.type().name() == "reference::2.0":
            # quotes required if spaces in file path (only for reference node)
            ref_path = f'"{ref_path}"'

        attribute = dep.attribute or "filepath1"
        node.parm(attribute).set(ref_path)

        self.logger.info(
            f'Reference node "{node_handle}" updated to point to file "{file_path}".'
        )

        return DependencyData(
            node_handle=node.path(),
            node_type=node.type().name(),
            attribute=attribute,
            file_path=node.parm(attribute).eval(),
            raw_path=file_path,
        )

    # ------------------------------------------
    # ADDITIONAL SUBCLASS FUNCTIONS
    # ------------------------------------------

    def _get_sop_dependencies(
        self,
        filter_nodes: set[str] | None = None,
        ignore_nodes: set[str] | None = None,
        must_exist: bool = True,
    ) -> list[DependencyData]:
        """Returns all references to external files in the current scene.
        Examples include textures, geometry caches, and usd files.

        Args:
            filter_nodes: Optionally provide a list of filter nodes.
                          Return the subset of these nodes that are dependencies.
            ignore_nodes: Optionally provide a list of nodes to ignore.
            must_exist: Only return dependencies that can be found on disk.

        Returns:
            List of DependencyData objects containing all pertinent information
            related to a file dependency.
        """
        deps = []

        # NOTE: for now it is safe to treat houdini file references as flat list
        #       because Houdini cannot reference scene files other than usd, and we
        #       are not supporting introspection of usd files yet.

        for parm, _ in hou.fileReferences():
            if parm is None:
                continue
            node = parm.node()
            if filter_nodes and node.path() not in filter_nodes:
                continue
            if ignore_nodes and node.path() in ignore_nodes:
                continue
            if "LOPNET_for_Import" in node.path():
                # This is a duplicate file reference that gets picked up with
                # sop usd imports, so ignore it.
                continue
            # Evaluating the parm will give us an absolute path (with env vars evaluated)
            full_path = cleanpath(parm.eval().strip('"'))
            raw_path = cleanpath(parm.rawValue().strip('"'))
            if must_exist and not os.path.isfile(full_path):
                continue
            deps.append(self._create_dep(parm, node, full_path, raw_path))

        return deps

    def _create_dep(self, parm, node, full_path, raw_path):
        """Create the appropriate DependencyData object."""
        dep = DependencyData(
            node_handle=node.path(),
            node_type=node.type().name(),
            attribute=parm.name(),
            file_path=full_path,
            raw_path=raw_path,
            dependencies=[],
        )
        dep.identify_component()
        dep.set_type()
        return dep

    def _on_file_event(self, event_type=None):
        """Receive Houdini file events and redirect to registered callbacks."""
        if event_type == hou.hipFileEventType.AfterClear:
            self.context.clear_flow_context()
        elif event_type == hou.hipFileEventType.AfterLoad:
            file_path = self.current_file()
            self.context.set_flow_context(file_path)

    def _export_alembic(self, file_path: str):
        """Export current scene to alembic file."""

        # Create an alembic ROP
        alembic_rop = hou.node("/out").createNode("alembic", "flow_alembic_export")

        # Set the output file path
        alembic_rop.parm("filename").set(file_path)

        # Set object list to all objects in scene
        obj_node = hou.node("/obj")
        all_objects = obj_node.children()
        all_object_paths = [o.path() for o in all_objects]
        alembic_rop.parm("objects").set(" ".join(all_object_paths))

        # Export full frame range of scene with an increment of 1
        start_frame, end_frame = hou.playbar.frameRange()
        alembic_rop.parm("trange").set(1)  # render a frame range
        alembic_rop.parmTuple("f").set((start_frame, end_frame, 1))

        msg = f"Exporting alembic with frame range ({start_frame}, {end_frame}) to {file_path}..."
        self.logger.info(msg)
        try:
            alembic_rop.render()
        except Exception as exc:  # pylint: disable=broad-except
            raise RuntimeError("Alembic export failed.") from exc
        self.logger.info("Alembic export complete!")

        # Clean up node
        alembic_rop.destroy()
