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

# File:        crypto.py
# Author:      Michael Gasche
# Created:     2026-08
# Product:     TuFac
# Description: AES-256-GCM encryption and scrypt key derivation for backups.


import base64
import hashlib
import json
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ENVELOPE_KEY = "tufac_backup"
ENVELOPE_VERSION = 1

NONCE_SIZE = 12
SALT_SIZE = 16

KDF_NAME = "scrypt"
SCRYPT_N = 2**16
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_MAXMEM = 128 * 1024 * 1024


def generate_key():
    return AESGCM.generate_key(bit_length=256)


def derive_key(passphrase, salt):
    return hashlib.scrypt(
        passphrase.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=32,
        maxmem=SCRYPT_MAXMEM,
    )


def _encrypt_bytes(plaintext, key):
    nonce = os.urandom(NONCE_SIZE)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
    return nonce, ciphertext


def _decrypt_bytes(nonce, ciphertext, key):
    return AESGCM(key).decrypt(nonce, ciphertext, None)


def is_envelope(data):
    return isinstance(data, dict) and data.get(ENVELOPE_KEY) is not None


def _build_envelope(data, key, salt):
    plaintext = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
    nonce, ciphertext = _encrypt_bytes(plaintext, key)

    envelope = {
        ENVELOPE_KEY: ENVELOPE_VERSION,
        "kdf": KDF_NAME if salt is not None else None,
        "salt": base64.b64encode(salt).decode("ascii") if salt is not None else None,
        "n": SCRYPT_N,
        "r": SCRYPT_R,
        "p": SCRYPT_P,
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
    }

    return envelope


def encrypt_with_key(data, key):
    return _build_envelope(data, key, salt=None)


def encrypt_backup(data, passphrase):
    salt = os.urandom(SALT_SIZE)
    key = derive_key(passphrase, salt)
    return _build_envelope(data, key, salt)


def _parse_envelope(envelope):
    if not is_envelope(envelope):
        raise ValueError("The file is not an encrypted TuFac backup.")

    if envelope[ENVELOPE_KEY] != ENVELOPE_VERSION:
        raise ValueError("Unsupported backup format version.")

    missing = [
        field for field in ("nonce", "ciphertext") if not isinstance(envelope.get(field), str)
    ]

    if missing:
        raise ValueError("The backup file is corrupted.")

    try:
        nonce = base64.b64decode(envelope["nonce"], validate=True)
        ciphertext = base64.b64decode(envelope["ciphertext"], validate=True)
    except ValueError as exc:
        raise ValueError("The backup file is corrupted.") from exc

    return nonce, ciphertext


def decrypt_with_key(envelope, key):
    nonce, ciphertext = _parse_envelope(envelope)
    plaintext = _decrypt_bytes(nonce, ciphertext, key)
    return json.loads(plaintext.decode("utf-8"))


def decrypt_backup(envelope, passphrase):
    nonce, ciphertext = _parse_envelope(envelope)

    kdf = envelope.get("kdf")

    if kdf != KDF_NAME:
        raise ValueError("Unsupported key derivation function.")

    salt = envelope.get("salt")

    if not isinstance(salt, str):
        raise TypeError("The backup file is corrupted.")

    key = derive_key(passphrase, base64.b64decode(salt, validate=True))

    plaintext = _decrypt_bytes(nonce, ciphertext, key)
    return json.loads(plaintext.decode("utf-8"))
