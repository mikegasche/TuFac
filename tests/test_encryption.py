import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))
os.environ["TUFAC_KEYRING_FILE"] = "1"

from crypto import (
    decrypt_backup,
    decrypt_with_key,
    encrypt_backup,
    encrypt_with_key,
    generate_key,
    is_envelope,
)
from cryptography.exceptions import InvalidTag
from storage import TuFacStorage


@pytest.fixture(autouse=True)
def isolated_data_dir(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setattr(
            "storage.get_data_dir",
            lambda: Path(tmp),
        )
        yield Path(tmp)


def test_crypto_roundtrip_with_key():
    data = {"groups": [{"name": "A", "accounts": [{"secret": "abc"}]}]}
    key = generate_key()

    envelope = encrypt_with_key(data, key)

    assert is_envelope(envelope)
    assert "secret" not in json.dumps(envelope)

    assert decrypt_with_key(envelope, key) == data


def test_crypto_wrong_key_fails():
    data = {"groups": []}
    envelope = encrypt_with_key(data, generate_key())

    with pytest.raises(InvalidTag):
        decrypt_with_key(envelope, generate_key())


def test_backup_roundtrip_with_passphrase():
    data = {"groups": [{"name": "A", "accounts": []}]}

    envelope = encrypt_backup(data, "s3cr3t")

    assert is_envelope(envelope)
    assert envelope["kdf"] == "scrypt"
    assert "secret" not in json.dumps(envelope)

    assert decrypt_backup(envelope, "s3cr3t") == data

    with pytest.raises(InvalidTag):
        decrypt_backup(envelope, "wrong")


def test_is_envelope_rejects_plain_data():
    assert not is_envelope({"groups": []})
    assert not is_envelope(None)
    assert not is_envelope([1, 2, 3])


def test_storage_saves_encrypted():
    storage = TuFacStorage()

    data = {"groups": [{"name": "A", "accounts": [{"secret": "secret-value"}]}]}
    storage.save(data)

    raw = json.loads(storage.data_file.read_text(encoding="utf-8"))

    assert is_envelope(raw)
    assert "secret-value" not in raw["ciphertext"]
    assert raw["ciphertext"] != "secret-value"


def test_storage_load_roundtrip():
    storage = TuFacStorage()

    data = {
        "groups": [
            {
                "name": "A",
                "accounts": [{"name": "Acc", "secret": "JBSWY3DPEHPK3PXP"}],
            }
        ]
    }

    storage.save(data)

    loaded = TuFacStorage().load()

    assert loaded == data


def test_storage_migrates_plaintext_file():
    storage = TuFacStorage()
    storage.data_dir.mkdir(parents=True, exist_ok=True)

    legacy = {"groups": [{"name": "Old", "accounts": []}]}
    storage.data_file.write_text(json.dumps(legacy), encoding="utf-8")

    loaded = storage.load()

    assert loaded == legacy

    raw = json.loads(storage.data_file.read_text(encoding="utf-8"))
    assert is_envelope(raw)


def test_export_backup_writes_encrypted_file():
    storage = TuFacStorage()

    data = {"groups": [{"name": "A", "accounts": []}]}
    output = Path(tempfile.gettempdir()) / "tufac-test-backup.json"

    try:
        storage.export_backup(data, output, "passphrase")
        envelope = json.loads(output.read_text(encoding="utf-8"))

        assert is_envelope(envelope)
        assert decrypt_backup(envelope, "passphrase") == data
    finally:
        output.unlink(missing_ok=True)


def test_load_returns_empty_on_corrupted_file():
    storage = TuFacStorage()
    storage.data_dir.mkdir(parents=True, exist_ok=True)
    storage.data_file.write_text("{ not valid json", encoding="utf-8")

    assert storage.load() == {"groups": []}
