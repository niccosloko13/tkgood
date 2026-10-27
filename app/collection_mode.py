"""Persisted operational pause, independent of session/security and search policy."""
import json
from pathlib import Path
from fastapi import HTTPException
from . import safe_collection as safe

DIRECT_TYPES=('READ_VIDEO_DETAIL','READ_COMMENTS_SAMPLE','READ_CREATOR_PROFILE')
REASON='REPEATED_CHALLENGE_AFTER_VIDEO_NAVIGATION'
ROOT=Path(__file__).resolve().parents[1]


def migrate(c):
    c.execute('''CREATE TABLE IF NOT EXISTS navigation_challenge_contexts (
      event_key TEXT PRIMARY KEY,navigation_mode TEXT NOT NULL,target TEXT NOT NULL,
      timestamp TEXT NOT NULL,stage TEXT NOT NULL,pre_health_json TEXT NOT NULL,
      post_health_json TEXT NOT NULL,source_json TEXT NOT NULL)''')


def direct(c):
    value=safe.state(c,'direct_video_enrichment')
    return value or {'status':'ENABLED','reason':None}


def assert_allowed(c):
    if direct(c)['status']=='PAUSED':raise HTTPException(409,'DIRECT_VIDEO_ENRICHMENT_PAUSED: '+REASON)


def status(c):
    b=safe.state(c,'tiktok_bridge');h=safe.health(b,b.get('extension_id',''),b.get('build_id',''))
    available=h['status']=='HEALTHY' and not safe.state(c,'browser_security_stop').get('reason') and not safe.state(c,'target_security_pending').get('items')
    return {'direct_video_enrichment':direct(c),'enrichment_availability':'SEARCH_ONLY' if direct(c)['status']=='PAUSED' else 'DIRECT_AVAILABLE',
            'search_collection':'AVAILABLE' if available else 'BLOCKED','page':b.get('current_page_status','unknown'),'session':b.get('tiktok_session_status','unconfirmed'),
            'global_security':'BLOCKED' if safe.state(c,'browser_security_stop').get('reason') else 'healthy','automatic_resume':False}


def _artifact(command):
    for path in (ROOT/'artifacts/selective-enrichment/pilot-v1.json',ROOT/'artifacts/selective-enrichment/manual-captcha-resume-v1.json'):
        try:value=json.loads(path.read_text(encoding='utf-8'))
        except (OSError,ValueError):continue
        if any(x.get('id')==command['id'] and x.get('query')==command['query'] for x in value.get('audit',{}).get('commands',[])):
            return value,str(path.relative_to(ROOT))
    return {},None


def preserve_contexts(c):
    migrate(c)
    for run in c.execute("SELECT * FROM selective_runs WHERE stop_reason='GLOBAL_SECURITY_EVENT'").fetchall():
        command=c.execute("SELECT * FROM bridge_commands WHERE type='READ_VIDEO_DETAIL' AND json_extract(options_json,'$.selective_run_id')=? ORDER BY id DESC LIMIT 1",(run['id'],)).fetchone()
        if not command:continue
        item=c.execute('SELECT steps_json FROM selective_items WHERE run_id=? AND video_id=?',(run['id'],run['current_video'])).fetchone()
        steps=json.loads(item['steps_json']) if item else {}
        if 'captcha' not in command['detail'].lower() and 'challenge' not in command['detail'].lower() and steps.get('detail',{}).get('post_check',{}).get('reason')!='GLOBAL_SECURITY_EVENT':continue
        artifact,path=_artifact(command);result=artifact.get('result',artifact)
        post=artifact.get('post_stop_check') or artifact.get('audit',{}).get('post_stop') or result
        post_health={'page':post.get('current_page_status',post.get('page',post.get('final_page','unknown'))),'session':post.get('tiktok_session_status',post.get('session','unconfirmed')),'observed_at':post.get('last_seen',post.get('observed_at'))}
        checkpoint=json.loads(run['checkpoint_json']);pre=checkpoint.get('pre_check') or {'status':'RAW_SAMPLES_NOT_RETAINED','gate':'HEALTHY/CONFIRMED required at original run creation','samples':[]}
        incident=artifact.get('global_security',result.get('global_security',{}))
        stamp=incident.get('observed_at') or run['finished_at']
        source={'run_id':run['id'],'command_id':command['id'],'detail_status':command['status'],'artifact':path,'incident':incident,'timestamp_basis':'incident.observed_at' if incident.get('observed_at') else 'run.finished_at','causality':'context association only; not proof this target technically caused CAPTCHA'}
        c.execute('INSERT OR IGNORE INTO navigation_challenge_contexts VALUES (?,?,?,?,?,?,?,?)',(f"selective:{run['id']}:individual-navigation-challenge",'DIRECT_VIDEO_ENRICHMENT',command['query'],stamp,command['type'],safe.encoded(pre),safe.encoded(post_health),safe.encoded(source)))


def pause(c):
    migrate(c)
    value=direct(c)
    if value['status']!='PAUSED':
        value={'status':'PAUSED','reason':REASON,'paused_at':safe.now(),'scope':'individual video navigation workflow risk; no absolute target causality','resume_requires':'new explicit human authorization'}
        safe.put(c,'direct_video_enrichment',value)
    # Do not interrupt/kill a live reader. Prevent any pending direct job from
    # opening a target after the pause; no browser or security state is changed.
    c.execute("UPDATE bridge_commands SET status='FAILED',detail='DIRECT_VIDEO_ENRICHMENT_PAUSED',updated_at=? WHERE type IN ('READ_VIDEO_DETAIL','READ_COMMENTS_SAMPLE','READ_CREATOR_PROFILE') AND status='PENDING'",(safe.now(),))
    preserve_contexts(c)
    return status(c)


def history(c):
    return [{**dict(r),'pre_health':json.loads(r['pre_health_json']),'post_health':json.loads(r['post_health_json']),'source':json.loads(r['source_json'])} for r in c.execute('SELECT * FROM navigation_challenge_contexts ORDER BY timestamp')]
