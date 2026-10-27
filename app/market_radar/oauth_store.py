"""Durable, encrypted OAuth state for hosted Mercado Livre authorization."""
from __future__ import annotations

import base64
import hashlib
import os
from datetime import datetime, timedelta, timezone
from typing import Callable

import psycopg
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class OAuthStoreError(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


class OAuthCrypto:
    def __init__(self, encoded_key: str):
        try:
            self.key = base64.urlsafe_b64decode(encoded_key.encode("ascii"))
        except Exception as exc:
            raise OAuthStoreError("OAuth encryption key is invalid") from exc
        if len(self.key) != 32:
            raise OAuthStoreError("OAuth encryption key must be 256 bits")
        self.aes = AESGCM(self.key)

    def encrypt(self, value: str) -> bytes:
        nonce = os.urandom(12)
        return nonce + self.aes.encrypt(nonce, value.encode("utf-8"), b"babi:mercado-livre:v1")

    def decrypt(self, value: bytes) -> str:
        if len(value) < 13:
            raise OAuthStoreError("Stored OAuth value is invalid")
        try:
            return self.aes.decrypt(value[:12], value[12:], b"babi:mercado-livre:v1").decode("utf-8")
        except Exception as exc:
            raise OAuthStoreError("Stored OAuth value cannot be decrypted") from exc


class PostgresOAuthStore:
    def __init__(self, database_url: str, encryption_key: str):
        self.database_url = database_url
        self.crypto = OAuthCrypto(encryption_key)

    def _connect(self):
        return psycopg.connect(self.database_url)

    def migrate(self) -> None:
        with self._connect() as con, con.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS market_oauth_transactions (state_hash TEXT PRIMARY KEY, verifier_ciphertext BYTEA NOT NULL, expires_at TIMESTAMPTZ NOT NULL, consumed_at TIMESTAMPTZ)")
            cur.execute("CREATE TABLE IF NOT EXISTS market_oauth_credentials (provider TEXT PRIMARY KEY, access_token_ciphertext BYTEA NOT NULL, refresh_token_ciphertext BYTEA, refresh_token_received BOOLEAN NOT NULL DEFAULT FALSE, issued_at TIMESTAMPTZ NOT NULL, expires_at TIMESTAMPTZ, updated_at TIMESTAMPTZ NOT NULL)")
            # Existing hosted installations predate the receipt marker.
            cur.execute("ALTER TABLE market_oauth_credentials ADD COLUMN IF NOT EXISTS refresh_token_received BOOLEAN NOT NULL DEFAULT FALSE")

    @staticmethod
    def _state_hash(state: str) -> str:
        return hashlib.sha256(state.encode("utf-8")).hexdigest()

    def create_transaction(self, state: str, verifier: str, *, ttl_minutes: int = 10) -> None:
        self.migrate()
        with self._connect() as con, con.cursor() as cur:
            cur.execute("INSERT INTO market_oauth_transactions(state_hash, verifier_ciphertext, expires_at) VALUES (%s,%s,%s)", (self._state_hash(state), self.crypto.encrypt(verifier), _now() + timedelta(minutes=ttl_minutes)))

    def consume_verifier(self, state: str) -> str:
        self.migrate()
        with self._connect() as con, con.cursor() as cur:
            cur.execute("UPDATE market_oauth_transactions SET consumed_at=NOW() WHERE state_hash=%s AND consumed_at IS NULL AND expires_at > NOW() RETURNING verifier_ciphertext", (self._state_hash(state),))
            row = cur.fetchone()
        if not row:
            raise OAuthStoreError("Invalid or expired authorization state")
        return self.crypto.decrypt(bytes(row[0]))

    def token_pair(self) -> tuple[str | None, str | None, datetime | None]:
        self.migrate()
        with self._connect() as con, con.cursor() as cur:
            cur.execute("SELECT access_token_ciphertext,refresh_token_ciphertext,expires_at FROM market_oauth_credentials WHERE provider='mercado_livre'")
            row = cur.fetchone()
        if not row:
            return None, None, None
        return self.crypto.decrypt(bytes(row[0])), self.crypto.decrypt(bytes(row[1])) if row[1] else None, row[2]

    def save_tokens(self, payload: dict) -> dict:
        access = payload.get("access_token"); refresh = payload.get("refresh_token")
        if not isinstance(access, str) or not access:
            raise OAuthStoreError("Mercado Livre response has no access token")
        issued = _now(); seconds = int(payload.get("expires_in") or 0); expires = issued + timedelta(seconds=seconds) if seconds else None
        with self._connect() as con, con.cursor() as cur:
            refresh_received = isinstance(refresh, str) and bool(refresh)
            cur.execute("INSERT INTO market_oauth_credentials(provider,access_token_ciphertext,refresh_token_ciphertext,refresh_token_received,issued_at,expires_at,updated_at) VALUES ('mercado_livre',%s,%s,%s,%s,%s,%s) ON CONFLICT(provider) DO UPDATE SET access_token_ciphertext=EXCLUDED.access_token_ciphertext,refresh_token_ciphertext=COALESCE(EXCLUDED.refresh_token_ciphertext,market_oauth_credentials.refresh_token_ciphertext),refresh_token_received=EXCLUDED.refresh_token_received,issued_at=EXCLUDED.issued_at,expires_at=EXCLUDED.expires_at,updated_at=EXCLUDED.updated_at", (self.crypto.encrypt(access), self.crypto.encrypt(refresh) if refresh_received else None, refresh_received, issued, expires, issued))
        return {"issued_at": issued.isoformat(), "expires_in": seconds, "expires_at": expires.isoformat() if expires else None,
                "refresh_token_received": refresh_received}

    def refresh_atomically(self, exchange: Callable[[str], dict]) -> dict:
        self.migrate()
        with self._connect() as con, con.cursor() as cur:
            cur.execute("SELECT refresh_token_ciphertext FROM market_oauth_credentials WHERE provider='mercado_livre' FOR UPDATE")
            row = cur.fetchone()
            if not row or not row[0]:
                raise OAuthStoreError("Mercado Livre refresh authorization is required")
            payload = exchange(self.crypto.decrypt(bytes(row[0])))
            access = payload.get("access_token"); refresh = payload.get("refresh_token")
            if not isinstance(access, str) or not access:
                raise OAuthStoreError("Mercado Livre response has no access token")
            issued = _now(); seconds = int(payload.get("expires_in") or 0); expires = issued + timedelta(seconds=seconds) if seconds else None
            cur.execute("UPDATE market_oauth_credentials SET access_token_ciphertext=%s,refresh_token_ciphertext=COALESCE(%s,refresh_token_ciphertext),issued_at=%s,expires_at=%s,updated_at=%s WHERE provider='mercado_livre'", (self.crypto.encrypt(access), self.crypto.encrypt(refresh) if isinstance(refresh, str) and refresh else None, issued, expires, issued))
        return {"issued_at": issued.isoformat(), "expires_in": seconds, "expires_at": expires.isoformat() if expires else None,
                "refresh_token_received": isinstance(refresh, str) and bool(refresh)}


def configured_store() -> PostgresOAuthStore | None:
    url = os.environ.get("OAUTH_DATABASE_URL"); key = os.environ.get("MERCADO_LIVRE_TOKEN_ENCRYPTION_KEY")
    if not url and not key:
        return None
    if not url or not key:
        raise OAuthStoreError("Hosted OAuth storage is not fully configured")
    return PostgresOAuthStore(url, key)
