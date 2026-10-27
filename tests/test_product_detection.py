import json
import pytest
from app import db
from app.product_detection import normalize,extractProductCandidatePhrases,detect,records

@pytest.fixture
def library(tmp_path,monkeypatch):
    monkeypatch.setattr(db,'DB_PATH',tmp_path/'test.db');db.init_db()
    return db

def seed(con,caption,username='@maker',n=1):
    at='2026-10-21T00:00:00+00:00'
    url=f'https://www.tiktok.com/{username}/video/{n}'
    vid=con.execute("INSERT INTO videos(source,video_id,canonical_url,creator_username,caption,first_seen_at,last_seen_at,field_evidence_json) VALUES ('tiktok',?,?,?,?,?,?,?)",(str(n),url,username,caption,at,at,'{}')).lastrowid
    cid=con.execute("INSERT INTO creators(platform,username,profile_url,first_seen_at,last_seen_at,extractor_version) VALUES ('tiktok',?,?,?,?,?)",(username,'https://www.tiktok.com/'+username,at,at,'test')).lastrowid
    con.execute('INSERT INTO video_creators VALUES (?,?,?,?)',(vid,cid,at,'test'))
    return vid

@pytest.mark.parametrize('raw',['Mini Blender!','mini blender','MINI-BLENDER'])
def test_normalize(raw):
    assert normalize(raw)=='mini blender'

@pytest.mark.parametrize('raw',['viral','amazing must have','home gadgets','link in bio buy now','wow need this','',None,'amazon finds'])
def test_noise(raw):
    assert extractProductCandidatePhrases(raw)==[]

@pytest.mark.parametrize('raw',['portable blender','MINI-BLENDER','#portable_blender','#PortableBlender','liquidificador portátil','خلاط محمول','licuadora portátil','Ninja Blast Portable Blender'])
def test_phrases(raw):
    assert extractProductCandidatePhrases(raw)

def test_history_dedup_urls_and_diversity(library):
    with library.connect() as c:
        seed(c,'Portable Blender',n=1);seed(c,'portable blender',username='@other',n=2)
    with library.connect() as c:
        a=detect(c); original=records(c)[0]
    with library.connect() as c:
        b=detect(c); after=records(c)[0]
        assert c.execute('SELECT count(*) FROM product_detection_runs').fetchone()[0]==2
    assert a['candidates_created']==1 and b['candidates_created']==0 and b['evidence_created']==0
    assert after==original
    assert after['unique_video_count']==2 and after['unique_creator_count']==2
    assert after['status']=='corroborated' and len({u['url'] for u in after['urls']})==4
    assert after['confidence']>0.49

def test_single_and_missing_alias_separation(library):
    with library.connect() as c:
        seed(c,'mini blender',n=1);seed(c,'portable blender',username='@other',n=2);seed(c,None,username='@third',n=3)
    with library.connect() as c:
        report=detect(c);items=records(c)
    assert report['videos_without_candidate']==1 and len(items)==2
    assert all(i['status']=='observed' and i['confidence']<=0.49 for i in items)

def test_migration_preserves_library(library):
    with library.connect() as c:seed(c,'fruit spinner')
    library.init_db();library.init_db()
    with library.connect() as c:
        assert c.execute('SELECT count(*) FROM videos').fetchone()[0]==1
        assert detect(c)['candidates_created']==1

def test_comments_profile_context_and_url_preservation(library):
    from app.product_detection import summarize,configuration
    with library.connect() as c:
        vid=seed(c,'portable blender')
    with library.connect() as c:
        detect(c);cid=records(c)[0]['id']
        for i in range(5):
            c.execute('INSERT INTO product_candidate_evidence(candidate_id,evidence_type,source_entity_type,source_entity_id,video_id,creator_id,commenter,source_url,raw_text,extracted_text,confidence,observed_at,extractor_version,dedup_key) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (cid,'comment','comment_observations',str(i),vid,1,'@buyer'+str(i),'https://www.tiktok.com/@maker/video/1','where can I buy this portable blender?','portable blender',.12,'2026-10-21','product-candidate-v1','comment'+str(i)))
        c.execute("INSERT INTO product_candidate_evidence(candidate_id,evidence_type,source_entity_type,source_entity_id,video_id,creator_id,source_url,raw_text,extracted_text,confidence,observed_at,extractor_version,dedup_key) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",(cid,'creator_bio','creator_profile_observations','1',vid,1,'https://www.tiktok.com/@maker','portable blender shop','portable blender',.18,'2026-10-21','product-candidate-v1','bio'))
        summary=summarize(c,cid,configuration())
        assert summary['supporting_comment_count']==5 and summary['unique_commenter_count']==5
        assert records(c)[0]['status']=='observed'  # A single video cannot corroborate identity.
    with library.connect() as c:
        detect(c);assert records(c)[0]['supporting_comment_count']==5
        assert len(records(c)[0]['urls'])>=2

def test_context_link_never_creates_product(library):
    with library.connect() as c:
        seed(c,'wow')
        c.execute("INSERT INTO creator_profile_observations(creator_id,command_id,observed_at,raw_visible_text,extractor_version,fields_json,field_evidence_json,links_json,signals_json,config_json) VALUES (1,1,'2026-10-21','','test','{}','{}',?,'{}','{}')",(json.dumps([{'url':'https://shop.example/portable-blender','label':'portable blender'}]),))
    with library.connect() as c:
        assert detect(c)['candidates_created']==0
        c.execute("UPDATE videos SET caption='portable blender'")
    with library.connect() as c:
        detect(c);item=records(c)[0]
        assert item['status']=='observed' and item['confidence']==.42
        assert any(e['evidence_type']=='profile_link' and e['extracted_text'] is None for e in item['evidence'])
        assert any(u['url']=='https://shop.example/portable-blender' for u in item['urls'])

def test_hashtag_raw_and_no_caption_double_count(library):
    with library.connect() as c:
        vid=seed(c,None)
        c.execute("INSERT INTO search_observations(video_id,capture_id,search_query,observed_at,extractor_version,extraction_completeness,fields_json,field_evidence_json) VALUES (?,'test','gadgets','2026-10-21','test',0,?,'{}')",(vid,json.dumps({'caption':'#PortableBlender #viral'})))
    with library.connect() as c:
        detect(c);item=records(c)[0]
        assert [e['evidence_type'] for e in item['evidence']]==['hashtag']
        assert item['evidence'][0]['raw_text']=='#PortableBlender'
        assert item['status']=='observed'

from test_capture import api,database

def test_api_detect_without_browser_without_bridge(api):
    _,call=api
    with db.connect() as c:seed(c,'portable blender')
    code,report=call('/api/product-candidates/detect',{})
    assert code==200 and report['videos_processed']==1
    code,listing=call('/api/product-candidates')
    assert code==200 and len(listing['items'])==1
    cid=listing['items'][0]['id']
    assert call(f'/api/product-candidates/{cid}')[1]['primary_reference_url'].endswith('/video/1')
    assert call('/api/product-candidates/999')[0]==404
    assert call('/api/product-candidates/detect',{'video_id':999})[0]==404
    assert call('/api/product-candidates/detect',{'video_id':1,'latest_capture':True})[0]==422
    with db.connect() as c:assert c.execute('SELECT count(*) FROM bridge_commands').fetchone()[0]==0
