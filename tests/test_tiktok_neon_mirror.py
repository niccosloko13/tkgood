from app.tiktok_neon_mirror import PublicVideo, SyncBatch, _validate_public_video
from pydantic import ValidationError
import pytest

def test_video_restricts_metrics_and_private_fields():
    video = PublicVideo(video_id="731234",caption="Test", metrics={"views": 100, "likes": 3, "cookie": "secret", "comments": -12},
                        product={"id":"9","name":"Cabo","token":"secret"})
    value = _validate_public_video(video)
    assert value["metrics"] == {"views": 100, "likes": 3}
    assert value["product"] == {"id": "9", "name": "Cabo"}
    assert "cookie" not in str(value)
    assert "token" not in str(value)

def test_batch_limit_enforced():
    with pytest.raises(ValidationError):
        SyncBatch(videos=[])
    with pytest.raises(ValidationError):
        SyncBatch(videos=[PublicVideo(video_id=str(i)) for i in range(101)])

def test_reject_extra_fields():
    with pytest.raises(ValidationError):
        PublicVideo(video_id="123", session_cookie="secret")
