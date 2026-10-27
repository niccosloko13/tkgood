"""Offline dimension read model. Identity records and human labels are never inputs to detection.

Identity approval is used only for commercial readiness. Candidate recurrence is
an unconfirmed local hint, never a same-product join.
"""
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from .comments import consumer_signals_v2

POLICY = Path('config/virality_quality.json')


def feature(status='insufficient', reason='NO_SUPPORTING_EVIDENCE', evidence=(), value=None):
    return dict(status=status, value=value, reason_codes=[reason], evidence_ids=list(evidence))


def dimension(status, classification, sample, sources, reasons, ids=(), **values):
    return dict(status=status, classification=classification, sample_size=sample,
                unique_sources=sources, confidence_status=status,
                coverage=values.pop('coverage', {'basis':'persisted local observations; not market coverage'}),
                reason_codes=list(reasons), reasons=list(reasons), evidence_ids=list(ids), **values)


def analyze(item, identity='UNRESOLVED'):
    policy=json.loads(POLICY.read_text(encoding='utf-8'))
    p=consumer_signals_v2(item.get('comments', [])); n=p['sample_size']; authors=p['unique_authors']
    ids=sorted({i for e in p['entries'] for i in e['evidence_ids']})
    comments=p['consumer_types']; caption=(item.get('caption') or '').casefold()
    caption_ids=[f"video:{item.get('video_id')}:caption"] if caption else []
    source_count=int(bool(caption))+int(bool(n))+int(bool(item.get('proposals')))
    purchase=dimension(p['status'], p['strength'], n, int(bool(n)),
        ['AUTHOR_DEDUPLICATED_INTENT','INTENT_IS_NOT_SALES'] if n else ['NO_COMMENT_SAMPLE'], p['evidence_ids'],
        coverage={'known_author_comments':p['known_author_comments'],'raw_observations':p['raw_observations']}, strength=p['strength'], **{k:p[k] for k in ('unique_authors','unique_intent_authors','intent_comments','intent_ratio','author_intent_ratio','intent_types')})
    duplicate=1-n/p['raw_observations'] if p['raw_observations'] else None
    creator=item.get('creator'); creators=item.get('confirmed_creator_count',int(bool(creator)))
    videos=item.get('confirmed_video_count',1)
    good_signal=videos>=policy['signal']['minimum_videos'] and creators>=policy['signal']['minimum_creators'] and authors>=policy['signal']['minimum_authors']
    dates=[]
    for text in item.get('observation_times',[])+[e['observed_at'] for e in p['entries'] if e.get('observed_at')]:
        try:dates.append(datetime.fromisoformat(text.replace('Z','+00:00')).timestamp())
        except (ValueError,TypeError):pass
    span=max(dates)-min(dates) if len(dates)>1 else None
    signal=dimension('measured' if good_signal else 'partial' if source_count else 'insufficient_data','STRONG' if good_signal else 'PARTIAL' if source_count else 'INSUFFICIENT_DATA',n,source_count,
        (['CROSS_CREATOR_LOCAL_COVERAGE'] if good_signal else ['SINGLE_VIDEO_DEPENDENCY' if videos==1 else 'LIMITED_VIDEO_COVERAGE','SINGLE_CREATOR_DEPENDENCY' if creators==1 else 'CREATOR_COVERAGE_LIMITED'])+['LOCAL_COVERAGE_ONLY'],ids,
        independent_videos=videos, independent_creators=creators or None,creator_diversity=creators/videos if creators>1 else None,
        commenter_diversity=authors/n if n else None,evidence_sources=[s for s,b in [('caption',caption),('comments',n),('visual_provider',item.get('proposals'))] if b],
        evidence_duration={'seconds':span,'basis':'capture timestamps, not consumer activity dates'},cross_source_agreement=None,duplicate_dependency=duplicate,single_creator_dependency=creators==1,single_video_dependency=videos==1)
    positive=set(comments['POSITIVE_REACTION']['authors']) | set(comments['USEFUL']['authors']) | set(comments['EASY_TO_USE']['authors'])
    negative=set(comments['NEGATIVE_REACTION']['authors'])
    complaint=set(comments['PRODUCT_COMPLAINT']['authors']) | set(comments['QUALITY_COMPLAINT']['authors'])
    qtypes=['DOES_NOT_WORK','BROKE','FAKE','USEFUL','EASY_TO_USE','HARD_TO_USE','PRODUCT_COMPLAINT','QUALITY_COMPLAINT','POSITIVE_REACTION','NEGATIVE_REACTION']
    # One video's self-reported comments cannot establish cross-creator product quality.
    qp=policy['quality'];quality_covered=n>=qp['minimum_sample'] and authors>=qp['minimum_authors'] and videos>=qp['minimum_videos'] and creators>=qp['minimum_creators']
    verdict='MIXED' if len(positive)>=qp['mixed_authors'] and len(negative|complaint)>=qp['mixed_authors'] else 'CONCERNING' if quality_covered and len(complaint)>=qp['complaint_authors'] and len(complaint)/authors>=qp['concerning_ratio'] else 'PROMISING' if quality_covered and len(positive)>=qp['positive_authors'] and not complaint else 'INSUFFICIENT_DATA'
    product=dimension('measured' if quality_covered else 'partial' if positive or negative or complaint else 'insufficient_data',verdict,n,int(bool(n)),
        ['SELF_REPORTED_COMMENTS','CROSS_CREATOR_QUALITY_COVERAGE' if quality_covered else 'INSUFFICIENT_QUALITY_COVERAGE','REACTION_IS_NOT_VERIFIED_USE'],ids,
        positive_unique_authors=len(positive),negative_unique_authors=len(negative),complaint_unique_authors=len(complaint),
        quality_issue_types={k:comments[k] for k in qtypes})
    visual={}; visual_ids=[]
    for proposal in item.get('proposals',[]):
        data=proposal.get('provider_payload_json') or {}
        if isinstance(data,str):data=json.loads(data)
        for key,value in data.get('data',{}).get('quality',{}).items():
            if value.get('status') in ('observed','partial'):
                visual[key]=value;visual_ids.append(f"visual:{proposal['id']}")
    def lexical(kind):return any(re.search(r'\b'+re.escape(term)+r'\b',caption) for term in policy['caption'][kind])
    def vf(key):
        v=visual.get(key)
        return feature(v['status'],'PERSISTED_VISUAL_PROVIDER_OBSERVATION',visual_ids,v.get('reason')) if v else feature()
    unknown=feature()
    repeat_features={key:feature() for key in ('multiple_use_cases','multiple_problem_angles','multiple_demo_angles','before_after_possible','comparison_possible','test_possible','reaction_possible','satisfying_demo_possible')}
    # Still-image assertions are potential, never evidence of timed creative execution.
    if visual.get('before_after_possible'):repeat_features['before_after_possible']=feature('partial','STILL_IMAGE_POTENTIAL_ONLY',visual_ids)
    if lexical('utility'):repeat_features['test_possible']=feature('partial','CAPTION_FUNCTION_CAN_BE_TESTED',caption_ids)
    for key,value in item.get('creative_observations',{}).items():
        if key in repeat_features and value.get('evidence_ids') and value.get('status') in ('observed','partial'):
            repeat_features[key]=value
    supported=sum(f['status']!='insufficient' for f in repeat_features.values())
    observed=sum(f['status']=='observed' for f in repeat_features.values())
    repeat=dimension('measured' if observed>=policy['repeatability']['high_observed_features'] else 'partial' if supported else 'insufficient_data','HIGH' if observed>=policy['repeatability']['high_observed_features'] else 'MEDIUM' if supported>=policy['repeatability']['medium_supported_features'] else 'LOW' if observed else 'INSUFFICIENT',supported,len(set(visual_ids+caption_ids)),
        ['CREATIVE_POSSIBILITIES_NOT_PERFORMANCE'] if supported else ['NO_CREATIVE_COVERAGE'],visual_ids+caption_ids,features=repeat_features)
    creative_fields={key:feature() for key in ('hook_type','problem_shown','solution_shown','demo_type','payoff_type','transformation_present','product_visible_early','video_length_when_known','cta_type','before_after','asmr_possible','satisfying_moment','repeatable_format','number_of_possible_angles')}
    if caption:
        creative_fields['hook_type']=feature('partial','CAPTION_NOT_OPENING_FRAME',caption_ids,'problem_solution' if lexical('problem') and lexical('solution') else 'caption_only')
    if lexical('cta'):creative_fields['cta_type']=feature('partial','CAPTION_CTA',caption_ids,'purchase_or_link')
    if item.get('video_duration') is not None:creative_fields['video_length_when_known']=feature('observed','PERSISTED_DURATION_METADATA',item.get('detail_ids',[]),item['video_duration'])
    creative_fields['solution_shown']=vf('demonstration_visibility')
    creative=dimension('partial' if caption or visual else 'insufficient_data','PARTIAL' if caption or visual else 'INSUFFICIENT_DATA',int(bool(caption))+int(bool(visual)),source_count,
        ['NO_TIMED_FRAME_ANALYSIS','CAPTION_AND_STILL_ONLY'],caption_ids+visual_ids,fields=creative_fields,repeatability=repeat)
    viral_features={key:feature() for key in ('problem_solution_clarity','visual_demonstration_strength','transformation_payoff','novelty','shareability','repeatability','purchase_intent_strength','hook_clarity','product_visibility','wow_factor','utility_clarity')}
    for target,source in [('problem_solution_clarity','problem_solution_clarity'),('visual_demonstration_strength','demonstration_visibility'),('product_visibility','product_visibility')]:viral_features[target]=vf(source)
    if lexical('utility'):viral_features['utility_clarity']=feature('partial','CAPTION_DESCRIBES_FUNCTION',caption_ids)
    if n:viral_features['purchase_intent_strength']=feature('observed' if p['status']=='measured' else 'partial','COMMENT_INTENT_NOT_VIRALITY',p['evidence_ids'],p['strength'])
    viral=dimension('partial' if caption or visual or n else 'insufficient_data','PARTIAL' if caption or visual or n else 'INSUFFICIENT_DATA',n,source_count,['NO_FINAL_VIRAL_SCORE','NO_SHAREABILITY_OR_TIMING_INFERENCE'],ids+visual_ids,features=viral_features)
    saturation=dimension('partial','LOCAL_EVIDENCE_ONLY',1,1,['CANDIDATE_RECURRENCE_NOT_SAME_PRODUCT','NOT_MARKET_SATURATION'],caption_ids,
        number_of_known_videos=videos,number_of_known_creators=creators or None,candidate_recurrence=[{'candidate_id':c.get('id'),'videos':c.get('recurrence')} for c in item.get('candidates',[])],same_product_occurrences=videos if videos>1 else None,query_recurrence=item.get('query_count'),duplicate_creator_dependence=creators==1)
    times=sorted(set(item.get('observation_times',[])))
    daily={}
    for entry in p['entries']:
        day=(entry.get('observed_at') or '')[:10]
        if not day:continue
        row=daily.setdefault(day,{'day':day,'comments_per_day':0,'purchase_intent_per_day':0})
        row['comments_per_day']+=1
        if set(entry['types']) & set(p['intent_types']):row['purchase_intent_per_day']+=1
    numeric=item.get('engagement_observations',[]);numeric_times=[]
    for row in numeric:
        try:numeric_times.append(datetime.fromisoformat(row['observed_at'].replace('Z','+00:00')).timestamp())
        except (ValueError,TypeError):pass
    ready_history=len(set(numeric_times))>=policy['trend']['minimum_observations'] and max(numeric_times)-min(numeric_times)>=policy['trend']['minimum_span_hours']*3600
    trend=dimension('measured' if ready_history else 'insufficient_data','READY_FOR_TREND_ANALYSIS' if ready_history else 'INSUFFICIENT_HISTORY',len(set(numeric_times)),1 if numeric_times else 0,['NUMERIC_OBSERVATION_HISTORY' if ready_history else 'NO_VALIDATED_LONGITUDINAL_ENGAGEMENT','OBSERVATION_DATES_NOT_PUBLICATION_DATES'],[f"detail:{r['id']}" for r in numeric],
        first_seen=item.get('first_seen'),last_seen=item.get('last_seen'),series=list(daily.values()),
        videos_per_day=None,unique_creators_per_day=None,engagement_observations=numeric,engagement_velocity=None,creator_acceleration=None,change_point=None)
    ready={'identity_ready':identity=='AUTO','purchase_intent_ready':p['status']=='measured' and p['strength']=='STRONG','product_quality_ready':quality_covered and verdict=='PROMISING',
        'visual_identity_ready':any(v.get('review_status')=='accepted' for v in item.get('proposals',[])), 'supplier_data_available':False,'price_data_available':False}
    research_ready=all(ready[k] for k in ('identity_ready','purchase_intent_ready','product_quality_ready'))
    commercial=dimension('measured' if research_ready else 'partial' if any(ready.values()) else 'insufficient_data','READY_FOR_SUPPLIER_DISCOVERY' if research_ready else 'PARTIAL' if any(ready.values()) else 'NOT_READY',n,source_count,
        ['READY_FOR_RESEARCH_NOT_SALES' if research_ready else 'READINESS_GAPS','NO_SUPPLIER_RESEARCH_PERFORMED'],p['evidence_ids'],**ready)
    dims=dict(purchase_intent=purchase,signal_quality=signal,viral_potential=viral,creative_dna=creative,product_quality=product,saturation=saturation,trend_readiness=trend,commercial_readiness=commercial)
    return dict(version=policy['version'],product_signal=['purchase_intent','signal_quality','product_quality','saturation','trend_readiness','commercial_readiness'],creative_signal=['creative_dna','viral_potential'],dimensions=dims,
        filters={'strong_purchase_intent':p['strength']=='STRONG','high_creative_repeatability':repeat['classification']=='HIGH','product_quality_concern':product['classification']=='CONCERNING','needs_more_data':any(d['status']!='measured' for d in dims.values()),'ready_for_supplier_discovery':commercial['classification']=='READY_FOR_SUPPLIER_DISCOVERY','review_identity':identity=='REVIEW'})


def for_video(con, vid, identity='UNRESOLVED'):
    from .intelligence_core import observation
    item=observation(con,vid)
    item['comments']=[dict(r) for r in con.execute('SELECT * FROM comment_observations WHERE video_id=? ORDER BY id',(vid,))]
    video=con.execute('SELECT * FROM videos WHERE id=?',(vid,)).fetchone()
    item.update(first_seen=video['first_seen_at'],last_seen=video['last_seen_at'],query_count=con.execute('SELECT count(DISTINCT search_query) FROM search_observations WHERE video_id=?',(vid,)).fetchone()[0],
        observation_times=[r[0] for r in con.execute('SELECT observed_at FROM video_detail_observations WHERE video_id=?',(vid,))])
    item['engagement_observations']=[]
    for detail in con.execute('SELECT id,observed_at,fields_json FROM video_detail_observations WHERE video_id=?',(vid,)):
        fields=json.loads(detail['fields_json']);metrics={}
        for key in ('views','likes','comments_count','shares','favorites'):
            value=fields.get(key)
            if isinstance(value,(int,float)) and not isinstance(value,bool) and value>=0:metrics[key]=value
        if metrics:item['engagement_observations'].append(dict(id=detail['id'],observed_at=detail['observed_at'],metrics=metrics))
        duration=fields.get('duration_seconds')
        if isinstance(duration,(int,float)) and not isinstance(duration,bool) and duration>0:item.update(video_duration=duration,detail_ids=[f"detail:{detail['id']}"])
    # Only approved entities can expand a product's evidence scope.
    peers=[r[0] for r in con.execute('SELECT DISTINCT video_id FROM intelligence_entity_observations WHERE product_id IN (SELECT product_id FROM intelligence_entity_observations WHERE video_id=?)',(vid,))]
    if peers:
        marks=','.join('?' for _ in peers)
        item['comments']=[dict(r) for r in con.execute(f'SELECT * FROM comment_observations WHERE video_id IN ({marks}) ORDER BY id',peers)]
        item['confirmed_video_count']=len(peers)
        item['confirmed_creator_count']=con.execute(f"SELECT count(DISTINCT lower(creator_username)) FROM videos WHERE id IN ({marks}) AND creator_username IS NOT NULL AND creator_username!=''",peers).fetchone()[0]
    return analyze(item,identity)


def persist(con, vid, result):
    con.execute('CREATE TABLE IF NOT EXISTS intelligence_dimension_snapshots (id INTEGER PRIMARY KEY,video_id INTEGER NOT NULL REFERENCES videos(id),version TEXT NOT NULL,input_hash TEXT NOT NULL,result_json TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,UNIQUE(video_id,version,input_hash))')
    encoded=json.dumps(result,sort_keys=True,ensure_ascii=False)
    digest=hashlib.sha256(encoded.encode()).hexdigest()
    con.execute('INSERT OR IGNORE INTO intelligence_dimension_snapshots(video_id,version,input_hash,result_json) VALUES (?,?,?,?)',(vid,result['version'],digest,encoded))
    return digest
