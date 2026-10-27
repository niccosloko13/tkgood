import json
import pytest
from app import db,enrichment as e
from test_capture import database,api


def seed(n=6):
    with db.connect() as c:
        at=e.now()
        creator=c.execute("INSERT INTO creators(platform,username,profile_url,first_seen_at,last_seen_at,extractor_version) VALUES ('tiktok','@maker','https://www.tiktok.com/@maker',?,?,'test')",(at,at)).lastrowid
        for i in range(1,n+1):
            v=c.execute("INSERT INTO videos(source,video_id,canonical_url,creator_username,caption,first_seen_at,last_seen_at,field_evidence_json) VALUES ('tiktok',?,?,'@maker','portable blender',?,?,'{}')",(str(i),f'https://www.tiktok.com/@maker/video/{i}',at,at)).lastrowid
            c.execute("INSERT INTO video_creators VALUES (?,?,?,'test')",(v,creator,at))
            c.execute('INSERT INTO video_enrichment_queue(video_id,created_at,updated_at) VALUES (?,?,?)',(v,at,at))


def reader(vid,step):
    with db.connect() as c:
        at=e.now();cmd=1000+vid*10+e.STEPS.index(step)
        if step=='detail':
            c.execute("INSERT INTO video_detail_observations(video_id,command_id,observed_at,extractor_version,fields_json,field_evidence_json) VALUES (?,?,?,'test',?,'{}')",(vid,cmd,at,json.dumps({'caption':'portable blender','creator_username':'@maker'})))
        elif step=='comments':
            c.execute("INSERT INTO comment_samples(video_id,command_id,observed_at,target_count,stop_reason,scroll_steps,extractor_version,signals_json,terms_config_json,diagnostics_json) VALUES (?,?,?,30,'no_more_loaded',0,'test','{}','{}','[]')",(vid,cmd,at))
        else:
            creator=c.execute('SELECT creator_id FROM video_creators WHERE video_id=?',(vid,)).fetchone()[0]
            c.execute("INSERT INTO creator_profile_observations(creator_id,command_id,observed_at,raw_visible_text,extractor_version,fields_json,field_evidence_json,links_json,signals_json,config_json) VALUES (?,?,?,'profile','test','{}','{}','[]','{}','{}')",(creator,cmd,at))
    return {'id':cmd,'status':'SUCCEEDED','detail':'fixture'}


def test_batch_limit_skip_and_creator_reuse_checkpoint_idempotency(database):
    seed();calls=[]
    def recorded(v,s):calls.append((v,s));return reader(v,s)
    batch=e.create_batch();e.run_batch(batch,recorded)
    with db.connect() as c:
        result=e.overview(c);b=result['batches'][0]
        assert len(b['video_ids'])==5 and b['checkpoint']['videos_processed']==5
        assert b['checkpoint']['detail_complete']==5 and b['checkpoint']['creator_complete']==5
        assert result['counts']['complete']==5
        assert sum(s=='creator' for _,s in calls)==1
        assert c.execute('SELECT count(*) FROM creator_profile_observations').fetchone()[0]==1
    next_batch=e.create_batch();e.run_batch(next_batch,recorded)
    assert len(calls)==13  # 6 detail, 6 samples, one shared profile
    with db.connect() as c:
        before=c.execute('SELECT count(*) FROM product_candidate_evidence').fetchone()[0]
        from app.product_detection import detect
        detect(c)
        assert c.execute('SELECT count(*) FROM product_candidate_evidence').fetchone()[0]==before
    with pytest.raises(Exception):e.create_batch()


def test_failure_isolated_no_comments_without_detail(database):
    seed(5)
    def failing(v,s):
        if v==1 and s=='detail':return {'status':'FAILED','detail':'Metadata timeout'}
        return reader(v,s)
    e.run_batch(e.create_batch(),failing)
    with db.connect() as c:
        result=e.overview(c)
        assert result['batches'][0]['checkpoint']['videos_processed']==5
        first=next(x for x in result['items'] if x['video_id']==1)
        assert first['stages']['detail']['status']=='failed'
        assert first['stages']['comments']['status']=='not_applicable'
        assert result['counts']['complete']==4


def test_stop_after_video_and_resume_no_duplicate_observations(database):
    seed();batch=e.create_batch()
    def stopping(v,s):
        result=reader(v,s)
        if s=='detail':
            with db.connect() as c:c.execute('UPDATE enrichment_batches SET stop_requested=1 WHERE id=?',(batch,))
        return result
    e.run_batch(batch,stopping)
    with db.connect() as c:
        result=e.overview(c)
        assert result['batches'][0]['status']=='stopped'
        assert result['batches'][0]['checkpoint']['videos_processed']==1
        assert result['counts']['complete']==1
    e.run_batch(e.create_batch(),reader)
    with db.connect() as c:
        assert c.execute('SELECT count(*) FROM video_detail_observations').fetchone()[0]==6


def test_selection_transparent_and_broad_diagnostic_does_not_change_score(database):
    seed(2)
    with db.connect() as c:
        c.execute('DELETE FROM video_enrichment_queue WHERE video_id=1')
        items=e.queue(c);assert items[0]['video_id']==2
        assert items[0]['priority_reason']['new_video'] is True
    with db.connect() as c:
        from app.product_detection import detect
        detect(c)
        before=c.execute('SELECT confidence,status FROM product_candidates').fetchall()
        e.diagnose_broad(c)
        assert [tuple(r) for r in before]==[tuple(r) for r in c.execute('SELECT confidence,status FROM product_candidates')]


def test_security_stops_batch_and_no_further_reads(database):
    seed();calls=[]
    def blocked(v,s):
        calls.append((v,s))
        from app.browser_safety import stop
        stop('HTTP 403')
        return {'status':'FAILED','detail':'Security stop HTTP 403'}
    e.run_batch(e.create_batch(),blocked)
    assert len(calls)==1
    with db.connect() as c:assert e.overview(c)['batches'][0]['status']=='failed'


def test_backlog_api_stop_and_recovery(api,monkeypatch):
    _,call=api;seed()
    batch=e.create_batch()
    assert call(f'/api/enrichment/batches/{batch}/stop',{})[0]==200
    assert call('/api/enrichment')[1]['batch_size']==5
    e.recover()
    with db.connect() as c:assert e.overview(c)['batches'][0]['status']=='interrupted'


@pytest.mark.parametrize('step,kind',[('detail','READ_VIDEO_DETAIL'),('comments','READ_COMMENTS_SAMPLE'),('creator','READ_CREATOR_PROFILE')])
def test_worker_uses_actual_strict_command_contract(database,monkeypatch,step,kind):
    seed(1)
    from app import main
    captured=[]
    def enqueue(payload):
        captured.append(payload.model_dump());return {'id':123}
    monkeypatch.setattr(main,'create_command',enqueue)
    monkeypatch.setattr(db,'list_commands',lambda:[{'id':123,'status':'FAILED','detail':'fixture terminal'}])
    assert e.execute_browser(1,step)['status']=='FAILED'
    assert captured[0]['type']==kind
