"""Bounded, deterministic occurrence comparisons. No browser, merge or Product entity."""
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
from itertools import combinations, product
import json
import re
from urllib.parse import urlsplit

from .candidate_semantics import configuration, normalize, product_signature, pairwise


def migrate(con):
    columns={r['name'] for r in con.execute('PRAGMA table_info(product_identity_pairs)')}
    additions={'id':'TEXT','candidate_a_id':'INTEGER','candidate_b_id':'INTEGER',
      'occurrence_a_id':'TEXT','occurrence_b_id':'TEXT','video_a_id':'INTEGER','video_b_id':'INTEGER',
      'identity_score':'REAL','semantic_result':'TEXT','reason':'TEXT','evidence_json':'TEXT',
      'resolver_version':'TEXT','created_at':'TEXT'}
    for name,kind in additions.items():
        if name not in columns:con.execute(f'ALTER TABLE product_identity_pairs ADD COLUMN {name} {kind}')
    con.execute('CREATE UNIQUE INDEX IF NOT EXISTS identity_resolver_id ON product_identity_pairs(id) WHERE id IS NOT NULL')
    con.execute('CREATE INDEX IF NOT EXISTS identity_resolver_candidates ON product_identity_pairs(resolver_version,candidate_a_id,candidate_b_id)')
    con.execute('INSERT OR IGNORE INTO schema_migrations(name) VALUES (?)',('product-identity-resolver-v1',))


def text_profile(occurrence,config):
    settings=config['resolver'];phrase=occurrence['phrase'];sig=product_signature(phrase,config)
    specific=set(sig['specific_tokens']);head=sig['head'];context=set();bundles=set()
    # Only configured modifiers adjacent to the observed phrase/head; never all caption words.
    for caption in occurrence.get('captions',[]):
        tokens=normalize(caption).split()
        for pos,token in enumerate(tokens):
            if head and token==head:
                radius=settings['context_window_tokens']
                window=tokens[max(0,pos-radius):pos+radius+1]
                context.update(set(window)&set(settings['context_modifiers']))
                bundles.update(re.findall(settings['bundle_pattern'],' '.join(window)))
    excluded=set(settings['context_modifiers'])|set(settings['domain_tokens'])|set(config['weak_modifiers'])|set(config['generic_heads'])|set(config['function_tokens'])
    brand={normalize(t) for t in re.findall(r'\b[A-Z][A-Za-z]+\b',phrase) if normalize(t) not in excluded}
    model={normalize(t) for t in re.findall(r'\b[A-Za-z0-9-]+\b',phrase) if re.search('[A-Za-z]',t) and re.search(r'\d',t)
      and not re.fullmatch(settings['dimension_pattern'],normalize(t)) and normalize(t) not in config['bundle_sequences']}
    dimensions={tuple(m) for m in re.findall(settings['dimension_pattern'],phrase.casefold())}
    # Repeated observations/comments do not multiply a feature.
    comments=set();support=[]
    for item in occurrence.get('comments',[]):
        text=item['text'] if isinstance(item,dict) else item;tokens=set(normalize(text).split())
        explicit=(head in tokens if head else False) or (normalize(phrase) and normalize(phrase) in normalize(text))
        found=tokens&(specific|context)
        if explicit and found:
            comments.update(found);support.append(item)
    return {'signature':sig,'specific':specific,'context':context,'brand_like':brand,'model_like':model,
      'dimensions':dimensions,'comment_tokens':comments,'supporting_comments':support,
      'number_tokens':sig['number_tokens'] or [n for bundle in sorted(bundles) for n in re.findall(r'\d+',bundle)],
      'caption_number_structures':sorted(bundles)}


def url_context(occurrence,config):
    listing=set();external=set();profile=set();classified=[]
    phrases={normalize(p) for p in [occurrence['phrase'],*occurrence.get('aliases',[])]}
    for item in occurrence.get('urls',[]):
        url=item.get('url') or item.get('source_url') or '';kind=item.get('url_type') or item.get('evidence_type')
        try:parsed=urlsplit(url)
        except ValueError:continue
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password:continue
        if kind=='creator_profile' or (parsed.hostname.lower() in ('www.tiktok.com','tiktok.com') and re.fullmatch(r'/@[^/]+/?',parsed.path)):
            profile.add(url);classification='creator_profile'
        else:
            external.add(url);classification='commercial_link' if kind in config['resolver']['commercial_evidence_types'] else 'context_link'
            bound=normalize(item.get('extracted_text')) in phrases
            excluded=parsed.hostname.lower() in config['excluded_listing_hosts']
            if kind in config['resolver']['commercial_evidence_types'] and bound and not excluded and re.search(config['listing_path_pattern'],parsed.path):
                listing.add(url);classification='exact_listing_url'
        classified.append({'url':url,'classification':classification,'source_id':item.get('id')})
    return {'listing':listing,'external':external,'profile':profile,'classified':classified}


def compare(a,b,config=None):
    config=config or configuration();settings=config['resolver'];weights=settings['weights']
    pa=text_profile(a,config);pb=text_profile(b,config);sa=pa['signature'];sb=pb['signature']
    ua=url_context(a,config);ub=url_context(b,config);features={}
    def feature(name,value,active,explanation,factor=1):
        features[name]={'value':value,'weight':weights[name],
          'contribution':round(weights[name]*factor,4) if active else 0,'explanation':explanation}
    shared=pa['specific']&pb['specific'];all_specific=pa['specific']|pb['specific']
    minimum=settings['minimum_specific_tokens'];specific_enough=len(shared)>=minimum
    exact=sa['normalized_phrase']==sb['normalized_phrase']
    feature('exact_normalized_phrase',exact,exact and specific_enough,'Exact observed phrase; generic/weak phrases receive no exact-identity points')
    feature('specific_token_overlap',sorted(shared),bool(shared),'Shared explicit non-generic phrase tokens',len(shared)/max(len(all_specific),1))
    modifiers=(pa['specific']|pa['context'])&(pb['specific']|pb['context'])
    feature('modifier_overlap',sorted(modifiers),bool(modifiers),'Shared phrase modifiers or configured adjacent caption modifiers',min(1,len(modifiers)/minimum))
    head=sa['head'] if sa['head']==sb['head'] else None
    feature('generic_head_overlap',head,False,'Generic heads provide concept context only: zero identity points')
    numbers_a=pa['number_tokens'];numbers_b=pb['number_tokens']
    numeric_conflict=bool(numbers_a and numbers_b and numbers_a!=numbers_b)
    feature('number_match',numbers_a if numbers_a==numbers_b else [],bool(numbers_a) and numbers_a==numbers_b,'Numbers preserved exactly, not stripped or inferred')
    dimensions=pa['dimensions']&pb['dimensions'];dimension_conflict=bool(pa['dimensions'] and pb['dimensions'] and not dimensions)
    feature('dimension_match',sorted(dimensions),bool(dimensions),'Explicit matching numeric dimensions and units; no unit inference')
    brands=pa['brand_like']&pb['brand_like'];models=pa['model_like']&pb['model_like']
    feature('brand_token_match',sorted(brands),len(brands)>=minimum,'Shared capitalized non-generic tokens; brand-like only, no brand assignment')
    feature('model_token_match',sorted(models),bool(models),'Shared explicitly written alphanumeric tokens; no model assignment')
    listings=ua['listing']&ub['listing']
    feature('commercial_url_match',sorted(listings),bool(listings),'Exactly identical public listing URL explicitly bound to each local phrase; never a profile URL')
    feature('shared_external_reference',sorted(ua['external']&ub['external']),False,'Unbound/external references are context only')
    comment_tokens=pa['comment_tokens']&pb['comment_tokens']
    feature('supporting_comment_phrase_overlap',sorted(comment_tokens),bool(comment_tokens),'Both occurrences have explicit specific comment support; capped once')
    weak=set(sa['weak_modifiers'])&set(sb['weak_modifiers'])
    feature('weak_modifier_overlap',sorted(weak),bool(weak),'Weak modifiers have bounded context weight only')
    conflicts=[]
    for group in settings['conflict_groups']:
        left=(pa['specific']|pa['context'])&set(group);right=(pb['specific']|pb['context'])&set(group)
        if left and right and not left&right:conflicts.append({'a':sorted(left),'b':sorted(right)})
    feature('modifier_conflict',conflicts,bool(conflicts),'Configured conflicting usage modifiers; heuristic negative evidence')
    feature('number_conflict',{'a':numbers_a,'b':numbers_b},numeric_conflict,'Both phrases explicitly carry different number structures')
    feature('dimension_conflict',{'a':sorted(pa['dimensions']),'b':sorted(pb['dimensions'])},dimension_conflict,'Both phrases carry incompatible explicit dimensions')
    model_conflict=bool(pa['model_like'] and pb['model_like'] and not models)
    feature('model_conflict',{'a':sorted(pa['model_like']),'b':sorted(pb['model_like'])},model_conflict,'Explicit differing alphanumeric tokens, not inferred models')
    unshared=bool(not shared and sa['normalized_phrase']!=sb['normalized_phrase'] and (pa['specific'] or pb['specific']))
    feature('unshared_specialization',unshared,unshared,'Unshared specialization is weak negative evidence, not proof of difference')
    negative=bool(conflicts or numeric_conflict or dimension_conflict or model_conflict)
    total=sum(f['contribution'] for f in features.values());score=max(0,min(settings['score_cap'],total))
    identity_anchor=bool(listings or (head and specific_enough))
    same_video=a.get('video_id') is not None and a.get('video_id')==b.get('video_id')
    caps=[]
    if not identity_anchor or negative or same_video:
        score=min(score,settings['insufficient_cap'])
        caps.append('Missing specific identity anchor, explicit conflict, or same-video context')
    result='possible_same_product' if score>=settings['possible_threshold'] else 'different' if negative and score<settings['different_below'] else 'insufficient'
    reason='; '.join([f"{name}: {f['contribution']:+g}" for name,f in features.items() if f['contribution']]) or 'Generic/concept overlap only; no discriminative identity evidence'
    return {'concept_similarity_score':round(pairwise(a['phrase'],b['phrase'],config=config)['concept_similarity_score']*100,4),
      'identity_score':round(score,4),'semantic_result':result,'reason':reason,'features':features,
      'raw_score':round(total,4),'caps':caps,'score_scale':'0-100 heuristic, not probability',
      'decision_thresholds':{'possible':settings['possible_threshold'],'different_below':settings['different_below'],'insufficient_cap':settings['insufficient_cap']},
      'caption_number_structures':{'a':pa['caption_number_structures'],'b':pb['caption_number_structures']},
      'occurrence_a':a,'occurrence_b':b,'url_classification_a':ua['classified'],'url_classification_b':ub['classified'],
      'supporting_comments_a':pa['supporting_comments'],'supporting_comments_b':pb['supporting_comments'],
      'resolver_version':settings['version'],'not_merged':True}


def occurrences(con,config=None):
    config=config or configuration();grouped={}
    for row in con.execute('''SELECT e.*,c.canonical_name FROM product_candidate_evidence e JOIN product_candidates c ON c.id=e.candidate_id
       WHERE e.video_id IS NOT NULL ORDER BY e.observed_at,e.id'''):
        e=dict(row);key=(e['candidate_id'],e['video_id'])
        grouped.setdefault(key,[]).append(e)
    output=[]
    for (cid,vid),evidence in sorted(grouped.items()):
        textual=[e for e in evidence if e['evidence_type'] in config['resolver']['identity_evidence_types'] and e['extracted_text']]
        if not textual:continue
        video=dict(con.execute('SELECT * FROM videos WHERE id=?',(vid,)).fetchone())
        creator=con.execute('SELECT c.username FROM creators c JOIN video_creators vc ON vc.creator_id=c.creator_id WHERE vc.video_id=?',(vid,)).fetchone()
        comments=[];seen_comments=set()
        for row in con.execute('SELECT id,text,author_username,sample_id FROM comment_observations WHERE video_id=? ORDER BY id',(vid,)):
            key=(normalize(row['author_username']),normalize(row['text']))
            if key not in seen_comments:comments.append(dict(row));seen_comments.add(key)
        phrases=sorted({e['extracted_text'] for e in textual})
        captions=list(dict.fromkeys(e['raw_text'] for e in evidence if e['evidence_type']=='caption' and e['raw_text']))
        # Use provenance-bound captions, never unrelated global candidate aliases.
        output.append({'id':f'{cid}:{vid}','candidate_id':cid,'candidate_name':textual[-1]['canonical_name'],'video_id':vid,
          'creator':creator[0] if creator else video.get('creator_username'),'video_url':video.get('canonical_url'),
          'phrase':textual[-1]['extracted_text'],'aliases':phrases,'captions':captions,'comments':comments,
          'urls':[{'id':e['id'],'url':e['source_url'],'evidence_type':e['evidence_type'],'extracted_text':e['extracted_text']} for e in evidence if e['evidence_type'] in ('profile_link','external_link','commercial_link','exact_listing_url')],
          'evidence_ids':[e['id'] for e in evidence]})
    return output


def generate_pairs(items,related=(),config=None):
    config=config or configuration();settings=config['resolver'];index=defaultdict(list);by_candidate=defaultdict(list)
    for i,item in enumerate(items):
        by_candidate[item['candidate_id']].append(i)
        keys={f"candidate:{item['candidate_id']}"}
        for phrase in [item['phrase'],*item.get('aliases',[])]:
            sig=product_signature(phrase,config);keys.update('specific:'+t for t in sig['specific_tokens'])
            tokens=sig['normalized_phrase'].split()
            for n in range(2,min(len(tokens),settings['max_ngram'])+1):
                for pos in range(len(tokens)-n+1):
                    # A phrase/head+modifier may link separate hypotheses; a bare generic head never does.
                    keys.add('phrase:'+' '.join(tokens[pos:pos+n]))
        for key in sorted(keys):index[key].append(i)
    pairs={};overflow=[]
    def add(a,b,reason):
        if a==b:return True
        key=tuple(sorted((a,b)))
        if key not in pairs and len(pairs)>=settings['max_pairs']:return False
        pairs.setdefault(key,set()).add(reason);return True
    for key,bucket in sorted(index.items()):
        if len(bucket)>settings['max_bucket_size']:overflow.append({'key':key,'size':len(bucket)});bucket=bucket[:settings['max_bucket_size']]
        for a,b in combinations(bucket,2):
            if not add(a,b,key):return pairs,{'truncated':True,'overflow_buckets':overflow}
    for ca,cb in sorted(set(related)):
        left=by_candidate[ca];right=by_candidate[cb]
        if max(len(left),len(right))>settings['max_bucket_size']:overflow.append({'key':f'related:{ca}:{cb}','size':max(len(left),len(right))})
        for a,b in product(left[:settings['max_bucket_size']],right[:settings['max_bucket_size']]):
            if not add(a,b,'related_candidate'):return pairs,{'truncated':True,'overflow_buckets':overflow}
    return pairs,{'truncated':bool(overflow),'overflow_buckets':overflow}


def resolve(con):
    config=configuration();migrate(con);items=occurrences(con,config)
    related={(r[0],r[1]) for r in con.execute('SELECT candidate_a,candidate_b FROM candidate_relationships')}
    pairs,diagnostics=generate_pairs(items,related,config);at=datetime.now(timezone.utc).isoformat();evaluated=[]
    for (ai,bi),reasons in sorted(pairs.items()):
        a,b=items[ai],items[bi]
        # Select strongest comparison from phrases actually observed in each occurrence.
        comparisons=[compare({**a,'phrase':pa},{**b,'phrase':pb},config) for pa in a['aliases'] for pb in b['aliases']]
        result=max(comparisons,key=lambda p:(p['identity_score'],p['semantic_result']=='different',p['concept_similarity_score']))
        result['generation_reasons']=sorted(reasons)
        key='resolver:'+config['resolver']['version']+':'+a['id']+':'+b['id'];identifier=hashlib.sha256(key.encode()).hexdigest()[:24]
        encoded=json.dumps(result,ensure_ascii=False,sort_keys=True)
        old=con.execute('SELECT evidence_json FROM product_identity_pairs WHERE pair_key=?',(key,)).fetchone()
        if not old or old['evidence_json']!=encoded:
            con.execute('''INSERT INTO product_identity_pairs(pair_key,candidate_a,candidate_b,video_a,video_b,concept_similarity_score,
              product_identity_score,eligible,details_json,version,updated_at,id,candidate_a_id,candidate_b_id,occurrence_a_id,occurrence_b_id,
              video_a_id,video_b_id,identity_score,semantic_result,reason,evidence_json,resolver_version,created_at)
              VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(pair_key) DO UPDATE SET
              concept_similarity_score=excluded.concept_similarity_score,product_identity_score=excluded.product_identity_score,
              details_json=excluded.details_json,updated_at=excluded.updated_at,identity_score=excluded.identity_score,
              semantic_result=excluded.semantic_result,reason=excluded.reason,evidence_json=excluded.evidence_json''',
              (key,a['candidate_id'],b['candidate_id'],a['video_id'],b['video_id'],result['concept_similarity_score'],result['identity_score']/100,
               int(result['semantic_result']=='possible_same_product'),encoded,config['resolver']['version'],at,identifier,
               a['candidate_id'],b['candidate_id'],a['id'],b['id'],a['video_id'],b['video_id'],result['identity_score'],result['semantic_result'],
               result['reason'],encoded,config['resolver']['version'],at))
        evaluated.append({'id':identifier,**result})
    return {'resolver_version':config['resolver']['version'],'pairs_evaluated':len(evaluated),
      **{status:sum(p['semantic_result']==status for p in evaluated) for status in ('different','insufficient','possible_same_product')},
      'generation':diagnostics,'pairs':evaluated,'possible_matches':[p for p in evaluated if p['semantic_result']=='possible_same_product'],
      'top_5':sorted(evaluated,key=lambda p:(-p['identity_score'],p['id']))[:5]}


def records(con,candidate_id=None):
    version=configuration()['resolver']['version']
    return [{**dict(r),'evidence':json.loads(r['evidence_json']),'not_merged':True} for r in con.execute('''SELECT * FROM product_identity_pairs
      WHERE resolver_version=? AND (? IS NULL OR candidate_a_id=? OR candidate_b_id=?) ORDER BY identity_score DESC,id''',
      (version,candidate_id,candidate_id,candidate_id))]
