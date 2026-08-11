# ------------------------------------------------------------------------------
# Copyright (c) 2026 Michael Gasche
#
# TuFac is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# TuFac is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with TuFac. If not, see <https://www.gnu.org/licenses/>.
# ------------------------------------------------------------------------------

# File:        tufac.py
# Author:      Michael Gasche
# Created:     2026-08
# Product:     TuFac
# Description: Application entry point for the TuFac TOTP manager.


import sys

from config import APP_NAME, APP_VERSION, TRAY_MODE
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon
from style import apply_theme
from tufac_gui import TuFacWindow, resource_path

app = None
window = None
LOGGING = False


def log(message):
    if LOGGING:
        with open("/tmp/tufac.log", "a") as f:
            f.write(message + "\n")


def create_window():
    global window
    if window is None:
        window = TuFacWindow()


def show_window():
    global window
    if window is None:
        create_window()

    window.show()
    window.raise_()
    window.activateWindow()
    window.setWindowState(window.windowState() & ~Qt.WindowState.WindowMinimized)


def tray_icon_path():
    if sys.platform == "darwin":
        return resource_path("tufac_trayTemplate.png")

    return resource_path("tufac_logo.png")


def create_tray():
    global window

    icon = QIcon(str(tray_icon_path()))
    if sys.platform == "darwin":
        icon.setIsMask(True)

    tray = QSystemTrayIcon(icon, window)
    tray.setToolTip(APP_NAME)

    menu = QMenu(window)

    show_action = QAction("Show TuFac", menu)
    show_action.triggered.connect(lambda: show_window())
    menu.addAction(show_action)

    settings_action = QAction("Settings...", menu)
    settings_action.triggered.connect(window.open_settings)
    menu.addAction(settings_action)

    menu.addSeparator()

    quit_action = QAction("Quit", menu)
    quit_action.triggered.connect(window.quit_app)
    menu.addAction(quit_action)

    tray.setContextMenu(menu)
    tray.activated.connect(
        lambda reason: (
            show_window() if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None
        )
    )
    tray.show()

    return tray


def main():
    global app, window

    app = QApplication(sys.argv)

    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)

    log("QApplication created")

    apply_theme(app)

    create_window()

    if TRAY_MODE:
        app.setQuitOnLastWindowClosed(False)
        _tray = create_tray()

        if "--autostart" not in sys.argv:
            show_window()
    else:
        show_window()

    ret = app.exec()

    window = None

    sys.exit(ret)


if __name__ == "__main__":
    main()
