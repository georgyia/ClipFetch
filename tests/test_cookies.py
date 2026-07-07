import hashlib
import shutil
import subprocess

import pytest

from clipfetch.cookies import (
    _clean_plaintext,
    _derive_key,
    _strip_pkcs7,
    decrypt_value,
)

_IV = b" " * 16
openssl = pytest.mark.skipif(shutil.which("openssl") is None, reason="needs openssl")


def _encrypt(plaintext: bytes, key: bytes) -> bytes:
    """Encrypt like Chrome does (AES-128-CBC, PKCS7), returning a v10 blob."""
    out = subprocess.run(
        ["openssl", "enc", "-aes-128-cbc", "-K", key.hex(), "-iv", _IV.hex()],
        input=plaintext, capture_output=True, check=True,
    ).stdout
    return b"v10" + out


def test_derive_key_is_deterministic_16_bytes():
    key = _derive_key(b"secret")
    assert key == hashlib.pbkdf2_hmac("sha1", b"secret", b"saltysalt", 1003, 16)
    assert len(key) == 16


def test_strip_pkcs7():
    assert _strip_pkcs7(b"abc" + bytes([3, 3, 3])) == b"abc"
    assert _strip_pkcs7(b"data" + bytes([1])) == b"data"
    assert _strip_pkcs7(b"nopadding") == b"nopadding"  # invalid pad left as-is


def test_clean_plaintext_strips_domain_hash_prefix():
    value = "sessionid-value-123"
    prefixed = b"\x00" * 32 + value.encode()  # non-text 32-byte prefix
    assert _clean_plaintext(prefixed) == value
    assert _clean_plaintext(value.encode()) == value  # no prefix case


@openssl
def test_decrypt_value_roundtrip_plain():
    key = _derive_key(b"pw")
    blob = _encrypt(b"12345%3Aabcdef", key)
    assert decrypt_value(blob, key) == "12345%3Aabcdef"


@openssl
def test_decrypt_value_roundtrip_with_domain_prefix():
    key = _derive_key(b"pw")
    value = b"73%3Asession%3Atoken"
    blob = _encrypt(b"\x11" * 32 + value, key)  # simulate newer-Chrome prefix
    assert decrypt_value(blob, key) == value.decode()


def test_decrypt_value_passthrough_when_unencrypted():
    assert decrypt_value(b"plaincookie", _derive_key(b"pw")) == "plaincookie"
