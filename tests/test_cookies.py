import base64
import hashlib
import shutil
import sqlite3
import struct
import subprocess

import pytest

from clipfetch.cookies import (
    CookieImportError,
    _chrome_decrypter,
    _chrome_paths,
    _clean_plaintext,
    _derive_key,
    _import_chrome,
    _import_firefox,
    _import_safari,
    _linux_safe_storage_password,
    _parse_safari_store,
    _strip_pkcs7,
    _windows_chrome_key,
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


def test_firefox_import_supports_schema_without_same_site(tmp_path, monkeypatch):
    profile = tmp_path / ".mozilla/firefox/legacy.default"
    profile.mkdir(parents=True)
    connection = sqlite3.connect(profile / "cookies.sqlite")
    connection.execute(
        "CREATE TABLE moz_cookies (name, value, host, path, expiry, "
        "isSecure, isHttpOnly)"
    )
    connection.execute(
        "INSERT INTO moz_cookies VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("sessionid", "legacy", ".instagram.com", "/", 0, 1, 0),
    )
    connection.commit()
    connection.close()
    monkeypatch.setattr("clipfetch.cookies.Path.home", lambda: tmp_path)
    monkeypatch.setattr("clipfetch.cookies.sys.platform", "linux")

    cookies = _import_firefox("instagram.com")

    assert cookies[0]["value"] == "legacy"
    assert "sameSite" not in cookies[0]


def test_firefox_import_includes_uncheckpointed_wal_cookies(tmp_path, monkeypatch):
    profile = tmp_path / ".mozilla/firefox/wal.default"
    profile.mkdir(parents=True)
    connection = sqlite3.connect(profile / "cookies.sqlite")
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA wal_autocheckpoint=0")
    connection.execute(
        "CREATE TABLE moz_cookies (name, value, host, path, expiry, "
        "isSecure, isHttpOnly, sameSite)"
    )
    connection.commit()
    connection.execute(
        "INSERT INTO moz_cookies VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("sessionid", "from-wal", ".instagram.com", "/", 0, 1, 1, 1),
    )
    connection.commit()
    monkeypatch.setattr("clipfetch.cookies.Path.home", lambda: tmp_path)
    monkeypatch.setattr("clipfetch.cookies.sys.platform", "linux")

    try:
        assert _import_firefox("instagram.com")[0]["value"] == "from-wal"
    finally:
        connection.close()


def test_chrome_paths_prefer_last_used_profile(tmp_path, monkeypatch):
    root = tmp_path / ".config/google-chrome"
    (root / "Default").mkdir(parents=True)
    (root / "Profile 2").mkdir()
    (root / "Local State").write_text(
        '{"profile":{"last_used":"Profile 2","info_cache":'
        '{"Default":{},"Profile 2":{}}}}',
        encoding="utf-8",
    )
    monkeypatch.setattr("clipfetch.cookies.Path.home", lambda: tmp_path)
    monkeypatch.setattr("clipfetch.cookies.sys.platform", "linux")

    paths, local_state = _chrome_paths()

    assert paths[0] == root / "Profile 2/Network/Cookies"
    assert paths[2] == root / "Default/Network/Cookies"
    assert local_state == root / "Local State"


def test_chrome_plaintext_cookie_does_not_load_encryption_key(tmp_path, monkeypatch):
    database = tmp_path / "Cookies"
    database.touch()
    monkeypatch.setattr(
        "clipfetch.cookies._chrome_paths", lambda: ([database], None),
    )
    monkeypatch.setattr(
        "clipfetch.cookies._read_chrome_rows",
        lambda path, host: [
            ("sessionid", "plain", b"", ".instagram.com", "/", 0, 1, 1, 1),
        ],
    )

    def unexpected_decrypter(local_state):
        raise AssertionError("plaintext cookies do not need an encryption key")

    monkeypatch.setattr("clipfetch.cookies._chrome_decrypter", unexpected_decrypter)

    assert _import_chrome("instagram.com")[0]["value"] == "plain"


def test_linux_safe_storage_falls_back_to_kwallet(monkeypatch):
    commands = []

    def fake_run(command, *, input=None):
        commands.append(command)
        if command[0] == "secret-tool":
            raise CookieImportError("no Secret Service")
        return b"wallet-password"

    monkeypatch.setattr("clipfetch.cookies._run", fake_run)

    assert _linux_safe_storage_password() == b"wallet-password"
    assert commands[-1] == [
        "kwallet-query", "-r", "Chrome Safe Storage",
        "-f", "Chrome Keys", "kdewallet",
    ]


def test_windows_app_bound_cookie_has_actionable_error(monkeypatch):
    monkeypatch.setattr("clipfetch.cookies.sys.platform", "win32")
    monkeypatch.setattr("clipfetch.cookies._windows_chrome_key", lambda state: b"key")
    decrypt = _chrome_decrypter(None)

    with pytest.raises(CookieImportError, match="app-bound.*Firefox"):
        decrypt(b"v20" + b"encrypted")


def test_windows_chrome_key_unwraps_local_state(tmp_path, monkeypatch):
    local_state = tmp_path / "Local State"
    wrapped = b"wrapped-key"
    local_state.write_text(
        '{"os_crypt":{"encrypted_key":"'
        + base64.b64encode(b"DPAPI" + wrapped).decode()
        + '"}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "clipfetch.cookies._windows_unprotect",
        lambda value: b"profile-key" if value == wrapped else b"unexpected",
    )

    assert _windows_chrome_key(local_state) == b"profile-key"


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


def test_safari_import_reads_macos_cookie_store(tmp_path, monkeypatch):
    cookie_store = tmp_path / "Library/Cookies/Cookies.binarycookies"
    cookie_store.parent.mkdir(parents=True)
    cookie_store.write_bytes(_safari_store())
    monkeypatch.setattr("clipfetch.cookies.Path.home", lambda: tmp_path)
    monkeypatch.setattr("clipfetch.cookies.sys.platform", "darwin")

    assert _import_safari("instagram.com")[0]["value"] == "token"
