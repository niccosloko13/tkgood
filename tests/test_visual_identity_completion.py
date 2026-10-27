import json
import sqlite3
from urllib.error import HTTPError
import pytest
from app import visual_identification as vi,visual_assets as va,intelligence_core as core
from app.visual_providers import AutomaticVisualProvider,ProviderUnavailable,ProviderSecurityStop
from app.intelligence_embeddings import provider,OpenCLIPProvider,ResourceBusy
from app.intelligence_index import ProductIndex
from test_product_detection import library,seed
from test_local_visual_assets import image_bytes,metadata


def analysis():
    observation={'status':'insufficient','reason':'Single test frame cannot establish temporal or market properties'}
    return {'assessment':'identified','visual_description':'Handheld white tool with a broad cleaning head',
        'possible_product_names':[{'name':'Mini PVA Sponge Mop','aliases':['Portable PVA Mop'],'supporting_features':['broad head'],'uncertainties':['SKU unknown']}],
        'detected_objects':['cleaning tool'],'functional_description':'Possibly wipes a smooth surface','distinctive_features':['broad head'],
        'possible_category':'Cleaning Tool','quality':{k:dict(observation) for k in ['demonstration_visibility','problem_solution_clarity','before_after_possible','transformation_strength','visual_novelty','product_visibility','creative_repeatability_possible']}}


class FakeProvider:
    def __init__(self):self.calls=[]
    def identify(self,item,response=None):
        self.calls.append('image')
        assert set(item)=={'image','bytes','mime'}
        return {'status':'suggested','provider_result':{'data':analysis(),'response_id':'fixture-response','model':'gpt-4.1-mini','api_host':'api.openai.com'},'image_sha256':item['image']['sha256'],'lens_status':'LENS_ASSISTED_REQUIRED'}
    def confirm_web(self,*args):
        self.calls.append('web')
        url='https://www.kaercher.com/test-product'
        return {'data':{'results':[{'url':url,'title':'Public cleaning tool','product_name':'Cleaning tool','compatibility':'PARTIAL','match_reason':'Same type, exact SKU unverified','independence':'Not assessed'}]},
                'annotations':[{'type':'url_citation','url_citation':{'url':url,'content':'Observed page excerpt'}}]}


@pytest.fixture
def visual_con(library,tmp_path,monkeypatch):
    monkeypatch.setattr(va,'ROOT',tmp_path);monkeypatch.setattr(vi,'ROOT',tmp_path)
    monkeypatch.setattr(OpenCLIPProvider,'version',property(lambda _:'fixture-model'))
    def embed(con,kind,value):
        provider.last_inference={'cache_status':'hit' if kind=='image' else 'miss','dimension':2,'model_version':'fixture-model'}
        return [1.,0.]
    monkeypatch.setattr(provider,'embed',embed)
    reference={'reference_id':'candidate:1','reference_kind':'CANDIDATE_REFERENCE','product_id':None,'name':'Possible tool',
               'source':{},'similarity':1.,'embedding_kind':'text','embedding_version':'fixture-model','index_version':'fixture-index','observed_at':vi.now()}
    monkeypatch.setattr(ProductIndex,'search',lambda *args:[reference]);monkeypatch.setattr(ProductIndex,'metadata',lambda _:None)
    with library.connect() as con:
        seed(con,'generic caption');va.persist_visual_asset(1,image_bytes(),metadata(),con);yield con


def test_real_pipeline_orchestration_without_name_entry_and_idempotent(visual_con):
    fake=FakeProvider();r=vi.run_visual_identity(visual_con,1,automatic=fake)
    assert r['status']=='complete' and fake.calls==['image','web']
    assert r['hypotheses'][0]['name']=='Mini PVA Sponge Mop'
    assert r['image_embedding']['cache_status']=='hit' and r['retrieval'][0]['reference_kind']=='CANDIDATE_REFERENCE'
    assert r['web_confirmations'][0]['compatibility']=='PARTIAL'
    assert not r['web_confirmations'][0]['independence_verified']
    assert r['decision']['status']=='REVIEW'
    assert visual_con.execute('SELECT count(*) FROM intelligence_entities').fetchone()[0]==0
    again=vi.run_visual_identity(visual_con,1,automatic=fake)
    assert again==r and fake.calls==['image','web']
    assert visual_con.execute('SELECT count(*) FROM visual_product_evidence').fetchone()[0]==1
    assert visual_con.execute('SELECT review_status FROM visual_product_evidence').fetchone()[0]=='suggested'


def test_resource_defer_reuses_image_search_and_vpe(visual_con,monkeypatch):
    fake=FakeProvider();original=provider.embed
    monkeypatch.setattr(provider,'embed',lambda *a:(_ for _ in ()).throw(ResourceBusy('pressure')))
    assert vi.run_visual_identity(visual_con,1,automatic=fake)['status']=='deferred'
    monkeypatch.setattr(provider,'embed',original)
    result=vi.run_visual_identity(visual_con,1,automatic=fake)
    assert result['status']=='complete' and fake.calls==['image','web']
    assert visual_con.execute('SELECT count(*) FROM visual_product_evidence').fetchone()[0]==1


def test_no_gold_input_no_candidate_mutation_and_unchanged_security(visual_con):
    con=visual_con;con.execute("INSERT INTO system_state VALUES ('browser_security_stop','{\"reason\":\"HTTP 403\"}','original')")
    before=tuple(con.execute("SELECT * FROM system_state WHERE key='browser_security_stop'").fetchone())
    candidates=[tuple(r) for r in con.execute('SELECT * FROM product_candidates')]
    con.set_authorizer(lambda action,a,b,db,trigger:sqlite3.SQLITE_DENY if a and a.startswith('gold_') else sqlite3.SQLITE_OK)
    vi.run_visual_identity(con,1,automatic=FakeProvider())
    vi.needs_visual(con)
    assert tuple(con.execute("SELECT * FROM system_state WHERE key='browser_security_stop'").fetchone())==before
    assert candidates==[tuple(r) for r in con.execute('SELECT * FROM product_candidates')]
    con.set_authorizer(lambda *a:sqlite3.SQLITE_OK)


def test_provider_unavailable_and_lens_assisted(visual_con,monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    assert vi.provider_states()['vision_model']['status']=='UNAVAILABLE'
    assert vi.provider_states()['google_lens_assisted']['status']=='AVAILABLE_ASSISTED'
    result=vi.run_visual_identity(visual_con,1)
    assert result['status']=='unavailable' and result['lens_status']=='LENS_ASSISTED_REQUIRED'


def test_security_403_is_terminal_without_provider_retry(visual_con):
    fake=FakeProvider()
    def blocked(*args):fake.calls.append('blocked');raise ProviderSecurityStop('HTTP_403')
    fake.identify=blocked
    assert vi.run_visual_identity(visual_con,1,automatic=fake)['status']=='blocked'
    assert vi.run_visual_identity(visual_con,1,automatic=fake)['status']=='blocked'
    assert fake.calls==['blocked']


def test_asset_unavailable_never_fetches_remote_thumbnail(library):
    with library.connect() as con:
        seed(con,'caption');con.execute("UPDATE videos SET thumbnail_url='https://p16.tiktokcdn.com/file.jpg'")
        fake=FakeProvider();r=vi.run_visual_identity(con,1,automatic=fake)
        assert r['status']=='visual_unavailable' and not r['provider_invoked'] and not fake.calls


def test_aliases_merge_only_explicit_equivalence():
    rows=vi.normalized_hypotheses([{'name':'Mini PVA Sponge Mop','aliases':['Portable PVA Mop']},{'name':'Portable PVA Mop','aliases':['Self-Squeeze Mini Mop']}])
    assert len(rows)==1 and rows[0]['name']=='Mini PVA Sponge Mop'
    assert 'Self-Squeeze Mini Mop' in rows[0]['aliases']
    assert len(vi.normalized_hypotheses([{'name':'Window Sponge','aliases':[]},{'name':'Dish Sponge','aliases':[]}]))==2


@pytest.mark.parametrize('caption,candidate,expected',[('Mini PVA Sponge Mop','Mini PVA Sponge Mop','SUPPORTED'),('Phone charger','Phone charger','CONFLICT'),('Nice gadget',None,'NEUTRAL')])
def test_visual_text_cross_check(caption,candidate,expected):
    context={'caption':caption,'comments':[],'existing_candidates':[{'id':1,'canonical_name':candidate}] if candidate else [],'unresolved_phrases':[],'category':{}}
    assert vi.text_cross_check(analysis()['possible_product_names'][0],context)['status']==expected


def test_web_requires_real_citation_and_allowed_domain():
    response=FakeProvider().confirm_web()
    response['data']['results']+=[{**response['data']['results'][0],'url':'https://www.tiktok.com/test'},
                                {**response['data']['results'][0],'url':'https://www.kaercher.com/invented'}]
    response['annotations'].append({'type':'url_citation','url_citation':{'url':'https://www.tiktok.com/test'}})
    assert len(vi.grounded_web_results(response))==1


def test_api_client_excludes_persisted_names_and_gold(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','fixture-not-a-real-key');monkeypatch.setenv('OPENAI_BASE_URL','https://openrouter.ai/api/v1')
    automatic=AutomaticVisualProvider();captured=[]
    def post(messages,schema,web=False):captured.append(messages);return {'data':analysis()}
    monkeypatch.setattr(automatic,'post',post)
    automatic.identify({'image':{'status':'available','sha256':'a'*64},'mime':'image/png','bytes':b'fixture','caption':'GOLD_SECRET_PREVIOUS_NAME'})
    assert 'GOLD_SECRET_PREVIOUS_NAME' not in json.dumps(captured)
    assert captured[0][0]['content'][1]['image_url']['url'].startswith('data:image/png;base64,')


def test_untrusted_api_endpoint_cannot_receive_credential(monkeypatch):
    monkeypatch.setenv('OPENAI_BASE_URL','https://untrusted.example/api/v1')
    with pytest.raises(ProviderUnavailable):AutomaticVisualProvider().endpoint()


def test_provider_response_must_match_current_asset(visual_con):
    fake=FakeProvider();original=fake.identify
    def wrong(item,response=None):
        result=original(item,response);result['image_sha256']='b'*64;return result
    fake.identify=wrong
    with pytest.raises(ValueError,match='current image'):vi.run_visual_identity(visual_con,1,automatic=fake)
    assert visual_con.execute('SELECT status FROM visual_pilots WHERE input_hash IS NOT NULL').fetchone()[0]=='failed'


def test_same_provider_reruns_are_not_independent_votes_and_keep_original_order(visual_con):
    from datetime import datetime,timezone
    vi.run_visual_identity(visual_con,1,automatic=FakeProvider())
    source=vi.image_source(visual_con,1)
    names=[{'name':'Window vacuum cleaner','aliases':[]},{'name':'Glass cleaner device','aliases':[]}]
    payload={'response_id':'fixture-second-response','data':{**analysis(),'possible_product_names':names}}
    for h in names:
        row=vi.suggest(visual_con,1,vi.ProposalInput(provider='vision_model',possible_product_name=h['name'],aliases=[],source_type='vision_model_output',
            observed_at=datetime.now(timezone.utc),reason='Second independent execution, same provider; not independent evidence',provider_version='gpt-4.1-mini',image_sha256=source['sha256']))
        visual_con.execute('UPDATE visual_product_evidence SET provider_payload_json=? WHERE id=?',(json.dumps(payload),row['id']))
    assert [p['possible_product_name'] for p in vi.proposals(visual_con,1,active_only=True)]==[n['name'] for n in names]
    assert len(vi.proposals(visual_con,1))==3  # Archived evidence remains present.
    assert core.observation(visual_con,1)['proposals'][0]['possible_product_name']=='Window vacuum cleaner'


def test_challenge_response_stops_before_web_normalization(monkeypatch):
    from app import visual_providers as vp
    monkeypatch.setenv('OPENAI_API_KEY','fixture-key');monkeypatch.setenv('OPENAI_BASE_URL','https://openrouter.ai/api/v1')
    class Response:
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def read(self,*a):return json.dumps({'choices':[{'message':{'content':'CAPTCHA required; Access Denied'}}]}).encode()
    class Opener:
        def open(self,*a,**kw):return Response()
    monkeypatch.setattr(vp,'build_opener',lambda *a:Opener())
    with pytest.raises(ProviderSecurityStop):AutomaticVisualProvider().confirm_web(['Window cleaner'],'visible tool')
