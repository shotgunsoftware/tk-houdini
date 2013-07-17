__all__ = ['QtCore', 'QtGui', 'QtNetwork', 'QtOpenGL', 'QtSql', 'QtSvg', 'QtTest', 'QtWebKit', 'QtScript']
__version__         = "1.2.0"
__version_info__    = (1, 2, 0, "final", 0)


def _setupQtDirectories():
    import sys
    import os
    from . import _utils

    pysideDir = _utils.get_pyside_dir()

    # On Windows add the PySide\openssl folder (if it exists) to the
    # PATH so the SSL DLLs can be found when Qt tries to dynamically
    # load them.  Tell Qt to load them and then reset the PATH.
    if sys.platform == 'win32':
        opensslDir = os.path.join(pysideDir, 'openssl')
        if os.path.exists(opensslDir):
            path = os.environ['PATH']
            try:
                os.environ['PATH'] = opensslDir + os.pathsep + path
                try:
                    from . import QtNetwork
                except ImportError:
                    pass
                else:
                    QtNetwork.QSslSocket.supportsSsl()
            finally:
                os.environ['PATH'] = path

    # Tell Qt to look for plugins in the PySide package, if the
    # plugins folder exists there, instead of just the default of
    # looking only in Qt's install or build folder.
    try:
        from . import QtCore
    except ImportError:
        pass
    else:
        pluginsDir = os.path.join(pysideDir, 'plugins')
        if os.path.exists(pluginsDir) and \
               pluginsDir not in QtCore.QCoreApplication.libraryPaths():
            QtCore.QCoreApplication.addLibraryPath(pluginsDir)

    # Tell Qt to look for qml imports in the PySide package, if the
    # imports folder exists there.
    importsDir = os.path.join(pysideDir, 'imports')
    if os.path.exists(importsDir):
        if 'QML_IMPORT_PATH' in os.environ:
            qml_import_path = os.environ['QML_IMPORT_PATH']
            os.environ['QML_IMPORT_PATH'] = importsDir + os.pathsep + qml_import_path
        else:
            os.environ['QML_IMPORT_PATH'] = importsDir


_setupQtDirectories()
