"""Observation → existing identity evidence → decision → approved entity.

Offline by construction: no bridge, browser, network, Gold or supplier imports.
Additive tables retain every decision/matching/review revision.
"""
import hashlib
import json
import time
from . import category_intelligence as category
from . import visual_identification as visual
from . import product_identity_resolver as resolver
from .candidate_semantics import product_signature, normalize
from .intelligence_decisions import decide, same_product, settings,specificity
from . import intelligence_jobs as jobs


def encoded(value):return json.dumps(value,sort_keys=True,ensure_ascii=False)
def fingerprint(value):return hashlib.sha256(encoded(value).encode()).hexdigest()


def migrate(con):
    jobs.migrate(con)
    con.executescript('''
    CREATE TABLE IF NOT EXISTS intelligence_embeddings (
      version TEXT NOT NULL,kind TEXT NOT NULL,sha256 TEXT NOT NULL,vector_json TEXT NOT NULL,
      observed_at TEXT NOT NULL,PRIMARY KEY(version,kind,sha256));
    CREATE TABLE IF NOT EXISTS intelligence_cache_stats(id INTEGER PRIMARY KEY CHECK(id=1),hits INTEGER NOT NULL);
    INSERT OR IGNORE INTO intelligence_cache_stats VALUES(1,0);
    CREATE TABLE IF NOT EXISTS intelligence_decisions (
      id INTEGER PRIMARY KEY,video_id INTEGER NOT NULL REFERENCES videos(id),input_hash TEXT NOT NULL,
      policy_version TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN ('AUTO','REVIEW','UNRESOLVED')),
      reason_code TEXT NOT NULL,name TEXT,result_json TEXT NOT NULL,evidence_json TEXT NOT NULL,
      created_at TEXT NOT NULL,UNIQUE(video_id,input_hash,policy_version));
    CREATE TABLE IF NOT EXISTS intelligence_entities (
      id TEXT PRIMARY KEY,canonical_name TEXT NOT NULL,decision_id INTEGER NOT NULL UNIQUE REFERENCES intelligence_decisions(id),
      approval TEXT NOT NULL CHECK(approval IN ('AUTO','human_confirmed')),created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS intelligence_entity_observations (
      decision_id INTEGER PRIMARY KEY REFERENCES intelligence_decisions(id),
      product_id TEXT NOT NULL REFERENCES intelligence_entities(id),video_id INTEGER NOT NULL REFERENCES videos(id));
    CREATE TABLE IF NOT EXISTS intelligence_matches (
      id INTEGER PRIMARY KEY,video_id INTEGER NOT NULL REFERENCES videos(id),product_id TEXT NOT NULL REFERENCES intelligence_entities(id),
      input_hash TEXT NOT NULL,similarity REAL,embedding_version TEXT NOT NULL,observed_at TEXT NOT NULL,
      result TEXT NOT NULL,evidence_json TEXT NOT NULL,UNIQUE(video_id,product_id,input_hash,embedding_version));
    CREATE TABLE IF NOT EXISTS intelligence_reviews (
      id INTEGER PRIMARY KEY,decision_id INTEGER NOT NULL UNIQUE REFERENCES intelligence_decisions(id),
      action TEXT NOT NULL,name TEXT,product_id TEXT,notes TEXT NOT NULL,observed_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS intelligence_retrievals (
      id INTEGER PRIMARY KEY,video_id INTEGER NOT NULL REFERENCES videos(id),input_hash TEXT NOT NULL,
      reference_id TEXT NOT NULL,reference_kind TEXT NOT NULL,similarity REAL NOT NULL,
      embedding_version TEXT NOT NULL,index_version TEXT NOT NULL,observed_at TEXT NOT NULL,source_json TEXT NOT NULL,
      UNIQUE(video_id,input_hash,reference_id,embedding_version,index_version));
    ''')


def observation(con,vid):
    item=next((v for v in category.library(con) if v['video_id']==vid),None)
    if item is None:raise KeyError('Video not found')
    image=visual.image_source(con,vid)
    # Current hash binding is mandatory; old image suggestions cannot leak forward.
    proposals=visual.proposals(con,vid,active_only=True)
    comments=[dict(r) for r in con.execute('SELECT id,text,author_username FROM comment_observations WHERE video_id=? ORDER BY id',(vid,))]
    for candidate in item['candidates']:
        candidate['recurrence']=con.execute('SELECT count(DISTINCT video_id) FROM product_candidate_evidence WHERE candidate_id=?',(candidate['id'],)).fetchone()[0]
    occurrences=[o for o in resolver.occurrences(con) if o['video_id']==vid]
    for p in proposals:
        # Adapt existing visual provenance to the existing resolver; never create a Candidate.
        occurrences.append({'id':'visual:'+str(p['id']),'video_id':vid,'phrase':p['possible_product_name'],
            'aliases':json.loads(p['aliases_json']),'captions':[item['caption']] if item['caption'] else [],
            'comments':comments,'urls':[{'url':w['url'],'evidence_type':'commercial_link','extracted_text':p['possible_product_name'],'id':w['id']}
                for w in p['web_evidence'] if w['possible_match'] and w['visual_compatible'] and not w['contradiction']],
            'evidence_ids':['visual:'+str(p['id'])]})
    return {'video_id':vid,'caption':item['caption'],'creator':item['creator'],
            'candidates':item['candidates'],'unresolved':item['unresolved'],'category':item['category'],
            'image':image,'proposals':proposals,
            'comments':comments,'occurrences':occurrences}


def evidence_for(item):
    from .comments import consumer_signals
    proposals=item['proposals']
    names=[]
    for p in proposals:
        n=p['hypothesis']['canonical_name_suggestion']
        if n and normalize(n) not in {normalize(x) for x in names}:names.append(n)
    text_names=[(c['canonical_name'],'candidate',c.get('recurrence',1)) for c in item['candidates']]
    text_names.extend((u['raw_phrase'],'unresolved',0) for u in item['unresolved'])
    specificity_rows=[{**specificity(n,item['caption'],item['comments'],r),'source':source} for n,source,r in text_names]
    ranked=sorted(specificity_rows,key=lambda r:(r['specific'],r['caption_literal_support'],r['compound_tokens'],r['comment_recurrence']),reverse=True)
    if not names:names=list(dict.fromkeys(r['phrase'] for r in ranked))
    name=names[0] if names else None
    conflicts=[]
    if len(names)>1 and len(proposals)>1:
        # Different observed names stay alternatives unless an explicit alias binds them.
        if not any(all(normalize(n) in {normalize(x) for x in json.loads(p['aliases_json'])+[p['possible_product_name'],p['hypothesis']['canonical_name_suggestion']]} for n in names) for p in proposals):conflicts.append('visual_names')
    if any('observed_contradiction_cap' in p['hypothesis']['reason'] for p in proposals):conflicts.append('contradiction')
    support=[p for p in proposals if normalize(name or '')==normalize(p['hypothesis']['canonical_name_suggestion'])
        and json.loads(p.get('provider_payload_json') or '{}').get('data',{}).get('assessment','identified')=='identified']
    visual_cross_checks=[json.loads(p.get('context_cross_check_json') or '{}') for p in proposals]
    if any(c.get('status')=='CONFLICT' for c in visual_cross_checks):conflicts.append('text_contradiction')
    signature=product_signature(name or '')
    text=next((r for r in ranked if normalize(r['phrase'])==normalize(name or '')),specificity(name or '',item['caption'],item['comments']))
    if text['contradicting_comment_ids'] or text['caption_contradiction']:conflicts.append('text_contradiction')
    caption_products=[r for r in ranked if r['specific'] and r['caption_literal_support'] and r['source']=='candidate']
    composition=len(caption_products)>1 and any(normalize(a['phrase']) not in normalize(b['phrase']) and normalize(b['phrase']) not in normalize(a['phrase']) for a in caption_products for b in caption_products)
    return {'name':name,'alternatives':names[1:],'visual_available':item['image']['status']=='available',
            'visual_supported':bool(support),'generic_text':not text['specific'] and (not name or visual.generic_name(name)),
            'specific_terms':signature['specific_tokens'],
            'specificity':text,'text_identity_specific':text['specific'] and (text['caption_literal_support'] or text['comment_recurrence']>0),
            'text_caption_supported':text['caption_literal_support'],'text_candidate_supported':text.get('source')=='candidate',
            'compatible_comment_authors':text['comment_authors'],'candidate_recurrence':text['candidate_recurrence'],'composition':composition,
            'visual_flow_status':'LENS_ASSISTED_REQUIRED' if item['image']['status']=='available' and not proposals and not text['caption_literal_support'] else 'NOT_REQUIRED' if text['specific'] and text['caption_literal_support'] else 'EVIDENCE_AVAILABLE' if proposals else 'VISUAL_UNAVAILABLE',
            'text_supported':text['caption_literal_support'] or text['comment_recurrence']>0 or any('literal_caption_support' in p['hypothesis']['reason'] or 'literal_comment_support_not_verified_identity' in p['hypothesis']['reason'] for p in support),
            'independent_listings':max((p['hypothesis']['independent_listing_sources'] for p in support),default=0),
            'consumer_signals':consumer_signals(item['comments']),
            'visual_provider_evidence':[{'evidence_id':p['id'],'provider':p['provider'],'model':p['provider_version'],
                'analysis':json.loads(p.get('provider_payload_json') or '{}'),'text_cross_check':json.loads(p.get('context_cross_check_json') or '{}'),
                'multimodal':json.loads(p.get('multimodal_json') or '{}')} for p in proposals],
            'lens_evidence':[p['id'] for p in proposals if p['provider']=='google_lens_assisted'],
            'web_evidence':[r for p in proposals for r in p['web_evidence']],
            'conflicts':conflicts,'source_ids':{'text':[c['id'] for c in item['candidates'] if normalize(c['canonical_name'])==normalize(name or '')], 'visual':[p['id'] for p in support],
              'comments':[c['id'] for c in item['comments']],
              'web':[r['id'] for p in support for r in p['web_evidence']]}}


def enqueue_library(con,with_embeddings=False):
    ids=[]
    for row in con.execute("SELECT id,payload_json FROM intelligence_jobs WHERE status='queued' AND job_type='identity'").fetchall():
        policy=json.loads(row['payload_json']).get('policy')
        if policy!=settings():
            con.execute("UPDATE intelligence_jobs SET status='superseded',reason_code='POLICY_SUPERSEDED' WHERE id=?",(row['id'],))
            con.execute('INSERT INTO intelligence_job_history(job_id,status,reason_code,observed_at) VALUES (?, ?, ?, ?)',(row['id'],'superseded','POLICY_SUPERSEDED',jobs.now()))
    for row in con.execute('SELECT id FROM videos ORDER BY id').fetchall():
        item=observation(con,row[0])
        payload=work_payload(con,item,with_embeddings)
        if with_embeddings:
            from .intelligence_embeddings import provider
            payload['embedding_version']=provider.version
        ids.append(jobs.enqueue(con,'identity',row[0],payload))
    return ids


def work_payload(con,item,with_embeddings=False):
    payload={'input_hash':fingerprint(item),'policy':settings(),'with_embeddings':with_embeddings,
             'entity_revision':con.execute('SELECT count(*) FROM intelligence_entities').fetchone()[0]}
    if with_embeddings:
        from .intelligence_index import ProductIndex
        metadata=ProductIndex().metadata()
        payload['index_source_hash']=metadata.get('source_hash') if metadata else None
    return payload


def evidence_changed(con,vid):
    """Lightweight event handler in the evidence transaction; never loads a model."""
    item=observation(con,vid)
    jid=jobs.enqueue(con,'identity',vid,work_payload(con,item))
    job=jobs.claim(con,embedding_mode=False,job_id=jid)
    if job:
        started=time.monotonic()
        result=identify(con,vid)
        jobs.finish(con,job,status=result['status'].lower(),reason=result['reason_code'],processing_ms=(time.monotonic()-started)*1000)
    return jid


def _approve(con,decision_id,name,approval,product_id=None):
    row=con.execute('SELECT * FROM intelligence_decisions WHERE id=?',(decision_id,)).fetchone()
    if not row:raise KeyError('Decision missing')
    if approval=='AUTO' and row['status']!='AUTO':raise ValueError('AUTO gate required')
    if approval=='human_confirmed' and not con.execute("SELECT 1 FROM intelligence_reviews WHERE decision_id=? AND action IN ('confirm','new_product')",(decision_id,)).fetchone():raise ValueError('Explicit human confirmation required')
    existing=con.execute('SELECT product_id FROM intelligence_entity_observations WHERE decision_id=?',(decision_id,)).fetchone()
    if existing:return existing[0]
    if product_id:
        if not con.execute('SELECT 1 FROM intelligence_entities WHERE id=?',(product_id,)).fetchone():raise ValueError('Unknown product')
    else:
        product_id='product-'+hashlib.sha256(str(decision_id).encode()).hexdigest()[:24]
        con.execute('INSERT OR IGNORE INTO intelligence_entities VALUES (?,?,?,?,?)',(product_id,name,decision_id,approval,jobs.now()))
    con.execute('INSERT INTO intelligence_entity_observations VALUES (?,?,?)',(decision_id,product_id,row['video_id']))
    return product_id


def identify(con,vid,with_embeddings=False):
    item=observation(con,vid); evidence=evidence_for(item)
    if not with_embeddings and con.execute('SELECT 1 FROM intelligence_entities e JOIN intelligence_decisions d ON d.id=e.decision_id WHERE d.video_id!=? LIMIT 1',(vid,)).fetchone():
        evidence['retrieval_conflict']=bool(evidence['visual_supported'])
    if with_embeddings:
        from .intelligence_embeddings import provider
        from .intelligence_index import ProductIndex
        metadata=ProductIndex().metadata()
        expected={r[0] for r in con.execute('SELECT id FROM intelligence_entities')}
        indexed=set(metadata['product_ids']) if metadata and metadata['embedding_version']==provider.version else set()
        evidence['retrieval_unavailable']=bool(expected-indexed)
        vector=None;text_vector=None
        if item['caption'] and item['caption'].strip():text_vector=provider.embed(con,'text',item['caption'])
        if item['image']['status']=='available':
            content=visual.image_bytes(con,vid)
            vector=provider.embed(con,'image',content[0])
        retrieved=ProductIndex().search(vector or text_vector,provider.version) if vector or text_vector else []
        evidence['retrieval']=retrieved
        match_evidence=[]
        for hit in retrieved:
            con.execute('''INSERT OR IGNORE INTO intelligence_retrievals(video_id,input_hash,reference_id,reference_kind,similarity,embedding_version,index_version,observed_at,source_json) VALUES (?,?,?,?,?,?,?,?,?)''',
                (vid,fingerprint(item),hit['reference_id'],hit['reference_kind'],hit['similarity'],hit['embedding_version'],hit['index_version'],hit['observed_at'],encoded(hit)))
            if hit['reference_kind']=='CANDIDATE_REFERENCE':
                match_evidence.append({**hit,'result':'insufficient','reason':'CANDIDATE_REFERENCE_IS_NOT_IDENTITY'})
                continue
            entity=con.execute('SELECT e.*,d.evidence_json FROM intelligence_entities e JOIN intelligence_decisions d ON d.id=e.decision_id WHERE e.id=?',(hit['product_id'],)).fetchone()
            if not entity:raise ValueError('Stale entity index')
            hit['product_name']=entity['canonical_name']
            reference=json.loads(entity['evidence_json'])['observation']
            if reference['video_id']==vid and reference['image'].get('sha256')==item['image'].get('sha256') and normalize(entity['canonical_name'])==normalize(evidence['name'] or ''):
                evidence['matched_product_id']=entity['id']
                continue  # Same observation is not independent corroboration or a conflict.
            comparisons=[resolver.compare(a,b) for a in item['occurrences'] for b in reference['occurrences'] if a['video_id']!=b['video_id']]
            best=max(comparisons,key=lambda x:x['identity_score']) if comparisons else None
            matched={**evidence,'resolver':best,'image_similarity':hit['similarity'] if vector and hit['embedding_kind']=='image' else None,
                     'text_similarity':None,'brand_model_match':False}
            # Image and text scores must refer to the same entity, not two nearest neighbours.
            reference_image=reference['image']
            if text_vector and reference.get('caption'):
                other=provider.embed(con,'text',reference['caption'])
                matched['text_similarity']=sum(a*b for a,b in zip(text_vector,other))
            if vector and reference_image.get('status')!='available':matched['image_similarity']=None
            # Existing resolver provides explicit brand/model features. Do not infer from cosine.
            if best:
                matched['brand_model_match']=any(f.get('value') and f.get('contribution',0)>0 for key,f in best.get('features',{}).items() if key in ('brand_token_match','model_token_match'))
                features=best.get('features',{})
                if features.get('model_conflict',{}).get('contribution',0)<0:matched['conflicts']=[*matched['conflicts'],'model']
                elif any(features.get(k,{}).get('contribution',0)<0 for k in ('modifier_conflict','dimension_conflict','number_conflict')):matched['conflicts']=[*matched['conflicts'],'variant']
            result=same_product(matched)
            if result in ('possible_same_product','same_product_likely') and normalize(entity['canonical_name']) not in {normalize(n) for n in [evidence['name'],*evidence['alternatives']] if n}:
                evidence['alternatives'].append(entity['canonical_name'])
            match_evidence.append({**hit,'result':result,'resolver':best})
            con.execute('''INSERT OR IGNORE INTO intelligence_matches(video_id,product_id,input_hash,similarity,embedding_version,observed_at,result,evidence_json) VALUES (?,?,?,?,?,?,?,?)''',
                (vid,hit['product_id'],fingerprint(item),hit['similarity'],hit['embedding_version'],hit['observed_at'],result,encoded(matched)))
        evidence['matches']=match_evidence
        same=[x for x in match_evidence if x['result']=='same_product_likely']
        same_ids={x['product_id'] for x in same}
        possible_ids={x['product_id'] for x in match_evidence if x['result']=='possible_same_product'}
        if len(same_ids)>1 or possible_ids-same_ids:evidence['retrieval_conflict']=True
        if same_ids:evidence['matched_product_id']=next(iter(same_ids)) if len(same_ids)==1 else None
    result=decide(evidence)
    payload={'observation':item,'signals':evidence}
    # Separate retrieval revision prevents overwriting earlier non-embedding decisions.
    digest=fingerprint({**payload,'signals':{**evidence,'retrieval':[{k:v for k,v in h.items() if k!='observed_at'} for h in evidence.get('retrieval',[])],
        'matches':[{k:v for k,v in h.items() if k!='observed_at'} for h in evidence.get('matches',[])]}})
    con.execute('''INSERT OR IGNORE INTO intelligence_decisions(video_id,input_hash,policy_version,status,reason_code,name,result_json,evidence_json,created_at)
      VALUES (?,?,?,?,?,?,?,?,?)''',(vid,digest,settings()['version'],result['status'],result['reason_code'],result['possible_product_name'],encoded(result),encoded(payload),jobs.now()))
    did=con.execute('SELECT id FROM intelligence_decisions WHERE video_id=? AND input_hash=? AND policy_version=?',(vid,digest,settings()['version'])).fetchone()[0]
    if result['status']=='AUTO':_approve(con,did,result['possible_product_name'],'AUTO',evidence.get('matched_product_id'))
    return {'id':did,'video_id':vid,**result}


def process(con,limit=None,with_embeddings=False):
    from .intelligence_embeddings import ResourceBusy,ModelUnavailable
    limit=min(limit or settings()['jobs']['batch_limit'],settings()['jobs']['batch_limit'])
    results=[]
    for _ in range(limit):
        job=jobs.claim(con,embedding_mode=with_embeddings)
        if not job:break
        con.commit()  # Publish ownership before potentially expensive local work.
        started=time.monotonic()
        try:
            if job['job_type']=='identity':
                result=identify(con,int(job['target']),json.loads(job['payload_json']).get('with_embeddings',with_embeddings))
                jobs.finish(con,job,status=result['status'].lower(),reason=result['reason_code'],processing_ms=(time.monotonic()-started)*1000)
                results.append(result)
            elif job['job_type']=='index_rebuild':
                result=rebuild_index(con);jobs.finish(con,job);results.append(result)
            else:
                item=observation(con,int(job['target']))
                from .intelligence_embeddings import provider
                if item['image']['status']!='available':jobs.finish(con,job,failure='INSUFFICIENT_DATA',reason='UNRESOLVED_NO_VISUAL')
                else:provider.embed(con,'image',visual.image_bytes(con,int(job['target']))[0]);jobs.finish(con,job)
        except ResourceBusy as exc:
            jobs.defer(con,job,str(exc))
            con.commit()
            break  # Pause the heavy lane; don't burn attempts on every waiting item.
        except ModelUnavailable as exc:jobs.finish(con,job,failure='INSUFFICIENT_DATA',reason='MODEL_UNAVAILABLE',error=str(exc))
        except (KeyError,ValueError,FileNotFoundError) as exc:jobs.finish(con,job,failure='PERMANENT',reason='INVALID_LOCAL_INPUT',error=str(exc))
        except Exception as exc:jobs.finish(con,job,failure='PERMANENT',reason='UNEXPECTED_LOCAL_ERROR',error=str(exc))
        con.commit()
    return results


def rebuild_index(con):
    from .intelligence_embeddings import provider,ResourceGovernor
    from .intelligence_index import ProductIndex
    index=ProductIndex()
    rows=con.execute('SELECT e.id,e.canonical_name,d.video_id,d.evidence_json FROM intelligence_entities e JOIN intelligence_decisions d ON d.id=e.decision_id ORDER BY e.id').fetchall()
    candidates=[dict(r) for r in con.execute('SELECT id,canonical_name FROM product_candidates ORDER BY id')]
    occurrences=[dict(r) for r in con.execute('SELECT o.*,e.canonical_name FROM intelligence_entity_observations o JOIN intelligence_entities e ON e.id=o.product_id ORDER BY o.decision_id')]
    source_hash=fingerprint({'entities':[{'id':r['id'],'name':r['canonical_name'],'approved_image':json.loads(r['evidence_json'])['observation']['image'],
                             'current_image':visual.image_source(con,r['video_id'])} for r in rows],'candidates':candidates,'confirmed_occurrences':occurrences})
    version=provider.version
    previous=index.metadata()
    if previous and previous['embedding_version']==version and previous.get('source_hash')==source_hash:return previous
    entries=[]
    for row in rows:
        # Only approved entities enter the product index; candidates and Gold never do.
        approved=json.loads(row['evidence_json'])['observation']['image']
        current=visual.image_source(con,row['video_id'])
        if current['status']=='available' and current['sha256']==approved.get('sha256'):
            entries.append({'reference_id':row['id'],'product_id':row['id'],'reference_kind':'PRODUCT_ENTITY','name':row['canonical_name'],'source':{'video_id':row['video_id']},'kind':'image','vector':provider.embed(con,'image',visual.image_bytes(con,row['video_id'])[0])})
        else:
            entries.append({'reference_id':row['id'],'product_id':row['id'],'reference_kind':'PRODUCT_ENTITY','name':row['canonical_name'],'source':{'video_id':row['video_id']},'kind':'text','vector':provider.embed(con,'text',row['canonical_name'])})
    for row in occurrences:
        entries.append({'reference_id':'occurrence:'+str(row['decision_id']),'product_id':row['product_id'],'reference_kind':'CONFIRMED_OCCURRENCE',
            'name':row['canonical_name'],'source':{'video_id':row['video_id'],'decision_id':row['decision_id']},'kind':'text','vector':provider.embed(con,'text',row['canonical_name'])})
    for row in candidates:
        entries.append({'reference_id':'candidate:'+str(row['id']),'product_id':None,'reference_kind':'CANDIDATE_REFERENCE',
            'name':row['canonical_name'],'source':{'candidate_id':row['id']},'kind':'text','vector':provider.embed(con,'text',row['canonical_name'])})
    if not entries:return index.rebuild([],version,source_hash=source_hash)
    with ResourceGovernor().reserve():return index.rebuild(entries,version,source_hash=source_hash)


def latest(con):
    return [dict(r) for r in con.execute('SELECT * FROM intelligence_decisions WHERE id IN (SELECT max(id) FROM intelligence_decisions GROUP BY video_id) ORDER BY video_id')]


def review(con,did,action,name=None,product_id=None,notes=''):
    if action not in ('confirm','new_product','uncertain'):raise ValueError('Invalid human action')
    row=con.execute('SELECT * FROM intelligence_decisions WHERE id=?',(did,)).fetchone()
    if not row or row['status']!='REVIEW':raise ValueError('Only REVIEW items can be reviewed')
    latest_id=con.execute('SELECT max(id) FROM intelligence_decisions WHERE video_id=?',(row['video_id'],)).fetchone()[0]
    payload=json.loads(row['evidence_json'])
    if latest_id!=did or fingerprint(observation(con,row['video_id']))!=fingerprint(payload['observation']):raise ValueError('Evidence changed; reprocess before review')
    choices=[payload['signals'].get('name'),*payload['signals'].get('alternatives',[])]
    if action=='confirm' and name not in choices:raise ValueError('Confirm an observed alternative')
    if action=='new_product' and not (name and name.strip()):raise ValueError('Human product name required')
    if product_id and product_id not in {x['product_id'] for x in payload['signals'].get('retrieval',[])}:raise ValueError('Confirm only a retrieved entity')
    prior=con.execute('SELECT * FROM intelligence_reviews WHERE decision_id=?',(did,)).fetchone()
    if prior:
        if (prior['action'],prior['name'],prior['product_id'],prior['notes'])!=(action,name,product_id,notes):raise ValueError('Review already recorded; preserved history')
        return dict(prior)
    con.execute('INSERT INTO intelligence_reviews(decision_id,action,name,product_id,notes,observed_at) VALUES (?,?,?,?,?,?)',(did,action,name,product_id,notes,jobs.now()))
    entity=_approve(con,did,name,'human_confirmed',product_id) if action!='uncertain' else None
    return {'decision_id':did,'human_action':action,'product_id':entity,'gold_changed':False,'candidate_changed':False}


def quality(item,result,consumer=None):
    from .comments import consumer_signals
    purchase=consumer if consumer is not None else consumer_signals(item['comments']);classes=purchase['consumer_classes']
    complaints=classes['PRODUCT_COMPLAINT']['count']+classes['QUALITY_COMPLAINT']['count']
    return {'identity_confidence':{'status':'measured' if result['status']=='AUTO' else 'partial' if result['status']=='REVIEW' else 'insufficient_data','value':None,'reason_code':result['reason_code']},
            'purchase_intent':purchase,
            'consumer_reaction':{'status':purchase['status'],'value':None,'classes':classes},
            'signal_quality':{'status':'measured' if purchase['sample_size']>=settings()['consumer']['minimum_sample'] else 'partial' if item['caption'] or item['comments'] else 'insufficient_data','value':None,
                              'unique_comments':purchase['sample_size'],'raw_observations':len(item['comments'])},
            'product_quality':{'status':'partial' if complaints else 'insufficient_data','value':None,'complaint_signals':complaints,
                               'evidence_ids':sorted(set(classes['PRODUCT_COMPLAINT']['evidence_ids']+classes['QUALITY_COMPLAINT']['evidence_ids']))},
            'commercial_readiness':{'status':'partial' if purchase['unique_purchase_intent_comments'] else 'insufficient_data','value':None,'purchase_signal_available':bool(purchase['unique_purchase_intent_comments'])},
            **{k:{'status':'insufficient_data','value':None} for k in ('viral_potential','saturation')}}


def overview(con):
    from .intelligence_embeddings import provider,ResourceGovernor
    from .intelligence_index import ProductIndex
    rows=latest(con);counts={k:sum(r['status']==k for r in rows) for k in ('AUTO','REVIEW','UNRESOLVED')}
    cards=[]
    for row in rows:
        payload=json.loads(row['evidence_json']);human=con.execute('SELECT action,name FROM intelligence_reviews WHERE decision_id=?',(row['id'],)).fetchone()
        state='AUTO' if human and human['action']!='uncertain' else 'UNRESOLVED' if human else row['status']
        cards.append({'id':row['id'],'video_id':row['video_id'],'product':human['name'] if human and human['name'] else row['name'],
                      'status':state,'reason_code':'HUMAN_CONFIRMED' if state=='AUTO' and human else row['reason_code'],
                      'alternatives':payload['signals'].get('alternatives',[]),'category':payload['observation']['category'],
                      'entity_options':[{'product_id':h['product_id'],'name':h.get('product_name')} for h in payload['signals'].get('matches',[]) if h['result'] in ('possible_same_product','same_product_likely')],
                      'evidence':payload['signals']['source_ids'],'quality':quality(payload['observation'],json.loads(row['result_json']),payload['signals'].get('consumer_signals')),
                      'visual_flow_status':payload['signals'].get('visual_flow_status','unknown'),
                      'trend':{'status':'insufficient_history','value':None},'technical':payload})
    from .intelligence_signals import for_video
    from .trend_history import for_video as trend_for_video,overview as trend_overview
    for card in cards:
        card['intelligence']=for_video(con,card['video_id'],card['status'])
        card['trend_history']=trend_for_video(con,card['video_id'])
    from .safe_collection import summary as collection_health
    return {'collection_health':collection_health(con),'counts':{k:sum(c['status']==k for c in cards) for k in counts},'items':cards,
            'review_queue':[c for c in cards if c['status']=='REVIEW'],
            'jobs':[dict(r) for r in con.execute('SELECT job_type,status,count(*) AS count,avg(processing_ms) AS avg_processing_ms FROM intelligence_jobs GROUP BY job_type,status')],
            'blocked_jobs':jobs.blocked_jobs(con),'embedding_cache_hits':con.execute('SELECT hits FROM intelligence_cache_stats WHERE id=1').fetchone()[0],
            'faiss_index':ProductIndex().metadata(),'model_loaded':provider.model is not None,'resource_state':ResourceGovernor().state(),
            'openclip':{'status':'ready' if con.execute("SELECT 1 FROM intelligence_embeddings WHERE kind='image' LIMIT 1").fetchone() else 'waiting',
                        'image_embeddings':con.execute("SELECT count(*) FROM intelligence_embeddings WHERE kind='image'").fetchone()[0],
                        'model_loaded':provider.model is not None,'last_inference':provider.last_inference},
            'purchase_intent_measured_items':sum(c['intelligence']['dimensions']['purchase_intent']['status']=='measured' for c in cards),
            'visual_identity':visual.visual_summary(con),
            'trend_history':trend_overview(con),'temporal_signals':temporal_signals(con)}


def temporal_signals(con):
    """Observation dates, not asserted publication dates or interpolated history."""
    from .comments import signals
    daily={}
    for r in con.execute('SELECT date(first_seen_at) AS day,count(*) AS videos,count(DISTINCT creator_username) AS creators FROM videos GROUP BY date(first_seen_at)'):
        daily[r['day']]={'day':r['day'],'videos_first_observed':r['videos'],'unique_creators_first_observed':r['creators'],
                         'comments_observed':None,'purchase_intent_observed':None,'engagement_observations':None}
    seen={}
    for r in con.execute('SELECT * FROM comment_observations ORDER BY observed_at,id'):
        key=(r['video_id'],normalize(r['author_username'] or ''),normalize(r['text']))
        if key not in seen:seen[key]=dict(r)
    grouped={}
    for r in seen.values():grouped.setdefault(r['observed_at'][:10],[]).append(r)
    for day,comments in grouped.items():
        item=daily.setdefault(day,{'day':day,'videos_first_observed':None,'unique_creators_first_observed':None,'engagement_observations':None})
        item['comments_observed']=len(comments);item['purchase_intent_observed']=signals(comments)['comments_with_buy_terms']
    for r in con.execute('SELECT date(observed_at) AS day,count(*) AS count FROM video_detail_observations GROUP BY date(observed_at)'):
        item=daily.setdefault(r['day'],{'day':r['day'],'videos_first_observed':None,'unique_creators_first_observed':None,'comments_observed':None,'purchase_intent_observed':None})
        item['engagement_observations']=r['count']
    bounds=con.execute('SELECT min(first_seen_at),max(last_seen_at) FROM videos').fetchone()
    return {'basis':'local observation timestamps; not publication/activity dates','first_seen':bounds[0],'last_seen':bounds[1],
            'series':[daily[k] for k in sorted(daily) if k],
            'topics':{'status':'insufficient_history','adapter':'future_bertopic'},
            'online_signals':{'status':'insufficient_history','adapter':'future_river'},
            'change_points':{'status':'insufficient_history','adapter':'future_ruptures'}}
