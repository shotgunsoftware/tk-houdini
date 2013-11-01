# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import hou

from tank.platform.qt import QtCore


class IntegratedEventLoop(object):
    """This class behaves like QEventLoop except it allows Python's Qt to run inside
    Houdini's event loop on the main thread.  You probably just want to
    call exec_() below instead of using this class directly.
    """
    def __init__(self, application):
        # We need the application to send posted events.  We hold a reference
        # to any dialogs to ensure that they don't get garbage collected
        # (and thus close in the process).  The reference count for this object
        # will go to zero when it removes itself from Houdini's event loop.
        self.application = application
        self.event_loop = QtCore.QEventLoop()

    def exec_(self):
        hou.ui.addEventLoopCallback(self.processEvents)

    def processEvents(self):
        self.event_loop.processEvents()
        self.application.sendPostedEvents(None, 0)


def exec_(application):
    """You cannot call QApplication.exec_, or Houdini will freeze while Python's Qt
    waits for and processes events.  Instead, call this function to allow
    Houdini's and Python's Qt's event loops to coexist.  Pass in any dialogs as
    extra arguments, if you want to ensure that something holds a reference
    to them while the event loop runs.

    This function returns right away.
    """
    IntegratedEventLoop(application).exec_()
