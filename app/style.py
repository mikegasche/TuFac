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

# File:        style.py
# Author:      Michael Gasche
# Created:     2026-08
# Product:     TuFac
# Description: Dark application theme (palette and stylesheet).


from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import QStyleFactory


def question_icon(size=48):
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#4a7fa5"))
    painter.drawEllipse(2, 2, size - 4, size - 4)
    painter.setPen(QColor(TEXT))
    font = painter.font()
    font.setPixelSize(int(size * 0.72))
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "?")
    painter.end()
    return pixmap


ACCENT = "#3399ff"
ACCENT_HOVER = "#55aaff"
WINDOW = "#1e1e1e"
PANEL = "#191919"
FIELD = "#262626"
BORDER = "#3a3a3a"
BACKGROUND_MENU = "#323232"
TEXT = "#ffffff"
TEXT_MUTED = "#a8a8a8"
TREE_TEXT = "#d8d8d8"
TREE_ACCOUNT = "#b8b8b8"
BRANCH_SHIFT = 2
BRANCH_DOT = "#a0a0a0"
BRANCH_DOT_RADIUS = 3
TITLE = "#abd0da"

APP_STYLE = f"""
* {{
    font-family: "Arial";
    font-size: 13px;
}}

QMainWindow, QDialog, QMessageBox {{
    background-color: {WINDOW};
    color: {TEXT};
}}

QWidget#detailPanel {{
    background-color: {PANEL};
}}

QLabel {{
    color: {TEXT_MUTED};
    background: transparent;
}}

QLineEdit, QComboBox, QSpinBox {{
    background-color: {FIELD};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    color: {TEXT};
    selection-background-color: {ACCENT};
    selection-color: {TEXT};
}}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border: 1px solid {ACCENT};
}}

QLineEdit:disabled {{
    color: #808080;
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox::down-arrow {{
    width: 0;
    height: 0;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #b0b0b0;
}}

QComboBox QAbstractItemView {{
    background-color: #2a2a2a;
    border: 1px solid {BORDER};
    color: {TEXT};
    selection-background-color: {ACCENT};
    selection-color: {TEXT};
    outline: none;
}}

QPushButton {{
    background-color: #747474;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    color: {TEXT};
}}

QPushButton:hover {{
    background-color: #909090;
}}

QPushButton:pressed {{
    background-color: #5c5c5c;
}}

QPushButton:disabled {{
    background-color: #3a3a3a;
    color: #808080;
}}

QPushButton#primaryButton {{
    background-color: {ACCENT};
}}

QPushButton#primaryButton:hover {{
    background-color: {ACCENT_HOVER};
}}

QPushButton#primaryButton:pressed {{
    background-color: #2277cc;
}}

QPushButton#iconButton {{
    background: transparent;
    border: none;
}}

QTreeWidget {{
    background-color: {WINDOW};
    border: none;
    color: {TREE_TEXT};
    font-size: 14px;
    outline: none;
    padding-top: 4px;
}}

QTreeWidget::item {{
    padding: 5px 4px;
    border-radius: 4px;
}}

QTreeWidget::item:hover {{
    background-color: {FIELD};
}}

QTreeWidget::item:selected {{
    background-color: {ACCENT};
    color: {TEXT};
}}

QHeaderView::section {{
    background-color: {FIELD};
    color: {TEXT_MUTED};
    border: none;
    padding: 6px;
}}

QMenuBar {{
    background-color: {BACKGROUND_MENU};
    color: {TEXT};
}}

QMenuBar::item {{
    padding: 6px 10px;
    background: transparent;
}}

QMenuBar::item:selected {{
    background-color: {ACCENT};
    color: {TEXT};
}}

QMenu {{
    background-color: {FIELD};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 6px;
}}

QMenu::item {{
    padding: 6px 22px;
    border-radius: 4px;
}}

QMenu::item:selected {{
    background-color: {ACCENT};
    color: {TEXT};
}}

QMenu::separator {{
    height: 1px;
    background-color: {BORDER};
    margin: 4px 8px;
}}

QStatusBar {{
    background-color: {WINDOW};
    color: {TEXT_MUTED};
    border-top: 1px solid {BORDER};
}}

QStatusBar::item {{
    border: none;
}}

QSplitter::handle {{
    background-color: {FIELD};
    width: 3px;
}}

QScrollBar:vertical {{
    background: {WINDOW};
    width: 12px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 6px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background: #4a4a4a;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background: {WINDOW};
    height: 12px;
    margin: 0;
}}

QScrollBar::handle:horizontal {{
    background: {BORDER};
    border-radius: 6px;
    min-width: 30px;
}}

QScrollBar::handle:horizontal:hover {{
    background: #4a4a4a;
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

QToolTip {{
    background-color: {FIELD};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 4px 8px;
}}

QMessageBox QLabel {{
    color: {TEXT};
}}
"""


def create_palette():
    palette = QPalette()

    palette.setColor(QPalette.ColorRole.Window, QColor(WINDOW))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Base, QColor(FIELD))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#2a2a2a"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(FIELD))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Text, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#8a8a8a"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#747474"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Link, QColor(ACCENT_HOVER))
    palette.setColor(QPalette.ColorRole.Light, QColor("#2a2a2a"))
    palette.setColor(QPalette.ColorRole.Mid, QColor(BORDER))
    palette.setColor(QPalette.ColorRole.Midlight, QColor("#3a3a3a"))
    palette.setColor(QPalette.ColorRole.Dark, QColor(WINDOW))

    return palette


def apply_theme(app):
    app.setPalette(create_palette())
    app.setStyle(QStyleFactory.create("Fusion"))
    app.setStyleSheet(APP_STYLE)
