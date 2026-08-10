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

# File:        keychain.py
# Author:      Michael Gasche
# Created:     2026-08
# Product:     TuFac
# Description: Storage key handling: macOS Keychain, Windows DPAPI, file fallback.


import base64
import ctypes
import os
import subprocess
import sys
from ctypes import wintypes

KEYCHAIN_SERVICE = "TuFac"
KEYCHAIN_ACCOUNT = "storage-key"
KEY_FILE_NAME = "tufac.key"

DPAPI_UI_FORBIDDEN = 0x1


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def _dpapi(data, protect):
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    crypt32.CryptProtectData.restype = wintypes.BOOL
    crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(_DataBlob),
        wintypes.LPCWSTR,
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]

    crypt32.CryptUnprotectData.restype = wintypes.BOOL
    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(_DataBlob),
        ctypes.POINTER(wintypes.LPWSTR),
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]

    kernel32.LocalFree.argtypes = [wintypes.HLOCAL]

    source = ctypes.cast(data, ctypes.POINTER(ctypes.c_ubyte))
    blob_in = _DataBlob(len(data), source)
    blob_out = _DataBlob()

    function = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData

    if not function(
        ctypes.byref(blob_in),
        None,
        None,
        None,
        None,
        DPAPI_UI_FORBIDDEN,
        ctypes.byref(blob_out),
    ):
        raise OSError("DPAPI operation failed.")

    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        kernel32.LocalFree(blob_out.pbData)


def _use_macos_keychain():
    return sys.platform == "darwin" and os.environ.get("TUFAC_KEYRING_FILE") != "1"


def _use_windows_dpapi():
    return sys.platform == "win32" and os.environ.get("TUFAC_KEYRING_FILE") != "1"


def _run_security(arguments):
    result = subprocess.run(
        ["security", *arguments],
        capture_output=True,
        text=True,
        check=False,
    )
    return result


class KeyStore:
    def __init__(self, data_dir):
        self.data_dir = data_dir

    def get(self):
        if _use_macos_keychain():
            return self._get_macos_keychain()

        if _use_windows_dpapi():
            return self._get_dpapi_key()

        return self._get_file_key()

    def store(self, key):
        if _use_macos_keychain():
            self._store_macos_keychain(key)
            return

        if _use_windows_dpapi():
            self._store_dpapi_key(key)
            return

        self._store_file_key(base64.b64encode(key).decode("ascii"))

    def _get_macos_keychain(self):
        result = _run_security(
            [
                "find-generic-password",
                "-s",
                KEYCHAIN_SERVICE,
                "-a",
                KEYCHAIN_ACCOUNT,
                "-w",
            ]
        )

        if result.returncode != 0:
            return None

        value = result.stdout.strip()

        if not value:
            return None

        try:
            return base64.b64decode(value)
        except ValueError:
            return None

    def _store_macos_keychain(self, key):
        value = base64.b64encode(key).decode("ascii")

        _run_security(
            [
                "add-generic-password",
                "-U",
                "-s",
                KEYCHAIN_SERVICE,
                "-a",
                KEYCHAIN_ACCOUNT,
                "-w",
                value,
            ]
        )

    def _key_file(self):
        return self.data_dir / KEY_FILE_NAME

    def _get_file_key(self):
        key_file = self._key_file()

        if not key_file.exists():
            return None

        try:
            value = base64.b64decode(key_file.read_text(encoding="ascii").strip())
        except (OSError, ValueError):
            return None

        if _use_windows_dpapi():
            try:
                return _dpapi(value, protect=False)
            except (OSError, ctypes.ArgumentError):
                return None

        return value

    def _store_file_key(self, value):
        self.data_dir.mkdir(parents=True, exist_ok=True)

        key_file = self._key_file()

        temporary_file = key_file.with_suffix(".key.tmp")
        temporary_file.write_text(value, encoding="ascii")
        os.chmod(temporary_file, 0o600)
        temporary_file.replace(key_file)

    def _get_dpapi_key(self):
        return self._get_file_key()

    def _store_dpapi_key(self, key):
        protected = _dpapi(key, protect=True)
        self._store_file_key(base64.b64encode(protected).decode("ascii"))
