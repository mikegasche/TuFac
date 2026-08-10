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

# File:        migration.py
# Author:      Michael Gasche
# Created:     2026-08
# Product:     TuFac
# Description: Google Authenticator migration URL decoding and encoding.


import base64
import urllib.parse


def _read_varint(data, pos):
    result = 0
    shift = 0

    while True:
        if pos >= len(data):
            raise ValueError("Unexpected end of protobuf data")

        byte = data[pos]
        pos += 1
        result |= (byte & 0x7F) << shift

        if not byte & 0x80:
            return result, pos

        shift += 7
        if shift > 63:
            raise ValueError("Invalid protobuf varint")


def _write_varint(value):
    result = bytearray()

    while value > 127:
        result.append((value & 0x7F) | 0x80)
        value >>= 7

    result.append(value)
    return bytes(result)


def _field_varint(number, value):
    return _write_varint((number << 3) | 0) + _write_varint(value)


def _field_bytes(number, value):
    return _write_varint((number << 3) | 2) + _write_varint(len(value)) + value


def _read_field(data, pos):
    tag, pos = _read_varint(data, pos)
    return tag >> 3, tag & 7, pos


def _skip_field(data, pos, wire_type):
    if wire_type == 0:
        _, pos = _read_varint(data, pos)
    elif wire_type == 1:
        pos += 8
    elif wire_type == 2:
        length, pos = _read_varint(data, pos)
        pos += length
    elif wire_type == 5:
        pos += 4
    else:
        raise ValueError("Unsupported protobuf wire type")

    if pos > len(data):
        raise ValueError("Invalid protobuf data")

    return pos


def _parse_otp(data):
    otp = {
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
        field, wire, pos = _read_field(data, pos)

        if field in (1, 2, 3) and wire == 2:
            length, pos = _read_varint(data, pos)
            value = data[pos : pos + length]
            pos += length

            if field == 1:
                otp["secret"] = value
            elif field == 2:
                otp["name"] = value.decode("utf-8", errors="replace")
            else:
                otp["issuer"] = value.decode("utf-8", errors="replace")

        elif field in (4, 5, 6, 7) and wire == 0:
            value, pos = _read_varint(data, pos)

            if field == 4:
                otp["algorithm"] = value
            elif field == 5:
                otp["digits"] = value
            elif field == 6:
                otp["type"] = value
            else:
                otp["counter"] = value

        else:
            pos = _skip_field(data, pos, wire)

    return otp


def decode_migration_url(value):
    parsed = urllib.parse.urlparse(value)

    if parsed.scheme != "otpauth-migration":
        raise ValueError("Not a Google Authenticator migration URL")

    query = urllib.parse.parse_qs(parsed.query)

    if "data" not in query:
        raise ValueError("Migration URL contains no data")

    encoded = query["data"][0]
    raw = base64.b64decode(encoded)

    accounts = []
    version = 1
    batch_size = 1
    batch_index = 0
    batch_id = 0

    pos = 0

    while pos < len(raw):
        field, wire, pos = _read_field(raw, pos)

        if field == 1 and wire == 2:
            length, pos = _read_varint(raw, pos)
            accounts.append(_parse_otp(raw[pos : pos + length]))
            pos += length

        elif field in (2, 3, 4, 5) and wire == 0:
            value, pos = _read_varint(raw, pos)

            if field == 2:
                version = value
            elif field == 3:
                batch_size = value
            elif field == 4:
                batch_index = value
            elif field == 5:
                batch_id = value

        else:
            pos = _skip_field(raw, pos, wire)

    return {
        "otp_parameters": accounts,
        "version": version,
        "batch_size": batch_size,
        "batch_index": batch_index,
        "batch_id": batch_id,
    }


def _build_otp(account):
    secret = base64.b32decode(
        account["secret"].upper() + "=" * (-len(account["secret"]) % 8)
    )

    algorithm = {
        "SHA1": 1,
        "SHA256": 2,
        "SHA512": 3,
        "MD5": 4,
    }.get(account.get("algorithm", "SHA1"), 1)

    digits = {
        6: 1,
        8: 2,
    }.get(account.get("digits", 6), 1)

    otp_type = 1 if account.get("type") == "hotp" else 2

    data = bytearray()

    data += _field_bytes(1, secret)
    data += _field_bytes(
        2,
        account.get("username", "").encode("utf-8"),
    )
    data += _field_bytes(
        3,
        account.get("issuer", "").encode("utf-8"),
    )
    data += _field_varint(4, algorithm)
    data += _field_varint(5, digits)
    data += _field_varint(6, otp_type)

    if otp_type == 1:
        data += _field_varint(
            7,
            account.get("counter", 0),
        )

    return bytes(data)


def encode_migration(accounts):
    payload = bytearray()

    for account in accounts:
        otp = _build_otp(account)
        payload += _field_bytes(1, otp)

    payload += _field_varint(2, 1)
    payload += _field_varint(3, 1)
    payload += _field_varint(4, 0)
    payload += _field_varint(5, 1)

    encoded = base64.b64encode(payload).decode("ascii")

    return "otpauth-migration://offline?data=" + urllib.parse.quote(encoded)
