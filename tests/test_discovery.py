import copy
from datetime import datetime,timedelta,timezone
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from app import db,discovery
from app.schemas import DiscoveryCommand,SearchResults
from test_capture import api,database


def start(query='home gadgets',**limits):
    options={'max_scrolls':5,'max_new_videos':30,'max_runtime':90,**limits}
    command=db.enqueue_command('DISCOVER_MORE_RESULTS',query,'ext',options)
    db.claim_command('ext')
    return command


def viewport(command,iteration,ids,query='home gadgets'):
    capture=SearchResults.model_validate({'query':query,'page_url':'https://www.tiktok.com/search?q='+query.replace(' ','+'),
        'results_count':len(ids),'links_detected':len(ids),'results':[{'video_id':str(n),'video_url':f'https://www.tiktok.com/@maker/video/{n}',
        'caption':'portable blender','search_position':i+1} for i,n in enumerate(ids)]}).model_dump()
    return {'extension_id':'ext','scroll_iteration':iteration,'document_token':'document-1','dom_card_count':len(ids),'capture':capture}


def step(command,iteration,ids,query='home gadgets'):
    with db.connect() as con:return discovery.ingest_step(con,command,viewport(command,iteration,ids,query))


def test_scroll_adds_videos_dedup_depth_history_and_rerun(database):
    command=start()
    first=step(command,0,[1,2]);second=step(command,1,[2,3])
    assert first['visible_start']==2 and second['unique_videos']==3
    assert second['new_videos']==3 and second['duplicates']==1 and second['scroll_count']==1
    with db.connect() as con:
        replay=discovery.ingest_step(con,command,viewport(command,1,[2,3]))
        assert replay['new_videos']==3
        assert con.execute('SELECT count(*) FROM videos').fetchone()[0]==3
        assert con.execute('SELECT count(*) FROM search_observations').fetchone()[0]==4
        rows=con.execute('SELECT * FROM search_observations WHERE scroll_iteration=1').fetchall()
        assert len(rows)==2 and all(r['global_position_estimate'] is None for r in rows)
        assert [r['visible_position'] for r in rows]==[1,2]
        assert len(discovery.enrichment_queue(con))==3
        changed=viewport(command,1,[2,4])
        with pytest.raises(HTTPException):discovery.ingest_step(con,command,changed)


def test_two_stagnant_cycles_stop(database):
    command=start();step(command,0,[1,2]);step(command,1,[1,2]);end=step(command,2,[1,2])
    assert end['stop_reason']=='no_new_results' and end['scroll_count']==2
    assert db.list_commands()[0]['status']=='SUCCEEDED'


def test_dom_stagnation_stops_even_if_visible_ids_rotate(database):
    command=start();step(command,0,[1,2]);step(command,1,[3,4]);end=step(command,2,[5,6])
    assert end['stop_reason']=='no_new_results' and end['stop_detail']=='dom_not_growing'
    assert end['unique_videos']==6


def test_hard_unique_session_cap_is_enforced(database):
    command=start();step(command,0,list(range(1,21)));end=step(command,1,list(range(21,41)))
    assert end['unique_videos']==30 and end['new_videos']==30 and end['stop_reason']=='max_videos'


def test_max_scroll_and_video_limits(database):
    command=start(max_scrolls=1);step(command,0,[1]);end=step(command,1,[2])
    assert end['stop_reason']=='max_scrolls'
    other=start(max_new_videos=1)
    end=step(other,0,[3,4,5])
    assert end['stop_reason']=='max_videos' and end['new_videos']==1
    with db.connect() as con:assert con.execute('SELECT count(*) FROM videos').fetchone()[0]==3


def test_timeout_and_security_stop_without_further_capture(database):
    command=start()
    with db.connect() as con:
        con.execute('UPDATE discovery_sessions SET started_at=? WHERE command_id=?',((datetime.now(timezone.utc)-timedelta(seconds=91)).isoformat(),command))
        assert discovery.control(con,command,'ext')['stop_reason']=='timeout'
    command=start()
    with db.connect() as con:
        discovery.finish(con,discovery.session_for(con,command),'security_challenge')
        assert discovery.session_for(con,command)['stop_reason']=='security_challenge'
        with pytest.raises(HTTPException):discovery.ingest_step(con,command,viewport(command,0,[1]))


@pytest.mark.parametrize('state',['PENDING','DISPATCHED'])
def test_cancel_all_active_states_cleanly(database,state):
    command=start()
    with db.connect() as con:
        con.execute('UPDATE bridge_commands SET status=? WHERE id=?',(state,command))
        con.execute('UPDATE discovery_sessions SET status=? WHERE command_id=?',(state,command))
        session=discovery.session_for(con,command)
        discovery.finish(con,session,'manual_stop');discovery.finish(con,discovery.session_for(con,command),'manual_stop')
        assert discovery.session_for(con,command)['status']=='CANCELLED'
        assert discovery.session_for(con,command)['command_status']=='SUCCEEDED'



def test_search_query_history_and_ownership(database):
    first=start();step(first,0,[1])
    with db.connect() as con:discovery.finish(con,discovery.session_for(con,first),'manual_stop')
    second=start(query='kitchen gadgets');step(second,0,[1],query='kitchen gadgets')
    with db.connect() as con:
        video=con.execute('SELECT * FROM videos').fetchone()
        assert video['first_search_query']=='home gadgets' and video['latest_search_query']=='kitchen gadgets'
        assert con.execute('SELECT count(DISTINCT search_query) FROM search_observations').fetchone()[0]==2
        assert discovery.session_for(con,second)['new_videos']==0
        bad=viewport(second,1,[2],query='kitchen gadgets');bad['extension_id']='other'
        with pytest.raises(HTTPException):discovery.ingest_step(con,second,bad)


def test_api_discovery_session_and_cancel(api):
    _,call=api
    call('/api/bridge/heartbeat',{'current_url':'https://www.tiktok.com/search?q=home+gadgets'})
    code,cmd=call('/api/commands',{'type':'DISCOVER_MORE_RESULTS','query':'home gadgets'})
    assert code==201
    call('/api/bridge/commands/next?extension_id=ext')
    assert call(f"/api/bridge/discovery/{cmd['id']}/step",viewport(cmd['id'],0,[1,2]))[0]==200
    appearances=call('/api/videos/1/search-appearances')[1]
    assert appearances['first_search_query']=='home gadgets' and appearances['total']==1
    assert appearances['items'][0]['scroll_iteration']==0
    assert appearances['items'][0]['global_position_estimate'] is None
    session=call('/api/discovery/sessions')[1]['items'][0]
    assert call(f"/api/discovery/sessions/{session['id']}/stop",{})[0]==200
    assert call('/api/discovery/sessions')[1]['items'][0]['stop_reason']=='manual_stop'
    assert len(call('/api/discovery/enrichment-queue')[1]['items'])==2
    assert call('/api/commands',{'type':'DISCOVER_MORE_RESULTS','query':'other'})[0]==409
    assert call('/api/commands',{'type':'DISCOVER_MORE_RESULTS','query':'home gadgets','max_scrolls':6})[0]==422


def test_additive_migration_preserves_command_and_appearances(database):
    cmd=start();step(cmd,0,[1,2])
    db.init_db();db.init_db()
    with db.connect() as con:
        assert con.execute('SELECT count(*) FROM search_observations').fetchone()[0]==2
        assert con.execute('SELECT count(*) FROM discovery_sessions').fetchone()[0]==1
        assert discovery.session_for(con,cmd)['unique_videos']==2


def test_manual_vocabulary_is_versioned_and_requires_a_new_run(database):
    from app.product_detection import detect,records
    from app.candidate_gaps import unresolved_records,review_phrase
    from app.product_vocabulary import version
    from test_product_detection import seed
    with db.connect() as con:seed(con,'self squeezing mop')
    with db.connect() as con:
        assert detect(con)['vocabulary_version']=='product-vocabulary-v1'
        phrase=unresolved_records(con)[0]
        result=review_phrase(con,phrase['id'],'approved','','2026-10-22')
        assert result['vocabulary_version']=='product-vocabulary-v2'
        assert not records(con)
        review_phrase(con,phrase['id'],'approved','','2026-10-22')
        assert version(con)=='product-vocabulary-v2'
    with db.connect() as con:
        report=detect(con)
        assert report['candidates_created']==1
        assert con.execute('SELECT vocabulary_version FROM product_detection_runs ORDER BY id DESC LIMIT 1').fetchone()[0]=='product-vocabulary-v2'
        review_phrase(con,phrase['id'],'rejected','','2026-10-22')
        assert version(con)=='product-vocabulary-v3'
