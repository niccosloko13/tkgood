from unittest.mock import patch
from starlette.requests import Request
from fastapi import HTTPException
import pytest
from app.tiktok_official_login import status,start

def req():
    return Request({"type":"http","method":"GET","path":"/","headers":[]})

def test_unconfigured_status_is_not_connected():
    with patch.dict("os.environ", {"TIKTOK_CLIENT_KEY":"","TIKTOK_CLIENT_SECRET":"",
                                 "TIKTOK_REDIRECT_URI":"","TIKTOK_OAUTH_ENCRYPTION_KEY":""}):
        data=status(req())
    assert data["configured"] is False
    assert data["connected"] is False
    assert data["collector_session_shared"] is False

def test_unconfigured_start_does_not_ask_credentials():
    with patch.dict("os.environ", {"TIKTOK_CLIENT_KEY":"","TIKTOK_CLIENT_SECRET":"",
                                 "TIKTOK_REDIRECT_URI":"","TIKTOK_OAUTH_ENCRYPTION_KEY":""}):
        with pytest.raises(HTTPException) as exc:
            start(req())
    assert exc.value.status_code==503
