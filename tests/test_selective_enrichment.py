import json
import pytest
from fastapi import HTTPException
from app import db,selective_enrichment as s,safe_collection as safe,target_safety,browser_safety
from app.observations import save_capture
from test_capture import database,api
from test_backlog import seed,reader as fixture_reader
from test_safe_collection import bridge


def setup(n=7):
    seed(n)
    with db.connect() as c:
        c.execute("UPDATE videos SET caption='soap dispenser'")
        save_capture(c,{'query':'home gadgets','results':[{'video_id':str(i),'video_url':f'https://www.tiktok.com/@maker/video/{i}','caption':'soap dispenser','creator_username':'@maker'} for i in range(1,n+1)]},'fixture:selective',s.now())
        safe.put(c,'tiktok_bridge',bridge())
        safe.put(c,'safe_collection_guard',{'enabled':True,'validation_id':'search-only'})


def reader(vid,step):
    result=fixture_reader(vid,step)
    with db.connect() as c:
        run=s.active(c);url=c.execute('SELECT canonical_url FROM videos WHERE id=?',(vid,)).fetchone()[0]
        c.execute('INSERT INTO bridge_commands(id,created_at,updated_at,type,query,status,extension_id,options_json) VALUES (?,?,?,?,?,?,?,?)',(result['id'],s.now(),s.now(),s.TYPES[step],url if step!='creator' else 'https://www.tiktok.com/@maker','SUCCEEDED','a'*32,json.dumps({'selective_run_id':run['id']})))
        if step=='comments':
            sample=c.execute('SELECT id FROM comment_samples WHERE command_id=?',(result['id'],)).fetchone()[0]
            for i in range(30):
                text='Where to buy? Price please' if i<20 else 'useful good product'
                c.execute("INSERT INTO comment_observations(sample_id,video_id,comment_key,author_username,text,position,source,observed_at,raw_visible_text,extraction_method,confidence,extractor_version) VALUES (?,?,?,?,?,?,'comments_visible',?,?,?,.9,'test')",(sample,vid,str(i),'@author'+str(i),text,i+1,s.now(),text,'semantic_text'))
    return result


def test_frozen_high_selection_caps_five_and_recomputes_only_selected(database):
    setup();calls=[]
    with db.connect() as c:
        buckets=s.candidates(c);assert sum(x['priority']=='HIGH' for x in buckets)==7
        assert all('score' not in x for x in buckets)
    ident=s.create('fixture-pilot')
    with db.connect() as c:
        assert len(json.loads(s.active(c)['selected_json']))==5
        original=[r[0] for r in c.execute('SELECT priority_json FROM selective_items WHERE run_id=? ORDER BY video_id',(ident,))]
    def recorded(vid,step):calls.append((vid,step));return reader(vid,step)
    result=s.run(ident,recorded)
    assert result['selected']==result['enriched']==5 and result['details_collected']==5
    assert result['comment_samples_collected']==5 and result['comments_collected']==150
    assert sum(step=='creator' for _,step in calls)==1
    assert all(v<=5 for v,_ in calls)
    assert result['items'][0]['before']['purchase_intent']['status']=='insufficient_data'
    assert result['items'][0]['after']['purchase_intent']['status']=='measured'
    assert result['run']['checkpoint']['unselected_unchanged']
    with db.connect() as c:
        assert not c.execute('SELECT 1 FROM intelligence_decisions WHERE video_id>5').fetchone()
        assert not c.execute('SELECT 1 FROM intelligence_dimension_snapshots WHERE video_id>5').fetchone()
        assert original==[r[0] for r in c.execute('SELECT priority_json FROM selective_items WHERE run_id=? ORDER BY video_id',(ident,))]
    with pytest.raises(HTTPException):s.create('fixture-pilot')


def test_insufficient_and_blocked_targets_never_selected_or_requested(database):
    setup(4)
    with db.connect() as c:
        target_safety.quarantine(c,'https://www.tiktok.com/@maker/video/1',s.now())
        c.execute('UPDATE videos SET caption=NULL,creator_username=NULL WHERE id=2')
        buckets={x['video_id']:x['priority'] for x in s.candidates(c)}
        assert buckets[1]=='LOW' and buckets[2]=='INSUFFICIENT'
    calls=[]
    result=s.run(s.create('quarantine'),lambda v,step:(calls.append((v,step)),reader(v,step))[1])
    assert {v for v,_ in calls}=={3,4}
    assert result['selected']==2 and result['stop_reason']=='NO_MORE_HIGH'


def test_guard_preserves_search_only_and_authorizes_exact_current_selected_step(database):
    setup(2);ident=s.create('guard')
    with db.connect() as c:
        c.execute('UPDATE selective_runs SET current_video=1,current_step=? WHERE id=?',('detail',ident))
        c.execute("UPDATE selective_items SET status='RUNNING' WHERE run_id=? AND video_id=1",(ident,))
    with pytest.raises(HTTPException):db.enqueue_command('READ_VIDEO_DETAIL','https://www.tiktok.com/@maker/video/1','a'*32)
    token=s.CONTEXT.set(True)
    try:
        with pytest.raises(HTTPException):db.enqueue_command('SEARCH','home gadgets','a'*32)
        with pytest.raises(HTTPException):db.enqueue_command('READ_VIDEO_DETAIL','https://www.tiktok.com/@maker/video/2','a'*32)
        cmd=db.enqueue_command('READ_VIDEO_DETAIL','https://www.tiktok.com/@maker/video/1','a'*32)
        assert db.claim_command('a'*32)['id']==cmd
    finally:s.CONTEXT.reset(token)


def test_global_stop_preserves_collected_step_and_stops_all_further_reads(database):
    setup(3);calls=[]
    def blocked(v,step):
        calls.append((v,step));result=reader(v,step)
        browser_safety.stop('CAPTCHA verify human',s.now());return result
    result=s.run(s.create('global'),blocked)
    assert calls==[(1,'detail')]
    assert result['stop_reason']=='GLOBAL_SECURITY_EVENT'
    assert result['details_collected']==1 and result['items'][0]['after'] is not None
    assert result['global_security']['reason']=='CAPTCHA verify human'


def test_target_failure_is_quarantined_without_global_stop_and_other_healthy_items_continue(database):
    setup(3);calls=[]
    def isolated(v,step):
        calls.append((v,step))
        if v==1:
            with db.connect() as c:target_safety.quarantine(c,'https://www.tiktok.com/@maker/video/1',s.now())
            return {'status':'FAILED','detail':'TARGET_HTTP_403_QUARANTINED'}
        return reader(v,step)
    result=s.run(s.create('target'),isolated)
    assert [x for x in calls if x[0]==1]==[(1,'detail')]
    assert result['blocked']==1 and result['enriched']==2 and not result['global_security'].get('reason')


def test_result_endpoint_does_not_promote_confirmed_quarantined_target_to_global(api):
    setup(1)
    with db.connect() as c:
        c.execute("INSERT INTO bridge_commands(id,created_at,updated_at,type,query,status,extension_id) VALUES (1,?,?,'READ_VIDEO_DETAIL',?,'DISPATCHED','ext')",(s.now(),s.now(),'https://www.tiktok.com/@maker/video/1'))
        target_safety.quarantine(c,'https://www.tiktok.com/@maker/video/1',s.now())
    code,_=api[1]('/api/bridge/commands/1/result',{'extension_id':'ext','status':'FAILED','detail':'TARGET_HTTP_403_QUARANTINED'})
    assert code==200 and not db.get_state('browser_security_stop',{}).get('reason')


def test_runtime_limit_prevents_any_reader_request(database,monkeypatch):
    setup(2);monkeypatch.setattr(s,'RUNTIME',1)
    result=s.run(s.create('timeout'),lambda *args:pytest.fail('no request after budget admission fails'))
    assert result['stop_reason']=='MAX_RUNTIME' and result['details_collected']==0


def test_quarantined_target_does_not_mask_challenge_in_result(api):
    setup(1)
    with db.connect() as c:
        c.execute("INSERT INTO bridge_commands(id,created_at,updated_at,type,query,status,extension_id) VALUES (1,?,?,'READ_VIDEO_DETAIL',?,'DISPATCHED','ext')",(s.now(),s.now(),'https://www.tiktok.com/@maker/video/1'))
        target_safety.quarantine(c,'https://www.tiktok.com/@maker/video/1',s.now())
    api[1]('/api/bridge/commands/1/result',{'extension_id':'ext','status':'FAILED','detail':'TARGET_HTTP_403_QUARANTINED; captcha challenge'})
    assert 'captcha' in db.get_state('browser_security_stop')['reason']
