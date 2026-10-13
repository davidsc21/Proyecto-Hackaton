"""Supabase clients for public and server-only access."""
from __future__ import annotations

from src.config import (
    SUPABASE_ANON_KEY,
    SUPABASE_KEY,
    SUPABASE_PUBLISHABLE_KEY,
    SUPABASE_SERVICE_ROLE_KEY,
    SUPABASE_URL,
)

_client = None
_server_client = None


def get_client():
    """Return a client using a public key suitable for browser-facing access."""
    global _client
    if _client is not None:
        return _client
    public_key = SUPABASE_ANON_KEY or SUPABASE_PUBLISHABLE_KEY or SUPABASE_KEY
    if not SUPABASE_URL or not public_key:
        return None
    try:
        from supabase import create_client

        _client = create_client(SUPABASE_URL, public_key)
        return _client
    except Exception:
        return None


def get_server_client():
    """Return a server-only client for protected reads; never send it to the browser."""
    global _server_client
    if _server_client is not None:
        return _server_client
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return None
    try:
        from supabase import create_client

        _server_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        return _server_client
    except Exception:
        return None


def test_connection(client=None) -> tuple[bool, str]:
    client = client or get_client()
    if client is None:
        return False, "Supabase URL / public key not configured."
    try:
        client.table("sismo").select("id_sismo").limit(1).execute()
        return True, "Connected to Supabase."
    except Exception as exc:
        return False, f"Supabase connection failed: {exc}"
