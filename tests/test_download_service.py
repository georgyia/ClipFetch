from __future__ import annotations

from dataclasses import dataclass

from clipfetch.services import download_service


@dataclass
class _Clip:
    ident: str


@dataclass
class _Result:
    clip: _Clip
    ok: bool
    size: int
    error: str | None = None
    catalog_error: str | None = None


def _outcome(results, *, accepted, found=None):
    return download_service.summarize(
        results, requested=5, found=found if found is not None else len(results), accepted=accepted
    )


def test_summarize_counts_and_bytes():
    results = [
        _Result(_Clip("a"), ok=True, size=100),
        _Result(_Clip("b"), ok=True, size=250, catalog_error="index busy"),
        _Result(_Clip("c"), ok=False, size=0, error="blocked"),
    ]
    outcome = _outcome(results, accepted=3)
    assert outcome.downloaded_count == 2
    assert outcome.failed_count == 1
    assert outcome.total_bytes == 350
    assert [r.ident for r in outcome.downloaded] == ["a", "b"]
    assert outcome.results[1].catalog_warning == "index busy"


def test_success_has_no_empty_reason():
    outcome = _outcome([_Result(_Clip("a"), ok=True, size=10)], accepted=1)
    assert (
        outcome.empty_reason(
            experimental=False, has_filters=False, platform_label="Instagram", noun="reel"
        )
        is None
    )


def test_no_matches_when_filters_exclude_everything():
    outcome = _outcome([], accepted=0)
    reason = outcome.empty_reason(
        experimental=False, has_filters=True, platform_label="Instagram", noun="reel"
    )
    assert reason is not None
    assert reason.kind == "no_matches"
    assert reason.message is None


def test_blocked_reason_for_experimental_platform():
    outcome = _outcome([_Result(_Clip("a"), ok=False, size=0, error="403")], accepted=1)
    reason = outcome.empty_reason(
        experimental=True, has_filters=False, platform_label="TikTok", noun="video"
    )
    assert reason is not None
    assert reason.kind == "blocked"
    assert "anti-bot" in (reason.message or "")


def test_generic_empty_reason():
    outcome = _outcome([_Result(_Clip("a"), ok=False, size=0, error="timeout")], accepted=1)
    reason = outcome.empty_reason(
        experimental=False, has_filters=False, platform_label="Instagram", noun="reel"
    )
    assert reason is not None
    assert reason.kind == "empty"
    assert "could be downloaded" in (reason.message or "")
