import json
from datetime import datetime,timezone
import pytest
from pydantic import ValidationError
from app import offline_intelligence as oi,category_intelligence as ci,gold_set
from app.supplier_foundation import SupplierListingEvidence
from app.observations import save_capture
from test_product_detection import library,seed
from test_enrichment import result,capture
from test_capture import api,database


def facts(**changes):
    return {'has_caption':False,'has_comments':False,'has_thumbnail':True,'likely_product':False,
        'has_candidate':False,'has_unresolved':False,'caption_kind':'no_text','comments_count':0,
        'category_status':'unclassified',**changes}


@pytest.mark.parametrize('f,group',[
    (facts(),'A'),(facts(has_caption=True,caption_kind='generic_or_functional'),'B'),
    (facts(has_caption=True,likely_product=True,caption_kind='generic_or_functional'),'C'),
    (facts(category_status='ambiguous'),'D'),(facts(explicit_non_product_evidence='human review no'),'E'),
    (facts(has_caption=True,caption_kind='descriptive'),'F'),
])
def test_exclusive_grouping_and_overlapping_tags(f,group):
    r=oi.group_video(f);assert r['primary_group']==group and group in r['group_tags']


def test_absence_of_match_is_never_negative_product_evidence():
    assert 'E' not in oi.group_video(facts())['group_tags']


def test_visual_priority_requires_preview_and_product_evidence_for_high():
    assert oi.visual_priority(facts(likely_product=True))['priority']=='HIGH'
    assert oi.visual_priority(facts(likely_product=True,caption_kind='descriptive'))['priority']=='MEDIUM'
    assert oi.visual_priority(facts(likely_product=True,has_thumbnail=False))['priority']=='LOW'
    assert oi.visual_priority(facts())['priority']=='LOW'
    assert not oi.visual_priority(facts(has_candidate=True))['eligible']


def test_gold_gap_analysis_is_diagnostic_and_keeps_human_reason():
    review={'fn_reason':None,'review_notes':'identified with Google Lens','review_status':'reviewed'}
    original=dict(review)
    r=oi.fn_causes({**facts(),'has_detail':False},review)
    assert {'no_text','missing_enrichment','likely_visual_dependency'}<=set(r['causes'])
    assert r['diagnostic_only'] and review==original and r['human_fn_reason'] is None


def test_audit_uses_query_only_and_does_not_change_labels_categories_or_commands(library):
    with library.connect() as con:
        seed(con,'Motion Sensor Lights');ci.classify_library(con);gold_set.migrate(con)
        con.execute("INSERT INTO system_state VALUES ('browser_security_stop','{\"reason\":\"HTTP 403\"}','2026-01-01')")
    with library.connect() as con:
        before='\n'.join(con.iterdump());con.execute('PRAGMA query_only=ON')
        a=oi.audit(con);b=oi.audit(con)
        assert a==b and a['unclassified'][0]['primary_group']=='F'
        assert '\n'.join(con.iterdump())==before
        assert a['gold_recall'] is None


def test_phrase_suggestion_respects_human_rejection_without_creating_candidates(library):
    with library.connect() as con:
        seed(con,'generic caption')
        for status,name in [('pending','vacuum cleaner'),('rejected','Mini Vacuum Cleaner')]:
            con.execute('''INSERT INTO unresolved_product_phrases(video_id,raw_phrase,normalized_phrase,signature,status,first_seen_at,last_seen_at,discovery_version)
                VALUES (1,?,?,?,?,?,?,?)''',(name,name.lower(),name.lower(),status,'2026-01-01','2026-01-01','test'))
        before='\n'.join(con.iterdump());r=oi.phrase_suggestions(con)
        assert r[0]['reviewable'] and not r[0]['automatic_candidate']
        assert r[0]['blocker']=='outside_approved_vocabulary'
        assert r[1]['human_rejected'] and not r[1]['reviewable']
        assert '\n'.join(con.iterdump())==before


def test_query_history_denominators_and_empty_history(library):
    with library.connect() as con:
        assert oi.query_intelligence(con,[])['queries']==[]
        save_capture(con,capture(result()),'first','2026-01-01T00:00:00+00:00')
        save_capture(con,capture(result(),result('https://www.tiktok.com/@maker/video/124',search_position=2)),
                     'second','2026-01-02T00:00:00+00:00')
        r=oi.query_intelligence(con,ci.library(con));q=r['queries'][0]
        assert q['total_seen']==3 and q['unique_videos']==2 and q['repeat_appearances']==1
        assert q['duplicate_rate']==pytest.approx(1/3)
        assert q['observation_uniqueness_rate']==pytest.approx(2/3)
        assert q['unique_creators']==1 and not r['comparison_supported']


def test_offline_api_works_under_security_stop_without_commands_or_writes(api):
    from app import db
    _,call=api
    with db.connect() as con:
        seed(con,'Motion Sensor Lights');gold_set.migrate(con)
        con.execute("INSERT INTO system_state VALUES ('browser_security_stop','{\"reason\":\"HTTP 403\"}','2026-01-01')")
    with db.connect() as con:before='\n'.join(con.iterdump())
    status,payload=call('/api/offline-intelligence')
    assert status==200 and payload['scope']=='persisted_only'
    assert payload['summary']['videos']==1
    with db.connect() as con:assert '\n'.join(con.iterdump())==before


def listing(**changes):
    return {'provider':'manual_reference','listing_title':'Example item','listing_url':'https://example.invalid/item',
            'observed_at':datetime.now(timezone.utc),**changes}


def test_supplier_contract_keeps_listing_separate_from_identity():
    s=SupplierListingEvidence(**listing(price='12.50',currency='USD',match_confidence=.8))
    assert s.product_entity_id is None and s.review_status=='unreviewed'
    assert s.match_confidence==.8
    assert 'product_confirmed' not in s.model_dump()


@pytest.mark.parametrize('changes',[
    {'listing_url':'javascript:alert(1)'},{'listing_url':'https://user:password@example.invalid'},
    {'price':-1,'currency':'USD'},{'price':1},{'currency':'usd'},
    {'match_confidence':1.1},{'rating':6},{'orders':-1},{'min_order':0},
    {'observed_at':'2026-01-01T00:00:00'},{'shipping':{'price':2}},
])
def test_supplier_invalid_units_ranges_and_references_are_rejected(changes):
    with pytest.raises(ValidationError):SupplierListingEvidence(**listing(**changes))
