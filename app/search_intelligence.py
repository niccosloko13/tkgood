"""Search-observation-only projections. No browser, profile, comments or identity work."""
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime,timezone,timedelta
from urllib.parse import urlsplit
from . import safe_collection as safe,target_safety,trend_history as trend

VERSION='search-only-intelligence-v1'
METRICS={'views':'views','likes':'likes','comments_count':'comments','shares':'shares','favorites':'favorites'}


def migrate(c):
    c.execute('''CREATE TABLE IF NOT EXISTS search_only_intelligence (
      video_id INTEGER PRIMARY KEY,version TEXT NOT NULL,source_hash TEXT NOT NULL,
      computed_at TEXT NOT NULL,result_json TEXT NOT NULL)''')


def _stamp(value):
    try:
        d=datetime.fromisoformat(value.replace('Z','+00:00'))
        return d.astimezone(timezone.utc).isoformat() if d.tzinfo else None
    except (ValueError,AttributeError,TypeError):return None


def _numeric(fields,evidence,key):
    value=evidence.get(key,{}).get('value',fields.get(key))
    return value if isinstance(value,(int,float)) and not isinstance(value,bool) and value>=0 else None


def analyze(c,video_id,creator_index=None):
    from .category_intelligence import classify
    from .product_detection import extractProductCandidatePhrases
    from .intelligence_decisions import specificity
    raw=[dict(r) for r in c.execute('SELECT * FROM search_observations WHERE video_id=? ORDER BY observed_at,id',(video_id,))]
    if not raw:return None
    parsed=[(r,json.loads(r['fields_json']),json.loads(r['field_evidence_json'])) for r in raw]
    last,fields,evidence=parsed[-1];known={};sources={}
    for r,f,e in parsed:
        for key in ('video_url','creator_username','caption','thumbnail_url'):
            if f.get(key) is not None:known[key]=f[key];sources[key]={'source_id':f"search_observations:{r['id']}",'observed_at':r['observed_at']}
    queries=sorted({r['search_query'] for r in raw});captures=len({r['capture_id'] for r in raw});timed=[];rows=[]
    for r,f,e in parsed:
        at=_stamp(r['observed_at'])
        if not at:continue
        timed.append(at)
        metrics={output:_numeric(f,e,key) for key,output in METRICS.items()}
        rows.append({'id':f"search_observations:{r['id']}",'observed_at':at,'metrics':metrics,'coverage':{'creator':f.get('creator_username'),'creator_coverage':int(bool(f.get('creator_username')))},'source':'SEARCH_OBSERVATION','source_keys':[f"search_observations:{r['id']}"]})
    temporal=trend.summarize(rows,'VIDEO')
    velocity={key:value for key,value in temporal['velocity'].items() if key in METRICS.values()}
    ready=any(v['latest'] is not None for v in velocity.values())
    span=temporal['time_span_seconds'];density=(captures-len(queries))/captures if captures else None
    creator=known.get('creator_username');index=creator_index or _creator_index(c)
    recurrence=index.get(creator,{'videos':set(),'queries':set(),'captures':set()})
    creator_recurrence={k:len(v) for k,v in recurrence.items()}
    caption=known.get('caption');hashtags=re.findall(r'#[\w]+',caption or '')
    classification=classify([{'type':'caption','text':caption or '','source_entity':'search_observation','source_id':sources.get('caption',{}).get('source_id'),'url':known.get('video_url')},*[{'type':'search_query','text':q,'source_entity':'search_observation','source_id':None,'url':None} for q in queries]])
    phrases=sorted({p['raw_phrase'] for p in extractProductCandidatePhrases(caption or '') if specificity(p['raw_phrase'],caption or '',[])['specific']})
    confidence='SUPPORTED_LOCAL_HISTORY' if ready and len(set(timed))>=3 and (span or 0)>=3600 and len(queries)>=2 and creator and (density or 0)<=.8 and not any(temporal['conflicting_timestamps'].values()) else 'PARTIAL' if caption or rows else 'INSUFFICIENT'
    current_metrics={key:{'value':_numeric(fields,evidence,key),'raw_value':evidence.get(key,{}).get('raw_value'),'source_id':f"search_observations:{last['id']}",'observed_at':last['observed_at']} for key in METRICS}
    first=min(timed) if timed and len(timed)==len(raw) else None
    novelty=(datetime.now(timezone.utc)-datetime.fromisoformat(first)<=timedelta(hours=48)) if first else None
    relevant=classification['primary_category']=='home';blocked=target_safety.blocked(c,known.get('video_url',''))
    support=relevant or len(queries)>=2 or novelty or (current_metrics['views']['value'] or 0)>=10000 or ready
    if blocked:priority='LOW';why=['TARGET_PREVIOUSLY_BLOCKED']
    elif not caption or not creator:priority='INSUFFICIENT';why=['CAPTION_OR_OBSERVED_CREATOR_MISSING']
    elif phrases and support:priority='HIGH';why=['SPECIFIC_LITERAL_SEARCH_PRODUCT','SUPPORTING_LOCAL_SEARCH_EVIDENCE']
    elif phrases or relevant or len(queries)>=2:priority='MEDIUM';why=['RETAIN_FOR_LATER_SEARCH_COVERAGE']
    else:priority='LOW';why=['LIMITED_SPECIFIC_SEARCH_SUPPORT']
    if len(queries)>=2:why.append('QUERY_DIVERSITY: '+str(len(queries)))
    if captures>=2:why.append('RECAPTURES: '+str(captures)+'; not independent product proof')
    if relevant:why.append('HOME_CATEGORY_FROM_SEARCH_TEXT')
    if novelty:why.append('FIRST_OBSERVED_IN_SEARCH_WITHIN_48H')
    missing=lambda reason:{'status':'INSUFFICIENT','reason':reason,'evidence_ids':[]}
    dimensions={'identity':missing('NO_CONFIRMED_IDENTITY_FROM_SEARCH'),'purchase_intent':missing('COMMENT_TEXT_NOT_COLLECTED_BY_SEARCH'),'product_quality':missing('PRODUCT_USE_NOT_OBSERVABLE_IN_SEARCH'),'creator_signal':missing('CREATOR_PROFILE_NOT_COLLECTED_BY_SEARCH'),'creative_dna':missing('VIDEO_TIMING_AND_DEMONSTRATION_NOT_OBSERVED'),'commercial_readiness':missing('COMMERCIAL_EVIDENCE_NOT_COLLECTED'),'signal_quality':{'status':'partial' if rows else 'INSUFFICIENT','classification':confidence},'trend_readiness':{'status':'partial' if ready else 'INSUFFICIENT','classification':'LOCAL_DISPLAYED_COUNTER_DELTAS_AVAILABLE' if ready else 'INSUFFICIENT_NUMERIC_HISTORY'}}
    thumb=urlsplit(known.get('thumbnail_url') or '')
    return {'video_id':video_id,'version':VERSION,'basis':'search_observations only; no detail/comments/profile inputs','video_url':known.get('video_url'),'creator':creator,'caption':caption,'hashtags':hashtags,'field_sources':sources,'visible_metrics':current_metrics,'rank':last.get('visible_position') or last['search_position'],'query':last['search_query'],'observed_at':last['observed_at'],
      'thumbnail_metadata':{'available':bool(known.get('thumbnail_url')),'host':thumb.hostname,'source':sources.get('thumbnail_url'),'content_fetched':False},'recurrence':captures,'query_diversity':len(queries),'queries':queries,'creator_recurrence':creator_recurrence,'duplicate_density':density,'category_relevance':classification,'specificity':phrases,'novelty_48h':novelty,'velocity':velocity,'lifecycle':temporal['lifecycle'],'trend_readiness':dimensions['trend_readiness'],'early_signal_confidence':confidence,'dimensions':dimensions,'priority':priority,'why':why,
      'coverage':{'observations':len(raw),'timed_observations':len(rows),'ambiguous_timestamps':len(raw)-len(rows),'time_span_seconds':span,'conflicting_timestamps':temporal['conflicting_timestamps'],'source_ids':[f"search_observations:{r['id']}" for r in raw]},'limits':['LOCAL_COVERAGE_NOT_MARKET_TREND','DISPLAYED_COUNTER_DELTAS_NOT_DEMAND_VELOCITY','RECAPTURES_NOT_INDEPENDENT_CREATORS','NO_METRIC_CARRY_FORWARD','NO_COMMENT_INTENT_OR_PROFILE_QUALITY_INFERENCE']}


def _creator_index(c):
    index=defaultdict(lambda:{'videos':set(),'queries':set(),'captures':set()})
    for row in c.execute('SELECT video_id,search_query,capture_id,fields_json FROM search_observations'):
        creator=json.loads(row['fields_json']).get('creator_username')
        if creator:
            entry=index[creator];entry['videos'].add(row['video_id']);entry['queries'].add(row['search_query']);entry['captures'].add(row['capture_id'])
    return index


def rebuild(c):
    migrate(c);index=_creator_index(c);count=0
    for row in c.execute('SELECT DISTINCT video_id FROM search_observations').fetchall():
        result=analyze(c,row['video_id'],index);encoded=json.dumps(result,sort_keys=True,ensure_ascii=False);digest=hashlib.sha256(encoded.encode()).hexdigest()
        old=c.execute('SELECT source_hash FROM search_only_intelligence WHERE video_id=?',(row['video_id'],)).fetchone()
        if old and old['source_hash']==digest:continue
        c.execute('INSERT INTO search_only_intelligence VALUES (?,?,?,?,?) ON CONFLICT(video_id) DO UPDATE SET version=excluded.version,source_hash=excluded.source_hash,computed_at=excluded.computed_at,result_json=excluded.result_json',(row['video_id'],VERSION,digest,safe.now(),encoded));count+=1
    return count
