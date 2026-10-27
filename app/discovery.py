"""Bounded, durable search-only discovery. No browser actions in the backend."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from fastapi import HTTPException

TERMINAL={'FINISHED','CANCELLED','FAILED'}
STOP_REASONS={'max_scrolls','max_videos','no_new_results','timeout','security_challenge','manual_stop','error'}


def configuration():
    return json.loads((Path(__file__).resolve().parents[1]/'config/discovery.json').read_text(encoding='utf-8'))


def now():
    return datetime.now(timezone.utc).isoformat()


def migrate(con):
    for statement in [
        '''CREATE TABLE IF NOT EXISTS discovery_sessions (
        id INTEGER PRIMARY KEY,command_id INTEGER NOT NULL UNIQUE,query TEXT NOT NULL,created_at TEXT NOT NULL,
        started_at TEXT,finished_at TEXT,scroll_count INTEGER NOT NULL DEFAULT 0,results_seen INTEGER NOT NULL DEFAULT 0,
        unique_videos INTEGER NOT NULL DEFAULT 0,new_videos INTEGER NOT NULL DEFAULT 0,duplicates INTEGER NOT NULL DEFAULT 0,
        visible_start INTEGER NOT NULL DEFAULT 0,status TEXT NOT NULL,stop_reason TEXT,stagnant_cycles INTEGER NOT NULL DEFAULT 0,
        max_scrolls INTEGER NOT NULL,max_new_videos INTEGER NOT NULL,max_runtime INTEGER NOT NULL,
        discovery_version TEXT NOT NULL,document_token TEXT)''',
        '''CREATE TABLE IF NOT EXISTS discovery_session_videos (
        session_id INTEGER NOT NULL REFERENCES discovery_sessions(id),video_id INTEGER NOT NULL REFERENCES videos(id),
        first_iteration INTEGER NOT NULL,is_new INTEGER NOT NULL,PRIMARY KEY(session_id,video_id))''',
        '''CREATE TABLE IF NOT EXISTS discovery_steps (
        session_id INTEGER NOT NULL REFERENCES discovery_sessions(id),scroll_iteration INTEGER NOT NULL,
        capture_id TEXT NOT NULL,payload_hash TEXT NOT NULL,new_links_detected INTEGER NOT NULL,duplicates_seen INTEGER NOT NULL,
        total_visible INTEGER NOT NULL,total_unique_session INTEGER NOT NULL,dom_card_count INTEGER NOT NULL,observed_at TEXT NOT NULL,
        PRIMARY KEY(session_id,scroll_iteration))''',
        '''CREATE TABLE IF NOT EXISTS video_enrichment_queue (
        video_id INTEGER PRIMARY KEY REFERENCES videos(id),needs_detail INTEGER NOT NULL DEFAULT 1,
        needs_comments INTEGER NOT NULL DEFAULT 1,needs_creator INTEGER NOT NULL DEFAULT 1,
        needs_product_detection INTEGER NOT NULL DEFAULT 1,enrichment_priority INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,updated_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS product_video_detection_state (
        video_id INTEGER PRIMARY KEY REFERENCES videos(id),detected_at TEXT NOT NULL,vocabulary_version TEXT NOT NULL)''',
    ]:
        con.execute(statement)
    if 'dom_stagnant_cycles' not in {r['name'] for r in con.execute('PRAGMA table_info(discovery_sessions)')}:
        con.execute('ALTER TABLE discovery_sessions ADD COLUMN dom_stagnant_cycles INTEGER NOT NULL DEFAULT 0')
    if 'stop_detail' not in {r['name'] for r in con.execute('PRAGMA table_info(discovery_sessions)')}:
        con.execute('ALTER TABLE discovery_sessions ADD COLUMN stop_detail TEXT')
    for column,kind in [('scroll_target','TEXT'),('scroll_before','REAL'),('scroll_after','REAL')]:
        if column not in {r['name'] for r in con.execute('PRAGMA table_info(discovery_steps)')}:
            con.execute(f'ALTER TABLE discovery_steps ADD COLUMN {column} {kind}')
    for column in ('first_search_query','latest_search_query'):
        if column not in {r['name'] for r in con.execute('PRAGMA table_info(videos)')}:
            con.execute(f'ALTER TABLE videos ADD COLUMN {column} TEXT')
    for column,kind in [('visible_position','INTEGER'),('global_position_estimate','INTEGER'),('scroll_iteration','INTEGER NOT NULL DEFAULT 0')]:
        if column not in {r['name'] for r in con.execute('PRAGMA table_info(search_observations)')}:
            con.execute(f'ALTER TABLE search_observations ADD COLUMN {column} {kind}')
    con.execute('UPDATE search_observations SET visible_position=search_position WHERE visible_position IS NULL AND search_position IS NOT NULL')
    con.execute('''UPDATE videos SET first_search_query=COALESCE(first_search_query,
        (SELECT search_query FROM search_observations WHERE video_id=videos.id ORDER BY observed_at,id LIMIT 1)),
        latest_search_query=COALESCE(latest_search_query,
        (SELECT search_query FROM search_observations WHERE video_id=videos.id ORDER BY observed_at DESC,id DESC LIMIT 1))
        WHERE first_search_query IS NULL OR latest_search_query IS NULL''')


def create_session(con, command_id, query, options):
    config=configuration()
    options={'max_scrolls':config['max_scrolls'],'max_new_videos':config['max_new_videos'],'max_runtime':config['max_runtime_seconds'],**(options or {})}
    con.execute('''INSERT OR IGNORE INTO discovery_sessions(command_id,query,created_at,status,max_scrolls,max_new_videos,max_runtime,discovery_version)
        SELECT ?,?,?,status,?,?,?,? FROM bridge_commands WHERE id=?''',
        (command_id,query,now(),options['max_scrolls'],options['max_new_videos'],options['max_runtime'],config['version'],command_id))


def finish(con, session, reason):
    if reason not in STOP_REASONS:
        raise HTTPException(422,'Invalid discovery stop reason')
    if session['status'] in TERMINAL:
        return
    status='CANCELLED' if reason=='manual_stop' else 'FAILED' if reason in ('security_challenge','error') else 'FINISHED'
    at=now()
    con.execute('UPDATE discovery_sessions SET status=?,stop_reason=?,finished_at=? WHERE id=?',(status,reason,at,session['id']))
    con.execute('UPDATE bridge_commands SET status=?,detail=?,updated_at=? WHERE id=?',
                ('FAILED' if status=='FAILED' else 'SUCCEEDED','Discovery stopped: '+reason,at,session['command_id']))


def session_for(con, command_id, extension_id=None):
    row=con.execute('SELECT s.*,b.extension_id,b.status AS command_status FROM discovery_sessions s JOIN bridge_commands b ON b.id=s.command_id WHERE s.command_id=?',(command_id,)).fetchone()
    if row is None or (extension_id is not None and row['extension_id']!=extension_id):
        raise HTTPException(404,'Discovery session not found for this Companion')
    return dict(row)


def control(con, command_id, extension_id):
    session=session_for(con,command_id,extension_id)
    if session['status'] not in TERMINAL and session['started_at']:
        if (datetime.now(timezone.utc)-datetime.fromisoformat(session['started_at'])).total_seconds()>=session['max_runtime']:
            finish(con,session,'timeout');session=session_for(con,command_id,extension_id)
    step=con.execute('SELECT max(scroll_iteration) FROM discovery_steps WHERE session_id=?',(session['id'],)).fetchone()[0]
    return {**session,'next_iteration':0 if step is None else step+1,
            'terminal':session['status'] in TERMINAL,
            'max_unique_videos':configuration()['max_unique_videos']}


def ingest_step(con, command_id, payload):
    from .observations import save_capture
    session=session_for(con,command_id,payload['extension_id'])
    iteration=payload['scroll_iteration']
    fingerprint=hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    previous=con.execute('SELECT * FROM discovery_steps WHERE session_id=? AND scroll_iteration=?',(session['id'],iteration)).fetchone()
    if previous:
        if previous['payload_hash']!=fingerprint:
            raise HTTPException(409,'Discovery retry changed its captured evidence')
        return control(con,command_id,payload['extension_id'])
    current=control(con,command_id,payload['extension_id'])
    if current['terminal']:
        raise HTTPException(409,'Discovery is already stopped')
    if session['command_status']!='DISPATCHED':
        raise HTTPException(409,'Discovery requires an active command')
    if iteration!=current['next_iteration'] or iteration>session['max_scrolls']:
        raise HTTPException(409,'Discovery viewport is out of sequence')
    capture=payload['capture']
    if capture['query']!=session['query']:
        raise HTTPException(409,'Discovery query changed')
    if session['document_token'] and session['document_token']!=payload['document_token']:
        raise HTTPException(409,'Discovery document changed')
    config=configuration();at=now()
    known={r[0] for r in con.execute('SELECT video_id FROM discovery_session_videos WHERE session_id=?',(session['id'],))}
    accepted=[];new_session=0;new_library=0;prospective_new=0
    for item in capture['results']:
        row=con.execute('SELECT id FROM videos WHERE video_id=? OR canonical_url=?',(item['video_id'],item['video_url'])).fetchone()
        if not row and session['new_videos']+prospective_new>=session['max_new_videos']:
            continue
        if (not row or row['id'] not in known) and len(known)+new_session>=config['max_unique_videos']:
            continue
        accepted.append(item)
        if not row:
            prospective_new+=1
        if not row or row['id'] not in known:
            new_session+=1
    compact={**capture,'results':accepted,'results_count':len(accepted)}
    for item in accepted:
        item['card_snapshot']=None
        item['raw_visible_text']=(item.get('raw_visible_text') or '')[:2000] or None
    capture_id=f"discovery:{session['id']}:{iteration}"
    new_library,_=save_capture(con,compact,capture_id,at)
    for item in accepted:
        video=con.execute('SELECT id,first_seen_at FROM videos WHERE video_id=? OR canonical_url=?',(item['video_id'],item['video_url'])).fetchone()
        is_new=video['first_seen_at']==at
        con.execute('INSERT OR IGNORE INTO discovery_session_videos VALUES (?,?,?,?)',(session['id'],video['id'],iteration,int(is_new)))
        con.execute('UPDATE search_observations SET scroll_iteration=?,visible_position=search_position,global_position_estimate=NULL WHERE capture_id=? AND video_id=?',(iteration,capture_id,video['id']))
        if is_new:
            con.execute('INSERT OR IGNORE INTO video_enrichment_queue(video_id,created_at,updated_at) VALUES (?,?,?)',(video['id'],at,at))
    total=con.execute('SELECT count(*) FROM discovery_session_videos WHERE session_id=?',(session['id'],)).fetchone()[0]
    duplicates=len(capture['results'])-new_session
    stagnant=session['stagnant_cycles']+1 if iteration>0 and new_session==0 else 0
    last_dom=con.execute('SELECT dom_card_count FROM discovery_steps WHERE session_id=? ORDER BY scroll_iteration DESC LIMIT 1',(session['id'],)).fetchone()
    dom_stagnant=session['dom_stagnant_cycles']+1 if iteration>0 and last_dom and payload['dom_card_count']<=last_dom[0] else 0
    con.execute('INSERT INTO discovery_steps(session_id,scroll_iteration,capture_id,payload_hash,new_links_detected,duplicates_seen,total_visible,total_unique_session,dom_card_count,observed_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
                (session['id'],iteration,capture_id,fingerprint,new_session,duplicates,len(capture['results']),total,payload['dom_card_count'],at))
    con.execute('UPDATE discovery_steps SET scroll_target=?,scroll_before=?,scroll_after=? WHERE session_id=? AND scroll_iteration=?',
                (payload.get('scroll_target'),payload.get('scroll_before'),payload.get('scroll_after'),session['id'],iteration))
    con.execute('''UPDATE discovery_sessions SET scroll_count=?,results_seen=results_seen+?,unique_videos=?,new_videos=new_videos+?,
        duplicates=duplicates+?,visible_start=CASE WHEN ?=0 THEN ? ELSE visible_start END,
        stagnant_cycles=?,dom_stagnant_cycles=?,document_token=COALESCE(document_token,?) WHERE id=?''',
        (iteration,len(capture['results']),total,new_library,duplicates,iteration,len(capture['results']),stagnant,dom_stagnant,payload['document_token'],session['id']))
    session=session_for(con,command_id)
    if total>=config['max_unique_videos'] or session['new_videos']>=session['max_new_videos']:
        finish(con,session,'max_videos')
    elif iteration>=session['max_scrolls']:
        finish(con,session,'max_scrolls')
    elif stagnant>=config['stagnant_cycles'] or dom_stagnant>=config['stagnant_cycles']:
        con.execute('UPDATE discovery_sessions SET stop_detail=? WHERE id=?',
                    ('no_new_ids' if stagnant>=config['stagnant_cycles'] else 'dom_not_growing',session['id']))
        finish(con,session,'no_new_results')
    return control(con,command_id,payload['extension_id'])


def sessions(con):
    rows=[]
    for row in con.execute('SELECT * FROM discovery_sessions ORDER BY id DESC LIMIT 20'):
        item=dict(row)
        item['steps']=[dict(r) for r in con.execute('SELECT * FROM discovery_steps WHERE session_id=? ORDER BY scroll_iteration',(row['id'],))]
        item['new_video_urls']=[r[0] for r in con.execute('SELECT v.canonical_url FROM discovery_session_videos s JOIN videos v ON v.id=s.video_id WHERE s.session_id=? AND s.is_new=1 ORDER BY s.first_iteration,v.id',(row['id'],))]
        rows.append(item)
    return rows


def enrichment_queue(con, session_id=None):
    from .product_vocabulary import version
    vocabulary_version=version(con)
    result=[]
    for row in con.execute('''SELECT q.*,v.canonical_url,v.video_id AS platform_video_id FROM video_enrichment_queue q
        JOIN videos v ON v.id=q.video_id WHERE (? IS NULL OR q.video_id IN
        (SELECT video_id FROM discovery_session_videos WHERE session_id=? AND is_new=1))
        ORDER BY enrichment_priority DESC,q.video_id LIMIT 100''',(session_id,session_id)):
        item=dict(row);vid=row['video_id']
        item['needs_detail']=not bool(con.execute('SELECT 1 FROM video_detail_observations WHERE video_id=?',(vid,)).fetchone())
        item['needs_comments']=not bool(con.execute('SELECT 1 FROM comment_samples WHERE video_id=?',(vid,)).fetchone())
        item['needs_creator']=not bool(con.execute('SELECT 1 FROM video_creators vc JOIN creator_profile_observations p ON p.creator_id=vc.creator_id WHERE vc.video_id=?',(vid,)).fetchone())
        item['needs_product_detection']=not bool(con.execute('''SELECT 1 FROM product_video_detection_state d WHERE video_id=? AND vocabulary_version=? AND detected_at>=
            COALESCE((SELECT max(observed_at) FROM video_detail_observations WHERE video_id=?),'') AND detected_at>=
            COALESCE((SELECT max(observed_at) FROM comment_samples WHERE video_id=?),'') AND detected_at>=
            COALESCE((SELECT max(p.observed_at) FROM video_creators vc JOIN creator_profile_observations p ON p.creator_id=vc.creator_id WHERE vc.video_id=?),'') AND detected_at>=
            COALESCE((SELECT max(observed_at) FROM search_observations WHERE video_id=?),'')''',(vid,vocabulary_version,vid,vid,vid,vid)).fetchone())
        con.execute('UPDATE video_enrichment_queue SET needs_detail=?,needs_comments=?,needs_creator=?,needs_product_detection=? WHERE video_id=?',
                    (int(item['needs_detail']),int(item['needs_comments']),int(item['needs_creator']),int(item['needs_product_detection']),vid))
        result.append(item)
    return result
