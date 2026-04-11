import os
from typing import Any

import requests


TLDV_BASE_URL = "https://gw.tldv.io"
TLDV_TIMEOUT_SECONDS = 30


def _empty_result(*, token_expired: bool = False) -> dict[str, Any]:
    return {
        "participants": [],
        "speakers": [],
        "token_expired": token_expired,
    }


def _call_watch_page(meeting_id: str, token: str) -> requests.Response | None:
    """Call TLDV watch-page endpoint and swallow connection/request errors."""
    url = f"{TLDV_BASE_URL}/v1/meetings/{meeting_id}/watch-page"
    headers = {
        "Authorization": f"Bearer {token}",
    }
    try:
        return requests.get(url, headers=headers, timeout=TLDV_TIMEOUT_SECONDS)
    except requests.RequestException:
        return None


def refresh_tldv_token() -> str | None:
    refresh_token = os.getenv("TLDV_REFRESH_TOKEN")
    if not refresh_token:
        return None

    try:
        response = requests.post(
            f"{TLDV_BASE_URL}/auth/refresh",
            json={"refreshToken": refresh_token},
            timeout=TLDV_TIMEOUT_SECONDS,
        )
    except requests.RequestException:
        return None

    if response.status_code != 200:
        return None

    payload = response.json() if response.content else {}
    new_token = payload.get("token") or payload.get("accessToken") or payload.get("access_token")
    if not new_token:
        return None

    os.environ["TLDV_JWT_TOKEN"] = new_token
    return new_token


def _extract_participants_and_speakers(response: requests.Response) -> dict[str, Any]:
    payload = response.json() if response.content else {}
    meeting = payload.get("meeting") or {}

    participants = meeting.get("participants") or []

    transcript_data = (
        ((meeting.get("video") or {}).get("transcript") or {}).get("data") or []
    )

    seen = set()
    speakers = []
    for entry in transcript_data:
        speaker = entry.get("speaker") if isinstance(entry, dict) else None
        if not speaker:
            continue
        if speaker in seen:
            continue
        seen.add(speaker)
        speakers.append(speaker)

    return {
        "participants": participants,
        "speakers": speakers,
        "token_expired": False,
    }


def fetch_participants_from_tldv_api(meeting_id: str, token: str) -> dict[str, Any]:
    response = _call_watch_page(meeting_id, token)
    if response is None:
        return _empty_result()

    if response.status_code == 401:
        refreshed_token = refresh_tldv_token()
        if not refreshed_token:
            return _empty_result(token_expired=True)

        retry_response = _call_watch_page(meeting_id, refreshed_token)
        if retry_response is None:
            return _empty_result()
        if retry_response.status_code != 200:
            return _empty_result()
        return _extract_participants_and_speakers(retry_response)

    if response.status_code != 200:
        return _empty_result()

    return _extract_participants_and_speakers(response)
