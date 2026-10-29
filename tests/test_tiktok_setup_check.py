from unittest.mock import patch
from app.tiktok_official_login import setup_check
from starlette.requests import Request

def test_setup_check_reports_missing_inputs_without_exposing_values():
    env={"TIKTOK_CLIENT_KEY":"visible-client-key","TIKTOK_CLIENT_SECRET":"private-test-secret",
         "TIKTOK_REDIRECT_URI":"https://babi-product-hunter.vercel.app/api/v2/tiktok-connect/callback",
         "OAUTH_DATABASE_URL":"postgresql://private-host","TIKTOK_OAUTH_ENCRYPTION_KEY":"invalid"}
    with patch.dict("os.environ",env):
        result=setup_check(Request({'type':'http','scheme':'https','server':('babi-product-hunter.vercel.app',443),'path':'/api/v2/tiktok-connect/setup-check','headers':[]}))
    assert result["client_key_set"] and result["client_secret_set"]
    assert not result["encryption_key_valid"] and not result["login_kit_ready"]
    assert "private-test-secret" not in str(result)
    assert "postgresql://" not in str(result)
    assert result["redirect_host_matches_babi"]
