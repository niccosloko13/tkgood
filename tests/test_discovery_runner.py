import json
from datetime import datetime,timezone,timedelta
import pytest
from fastapi import HTTPException
from app.discovery_runner import DiscoveryPlan,DiscoveryRunner
from test_safe_collection import ready,capture,EXT
from test_product_detection import library
from app import db,safe_collection as safe
from app.observations import save_capture
from app.safety import SafetyGate,CONTRACT


def test_stage_plans_are_bounded_search_only():
    one=DiscoveryPlan.build(1,['home gadgets']);two=DiscoveryPlan.build(2,['home gadgets','home finds'])
    assert (one['max_queries'],one['max_results_per_query'],one['max_scrolls'],one['search_only'])==(1,10,0,True)
    assert (two['max_queries'],two['max_new_videos'],two['max_runtime_seconds'])==(5,30,180)
    for bad in ([],['x','y'],[' '],['a','a'],[{}]):
        with pytest.raises((HTTPException,TypeError)):DiscoveryPlan.build(1,bad)
    with pytest.raises(HTTPException):DiscoveryPlan.build(3,['x'])


def test_python_safety_contract_maps_existing_evidence_without_side_effects():
    assert SafetyGate.VERSION if hasattr(SafetyGate,'VERSION') else CONTRACT['version']=='babi-safety-v1'
    good={'current_page_status':'healthy','page_ready_state':'complete','tiktok_session_status':'confirmed','last_seen':(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat(),'extension_id':'e','build_id':'b','tab_id':1,'current_url':'https://www.tiktok.com/search?q=home+gadgets','session_evidence':['visible_own_profile_with_avatar','visible_account_inbox']}
    assert SafetyGate.assess(good,'e','b').may_continue
    assert SafetyGate.observation({'page_ready_state':'loading'}).transient
    assert SafetyGate.observation(good,global_stopped=True).security=='GLOBAL_BLOCKED'
    assert SafetyGate.observation(good,target_blocked=True).security=='TARGET_BLOCKED'
    assert SafetyGate.observation({'current_page_status':'challenge'}).page=='CHALLENGE'
    assert SafetyGate.observation({'tiktok_session_status':'login_required'}).page=='LOGGED_OUT'
    stale={**good,'last_seen':'2000-01-01T00:00:00+00:00'}
    assert not SafetyGate.assess(stale,'e','b').may_continue


def test_legacy_stage_adapters_return_the_canonical_discovery_report(library):
    with db.connect() as con:
        ident=ready(con)
        save_capture(con,capture(),'fixture:query','2026-10-25T00:00:00+00:00')
        batch=safe.start(con,ident,['home organization'],1)
        report=DiscoveryRunner.report(con,batch['id'])
        assert {k:report[k] for k in ('stage','queries','status','query_index','results','new_videos','duplicates','observations','trend_snapshots','stop_reason')}=={
            'stage':1,'queries':['home organization'],'status':'PENDING','query_index':1,'results':0,'new_videos':0,'duplicates':0,'observations':0,'trend_snapshots':0,'stop_reason':None}
        assert set(report)==set(__import__('json').loads(open('config/discovery_contract.json').read())['report_fields'])
