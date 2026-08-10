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

# File:        storage.py
# Author:      Michael Gasche
# Created:     2026-08
# Product:     TuFac
# Description: Local AES-GCM encrypted JSON persistence for TuFac accounts.


import json
import os
import sys
from pathlib import Path

from crypto import (
    decrypt_with_key,
    encrypt_backup,
    encrypt_with_key,
    generate_key,
    is_envelope,
)
from keychain import KeyStore

APP_NAME = "TuFac"


def get_data_dir():
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME

    if sys.platform == "win32":
        app_data = os.environ.get("APPDATA")

        if app_data:
            return Path(app_data) / APP_NAME

        return Path.home() / "AppData" / "Roaming" / APP_NAME

    xdg_config = os.environ.get("XDG_CONFIG_HOME")

    if xdg_config:
        return Path(xdg_config) / APP_NAME

    return Path.home() / ".config" / APP_NAME


def _write_json(data, path):
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)
        file.write("\n")


class TuFacStorage:
    def __init__(self):
        self.data_dir = get_data_dir()
        self.data_file = self.data_dir / "tufac.json"
        self._key = None
        self._keystore = KeyStore(self.data_dir)

    def _get_key(self):
        if self._key is None:
            key = self._keystore.get()

            if key is None:
                key = generate_key()
                self._keystore.store(key)

            self._key = key

        return self._key

    def load(self):
        if not self.data_file.exists():
            return {"groups": []}

        try:
            with self.data_file.open("r", encoding="utf-8") as file:
                raw = json.load(file)
        except (OSError, json.JSONDecodeError):
            return {"groups": []}

        if is_envelope(raw):
            try:
                data = decrypt_with_key(raw, self._get_key())
            except Exception:  # noqa: BLE001
                print("TuFac: could not decrypt the data file.", file=sys.stderr)
                return {"groups": []}
        else:
            data = raw

            if isinstance(data, dict):
                self.save(data)

        if not isinstance(data, dict):
            return {"groups": []}

        if not isinstance(data.get("groups"), list):
            data["groups"] = []

        return data

    def save(self, data):
        self.data_dir.mkdir(parents=True, exist_ok=True)

        envelope = encrypt_with_key(data, self._get_key())

        temporary_file = self.data_file.with_suffix(".json.tmp")

        _write_json(envelope, temporary_file)

        temporary_file.replace(self.data_file)

    def export_json(self, data, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_json(data, path)

    def export_backup(self, data, path, passphrase):
        path.parent.mkdir(parents=True, exist_ok=True)

        envelope = encrypt_backup(data, passphrase)

        _write_json(envelope, path)
