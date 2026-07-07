"""Opt-in import of a browser's existing session cookies (macOS Chrome).

This lets you skip ClipFetch's own sign-in by reusing the Instagram session
already in your real Chrome. It only ever reads your *own* cookies on your
*own* machine, and Chrome's own encryption forces a Keychain consent prompt
before anything can be decrypted.

Kept dependency-free: the key is derived with stdlib :mod:`hashlib`, the
Keychain secret is read via the ``security`` CLI, and AES decryption is done
with the system ``openssl`` — no third-party crypto library.
"""

from __future__ import annotations

import hashlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

from clipfetch.errors import ClipFetchError
from clipfetch.platforms.base import Platform

_CHROME_COOKIES = (
    Path.home() / "Library/Application Support/Google/Chrome/Default/Cookies"
)
_SALT = b"saltysalt"
_IV = b" " * 16
_ITERATIONS = 1003
_KEY_LEN = 16
_SHA256_PREFIX_LEN = 32  # newer Chrome prepends SHA256(domain) to the plaintext


class CookieImportError(ClipFetchError):
    """Importing cookies from the real browser failed."""


def _require_macos() -> None:
    if sys.platform != "darwin":
        raise CookieImportError(
            "Importing browser cookies is currently supported on macOS only."
        )


def _keychain_password() -> bytes:
    """Read Chrome's 'Safe Storage' secret from the login Keychain."""
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-w", "-s", "Chrome Safe Storage"],
            capture_output=True,
            timeout=30,
        )
    except FileNotFoundError:
        raise CookieImportError("The macOS 'security' tool was not found.")
    if result.returncode != 0:
        raise CookieImportError(
            "Could not read Chrome's key from the Keychain (access denied or Chrome "
            "not installed)."
        )
    return result.stdout.strip()


def _derive_key(password: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha1", password, _SALT, _ITERATIONS, _KEY_LEN)


def _strip_pkcs7(data: bytes) -> bytes:
    if not data:
        return data
    pad = data[-1]
    if 1 <= pad <= 16 and data[-pad:] == bytes([pad]) * pad:
        return data[:-pad]
    return data


def _clean_plaintext(plaintext: bytes) -> str:
    """Turn a decrypted cookie blob into its string value.

    Newer Chrome prepends a 32-byte SHA256(domain) hash; drop it when the raw
    value would otherwise contain non-text bytes.
    """
    unpadded = _strip_pkcs7(plaintext)
    for candidate in (unpadded, unpadded[_SHA256_PREFIX_LEN:]):
        try:
            text = candidate.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if text.isprintable():
            return text
    return unpadded.decode("utf-8", "replace")


def decrypt_value(encrypted: bytes, key: bytes) -> str:
    """Decrypt one Chrome ``v10``-prefixed AES-128-CBC cookie value."""
    if not encrypted.startswith(b"v10"):
        # Unencrypted (rare) — stored as plain bytes.
        return encrypted.decode("utf-8", "replace")
    ciphertext = encrypted[3:]
    try:
        result = subprocess.run(
            ["openssl", "enc", "-aes-128-cbc", "-d", "-nopad",
             "-K", key.hex(), "-iv", _IV.hex()],
            input=ciphertext,
            capture_output=True,
            timeout=30,
        )
    except FileNotFoundError:
        raise CookieImportError("The 'openssl' tool was not found.")
    if result.returncode != 0:
        raise CookieImportError("Failed to decrypt a cookie value.")
    return _clean_plaintext(result.stdout)


def _read_encrypted_cookies(host: str) -> dict[str, bytes]:
    """Return ``{name: encrypted_value}`` for ``host`` from Chrome's store."""
    if not _CHROME_COOKIES.exists():
        raise CookieImportError(f"Chrome cookie store not found at {_CHROME_COOKIES}.")
    # Copy first: Chrome keeps the SQLite file locked while running.
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "Cookies"
        shutil.copy2(_CHROME_COOKIES, copy)
        conn = sqlite3.connect(copy)
        try:
            rows = conn.execute(
                "SELECT name, encrypted_value FROM cookies "
                "WHERE host_key LIKE ?",
                (f"%{host}",),
            ).fetchall()
        finally:
            conn.close()
    return {name: value for name, value in rows}


def import_session_cookies(platform: Platform, browser: str = "chrome") -> list[dict]:
    """Decrypt the platform's cookies from the real browser for ``add_cookies``.

    Returns a list of Playwright cookie dicts. Raises :class:`CookieImportError`
    with a clear message on any failure.
    """
    if browser != "chrome":
        raise CookieImportError(f"Unsupported browser: {browser!r} (only 'chrome').")
    _require_macos()

    key = _derive_key(_keychain_password())
    encrypted = _read_encrypted_cookies(platform.host)
    if not encrypted:
        raise CookieImportError(
            f"No {platform.label} cookies found in Chrome — are you signed in there?"
        )

    domain = f".{platform.host}"
    cookies = []
    for name, blob in encrypted.items():
        value = decrypt_value(blob, key)
        if value:
            cookies.append({
                "name": name,
                "value": value,
                "domain": domain,
                "path": "/",
                "secure": True,
            })
    return cookies
