import json
from datetime import datetime,timezone,timedelta
import pytest
from fastapi import HTTPException
from app import db,safe_collection as safe,selective_enrichment as s,manual_captcha_recovery as m,target_safety as ts,browser_safety,collection_mode
from test_capture import database
from test_selective_enrichment import setup,reader
from test_safe_collection import EXT,bridge,confirm


def stopped_parent():
    setup(3);parent=s.create('parent-challenge')
    def challenge(vid,step):
        cmd=db.enqueue_command('READ_VIDEO_DETAIL',f'https://www.tiktok.com/@maker/video/{vid}',EXT)
        db.claim_command(EXT);browser_safety.stop('captcha',s.now())
        return next(x for x in db.list_commands() if x['id']==cmd)
    result=s.run(parent,challenge)
    assert result['stop_reason']=='GLOBAL_SECURITY_EVENT'
    return parent


def checked(c):
    ident=safe.request_check(c,EXT)['id'];confirm(c,ident);return ident


def test_context_quarantine_is_association_not_403_and_cannot_be_opened(database):
    parent=stopped_parent()
    with db.connect() as c:
        q=ts.quarantine_challenge_context(c,parent)
        assert q['status']=='TEMPORARILY_QUARANTINED' and q['reason']=='CHALLENGE_TRIGGER_CONTEXT'
        assert 'not evidence' in q['note']
        assert ts.blocked(c,'https://www.tiktok.com/@renamed/video/1')
        assert c.execute('SELECT count(*) FROM target_block_events').fetchone()[0]==0
        assert ts.rows(c)[0]['status']=='TEMPORARILY_QUARANTINED'
    with pytest.raises(HTTPException,match='TARGET_PREVIOUSLY_BLOCKED'):db.enqueue_command('READ_VIDEO_DETAIL','https://www.tiktok.com/@maker/video/1',EXT)


@pytest.mark.parametrize('change',['unconfirmed','challenge','expired','new_incident'])
def test_release_requires_fresh_matching_healthy_confirmed_proof(database,change):
    parent=stopped_parent()
    with db.connect() as c:
        ts.quarantine_challenge_context(c,parent);check=checked(c);incident=safe.state(c,'browser_security_stop')
        if change=='expired':c.execute('UPDATE safe_recovery_checks SET validated_at=? WHERE id=?',((datetime.now(timezone.utc)-timedelta(seconds=16)).isoformat(),check))
        elif change=='new_incident':safe.put(c,'browser_security_stop',{'reason':'new captcha','observed_at':s.now()})
        else:safe.put(c,'tiktok_bridge',{**bridge(),**({'tiktok_session_status':'unconfirmed'} if change=='unconfirmed' else {'current_page_status':'challenge'})})
        with pytest.raises(HTTPException):m.release(c,check,parent,EXT)
        assert safe.state(c,'browser_security_stop').get('reason')
        assert not c.execute('SELECT 1 FROM manual_captcha_recoveries').fetchone()


def test_one_next_high_only_and_recovery_calls_are_idempotent(database,monkeypatch):
    parent=stopped_parent()
    with db.connect() as c:
        ts.quarantine_challenge_context(c,parent);check=checked(c)
        release=m.release(c,check,parent,EXT);again=m.release(c,check,parent,EXT)
        assert again['reused'] and not safe.state(c,'browser_security_stop').get('reason')
        assert safe.state(c,'browser_security_history')['items'][-1]['previous_incident']['reason']=='captcha'
        assert len(release['validation_samples'])==2
        child=m.next_high(c,check,EXT);again=m.next_high(c,check,EXT)
        assert child['video_id']==2 and again['id']==child['id'] and again['reused']
        assert json.loads(c.execute('SELECT selected_json FROM selective_runs WHERE id=?',(child['id'],)).fetchone()[0])==[2]
    events=[]
    def checkpoint(vid,label,after):events.append(('check',vid,label));return {'status':'HEALTHY','samples':[{'consecutive':1},{'consecutive':2}]}
    monkeypatch.setattr(m,'checkpoint',checkpoint)
    def recorded(vid,step):events.append(('read',vid,step));return reader(vid,step)
    result=s.run(child['id'],recorded)
    assert [x[2] for x in events if x[0]=='read']==['detail','comments','creator']
    assert all(x[1]==2 for x in events)
    assert events==[('check',2,'pre'),('read',2,'detail'),('check',2,'detail'),('read',2,'comments'),('check',2,'comments'),('read',2,'creator'),('check',2,'creator')]
    assert result['enriched']==1 and result['selected']==1 and result['stop_reason']=='SINGLE_CANDIDATE_LIMIT'
    assert result['run']['checkpoint']['unselected_unchanged']
    with db.connect() as c:assert c.execute('SELECT count(*) FROM selective_items WHERE run_id=?',(child['id'],)).fetchone()[0]==1


def test_manual_release_keeps_direct_enrichment_paused(database):
    parent=stopped_parent()
    with db.connect() as c:
        safe.put(c,'direct_video_enrichment',{'status':'PAUSED','reason':'REPEATED_CHALLENGE_AFTER_VIDEO_NAVIGATION'})
        ts.quarantine_challenge_context(c,parent);check=checked(c)
        result=m.release(c,check,parent,EXT)
        assert result['release_type']=='EXPLICIT_MANUAL_CAPTCHA_RECOVERY'
        assert safe.state(c,'direct_video_enrichment')['status']=='PAUSED'
        assert not safe.state(c,'browser_security_stop').get('reason')


def test_manual_release_uses_persisted_post_check_challenge_context(database):
    parent=stopped_parent()
    with db.connect() as c:
        command=c.execute("SELECT * FROM bridge_commands WHERE json_extract(options_json,'$.selective_run_id')=?",(parent,)).fetchone()
        c.execute("UPDATE bridge_commands SET status='SUCCEEDED',detail='detail capture persisted before post-check' WHERE id=?",(command['id'],))
        collection_mode.migrate(c)
        incident=safe.state(c,'browser_security_stop')
        c.execute('''INSERT INTO navigation_challenge_contexts VALUES (?,?,?,?,?,?,?,?)''',
            (f'selective:{parent}:individual-navigation-challenge','DIRECT_VIDEO_ENRICHMENT',command['query'],incident['observed_at'],'READ_VIDEO_DETAIL','{}','{}',json.dumps({'command_id':command['id'],'incident':incident})))
        check=checked(c)
        released=m.release(c,check,parent,EXT)
        assert released['temporary_quarantine']['context_command_id']==command['id']
        assert ts.blocked(c,command['query'])


def test_passive_checkpoint_waits_transient_then_two_new_samples_without_commands(database,monkeypatch):
    setup(2);clock=[0]
    with db.connect() as c:safe.put(c,'tiktok_bridge',{**bridge(),'current_url':'https://www.tiktok.com/@maker/video/2','current_page_status':'unknown','tiktok_session_status':'unconfirmed'})
    monkeypatch.setattr(m.time,'monotonic',lambda:clock[0])
    def sleep(seconds):
        clock[0]+=seconds
        with db.connect() as c:safe.put(c,'tiktok_bridge',{**bridge(),'current_url':'https://www.tiktok.com/@maker/video/2'})
    monkeypatch.setattr(m.time,'sleep',sleep)
    result=m.checkpoint(2,'detail')
    assert [x['state'] for x in result['samples']]==['TRANSIENT_LOADING','HEALTHY_CONFIRMED','HEALTHY_CONFIRMED']
    with db.connect() as c:assert c.execute('SELECT count(*) FROM bridge_commands').fetchone()[0]==0


def test_passive_checkpoint_timeout_and_new_challenge_do_not_continue(database,monkeypatch):
    setup(2);clock=[0]
    monkeypatch.setattr(m.time,'monotonic',lambda:clock[0]);monkeypatch.setattr(m.time,'sleep',lambda seconds:clock.__setitem__(0,clock[0]+seconds))
    with db.connect() as c:safe.put(c,'tiktok_bridge',{**bridge(),'current_page_status':'unknown','tiktok_session_status':'unconfirmed'})
    with pytest.raises(m.CheckFailure,match='SESSION_NOT_STABLE'):m.checkpoint(2,'detail')
    assert clock[0]==25
    with db.connect() as c:safe.put(c,'tiktok_bridge',{**bridge(),'current_page_status':'challenge'})
    with pytest.raises(m.CheckFailure,match='GLOBAL_SECURITY_EVENT'):m.checkpoint(2,'detail')
    assert db.get_state('browser_security_stop')['reason'].startswith('GLOBAL_BLOCK:')


def test_passive_target_403_remains_target_quarantine_without_global_promotion(database):
    setup(2)
    with db.connect() as c:safe.put(c,'tiktok_bridge',{**bridge(),'current_url':'https://www.tiktok.com/@maker/video/2','current_page_status':'http_403'})
    with pytest.raises(m.CheckFailure,match='HTTP_403_NO_RETRY'):m.checkpoint(2,'detail')
    with db.connect() as c:
        assert ts.blocked(c,'https://www.tiktok.com/@maker/video/2')
        assert not safe.state(c,'browser_security_stop').get('reason')
