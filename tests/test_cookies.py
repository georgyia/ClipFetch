import hashlib
import shutil
import sqlite3
import struct
import subprocess

import pytest

from clipfetch.cookies import (
    _clean_plaintext,
    _derive_key,
    _import_firefox,
    _parse_safari_store,
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


def test_firefox_import_reads_default_profile(tmp_path, monkeypatch):
    root = tmp_path / ".mozilla/firefox"
    profile = root / "abc.default-release"
    profile.mkdir(parents=True)
    (root / "profiles.ini").write_text(
        "[Profile0]\nName=default-release\nIsRelative=1\n"
        "Path=abc.default-release\nDefault=1\n",
        encoding="utf-8",
    )
    connection = sqlite3.connect(profile / "cookies.sqlite")
    connection.execute(
        "CREATE TABLE moz_cookies (name, value, host, path, expiry, "
        "isSecure, isHttpOnly, sameSite)"
    )
    connection.executemany(
        "INSERT INTO moz_cookies VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("sessionid", "token", ".instagram.com", "/", 2_000_000_000, 1, 1, 1),
            ("foreign", "skip", ".example.com", "/", 0, 0, 0, 0),
        ],
    )
    connection.commit()
    connection.close()
    monkeypatch.setattr("clipfetch.cookies.Path.home", lambda: tmp_path)
    monkeypatch.setattr("clipfetch.cookies.sys.platform", "linux")

    assert _import_firefox("instagram.com") == [{
        "name": "sessionid",
        "value": "token",
        "domain": ".instagram.com",
        "path": "/",
        "secure": True,
        "httpOnly": True,
        "expires": 2_000_000_000.0,
        "sameSite": "Lax",
    }]


def _safari_store(domain=".instagram.com", name="sessionid", value="token"):
    strings = bytearray()

    def add(text):
        offset = 56 + len(strings)
        strings.extend(text.encode() + b"\0")
        return offset

    domain_at = add(domain)
    name_at = add(name)
    path_at = add("/")
    value_at = add(value)
    cookie = bytearray(56) + strings
    struct.pack_into(
        "<8I", cookie, 0, len(cookie), 0, 5, 0,
        domain_at, name_at, path_at, value_at,
    )
    struct.pack_into("<d", cookie, 40, 1_000_000_000)
    page = bytearray(12) + cookie
    struct.pack_into("<III", page, 0, 0x100, 1, 12)
    return b"cook" + struct.pack(">II", 1, len(page)) + page


def test_safari_binary_cookie_parser_filters_host_and_preserves_flags():
    cookies = _parse_safari_store(_safari_store(), "instagram.com")
    assert len(cookies) == 1
    assert cookies[0]["name"] == "sessionid"
    assert cookies[0]["value"] == "token"
    assert cookies[0]["secure"] is True
    assert cookies[0]["httpOnly"] is True
    assert _parse_safari_store(_safari_store(".example.com"), "instagram.com") == []
