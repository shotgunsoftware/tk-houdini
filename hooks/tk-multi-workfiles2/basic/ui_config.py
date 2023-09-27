# Copyright (c) 2021 Autodesk, Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Autodesk, Inc.

import sgtk
from sgtk.platform.qt import QtGui

HookClass = sgtk.get_hook_baseclass()


class HoudiniUIConfig(HookClass):
    """Hook to customize customize the main file view for Houdini."""

    def get_item_background_color(self, item):
        """
        Returns the brush to use to draw the background for this widget

        Top-level items will use the default brush (None is returned), and non-top level items
        will use the QPalette base brush to paint the background.

        :param item: The model item
        :type item: :class:`sgkt.platofrm.qt.QtGui.QStandardItem`

        :return: The QBrush.
        :rtype: :class:`sgtk.platform.qt.QtGui.QBrush`
        """

        parent = item.index().parent()
        if not parent.isValid():
            return

        return QtGui.QApplication.palette().base()
