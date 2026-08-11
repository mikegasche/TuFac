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

# File:        settings_dialog.py
# Author:      Michael Gasche
# Created:     2026-08
# Product:     TuFac
# Description: Settings dialog for TuFac.


import sys

import autostart
from config import APP_NAME
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle(f"{APP_NAME} Settings")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        autostart_label = QLabel("Start at login")
        autostart_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(autostart_label)

        self.autostart_check = QCheckBox("Start TuFac automatically when the computer starts")
        self.autostart_check.setChecked(autostart.is_enabled())
        layout.addWidget(self.autostart_check)

        note = QLabel()
        if sys.platform == "darwin":
            note_text = "Uses a macOS LaunchAgent. TuFac only starts when you enable this option."
        elif sys.platform == "win32":
            note_text = "Uses a Windows registry entry (current user)."
        else:
            note_text = "Auto-start is not supported on this platform."
        note.setText(note_text)
        note.setWordWrap(True)
        note.setStyleSheet("color: #8a8a8a; font-size: 12px;")
        layout.addWidget(note)

        layout.addSpacing(8)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
        ok_button.setText("OK")
        ok_button.setObjectName("primaryButton")
        button_box.accepted.connect(self._apply)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _apply(self):
        if self.autostart_check.isChecked():
            autostart.enable()
        else:
            autostart.disable()
        self.accept()
