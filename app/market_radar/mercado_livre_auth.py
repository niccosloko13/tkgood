"""Mercado Livre OAuth with local development and durable hosted storage."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .oauth_store import OAuthStoreError, configured_store

AUTHORIZATION_URL = "https://auth.mercadolivre.com.br/authorization"
TOKEN_URL = "https://api.mercadolibre.com/oauth/token"
_pending: dict[str, str] = {}


class MercadoLivreOAuthError(RuntimeError):
    pass


@dataclass(frozen=True)
class OAuthConfig:
    client_id: str | None
    client_secret: str | None
    redirect_uri: str | None
    access_token: str | None
    refresh_token: str | None

    @property
    def app_configured(self) -> bool:
        return bool(self.client_id and self.client_secret and self.redirect_uri)


def _local_env() -> dict[str, str]:
    path = Path(".env")
    if not path.exists():
        return {}
    allowed = {"MERCADO_LIVRE_CLIENT_ID", "MERCADO_LIVRE_CLIENT_SECRET", "MERCADO_LIVRE_REDIRECT_URI", "MERCADO_LIVRE_ACCESS_TOKEN", "MERCADO_LIVRE_REFRESH_TOKEN"}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key in allowed and value:
            values[key] = value
    return values


def config() -> OAuthConfig:
    local = _local_env()
    values = [os.environ.get(name) or local.get(name) for name in ("MERCADO_LIVRE_CLIENT_ID", "MERCADO_LIVRE_CLIENT_SECRET", "MERCADO_LIVRE_REDIRECT_URI", "MERCADO_LIVRE_ACCESS_TOKEN", "MERCADO_LIVRE_REFRESH_TOKEN")]
    try:
        store = configured_store()
        if store:
            access, refresh, _ = store.token_pair()
            values[3:5] = [access, refresh]
    except OAuthStoreError as exc:
        raise MercadoLivreOAuthError("Hosted OAuth storage is unavailable") from exc
    return OAuthConfig(*values)


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return verifier, challenge


def start_authorization() -> dict:
    settings = config()
    if not settings.app_configured:
        raise MercadoLivreOAuthError("Mercado Livre application configuration is required")
    state = secrets.token_urlsafe(32)
    verifier, challenge = _pkce()
    try:
        store = configured_store()
        if store:
            store.create_transaction(state, verifier)
        else:
            _pending[state] = verifier
    except OAuthStoreError as exc:
        raise MercadoLivreOAuthError("OAuth authorization state could not be stored") from exc
    # Ask only for the two capabilities this read-only integration needs.  The
    # grant remains subject to the permissions configured in Mercado Livre's
    # DevCenter and to the account holder's manual consent.
    params = {"response_type": "code", "client_id": settings.client_id, "redirect_uri": settings.redirect_uri,
              "state": state, "code_challenge": challenge, "code_challenge_method": "S256",
              "scope": "read offline_access"}
    return {"authorization_url": f"{AUTHORIZATION_URL}?{urlencode(params)}", "state": state}


def authorization_grants_summary() -> dict:
    """Return a safe, aggregate view of the official application grants.

    Individual account identifiers and the raw OAuth payload stay server-side.
    This is deliberately separate from token persistence so a grant can be
    audited without exposing an access token to an API client.
    """
    settings = config()
    if not settings.client_id or not settings.access_token:
        raise MercadoLivreOAuthError("Mercado Livre authorization is required")
    from .adapters.mercado_livre import MercadoLivreClient, MercadoLivreError
    try:
        payload = MercadoLivreClient(settings.access_token).get(f"/applications/{settings.client_id}/grants")
    except MercadoLivreError as exc:
        raise MercadoLivreOAuthError("Mercado Livre grants could not be read") from exc
    grants = payload.get("grants") if isinstance(payload, dict) else None
    if not isinstance(grants, list):
        raise MercadoLivreOAuthError("Mercado Livre returned an invalid grants response")
    scopes = sorted({str(scope) for grant in grants if isinstance(grant, dict)
                     for scope in (grant.get("scopes") or []) if isinstance(scope, str)})
    return {"grant_count": len(grants), "scopes": scopes,
            "read_granted": "read" in scopes,
            "offline_access_granted": "offline_access" in scopes,
            "write_granted": "write" in scopes}


def _post_form(values: dict[str, str]) -> dict:
    body = urlencode(values).encode("utf-8")
    request = Request(TOKEN_URL, data=body, headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    try:
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        raise MercadoLivreOAuthError("Mercado Livre token exchange failed") from exc
    if not isinstance(payload, dict) or not payload.get("access_token"):
        raise MercadoLivreOAuthError("Mercado Livre returned an invalid token response")
    return payload


def exchange_code(*, code: str, state: str) -> dict:
    settings = config()
    if not settings.app_configured:
        raise MercadoLivreOAuthError("Mercado Livre application configuration is required")
    try:
        store = configured_store()
        verifier = store.consume_verifier(state) if store else _pending.pop(state, None)
    except OAuthStoreError as exc:
        raise MercadoLivreOAuthError("Invalid or expired authorization state") from exc
    if not verifier:
        raise MercadoLivreOAuthError("Invalid or expired authorization state")
    payload = _post_form({"grant_type": "authorization_code", "client_id": settings.client_id or "", "client_secret": settings.client_secret or "", "code": code, "redirect_uri": settings.redirect_uri or "", "code_verifier": verifier})
    return persist_tokens(payload)


def refresh_mercado_livre_token() -> dict:
    settings = config()
    if not settings.app_configured:
        raise MercadoLivreOAuthError("Mercado Livre refresh authorization is required")
    try:
        store = configured_store()
        if store:
            return store.refresh_atomically(lambda refresh: _post_form({"grant_type": "refresh_token", "client_id": settings.client_id or "", "client_secret": settings.client_secret or "", "refresh_token": refresh}))
    except OAuthStoreError as exc:
        raise MercadoLivreOAuthError("Mercado Livre refresh authorization is required") from exc
    if not settings.refresh_token:
        raise MercadoLivreOAuthError("Mercado Livre refresh authorization is required")
    return persist_tokens(_post_form({"grant_type": "refresh_token", "client_id": settings.client_id or "", "client_secret": settings.client_secret or "", "refresh_token": settings.refresh_token}))


def persist_tokens(payload: dict) -> dict:
    try:
        store = configured_store()
        if store:
            return store.save_tokens(payload)
    except OAuthStoreError as exc:
        raise MercadoLivreOAuthError("Hosted OAuth token storage is unavailable") from exc
    access_token = payload.get("access_token")
    refresh_token = payload.get("refresh_token")
    if not isinstance(access_token, str):
        raise MercadoLivreOAuthError("Mercado Livre response has no access token")
    path = Path(".env")
    existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    updates = {"MERCADO_LIVRE_ACCESS_TOKEN": access_token}
    if isinstance(refresh_token, str):
        updates["MERCADO_LIVRE_REFRESH_TOKEN"] = refresh_token
    retained = [line for line in existing if not any(line.startswith(f"{key}=") for key in updates)]
    path.write_text("\n".join([*retained, *(f"{key}={value}" for key, value in updates.items())]) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    os.environ.update(updates)
    issued_at = datetime.now(timezone.utc)
    expires_in = int(payload.get("expires_in") or 0)
    return {"issued_at": issued_at.isoformat(), "expires_in": expires_in, "expires_at": (issued_at + timedelta(seconds=expires_in)).isoformat() if expires_in else None}


def storage_mode() -> str:
    try:
        return "postgres_encrypted" if configured_store() else "local_env"
    except OAuthStoreError:
        return "unavailable"
