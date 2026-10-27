"""Read-only local diagnostics. No network, inference service, labels or detection writes."""
from collections import Counter
import json
import re
from . import category_intelligence as ci, gold_set, product_detection as detector
from .candidate_gaps import unresolved_records

VERSION='offline-intelligence-v1'
GROUPS={'A':'missing_data','B':'generic_text','C':'possible_visual_product','D':'ambiguous_category',
        'E':'non_product_evidence','F':'possible_classifier_coverage_gap'}
# Audit cues only: never taxonomy, detector vocabulary, product names or Gold labels.
NOUN_CUES=r'\b(?:motion sensor lights|grater|juicer machine|ceiling fan|cookie press|colander|faucet filter|mosquito coil box|difusor|aromatizador|secador|rodinho|escova)\b'
FUNCTION_CUES=r'\b(?:slice|slices|chopping|stirring|squeeze|store eggs|store peppers|dry clothes|limpar|triture|clean kitchen|remove the stains)\b'
COMMERCIAL_CUES=r'\b(?:buy|price|shipping|link in bio|in bio|carrinho|tiktokshop|achadinhos|tiktokmademebuyit)\b'


def caption_kind(text):
    text=text or ''
    if not re.search(r'\w',text):return 'no_text'
    if re.search(NOUN_CUES,text,re.I):return 'descriptive'
    # A named phrase recognised by the existing detector is descriptive too.
    if detector.extractProductCandidatePhrases(text):return 'descriptive'
    return 'generic_or_functional'


def group_video(f):
    """Primary group is exclusive; tags retain overlapping diagnostic conditions."""
    tags=[]
    if not f['has_caption'] and not f['has_comments']:tags.append('A')
    if f['caption_kind']=='generic_or_functional':tags.append('B')
    if f['likely_product'] and f['has_thumbnail'] and f['caption_kind']!='descriptive':tags.append('C')
    if f['category_status']=='ambiguous':tags.append('D')
    # E requires explicit non-product evidence; absence of a match is not negative evidence.
    if f.get('explicit_non_product_evidence'):tags.append('E')
    if f['category_status']=='unclassified' and (f['caption_kind']=='descriptive' or f['has_candidate'] or f['has_unresolved']):tags.append('F')
    primary=next((g for g in ('D','E','F','A','C','B') if g in tags),'A')
    return {'primary_group':primary,'group_name':GROUPS[primary],'group_tags':tags or ['A']}


def visual_priority(f):
    reasons=[]
    for key in ('has_thumbnail','likely_product','has_candidate','has_unresolved'):
        if f[key]:reasons.append(key)
    if not f['has_candidate']:reasons.append('candidate_missing')
    if f['caption_kind']!='descriptive':reasons.append(f['caption_kind'])
    if f['comments_count']<30:reasons.append('comments_insufficient')
    if f['category_status'] in ('unclassified','ambiguous'):reasons.append('category_'+f['category_status'])
    if f['has_candidate']:return {'priority':None,'reasons':reasons,'eligible':False}
    if not f['has_thumbnail']:reasons.append('thumbnail_missing')
    high=(f['likely_product'] and f['has_thumbnail'] and f['caption_kind']!='descriptive' and
          f['comments_count']<30 and f['category_status'] in ('unclassified','ambiguous'))
    level='HIGH' if high else 'MEDIUM' if f['likely_product'] and f['has_thumbnail'] else 'LOW'
    return {'priority':level,'reasons':reasons,'eligible':True,
            'image_status':'reference_only_not_fetched' if f['has_thumbnail'] else 'missing'}


def fn_causes(f,review):
    causes=[]
    if f['has_unresolved']:causes.append('unknown_vocabulary')
    if f['caption_kind']=='no_text':causes.append('no_text')
    elif f['caption_kind']=='generic_or_functional':causes.append('generic_caption')
    if f['caption_kind']!='descriptive' and not f['has_unresolved']:causes.append('insufficient_text_evidence')
    if not f['has_detail'] or f['comments_count']<30:causes.append('missing_enrichment')
    notes=review.get('review_notes') or ''
    if (f['has_thumbnail'] and f['caption_kind']!='descriptive' and not f['has_unresolved']) or re.search('lens|visual|identificar',notes,re.I):
        causes.append('likely_visual_dependency')
    return {'causes':causes or ['other'],'primary_cause':(causes or ['other'])[0],
            'diagnostic_only':True,'human_fn_reason':review.get('fn_reason'),
            'human_notes':notes,'review_status_preserved':review['review_status']}


def phrase_suggestions(con):
    from .product_vocabulary import augment
    config=augment(detector.configuration(),con);items=[]
    for phrase in unresolved_records(con):
        extracted=detector.extractProductCandidatePhrases(phrase['raw_phrase'],config)
        reviews=phrase['reviews'];rejected=phrase['status']=='rejected' or bool(reviews and reviews[-1]['decision']=='rejected')
        items.append({'phrase_id':phrase['id'],'video_id':phrase['video_id'],'raw_phrase':phrase['raw_phrase'],
            'status':phrase['status'],'human_rejected':rejected,'reviews':reviews,'observations':phrase['observations'],
            'detector_matches':extracted,'blocker':'outside_approved_vocabulary' if not extracted else 'inspect_evidence_gate',
            'blocking_stage':'configured_product_patterns' if not extracted else 'requires_evidence_review',
            'vocabulary_version':config['vocabulary_version'],
            'mode':'reviewable_suggestion','reviewable':not rejected and phrase['status']=='pending',
            'automatic_candidate':False,'explanation':'Unresolved is not a rejection. Approval remains an explicit human vocabulary decision; precision impact is unmeasured.'})
    return items


def query_intelligence(con,inventory):
    queries={r[0] for r in con.execute('SELECT DISTINCT search_query FROM search_observations')}
    queries.update(r[0] for r in con.execute('SELECT DISTINCT search_query FROM search_captures'))
    queries.update(r[0] for r in con.execute('SELECT DISTINCT query FROM discovery_sessions'))
    queries.update(r[0] for r in con.execute("SELECT DISTINCT query FROM bridge_commands WHERE type IN ('SEARCH','READ_SEARCH_RESULTS','DISCOVER_MORE_RESULTS')"))
    result=[]
    for query in sorted(queries):
        observations=con.execute('SELECT video_id FROM search_observations WHERE search_query=?',(query,)).fetchall()
        ids={r[0] for r in observations};linked=[v for v in inventory if v['video_id'] in ids]
        captures=con.execute('SELECT count(*) FROM search_captures WHERE search_query=?',(query,)).fetchone()[0]
        n=len(observations);unique=len(ids)
        result.append({'query':query,'captures':captures,'total_seen':n,'unique_videos':unique,
            'repeat_appearances':n-unique,'duplicate_rate':(n-unique)/n if n else None,
            'unique_creators':len({v['creator'] for v in linked if v['creator']}),
            'candidates':len({c['id'] for v in linked for c in v['candidates']}),
            'videos_with_candidates':sum(bool(v['candidates']) for v in linked),
            'unresolved':sum(len(v['unresolved']) for v in linked),
            **{k:sum(v['category']['category_status']==k for v in linked) for k in ('classified','ambiguous','unclassified')},
            'candidate_rate':sum(bool(v['candidates']) for v in linked)/unique if unique else None,
            'observation_uniqueness_rate':unique/n if n else None,
            'definition':'observation-level repeat rate; not discovery-session known-video rate'})
    ranked=sorted([q for q in result if q['total_seen']],key=lambda q:(-(q['observation_uniqueness_rate'] or 0),-(q['candidate_rate'] or 0),q['query']))
    dist=Counter(v['category']['primary_category'] for v in inventory)
    under=[{'category':key,'classified_videos':dist[key]} for key in ci.config()['categories'] if dist[key]==0]
    return {'queries':result,'best_historical_queries':ranked,'low_value_queries':[q for q in ranked if q['duplicate_rate']>=.8 and not q['videos_with_candidates']],
            'comparison_supported':len(ranked)>1,'underexplored_categories':under,'planner':ci.plan(con),
            'session_metrics':ci.query_metrics(con),'execution':'blocked_by_security_stop'}


def audit(con):
    inventory=ci.library(con);gold=gold_set.listing(con);reviews={r['video_id']:r for r in gold['items']}
    items=[];classified=[]
    for v in inventory:
        vid=v['video_id'];row=con.execute('SELECT * FROM videos WHERE id=?',(vid,)).fetchone()
        samples=con.execute('SELECT id,signals_json FROM comment_samples WHERE video_id=? ORDER BY id DESC LIMIT 1',(vid,)).fetchone()
        signals=json.loads(samples['signals_json']) if samples else {}
        comments=con.execute('SELECT count(*) FROM comment_observations WHERE sample_id=?',(samples['id'],)).fetchone()[0] if samples else 0
        all_comments=con.execute('SELECT count(*) FROM comment_observations WHERE video_id=?',(vid,)).fetchone()[0]
        review=reviews.get(vid,{})
        caption=row['caption'];kind=caption_kind(caption)
        product_reasons=[]
        if v['candidates']:product_reasons.append('persisted_candidate')
        if v['unresolved']:product_reasons.append('persisted_unresolved_phrase')
        if kind=='descriptive':product_reasons.append('explicit_caption_noun_cue')
        if re.search(FUNCTION_CUES,caption or '',re.I):product_reasons.append('caption_product_function_cue')
        if review.get('human_reviewed') and review.get('product_presence')=='yes':product_reasons.append('existing_human_presence_review')
        f={'video_id':vid,'platform_video_id':v['platform_video_id'],'caption':caption,'creator':v['creator'],
           'has_caption':bool(caption and re.search(r'\w',caption)),'has_thumbnail':bool(row['thumbnail_url']),
           'has_comments':all_comments>0,'persisted_comments_count':all_comments,'comments_count':comments,'has_creator':bool(v['creator']),
           'has_unresolved':bool(v['unresolved']),'has_candidate':bool(v['candidates']),'has_query':bool(v['queries']),
           'source_queries':v['queries'],'has_detail':bool(con.execute('SELECT 1 FROM video_detail_observations WHERE video_id=?',(vid,)).fetchone()),
           'buy_signals':{'comment_buy_terms':signals.get('comments_with_buy_terms',0),
                          'caption_commercial_context':bool(re.search(COMMERCIAL_CUES,caption or '',re.I))},
           'caption_kind':kind,'likely_product':bool(product_reasons),'likely_product_reasons':product_reasons,
           'category_status':v['category']['category_status'],'category':v['category'],
           'candidates':v['candidates'],'unresolved':v['unresolved']}
        # No algorithm may turn lack of data into a negative product label.
        if review.get('human_reviewed') and review.get('product_presence')=='no':
            f['explicit_non_product_evidence']='existing_human_negative_presence_review'
        f.update(group_video(f));f['visual']=visual_priority(f)
        gap=con.execute('SELECT reason,explanation FROM product_detection_gaps WHERE video_id=? ORDER BY run_id DESC LIMIT 1',(vid,)).fetchone()
        f['persisted_detection_gap']=dict(gap) if gap else None
        items.append(f)
        if f['category_status']=='classified':
            sources=ci.sources_for(con,row);proof=v['category'].get('category_evidence',[])
            invalid=[p for p in proof if not any(all(p.get(k)==s.get(k) for k in ('type','text','source_entity','source_id','url')) for s in sources)]
            warnings=[]
            if not any(p['type'] in ('caption','hashtag','candidate') for p in proof):warnings.append('comment_or_unresolved_only')
            if v['category']['category_confidence']<.6:warnings.append('low_heuristic_confidence')
            if any(p['matched_term'] in ('limpeza','cleaning') for p in proof):warnings.append('broad_context_term')
            if v['category']['product_family']=='dispensers' and re.search('dish brush',caption or '',re.I):warnings.append('bathroom_subcategory_context_not_proven')
            if invalid:warnings.append('source_provenance_not_reproduced')
            classified.append({'video_id':vid,'caption':caption,**v['category'],'warnings':warnings,
                'invalid_evidence_count':len(invalid),'explanation':'Maximum configured source weight, not independent evidence count; category is not product identity.'})
    unclassified=[i for i in items if i['category_status']=='unclassified']
    queue=sorted([i for i in items if i['visual']['eligible']],key=lambda i:({'HIGH':0,'MEDIUM':1,'LOW':2}[i['visual']['priority']],i['video_id']))
    fn=[{'video_id':i['video_id'],'caption':i['caption'],'coverage':{k:i[k] for k in ('has_detail','comments_count','has_thumbnail','caption_kind')},
         **fn_causes(i,reviews[i['video_id']])} for i in items if reviews[i['video_id']]['benchmark_category']=='fn']
    counts=gold['filter_counts'];den=counts.get('tp',0)+counts.get('fn',0)
    return {'version':VERSION,'scope':'persisted_only','taxonomy':ci.config(),'items':items,'unclassified':unclassified,
        'unclassified_breakdown':{k:sum(i['primary_group']==k for i in unclassified) for k in GROUPS},'group_definitions':GROUPS,
        'category_audit':classified,'visual_queue':queue,'gold_fn_diagnostics':fn,
        'gold_progress':gold['progress'],'gold_filter_counts':counts,'gold_recall':counts.get('tp',0)/den if den else None,
        'phrase_suggestions':phrase_suggestions(con),
        'phrase_decision_audit':{'statuses':dict(Counter(r[0] for r in con.execute('SELECT status FROM unresolved_product_phrases'))),
            'vocabulary_reviews':con.execute('SELECT count(*) FROM product_vocabulary_reviews').fetchone()[0],
            'rejected_candidates':[dict(r) for r in con.execute("SELECT id,canonical_name,status,manual_status FROM product_candidates WHERE status='rejected' OR manual_status='rejected'")]},
        'query_intelligence':query_intelligence(con,inventory),
        'summary':{'videos':len(items),'classified':len(classified),'ambiguous':sum(i['category_status']=='ambiguous' for i in items),
            'unclassified':len(unclassified),'visual_queue':len(queue),
            'visual_priorities':dict(Counter(i['visual']['priority'] for i in queue)),
            'candidates':con.execute('SELECT count(*) FROM product_candidates').fetchone()[0],
            'unresolved':con.execute('SELECT count(*) FROM unresolved_product_phrases').fetchone()[0],
            'top_detection_gaps':dict(Counter(i['persisted_detection_gap']['reason'] for i in items if not i['has_candidate'] and i['persisted_detection_gap']))}}
