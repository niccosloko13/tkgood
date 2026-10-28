import hashlib
import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

from scripts.auto_sync_tiktok_neon import outbox, enqueue_from_library, send_pending, public_projection


def test_projection_omits_sensitive_fields():
    value = public_projection({"video_id":"123","caption":"hello","cookie":"secret","profile":"private"})
    assert value == {"video_id":"123","caption":"hello"}


def test_outbox_deduplicates_and_requeues_changed_observation(tmp_path: Path):
    path=tmp_path/"outbox.db"
    db=outbox(path)
    fake={"items":[{"video_id":"123","caption":"original","metrics":{"views":3}}]}
    with patch("scripts.auto_sync_tiktok_neon.connect") as local, patch("scripts.auto_sync_tiktok_neon.library_read_model",return_value=fake):
        local.return_value.__enter__.return_value=object()
        assert enqueue_from_library(db)[1]==1
        assert enqueue_from_library(db)[1]==0
        fake["items"][0]["caption"]="updated"
        assert enqueue_from_library(db)[1]==1
    assert db.execute("SELECT count(*) FROM pending").fetchone()[0]==1
    db.close()


def test_delivery_ack_deletes_only_confirmed_batch(tmp_path: Path):
    db=outbox(tmp_path/"outbox.db")
    payload=json.dumps({"video_id":"123"})
    db.execute("INSERT INTO pending(video_id,checksum,payload,updated_at) VALUES (?,?,?,0)",("123","sha",payload))
    db.commit()
    class Reply:
        status=200
        def __enter__(self): return self
        def __exit__(self,*args): return False
        def read(self,n): return b'{"accepted":1}'
    with patch("scripts.auto_sync_tiktok_neon.request.urlopen",return_value=Reply()):
        assert send_pending(db,base="https://example.org",secret="x"*64)==(1,0)
    assert db.execute("SELECT count(*) FROM pending").fetchone()[0]==0
    assert db.execute("SELECT count(*) FROM delivered").fetchone()[0]==1
    db.close()
