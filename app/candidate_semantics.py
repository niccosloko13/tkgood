"""Additive semantics: lexical recurrence is not physical-product identity.

Persisted text/explicit URL bindings only; never merges candidates or changes legacy scores.
"""
import hashlib
from itertools import combinations
import json
from pathlib import Path
import re
from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode


def configuration():
    return json.loads((Path(__file__).resolve().parents[1]/'config/product_identity.json').read_text(encoding='utf-8'))


def normalize(text):
    from .product_detection import normalize as conservative_normalize
    return conservative_normalize(text or '')


def product_signature(phrase,config=None):
    config=config or configuration();normalized=normalize(phrase);work=normalized
    for sequence,replacement in config['modifier_sequences'].items():
        work=re.sub(r'(?<!\w)'+re.escape(sequence)+r'(?!\w)',replacement,work)
    tokens=work.split();heads=config['generic_heads']
    head=next((t for t in reversed(tokens) if t in heads),None)
    generic=[t for t in tokens if t in heads]
    specific=[t for t in tokens if t not in heads and t not in config['weak_modifiers'] and t not in config['function_tokens'] and not t.isdigit()]
    weak=[t for t in tokens if t in config['weak_modifiers']]
    numbers=[t for t in normalized.split() if any(ch.isdigit() for ch in t)]
    bundles=[s for s in config['bundle_sequences'] if re.search(r'(?<!\w)'+re.escape(s)+r'(?!\w)',normalized)]
    weights=config['specificity']
    score=min(weights['maximum'],(weights['head_weight'] if head else 0)+len(set(specific))*weights['specific_modifier_weight']+
              sum(config['weak_modifiers'][t] for t in set(weak))+len(bundles)*weights['bundle_weight'])
    # Unknown single nouns are not made specific by the absence of vocabulary coverage.
    if not head:score=0
    score=round(score,4)
    level='high' if score>=weights['high_threshold'] else 'medium' if score>=weights['medium_threshold'] else 'low'
    return {'raw_phrase':phrase,'normalized_phrase':normalized,'head':head,'modifiers':[t for t in tokens if t!=head],
      'specific_tokens':sorted(set(specific)),'generic_tokens':sorted(set(generic)),
      'weak_modifiers':sorted(set(weak)),'number_tokens':numbers,'bundle_sequences':bundles,
      'phrase_specificity':score,'specificity_level':level,'version':config['version']}


def pairwise(a,b,aliases_a=(),aliases_b=(),bound_urls_a=(),bound_urls_b=(),config=None):
    config=config or configuration();sa=product_signature(a,config);sb=product_signature(b,config)
    ta=set(sa['normalized_phrase'].split());tb=set(sb['normalized_phrase'].split());shared=ta&tb
    same=sa['normalized_phrase']==sb['normalized_phrase']
    same_head=sa['head'] is not None and sa['head']==sb['head']
    if same:concept=config['concept']['same_phrase']
    elif same_head:concept=config['concept']['shared_head']+config['concept']['token_overlap_weight']*len(shared)/max(len(ta|tb),1)
    else:concept=config['concept']['different_head_overlap_weight']*len(shared)/max(len(ta|tb),1)
    specific=set(sa['specific_tokens'])&set(sb['specific_tokens']);settings=config['identity']
    numeric_compatible=sa['number_tokens']==sb['number_tokens']
    modifiers_compatible=set(sa['specific_tokens'])==set(sb['specific_tokens'])
    strong=min(sa['phrase_specificity'],sb['phrase_specificity'])>=settings['minimum_specificity']
    enough=len(specific)>=settings['minimum_shared_specific_modifiers']
    signals=[];identity=0
    if same and strong and enough and numeric_compatible:
        identity=settings['exact_specific_phrase'];signals.append({'type':'exact_specific_phrase','phrases':[a,b]})
    aliases=[]
    for raw in set(aliases_a)&set(aliases_b):
        sig=product_signature(raw,config)
        if sig['phrase_specificity']>=settings['minimum_specificity'] and len(sig['specific_tokens'])>=settings['minimum_shared_specific_modifiers']:
            aliases.append(raw)
    if aliases and same_head and numeric_compatible and modifiers_compatible:
        identity=max(identity,settings['specific_shared_alias']);signals.append({'type':'strong_shared_alias','aliases':sorted(aliases)})
    if identity and enough:
        identity+=settings['shared_modifiers'];signals.append({'type':'specific_modifiers_shared','tokens':sorted(specific)})
    urls=set(bound_urls_a)&set(bound_urls_b)
    if urls and same_head and numeric_compatible:
        identity=max(identity,settings['matching_bound_listing_url']);signals.append({'type':'matching_bound_commercial_url','urls':sorted(urls)})
    return {'concept_similarity_score':round(min(concept,config['concept']['cap']),4),'product_identity_score':round(min(identity,settings['cap']),4),
      'signature_a':sa,'signature_b':sb,'shared_specific_tokens':sorted(specific),'numeric_compatible':numeric_compatible,
      'identity_signals':signals,'reason':'Specific text/explicit bound listing signals' if signals else 'Insufficient physical identity evidence; shared generic/weak tokens are concept context only',
      'version':config['version']}


def migrate(con):
    con.execute('''CREATE TABLE IF NOT EXISTS candidate_semantics (
      candidate_id INTEGER PRIMARY KEY REFERENCES product_candidates(id),semantic_status TEXT NOT NULL
      CHECK(semantic_status IN ('observed','concept_recurring','possible_same_product','product_matched')),
      detection_confidence REAL NOT NULL,recurrence_confidence REAL NOT NULL,identity_confidence REAL NOT NULL,
      phrase_specificity REAL NOT NULL,details_json TEXT NOT NULL,fingerprint TEXT NOT NULL,version TEXT NOT NULL,updated_at TEXT NOT NULL)''')
    con.execute('''CREATE TABLE IF NOT EXISTS candidate_semantic_history (
      id INTEGER PRIMARY KEY,candidate_id INTEGER NOT NULL REFERENCES product_candidates(id),prior_semantic_status TEXT,
      semantic_status TEXT NOT NULL,legacy_status TEXT NOT NULL,legacy_confidence REAL NOT NULL,
      legacy_reason_json TEXT NOT NULL,semantic_snapshot_json TEXT NOT NULL,fingerprint TEXT NOT NULL,observed_at TEXT NOT NULL,
      UNIQUE(candidate_id,fingerprint))''')
    con.execute('''CREATE TABLE IF NOT EXISTS product_identity_pairs (
      pair_key TEXT PRIMARY KEY,candidate_a INTEGER NOT NULL REFERENCES product_candidates(id),candidate_b INTEGER NOT NULL REFERENCES product_candidates(id),
      video_a INTEGER REFERENCES videos(id),video_b INTEGER REFERENCES videos(id),concept_similarity_score REAL NOT NULL,
      product_identity_score REAL NOT NULL,eligible INTEGER NOT NULL,details_json TEXT NOT NULL,version TEXT NOT NULL,updated_at TEXT NOT NULL)''')
    con.execute('''CREATE TABLE IF NOT EXISTS product_identity_evidence (
      pair_key TEXT NOT NULL REFERENCES product_identity_pairs(pair_key),signal_type TEXT NOT NULL,
      evidence_json TEXT NOT NULL,version TEXT NOT NULL,observed_at TEXT NOT NULL,
      PRIMARY KEY(pair_key,signal_type,version))''')
    marker='product-identity-foundation-v1'
    if not con.execute('SELECT 1 FROM schema_migrations WHERE name=?',(marker,)).fetchone():
        refresh(con)
        con.execute('INSERT INTO schema_migrations VALUES (?)',(marker,))


def listing_urls(evidence,name,config):
    result=set()
    for e in evidence:
        # A profile URL, bio redirect or unbound commercial context is never a listing match.
        if e['evidence_type']!='external_link' or normalize(e.get('extracted_text'))!=normalize(name):continue
        try:u=urlsplit(e['source_url'] or '')
        except ValueError:continue
        if u.scheme!='https' or not u.hostname or u.hostname in config['excluded_listing_hosts'] or u.username or u.password:continue
        if not re.search(config['listing_path_pattern'],u.path):continue
        query=[(k,v) for k,v in parse_qsl(u.query,keep_blank_values=True) if not k.lower().startswith('utm_')]
        result.add(urlunsplit((u.scheme,u.netloc.lower(),u.path,urlencode(query),'')))
    return result


def refresh(con):
    from datetime import datetime,timezone
    config=configuration();at=datetime.now(timezone.utc).isoformat();candidates=[dict(r) for r in con.execute('SELECT * FROM product_candidates ORDER BY id')]
    candidates_by_id={c['id']:c for c in candidates};aliases={};pairs=[]
    for c in candidates:
        cid=c['id'];aliases[cid]=sorted({r[0] for r in con.execute('SELECT normalized_alias FROM product_candidate_aliases WHERE candidate_id=?',(cid,))})
        by_video={}
        for r in con.execute("SELECT * FROM product_candidate_evidence WHERE candidate_id=? ORDER BY id",(cid,)):
            e=dict(r)
            if e['video_id'] is not None:by_video.setdefault(e['video_id'],[]).append(e)
        for va,vb in combinations(sorted(by_video),2):
            # Require identity-bearing phrase evidence in each occurrence, not merely a profile link.
            if not all(any(e['evidence_type'] in ('caption','hashtag','video_metadata') for e in by_video[v]) for v in (va,vb)):continue
            phrases={v:sorted({e['extracted_text'] for e in by_video[v] if e['evidence_type'] in ('caption','hashtag','video_metadata') and e['extracted_text']}) for v in (va,vb)}
            if not all(phrases.values()):continue
            comparisons=[pairwise(a,b,phrases[va],phrases[vb],listing_urls(by_video[va],a,config),listing_urls(by_video[vb],b,config),config) for a in phrases[va] for b in phrases[vb]]
            detail=max(comparisons,key=lambda p:(p['product_identity_score'],p['concept_similarity_score']))
            creators=[]
            for vid in (va,vb):
                row=con.execute('SELECT c.username FROM creators c JOIN video_creators vc ON vc.creator_id=c.creator_id WHERE vc.video_id=?',(vid,)).fetchone()
                creators.append(normalize(row[0]) if row and row[0] else None)
            eligible=bool(all(creators) and len(set(creators))>=config['identity']['minimum_creators'] and len(by_video)>=config['identity']['minimum_videos'])
            detail.update(evidence_ids_a=[e['id'] for e in by_video[va]],evidence_ids_b=[e['id'] for e in by_video[vb]],creators=creators)
            pairs.append((f'occurrence:{cid}:{va}:{vb}',cid,cid,va,vb,eligible,detail))
    related={(r[0],r[1]) for r in con.execute('SELECT candidate_a,candidate_b FROM candidate_relationships')}
    for ca,cb in sorted(related):
        if ca not in candidates_by_id or cb not in candidates_by_id:continue
        detail=pairwise(candidates_by_id[ca]['normalized_name'],candidates_by_id[cb]['normalized_name'],aliases[ca],aliases[cb],config=config)
        pairs.append((f'candidate:{ca}:{cb}',ca,cb,None,None,False,detail))
    for key,ca,cb,va,vb,eligible,detail in pairs:
        encoded=json.dumps(detail,sort_keys=True,ensure_ascii=False)
        old=con.execute('SELECT details_json,eligible FROM product_identity_pairs WHERE pair_key=?',(key,)).fetchone()
        if old and old['details_json']==encoded and bool(old['eligible'])==eligible:continue
        con.execute('''INSERT INTO product_identity_pairs(pair_key,candidate_a,candidate_b,video_a,video_b,concept_similarity_score,
          product_identity_score,eligible,details_json,version,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(pair_key) DO UPDATE SET
          concept_similarity_score=excluded.concept_similarity_score,product_identity_score=excluded.product_identity_score,
          eligible=excluded.eligible,details_json=excluded.details_json,version=excluded.version,updated_at=excluded.updated_at''',
          (key,ca,cb,va,vb,detail['concept_similarity_score'],detail['product_identity_score'],int(eligible),encoded,config['version'],at))
        for signal in detail['identity_signals']:
            con.execute('INSERT OR IGNORE INTO product_identity_evidence VALUES (?,?,?,?,?)',(key,signal['type'],json.dumps(signal,sort_keys=True),config['version'],at))
    for c in candidates:
        cid=c['id'];summary=json.loads(c['summary_json']);videos=summary.get('independent_video_count',0);creators=summary.get('independent_creator_count',0)
        recurrent=videos>=config['recurrence']['minimum_videos'];settings=config['recurrence']
        recurrence=min(settings['cap'],(settings['second_video']+max(0,videos-2)*settings['additional_video'] if recurrent else 0)+
                       (settings['second_creator']+max(0,creators-2)*settings['additional_creator'] if recurrent and creators>=2 else 0))
        supported=[p for p in pairs if p[1]==cid and p[2]==cid and p[5]]
        identity=max((p[6]['product_identity_score'] for p in supported),default=0)
        possible=bool(recurrent and creators>=config['identity']['minimum_creators'] and identity>=config['identity']['possible_threshold'])
        status='possible_same_product' if possible else 'concept_recurring' if recurrent else 'observed'
        sig=product_signature(c['canonical_name'],config)
        payload={'semantic_status':status,'detection_confidence':summary.get('confidence_components',{}).get('base_identity',0),
          'recurrence_confidence':round(recurrence,4),'identity_confidence':round(identity,4),'phrase_specificity':sig['phrase_specificity'],
          'specificity_level':sig['specificity_level'],'product_signature':sig,'concept_recurring':recurrent,'possible_same_product':possible,
          'product_matched':False,'independent_video_count':videos,'independent_creator_count':creators,
          'recurrence_reason':{'independent_videos':videos,'independent_creators':creators,
            'components':{'video_support':round(settings['second_video']+max(0,videos-2)*settings['additional_video'],4) if recurrent else 0,
                          'creator_support':round(settings['second_creator']+max(0,creators-2)*settings['additional_creator'],4) if recurrent and creators>=2 else 0},
            'cap':settings['cap'],'formula':'Independent-source heuristic; not physical identity probability'},
          'identity_evidence_status':'possible_textual_match' if possible else 'insufficient',
          'identity_pair_keys':[p[0] for p in supported],'semantic_version':config['version']}
        encoded=json.dumps(payload,sort_keys=True,ensure_ascii=False);fingerprint=hashlib.sha256(encoded.encode()).hexdigest()
        old=con.execute('SELECT * FROM candidate_semantics WHERE candidate_id=?',(cid,)).fetchone()
        if old and old['fingerprint']==fingerprint:continue
        reason=json.dumps({'reason':'Split lexical recurrence from unconfirmed physical identity','legacy_corroboration_reason':summary.get('corroboration_reason')},sort_keys=True)
        con.execute('''INSERT OR IGNORE INTO candidate_semantic_history(candidate_id,prior_semantic_status,semantic_status,legacy_status,
          legacy_confidence,legacy_reason_json,semantic_snapshot_json,fingerprint,observed_at) VALUES (?,?,?,?,?,?,?,?,?)''',
          (cid,old['semantic_status'] if old else None,status,c['status'],c['confidence'],reason,encoded,fingerprint,at))
        con.execute('''INSERT INTO candidate_semantics VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(candidate_id) DO UPDATE SET
          semantic_status=excluded.semantic_status,detection_confidence=excluded.detection_confidence,recurrence_confidence=excluded.recurrence_confidence,
          identity_confidence=excluded.identity_confidence,phrase_specificity=excluded.phrase_specificity,details_json=excluded.details_json,
          fingerprint=excluded.fingerprint,version=excluded.version,updated_at=excluded.updated_at''',
          (cid,status,payload['detection_confidence'],payload['recurrence_confidence'],payload['identity_confidence'],sig['phrase_specificity'],encoded,fingerprint,config['version'],at))


def public_fields(con,cid):
    row=con.execute('SELECT * FROM candidate_semantics WHERE candidate_id=?',(cid,)).fetchone()
    if not row:return {}
    result=json.loads(row['details_json'])
    result['identity_pairs']=[{**dict(r),'details':json.loads(r['details_json'])} for r in con.execute("SELECT * FROM product_identity_pairs WHERE (candidate_a=? OR candidate_b=?) AND pair_key NOT LIKE 'resolver:%' ORDER BY pair_key",(cid,cid))]
    result['semantic_history']=[dict(r) for r in con.execute('SELECT * FROM candidate_semantic_history WHERE candidate_id=? ORDER BY id',(cid,))]
    return result
