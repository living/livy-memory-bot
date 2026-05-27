#!/usr/bin/env python3
"""
azure_transcript_search.py — Search full meeting transcripts stored in Azure Blob.

Provides:
- search_transcripts(query, limit) — search across all meeting transcripts in blob
- get_transcript(meeting_id) — fetch full transcript for one meeting
- extract_speakers(meeting_id) — extract participant list from transcript

Uses the Azure storage credentials from environment.
"""
from __future__ import annotations

import json
import os
import re
from typing import Optional

from azure.storage.blob import BlobServiceClient

# ─── Azure Blob client ────────────────────────────────────────────────────────

def _get_blob_client() -> BlobServiceClient:
    conn_str = (
        f"DefaultEndpointsProtocol=https;"
        f"AccountName={os.environ['AZURE_STORAGE_ACCOUNT_NAME']};"
        f"AccountKey={os.environ['AZURE_STORAGE_ACCOUNT_KEY']};"
        f"EndpointSuffix=core.windows.net"
    )
    return BlobServiceClient.from_connection_string(conn_str)


def _blob_container() -> str:
    return os.environ.get("AZURE_STORAGE_CONTAINER_NAME", "living-meeting-hub")


# ─── Transcript fetching ───────────────────────────────────────────────────────

def get_transcript(meeting_id: str) -> Optional[list[dict]]:
    """Fetch full transcript from Azure Blob. Returns list of segments or None."""
    client = _get_blob_client()
    container = client.get_container_client(_blob_container())

    # Try tldv format first (has speaker labels)
    for suffix in (".transcript.tldv.json", ".transcript.json"):
        blob_name = f"meetings/{meeting_id}{suffix}"
        blob = container.get_blob_client(blob_name)
        try:
            data = blob.download_blob().readall()
            transcript = json.loads(data)
            if isinstance(transcript, list) and len(transcript) > 0:
                return transcript
        except Exception:
            pass
    return None


def extract_speakers(meeting_id: str) -> list[dict]:
    """Extract participants with segment counts from a meeting transcript."""
    transcript = get_transcript(meeting_id)
    if not transcript:
        return []

    speakers: dict[str, dict] = {}
    for seg in transcript:
        s = seg.get("speaker", "Unknown")
        text = seg.get("text", "")
        start_ms = seg.get("start_ms", 0)
        if s not in speakers:
            speakers[s] = {"name": s, "segments": 0, "words": 0, "first_appearance_ms": start_ms}
        speakers[s]["segments"] += 1
        speakers[s]["words"] += len(text.split())
        if start_ms < speakers[s]["first_appearance_ms"]:
            speakers[s]["first_appearance_ms"] = start_ms

    return list(speakers.values())


def format_transcript_full(transcript: list[dict], query: str | None = None,
                           limit_chars: int = 3000) -> str:
    """Format full transcript as readable text with speaker labels."""
    lines = []
    char_count = 0

    for seg in transcript:
        speaker = seg.get("speaker", "Unknown")
        text = seg.get("text", "")
        start_ms = seg.get("start_ms", 0)
        h, rem = divmod(start_ms // 1000, 3600)
        m, s = divmod(rem, 60)
        ts = f"[{h:02d}:{m:02d}:{s:02d}]"

        line = f"{ts} {speaker}: {text}"
        if query:
            # Highlight query matches
            line_hl = re.sub(
                f"(?i)({re.escape(query)})",
                r"**\1**",
                line
            )
            lines.append(line_hl)
        else:
            lines.append(line)

        char_count += len(line) + 1
        if limit_chars and char_count > limit_chars:
            lines.append(f"\n... (truncated at {limit_chars} chars)")
            break

    return "\n".join(lines)


# ─── Cross-source search ─────────────────────────────────────────────────────

def search_transcripts(query: str, limit: int = 5,
                       limit_chars: int = 2000) -> list[dict]:
    """
    Search across all meeting transcripts in Azure Blob.

    Returns list of dicts with:
      - meeting_id, date (from blob metadata), speakers, matched_segments,
        transcript_preview, full_transcript_url
    """
    client = _get_blob_client()
    container = client.get_container_client(_blob_container())

    query_lower = query.lower()
    results = []

    # List all transcript blobs
    try:
        blobs = list(container.list_blobs(
            name_starts_with="meetings/",
            include=["metadata"]
        ))
    except Exception as e:
        return [{"error": str(e)}]

    # Filter to TLDV transcripts only (have speaker labels)
    tldv_blobs = [
        b for b in blobs
        if ".transcript.tldv.json" in b.name
    ]

    for blob in tldv_blobs:
        # Extract meeting_id from blob name: meetings/{id}.transcript.tldv.json
        name = blob.name
        match = re.search(r"meetings/([a-zA-Z0-9]+)\.transcript\.tldv\.json", name)
        if not match:
            continue
        meeting_id = match.group(1)

        # Load transcript
        blob_client = container.get_blob_client(name)
        try:
            data = blob_client.download_blob().readall()
            transcript = json.loads(data)
        except Exception:
            continue

        if not isinstance(transcript, list):
            continue

        # Search in transcript
        matched_segs = []
        for seg in transcript:
            text = seg.get("text", "")
            speaker = seg.get("speaker", "")
            if query_lower in text.lower() or query_lower in speaker.lower():
                matched_segs.append(seg)

        if not matched_segs:
            continue

        # Extract speakers
        speakers = list(set(seg.get("speaker", "Unknown") for seg in matched_segs))

        # Build preview (first match with context)
        first_match = matched_segs[0]
        start_ms = first_match.get("start_ms", 0)
        h, rem = divmod(start_ms // 1000, 3600)
        m, s = divmod(rem, 60)
        ts = f"[{h:02d}:{m:02d}:{s:02d}]"
        preview = f"{ts} {first_match.get('speaker','Unknown')}: {first_match.get('text','')[:200]}"

        # Date from last_modified
        date_str = blob.last_modified.strftime("%Y-%m-%d") if blob.last_modified else "unknown"

        results.append({
            "meeting_id": meeting_id,
            "blob_name": name,
            "date": date_str,
            "total_segments": len(transcript),
            "matched_segments": len(matched_segs),
            "speakers": speakers,
            "query": query,
            "matched_segment_preview": preview,
            "matched_segment": first_match,
        })

        if len(results) >= limit:
            break

    return results


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: azure_transcript_search.py <query>")
        sys.exit(1)

    query = sys.argv[1]
    results = search_transcripts(query, limit=5)
    for r in results:
        print(f"\n--- {r['date']} | {r['meeting_id']} | {r['matched_segments']} matches ---")
        print(f"Speakers: {', '.join(r['speakers'])}")
        print(f"Preview: {r['matched_segment_preview']}")
