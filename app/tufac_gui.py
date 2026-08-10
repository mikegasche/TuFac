#!/usr/bin/env python

import sys
import time
import base64
import urllib.parse
import pyotp

from pathlib import Path

from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
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


def read_varint(data, pos):
    value = 0
    shift = 0

    while True:
        if pos >= len(data):
            raise ValueError("Unexpected end of protobuf data")

        byte = data[pos]
        pos += 1
        value |= (byte & 0x7F) << shift

        if not byte & 0x80:
            return value, pos

        shift += 7

        if shift > 64:
            raise ValueError("Invalid protobuf varint")


def skip_field(data, pos, wire_type):
    if wire_type == 0:
        _, pos = read_varint(data, pos)
    elif wire_type == 1:
        pos += 8
    elif wire_type == 2:
        length, pos = read_varint(data, pos)
        pos += length
    elif wire_type == 5:
        pos += 4
    else:
        raise ValueError("Unsupported protobuf wire type")

    if pos > len(data):
        raise ValueError("Invalid protobuf data")

    return pos


def parse_otp_parameters(data):
    result = {
        "secret": b"",
        "name": "",
        "issuer": "",
        "algorithm": 1,
        "digits": 1,
        "type": 2,
        "counter": 0,
    }

    pos = 0

    while pos < len(data):
        tag, pos = read_varint(data, pos)
        field = tag >> 3
        wire = tag & 7

        if field in (1, 2, 3) and wire == 2:
            length, pos = read_varint(data, pos)
            value = data[pos:pos + length]
            pos += length

            if field == 1:
                result["secret"] = value
            elif field == 2:
                result["name"] = value.decode("utf-8", errors="replace")
            else:
                result["issuer"] = value.decode("utf-8", errors="replace")

        elif field in (4, 5, 6, 7) and wire == 0:
            value, pos = read_varint(data, pos)

            if field == 4:
                result["algorithm"] = value
            elif field == 5:
                result["digits"] = value
            elif field == 6:
                result["type"] = value
            else:
                result["counter"] = value

        else:
            pos = skip_field(data, pos, wire)

    return result


def parse_migration_payload(data):
    result = {
        "otp_parameters": [],
        "version": 0,
        "batch_size": 0,
        "batch_index": 0,
        "batch_id": 0,
    }

    pos = 0

    while pos < len(data):
        tag, pos = read_varint(data, pos)
        field = tag >> 3
        wire = tag & 7

        if field == 1 and wire == 2:
            length, pos = read_varint(data, pos)
            end = pos + length

            result["otp_parameters"].append(
                parse_otp_parameters(data[pos:end])
            )

            pos = end

        elif field in (2, 3, 4, 5) and wire == 0:
            value, pos = read_varint(data, pos)

            if field == 2:
                result["version"] = value
            elif field == 3:
                result["batch_size"] = value
            elif field == 4:
                result["batch_index"] = value
            else:
                result["batch_id"] = value

        else:
            pos = skip_field(data, pos, wire)

    return result


def decode_migration_url(value):
    parsed = urllib.parse.urlparse(value)

    if parsed.scheme != "otpauth-migration":
        raise ValueError("Not a Google Authenticator migration URL")

    query = urllib.parse.parse_qs(parsed.query)
    encoded = query.get("data", [None])[0]

    if not encoded:
        raise ValueError("Migration URL contains no data")

    return parse_migration_payload(
        base64.b64decode(encoded)
    )


def secret_to_base32(secret):
    return base64.b32encode(secret).decode("ascii").rstrip("=")


def decode_qr_image(filename):
    import cv2
    import zxingcpp

    image = cv2.imread(str(filename))

    if image is None:
        raise ValueError(
            f"Cannot read image:\n{filename}"
        )

    results = zxingcpp.read_barcodes(image)

    values = [
        result.text
        for result in results
        if result.text
    ]

    if not values:
        raise ValueError(
            f"No QR code found in:\n{filename}"
        )

    return values


class AboutDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle(f"About {APP_NAME}")
        self.setFixedSize(420, 300)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_path = resource_path("app_icon.png")

        if icon_path.exists():
            icon = QPushButton()
            icon.setIcon(QIcon(str(icon_path)))
            icon.setIconSize(QSize(96, 96))
            icon.setFlat(True)
            icon.setEnabled(False)
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
        self.setMinimumSize(560, 320)

        account = account or {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)

        title = QLabel(
            "Edit Account" if account else "Add Account"
        )
        title.setStyleSheet(
            "font-size: 20px; font-weight: bold;"
        )
        layout.addWidget(title)

        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(14)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        self.name_edit = QLineEdit(account.get("name", ""))
        self.issuer_edit = QLineEdit(account.get("issuer", ""))
        self.username_edit = QLineEdit(account.get("username", ""))
        self.secret_edit = QLineEdit(account.get("secret", ""))

        for edit in (
            self.name_edit,
            self.issuer_edit,
            self.username_edit,
            self.secret_edit,
        ):
            edit.setMinimumHeight(34)

        self.secret_edit.setEchoMode(
            QLineEdit.EchoMode.Password
        )

        form.addRow("Name:", self.name_edit)
        form.addRow("Issuer:", self.issuer_edit)
        form.addRow("Username:", self.username_edit)
        form.addRow("Secret:", self.secret_edit)

        layout.addLayout(form)
        layout.addStretch()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
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

        icon_path = resource_path(get_app_icon_name())

        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.create_menu()
        self.create_central_widget()
        self.create_status_bar()
        self.load_tree()

    def create_central_widget(self):
        splitter = QSplitter(Qt.Orientation.Horizontal)

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

        self.tree.itemChanged.connect(self.item_changed)
        self.tree.itemSelectionChanged.connect(
            self.selection_changed
        )

        splitter.addWidget(self.tree)

        self.account_panel = QWidget()
        account_layout = QVBoxLayout(self.account_panel)
        account_layout.setContentsMargins(32, 32, 32, 32)
        account_layout.setSpacing(16)

        self.account_title = QLabel("Select an account")
        self.account_title.setStyleSheet(
            "font-size: 24px; font-weight: bold;"
        )

        self.account_info = QLabel(
            "Select an account from the tree."
        )
        self.account_info.setWordWrap(True)

        self.otp_code = QLabel("------")
        self.otp_code.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.otp_code.setStyleSheet(
            "font-size: 42px; font-weight: bold; "
            "letter-spacing: 8px;"
        )

        self.otp_remaining = QLabel("")
        self.otp_remaining.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.copy_code_button = QPushButton("Copy Code")
        self.copy_code_button.setEnabled(False)
        self.copy_code_button.clicked.connect(
            self.copy_otp_code
        )

        account_layout.addWidget(self.account_title)
        account_layout.addWidget(self.account_info)
        account_layout.addSpacing(20)
        account_layout.addWidget(self.otp_code)
        account_layout.addWidget(self.otp_remaining)
        account_layout.addWidget(
            self.copy_code_button,
            alignment=Qt.AlignmentFlag.AlignCenter
        )
        account_layout.addStretch()

        splitter.addWidget(self.account_panel)
        splitter.setSizes([280, 720])

        self.setCentralWidget(splitter)

        self.otp_timer = QTimer(self)
        self.otp_timer.timeout.connect(self.update_otp)
        self.otp_timer.start(500)


    def create_menu(self):
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")

        import_action = QAction(
            "Import Accounts...",
            self
        )
        import_action.triggered.connect(
            self.import_accounts
        )
        file_menu.addAction(import_action)

        export_action = QAction(
            "Export Accounts...",
            self
        )
        export_action.triggered.connect(
            self.export_accounts
        )
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.setShortcut(QKeySequence.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        groups_menu = menu_bar.addMenu("&Groups")

        add_group_action = QAction("New Group", self)
        add_group_action.setShortcut(
            QKeySequence("Ctrl+Shift+N")
        )
        add_group_action.triggered.connect(self.add_group)
        groups_menu.addAction(add_group_action)

        rename_group_action = QAction(
            "Rename Group", self
        )
        rename_group_action.triggered.connect(
            self.rename_selected_group
        )
        groups_menu.addAction(rename_group_action)

        delete_group_action = QAction(
            "Delete Group", self
        )
        delete_group_action.triggered.connect(
            self.delete_selected_group
        )
        groups_menu.addAction(delete_group_action)

        account_menu = menu_bar.addMenu("&Account")

        add_account_action = QAction(
            "Add Account...",
            self
        )
        add_account_action.triggered.connect(
            self.add_account
        )
        account_menu.addAction(add_account_action)

        edit_account_action = QAction(
            "Edit Account...",
            self
        )
        edit_account_action.triggered.connect(
            self.edit_account
        )
        account_menu.addAction(edit_account_action)

        delete_account_action = QAction(
            "Delete Account",
            self
        )
        delete_account_action.triggered.connect(
            self.delete_selected_account
        )
        account_menu.addAction(delete_account_action)

        help_menu = menu_bar.addMenu("&Help")

        about_action = QAction(
            f"About {APP_NAME}",
            self
        )
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def create_tree_item(self, text):
        item = QTreeWidgetItem([text])
        item.setFlags(
            item.flags() | Qt.ItemFlag.ItemIsEditable
        )
        return item

    def load_tree(self):
        self.tree.blockSignals(True)
        self.tree.clear()

        for group in self.data.get("groups", []):
            group_item = self.create_tree_item(
                group.get("name", "Unnamed Group")
            )

            self.tree.addTopLevelItem(group_item)

            for account in group.get("accounts", []):
                account_item = self.create_tree_item(
                    account.get("name", "Unnamed Account")
                )
                group_item.addChild(account_item)

        self.tree.blockSignals(False)

    def save_data(self):
        self.storage.save(self.data)

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

        group_index = self.tree.indexOfTopLevelItem(item)

        if group_index < 0:
            return

        dialog = AccountDialog(parent=self)

        if dialog.exec() != QDialog.DialogCode.Accepted:
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
        self.tree.setCurrentItem(account_item)

    def rename_selected(self):
        item = self.tree.currentItem()

        if item is not None:
            self.tree.editItem(item, 0)

    def rename_selected_group(self):
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

            accounts = self.data["groups"][group_index].get(
                "accounts", []
            )

            if 0 <= account_index < len(accounts):
                accounts[account_index]["name"] = name

        self.save_data()

    def delete_selected(self):
        item = self.tree.currentItem()

        if item is None:
            return

        if item.parent() is None:
            self.delete_selected_group()
        else:
            self.delete_selected_account()

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

        index = self.tree.indexOfTopLevelItem(item)

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
        group_index = self.tree.indexOfTopLevelItem(group_item)
        account_index = group_item.indexOfChild(item)

        if group_index < 0:
            return

        accounts = self.data["groups"][group_index].get(
            "accounts", []
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
            action = menu.addAction("New Group")
            action.triggered.connect(self.add_group)

        elif item.parent() is None:
            action = menu.addAction("Add Account...")
            action.triggered.connect(self.add_account)

            menu.addSeparator()

            action = menu.addAction("Rename")
            action.triggered.connect(self.rename_selected)

            action = menu.addAction("Delete")
            action.triggered.connect(
                self.delete_selected_group
            )

        else:
            action = menu.addAction("Edit Account...")
            action.triggered.connect(self.edit_account)

            action = menu.addAction("Rename")
            action.triggered.connect(self.rename_selected)

            menu.addSeparator()

            action = menu.addAction("Delete")
            action.triggered.connect(
                self.delete_selected_account
            )

        menu.exec(
            self.tree.viewport().mapToGlobal(position)
        )

    def selection_changed(self):
        item = self.tree.currentItem()

        if item is None:
            self.account_title.setText("Select an account")
            self.account_info.setText(
                "Select an account from the tree."
            )
            return

        if item.parent() is None:
            self.account_title.setText(item.text(0))
            self.account_info.setText("Group")
            return

        group_item = item.parent()
        group_index = self.tree.indexOfTopLevelItem(group_item)
        account_index = group_item.indexOfChild(item)

        account = None

        if group_index >= 0:
            accounts = self.data["groups"][group_index].get(
                "accounts", []
            )

            if 0 <= account_index < len(accounts):
                account = accounts[account_index]

        if account is None:
            self.account_title.setText(item.text(0))
            self.account_info.setText("TOTP account")
            return

        # The Google Authenticator title is the account name.
        title = account.get("name") or account.get("issuer") or "Unnamed Account"

        self.account_title.setText(
            account.get("name", "Unnamed Account")
        )

        information = "TOTP account"

        if account.get("username"):
            information += f"\nUsername: {account['username']}"

        self.account_info.setText(information)

        self.update_otp()

    def edit_account(self):
        item = self.tree.currentItem()

        if item is None or item.parent() is None:
            return

        group_item = item.parent()
        group_index = self.tree.indexOfTopLevelItem(group_item)
        account_index = group_item.indexOfChild(item)

        if group_index < 0:
            return

        accounts = self.data["groups"][group_index].get(
            "accounts", []
        )

        if not 0 <= account_index < len(accounts):
            return

        dialog = AccountDialog(
            account=accounts[account_index],
            parent=self
        )

        if dialog.exec() != QDialog.DialogCode.Accepted:
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
        item.setText(0, account["name"])

        self.save_data()
        self.selection_changed()

    def import_accounts(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Import Google Authenticator Accounts",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )

        if not files:
            return

        accounts = []
        batches = {}

        try:
            for filename in files:
                for value in decode_qr_image(filename):
                    if not value.startswith(
                        "otpauth-migration://"
                    ):
                        continue

                    payload = decode_migration_url(value)

                    batch_id = payload["batch_id"]
                    batches.setdefault(batch_id, {})[
                        payload["batch_index"]
                    ] = payload

            for batch in batches.values():
                for index in sorted(batch):
                    accounts.extend(
                        batch[index]["otp_parameters"]
                    )

        except Exception as exc:
            import traceback

            print("\nTuFac import failed:", file=sys.stderr)
            traceback.print_exc()

            message = QMessageBox(self)
            message.setIcon(
                QMessageBox.Icon.Critical
            )
            message.setWindowTitle(str(APP_NAME))
            message.setText("Import failed")
            message.setInformativeText(str(exc))
            message.setStandardButtons(
                QMessageBox.StandardButton.Ok
            )
            message.exec()

            return

        if not accounts:
            QMessageBox.warning(
                self,
                APP_NAME,
                "No Google Authenticator accounts were found."
            )
            return

        group_name = "Imported Accounts"

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
                username = name[len(issuer) + 1:]

            display_name = f"{issuer}: {username}" if issuer and username else (
                issuer or username or "Imported Account"
            )

            group["accounts"].append({
                "name": display_name,
                "issuer": issuer,
                "username": username,
                "secret": secret_to_base32(otp["secret"]),
                "algorithm": algorithm,
                "digits": digits,
                "period": 30,
            })

        if not group["accounts"]:
            QMessageBox.warning(
                self,
                APP_NAME,
                "No TOTP accounts were found."
            )
            return

        self.data.setdefault("groups", []).append(group)
        self.save_data()
        self.load_tree()

        group_item = self.tree.topLevelItem(
            self.tree.topLevelItemCount() - 1
        )
        group_item.setExpanded(True)
        self.tree.setCurrentItem(group_item)

        QMessageBox.information(
            self,
            APP_NAME,
            f"Imported {len(group['accounts'])} account(s)."
        )

    def export_accounts(self):
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Accounts",
            "tufac-export.json",
            "JSON Files (*.json)"
        )

        if not filename:
            return

        try:
            self.storage.export_json(
                self.data,
                Path(filename)
            )
        except AttributeError:
            import json

            Path(filename).write_text(
                json.dumps(
                    self.data,
                    indent=2,
                    ensure_ascii=False
                ),
                encoding="utf-8"
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                APP_NAME,
                f"Export failed:\n\n{exc}"
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
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage(
            f"{APP_NAME} {APP_VERSION}"
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

        accounts = self.data["groups"][group_index].get(
            "accounts", []
        )

        if not 0 <= account_index < len(accounts):
            return

        account = accounts[account_index]

        try:
            totp = pyotp.TOTP(
                account["secret"],
                digits=int(account.get("digits", 6)),
                interval=int(account.get("period", 30)),
                digest=getattr(
                    __import__("hashlib"),
                    account.get("algorithm", "SHA1").lower()
                ),
            )

            code = totp.now()

            current_time = time.time()
            remaining = int(
                totp.interval - (current_time % totp.interval)
            )

            self.otp_code.setText(code)
            self.otp_remaining.setText(
                f"Valid for {remaining} seconds"
            )
            self.copy_code_button.setEnabled(True)

        except Exception as exc:
            self.otp_code.setText("ERROR")
            self.otp_remaining.setText(str(exc))
            self.copy_code_button.setEnabled(False)


    def copy_otp_code(self):
        code = self.otp_code.text()

        if code and code != "------" and code != "ERROR":
            QApplication.clipboard().setText(code)
            self.statusBar().showMessage(
                "Code copied to clipboard",
                2000
            )

def main():
    app = QApplication(sys.argv)

    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)

    icon_path = resource_path(get_app_icon_name())

    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = TuFacWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
