#!/usr/bin/env python

import json
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QMainWindow,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config import APP_COPYRIGHT, APP_NAME, APP_VERSION
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


class AboutDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle(f"About {APP_NAME}")
        self.setFixedSize(420, 300)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_path = resource_path("app_icon.png")

        if icon_path.exists():
            icon = QLabel()
            icon.setPixmap(
                QIcon(str(icon_path)).pixmap(96, 96)
            )
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(icon)

        name = QLabel(APP_NAME)
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name.setStyleSheet(
            "font-size: 24px; font-weight: bold;"
        )
        layout.addWidget(name)

        version = QLabel(f"Version {APP_VERSION}")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)

        description = QLabel(
            "Local Two-Factor Authentication Manager"
        )
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(description)

        copyright_label = QLabel(APP_COPYRIGHT)
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(copyright_label)

        layout.addSpacing(15)

        button = QPushButton("OK")
        button.clicked.connect(self.accept)
        button.setDefault(True)
        layout.addWidget(button)


class AccountDialog(QDialog):

    def __init__(self, account=None, parent=None):
        super().__init__(parent)

        self.setWindowTitle(
            "Edit Account" if account else "Add Account"
        )
        self.setMinimumSize(560, 340)

        account = account or {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)

        title = QLabel("Account Details")
        title.setStyleSheet(
            "font-size: 20px; font-weight: bold;"
        )
        layout.addWidget(title)

        form_box = QGroupBox("TOTP Account")
        form = QFormLayout(form_box)
        form.setContentsMargins(18, 18, 18, 18)
        form.setHorizontalSpacing(20)
        form.setVerticalSpacing(14)

        self.name_edit = QLineEdit(
            account.get("name", "")
        )
        self.issuer_edit = QLineEdit(
            account.get("issuer", "")
        )
        self.username_edit = QLineEdit(
            account.get("username", "")
        )
        self.secret_edit = QLineEdit(
            account.get("secret", "")
        )

        for edit in (
            self.name_edit,
            self.issuer_edit,
            self.username_edit,
            self.secret_edit,
        ):
            edit.setMinimumHeight(32)

        self.secret_edit.setEchoMode(
            QLineEdit.EchoMode.Password
        )

        form.addRow("Name:", self.name_edit)
        form.addRow("Issuer:", self.issuer_edit)
        form.addRow("Username:", self.username_edit)
        form.addRow("Secret:", self.secret_edit)

        layout.addWidget(form_box)
        layout.addStretch()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addWidget(buttons)

        self.name_edit.setFocus()

    def get_account(self):
        return {
            "name": self.name_edit.text().strip(),
            "issuer": self.issuer_edit.text().strip(),
            "username": self.username_edit.text().strip(),
            "secret": self.secret_edit.text().strip(),
            "algorithm": "SHA1",
            "digits": 6,
            "period": 30,
        }


class TuFacWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(APP_NAME)
        self.resize(1000, 650)

        self.storage = TuFacStorage()
        self.data = self.storage.load()

        icon_path = resource_path(
            get_app_icon_name()
        )

        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.create_menu()
        self.create_central_widget()
        self.create_status_bar()
        self.load_tree()

    def create_central_widget(self):

        splitter = QSplitter(
            Qt.Orientation.Horizontal
        )

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setMinimumWidth(280)

        self.tree.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )

        self.tree.customContextMenuRequested.connect(
            self.show_context_menu
        )

        self.tree.setEditTriggers(
            QTreeWidget.EditTrigger.DoubleClicked
            | QTreeWidget.EditTrigger.EditKeyPressed
        )

        self.tree.itemChanged.connect(
            self.item_changed
        )

        self.tree.itemSelectionChanged.connect(
            self.selection_changed
        )

        splitter.addWidget(self.tree)

        self.account_panel = QWidget()
        account_layout = QVBoxLayout(
            self.account_panel
        )
        account_layout.setContentsMargins(
            28, 28, 28, 28
        )

        self.account_title = QLabel(
            "Select an account"
        )
        self.account_title.setStyleSheet(
            "font-size: 22px; font-weight: bold;"
        )

        self.account_info = QLabel(
            "Select an account from the tree."
        )

        account_layout.addWidget(
            self.account_title
        )
        account_layout.addWidget(
            self.account_info
        )
        account_layout.addStretch()

        splitter.addWidget(self.account_panel)
        splitter.setSizes([280, 720])

        self.setCentralWidget(splitter)

    def create_menu(self):

        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")

        action = QAction(
            "Import Accounts...",
            self
        )
        action.triggered.connect(
            self.import_accounts
        )
        file_menu.addAction(action)

        action = QAction(
            "Export Accounts...",
            self
        )
        action.triggered.connect(
            self.export_accounts
        )
        file_menu.addAction(action)

        file_menu.addSeparator()

        action = QAction("Quit", self)
        action.setShortcut(QKeySequence.Quit)
        action.triggered.connect(self.close)
        file_menu.addAction(action)

        groups_menu = menu_bar.addMenu("&Groups")

        action = QAction("New Group", self)
        action.setShortcut(
            QKeySequence("Ctrl+Shift+N")
        )
        action.triggered.connect(self.add_group)
        groups_menu.addAction(action)

        action = QAction("Rename Group", self)
        action.triggered.connect(
            self.rename_selected_group
        )
        groups_menu.addAction(action)

        action = QAction("Delete Group", self)
        action.triggered.connect(
            self.delete_selected_group
        )
        groups_menu.addAction(action)

        account_menu = menu_bar.addMenu("&Account")

        action = QAction(
            "Add Account...",
            self
        )
        action.triggered.connect(
            self.add_account
        )
        account_menu.addAction(action)

        action = QAction(
            "Edit Account...",
            self
        )
        action.triggered.connect(
            self.edit_account
        )
        account_menu.addAction(action)

        action = QAction(
            "Delete Account",
            self
        )
        action.triggered.connect(
            self.delete_selected_account
        )
        account_menu.addAction(action)

        help_menu = menu_bar.addMenu("&Help")

        action = QAction(
            f"About {APP_NAME}",
            self
        )
        action.triggered.connect(
            self.show_about
        )
        help_menu.addAction(action)

    def create_tree_item(self, text):

        item = QTreeWidgetItem([text])
        item.setFlags(
            item.flags()
            | Qt.ItemFlag.ItemIsEditable
        )
        return item

    def load_tree(self):

        self.tree.blockSignals(True)
        self.tree.clear()

        for group in self.data.get("groups", []):

            group_item = self.create_tree_item(
                group.get(
                    "name",
                    "Unnamed Group"
                )
            )

            self.tree.addTopLevelItem(
                group_item
            )

            for account in group.get(
                "accounts",
                []
            ):

                account_item = self.create_tree_item(
                    account.get(
                        "name",
                        "Unnamed Account"
                    )
                )

                group_item.addChild(
                    account_item
                )

        self.tree.blockSignals(False)

    def save_data(self):
        self.storage.save(self.data)

    def add_group(self):

        group = {
            "name": "New Group",
            "accounts": [],
        }

        self.data["groups"].append(group)
        self.save_data()

        item = self.create_tree_item(
            group["name"]
        )

        self.tree.addTopLevelItem(item)
        self.tree.setCurrentItem(item)

        QTimer.singleShot(
            0,
            lambda: self.tree.editItem(item, 0)
        )

    def add_account(self):

        item = self.tree.currentItem()

        if item is None:
            QMessageBox.information(
                self,
                APP_NAME,
                "Please select a group first."
            )
            return

        if item.parent() is not None:
            item = item.parent()

        group_index = (
            self.tree.indexOfTopLevelItem(item)
        )

        if group_index < 0:
            return

        dialog = AccountDialog(
            parent=self
        )

        if (
            dialog.exec()
            != QDialog.DialogCode.Accepted
        ):
            return

        account = dialog.get_account()

        if not account["name"]:
            QMessageBox.warning(
                self,
                APP_NAME,
                "An account name is required."
            )
            return

        self.data["groups"][group_index][
            "accounts"
        ].append(account)

        self.save_data()

        account_item = self.create_tree_item(
            account["name"]
        )

        item.addChild(account_item)
        item.setExpanded(True)

        self.tree.setCurrentItem(
            account_item
        )

    def rename_selected(self):

        item = self.tree.currentItem()

        if item is not None:
            self.tree.editItem(item, 0)

    def rename_selected_group(self):

        item = self.tree.currentItem()

        if item is None or item.parent() is not None:
            return

        self.tree.editItem(item, 0)

    def item_changed(self, item, column):

        if column != 0:
            return

        name = item.text(0).strip()

        if not name:
            return

        if item.parent() is None:

            group_index = (
                self.tree.indexOfTopLevelItem(item)
            )

            if group_index >= 0:
                self.data["groups"][
                    group_index
                ]["name"] = name

        else:

            group_item = item.parent()

            group_index = (
                self.tree.indexOfTopLevelItem(
                    group_item
                )
            )

            account_index = (
                group_item.indexOfChild(item)
            )

            if group_index < 0:
                return

            accounts = self.data[
                "groups"
            ][group_index].get(
                "accounts",
                []
            )

            if 0 <= account_index < len(accounts):
                accounts[
                    account_index
                ]["name"] = name

        self.save_data()

        self.statusBar().showMessage(
            f"Renamed to: {name}",
            2000
        )

    def delete_selected_group(self):

        item = self.tree.currentItem()

        if item is None or item.parent() is not None:
            return

        result = QMessageBox.question(
            self,
            APP_NAME,
            f"Delete group '{item.text(0)}'?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
        )

        if result != QMessageBox.StandardButton.Yes:
            return

        index = self.tree.indexOfTopLevelItem(
            item
        )

        if index < 0:
            return

        del self.data["groups"][index]

        self.tree.takeTopLevelItem(index)
        self.save_data()

    def delete_selected_account(self):

        item = self.tree.currentItem()

        if item is None or item.parent() is None:
            return

        result = QMessageBox.question(
            self,
            APP_NAME,
            f"Delete account '{item.text(0)}'?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
        )

        if result != QMessageBox.StandardButton.Yes:
            return

        group_item = item.parent()

        group_index = (
            self.tree.indexOfTopLevelItem(
                group_item
            )
        )

        account_index = (
            group_item.indexOfChild(item)
        )

        if group_index < 0:
            return

        accounts = self.data[
            "groups"
        ][group_index].get(
            "accounts",
            []
        )

        if not 0 <= account_index < len(accounts):
            return

        del accounts[account_index]

        group_item.removeChild(item)
        self.save_data()

    def show_context_menu(self, position):

        item = self.tree.itemAt(position)

        menu = QMenu(self)

        if item is None:

            action = menu.addAction(
                "New Group"
            )
            action.triggered.connect(
                self.add_group
            )

        elif item.parent() is None:

            action = menu.addAction(
                "Add Account..."
            )
            action.triggered.connect(
                self.add_account
            )

            menu.addSeparator()

            action = menu.addAction(
                "Rename"
            )
            action.triggered.connect(
                self.rename_selected
            )

            action = menu.addAction(
                "Delete"
            )
            action.triggered.connect(
                self.delete_selected_group
            )

        else:

            action = menu.addAction(
                "Edit Account..."
            )
            action.triggered.connect(
                self.edit_account
            )

            action = menu.addAction(
                "Rename"
            )
            action.triggered.connect(
                self.rename_selected
            )

            menu.addSeparator()

            action = menu.addAction(
                "Delete"
            )
            action.triggered.connect(
                self.delete_selected_account
            )

        menu.exec(
            self.tree.viewport().mapToGlobal(
                position
            )
        )

    def selection_changed(self):

        item = self.tree.currentItem()

        if item is None:
            self.account_title.setText(
                "Select an account"
            )
            self.account_info.setText(
                "Select an account from the tree."
            )
            return

        if item.parent() is None:
            self.account_title.setText(
                item.text(0)
            )
            self.account_info.setText(
                "Group"
            )
            return

        self.account_title.setText(
            item.text(0)
        )

        group_item = item.parent()

        group_index = (
            self.tree.indexOfTopLevelItem(
                group_item
            )
        )

        account_index = (
            group_item.indexOfChild(item)
        )

        account = None

        if group_index >= 0:

            accounts = self.data[
                "groups"
            ][group_index].get(
                "accounts",
                []
            )

            if 0 <= account_index < len(accounts):
                account = accounts[
                    account_index
                ]

        if account is None:
            self.account_info.setText(
                "TOTP account"
            )
            return

        issuer = account.get("issuer", "")
        username = account.get("username", "")

        information = "TOTP account"

        if issuer:
            information += f"\nIssuer: {issuer}"

        if username:
            information += f"\nUsername: {username}"

        self.account_info.setText(
            information
        )

    def edit_account(self):

        item = self.tree.currentItem()

        if item is None or item.parent() is None:
            return

        group_item = item.parent()

        group_index = (
            self.tree.indexOfTopLevelItem(
                group_item
            )
        )

        account_index = (
            group_item.indexOfChild(item)
        )

        if group_index < 0:
            return

        accounts = self.data[
            "groups"
        ][group_index].get(
            "accounts",
            []
        )

        if not 0 <= account_index < len(accounts):
            return

        dialog = AccountDialog(
            account=accounts[account_index],
            parent=self
        )

        if (
            dialog.exec()
            != QDialog.DialogCode.Accepted
        ):
            return

        account = dialog.get_account()

        if not account["name"]:
            QMessageBox.warning(
                self,
                APP_NAME,
                "An account name is required."
            )
            return

        accounts[account_index] = account

        item.setText(
            0,
            account["name"]
        )

        self.save_data()
        self.selection_changed()

    def import_accounts(self):

        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Import TuFac Accounts",
            "",
            "TuFac JSON (*.json);;JSON Files (*.json);;All Files (*)"
        )

        if not filename:
            return

        try:
            with open(
                filename,
                "r",
                encoding="utf-8"
            ) as file:
                imported = json.load(file)

        except (
            OSError,
            json.JSONDecodeError
        ) as exc:
            QMessageBox.critical(
                self,
                APP_NAME,
                f"Could not import accounts:\n\n{exc}"
            )
            return

        if (
            not isinstance(imported, dict)
            or not isinstance(
                imported.get("groups"),
                list
            )
        ):
            QMessageBox.warning(
                self,
                APP_NAME,
                "The selected file is not a valid "
                "TuFac file."
            )
            return

        result = QMessageBox.question(
            self,
            APP_NAME,
            "Import the accounts from this file?\n\n"
            "Existing accounts will be replaced.",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
        )

        if result != QMessageBox.StandardButton.Yes:
            return

        self.data = imported
        self.save_data()
        self.load_tree()

        QMessageBox.information(
            self,
            APP_NAME,
            "Accounts imported successfully."
        )

    def export_accounts(self):

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export TuFac Accounts",
            "tufac.json",
            "TuFac JSON (*.json);;JSON Files (*.json)"
        )

        if not filename:
            return

        try:
            with open(
                filename,
                "w",
                encoding="utf-8"
            ) as file:
                json.dump(
                    self.data,
                    file,
                    indent=2,
                    ensure_ascii=False
                )
                file.write("\n")

        except OSError as exc:
            QMessageBox.critical(
                self,
                APP_NAME,
                f"Could not export accounts:\n\n{exc}"
            )
            return

        QMessageBox.information(
            self,
            APP_NAME,
            "Accounts exported successfully."
        )

    def show_about(self):

        dialog = AboutDialog(self)
        dialog.exec()

    def create_status_bar(self):

        self.setStatusBar(
            QStatusBar(self)
        )

        self.statusBar().showMessage(
            f"{APP_NAME} {APP_VERSION}"
        )
