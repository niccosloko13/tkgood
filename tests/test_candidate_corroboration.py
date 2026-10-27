import json
from copy import deepcopy

import pytest

from app import db
from app.product_detection import configuration, detect, records, summarize
from app.candidate_corroboration import lexical_relation, signature, relationships
from app.candidate_gaps import classify_gap, unresolved_records, review_phrase
from test_product_detection import library, seed
from test_capture import api, database


def add_video(con, caption, n, creator=1, username='@maker'):
    at='2026-10-21'
    vid=con.execute("INSERT INTO videos(source,video_id,canonical_url,creator_username,caption,first_seen_at,last_seen_at,field_evidence_json) VALUES ('tiktok',?,?,?,?,?,?,?)",
                    (str(n),f'https://www.tiktok.com/{username}/video/{n}',username,caption,at,at,'{}')).lastrowid
    if creator is not None:
        con.execute("INSERT INTO video_creators VALUES (?,?,?,'test')",(vid,creator,at))
    return vid


def evidence(con,cid,kind,vid=1,creator=1,author=None,text='portable blender',key=None):
    key=key or kind+str(vid)
    con.execute('''INSERT OR IGNORE INTO product_candidate_evidence(candidate_id,evidence_type,source_entity_type,source_entity_id,
        video_id,creator_id,commenter,source_url,raw_text,extracted_text,confidence,observed_at,extractor_version,dedup_key)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (cid,kind,'test',key,vid,creator,author,f'https://www.tiktok.com/@maker/video/{vid}',text,text,.5,'2026-10-21','test',str(cid)+key))


def test_same_video_context_one_group_and_no_confidence_inflation(library):
    with library.connect() as con:seed(con,'portable blender')
    with library.connect() as con:
        detect(con);cid=records(con)[0]['id']
        for i in range(10):
            evidence(con,cid,'caption',key='caption'+str(i))
        for kind in ['hashtag','profile_link','search_query']:
            evidence(con,cid,kind,text='home gadgets')
        summary=summarize(con,cid,configuration());item=records(con)[0]
    assert summary['evidence_count']==14
    assert summary['unique_evidence_groups']==1
    assert summary['unique_video_count']==1 and summary['independent_creator_count']==1
    assert item['confidence']==.42 and item['status']=='observed'
    assert summary['source_diversity_score']<=100


def test_repeated_search_captures_do_not_increase_diversity(library):
    with library.connect() as con:
        seed(con,'portable blender')
        con.execute("INSERT INTO search_observations(video_id,capture_id,search_query,observed_at,extractor_version,extraction_completeness,fields_json,field_evidence_json) VALUES (1,'capture:1','home gadgets','2026-10-21','test',1,?,'{}')",(json.dumps({'caption':'portable blender'}),))
    with library.connect() as con:detect(con);before=records(con)[0]
    with library.connect() as con:
        for i in range(2,12):
            con.execute("INSERT INTO search_observations(video_id,capture_id,search_query,observed_at,extractor_version,extraction_completeness,fields_json,field_evidence_json) VALUES (1,?,'home gadgets','2026-10-21','test',1,?,'{}')",('capture:'+str(i),json.dumps({'caption':'portable blender'})))
    with library.connect() as con:detect(con);after=records(con)[0]
    assert after['evidence_count']>before['evidence_count']
    assert len(after['search_capture_groups'])==11
    assert after['independent_search_observation_count']==1
    assert after['source_diversity_score']==before['source_diversity_score']
    assert after['confidence']==before['confidence']==.42


def test_same_creator_two_videos_is_not_two_creators(library):
    with library.connect() as con:
        seed(con,'portable blender');add_video(con,'portable blender',2)
    with library.connect() as con:
        detect(con);item=records(con)[0]
    assert item['unique_video_count']==2 and item['independent_creator_count']==1
    assert item['status']=='observed' and item['confidence']==.54


def test_two_creators_rule_A_and_explanation(library):
    with library.connect() as con:
        seed(con,'portable blender');seed(con,'Portable Blender',n=2,username='@other')
    with library.connect() as con:
        detect(con);item=records(con)[0]
    assert item['corroboration_rules_satisfied']==['A']
    assert item['status']=='corroborated' and item['confidence']==.64
    assert item['confidence_components']['base_identity']==.42
    assert item['confidence_components']['cross_video']==.12
    assert item['confidence_components']['cross_creator']==.10


def test_three_videos_unknown_creators_rule_C(library):
    with library.connect() as con:
        for n in range(1,4):add_video(con,'portable blender',n,creator=None,username='')
    with library.connect() as con:
        detect(con);item=records(con)[0]
    assert item['corroboration_rules_satisfied']==['C']
    assert item['independent_creator_count']==0 and item['unique_video_count']==3


def test_bio_repeated_across_videos_is_not_cross_video_support(library):
    with library.connect() as con:
        seed(con,'portable blender');add_video(con,None,2);add_video(con,None,3)
    with library.connect() as con:
        detect(con);cid=records(con)[0]['id']
        evidence(con,cid,'creator_bio',vid=2,key='bio2')
        evidence(con,cid,'creator_bio',vid=3,key='bio3')
        summarize(con,cid,configuration());item=records(con)[0]
    assert item['unique_video_count']==3 and item['independent_video_count']==1
    assert item['status']=='observed' and item['confidence']==.42
    assert item['unique_evidence_groups']==1


def test_creator_self_comments_are_context_and_handles_remain_distinct(library):
    with library.connect() as con:seed(con,'portable blender',username='@maker.one')
    with library.connect() as con:
        detect(con);cid=records(con)[0]['id']
        evidence(con,cid,'comment',author='@Maker.One',text='my portable blender',key='self')
        summarize(con,cid,configuration());item=records(con)[0]
        assert item['unique_commenter_count']==0 and item['unique_evidence_groups']==1
        assert item['confidence']==.42
        evidence(con,cid,'comment',author='@maker_one',text='another portable blender',key='other')
        summarize(con,cid,configuration());item=records(con)[0]
        assert item['unique_commenter_count']==1 and item['unique_evidence_groups']==2
        assert item['confidence']==.46


def test_rule_B_distinct_comments_and_diminishing_returns(library):
    with library.connect() as con:
        seed(con,'portable blender');add_video(con,'portable blender',2)
    with library.connect() as con:
        detect(con);cid=records(con)[0]['id']
        for i in range(20):evidence(con,cid,'comment',author='@buyer'+str(i),text='same blender comment',key='comment'+str(i))
        summarize(con,cid,configuration());item=records(con)[0]
        assert item['confidence_components']['supporting_comments']==.04
        assert item['status']=='observed'
        evidence(con,cid,'comment',author='@different',text='where can I buy this portable blender?',key='different')
        summarize(con,cid,configuration());item=records(con)[0]
        assert item['confidence_components']['supporting_comments']==.06
        assert item['status']=='corroborated' and item['corroboration_rules_satisfied']==['B']
        for i in range(30):evidence(con,cid,'comment',author='@different',text='different text '+str(i),key='extra'+str(i))
        summarize(con,cid,configuration());item=records(con)[0]
        assert item['confidence_components']['supporting_comments']==.06


def test_query_is_weak_context_never_identity(library):
    with library.connect() as con:seed(con,'portable blender')
    with library.connect() as con:
        detect(con);cid=records(con)[0]['id']
        evidence(con,cid,'search_query',text='home gadgets',key='generic')
        summarize(con,cid,configuration());assert records(con)[0]['confidence']==.42
        evidence(con,cid,'search_query',text='portable blender',key='specific')
        summarize(con,cid,configuration());item=records(con)[0]
        assert item['confidence']==.43 and item['status']=='observed'
        assert item['unique_evidence_groups']==1


@pytest.mark.parametrize('a,b',[
    ('dish brush','floor brush'),('mini brush','portable brush'),('tool','tool'),
    ('window cleaner 12','window cleaner 13'),('burger maker','soap maker'),('Ninja Blast 2 blender','Ninja Blast 3 blender')])
def test_generic_or_model_collision(a,b):
    assert lexical_relation(a,b,configuration()) is None


def test_signature_and_non_destructive_relationships(library):
    cfg=configuration()
    assert signature('3 in 1 Window Cleaner',cfg)=='window cleaner'
    assert signature('Ninja Blast 2 Blender',cfg)=='ninja blast 2 blender'
    assert lexical_relation('portable dryer','portable clothes dryer',cfg)
    # Expand the fixture's vocabulary only, never production vocabulary.
    from unittest.mock import patch
    cfg=deepcopy(cfg);cfg['product_patterns'].append(r'portable clothes dryer')
    with library.connect() as con:
        seed(con,'portable dryer');seed(con,'portable clothes dryer',n=2,username='@other')
    with patch('app.product_detection.configuration',return_value=cfg):
        with library.connect() as con:detect(con);before=records(con);edges=relationships(con)
        with library.connect() as con:report=detect(con);after=records(con)
    assert len(before)==2 and before==after
    assert report['candidates_created']==0 and report['evidence_created']==0
    assert {e['relationship_type'] for e in edges}=={'lexically_related','possible_same_product'}
    assert all(c['status']=='observed' for c in after)


def test_same_video_creator_edges_do_not_merge_brushes(library):
    with library.connect() as con:seed(con,'dish brush and floor brush')
    with library.connect() as con:
        detect(con);items=records(con);edges=relationships(con)
    assert len(items)==2
    assert {e['relationship_type'] for e in edges}=={'same_video','same_creator'}
    assert all(c['confidence']==.42 for c in items)


@pytest.mark.parametrize('text,expected',[
    ('','no_text'),('home gadgets','generic_only'),('link in bio amazon finds','noise_filtered'),
    ('easy to clean kitchen','insufficient_evidence'),('\u4f60\u597d\u5546\u54c1','unsupported_language')])
def test_gap_categories(text,expected):
    sources=[{'kind':'caption','text':text}]
    assert classify_gap(sources,[],configuration())[0]==expected


def test_unknown_phrase_is_retained_without_candidate_and_review_survives_rerun(library):
    with library.connect() as con:seed(con,'self squeezing mop')
    with library.connect() as con:
        report=detect(con);items=unresolved_records(con)
        assert report['no_candidate_reasons']['unknown_product_phrase']==1
        assert not records(con)
        assert items and items[0]['raw_phrase']=='self squeezing mop'
        pid=items[0]['id']
        assert review_phrase(con,pid,'approved','local review','2026-10-22')['detector_vocabulary_changed'] is True
        review_phrase(con,pid,'approved','local review','2026-10-22')
    with library.connect() as con:
        detect(con);after=unresolved_records(con)
        assert after[0]['status']=='approved' and len(after[0]['reviews'])==1
        assert len(after)==len(items) and len(after[0]['observations'])==len(items[0]['observations'])
        assert len(records(con))==1
        assert records(con)[0]['normalized_name']=='self squeezing mop'
        from app.product_vocabulary import version
        assert version(con)=='product-vocabulary-v2'


def test_corroboration_thresholds_are_configurable(library):
    cfg=configuration();cfg['corroboration_v2']['rules']['A']['minimum_creators']=3
    from unittest.mock import patch
    with library.connect() as con:
        seed(con,'portable blender');seed(con,'portable blender',n=2,username='@other')
    with patch('app.product_detection.configuration',return_value=cfg):
        with library.connect() as con:detect(con);assert records(con)[0]['status']=='observed'


def test_api_review_and_reports_stay_local_without_browser(api):
    _,call=api
    with db.connect() as con:seed(con,'self squeezing mop')
    assert call('/api/product-candidates/detect',{})[0]==200
    assert call('/api/product-candidates/gap-report')[1]['videos_without_candidate']==1
    assert call('/api/product-candidates/relationships')[1]['items']==[]
    pid=call('/api/product-candidates/unresolved-phrases')[1]['items'][0]['id']
    assert call(f'/api/product-candidates/unresolved-phrases/{pid}/review',{'decision':'rejected'})[0]==200
    assert call(f'/api/product-candidates/unresolved-phrases/{pid}/review',{'decision':'auto-learn'})[0]==422
    assert call('/api/product-candidates/unresolved-phrases/999/review',{'decision':'approved'})[0]==404
    with db.connect() as con:assert con.execute('SELECT count(*) FROM bridge_commands').fetchone()[0]==0
