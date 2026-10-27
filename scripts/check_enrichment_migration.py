"""Validate migration on a temporary SQLite backup, never on the source DB."""
import json
import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import db
from app.extraction import video_identity


def main():
    original = Path(db.DB_PATH).resolve()
    with tempfile.TemporaryDirectory(prefix='product-hunter-migration-') as directory:
        target = Path(directory) / 'migration.db'
        with closing(sqlite3.connect(original.as_uri() + '?mode=ro', uri=True)) as source, closing(sqlite3.connect(target)) as copy:
            source.backup(copy)
        db.DB_PATH = target
        with db.connect() as con:
            before = [dict(row) for row in con.execute('SELECT * FROM video_observations ORDER BY id')]
            has_videos = con.execute("SELECT 1 FROM sqlite_master WHERE name='videos'").fetchone()
            existing_videos = [dict(row) for row in con.execute('SELECT * FROM videos ORDER BY id')] if has_videos else []
            existing_observations = [dict(row) for row in con.execute('SELECT * FROM search_observations ORDER BY id')] if has_videos else []
        db.init_db()
        with db.connect() as con:
            assert before == [dict(row) for row in con.execute('SELECT * FROM video_observations ORDER BY id')]
            if existing_videos:
                assert existing_videos == [dict(row) for row in con.execute('SELECT * FROM videos ORDER BY id')]
                assert existing_observations == [dict(row) for row in con.execute('SELECT * FROM search_observations ORDER BY id')]
            for old in before:
                _, strong_id = video_identity(old['video_url'])
                row = con.execute('SELECT * FROM videos WHERE video_id=?', (strong_id,)).fetchone()
                assert row and row['first_seen_at'] <= old['first_seen_at'] and row['last_seen_at'] >= old['last_seen_at']
            observations = con.execute('SELECT COUNT(*) FROM search_observations').fetchone()[0]
            videos = con.execute('SELECT COUNT(*) FROM videos').fetchone()[0]
        db.init_db()
        with db.connect() as con:
            assert con.execute('SELECT COUNT(*) FROM search_observations').fetchone()[0] == observations
        print(json.dumps({'legacy_rows_preserved': len(before), 'videos_after_migration': videos,
                          'observations_after_migration': observations, 'migration_idempotent': True,
                          'production_database_untouched': True, 'latest_capture': db.extraction_quality()}))


if __name__ == '__main__':
    main()
