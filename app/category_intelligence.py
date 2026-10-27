"""Additive, auditable categories. Never a product identity decision."""
from collections import Counter,defaultdict
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
def config(name='category_taxonomy'):return json.loads((ROOT/'config'/f'{name}.json').read_text(encoding='utf-8'))
def now():return datetime.now(timezone.utc).isoformat()
def encoded(v):return json.dumps(v,ensure_ascii=False,sort_keys=True)

def migrate(con):
    for sql in [
        '''CREATE TABLE IF NOT EXISTS video_category_classifications (
        id INTEGER PRIMARY KEY,video_id INTEGER NOT NULL REFERENCES videos(id),primary_category TEXT,
        primary_subcategory TEXT,product_family TEXT,category_status TEXT NOT NULL,
        category_confidence REAL NOT NULL,category_evidence TEXT NOT NULL,classifier_version TEXT NOT NULL,
        taxonomy_version TEXT NOT NULL,input_hash TEXT NOT NULL,observed_at TEXT NOT NULL,
        UNIQUE(video_id,classifier_version,input_hash))''',
        '''CREATE TABLE IF NOT EXISTS human_category_reviews (
        id INTEGER PRIMARY KEY,video_id INTEGER NOT NULL REFERENCES videos(id),primary_category TEXT,
        primary_subcategory TEXT,product_family TEXT,notes TEXT NOT NULL,reviewed_at TEXT NOT NULL,
        taxonomy_version TEXT NOT NULL,prior_classification_id INTEGER)''',
        '''CREATE TABLE IF NOT EXISTS visual_product_evidence (
        id INTEGER PRIMARY KEY,video_id INTEGER NOT NULL REFERENCES videos(id),image_source TEXT NOT NULL,
        provider TEXT NOT NULL,possible_product_name TEXT,result_url TEXT,confidence REAL,
        review_status TEXT NOT NULL,observed_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS night_discovery_runs (
        id INTEGER PRIMARY KEY,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,status TEXT NOT NULL,
        stop_reason TEXT,stop_requested INTEGER NOT NULL DEFAULT 0,settings_json TEXT NOT NULL,
        checkpoint_json TEXT NOT NULL DEFAULT '{}')''',
        '''CREATE TABLE IF NOT EXISTS night_discovery_checkpoints (
        id INTEGER PRIMARY KEY,run_id INTEGER NOT NULL REFERENCES night_discovery_runs(id),
        session_id INTEGER,query TEXT NOT NULL,stage TEXT NOT NULL,data_json TEXT NOT NULL,created_at TEXT NOT NULL)''',
    ]:con.execute(sql)
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS one_running_night ON night_discovery_runs((1)) WHERE status='running'")

def classify(sources,settings=None):
    settings=settings or config();scores={};proof=defaultdict(list)
    for rule in settings['rules']:
        key=(rule['category'],rule['subcategory'],rule['family']);best=0
        for source in sources:
            for term in rule['terms']:
                if re.search(r'(?<!\w)'+re.escape(term)+r'(?!\w)',source['text'],re.I):
                    weight=settings['source_weights'][source['type']]
                    best=max(best,weight)
                    proof[key].append({**source,'matched_term':term,'weight':weight})
        if best:scores[key]=max(scores.get(key,0),best)
    ranked=sorted(scores,key=lambda k:(-scores[k],str(k)))
    eligible=[k for k in ranked if scores[k]>=settings['minimum_score']]
    evidence=[p for k in ranked for p in proof[k]]
    if not eligible:return {'primary_category':None,'primary_subcategory':None,'product_family':None,
        'category_status':'unclassified','category_confidence':0,'category_evidence':evidence}
    top=eligible[0];close=[k for k in eligible if scores[top]-scores[k]<settings['ambiguity_margin']]
    ambiguous=len({(k[0],k[1]) for k in close})>1
    return {'primary_category':None if ambiguous else top[0],'primary_subcategory':None if ambiguous else top[1],
        'product_family':None if ambiguous or len({k[2] for k in close})>1 else top[2], 'category_status':'ambiguous' if ambiguous else 'classified',
        'category_confidence':min(settings['confidence_cap'],scores[top]),'category_evidence':evidence}

def sources_for(con,v):
    vid=v['id'];sources=[]
    def add(kind,text,entity,key,url):
        if text:sources.append({'type':kind,'text':text,'source_entity':entity,'source_id':key,'url':url})
    add('caption',v['caption'],'video',vid,v['canonical_url'])
    for term in re.findall(r'#[\w]+',v['caption'] or ''):add('hashtag',term[1:].replace('_',' '),'video',vid,v['canonical_url'])
    for r in con.execute('SELECT id,text FROM comment_observations WHERE sample_id=(SELECT id FROM comment_samples WHERE video_id=? ORDER BY id DESC LIMIT 1)',(vid,)):
        add('comment',r['text'],'comment',r['id'],v['canonical_url'])
    for r in con.execute("SELECT id,extracted_text,source_url FROM product_candidate_evidence WHERE video_id=? AND evidence_type IN ('caption','hashtag','comment')",(vid,)):
        add('candidate',r['extracted_text'],'candidate_evidence',r['id'],r['source_url'])
    for r in con.execute('SELECT id,raw_phrase FROM unresolved_product_phrases WHERE video_id=?',(vid,)):
        add('unresolved',r['raw_phrase'],'unresolved_phrase',r['id'],v['canonical_url'])
    for r in con.execute('SELECT DISTINCT search_query FROM search_observations WHERE video_id=?',(vid,)):
        add('search_query',r['search_query'],'search_observation',vid,v['canonical_url'])
    r=con.execute('''SELECT p.id,p.fields_json FROM creator_profile_observations p JOIN video_creators vc
        ON vc.creator_id=p.creator_id WHERE vc.video_id=? ORDER BY p.id DESC LIMIT 1''',(vid,)).fetchone()
    if r:
        fields=json.loads(r['fields_json']);bio=fields.get('bio');bio=bio.get('value') if isinstance(bio,dict) else bio
        add('creator_context',bio,'creator_profile_observation',r['id'],None)
    # Repeated provenance is retained once; confidence uses max per rule, not raw count.
    return sorted({encoded(s):s for s in sources}.values(),key=encoded)

def classify_library(con,video_ids=None):
    settings=config();created=0
    for v in con.execute('SELECT * FROM videos ORDER BY id').fetchall():
        if video_ids is not None and v['id'] not in video_ids:continue
        sources=sources_for(con,v);fingerprint=hashlib.sha256(encoded({'sources':sources,'config':settings}).encode()).hexdigest()
        result=classify(sources,settings)
        created+=con.execute('''INSERT OR IGNORE INTO video_category_classifications
            (video_id,primary_category,primary_subcategory,product_family,category_status,category_confidence,
            category_evidence,classifier_version,taxonomy_version,input_hash,observed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
            (v['id'],result['primary_category'],result['primary_subcategory'],result['product_family'],result['category_status'],
             result['category_confidence'],encoded(result['category_evidence']),settings['classifier_version'],settings['version'],fingerprint,now())).rowcount
    return {'classifications_created':created}

def library(con,filters=None):
    filters=filters or {};items=[]
    weights=config('discovery_intelligence')['enrichment_weights']
    for v in con.execute('SELECT * FROM videos ORDER BY id DESC').fetchall():
        vid=v['id'];auto=con.execute('SELECT * FROM video_category_classifications WHERE video_id=? ORDER BY id DESC LIMIT 1',(vid,)).fetchone()
        human=con.execute('SELECT * FROM human_category_reviews WHERE video_id=? ORDER BY id DESC LIMIT 1',(vid,)).fetchone()
        category=dict(auto) if auto else {'category_status':'unclassified','primary_category':None,'primary_subcategory':None,'product_family':None,'category_confidence':0}
        if auto:category['category_evidence']=json.loads(category['category_evidence'])
        category['human_review']=dict(human) if human else None
        if human:
            category.update({k:human[k] for k in ('primary_category','primary_subcategory','product_family')})
            category['category_status']='classified' if human['primary_category'] else 'unclassified'
        candidates=[dict(r) for r in con.execute('''SELECT DISTINCT c.id,c.canonical_name,s.semantic_status FROM product_candidates c
            JOIN product_candidate_evidence e ON e.candidate_id=c.id LEFT JOIN candidate_semantics s ON s.candidate_id=c.id WHERE e.video_id=?''',(vid,))]
        unresolved=[dict(r) for r in con.execute('SELECT id,raw_phrase,status FROM unresolved_product_phrases WHERE video_id=?',(vid,))]
        queries=[r[0] for r in con.execute('SELECT DISTINCT search_query FROM search_observations WHERE video_id=? ORDER BY search_query',(vid,))]
        stages=[dict(r) for r in con.execute('SELECT step,status,reason FROM enrichment_stages WHERE video_id=?',(vid,))]
        status='complete' if len(stages)==5 and all(s['status'] in ('complete','not_applicable') for s in stages) else 'failed' if any(s['status']=='failed' for s in stages) else 'running' if any(s['status']=='running' for s in stages) else 'pending'
        sample=con.execute('SELECT signals_json FROM comment_samples WHERE video_id=? ORDER BY id DESC LIMIT 1',(vid,)).fetchone()
        signals=json.loads(sample[0]) if sample else {}
        flags={'category':category['category_status']=='classified','candidate_absent':not candidates,
            'caption_insufficient':not v['caption'] or len(v['caption'].split())<3,'unresolved':bool(unresolved),
            'comments_available':bool(sample),'thumbnail':bool(v['thumbnail_url']),'buy_intent':bool(signals.get('comments_with_buy_terms'))}
        item={'video_id':vid,'platform_video_id':v['video_id'],'video_url':v['canonical_url'],'caption':v['caption'],
            'creator':v['creator_username'],'category':category,'candidates':candidates,'unresolved':unresolved,'queries':queries,
            'enrichment_status':status,'enrichment_stages':stages,'enrichment_priority':sum(weights[k] for k,b in flags.items() if b),
            'enrichment_priority_reasons':[k for k,b in flags.items() if b]}
        checks={'category':category['primary_category'] or 'unclassified','subcategory':category['primary_subcategory'],'family':category['product_family'],
            'creator':item['creator'],'enrichment':status}
        if any(filters.get(k) and filters[k]!=val for k,val in checks.items()):continue
        if filters.get('query') and filters['query'] not in queries:continue
        if filters.get('has_product') and bool(candidates)!=(filters['has_product']=='yes'):continue
        if filters.get('unresolved') and bool(unresolved)!=(filters['unresolved']=='yes'):continue
        if filters.get('candidate_status') and not any(c['semantic_status']==filters['candidate_status'] for c in candidates):continue
        items.append(item)
    return items

def review_category(con,vid,data):
    settings=config();category=data.get('primary_category');sub=data.get('primary_subcategory')
    if not con.execute('SELECT 1 FROM videos WHERE id=?',(vid,)).fetchone():raise KeyError('Video not found')
    if category is not None and category not in settings['categories']:raise ValueError('Unknown category')
    if sub and (not category or sub not in settings['categories'][category].get('subcategories',{})):raise ValueError('Invalid subcategory')
    if not data.get('human_reviewed'):raise ValueError('Explicit human confirmation required')
    old=con.execute('SELECT id FROM video_category_classifications WHERE video_id=? ORDER BY id DESC LIMIT 1',(vid,)).fetchone()
    con.execute('''INSERT INTO human_category_reviews(video_id,primary_category,primary_subcategory,product_family,notes,
        reviewed_at,taxonomy_version,prior_classification_id) VALUES (?,?,?,?,?,?,?,?)''',
        (vid,category,sub,data.get('product_family'),data.get('notes',''),now(),settings['version'],old['id'] if old else None))
    return {'saved':True}

def query_metrics(con):
    settings=config('discovery_intelligence');result=[];items=library(con)
    known={q[0]:q for q in settings['queries']}
    for row in con.execute('SELECT DISTINCT query FROM discovery_sessions'):known.setdefault(row[0],[row[0],None,None,1])
    for query,category,sub,priority in known.values():
        sessions=[dict(r) for r in con.execute('SELECT * FROM discovery_sessions WHERE query=? ORDER BY id',(query,))]
        has_metrics=con.execute("SELECT 1 FROM sqlite_master WHERE name='safe_query_metrics'").fetchone()
        bounded=[dict(r) for r in con.execute("SELECT * FROM safe_query_metrics WHERE query=? AND status='SUCCEEDED' ORDER BY observed_at",(query,))] if has_metrics else []
        linked=[v for v in items if query in v['queries']];seen=sum(s['unique_videos'] for s in sessions)
        seen+=sum(s['results'] for s in bounded)
        new=sum(s['new_videos'] for s in sessions)+sum(s['new_videos'] for s in bounded);duplicates=max(0,seen-new)
        creators=len({v['creator'] for v in linked if v['creator']});n=len(linked)
        candidate=sum(bool(v['candidates']) for v in linked);classified=sum(v['category']['category_status']=='classified' for v in linked)
        result.append({'query':query,'category_hint':category,'subcategory_hint':sub,'priority':priority,
            'last_run':max([s['created_at'] for s in sessions]+[s['observed_at'] for s in bounded],default=None),'runs':len(sessions)+len(bounded),'videos_seen':seen,
            'new_videos':new,'duplicates':duplicates,'raw_duplicate_appearances':sum(s['duplicates'] for s in sessions),'unique_creators':creators,'attributed_videos':n,
            'candidate_count':candidate,'unresolved_count':sum(bool(v['unresolved']) for v in linked),
            'classified_count':classified,'unclassified_count':n-classified,
            'novelty_rate':new/seen if seen else None,'duplicate_rate':duplicates/seen if seen else None,
            'candidate_rate':candidate/n if n else None,'classified_rate':classified/n if n else None,
            'unique_creator_rate':creators/n if n else None})
    return result

def plan(con,at=None,excluded=()):
    at=at or datetime.now(timezone.utc);settings=config('discovery_intelligence')['planner'];choices=[]
    distribution=Counter((v['category']['primary_category'],v['category']['primary_subcategory']) for v in library(con))
    for q in query_metrics(con):
        if q['query'] in excluded:continue
        age=(at-datetime.fromisoformat(q['last_run'])).total_seconds() if q['last_run'] else None
        if age is not None and age<settings['repeat_cooldown_seconds']:continue
        terms={'base_priority':q['priority'],'novelty':(q['novelty_rate'] or 0)*settings['novelty_weight'],
            'duplicate_penalty':-(q['duplicate_rate'] or 0)*settings['duplicate_penalty'],
            'creators':(q['unique_creator_rate'] or 0)*settings['creator_weight'],
            'age':settings['age_weight'] if age is None else min(1,age/(3600*settings['age_cap_hours']))*settings['age_weight'],
            'underrepresented':settings['underrepresented_bonus']/(1+distribution[(q['category_hint'],q['subcategory_hint'])])}
        choices.append((sum(terms.values()),q,terms))
    if not choices:return {'selected_query':None,'reason':'All eligible queries are cooling down or already used'}
    _,q,terms=max(choices,key=lambda x:(x[0],x[1]['query']))
    return {'selected_query':q['query'],'reason':terms,'expected_category':q['category_hint'],
        'expected_subcategory':q['subcategory_hint'],'previous_performance':q,'planner_version':config('discovery_intelligence')['version']}


class VisualSearchProvider:
    """Deprecated compatibility shim. Use visual_identification.VisualSearchProvider."""
    def search(self,image_source):
        import warnings
        warnings.warn('Use visual_identification.VisualSearchProvider.identify',DeprecationWarning,stacklevel=2)
        from .visual_identification import GoogleLensAssistedProvider
        return GoogleLensAssistedProvider().identify({'image':image_source})
