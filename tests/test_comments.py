from scripts.process_runtime import hidden_kwargs
import copy
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import subprocess

import pytest
from pydantic import ValidationError
from app import db
from app.comment_schemas import CommentsCommand,CommentsSample,VisibleComment
from app.comments import signals,latest_samples
from app.policy import ReadOnlyPolicy
from test_capture import api,database,capture_body


def comment(text='Price? Link to buy',**changes):
    return VisibleComment(text=text,raw_visible_text=text,position=1,**changes).model_dump()


def sample(**changes):
    return CommentsSample(video_url='https://www.tiktok.com/@maker/video/123',target_count=30,
                          comments=[comment()],stop_reason='no_scrollable_region',scroll_steps=0,**changes).model_dump()


def seed(call):
    call('/api/bridge/heartbeat',{'current_url':'https://www.tiktok.com/search?q=home+gadgets'})
    command_id=call('/api/commands',{'type':'READ_SEARCH_RESULTS'})[1]['id']
    call('/api/bridge/commands/next?extension_id=ext')
    assert call(f'/api/bridge/commands/{command_id}/result',{'extension_id':'ext','status':'SUCCEEDED','capture':capture_body()})[0]==200
    # Existing approved metric extractor remains untouched. Seed identity-only
    # historical v1 detail so tests can exercise the enriched-video gate.
    detail={'video_url':'https://www.tiktok.com/@maker/video/123','video_id':'123',
            'extraction_version':'tiktok-video-detail-v1','extraction_completeness':2/6,
            'field_evidence':{key:{'value':value,'confidence':1.0,'source':'video_detail'}
                for key,value in [('video_url','https://www.tiktok.com/@maker/video/123'),('video_id','123')]}}
    command_id=call('/api/commands',{'type':'READ_VIDEO_DETAIL','video_url':detail['video_url']})[1]['id']
    call('/api/bridge/commands/next?extension_id=ext')
    assert call(f'/api/bridge/commands/{command_id}/result',{'extension_id':'ext','status':'SUCCEEDED','video_detail':detail})[0]==200


def test_comment_schemas_and_permanent_policy():
    assert CommentsCommand(type='READ_COMMENTS_SAMPLE',video_url=sample()['video_url']).target_count==30
    for count in (0,101,'30',True):
        with pytest.raises(ValidationError): CommentsCommand(type='READ_COMMENTS_SAMPLE',video_url=sample()['video_url'],target_count=count)
    for action in ('LIKE','REPLY','COMMENT','FOLLOW','SHARE','SAVE','DM'):
        assert not ReadOnlyPolicy().check(action).allowed
    assert ReadOnlyPolicy().check('READ_COMMENTS_SAMPLE').allowed
    value=comment()
    assert value['author_username'] is None and value['likes'] is None and value['timestamp'] is None and value['is_reply'] is None
    for changes in ({'likes':1},{'likes_raw':'1.4K','likes':1},{'confidence':1.0},{'text':' '},{'source':'video_detail'}):
        with pytest.raises(ValidationError): VisibleComment(**{**value,**changes})
    valid={**value,'likes_raw':'1.4K','likes':1400}
    assert VisibleComment(**valid).likes==1400


def test_objective_signals_are_counted_once_per_comment_and_configured_per_language():
    comments=[comment('Price? Link to buy',author_username='@Alice'),comment('price? link to BUY',author_username='@bob'),
              comment('Quanto custa? Não funciona',author_username='@alice'),comment('¿precio',author_username=None)]
    result=signals(comments)
    assert result['comments_sampled']==4 and result['unique_commenters']==2
    assert result['duplicate_ratio']==.25
    assert result['comments_with_question_mark']==4
    assert result['comments_with_price_terms']==4
    assert result['comments_with_link_terms']==2 and result['comments_with_buy_terms']==2
    assert result['comments_with_problem_terms']==1
    assert result['by_language']['pt']['comments_with_problem_terms']==1
    assert signals([comment('blink preorder')])['comments_with_link_terms']==0
    config={'version':'custom','languages':{'xx':{'price':['zork'],'link':[],'buy':[],'problem':[]}}}
    assert signals([comment('zork')],config)['comments_with_price_terms']==1
    assert signals([])['duplicate_ratio']==0


def test_comment_storage_api_idempotency_history_and_no_metric_changes(api):
    _,call=api
    assert call('/api/commands',{'type':'READ_COMMENTS_SAMPLE','video_url':sample()['video_url']})[0]==409
    seed(call)
    before=call('/api/videos/recent')[1]
    quality=call('/api/extraction/quality')[1]
    command=call('/api/commands',{'type':'READ_COMMENTS_SAMPLE','video_url':sample()['video_url']})[1]
    assert call('/api/commands',{'type':'READ_COMMENTS_SAMPLE','video_url':sample()['video_url']})[0]==409
    call('/api/bridge/commands/next?extension_id=ext')
    body={'extension_id':'ext','status':'SUCCEEDED','comments_sample':sample()}
    route=f'/api/bridge/commands/{command["id"]}/result'
    assert call(route,body)[0]==200
    assert call(route,body)[0]==200
    changed=copy.deepcopy(body);changed['comments_sample']['comments'][0]['text']='Changed'
    assert call(route,changed)[0]==409
    view=call('/api/videos/123/comments')[1]['items'][0]
    assert view['signals']['comments_sampled']==1
    assert view['comments'][0]['video_id']=='123'
    assert view['comments'][0]['observed_at']==view['observed_at']
    assert view['coverage']['text']==100 and view['coverage']['author_username']==0
    assert call('/api/comments/summaries')[1]['items'][0]['signals']['comments_with_buy_terms']==1
    second=call('/api/commands',{'type':'READ_COMMENTS_SAMPLE','video_url':sample()['video_url']})[1]['id']
    call('/api/bridge/commands/next?extension_id=ext')
    assert call(f'/api/bridge/commands/{second}/result',body)[0]==200
    with db.connect() as con:
        assert con.execute('SELECT COUNT(*) FROM comment_samples').fetchone()[0]==2
        assert con.execute('SELECT COUNT(*) FROM comment_observations').fetchone()[0]==2
    assert call('/api/videos/recent')[1]==before
    assert call('/api/extraction/quality')[1]==quality
    assert call('/api/videos/not-an-id/comments')[0]==422


def test_sample_requires_matching_video_limit_and_extended_timeout(api):
    _,call=api;seed(call)
    ident=call('/api/commands',{'type':'READ_COMMENTS_SAMPLE','video_url':sample()['video_url'],'target_count':1})[1]['id']
    call('/api/bridge/commands/next?extension_id=ext')
    body={'extension_id':'ext','status':'SUCCEEDED','comments_sample':sample()}
    assert call(f'/api/bridge/commands/{ident}/result',body)[0]==409
    body['comments_sample']['target_count']=1
    with db.connect() as con:
        con.execute('UPDATE bridge_commands SET created_at=? WHERE id=?',((datetime.now(timezone.utc)-timedelta(seconds=60)).isoformat(),ident))
    assert call('/api/commands')[1]['items'][0]['status']=='DISPATCHED'
    assert call(f'/api/bridge/commands/{ident}/result',body)[0]==200
    assert call('/api/commands',{'type':'READ_COMMENTS_SAMPLE','video_url':'https://evil.example/@maker/video/123'})[0]==422


def test_actual_extension_comment_payload_through_http_and_sqlite(api):
    _,call=api;seed(call)
    payload=json.loads(subprocess.check_output(['node',str(Path(__file__).with_name('comments_payload.cjs'))],text=True,timeout=10, **hidden_kwargs()))
    CommentsSample(**payload)
    ident=call('/api/commands',{'type':'READ_COMMENTS_SAMPLE','video_url':payload['video_url']})[1]['id']
    call('/api/bridge/commands/next?extension_id=ext')
    assert call(f'/api/bridge/commands/{ident}/result',{'extension_id':'ext','status':'SUCCEEDED','comments_sample':payload})[0]==200
    sample=call('/api/videos/123/comments')[1]['items'][0]
    assert sample['signals']['comments_sampled']==2
    assert sample['signals']['comments_with_question_mark']==1
    assert sample['signals']['comments_with_buy_terms']==1
    assert sample['coverage']['likes']==100
    assert sample['coverage']['timestamp']==100
    assert sample['comments'][1]['likes']==0
