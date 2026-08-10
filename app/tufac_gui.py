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

# File:        tufac_gui.py
# Author:      Michael Gasche
# Created:     2026-08
# Product:     TuFac
# Description: Graphical user interface for managing TOTP accounts.


import base64
import hashlib
import json
import sys
import time
from pathlib import Path

import pyotp
from config import APP_COPYRIGHT, APP_NAME, APP_VERSION, GITHUB_LINK
from crypto import decrypt_backup, is_envelope
from migration import decode_migration_url
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QPainter,
    QBrush,
    QPen,
    QFontMetrics,
    QIcon,
    QKeySequence,
    QPixmap,
)
from style import TREE_ACCOUNT, question_icon
from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QStyledItemDelegate,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from storage import TuFacStorage

PROJECT_ROOT = Path(__file__).resolve().parent
RESOURCE_DIR = PROJECT_ROOT / "resources"


def get_app_icon_name():
    if sys.platform == "win32":
        return "app_icon.ico"
    elif sys.platform == "darwin":
        return "app_icon.icns"
    return "app_icon.png"


def resource_path(name):
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS) / "resources"
    else:
        base = RESOURCE_DIR
    return base / name


def secret_to_base32(secret):
    return base64.b32encode(secret).decode("ascii").rstrip("=")


def decode_qr_image(filename):
    import cv2
    import zxingcpp

    image = cv2.imread(str(filename))

    if image is None:
        raise ValueError(f"Cannot read image:\n{filename}")

    results = zxingcpp.read_barcodes(image)

    values = [result.text for result in results if result.text]

    if not values:
        raise ValueError(f"No QR code found in:\n{filename}")

    return values


class ColorCircle(QLabel):
    def __init__(self, color=None, parent=None):
        super().__init__(parent)
        self.color = color
        self.setFixedSize(32, 32)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background: transparent;")
    
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        if self.color and self.color.isValid():
            painter.setBrush(QBrush(self.color))
        else:
            painter.setBrush(QBrush(QColor(200, 200, 200)))
        
        painter.setPen(QPen(Qt.GlobalColor.transparent, 0))
        painter.drawEllipse(4, 4, 24, 24)


class AccountTreeDelegate(QStyledItemDelegate):
    def updateEditorGeometry(self, editor, option, index):
        rect = option.rect
        height = max(rect.height() + 8, 28)
        text = index.data(Qt.ItemDataRole.DisplayRole)
        metrics = QFontMetrics(editor.font())
        width = metrics.horizontalAdvance(text or "") + 24
        width = min(width, editor.parent().width() - rect.x())
        editor.setGeometry(
            rect.x(),
            rect.y() - (height - rect.height()) // 2,
            width,
            height,
        )


class AccountTree(QTreeWidget):
    dropped = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setMinimumWidth(300)
        self.setItemDelegate(AccountTreeDelegate(self))
        
        # Enable multi-selection with Ctrl/Shift
        self.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        
        # Enable drag & drop for moving items
        self.setDragDropMode(QTreeWidget.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDropIndicatorShown(True)
        
        # Context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(parent.show_context_menu)
        
        # Edit triggers
        self.setEditTriggers(
            QTreeWidget.EditTrigger.DoubleClicked
            | QTreeWidget.EditTrigger.EditKeyPressed
        )
        
        # Connect signals
        self.itemChanged.connect(parent.item_changed)
        self.itemSelectionChanged.connect(parent.selection_changed)
        self.dropped.connect(parent.after_tree_drop)

    def startDrag(self, actions):
        # Allow dragging both groups and accounts
        super().startDrag(actions)

    def dropEvent(self, event):
        target = self.itemAt(event.position().toPoint())
        indicator = self.dropIndicatorPosition()
        selected_items = self.selectedItems()
        
        if target is None:
            # Dropping on empty area - move groups to end
            moved_count = 0
            for item in selected_items:
                if item.parent() is None:
                    current_index = self.indexOfTopLevelItem(item)
                    if current_index >= 0:
                        self.takeTopLevelItem(current_index)
                        self.addTopLevelItem(item)
                        moved_count += 1
            
            if moved_count > 0:
                self.dropped.emit()
                event.accept()
                return
            
            event.ignore()
            return
        
        # Dropping accounts onto a group
        if target.parent() is None and indicator == QTreeWidget.DropIndicatorPosition.OnItem:
            group_item = target
            moved_count = 0
            
            for item in selected_items:
                if item.parent() is not None:
                    old_parent = item.parent()
                    old_parent.removeChild(item)
                    group_item.addChild(item)
                    moved_count += 1
            
            if moved_count > 0:
                group_item.setExpanded(True)
                self.dropped.emit()
                event.accept()
                return
        
        # Reordering groups
        if target.parent() is None:
            group_items = [item for item in selected_items if item.parent() is None]
            
            if group_items:
                for item in group_items:
                    current_index = self.indexOfTopLevelItem(item)
                    target_index = self.indexOfTopLevelItem(target)
                    
                    if current_index >= 0 and target_index >= 0 and current_index != target_index:
                        self.takeTopLevelItem(current_index)
                        if current_index < target_index:
                            target_index -= 1
                        self.insertTopLevelItem(target_index, item)
                
                self.dropped.emit()
                event.accept()
                return
        
        super().dropEvent(event)
        if event.isAccepted():
            self.dropped.emit()


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle(f"About {APP_NAME}")
        self.setFixedSize(420, 340)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_path = resource_path("app_icon.png")

        if icon_path.exists():
            icon = QLabel()
            icon.setPixmap(
                QPixmap(str(icon_path)).scaled(
                    96,
                    96,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(icon)

        layout.addSpacing(6)

        name = QLabel(APP_NAME)
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name.setStyleSheet("color: #abd0da; font-size: 28px; font-weight: bold;")
        layout.addWidget(name)

        version = QLabel(f"Version {APP_VERSION}")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)

        description = QLabel("Local Two-Factor Authentication Manager")
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(description)

        copyright_label = QLabel(APP_COPYRIGHT)
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(copyright_label)

        github_url = GITHUB_LINK
        if not github_url.startswith(("http://", "https://")):
            github_url = "https://" + github_url
        
        github_label = QLabel()
        
        github_label.setText(f'<a href="{github_url}" style="text-decoration:none;">{GITHUB_LINK}</a>')
        github_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        github_label.setOpenExternalLinks(True)
        layout.addWidget(github_label)

        layout.addSpacing(14)

        button = QPushButton("OK")
        button.setObjectName("primaryButton")
        button.clicked.connect(self.accept)
        button.setDefault(True)
        button.setMinimumWidth(140)
        layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignHCenter)


class GroupDialog(QDialog):
    def __init__(self, parent=None, default_name="New Group"):
        super().__init__(parent)

        self.setWindowTitle("Create Group")
        self.setMinimumSize(480, 200)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)

        title = QLabel("Create Group")
        title.setStyleSheet("color: #abd0da; font-size: 22px; font-weight: bold;")
        layout.addWidget(title)

        description = QLabel(
            "Enter a name for the new group.\n"
            "Selected accounts will be moved to this group."
        )
        description.setWordWrap(True)
        description.setStyleSheet("font-size: 13px; color: #a8a8a8;")
        layout.addWidget(description)

        form = QFormLayout()
        form.setHorizontalSpacing(20)
        form.setVerticalSpacing(14)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.name_edit = QLineEdit(default_name)
        self.name_edit.setPlaceholderText("e.g. Work Accounts")
        self.name_edit.selectAll()

        form.addRow("Group Name:", self.name_edit)

        layout.addLayout(form)
        layout.addStretch()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )

        buttons.button(QDialogButtonBox.StandardButton.Ok).setObjectName(
            "primaryButton"
        )

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addWidget(buttons)

        self.name_edit.setFocus()

    def group_name(self):
        return self.name_edit.text().strip()
    
class BackupPassphraseDialog(QDialog):
    def __init__(self, parent=None, confirm=False):
        super().__init__(parent)

        self.setWindowTitle("Backup Passphrase")
        self.setMinimumSize(480, 280)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)

        title = QLabel("Backup Passphrase")
        title.setStyleSheet("color: #abd0da; font-size: 22px; font-weight: bold;")
        layout.addWidget(title)

        description = QLabel(
            "Choose a passphrase to protect the backup file.\n"
            "It will be required again to restore the backup."
        )
        description.setWordWrap(True)
        description.setStyleSheet("font-size: 13px; color: #a8a8a8;")
        layout.addWidget(description)

        form = QFormLayout()
        form.setHorizontalSpacing(20)
        form.setVerticalSpacing(14)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.passphrase_edit = QLineEdit()
        self.passphrase_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.passphrase_edit.setPlaceholderText("e.g. correct horse battery staple")

        form.addRow("Passphrase:", self.passphrase_edit)

        self.confirm_edit = None

        if confirm:
            self.confirm_edit = QLineEdit()
            self.confirm_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.confirm_edit.setPlaceholderText("Repeat the passphrase")

            form.addRow("Repeat:", self.confirm_edit)

        layout.addLayout(form)
        layout.addStretch()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )

        buttons.button(QDialogButtonBox.StandardButton.Ok).setObjectName(
            "primaryButton"
        )

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addWidget(buttons)

        self.passphrase_edit.setFocus()

    def passphrase(self):
        return self.passphrase_edit.text()

    def accept(self):
        passphrase = self.passphrase_edit.text()

        if not passphrase:
            QMessageBox.warning(self, APP_NAME, "A passphrase is required.")
            return

        if self.confirm_edit is not None and passphrase != self.confirm_edit.text():
            QMessageBox.warning(self, APP_NAME, "The passphrases do not match.")
            return

        super().accept()


class AccountDialog(QDialog):
    def __init__(self, account=None, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Edit Account" if account else "Add Account")
        self.setMinimumSize(600, 400)

        account = account or {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)

        title = QLabel("Edit Account" if account else "Add Account")
        title.setStyleSheet("color: #abd0da; font-size: 22px; font-weight: bold;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setHorizontalSpacing(20)
        form.setVerticalSpacing(14)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.name_edit = QLineEdit(account.get("name", ""))
        self.name_edit.setPlaceholderText("e.g. Google")
        self.issuer_edit = QLineEdit(account.get("issuer", ""))
        self.issuer_edit.setPlaceholderText("e.g. Google")
        self.username_edit = QLineEdit(account.get("username", ""))
        self.username_edit.setPlaceholderText("e.g. user@example.com")
        self.secret_edit = QLineEdit(account.get("secret", ""))
        self.secret_edit.setPlaceholderText("e.g. JBSWY3DPEHPK3PXP")

        self.algorithm_combo = QComboBox()
        self.algorithm_combo.addItems(["SHA1", "SHA256", "SHA512", "MD5"])

        algorithm = account.get("algorithm", "SHA1")
        algorithm_index = self.algorithm_combo.findText(algorithm)
        self.algorithm_combo.setCurrentIndex(max(algorithm_index, 0))

        self.digits_combo = QComboBox()
        self.digits_combo.addItems(["6", "8"])

        digits_index = self.digits_combo.findText(str(account.get("digits", 6)))
        self.digits_combo.setCurrentIndex(max(digits_index, 0))

        self.period_spin = QSpinBox()
        self.period_spin.setRange(1, 300)
        self.period_spin.setValue(int(account.get("period", 30)))
        self.period_spin.setSuffix(" s")

        self.secret_edit.setEchoMode(QLineEdit.EchoMode.Password)

        form.addRow("Name:", self.name_edit)
        form.addRow("Issuer:", self.issuer_edit)
        form.addRow("Username:", self.username_edit)
        form.addRow("Secret:", self.secret_edit)
        form.addRow("Algorithm:", self.algorithm_combo)
        form.addRow("Digits:", self.digits_combo)
        form.addRow("Period:", self.period_spin)

        layout.addLayout(form)
        layout.addStretch()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )

        buttons.button(QDialogButtonBox.StandardButton.Ok).setObjectName(
            "primaryButton"
        )

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addWidget(buttons)

        self.name_edit.setFocus()
        self.name_edit.selectAll()

    def get_account(self):
        return {
            "name": self.name_edit.text().strip(),
            "issuer": self.issuer_edit.text().strip(),
            "username": self.username_edit.text().strip(),
            "secret": self.secret_edit.text().strip(),
            "algorithm": self.algorithm_combo.currentText(),
            "digits": int(self.digits_combo.currentText()),
            "period": self.period_spin.value(),
        }


class TuFacWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.resize(1000, 650)

        self.storage = TuFacStorage()
        self.data = self.storage.load()

        icon_path = resource_path(get_app_icon_name())

        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.create_menu()
        self.create_central_widget()
        self.create_status_bar()
        self.load_tree()

    def set_group_color(self):
        item = self.tree.currentItem()
        
        if item is None or item.parent() is not None:
            return
        
        current_color = item.data(0, Qt.ItemDataRole.UserRole)
        if current_color:
            color = QColorDialog.getColor(QColor(current_color), self, "Choose Group Color")
        else:
            color = QColorDialog.getColor(QColor(), self, "Choose Group Color")
        
        if not color.isValid():
            return
        
        # Store color in group data
        group_index = self.tree.indexOfTopLevelItem(item)
        if group_index >= 0:
            self.data["groups"][group_index]["color"] = color.name()
            self.save_data()
            self.update_group_display(item, color)

    def remove_group_color(self):
        if not self.tree.selectedItems():
            return
        
        item = self.tree.currentItem()
        
        if item is None or item.parent() is not None:
            return
        
        group_index = self.tree.indexOfTopLevelItem(item)
        if group_index >= 0:
            if "color" in self.data["groups"][group_index]:
                del self.data["groups"][group_index]["color"]
                self.save_data()
                item.setIcon(0, QIcon())
                item.setData(0, Qt.ItemDataRole.UserRole, None)

    def update_group_display(self, item, color):
        if color is None:
            item.setData(0, Qt.ItemDataRole.UserRole, None)
            item.setText(0, item.text(0))
            item.setIcon(0, QIcon())  # Remove icon
        else:
            item.setData(0, Qt.ItemDataRole.UserRole, color.name())
            # Create colored circle as icon
            pixmap = QPixmap(24, 24)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(Qt.GlobalColor.transparent, 0))
            painter.drawEllipse(2, 2, 20, 20)
            painter.end()
            item.setIcon(0, QIcon(pixmap))
            item.setText(0, item.text(0))

    def create_group_from_selected(self):
        selected_items = self.tree.selectedItems()
        selected_accounts = [it for it in selected_items if it.parent() is not None]
        
        if not selected_accounts:
            return
        
        default_name = f"Group {len(self.data['groups']) + 1}"
        
        dialog = GroupDialog(self, default_name)
        
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        
        group_name = dialog.group_name()
        
        if not group_name:
            QMessageBox.warning(self, APP_NAME, "A group name is required.")
            return
        
        # Create new group in data structure
        new_group = {
            "name": group_name,
            "accounts": []
        }
        self.data["groups"].append(new_group)
        group_index = len(self.data["groups"]) - 1
        
        # Create new group in tree
        group_item = self.create_tree_item(group_name)
        self.tree.addTopLevelItem(group_item)
        
        # Move selected accounts to new group
        for account_item in selected_accounts:
            account = account_item.data(0, Qt.ItemDataRole.UserRole)
            if account:
                # Add to new group in data
                self.data["groups"][group_index]["accounts"].append(account)
                
                # Remove from old group in data
                old_group_item = account_item.parent()
                if old_group_item:
                    old_group_index = self.tree.indexOfTopLevelItem(old_group_item)
                    if 0 <= old_group_index < len(self.data["groups"]):
                        old_accounts = self.data["groups"][old_group_index]["accounts"]
                        if account in old_accounts:
                            old_accounts.remove(account)
                
                # Move in tree
                old_parent = account_item.parent()
                if old_parent:
                    old_parent.removeChild(account_item)
                
                group_item.addChild(account_item)
        
        # Save and update UI
        self.save_data()
        group_item.setExpanded(True)
        
        # Clear selection to prevent context menu from reopening
        self.tree.clearSelection()
        self.tree.setCurrentItem(None)
    
        QMessageBox.information(
            self,
            APP_NAME,
            f"Created group '{group_name}' with {len(selected_accounts)} account(s)."
        )

    def delete_multiple_accounts(self):
        selected_items = self.tree.selectedItems()
        selected_accounts = [it for it in selected_items if it.parent() is not None]
        
        if not selected_accounts:
            return
        
        # Confirm deletion
        if not self.confirm(f"Delete {len(selected_accounts)} account(s) from their groups?"):
            return
        
        # Delete each account
        for account_item in selected_accounts:
            group_item = account_item.parent()
            if not group_item:
                continue
            
            group_index = self.tree.indexOfTopLevelItem(group_item)
            if group_index < 0:
                continue
            
            account_index = group_item.indexOfChild(account_item)
            accounts = self.data["groups"][group_index].get("accounts", [])
            
            if 0 <= account_index < len(accounts):
                del accounts[account_index]
                group_item.removeChild(account_item)
        
        self.save_data()
        self.update_status_counts()
        
        # Clear selection to prevent context menu from reopening
        self.tree.clearSelection()
        self.tree.setCurrentItem(None)
    
    def create_central_widget(self):
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.tree = AccountTree(self)
        self.tree.setHeaderHidden(True)
        self.tree.setMinimumWidth(300)
        self.tree.setItemDelegate(AccountTreeDelegate(self.tree))

        self.tree.setDragDropMode(QTreeWidget.DragDropMode.InternalMove)
        self.tree.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.tree.setDropIndicatorShown(True)

        self.tree.setEditTriggers(
            QTreeWidget.EditTrigger.DoubleClicked
            | QTreeWidget.EditTrigger.EditKeyPressed
        )

        self.tree.itemChanged.connect(self.item_changed)
        self.tree.itemSelectionChanged.connect(self.selection_changed)
        self.tree.dropped.connect(self.after_tree_drop)

        splitter.addWidget(self.tree)

        self.account_panel = QWidget()
        self.account_panel.setObjectName("detailPanel")
        self.account_panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        account_layout = QVBoxLayout(self.account_panel)
        account_layout.setContentsMargins(48, 40, 48, 40)
        account_layout.setSpacing(14)

        self.account_title = QLabel("Select an account")
        self.account_title.setWordWrap(True)
        self.account_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.account_title.setStyleSheet(
            "font-size: 26px; font-weight: bold; color: #ffffff;"
        )

        self.account_info = QLabel("Select an account from the tree.")
        self.account_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.account_info.setWordWrap(True)
        self.account_info.setStyleSheet("font-size: 14px; color: #a8a8a8;")

        self.brand_logo = QLabel()
        logo_path = resource_path("logo_512.png")
        if logo_path.exists():
            self.brand_logo.setPixmap(
                QPixmap(str(logo_path)).scaled(
                    180,
                    180,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        self.brand_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.brand_title = QLabel(f"{APP_NAME} {APP_VERSION}")
        self.brand_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.brand_title.setStyleSheet(
            "font-size: 34px; font-weight: bold; color: #ffffff;"
        )

        self.brand_copyright = QLabel(APP_COPYRIGHT)
        self.brand_copyright.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.brand_copyright.setStyleSheet("font-size: 13px; color: #8a8a8a;")

        self.brand_description = QLabel(
            "TuFac manages your TOTP two-factor codes and generates the "
            "one-time passwords directly on this device — encrypted and local."
        )
        self.brand_description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.brand_description.setWordWrap(True)
        self.brand_description.setStyleSheet("font-size: 14px; color: #a8a8a8;")

        self.brand_widget = QWidget()
        brand_layout = QVBoxLayout(self.brand_widget)
        brand_layout.setContentsMargins(48, 40, 48, 40)
        brand_layout.setSpacing(14)
        brand_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_layout.addStretch()
        brand_layout.addWidget(self.brand_title)
        brand_layout.addSpacing(14)
        brand_layout.addWidget(self.brand_logo)
        brand_layout.addSpacing(14)
        brand_layout.addWidget(self.brand_description)
        brand_layout.addSpacing(28)
        brand_layout.addWidget(self.brand_copyright)
        brand_layout.addStretch()

        self.otp_code = QLabel("------")
        self.otp_code.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.otp_code.setStyleSheet(
            "font-size: 44px; font-weight: bold; letter-spacing: 10px; color: #4da6ff;"
        )

        self.otp_remaining = QLabel("")
        self.otp_remaining.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.otp_remaining.setStyleSheet("font-size: 13px; color: #a8a8a8;")

        self.copy_code_button = QPushButton("Copy Code")
        self.copy_code_button.setObjectName("primaryButton")
        self.copy_code_button.setEnabled(False)
        self.copy_code_button.setMinimumWidth(160)
        self.copy_code_button.clicked.connect(self.copy_otp_code)

        account_page = QWidget()
        account_layout = QVBoxLayout(account_page)
        account_layout.setContentsMargins(48, 64, 48, 64)
        account_layout.setSpacing(14)
        account_layout.addWidget(self.account_title)
        account_layout.addWidget(self.account_info)
        account_layout.addSpacing(80)
        account_layout.addWidget(self.otp_code)
        account_layout.addWidget(self.otp_remaining)
        account_layout.addSpacing(8)
        account_layout.addWidget(
            self.copy_code_button, alignment=Qt.AlignmentFlag.AlignCenter
        )
        account_layout.addStretch()

        self.detail_stack = QStackedWidget()
        self.detail_stack.addWidget(self.brand_widget)
        self.detail_stack.addWidget(account_page)

        splitter.addWidget(self.detail_stack)
        splitter.setSizes([320, 680])

        self.set_detail_visible(False)

        self.setCentralWidget(splitter)

        self.otp_timer = QTimer(self)
        self.otp_timer.timeout.connect(self.update_otp)
        self.otp_timer.start(500)

    def create_menu(self):
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")

        import_action = QAction("Import from QR Codes...", self)
        import_action.triggered.connect(self.import_accounts)
        file_menu.addAction(import_action)

        import_backup_action = QAction("Import Backup File...", self)
        import_backup_action.triggered.connect(self.import_backup)
        file_menu.addAction(import_backup_action)

        export_action = QAction("Export Backup...", self)
        export_action.triggered.connect(self.export_accounts)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.setShortcut(QKeySequence.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        groups_menu = menu_bar.addMenu("&Groups")

        add_group_action = QAction("New Group", self)
        add_group_action.setShortcut(QKeySequence("Ctrl+Shift+N"))
        add_group_action.triggered.connect(self.add_group)
        groups_menu.addAction(add_group_action)

        rename_group_action = QAction("Rename Group", self)
        rename_group_action.triggered.connect(self.rename_selected_group)
        groups_menu.addAction(rename_group_action)

        delete_group_action = QAction("Delete Group", self)
        delete_group_action.triggered.connect(self.delete_selected_group)
        groups_menu.addAction(delete_group_action)

        account_menu = menu_bar.addMenu("&Account")

        add_account_action = QAction("Add Account...", self)
        add_account_action.triggered.connect(self.add_account)
        account_menu.addAction(add_account_action)

        edit_account_action = QAction("Edit Account...", self)
        edit_account_action.triggered.connect(self.edit_account)
        account_menu.addAction(edit_account_action)

        delete_account_action = QAction("Delete Account", self)
        delete_account_action.triggered.connect(self.delete_selected_account)
        account_menu.addAction(delete_account_action)

        help_menu = menu_bar.addMenu("&Help")

        about_action = QAction(f"About {APP_NAME}", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def create_tree_item(self, text):
        item = QTreeWidgetItem([text])
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
        return item

    def create_account_tree_item(self, text):
        item = self.create_tree_item(text)
        item.setForeground(0, QColor(TREE_ACCOUNT))
        return item

    def load_tree(self):
        self.tree.blockSignals(True)
        self.tree.clear()
    
        for group in self.data.get("groups", []):
            group_item = self.create_tree_item(group.get("name", "Unnamed Group"))
            
            # Restore color as icon if exists
            if "color" in group:
                color = QColor(group["color"])
                # Create colored circle as icon
                pixmap = QPixmap(24, 24)
                pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pixmap)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setBrush(QBrush(color))
                painter.setPen(QPen(Qt.GlobalColor.transparent, 0))
                painter.drawEllipse(2, 2, 20, 20)
                painter.end()
                group_item.setIcon(0, QIcon(pixmap))
                group_item.setData(0, Qt.ItemDataRole.UserRole, group["color"])
            else:
                group_item.setIcon(0, QIcon())
            
            group_item.setText(0, group.get('name', 'Unnamed Group'))
            self.tree.addTopLevelItem(group_item)
    
            # Sort accounts alphanumerically by name before adding to tree
            accounts = sorted(
                group.get("accounts", []),
                key=lambda a: a.get("name", "").lower()
            )
    
            for account in accounts:
                account_item = self.create_account_tree_item(
                    account.get("name", "Unnamed Account")
                )
                account_item.setData(0, Qt.ItemDataRole.UserRole, account)
                group_item.addChild(account_item)
    
        self.tree.blockSignals(False)

    def save_data(self):
        self.storage.save(self.data)
        self.update_status_counts()

    def add_group(self):
        group = {
            "name": "New Group",
            "accounts": [],
        }

        self.data.setdefault("groups", []).append(group)
        self.save_data()

        item = self.create_tree_item(group["name"])
        self.tree.addTopLevelItem(item)
        self.tree.setCurrentItem(item)

        self.tree.editItem(item, 0)

        # Clear selection to prevent context menu from reopening
        self.tree.clearSelection()
        self.tree.setCurrentItem(None)
    
    def add_account(self):
        
        if not self.tree.selectedItems():
            QMessageBox.information(self, APP_NAME, "Please select a group first.")
            return

        item = self.tree.currentItem()

        if item is None:
            QMessageBox.information(self, APP_NAME, "Please select a group first.")
            return

        if item.parent() is not None:
            item = item.parent()

        group_index = self.tree.indexOfTopLevelItem(item)

        if group_index < 0:
            return

        dialog = AccountDialog(parent=self)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        account = dialog.get_account()

        if not account["name"]:
            QMessageBox.warning(self, APP_NAME, "An account name is required.")
            return

        self.data["groups"][group_index]["accounts"].append(account)

        self.save_data()

        account_item = self.create_account_tree_item(account["name"])
        account_item.setData(0, Qt.ItemDataRole.UserRole, account)

        item.addChild(account_item)
        item.setExpanded(True)
        self.tree.setCurrentItem(account_item)

    def rename_selected_with_close(self, menu):
        menu.close()
        menu.deleteLater()
        QTimer.singleShot(0, self.rename_selected)
    
    def rename_selected(self):
        if not self.tree.selectedItems():
            return

        item = self.tree.currentItem()
        if item is not None:
            self.tree.editItem(item, 0)
    
    def rename_selected_group(self):
        if not self.tree.selectedItems():
            return
        
        item = self.tree.currentItem()
        if item is not None and item.parent() is None:
            self.tree.editItem(item, 0)

    def item_changed(self, item, column):
        if column != 0:
            return

        name = item.text(0).strip()

        if not name:
            return

        if item.parent() is None:
            group_index = self.tree.indexOfTopLevelItem(item)

            if group_index >= 0:
                self.data["groups"][group_index]["name"] = name

        else:
            group_item = item.parent()
            group_index = self.tree.indexOfTopLevelItem(group_item)
            account_index = group_item.indexOfChild(item)

            if group_index < 0:
                return

            accounts = self.data["groups"][group_index].get("accounts", [])

            if 0 <= account_index < len(accounts):
                accounts[account_index]["name"] = name

        self.save_data()

    def delete_selected(self):
        if not self.tree.selectedItems():
            return

        item = self.tree.currentItem()

        if item is None:
            return

        if item.parent() is None:
            self.delete_selected_group()
        else:
            self.delete_selected_account()

    def confirm(self, text):
        box = QMessageBox(self)
        box.setWindowTitle(APP_NAME)
        box.setIconPixmap(question_icon())
        box.setText(text)
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        box.setDefaultButton(QMessageBox.StandardButton.No)
        return box.exec() == QMessageBox.StandardButton.Yes

    def delete_selected_group(self):
        if not self.tree.selectedItems():
            return

        item = self.tree.currentItem()

        if item is None or item.parent() is not None:
            return

        if not self.confirm(f"Delete group '{item.text(0)}'?"):
            return

        index = self.tree.indexOfTopLevelItem(item)

        if index < 0:
            return

        del self.data["groups"][index]
        self.tree.takeTopLevelItem(index)
        self.save_data()
        
        # Clear selection to prevent context menu from reopening
        self.tree.clearSelection()
        self.tree.setCurrentItem(None)

    def delete_selected_account(self):
        if not self.tree.selectedItems():
            return

        item = self.tree.currentItem()

        if item is None or item.parent() is None:
            return

        if not self.confirm(f"Delete account '{item.text(0)}'?"):
            return

        group_item = item.parent()
        group_index = self.tree.indexOfTopLevelItem(group_item)
        account_index = group_item.indexOfChild(item)

        if group_index < 0:
            return

        accounts = self.data["groups"][group_index].get("accounts", [])

        if not 0 <= account_index < len(accounts):
            return

        del accounts[account_index]
        group_item.removeChild(item)
        self.save_data()

        # Clear selection to prevent context menu from reopening
        self.tree.clearSelection()
        self.tree.setCurrentItem(None)

    def show_context_menu(self, position):
        item = self.tree.itemAt(position)
        selected_items = self.tree.selectedItems()
        selected_accounts = [it for it in selected_items if it.parent() is not None]
        
        menu = QMenu(self)

        # No accounts selected - show regular menu
        if not selected_accounts:
            if item is None:
                action = menu.addAction("New Group")
                action.triggered.connect(self.add_group)
            elif item.parent() is None:
                action = menu.addAction("Add Account...")
                action.triggered.connect(self.add_account)
                menu.addSeparator()
                
                action = menu.addAction("Rename")
                action.triggered.connect(lambda: self.rename_selected_with_close(menu))
                
                # Color submenu for groups
                color_menu = menu.addMenu("Color")
                set_color_action = color_menu.addAction("Set Color...")
                set_color_action.triggered.connect(self.set_group_color)
                
                if item.data(0, Qt.ItemDataRole.UserRole) is not None:
                    remove_color_action = color_menu.addAction("Remove Color")
                    remove_color_action.triggered.connect(self.remove_group_color)
                
                menu.addSeparator()
                action = menu.addAction("Delete")
                action.triggered.connect(self.delete_selected_group)
            else:
                action = menu.addAction("Edit Account...")
                action.triggered.connect(self.edit_account)
                
                action = menu.addAction("Rename")
                action.triggered.connect(lambda: self.rename_selected_with_close(menu))
                
                menu.addSeparator()
                action = menu.addAction("Delete")
                action.triggered.connect(self.delete_selected_account)
            
            menu.popup(self.tree.viewport().mapToGlobal(position))
            return
    
        # Accounts selected - show group creation option
        action = menu.addAction(f"Create Group from {len(selected_accounts)} Account(s)")
        action.triggered.connect(self.create_group_from_selected)
        
        menu.addSeparator()
        
        if len(selected_accounts) == 1:
            action = menu.addAction("Edit Account...")
            action.triggered.connect(self.edit_account)
            
            action = menu.addAction("Rename")
            action.triggered.connect(lambda: self.rename_selected_with_close(menu))
            
            menu.addSeparator()
            action = menu.addAction("Delete")
            action.triggered.connect(self.delete_selected_account)
        else:
            action = menu.addAction(f"Delete {len(selected_accounts)} Accounts")
            action.triggered.connect(self.delete_multiple_accounts)
        
        menu.popup(self.tree.viewport().mapToGlobal(position))
        
    def set_detail_visible(self, visible):
        self.account_title.setVisible(visible)
        self.account_info.setVisible(visible)
        self.otp_code.setVisible(visible)
        self.otp_remaining.setVisible(visible)
        self.copy_code_button.setVisible(visible)
        self.detail_stack.setCurrentIndex(1 if visible else 0)

    def selection_changed(self):
        item = self.tree.currentItem()

        if item is None:
            self.set_detail_visible(False)
            return

        if item.parent() is None:
            self.account_title.setText(item.text(0))
            self.set_detail_visible(False)
            return

        group_item = item.parent()
        group_index = self.tree.indexOfTopLevelItem(group_item)
        account_index = group_item.indexOfChild(item)

        account = None

        if group_index >= 0:
            accounts = self.data["groups"][group_index].get("accounts", [])

            if 0 <= account_index < len(accounts):
                account = accounts[account_index]

        if account is None:
            self.account_title.setText(item.text(0))
            self.account_info.setText("TOTP account")
            self.set_detail_visible(True)
            return

        self.account_title.setText(account.get("name", "Unnamed Account"))

        information = "TOTP account"

        if account.get("username"):
            information += f"\nUsername: {account['username']}"

        self.account_info.setText(information)

        self.set_detail_visible(True)

        self.update_otp()

    def edit_account(self):
        if not self.tree.selectedItems():
            return

        item = self.tree.currentItem()

        if item is None or item.parent() is None:
            return

        group_item = item.parent()
        group_index = self.tree.indexOfTopLevelItem(group_item)
        account_index = group_item.indexOfChild(item)

        if group_index < 0:
            return

        accounts = self.data["groups"][group_index].get("accounts", [])

        if not 0 <= account_index < len(accounts):
            return

        dialog = AccountDialog(account=accounts[account_index], parent=self)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        account = dialog.get_account()

        if not account["name"]:
            QMessageBox.warning(self, APP_NAME, "An account name is required.")
            return

        accounts[account_index] = account
        item.setData(0, Qt.ItemDataRole.UserRole, account)
        item.setText(0, account["name"])

        self.save_data()
        self.selection_changed()

        # Clear selection to prevent context menu from reopening
        self.tree.clearSelection()
        self.tree.setCurrentItem(None)

    def import_accounts(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Import Google Authenticator Accounts",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)",
        )

        if not files:
            return

        accounts = []
        batches = {}

        try:
            for filename in files:
                for value in decode_qr_image(filename):
                    if not value.startswith("otpauth-migration://"):
                        continue

                    payload = decode_migration_url(value)

                    batch_id = payload["batch_id"]
                    batches.setdefault(batch_id, {})[payload["batch_index"]] = payload

            for batch in batches.values():
                for index in sorted(batch):
                    accounts.extend(batch[index]["otp_parameters"])

        except Exception as exc:  # noqa: BLE001
            import traceback

            print("\nTuFac import failed:", file=sys.stderr)
            traceback.print_exc()

            message = QMessageBox(self)
            message.setIcon(QMessageBox.Icon.Critical)
            message.setWindowTitle(str(APP_NAME))
            message.setText("Import failed")
            message.setInformativeText(str(exc))
            message.setStandardButtons(QMessageBox.StandardButton.Ok)
            message.exec()

            return

        if not accounts:
            QMessageBox.warning(
                self, APP_NAME, "No Google Authenticator accounts were found."
            )
            return

        group_name = self.unique_group_name("Imported Accounts")

        group = {
            "name": group_name,
            "accounts": [],
        }

        for otp in accounts:
            if otp["type"] != 2:
                continue

            algorithm = {
                1: "SHA1",
                2: "SHA256",
                3: "SHA512",
                4: "MD5",
            }.get(otp["algorithm"], "SHA1")

            digits = {
                1: 6,
                2: 8,
            }.get(otp["digits"], 6)

            name = otp["name"]
            issuer = otp["issuer"]

            username = name

            if issuer and name.startswith(issuer + ":"):
                username = name[len(issuer) + 1 :]

            display_name = (
                f"{issuer}: {username}"
                if issuer and username
                else (issuer or username or "Imported Account")
            )

            group["accounts"].append(
                {
                    "name": display_name,
                    "issuer": issuer,
                    "username": username,
                    "secret": secret_to_base32(otp["secret"]),
                    "algorithm": algorithm,
                    "digits": digits,
                    "period": 30,
                }
            )

        if not group["accounts"]:
            QMessageBox.warning(self, APP_NAME, "No TOTP accounts were found.")
            return

        self.data.setdefault("groups", []).append(group)
        self.save_data()
        self.load_tree()

        group_item = self.tree.topLevelItem(self.tree.topLevelItemCount() - 1)
        group_item.setExpanded(True)
        self.tree.setCurrentItem(group_item)

        QMessageBox.information(
            self, APP_NAME, f"Imported {len(group['accounts'])} account(s)."
        )

    def export_accounts(self):
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Backup",
            "tufac-backup.json",
            "JSON Files (*.json)",
        )

        if not filename:
            return

        dialog = BackupPassphraseDialog(self, confirm=True)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            self.storage.export_backup(self.data, Path(filename), dialog.passphrase())
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, APP_NAME, f"Export failed:\n\n{exc}")
            return

        QMessageBox.information(
            self,
            APP_NAME,
            "Backup exported successfully.\nThe file is protected by the passphrase.",
        )

    def import_backup(self):
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Import Backup File",
            "",
            "JSON Files (*.json)",
        )

        if not filename:
            return

        try:
            with Path(filename).open("r", encoding="utf-8") as file:
                imported = json.load(file)
        except (OSError, json.JSONDecodeError) as exc:
            QMessageBox.critical(self, APP_NAME, f"Import failed:\n\n{exc}")
            return

        if is_envelope(imported):
            dialog = BackupPassphraseDialog(self, confirm=False)

            if dialog.exec() != QDialog.DialogCode.Accepted:
                return

            try:
                imported = decrypt_backup(imported, dialog.passphrase())
            except Exception:  # noqa: BLE001
                QMessageBox.critical(
                    self,
                    APP_NAME,
                    "Import failed:\n\nWrong passphrase or corrupted file.",
                )
                return

        if not isinstance(imported, dict) or not isinstance(
            imported.get("groups"), list
        ):
            QMessageBox.warning(self, APP_NAME, "The file is not a valid TuFac backup.")
            return

        added_groups = 0
        added_accounts = 0

        for group in imported["groups"]:
            if not isinstance(group, dict):
                continue

            group_name = group.get("name", "Unnamed Group")
            accounts = [
                account
                for account in group.get("accounts", [])
                if isinstance(account, dict)
            ]

            existing = next(
                (
                    existing_group
                    for existing_group in self.data.setdefault("groups", [])
                    if existing_group.get("name") == group_name
                ),
                None,
            )

            if existing is None:
                self.data["groups"].append(
                    {"name": group_name, "accounts": list(accounts)}
                )
                added_groups += 1
                added_accounts += len(accounts)
                continue

            existing_accounts = existing.setdefault("accounts", [])
            before = len(existing_accounts)

            for account in accounts:
                if account not in existing_accounts:
                    existing_accounts.append(account)

            added_accounts += len(existing_accounts) - before

        self.save_data()
        self.load_tree()

        QMessageBox.information(
            self,
            APP_NAME,
            f"Imported {added_groups} group(s) with {added_accounts} new account(s).",
        )

    def unique_group_name(self, base_name):
        existing = {group.get("name") for group in self.data.get("groups", [])}

        name = base_name
        counter = 2

        while name in existing:
            name = f"{base_name} {counter}"
            counter += 1

        return name

    def rebuild_data_from_tree(self):
        groups = []
    
        for index in range(self.tree.topLevelItemCount()):
            group_item = self.tree.topLevelItem(index)
    
            accounts = []
    
            for child_index in range(group_item.childCount()):
                account_item = group_item.child(child_index)
                account = account_item.data(0, Qt.ItemDataRole.UserRole)
    
                if account is not None:
                    accounts.append(account)
    
            # Sort accounts alphanumerically by name
            accounts.sort(key=lambda a: a.get("name", "").lower())
    
            groups.append(
                {
                    "name": group_item.text(0).strip() or "Unnamed Group",
                    "accounts": accounts,
                }
            )
    
        self.data["groups"] = groups

    def after_tree_drop(self):
        self.rebuild_data_from_tree()
        
        # Re-sort accounts within each group after drag & drop
        for group_index in range(len(self.data["groups"])):
            accounts = self.data["groups"][group_index].get("accounts", [])
            accounts.sort(key=lambda a: a.get("name", "").lower())
        
        # Refresh the tree to show sorted order
        self.load_tree()
        
        self.save_data()

    def show_about(self):
        dialog = AboutDialog(self)
        dialog.exec()

    def create_status_bar(self):
        self.setStatusBar(QStatusBar(self))
        self.statusBar().setContentsMargins(12, 0, 12, 5)

        self.status_counts = QLabel()
        self.status_counts.setStyleSheet("color: #a8a8a8;")
        self.status_counts.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.statusBar().addWidget(self.status_counts)

        self.status_encrypted = QLabel("Encrypted")
        self.status_encrypted.setStyleSheet("color: #7fd18a;")
        self.status_encrypted.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.statusBar().addPermanentWidget(self.status_encrypted)

        self.update_status_counts()

    def update_status_counts(self):
        groups = self.data.get("groups", [])
        accounts = sum(len(group.get("accounts", [])) for group in groups)

        group_word = "group" if len(groups) == 1 else "groups"
        account_word = "account" if accounts == 1 else "accounts"

        self.status_counts.setText(
            f"{len(groups)} {group_word}  \u00b7  {accounts} {account_word}"
        )

    def update_otp(self):
        item = self.tree.currentItem()

        if item is None or item.parent() is None:
            self.otp_code.setText("------")
            self.otp_remaining.setText("")
            self.copy_code_button.setEnabled(False)
            return

        group_item = item.parent()
        group_index = self.tree.indexOfTopLevelItem(group_item)
        account_index = group_item.indexOfChild(item)

        if group_index < 0:
            return

        accounts = self.data["groups"][group_index].get("accounts", [])

        if not 0 <= account_index < len(accounts):
            return

        account = accounts[account_index]

        try:
            totp = pyotp.TOTP(
                account["secret"],
                digits=int(account.get("digits", 6)),
                interval=int(account.get("period", 30)),
                digest=getattr(hashlib, account.get("algorithm", "SHA1").lower()),
            )

            code = totp.now()

            current_time = time.time()
            remaining = int(totp.interval - (current_time % totp.interval))

            self.otp_code.setText(code)
            self.otp_remaining.setText(f"Valid for {remaining} seconds")
            self.copy_code_button.setEnabled(True)

        except Exception as exc:  # noqa: BLE001
            self.otp_code.setText("ERROR")
            self.otp_remaining.setText(str(exc))
            self.copy_code_button.setEnabled(False)

    def copy_otp_code(self):
        code = self.otp_code.text()

        if code and code != "------" and code != "ERROR":
            QApplication.clipboard().setText(code)
            self.statusBar().showMessage("Code copied to clipboard", 2000)
