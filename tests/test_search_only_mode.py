import json
import pytest
from fastapi import HTTPException
from app import db,collection_mode as mode,search_intelligence as signals,safe_collection as safe
from app.observations import save_capture
from test_product_detection import library
from test_safe_collection import bridge,ready,capture,EXT


def test_pause_preserves_stop_and_prevents_all_direct_types(library):
 with db.connect() as c:
  safe.put(c,'browser_security_stop',{'reason':'CAPTCHA','observed_at':'original'})
  first=mode.pause(c);second=mode.pause(c)
  assert first==second and first['search_collection']=='BLOCKED'
  assert safe.state(c,'browser_security_stop')=={'reason':'CAPTCHA','observed_at':'original'}
 for kind in mode.DIRECT_TYPES:
  with pytest.raises(HTTPException,match='DIRECT_VIDEO_ENRICHMENT_PAUSED'):
   db.enqueue_command(kind,'https://www.tiktok.com/@maker/video/123',EXT)
 assert db.claim_command(EXT) is None


def test_paused_direct_keeps_proven_search_pipeline(library):
 with db.connect() as c:
  check=ready(c);mode.pause(c)
  assert mode.status(c)['search_collection']=='AVAILABLE'
  batch=safe.start(c,check,['home organization']);command=batch['command_id']
 assert db.claim_command(EXT)['id']==command
 assert db.finish_command(command,EXT,'SUCCEEDED','Bounded capture',capture())=='ok'
 assert db.finish_command(command,EXT,'SUCCEEDED','Bounded capture',capture())=='ok'
 with db.connect() as c:
  assert c.execute('SELECT snapshots FROM safe_collection_batches').fetchone()[0]==1
  assert c.execute("SELECT count(*) FROM search_observations WHERE capture_id=?",(f'command:{command}',)).fetchone()[0]==1
  assert mode.direct(c)['status']=='PAUSED'


def test_search_projection_ignores_enriched_library_and_is_idempotent(library):
 with db.connect() as c:
  for i in range(3):
   item=capture('home organization' if i<2 else 'kitchen gadgets')
   item['results'][0]['views_raw']=str(1000+100*i)
   save_capture(c,item,f'fixture:{i}',f'2026-10-25T0{i}:00:00+00:00')
  before=signals.analyze(c,1)
  assert before['recurrence']==3 and before['query_diversity']==2
  assert before['visible_metrics']['views']['value']==1200
  assert before['velocity']['views']['latest'] is not None
  assert before['dimensions']['purchase_intent']['status']=='INSUFFICIENT'
  c.execute("UPDATE videos SET caption='misleading enriched text',creator_username='@other'")
  assert signals.analyze(c,1)==before
  counts=[c.execute(f'SELECT count(*) FROM {t}').fetchone()[0] for t in ('videos','search_observations','trend_snapshots')]
  assert signals.rebuild(c)==1 and signals.rebuild(c)==0
  assert counts==[c.execute(f'SELECT count(*) FROM {t}').fetchone()[0] for t in ('videos','search_observations','trend_snapshots')]
  c.execute("UPDATE search_observations SET observed_at='2026-10-25T00:00:00'")
  after=signals.analyze(c,1)
  assert after['coverage']['timed_observations']==0
  assert after['trend_readiness']['status']=='INSUFFICIENT'
  assert after['novelty_48h'] is None


def test_missing_counters_are_not_reused(library):
 with db.connect() as c:
  save_capture(c,capture(),'fixture:old','2026-10-25T00:00:00+00:00')
  item=capture();item['results'][0].pop('views_raw')
  save_capture(c,item,'fixture:new','2026-10-25T01:00:00+00:00')
  assert signals.analyze(c,1)['visible_metrics']['views']['value'] is None

def test_pending_direct_is_cancelled_without_security_mutation(library):
 with db.connect() as c:
  now=safe.now()
  c.execute("INSERT INTO bridge_commands(created_at,updated_at,type,query,status,extension_id,options_json) VALUES (?,?,?,?,?,?,?)",(now,now,'READ_VIDEO_DETAIL','https://www.tiktok.com/@maker/video/123','PENDING',EXT,'{}'))
  mode.pause(c)
  row=c.execute('SELECT status,detail FROM bridge_commands').fetchone()
  assert tuple(row)==('FAILED','DIRECT_VIDEO_ENRICHMENT_PAUSED')
  assert safe.state(c,'browser_security_stop')=={}
  assert mode.history(c)==[]
  assert not c.execute('SELECT 1 FROM search_observations').fetchone()
