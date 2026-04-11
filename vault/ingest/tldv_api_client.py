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

    try:
        payload = response.json() if response.content else {}
    except ValueError:
        return None

    new_token = payload.get("token") or payload.get("accessToken") or payload.get("access_token")
    if not new_token:
        return None

    os.environ["TLDV_JWT_TOKEN"] = new_token
    return new_token


def _extract_participants_and_speakers(response: requests.Response) -> dict[str, Any]:
    try:
        payload = response.json() if response.content else {}
    except ValueError:
        return _empty_result()

    meeting = payload.get("meeting") or {}

    # ── Participants: watch-page may have participants, or they may be None ──
    # If watch-page doesn't have them, we'll get them via /v1/meetings (see
    # fetch_participants_from_tldv_api below).
    participants = meeting.get("participants") or []

    # ── Speakers: transcript segments are lists of word dicts ──
    # Each segment = [{speaker, word, startTime, endTime}, ...]
    # Speaker label is on the first word of each segment.
    # Try both meeting.video.transcript and top-level video.transcript.
    video = meeting.get("video") or payload.get("video") or {}
    transcript_data = ((video.get("transcript") or {}).get("data") or [])

    seen = set()
    speakers = []
    for entry in transcript_data:
        if isinstance(entry, list) and entry:
            # Real format: list of word dicts, speaker on first word
            speaker = entry[0].get("speaker", "") if isinstance(entry[0], dict) else ""
        elif isinstance(entry, dict):
            speaker = entry.get("speaker", "")
        else:
            speaker = ""
        if isinstance(speaker, str) and speaker.strip() and speaker not in seen:
            seen.add(speaker)
            speakers.append(speaker)

    return {
        "participants": participants,
        "speakers": speakers,
        "token_expired": False,
    }


def _call_meetings_list(token: str) -> requests.Response | None:
    """Call TLDV /v1/meetings endpoint to get participant list."""
    url = f"{TLDV_BASE_URL}/v1/meetings"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        return requests.get(url, headers=headers, timeout=TLDV_TIMEOUT_SECONDS)
    except requests.RequestException:
        return None


def _fetch_participants_from_meetings_list(
    meeting_id: str, token: str
) -> list[dict[str, Any]]:
    """Fetch participants from /v1/meetings (has full participant data).

    The /watch-page endpoint often returns participants=None, so we
    fall back to the meetings list which always has them.
    """
    resp = _call_meetings_list(token)
    if resp is None or not resp.ok:
        return []

    try:
        data = resp.json()
    except ValueError:
        return []

    results = data.get("results") or (data if isinstance(data, list) else [])
    for m in results:
        mid = m.get("id") or m.get("_id")
        if mid == meeting_id:
            raw_parts = m.get("participants") or []
            out = []
            for p in raw_parts:
                if isinstance(p, dict):
                    name = (p.get("name") or "").strip()
                    email = (p.get("email") or "").strip()
                    pid = str(p.get("id") or "")
                    if name or email:
                        out.append({
                            "id": pid,
                            "name": name,
                            "email": email or None,
                        })
            return out
    return []


def fetch_participants_from_tldv_api(meeting_id: str, token: str) -> dict[str, Any]:
    """Fetch participants and speakers via TLDV API.

    Strategy:
    1. Call /watch-page for speakers (from transcript)
    2. If participants empty, call /v1/meetings for full participant list
    3. Merge both sources
    """
    response = _call_watch_page(meeting_id, token)
    if response is None:
        return _empty_result()

    # Handle 401 with token refresh
    if response.status_code == 401:
        refreshed_token = refresh_tldv_token()
        if not refreshed_token:
            return _empty_result(token_expired=True)

        retry_response = _call_watch_page(meeting_id, refreshed_token)
        if retry_response is None:
            return _empty_result()
        if retry_response.status_code != 200:
            return _empty_result()
        result = _extract_participants_and_speakers(retry_response)
    elif response.status_code != 200:
        return _empty_result()
    else:
        result = _extract_participants_and_speakers(response)

    # If watch-page didn't return participants, try /v1/meetings
    if not result["participants"]:
        list_participants = _fetch_participants_from_meetings_list(meeting_id, token)
        result["participants"] = list_participants

    return result
