"""Search/detail regression coverage, reconstructed after a backlog-test name collision.

Keep the public result() fixture used by test_capture. Backlog tests live separately.
"""
import copy
import json
from pathlib import Path
import pytest
from pydantic import ValidationError
from app import db
from app.extraction import parse_views,video_identity,legacy_url_fallback,completeness,capture_quality,merge_evidence,STRUCTURED_FIELDS
from app.schemas import VisibleVideo,SearchResults
from app.observations import save_capture,save_detail,sanitize_snapshot,quality
from test_capture import database


def result(url='https://www.tiktok.com/@maker/video/123',**changes):
    url,vid=video_identity(url)
    value=dict(video_url=url,video_id=vid,creator_username='@maker',creator_display_name='Maker',
       caption='Useful portable blender',views_raw='83.1K',views=83100,thumbnail_url='https://images.example/product.jpg',
       search_position=1,extraction_version='tiktok-search-card-v2')
    value.update(changes)
    value['field_evidence']={k:dict(value=value[k],source='search_card',confidence=.98) for k in STRUCTURED_FIELDS if value.get(k) is not None}
    if value.get('views') is not None:value['field_evidence']['views']['raw_value']=value['views_raw']
    value['extraction_completeness']=completeness(value)
    return value


def capture(*items):
    return SearchResults(query='home gadgets',page_url='https://www.tiktok.com/search?q=home+gadgets',results_count=len(items),links_detected=len(items),results=list(items)).model_dump()


@pytest.mark.parametrize('raw,expected',json.loads(Path('tests/fixtures/view-formats.json').read_text(encoding='utf-8')))
def test_view_parser(raw,expected):
    assert parse_views(raw)==expected


def test_video_identity_and_normalization():
    assert video_identity('https://tiktok.com/@Maker/video/123/?x=1')[0]=='https://www.tiktok.com/@Maker/video/123'
    for url in ['http://www.tiktok.com/@a/video/123','https://www.tiktok.com/settings','https://www.tiktok.com.evil.test/@a/video/123','https://www.tiktok.com/@a/video/no']:
        with pytest.raises(ValueError):video_identity(url)


def test_field_precedence_and_recency():
    def ev(value,source,date):return {'caption':dict(value=value,source=source,observed_at=date)}
    strong=ev('detail','video_detail','2026-01-01T00:00:00')
    assert merge_evidence(strong,ev('new search','search_card','2026-02-01T00:00:00'))==strong
    assert merge_evidence(strong,ev(None,'video_detail','2026-03-01T00:00:00'))==strong
    assert merge_evidence(strong,ev('new detail','video_detail','2026-03-01T00:00:00'))['caption']['value']=='new detail'


def test_completeness_and_coverage():
    full=result();minimal=result(caption=None,creator_username=None,thumbnail_url=None,views=None,views_raw=None)
    assert completeness(full)==1 and completeness(minimal)==2/6
    report=capture_quality([full]*8)
    assert report['thresholds_met'] and report['coverage']['caption']==100
    assert capture_quality([])['total']==0 and not capture_quality([minimal]*8)['thresholds_met']


def test_strict_field_confidence_source_identity_and_normalized_values():
    VisibleVideo(**result())
    for change in [{'video_id':'999'},{'views':1},{'thumbnail_url':'javascript:alert(1)'},{'extraction_completeness':0}]:
        bad=result();bad.update(change)
        with pytest.raises(ValidationError):VisibleVideo(**bad)
    for change in [{'confidence':.2},{'source':'external_source'},{'value':'invented'}]:
        bad=result();bad['field_evidence']['caption'].update(change)
        with pytest.raises(ValidationError):VisibleVideo(**bad)


def test_snapshot_sanitization():
    raw='<div onclick="bad()"><script>secret</script><input value="secret"><form>private</form><b>product</b></div>'
    cleaned=sanitize_snapshot(raw)
    assert 'secret' not in cleaned and 'onclick' not in cleaned and '<input' not in cleaned and 'product' in cleaned
    assert len(sanitize_snapshot('<div>'+'x'*15000+'</div>'))<=12000


def test_video_dedup_and_observation_history_and_latest_capture_quality(database):
    with db.connect() as c:
        assert save_capture(c,capture(result()),'command:1','2026-01-01T00:00:00')==(1,0)
        save_capture(c,capture(result()),'command:1','2026-01-01T00:00:00')
        save_capture(c,capture(result(caption='new caption')),'command:2','2026-01-02T00:00:00')
        assert c.execute('SELECT count(*) FROM videos').fetchone()[0]==1
        assert c.execute('SELECT count(*) FROM search_observations').fetchone()[0]==2
        assert c.execute('SELECT first_seen_at FROM videos').fetchone()[0]=='2026-01-01T00:00:00'
        save_capture(c,capture(result(caption=None)),'command:3','2026-01-03T00:00:00')
        assert quality(c)['coverage']['caption']==0
        assert c.execute('SELECT caption FROM videos').fetchone()[0]=='new caption'
        save_capture(c,capture(),'command:4','2026-01-04T00:00:00')
        assert quality(c)['current_capture']==0 and quality(c)['library_total']==1


def test_storage_preserves_stronger_fields_but_observation_retains_local_evidence(database):
    with db.connect() as c:
        save_capture(c,capture(result()),'command:1','2026-01-01T00:00:00')
        detail=result(caption='strong detail');detail['extraction_version']='tiktok-video-detail-v1'
        for field in detail['field_evidence'].values():field['source']='video_detail'
        assert save_detail(c,detail,123,'2026-01-02T00:00:00')
        save_capture(c,capture(result(caption='new weaker caption')),'command:2','2026-01-03T00:00:00')
        assert c.execute('SELECT caption FROM videos').fetchone()[0]=='strong detail'
        assert json.loads(c.execute('SELECT fields_json FROM search_observations ORDER BY id DESC LIMIT 1').fetchone()[0])['caption']=='new weaker caption'


def test_metric_evidence_preserved_without_inventing_missing_metrics(database):
    with db.connect() as c:
        save_capture(c,capture(result()),'command:1','2026-01-01T00:00:00')
        evidence=json.loads(c.execute('SELECT field_evidence_json FROM videos').fetchone()[0])
        assert evidence['views']['value']==83100
        assert all(k not in evidence for k in ['likes','comments_count','shares','favorites'])
        item=result();item['likes']='0';item['field_evidence']['likes']={'value':0,'raw_value':'0','source':'search_card','confidence':.98}
        save_capture(c,capture(item),'command:2','2026-01-02T00:00:00')
        evidence=json.loads(c.execute('SELECT field_evidence_json FROM videos').fetchone()[0])
        assert evidence['likes']['value']==0 and 'shares' not in evidence


def test_legacy_canonical_fallback_deduplicates_without_inventing_video_id(database):
    assert legacy_url_fallback('https://tiktok.com/legacy/?token=ignored')=='https://www.tiktok.com/legacy'
    assert legacy_url_fallback('https://www.tiktok.com/@maker/').endswith('/@maker')
    with db.connect() as c:
        for n,url in enumerate(['https://tiktok.com/legacy/?x=1','https://www.tiktok.com/legacy/?x=2']):
            save_capture(c,{'query':'legacy','results':[{'video_url':url}]},f'legacy:{n}','2026-01-01')
        assert c.execute('SELECT count(*) FROM videos').fetchone()[0]==1
        assert c.execute('SELECT video_id FROM videos').fetchone()[0] is None
        assert c.execute('SELECT count(*) FROM search_observations').fetchone()[0]==2


def test_legacy_eight_video_migration_is_lossless_and_idempotent(database):
    with db.connect() as c:
        c.execute("DELETE FROM schema_migrations WHERE name='search-enrichment-v1'")
        for i in range(8):
            c.execute("INSERT INTO video_observations(search_query,video_url,collected_at,first_seen_at,last_seen_at,extraction_version) VALUES ('legacy',?,'2026-01-01','2026-01-01','2026-01-01','search-dom-v1')",(f'https://www.tiktok.com/@maker/video/{i}',))
        before=[tuple(r) for r in c.execute('SELECT * FROM video_observations ORDER BY id')]
    db.init_db();db.init_db()
    with db.connect() as c:
        assert c.execute('SELECT count(*) FROM videos').fetchone()[0]==8
        assert c.execute('SELECT count(*) FROM video_observations').fetchone()[0]==8
        assert c.execute('SELECT count(*) FROM search_observations').fetchone()[0]==8
        assert before==[tuple(r) for r in c.execute('SELECT * FROM video_observations ORDER BY id')]


def test_library_capture_new_updated_counters_backfill_and_history(database):
    with db.connect() as c:
        save_capture(c,capture(result()),'command:1','2026-01-01T00:00:00')
        save_capture(c,capture(result()),'command:2','2026-01-02T00:00:00')
        rows=c.execute('SELECT new_count,updated_count FROM search_captures ORDER BY capture_id').fetchall()
        assert [tuple(r) for r in rows]==[(1,0),(0,1)]
        c.execute("UPDATE search_captures SET new_count=NULL,updated_count=NULL WHERE capture_id='command:1'")
    db.init_db()
    with db.connect() as c:
        assert tuple(c.execute("SELECT new_count,updated_count FROM search_captures WHERE capture_id='command:1'").fetchone())==(1,0)
