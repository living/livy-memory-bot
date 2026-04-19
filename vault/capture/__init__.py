"""Capture module — raw data fetchers for vault ingestion.

Provides lazy-loaded segment fetchers that extract raw transcript segments
from Azure Blob Storage or Supabase, feeding structured data into vault
processing pipelines.
"""
from vault.capture.azure_blob_client import load_transcript_segments
from vault.capture.supabase_transcript import load_segments_from_supabase

__all__ = [
    "load_transcript_segments",
    "load_segments_from_supabase",
]
