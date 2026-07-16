"""Opt-in import of session cookies from locally installed browsers.

Firefox stores plaintext cookies in SQLite and Safari uses Apple's
``Cookies.binarycookies`` format. Chrome's storage is platform-specific:
macOS and Linux use AES-CBC with a Safe Storage password, while current
Windows releases use a DPAPI-protected AES-GCM key.

Cookie databases and their write-ahead logs are copied before reading because
browsers may keep them locked. Only cookies for the requested platform host are
returned.
"""

from __future__ import annotations

import base64
import configparser
import ctypes
import hashlib
import importlib
import json
import os
import shutil
import sqlite3
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

from clipfetch.errors import ClipFetchError
from clipfetch.platforms.base import Platform

_SALT = b"saltysalt"
_IV = b" " * 16
_KEY_LEN = 16
_SHA256_PREFIX_LEN = 32  # Chrome 24+ prepends SHA256(domain) to plaintext
_SAFARI_EPOCH_OFFSET = 978307200  # 2001-01-01 to Unix epoch


class CookieImportError(ClipFetchError):
    """Importing cookies from the real browser failed."""


def _run(command: list[str], *, input: bytes | None = None) -> bytes:
    try:
        result = subprocess.run(
            command, input=input, capture_output=True, timeout=30,
        )
    except FileNotFoundError:
        raise CookieImportError(f"The {command[0]!r} tool was not found.") from None
    if result.returncode != 0:
        raise CookieImportError(f"{command[0]!r} failed while importing cookies.")
    return result.stdout.strip()


def _derive_key(password: bytes, iterations: int = 1003) -> bytes:
    return hashlib.pbkdf2_hmac("sha1", password, _SALT, iterations, _KEY_LEN)


def _strip_pkcs7(data: bytes) -> bytes:
    if not data:
        return data
    pad = data[-1]
    if 1 <= pad <= 16 and data[-pad:] == bytes([pad]) * pad:
        return data[:-pad]
    return data


def _clean_plaintext(plaintext: bytes) -> str:
    """Turn a decrypted Chrome cookie blob into its string value."""
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
    """Decrypt a Chrome AES-CBC ``v10``/``v11`` cookie value."""
    if not encrypted.startswith((b"v10", b"v11")):
        return encrypted.decode("utf-8", "replace")
    plaintext = _run(
        [
            "openssl", "enc", "-aes-128-cbc", "-d", "-nopad",
            "-K", key.hex(), "-iv", _IV.hex(),
        ],
        input=encrypted[3:],
    )
    return _clean_plaintext(plaintext)


def _copy_sqlite(path: Path) -> Path:
    if not path.exists():
        raise CookieImportError(f"Cookie store not found at {path}.")
    temp_dir = Path(tempfile.mkdtemp(prefix="clipfetch-cookies-"))
    copy = temp_dir / path.name
    try:
        shutil.copy2(path, copy)
        # Firefox and Chrome commonly leave the newest cookies in SQLite's WAL
        # while they are running.  Keep the sidecars beside the copied database
        # so SQLite can recover the complete snapshot when it opens the copy.
        for suffix in ("-wal", "-shm"):
            sidecar = path.with_name(path.name + suffix)
            if sidecar.exists():
                shutil.copy2(sidecar, copy.with_name(copy.name + suffix))
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    return copy


def _first_existing(paths: list[Path], browser: str) -> Path:
    for path in paths:
        if path.exists():
            return path
    locations = ", ".join(str(path) for path in paths)
    raise CookieImportError(f"{browser} cookie store not found (checked {locations}).")


def _cookie(
    name: str,
    value: str,
    domain: str,
    path: str = "/",
    secure: bool = True,
    expires: float | int | None = None,
    http_only: bool = False,
    same_site: str | int | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "name": name,
        "value": value,
        "domain": domain,
        "path": path or "/",
        "secure": secure,
        "httpOnly": http_only,
    }
    if expires and expires > 0:
        result["expires"] = float(expires)
    same_sites = {0: "None", 1: "Lax", 2: "Strict", "none": "None", "lax": "Lax",
                  "strict": "Strict"}
    normalized = same_sites.get(same_site)
    if normalized:
        result["sameSite"] = normalized
    return result


def _host_matches(domain: str, host: str) -> bool:
    return domain.lstrip(".") == host or host.endswith("." + domain.lstrip("."))


def _firefox_profile() -> Path:
    home = Path.home()
    if sys.platform == "darwin":
        root = home / "Library/Application Support/Firefox"
    elif sys.platform == "win32":
        root = Path(os.environ.get("APPDATA", home)) / "Mozilla/Firefox"
    else:
        root = home / ".mozilla/firefox"

    config_path = root / "profiles.ini"
    if config_path.exists():
        config = configparser.ConfigParser()
        config.read(config_path, encoding="utf-8")
        preferred: list[Path] = []
        fallback: list[Path] = []
        for section in config.sections():
            if not section.startswith("Profile"):
                continue
            raw = config.get(section, "Path", fallback="")
            if not raw:
                continue
            path = Path(raw)
            if config.getboolean(section, "IsRelative", fallback=True):
                path = root / path
            (preferred if config.getboolean(section, "Default", fallback=False)
             else fallback).append(path)
        for profile in [*preferred, *fallback]:
            if (profile / "cookies.sqlite").exists():
                return profile

    candidates = sorted(
        (p.parent for p in root.glob("**/cookies.sqlite")),
        key=lambda p: (p / "cookies.sqlite").stat().st_mtime,
        reverse=True,
    )
    if candidates:
        return candidates[0]
    raise CookieImportError(f"Firefox profile not found under {root}.")


def _import_firefox(host: str) -> list[dict[str, Any]]:
    database = _copy_sqlite(_firefox_profile() / "cookies.sqlite")
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(database)
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(moz_cookies)")
        }
        same_site = "sameSite" if "sameSite" in columns else "NULL AS sameSite"
        rows = connection.execute(
            "SELECT name, value, host, path, expiry, isSecure, isHttpOnly, "
            f"{same_site} "
            "FROM moz_cookies WHERE host = ? OR host LIKE ?",
            (host, f"%.{host}"),
        ).fetchall()
    finally:
        if connection is not None:
            connection.close()
        shutil.rmtree(database.parent, ignore_errors=True)
    return [
        _cookie(name, value, domain, path, bool(secure), expiry, bool(http_only), same_site)
        for name, value, domain, path, expiry, secure, http_only, same_site in rows
        if value
    ]


def _chrome_profile_names(root: Path, local_state: Path) -> list[str]:
    """Return Chrome profile directories with the last-used profile first."""
    state: dict[str, Any] = {}
    try:
        state = json.loads(local_state.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        pass

    profile = state.get("profile", {})
    if not isinstance(profile, dict):
        profile = {}
    names = [profile.get("last_used"), "Default"]
    info_cache = profile.get("info_cache", {})
    if isinstance(info_cache, dict):
        names.extend(info_cache)
    names.extend(path.name for path in sorted(root.glob("Profile *")) if path.is_dir())

    result: list[str] = []
    for name in names:
        # Local State is browser-owned input.  Reject separators before using a
        # profile name as a child path.
        if (isinstance(name, str) and name not in ("", ".", "..")
                and "/" not in name and "\\" not in name
                and name not in result):
            result.append(name)
    return result


def _chrome_paths() -> tuple[list[Path], Path | None]:
    home = Path.home()
    if sys.platform == "darwin":
        root = home / "Library/Application Support/Google/Chrome"
    elif sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", home)) / "Google/Chrome/User Data"
    else:
        roots = [home / ".config/google-chrome", home / ".config/chromium"]
        root = next((candidate for candidate in roots if candidate.exists()), roots[0])
    local_state = root / "Local State"
    paths: list[Path] = []
    for name in _chrome_profile_names(root, local_state):
        profile = root / name
        paths.extend((profile / "Network/Cookies", profile / "Cookies"))
    return paths, local_state


def _read_chrome_rows(path: Path, host: str) -> list[tuple[Any, ...]]:
    database = _copy_sqlite(path)
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(database)
        rows = connection.execute(
            "SELECT name, value, encrypted_value, host_key, path, expires_utc, "
            "is_secure, is_httponly, samesite FROM cookies "
            "WHERE host_key = ? OR host_key LIKE ?",
            (host, f"%.{host}"),
        ).fetchall()
        return rows
    finally:
        if connection is not None:
            connection.close()
        shutil.rmtree(database.parent, ignore_errors=True)


def _macos_safe_storage_password() -> bytes:
    return _run(
        ["security", "find-generic-password", "-w", "-s", "Chrome Safe Storage"]
    )


def _linux_safe_storage_password() -> bytes:
    for application in ("chrome", "chromium"):
        try:
            password = _run(["secret-tool", "lookup", "application", application])
        except CookieImportError:
            continue
        if password:
            return password
    # KDE stores the same safe-storage secret in KWallet instead of libsecret.
    # Wallet/folder names are the defaults used by Chrome and Chromium.
    for service, folder in (
        ("Chrome Safe Storage", "Chrome Keys"),
        ("Chromium Safe Storage", "Chromium Keys"),
    ):
        try:
            password = _run([
                "kwallet-query", "-r", service, "-f", folder, "kdewallet",
            ])
        except CookieImportError:
            continue
        if password:
            return password
    # Chrome's documented basic-text fallback when no Secret Service is present.
    return b"peanuts"


class _DataBlob(ctypes.Structure):
    _fields_ = [("size", ctypes.c_ulong), ("data", ctypes.POINTER(ctypes.c_ubyte))]


def _windows_unprotect(data: bytes) -> bytes:
    if sys.platform != "win32":
        raise CookieImportError("DPAPI decryption is only available on Windows.")
    buffer = ctypes.create_string_buffer(data)
    source = _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    destination = _DataBlob()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    if not crypt32.CryptUnprotectData(
        ctypes.byref(source), None, None, None, None, 0, ctypes.byref(destination)
    ):
        raise CookieImportError("Windows DPAPI could not decrypt Chrome's cookie key.")
    try:
        return ctypes.string_at(destination.data, destination.size)
    finally:
        kernel32.LocalFree(destination.data)


def _windows_chrome_key(local_state: Path | None) -> bytes:
    if local_state is None or not local_state.exists():
        raise CookieImportError("Chrome Local State was not found beside the profile.")
    try:
        state = json.loads(local_state.read_text(encoding="utf-8"))
        wrapped = base64.b64decode(state["os_crypt"]["encrypted_key"])
    except (KeyError, ValueError, OSError, json.JSONDecodeError):
        raise CookieImportError("Chrome Local State has no usable encryption key.") from None
    if not wrapped.startswith(b"DPAPI"):
        raise CookieImportError("Chrome's Windows encryption key has an unknown format.")
    return _windows_unprotect(wrapped[5:])


def _aes_gcm_decrypt(blob: bytes, key: bytes) -> str:
    try:
        AESGCM = importlib.import_module(
            "cryptography.hazmat.primitives.ciphers.aead"
        ).AESGCM
    except ImportError:
        raise CookieImportError(
            "Modern Windows Chrome cookies require the optional crypto support; "
            "install it with: pip install 'clipfetch[cookies]'"
        ) from None
    if len(blob) < 3 + 12 + 16:
        raise CookieImportError("Chrome returned a truncated encrypted cookie.")
    try:
        plaintext = AESGCM(key).decrypt(blob[3:15], blob[15:], None)
    except Exception as error:
        raise CookieImportError(
            "Chrome's encrypted cookie could not be decrypted with its profile key."
        ) from error
    return _clean_plaintext(plaintext)


def _chrome_decrypter(local_state: Path | None) -> Callable[[bytes], str]:
    if sys.platform == "darwin":
        key = _derive_key(_macos_safe_storage_password(), 1003)
        return lambda value: decrypt_value(value, key)
    if sys.platform == "win32":
        key = _windows_chrome_key(local_state)

        def decrypt_windows(value: bytes) -> str:
            if value.startswith(b"v20"):
                raise CookieImportError(
                    "This Chrome cookie uses Windows app-bound encryption, which "
                    "cannot be imported outside Chrome; import from Firefox instead."
                )
            if value.startswith((b"v10", b"v11")):
                return _aes_gcm_decrypt(value, key)
            return _windows_unprotect(value).decode("utf-8", "replace")

        return decrypt_windows
    key = _derive_key(_linux_safe_storage_password(), 1)
    return lambda value: decrypt_value(value, key)


def _chrome_expiry(value: int) -> float | None:
    # Chrome timestamps are microseconds since 1601-01-01.
    if value <= 0:
        return None
    return value / 1_000_000 - 11644473600


def _import_chrome(host: str) -> list[dict[str, Any]]:
    paths, local_state = _chrome_paths()
    database = _first_existing(paths, "Chrome")
    rows = _read_chrome_rows(database, host)
    decrypt: Callable[[bytes], str] | None = None
    cookies: list[dict[str, Any]] = []
    for name, plain, encrypted, domain, path, expiry, secure, http_only, same_site in rows:
        value = plain
        if not value and encrypted:
            if decrypt is None:
                decrypt = _chrome_decrypter(local_state)
            value = decrypt(bytes(encrypted))
        if value:
            cookies.append(
                _cookie(name, value, domain, path, bool(secure), _chrome_expiry(expiry),
                        bool(http_only), same_site)
            )
    return cookies


def _safari_string(cookie: bytes, offset: int) -> str:
    if offset < 0 or offset >= len(cookie):
        return ""
    return cookie[offset:].split(b"\0", 1)[0].decode("utf-8", "replace")


def _parse_safari_cookie(cookie: bytes) -> dict[str, Any] | None:
    if len(cookie) < 56:
        return None
    try:
        size, _unknown, flags, _unknown2, domain_at, name_at, path_at, value_at = \
            struct.unpack_from("<8I", cookie, 0)
        expires = struct.unpack_from("<d", cookie, 40)[0] + _SAFARI_EPOCH_OFFSET
    except struct.error:
        return None
    if size > len(cookie):
        return None
    name = _safari_string(cookie, name_at)
    value = _safari_string(cookie, value_at)
    domain = _safari_string(cookie, domain_at)
    if not name or not value or not domain:
        return None
    return _cookie(name, value, domain, _safari_string(cookie, path_at), bool(flags & 1),
                   expires, bool(flags & 4))


def _parse_safari_store(data: bytes, host: str) -> list[dict[str, Any]]:
    if len(data) < 8 or data[:4] != b"cook":
        raise CookieImportError("Safari cookie store has an invalid header.")
    page_count = struct.unpack_from(">I", data, 4)[0]
    sizes_end = 8 + page_count * 4
    if sizes_end > len(data):
        raise CookieImportError("Safari cookie store is truncated.")
    page_sizes = struct.unpack_from(f">{page_count}I", data, 8)
    cursor = sizes_end
    cookies: list[dict[str, Any]] = []
    for page_size in page_sizes:
        page = data[cursor:cursor + page_size]
        cursor += page_size
        if len(page) < 8 or struct.unpack_from("<I", page, 0)[0] != 0x100:
            continue
        count = struct.unpack_from("<I", page, 4)[0]
        if 8 + count * 4 > len(page):
            continue
        for offset in struct.unpack_from(f"<{count}I", page, 8):
            if offset + 4 > len(page):
                continue
            size = struct.unpack_from("<I", page, offset)[0]
            parsed = _parse_safari_cookie(page[offset:offset + size])
            if parsed and _host_matches(parsed["domain"], host):
                cookies.append(parsed)
    return cookies


def _import_safari(host: str) -> list[dict[str, Any]]:
    if sys.platform != "darwin":
        raise CookieImportError("Safari cookie import is available on macOS only.")
    path = Path.home() / "Library/Cookies/Cookies.binarycookies"
    if not path.exists():
        raise CookieImportError(f"Safari cookie store not found at {path}.")
    try:
        return _parse_safari_store(path.read_bytes(), host)
    except PermissionError:
        raise CookieImportError(
            "macOS denied access to Safari cookies; grant Full Disk Access to the terminal."
        ) from None


_IMPORTERS: dict[str, Callable[[str], list[dict[str, Any]]]] = {
    "chrome": _import_chrome,
    "firefox": _import_firefox,
    "safari": _import_safari,
}


def import_session_cookies(platform: Platform, browser: str = "chrome") -> list[dict]:
    """Return the platform's cookies in Playwright ``add_cookies`` format."""
    importer = _IMPORTERS.get(browser)
    if importer is None:
        supported = ", ".join(sorted(_IMPORTERS))
        raise CookieImportError(f"Unsupported browser: {browser!r} (choose {supported}).")
    cookies = importer(platform.host)
    if not cookies:
        raise CookieImportError(
            f"No {platform.label} cookies found in {browser.title()} — are you signed in there?"
        )
    return cookies
