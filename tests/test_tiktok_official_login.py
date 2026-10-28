from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
def test_tiktok_status_requires_no_password():
    with patch.dict("os.environ", {"TIKTOK_CLIENT_KEY":"","TIKTOK_CLIENT_SECRET":"",
                                 "TIKTOK_REDIRECT_URI":"","TIKTOK_OAUTH_ENCRYPTION_KEY":""}):
        r=TestClient(app).get("/api/v2/tiktok-connect/status")
    assert r.status_code==200
    assert r.json()["connected"] is False
    assert r.json()["collector_session_shared"] is False
def test_unconfigured_tiktok_never_redirects_or_requests_credentials():
    with patch.dict("os.environ", {"TIKTOK_CLIENT_KEY":"","TIKTOK_CLIENT_SECRET":"",
                                 "TIKTOK_REDIRECT_URI":"","TIKTOK_OAUTH_ENCRYPTION_KEY":""}):
        r=TestClient(app).get("/api/v2/tiktok-connect/start",follow_redirects=False)
    assert r.status_code==503
    assert "password" not in r.text.lower()
