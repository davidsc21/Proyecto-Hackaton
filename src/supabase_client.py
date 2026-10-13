"""Thin helper to create a Supabase client from environment variables."""

from __future__ import annotations

from typing import Optional

from src.config import has_supabase, SUPABASE_KEY, SUPABASE_URL

_client = None


def get_client():
    """Return a Supabase client, or None when credentials are missing."""
    global _client
    if _client is not None:
        return _client
    if not has_supabase():
        return None
    try:
        from supabase import create_client

        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
        return _client
    except Exception: 
        return None


def test_connection(client=None) -> tuple[bool, str]:
    client = client or get_client()
    if client is None:
        return False, "SUPABASE_URL / SUPABASE_KEY not configured (offline mode)."
    try:
        client.table("earthquakes").select("event_id").limit(1).execute()
        return True, "Connected to Supabase."
    except Exception as exc:
        return False, f"Supabase connection failed: {exc}"
