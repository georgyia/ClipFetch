"""Account endpoints: per-platform sign-in status and UI-triggered one-time sign-in.

Loopback, single-user only. The sign-in opens ClipFetch's own browser profile so the user signs in
once; responses carry states and labels, never cookies or paths. See ``accounts_service``.
"""

from typing import Any

from fastapi import APIRouter, Request

from clipfetch.api.errors import ApiException
from clipfetch.services.accounts_service import AccountError, AccountManager, default_manager

router = APIRouter(prefix="/api/v1/accounts", tags=["accounts"])


def _manager(request: Request) -> AccountManager:
    manager = getattr(request.app.state, "accounts", None)
    if manager is None:  # pragma: no cover - create_app installs one
        manager = default_manager()
        request.app.state.accounts = manager
    return manager


@router.get("")
def list_accounts(request: Request) -> dict[str, Any]:
    return _manager(request).status()


@router.post("/{platform}/connect")
def connect_account(platform: str, request: Request) -> dict[str, Any]:
    try:
        return _manager(request).connect(platform)
    except AccountError as err:
        raise ApiException(404, "unknown_platform", str(err)) from err
