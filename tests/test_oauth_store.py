import base64

import pytest

from app.market_radar import mercado_livre_auth as oauth
from app.market_radar.oauth_store import OAuthCrypto, OAuthStoreError


def _key(byte: int = 7) -> str:
    return base64.urlsafe_b64encode(bytes([byte]) * 32).decode("ascii")


def test_aes_gcm_is_authenticated_and_does_not_accept_the_wrong_key():
    encrypted = OAuthCrypto(_key()).encrypt("server-only-token")
    assert OAuthCrypto(_key()).decrypt(encrypted) == "server-only-token"
    with pytest.raises(OAuthStoreError):
        OAuthCrypto(_key(8)).decrypt(encrypted)


def test_hosted_store_configuration_rejects_partial_configuration(monkeypatch):
    monkeypatch.setenv("OAUTH_DATABASE_URL", "postgresql://example.invalid/db")
    monkeypatch.delenv("MERCADO_LIVRE_TOKEN_ENCRYPTION_KEY", raising=False)
    from app.market_radar.oauth_store import configured_store
    with pytest.raises(OAuthStoreError):
        configured_store()


class _Store:
    def __init__(self):
        self.state = None
        self.consumed = False
        self.saved = None

    def token_pair(self):
        return None, "stored-refresh", None

    def create_transaction(self, state, verifier):
        self.state = (state, verifier)

    def consume_verifier(self, state):
        if not self.state or self.consumed or state != self.state[0]:
            raise OAuthStoreError("invalid state")
        self.consumed = True
        return self.state[1]

    def save_tokens(self, payload):
        self.saved = payload
        return {"issued_at": "now", "expires_in": 1, "expires_at": "later"}

    def refresh_atomically(self, exchange):
        payload = exchange("stored-refresh")
        self.saved = payload
        return {"issued_at": "now", "expires_in": 1, "expires_at": "later"}


def test_durable_state_is_single_use_and_refresh_delegates_to_atomic_store(monkeypatch):
    store = _Store()
    monkeypatch.setattr(oauth, "configured_store", lambda: store)
    monkeypatch.setenv("MERCADO_LIVRE_CLIENT_ID", "client")
    monkeypatch.setenv("MERCADO_LIVRE_CLIENT_SECRET", "secret")
    monkeypatch.setenv("MERCADO_LIVRE_REDIRECT_URI", "https://example.test/callback")
    start = oauth.start_authorization()
    assert start["state"] == store.state[0]
    monkeypatch.setattr(oauth, "_post_form", lambda body: {"access_token": "access", "refresh_token": "rotated", "expires_in": 2})
    assert oauth.exchange_code(code="code", state=start["state"])["expires_in"] == 1
    with pytest.raises(oauth.MercadoLivreOAuthError):
        oauth.exchange_code(code="code", state=start["state"])
    assert oauth.refresh_mercado_livre_token()["expires_in"] == 1
    assert store.saved["refresh_token"] == "rotated"
