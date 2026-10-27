"""Bounded offline visual proposals. No network clients or product/Gold mutations."""
from abc import ABC,abstractmethod
from collections import Counter
from datetime import datetime,timezone
import base64
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from urllib.parse import urlsplit
from pydantic import BaseModel,ConfigDict,Field,field_validator
from typing import Literal
from . import category_intelligence as ci,gold_set
from .offline_intelligence import audit

ROOT=Path(__file__).resolve().parents[1]
MAX_VISUAL_ITEMS=14
MAX_IMAGE_BYTES=10*1024*1024
PROVIDERS=('vision_model','web_image_search','google_lens_assisted')
STATES=('suggested','accepted','rejected','unclear')

def now():return datetime.now(timezone.utc).isoformat()
def encoded(value):return json.dumps(value,ensure_ascii=False,sort_keys=True)
def normalized(value):return ' '.join(unicodedata.normalize('NFKC',value or '').casefold().split())


def migrate(con):
    ci.migrate(con)
    columns={r[1] for r in con.execute('PRAGMA table_info(visual_product_evidence)')}
    for key,definition in {'source_type':'TEXT','aliases_json':"TEXT NOT NULL DEFAULT '[]'",'image_sha256':'TEXT',
            'reason':"TEXT NOT NULL DEFAULT ''",'provider_version':'TEXT','idempotency_key':'TEXT',
            'provider_payload_json':"TEXT NOT NULL DEFAULT '{}'",'context_cross_check_json':"TEXT NOT NULL DEFAULT '{}'",
            'multimodal_json':"TEXT NOT NULL DEFAULT '{}'"}.items():
        if key not in columns:con.execute('ALTER TABLE visual_product_evidence ADD COLUMN '+key+' '+definition)
    con.execute('CREATE UNIQUE INDEX IF NOT EXISTS visual_proposal_idempotency ON visual_product_evidence(idempotency_key) WHERE idempotency_key IS NOT NULL')
    for statement in [
        '''CREATE TABLE IF NOT EXISTS visual_image_assets (
            id INTEGER PRIMARY KEY,video_id INTEGER NOT NULL REFERENCES videos(id),relative_path TEXT NOT NULL,
            source_type TEXT NOT NULL,sha256 TEXT NOT NULL,mime_type TEXT NOT NULL,observed_at TEXT NOT NULL,
            UNIQUE(video_id,sha256))''',
        '''CREATE TABLE IF NOT EXISTS visual_review_history (
            id INTEGER PRIMARY KEY,evidence_id INTEGER NOT NULL REFERENCES visual_product_evidence(id),
            previous_status TEXT NOT NULL,review_status TEXT NOT NULL,notes TEXT NOT NULL,observed_at TEXT NOT NULL,
            reviewer_type TEXT NOT NULL CHECK(reviewer_type='human'))''',
        '''CREATE TABLE IF NOT EXISTS visual_product_search_evidence (
            id INTEGER PRIMARY KEY,evidence_id INTEGER NOT NULL REFERENCES visual_product_evidence(id),title TEXT NOT NULL,
            url TEXT NOT NULL,source TEXT NOT NULL,observed_at TEXT NOT NULL,possible_match INTEGER NOT NULL,
            match_reason TEXT NOT NULL,visual_compatible INTEGER NOT NULL,contradiction INTEGER NOT NULL,
            independence_group TEXT,independence_reviewed INTEGER NOT NULL,UNIQUE(evidence_id,url,observed_at))''',
        '''CREATE TABLE IF NOT EXISTS visual_pilots (
            id INTEGER PRIMARY KEY,created_at TEXT NOT NULL,provider TEXT NOT NULL,selected_ids_json TEXT NOT NULL,
            status TEXT NOT NULL,completed_at TEXT)''',
        '''CREATE TABLE IF NOT EXISTS visual_pilot_items (
            pilot_id INTEGER NOT NULL REFERENCES visual_pilots(id),video_id INTEGER NOT NULL REFERENCES videos(id),
            availability TEXT NOT NULL,reason TEXT NOT NULL,source_type TEXT,image_sha256 TEXT,provider_status TEXT NOT NULL,
            PRIMARY KEY(pilot_id,video_id))''',
        '''CREATE TABLE IF NOT EXISTS visual_gold_assessments (
            id INTEGER PRIMARY KEY,video_id INTEGER NOT NULL REFERENCES videos(id),evidence_id INTEGER NOT NULL REFERENCES visual_product_evidence(id),
            name_match TEXT NOT NULL,helpful INTEGER,notes TEXT NOT NULL,observed_at TEXT NOT NULL,
            reviewer_type TEXT NOT NULL CHECK(reviewer_type='human'))''',
    ]:con.execute(statement)
    from .visual_assets import migrate as migrate_assets
    migrate_assets(con)
    for name,definition in {'input_hash':'TEXT','result_json':"TEXT NOT NULL DEFAULT '{}'",'context_json':"TEXT NOT NULL DEFAULT '{}'"}.items():
        if name not in {r[1] for r in con.execute('PRAGMA table_info(visual_pilots)')}:
            con.execute('ALTER TABLE visual_pilots ADD COLUMN '+name+' '+definition)
    con.execute('CREATE UNIQUE INDEX IF NOT EXISTS visual_pipeline_input ON visual_pilots(input_hash) WHERE input_hash IS NOT NULL')
    for name,definition in {'product_name':'TEXT','compatibility':'TEXT','independence_basis':'TEXT'}.items():
        if name not in {r[1] for r in con.execute('PRAGMA table_info(visual_product_search_evidence)')}:
            con.execute('ALTER TABLE visual_product_search_evidence ADD COLUMN '+name+' '+definition)


def image_mime(data):
    if len(data)>MAX_IMAGE_BYTES:raise ValueError('Image exceeds 10 MB')
    if len(data)>=33 and data.startswith(b'\x89PNG\r\n\x1a\n') and data[12:16]==b'IHDR':return 'image/png'
    if len(data)>=16 and data.startswith(b'\xff\xd8\xff') and data.endswith(b'\xff\xd9'):return 'image/jpeg'
    if len(data)>=30 and data.startswith(b'RIFF') and data[8:12]==b'WEBP':return 'image/webp'
    raise ValueError('Only persisted PNG/JPEG/WebP images are supported')


def read_local(path):
    # No absolute/UNC paths, symlinks outside the two designated evidence folders,
    # arbitrary filesystem reads, redirects or requests to remote thumbnail URLs.
    p=Path(path)
    if p.is_absolute() or '..' in p.parts or '\\' in str(path) or ':' in str(path):raise ValueError('Use a workspace-relative media path')
    resolved=(ROOT/p).resolve()
    if not resolved.is_relative_to(ROOT.resolve()) or not any(resolved.is_relative_to((ROOT/x).resolve()) for x in ('data/media','data/visual-images','data/visual_assets')):
        raise ValueError('Image must be inside a workspace local media folder')
    if not resolved.is_file():raise ValueError('Persisted local image not found')
    if resolved.stat().st_size>MAX_IMAGE_BYTES:raise ValueError('Image exceeds 10 MB')
    data=resolved.read_bytes();return data,image_mime(data)


def register_image(con,vid,path,source_type):
    if source_type not in ('local_frame','local_thumbnail'):raise ValueError('Invalid local source type')
    if not con.execute('SELECT 1 FROM videos WHERE id=?',(vid,)).fetchone():raise KeyError('Video not found')
    data,mime=read_local(path);sha=hashlib.sha256(data).hexdigest()
    con.execute('INSERT OR IGNORE INTO visual_image_assets(video_id,relative_path,source_type,sha256,mime_type,observed_at) VALUES (?,?,?,?,?,?)',
                (vid,path,source_type,sha,mime,now()))
    return image_source(con,vid)


def image_source(con,vid):
    row=con.execute('SELECT thumbnail_url FROM videos WHERE id=?',(vid,)).fetchone()
    if not row:raise KeyError('Video not found')
    assets=con.execute('''SELECT a.* FROM visual_image_assets a LEFT JOIN visual_asset_selections s ON s.video_id=a.video_id
        WHERE a.video_id=? ORDER BY CASE WHEN s.asset_id=a.id THEN 0 WHEN a.source_type='local_frame' THEN 1 ELSE 2 END,a.id DESC''',(vid,)).fetchall()
    for asset in assets:
        try:
            data,mime=read_local(asset['relative_path'])
            if hashlib.sha256(data).hexdigest()!=asset['sha256']:continue
            return {'status':'available','visual_available':True,'asset_id':asset['id'],'source_type':asset['source_type'],'image_source':asset['relative_path'],
                    'sha256':asset['sha256'],'mime_type':mime,'width':asset['width'],'height':asset['height'],'reason':'validated_persisted_local_image'}
        except (ValueError,OSError):continue
    thumb=row['thumbnail_url'] or ''
    if thumb.startswith('data:image/'):
        try:
            header,payload=thumb.split(',',1)
            if ';base64' not in header or len(payload)>MAX_IMAGE_BYTES*2:raise ValueError('Invalid embedded image')
            data=base64.b64decode(payload,validate=True);mime=image_mime(data)
            return {'status':'available','source_type':'embedded_thumbnail','image_source':'persisted_thumbnail:'+str(vid),
                    'sha256':hashlib.sha256(data).hexdigest(),'mime_type':mime,'reason':'validated_embedded_thumbnail'}
        except (ValueError,TypeError):pass
    elif thumb and not urlsplit(thumb).scheme and not thumb.startswith('//'):
        try:
            data,mime=read_local(thumb)
            return {'status':'available','source_type':'local_thumbnail','image_source':thumb,
                    'sha256':hashlib.sha256(data).hexdigest(),'mime_type':mime,'reason':'validated_persisted_local_thumbnail'}
        except (ValueError,OSError):pass
    host=(urlsplit(thumb).hostname or '').lower()
    tiktok=any(host==h or host.endswith('.'+h) for h in ('tiktok.com','tiktokcdn.com','tiktokcdn-us.com','tiktokv.com','byteoversea.com','ibytedtos.com'))
    return {'status':'visual_unavailable','source_type':'remote_thumbnail' if host else None,'sha256':None,
            'image_source':None,'remote_host':host or None,
            'reason':'blocked_by_security_stop_tiktok_cdn' if tiktok else 'remote_reference_not_cached' if host else 'no_valid_local_image'}


def image_bytes(con,vid):
    source=image_source(con,vid)
    if source['status']!='available':raise ValueError('Visual unavailable; no remote fetching is allowed')
    if source['source_type']=='embedded_thumbnail':
        value=con.execute('SELECT thumbnail_url FROM videos WHERE id=?',(vid,)).fetchone()[0]
        data=base64.b64decode(value.split(',',1)[1],validate=True)
    else:data,_=read_local(source['image_source'])
    if hashlib.sha256(data).hexdigest()!=source['sha256']:raise ValueError('Image changed during read')
    return data,source['mime_type']


def prepare_local_assisted(con,vid,image_sha256):
    """Production image preparation, independent of evaluation/pilot membership."""
    image=image_source(con,vid)
    if image['status']!='available' or image['sha256']!=image_sha256:
        raise ValueError('Current validated local image required')
    con.execute('INSERT OR IGNORE INTO visual_assisted_sessions(video_id,image_sha256,asset_id,created_at) VALUES (?,?,?,?)',
                (vid,image['sha256'],image.get('asset_id'),now()))
    return {'video_id':vid,'image_url':f'/api/visual-identification/videos/{vid}/image',
            'download_url':f'/api/visual-identification/videos/{vid}/image?download=true',
            'image_sha256':image['sha256'],'provider_invoked':False,'status':'awaiting_assisted_result'}


def high_queue(con):
    return [v for v in audit(con)['visual_queue'] if v['visual']['priority']=='HIGH'][:MAX_VISUAL_ITEMS]


def review_item(con,vid,queue_snapshot=None):
    v=next((v for v in ci.library(con) if v['video_id']==vid),None)
    if v is None:raise KeyError('Video not found')
    raw=con.execute('SELECT thumbnail_url FROM videos WHERE id=?',(vid,)).fetchone()[0]
    comments=[dict(r) for r in con.execute('SELECT id,text,sample_id,author_username FROM comment_observations WHERE video_id=? ORDER BY id DESC',(vid,))]
    # Keep relevant mentions/questions first, dedup exact repeated observations.
    comments=list({(r['author_username'],r['text']):r for r in reversed(comments)}.values())
    comments.sort(key=lambda r:(not bool(re.search(r'price|buy|link|where|produto|nome|vacuum|cleaner|\?',r['text'],re.I)),r['id']))
    snapshot=next((v for v in (high_queue(con) if queue_snapshot is None else queue_snapshot) if v['video_id']==vid),None)
    image=image_source(con,vid)
    prepared=image['status']=='available' and bool(con.execute('SELECT 1 FROM visual_assisted_sessions WHERE video_id=? AND image_sha256=?',(vid,image['sha256'])).fetchone())
    stored=proposals(con,vid)
    reference=next((r for r in gold_set.listing(con)['items'] if r['video_id']==vid and r['human_reviewed']),None) if stored else None
    return {'video_id':vid,'platform_video_id':v['platform_video_id'],'thumbnail_url':raw,
        'image':image,'assisted_prepared':prepared,'caption':v['caption'],'hashtags':re.findall(r'#[\w]+',v['caption'] or ''),
        'relevant_comments':comments[:10],'current_candidate':v['candidates'],'unresolved_phrases':v['unresolved'],
        'category':v['category']['primary_category'],'subcategory':v['category']['primary_subcategory'],
        'product_family':v['category']['product_family'],'visual_priority_reason':snapshot['visual']['reasons'] if snapshot else [],
        'in_high_pilot':snapshot is not None,'in_gold_high_pilot':vid in {v['video_id'] for v in gold_high_queue(con,queue_snapshot)},
        'gold_reference_name':reference.get('canonical_product_name') if reference else None,'proposals':stored}


def gold_high_queue(con,queue_snapshot=None):
    queue=high_queue(con) if queue_snapshot is None else queue_snapshot
    reviews={r['video_id']:r for r in gold_set.listing(con)['items'] if r['human_reviewed']}
    result=[{'video_id':v['video_id'],'benchmark_category':reviews[v['video_id']]['benchmark_category'],
             'image':image_source(con,v['video_id'])} for v in queue if v['video_id'] in reviews]
    return sorted(result,key=lambda v:(v['benchmark_category']!='fn',v['video_id']))


def prepare_assisted(con,vid,expected_sha):
    if vid not in {v['video_id'] for v in gold_high_queue(con)}:
        raise ValueError('Initial assisted pilot is restricted to HIGH items with existing Gold reviews')
    item=review_item(con,vid);image=item['image']
    if image['status']!='available' or image['sha256']!=expected_sha:raise ValueError('Current local image required')
    con.execute('INSERT OR IGNORE INTO visual_assisted_sessions(video_id,image_sha256,asset_id,created_at) VALUES (?,?,?,?)',
                (vid,image['sha256'],image.get('asset_id'),now()))
    session=con.execute('SELECT id FROM visual_assisted_sessions WHERE video_id=? AND image_sha256=?',(vid,image['sha256'])).fetchone()[0]
    return {'session_id':session,'video_id':vid,'image_sha256':image['sha256'],
            'image_url':f'/api/visual-identification/videos/{vid}/image',
            'download_url':f'/api/visual-identification/videos/{vid}/image?download=true',
            'caption':item['caption'],'comments':item['relevant_comments'],'category':item['category'],
            'current_candidate':item['current_candidate'],'unresolved_phrases':item['unresolved_phrases'],
            'provider_invoked':False,'status':'awaiting_assisted_result'}


def local_asset_metrics(con):
    queue=high_queue(con);pilot=gold_high_queue(con,queue);gold={r['video_id']:r for r in gold_comparison(con)}
    available=sum(image_source(con,v['video_id'])['status']=='available' for v in queue)
    attempted={r[0] for r in con.execute('SELECT DISTINCT video_id FROM visual_assisted_sessions')}
    ready={v['video_id'] for v in pilot if v['video_id'] in attempted and
           any(p['image_sha256']==v['image'].get('sha256') for p in proposals(con,v['video_id']))}
    matches=sum(gold[v['video_id']]['visual_name_match'] is True for v in pilot if v['video_id'] in ready)
    helpful=sum(gold[v['video_id']]['visual_helpful'] is True for v in pilot if v['video_id'] in ready)
    wrong=sum(gold[v['video_id']]['visual_wrong'] is True for v in pilot if v['video_id'] in ready)
    resolved={v['video_id'] for v in pilot if v['video_id'] in ready and
              (gold[v['video_id']]['visual_name_match'] is True or gold[v['video_id']]['visual_wrong'] is True)}
    return {'assets_uploaded':con.execute("SELECT count(*) FROM visual_image_assets WHERE source_type='manual_upload'").fetchone()[0],
        'assets_total':con.execute('SELECT count(*) FROM visual_image_assets').fetchone()[0],
        'HIGH_resolved':available,'HIGH_remaining':len(queue)-available,'HIGH_resolved_definition':'local image available, not identity confirmed',
        'gold_high_items':len(pilot),'gold_FN_items':sum(v['benchmark_category']=='fn' for v in pilot),
        'Gold_FN_tested':sum(v['benchmark_category']=='fn' and v['video_id'] in ready for v in pilot),
        'visual_attempted':sum(v['video_id'] in attempted for v in pilot),'visual_helpful':helpful,
        'visual_match':matches,'visual_wrong':wrong,'still_unclear':len(pilot)-len(resolved),
        'helpfulness_assessed':sum(gold[v['video_id']]['visual_helpful'] is not None for v in pilot if v['video_id'] in ready),
        'pilot':pilot,'product_confirmed':False}


def public_url(value):
    if not value:return value
    u=urlsplit(value);host=(u.hostname or '').lower()
    if u.scheme not in ('http','https') or not host or u.username or u.password:raise ValueError('HTTP(S) reference without credentials required')
    if any(host==d or host.endswith('.'+d) for d in ('tiktok.com','tiktokcdn.com','tiktokcdn-us.com','tiktokv.com')):
        raise ValueError('TikTok references cannot be visual/web result targets during security stop')
    return value


class ProposalInput(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    provider:Literal['vision_model','web_image_search','google_lens_assisted']
    possible_product_name:str=Field(min_length=2,max_length=300)
    aliases:list[str]=Field(default_factory=list,max_length=12)
    result_url:str|None=Field(default=None,max_length=4000)
    source_type:Literal['assisted_visual_review','vision_model_output','web_image_result']
    observed_at:datetime
    confidence:float|None=Field(default=None,ge=0,le=1,allow_inf_nan=False)
    reason:str=Field(min_length=1,max_length=4000)
    provider_version:str=Field(min_length=1,max_length=100)
    image_sha256:str=Field(pattern=r'^[a-f0-9]{64}$')

    @field_validator('result_url')
    @classmethod
    def safe_url(cls,value):return public_url(value)

    @field_validator('observed_at')
    @classmethod
    def aware(cls,value):
        if value.utcoffset() is None:raise ValueError('Timezone required')
        return value

    @field_validator('aliases')
    @classmethod
    def bounded_aliases(cls,values):
        if any(not v.strip() or len(v)>300 for v in values):raise ValueError('Invalid alias')
        return values


class VisualSearchProvider(ABC):
    @abstractmethod
    def identify(self,item,response=None):pass


class AssistedVisualProvider(VisualSearchProvider):
    name=None
    def identify(self,item,response=None):
        if item['image']['status']!='available':return {'status':'visual_unavailable','proposal':None}
        if response is None:return {'status':'awaiting_assisted_input','proposal':None}
        proposal=ProposalInput.model_validate(response)
        if proposal.provider!=self.name:raise ValueError('Provider attribution mismatch')
        if proposal.image_sha256!=item['image']['sha256']:raise ValueError('Image changed; review the current image before suggesting')
        return {'status':'suggested','proposal':proposal}


class VisionModelProvider(AssistedVisualProvider):name='vision_model'
class WebImageSearchProvider(AssistedVisualProvider):name='web_image_search'
class GoogleLensAssistedProvider(AssistedVisualProvider):name='google_lens_assisted'
REGISTRY={p.name:p() for p in (VisionModelProvider,WebImageSearchProvider,GoogleLensAssistedProvider)}


def provider_states():
    from .visual_providers import AutomaticVisualProvider
    return {'vision_model':AutomaticVisualProvider().availability(),
            'google_lens_assisted':{'status':'AVAILABLE_ASSISTED','workflow_status':'LENS_ASSISTED_REQUIRED'},
            'google_lens_automatic':{'status':'UNAVAILABLE'}}


def normalized_hypotheses(names):
    """Merge only explicit alias equivalence, never cosine or shared generic heads."""
    from .candidate_semantics import normalize
    groups=[]
    for entry in names[:3]:
        name=entry['name'].strip();aliases=entry.get('aliases',[])
        keys={normalize(n) for n in [name,*aliases]}
        previous=next((g for g in groups if keys & {normalize(n) for n in [g['name'],*g['aliases']]}),None)
        if previous:previous['aliases'].extend([name,*aliases])
        else:groups.append({**entry,'name':name,'aliases':list(aliases)})
    for g in groups:
        unique={}
        for name in g['aliases']:
            if normalize(name)!=normalize(g['name']):unique.setdefault(normalize(name),name.strip())
        g['aliases']=list(unique.values())[:12]
    return groups


def persisted_visual_context(con,vid):
    from .intelligence_core import observation
    from .comments import consumer_signals
    item=observation(con,vid)
    return {'video_id':vid,'caption':item['caption'],'hashtags':re.findall(r'#[\w]+',item['caption'] or ''),
            'comments':item['comments'],'creator':item['creator'],
            'queries':[r[0] for r in con.execute('SELECT DISTINCT search_query FROM search_observations WHERE video_id=?',(vid,))],
            'existing_candidates':item['candidates'],'unresolved_phrases':item['unresolved'],
            'category':item['category'],'product_family':item['category'].get('product_family'),
            'purchase_intent':consumer_signals(item['comments']),'image':item['image']}


def text_cross_check(hypothesis,context):
    from .intelligence_decisions import specificity
    from .candidate_semantics import normalize
    names=[hypothesis['name'],*hypothesis.get('aliases',[])]
    support=[];conflicts=[]
    for name in names:
        result=specificity(name,context.get('caption'),context['comments'])
        if result['caption_literal_support']:support.append('caption')
        support.extend('comment:'+str(i) for i in result['comment_evidence_ids'])
        conflicts.extend('comment:'+str(i) for i in result['contradicting_comment_ids'])
        if result['caption_contradiction']:conflicts.append('caption_negation')
    observed_names={normalize(n) for n in names}
    for candidate in context['existing_candidates']:
        if normalize(candidate['canonical_name']) in observed_names:support.append('candidate:'+str(candidate['id']))
    for phrase in context['unresolved_phrases']:
        if normalize(phrase['raw_phrase']) in observed_names:support.append('unresolved:'+str(phrase['id']))
    # A specific incompatible literal candidate is a conflict, unlike a generic
    # caption or a broad "vacuum cleaner" comment which is merely neutral.
    visual_tokens=set(normalize(' '.join(names)).split())
    for candidate in context['existing_candidates']:
        text=candidate['canonical_name'];sig=specificity(text,context.get('caption'),context['comments'])
        compound_candidate=len(normalize(text).split())>=2 and not generic_name(text)
        if (sig['specific'] or compound_candidate) and sig['caption_literal_support'] and not visual_tokens & set(normalize(text).split()):
            conflicts.append('specific_candidate:'+str(candidate['id']))
    proposed_category=set(normalize(hypothesis.get('possible_category','')).split())
    category_tokens=set(normalize(' '.join(str(context['category'].get(k) or '') for k in ('primary_category','primary_subcategory','product_family'))).split())
    return {'status':'CONFLICT' if conflicts else 'SUPPORTED' if support else 'NEUTRAL',
            'support':sorted(set(support)),'conflicts':sorted(set(conflicts)),
            'reason':'Specific observed contradiction' if conflicts else 'Literal compatible persisted evidence' if support else 'Generic or non-matching context cannot confirm or refute the visual hypothesis',
            'category_context':context['category'],'category_compatibility':'SUPPORTED' if proposed_category & category_tokens else 'NEUTRAL',
            'context_did_not_enter_image_prompt':True}


def grounded_web_results(response):
    """Only cited URLs on the configured allowlist; no arbitrary fetches or URLs."""
    from .visual_providers import config
    allowed=config()['web_domains']
    cited={a.get('url_citation',{}).get('url'):a.get('url_citation',{}) for a in response.get('annotations',[]) if a.get('type')=='url_citation'}
    rows=[]
    for row in (response.get('data') or {}).get('results',[])[:3]:
        parsed=urlsplit(row['url']);host=(parsed.hostname or '').lower()
        if parsed.scheme!='https' or parsed.username or parsed.password:continue
        if not any(host==d or host.endswith('.'+d) for d in allowed):continue
        if row['url'] not in cited:continue
        rows.append({**row,'domain':host,'source_excerpt':cited[row['url']].get('content','')[:6000],
                     'independence_group':site_group(row['url']),'independence_verified':False})
    return rows


def run_visual_identity(con,vid,automatic=None,prefetched_image=None,prefetched_web=None):
    """Existing assets/VPE/core, in order. Cached steps resume; Gold is never read."""
    from .visual_providers import AutomaticVisualProvider,ProviderUnavailable,ProviderSecurityStop,config
    from .intelligence_embeddings import provider,ResourceBusy
    from .intelligence_index import ProductIndex
    from . import intelligence_core as core
    context=persisted_visual_context(con,vid);source=context['image']
    if source['status']!='available':return {'video_id':vid,'status':'visual_unavailable','reason':'LOCAL_ASSET_REQUIRED','provider_invoked':False}
    automatic=automatic or AutomaticVisualProvider()
    key=hashlib.sha256(encoded({'context':context,'config':config(),'stage_version':'visual-pipeline-v1'}).encode()).hexdigest()
    run=con.execute('SELECT * FROM visual_pilots WHERE input_hash=?',(key,)).fetchone()
    if run and run['status'] in ('complete','blocked','unavailable'):return json.loads(run['result_json'])
    if not run:
        rid=con.execute('INSERT INTO visual_pilots(created_at,provider,selected_ids_json,status,input_hash,context_json) VALUES (?,?,?,\'running\',?,?)',
            (now(),'vision_model',encoded([vid]),key,encoded(context))).lastrowid
        run=con.execute('SELECT * FROM visual_pilots WHERE id=?',(rid,)).fetchone()
    result=json.loads(run['result_json']);result.update({'run_id':run['id'],'video_id':vid,'asset_id':source.get('asset_id'),
        'image_sha256':source['sha256'],'lens_status':'LENS_ASSISTED_REQUIRED','provider_states':provider_states()})
    def checkpoint(status):
        result['status']=status
        con.execute('UPDATE visual_pilots SET status=?,result_json=?,completed_at=? WHERE id=?',
            (status,encoded(result),now() if status in ('complete','blocked','unavailable') else None,run['id']))
        con.commit()
    try:
        if 'visual_search' not in result:
            if prefetched_image is not None:result['visual_search']=prefetched_image
            else:
                for prior in con.execute("SELECT id,created_at,result_json FROM visual_pilots WHERE input_hash IS NOT NULL AND status='complete' ORDER BY id DESC"):
                    cached=json.loads(prior['result_json']);search=cached.get('visual_search',{})
                    model=search.get('provider_result',{}).get('model','').split('/')[-1]
                    if search.get('image_sha256')==source['sha256'] and model.startswith(config()['model']):
                        result['visual_search']=search;result['image_analysis_cached_from_run']=prior['id']
                        if 'web_search' in cached:
                            result['web_search']=cached['web_search'];result['web_observed_at']=cached.get('web_observed_at',prior['created_at'])
                        break
                if 'visual_search' not in result:
                    data,mime=image_bytes(con,vid)
                    result['visual_search']=automatic.identify({'image':source,'bytes':data,'mime':mime})
            checkpoint('running')
        if result['visual_search'].get('image_sha256')!=source['sha256']:
            raise ValueError('Visual provider response is not bound to the current image')
        from .visual_providers import VisualAnalysis
        VisualAnalysis.model_validate(result['visual_search']['provider_result']['data'])
        analysis=result['visual_search']['provider_result']['data']
        hypotheses=normalized_hypotheses(analysis['possible_product_names']);result['hypotheses']=hypotheses
        result['visual_quality']=analysis['quality'];result['evidence_ids']=[]
        for h in hypotheses:
            proposal=ProposalInput(provider='vision_model',possible_product_name=h['name'],aliases=h['aliases'],source_type='vision_model_output',
                observed_at=datetime.fromisoformat(run['created_at']),reason=encoded({'visible':h['supporting_features'],'uncertainties':h['uncertainties']}),
                provider_version=result['visual_search']['provider_result']['model'],image_sha256=source['sha256'])
            existing=next((dict(r) for r in con.execute("SELECT * FROM visual_product_evidence WHERE video_id=? AND image_sha256=? AND provider='vision_model' AND possible_product_name=?",
                (vid,source['sha256'],h['name'])) if json.loads(r['provider_payload_json'] or '{}').get('response_id')==result['visual_search']['provider_result'].get('response_id')),None)
            row=existing or suggest(con,vid,proposal);eid=row['id'];result['evidence_ids'].append(eid)
            cross=text_cross_check({**h,'possible_category':analysis['possible_category']},context)
            con.execute('UPDATE visual_product_evidence SET provider_payload_json=?,context_cross_check_json=? WHERE id=?',
                (encoded(result['visual_search']['provider_result']),encoded(cross),eid))
            h['evidence_id']=eid;h['text_cross_check']=cross
        checkpoint('running')
        data,_=image_bytes(con,vid);vector=provider.embed(con,'image',data);result['image_embedding']=dict(provider.last_inference)
        result['retrieval']=ProductIndex().search(vector,provider.version)
        for h in hypotheses:
            text=provider.embed(con,'text',h['name'])
            h['hypothesis_embedding']=dict(provider.last_inference)
            h['image_text_similarity']=sum(a*b for a,b in zip(vector,text))
            h['similarity_is_probability']=False
            con.execute('UPDATE visual_product_evidence SET multimodal_json=? WHERE id=?',
                (encoded({'model_version':provider.version,'image_text_similarity':h['image_text_similarity'],'retrieval':result['retrieval'],'similarity_is_probability':False}),h['evidence_id']))
        checkpoint('running')
        if hypotheses and 'web_search' not in result:
            result['web_search']=prefetched_web if prefetched_web is not None else automatic.confirm_web([h['name'] for h in hypotheses],analysis['visual_description'])
            result['web_observed_at']=run['created_at']
            checkpoint('running')
        result['web_confirmations']=grounded_web_results(result.get('web_search',{}))
        for h in hypotheses:
            for web in result['web_confirmations']:
                con.execute('''INSERT OR IGNORE INTO visual_product_search_evidence(evidence_id,title,url,source,observed_at,possible_match,
                    match_reason,visual_compatible,contradiction,independence_group,independence_reviewed,domain,product_name,compatibility,independence_basis)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (h['evidence_id'],web['title'],web['url'],'automatic_cited_web_search',result.get('web_observed_at',run['created_at']),int(web['compatibility']!='CONFLICT'),
                     web['match_reason'],0,int(web['compatibility']=='CONFLICT'),web['independence_group'],0,web['domain'],web['product_name'],
                     web['compatibility'],'publisher_domain_only_not_human_verified'))
        result['decision']=core.identify(con,vid,with_embeddings=True)
        checkpoint('complete');return result
    except ResourceBusy as exc:
        if result.get('hypotheses'):result['decision']=core.identify(con,vid)
        result['reason']='RESOURCE_DEFER';result['error']=str(exc);checkpoint('deferred');return result
    except ProviderSecurityStop as exc:
        result['reason']='SECURITY_BLOCK';result['error']=str(exc);checkpoint('blocked');return result
    except ProviderUnavailable as exc:
        if result.get('hypotheses'):result['decision']=core.identify(con,vid)
        result['reason']='PROVIDER_UNAVAILABLE';result['error']=str(exc);checkpoint('unavailable');return result
    except (ValueError,KeyError,TypeError) as exc:
        result['reason']='INVALID_VISUAL_RESPONSE';result['error']=type(exc).__name__;checkpoint('failed');raise


def needs_visual(con):
    """Production priority is independent of Gold; evaluation can flag FN later."""
    from .intelligence_core import latest
    from .visual_providers import config
    decisions={r['video_id']:r for r in latest(con)};rows=[]
    for item in ci.library(con):
        vid=item['video_id'];image=image_source(con,vid);current=proposals(con,vid,active_only=True)
        decision=decisions.get(vid);status=decision['status'] if decision else 'UNRESOLVED'
        if current:continue
        priority='A' if status=='REVIEW' else 'B' if image['status']=='available' and vid in config()['historical_priority_ids'] else 'C' if not item['candidates'] else 'D'
        rows.append({'video_id':vid,'priority':priority,'reason':'REVIEW_WITHOUT_VISUAL_EVIDENCE' if priority=='A' else 'UNRESOLVED_VISUAL_GAP',
                     'local_asset':image if image['status']=='available' else None,'visual_status':'NEEDS_VISUAL' if image['status']=='available' else 'LOCAL_ASSET_REQUIRED'})
    return sorted(rows,key=lambda r:(r['local_asset'] is None,r['priority'],r['video_id']))


def visual_summary(con):
    items=ci.library(con);assets=[];processed=[];hypotheses=[];conflicted=set();lens=set()
    for item in items:
        vid=item['video_id'];source=image_source(con,vid)
        if source['status']!='available':continue
        assets.append(vid)
        current=proposals(con,vid,active_only=True)
        completed=any(json.loads(r[0]).get('image_sha256')==source['sha256'] for r in con.execute("SELECT result_json FROM visual_pilots WHERE input_hash IS NOT NULL AND status='complete' AND selected_ids_json=?",(encoded([vid]),)))
        if current or completed:processed.append(vid)
        for p in current:
            if p['review_status']=='rejected':continue
            hypotheses.append({'video_id':vid,'evidence_id':p['id'],'name':p['possible_product_name'],'review_status':p['review_status']})
            if json.loads(p.get('context_cross_check_json') or '{}').get('status')=='CONFLICT' or any(r['contradiction'] for r in p['web_evidence']):conflicted.add(vid)
        latest_reason=con.execute('SELECT reason_code FROM intelligence_decisions WHERE video_id=? ORDER BY id DESC LIMIT 1',(vid,)).fetchone()
        if latest_reason and latest_reason[0] in ('REVIEW_CONFLICTING_VISUAL_RESULTS','REVIEW_POSSIBLE_VARIANT','REVIEW_CONFLICTING_TEXT_EVIDENCE'):conflicted.add(vid)
        if not any(p['provider']=='google_lens_assisted' and p['review_status']!='rejected' for p in current):lens.add(vid)
    return {'available_assets':len(assets),'needs_visual':len(needs_visual(con)),'visual_processed':len(processed),
            'running':con.execute("SELECT count(*) FROM visual_pilots WHERE input_hash IS NOT NULL AND status IN ('running','deferred')").fetchone()[0],
            'lens_assisted_required':len(lens),'visual_hypotheses':len(hypotheses),
            'confirmed':con.execute('SELECT count(DISTINCT video_id) FROM intelligence_entity_observations').fetchone()[0],
            'conflicted':len(conflicted),'providers':provider_states(),'queue':needs_visual(con),'hypotheses':hypotheses}


def suggest(con,vid,body):
    image=image_source(con,vid)
    outcome=REGISTRY[body.provider].identify({'image':image},body.model_dump())
    if outcome['status']!='suggested':raise ValueError('Accessible persisted image required; no visual name inferred from captions')
    aliases=[];seen={normalized(body.possible_product_name)}
    for name in body.aliases:
        if normalized(name) not in seen:aliases.append(name.strip());seen.add(normalized(name))
    payload=body.model_dump(mode='json');payload['aliases']=aliases
    payload['observed_at']=body.observed_at.astimezone(timezone.utc).isoformat()
    key=hashlib.sha256(encoded({'video_id':vid,'image':image['sha256'],'proposal':payload}).encode()).hexdigest()
    con.execute('''INSERT OR IGNORE INTO visual_product_evidence(video_id,image_source,provider,possible_product_name,result_url,
        confidence,review_status,observed_at,source_type,aliases_json,image_sha256,reason,provider_version,idempotency_key)
        VALUES (?,?,?,?,?,?,'suggested',?,?,?,?,?,?,?)''',
        (vid,image['image_source'],body.provider,body.possible_product_name,body.result_url,body.confidence,
         payload['observed_at'],body.source_type,encoded(aliases),image['sha256'],body.reason,body.provider_version,key))
    return dict(con.execute('SELECT * FROM visual_product_evidence WHERE idempotency_key=?',(key,)).fetchone())


def review_proposal(con,eid,status,notes=''):
    if status not in ('accepted','rejected','unclear'):raise ValueError('Explicit human decision required')
    row=con.execute('SELECT * FROM visual_product_evidence WHERE id=?',(eid,)).fetchone()
    if not row:raise KeyError('Proposal not found')
    if not row['image_sha256']:raise ValueError('Legacy evidence requires a new image-bound proposal')
    if row['review_status']!=status:
        con.execute('INSERT INTO visual_review_history(evidence_id,previous_status,review_status,notes,observed_at,reviewer_type) VALUES (?,?,?,?,?,\'human\')',
                    (eid,row['review_status'],status,notes,now()))
        con.execute('UPDATE visual_product_evidence SET review_status=? WHERE id=?',(status,eid))
    return {'review_status':status,'product_confirmed':False,'gold_set_changed':False}


def compatible_name(name,text):
    n=normalized(name);t=normalized(text)
    return bool(n and re.search(r'(?<!\w)'+re.escape(n)+r'(?!\w)',t))


def generic_name(name):
    return normalized(name) in {'product','produto','gadget','gadgets','item','tool','appliance','accessory','home gadget','utensílio','acessório'}


def site_group(url):
    host=urlsplit(url).hostname or ''
    # Conservative site buckets plus explicit human independence attestation.
    # Same-domain pages and subdomains never become independent listings.
    parts=host.lower().split('.')
    suffix='.'.join(parts[-2:])
    return '.'.join(parts[-3:] if suffix in ('com.br','co.uk','com.au','co.jp','co.in') else parts[-2:])


def hypothesis(con,row):
    """Legacy compatibility diagnostics; deprecated as an operational decision gate.

    Intelligence Core consumes observed names/support/provenance, never this score.
    """
    v=con.execute('SELECT caption FROM videos WHERE id=?',(row['video_id'],)).fetchone()
    comments=[dict(r) for r in con.execute('SELECT id,text FROM comment_observations WHERE video_id=?',(row['video_id'],))]
    listings=[dict(r) for r in con.execute('''SELECT * FROM visual_product_search_evidence WHERE id IN
        (SELECT id FROM (SELECT id,row_number() OVER (PARTITION BY url ORDER BY julianday(observed_at) DESC,id DESC) AS seq
         FROM visual_product_search_evidence WHERE evidence_id=?) WHERE seq=1)''',(row['id'],))]
    name_evidence=[{'name':row['possible_product_name'],'source_type':'visual','source_id':row['id']}]
    name_evidence.extend({'name':n,'source_type':'provider_alias','source_id':row['id']} for n in json.loads(row['aliases_json']))
    name_evidence.extend({'name':r['title'],'source_type':'web_product_evidence','source_id':r['id']} for r in listings
        if r['possible_match'] and r['visual_compatible'] and not r['contradiction'] and len(r['title'])<=300 and not generic_name(r['title']))
    unique={}
    for entry in name_evidence:unique.setdefault(normalized(entry['name']),entry['name'])
    names=[n for n in unique.values() if not generic_name(n)]
    def support(name):
        # Choose among actually observed names only; never invent a blended synonym.
        return (int(bool(v and compatible_name(name,v['caption']))),
                int(any(compatible_name(name,r['text']) for r in comments)),
                int(normalized(name)==normalized(row['possible_product_name'])))
    canonical=max(names,key=support) if names else row['possible_product_name']
    aliases=[name for key,name in unique.items() if key!=normalized(canonical)]
    text=bool(v and any(compatible_name(n,v['caption']) for n in names))
    matches=[r for r in comments if any(compatible_name(n,r['text']) for n in names)]
    supported=[r for r in listings if r['possible_match'] and r['visual_compatible'] and not r['contradiction'] and
        r['independence_reviewed'] and r['independence_group'] and any(compatible_name(n,r['title']) for n in names)]
    independent=min(len({r['independence_group'] for r in supported}),len({site_group(r['url']) for r in supported}))
    generic=generic_name(row['possible_product_name'])
    context=[v['caption'] or '',*[r['text'] for r in comments]]
    text_contradiction=any(re.search(r'(?<!\w)(?:not|is not|isn\'t|não é)\s+(?:(?:a|an|um|uma)\s+)?'+re.escape(normalized(n))+r'(?!\w)',normalized(t)) for n in names for t in context)
    contradiction=any(r['contradiction'] for r in listings) or text_contradiction
    score=.25+.1*text+.1*bool(matches)+(.25 if independent>=2 else 0)
    reasons=['single_visual_result_is_not_confirmation']
    if text:reasons.append('literal_caption_support')
    if matches:reasons.append('literal_comment_support_not_verified_identity')
    if independent>=2:reasons.append('two_attested_independent_compatible_listing_sources')
    else:reasons.append('insufficient_independent_listing_support')
    if generic:score=min(score,.2);reasons.append('generic_name_cap')
    if contradiction:score=min(score,.2);reasons.append('observed_contradiction_cap')
    if row['review_status']=='rejected':score=0;reasons.append('human_rejected_proposal')
    return {'possible_product_name':row['possible_product_name'],'canonical_name_suggestion':normalized(canonical),
        'aliases':aliases,'name_evidence':name_evidence,'identity_confidence':round(min(score,.7),2),'confidence_is_probability':False,
        'evidence_sources':{'visual':[row['id']],'text':['videos:'+str(row['video_id'])] if text else [],
            'comments':['comment_observations:'+str(r['id']) for r in matches],
            'web_product_evidence':[r['id'] for r in listings]},'independent_listing_sources':independent,'reason':reasons,
        'review_status':row['review_status'],'product_confirmed':False}


def proposals(con,vid,active_only=False):
    items=[];current=image_source(con,vid)
    for row in con.execute('SELECT * FROM visual_product_evidence WHERE video_id=? AND image_sha256 IS NOT NULL ORDER BY id DESC',(vid,)):
        item=dict(row);item['hypothesis']=hypothesis(con,row)
        item['image_matches_current']=current['status']=='available' and current['sha256']==row['image_sha256']
        item['web_evidence']=[dict(r) for r in con.execute('SELECT * FROM visual_product_search_evidence WHERE evidence_id=?',(row['id'],))]
        item['history']=[dict(r) for r in con.execute('SELECT * FROM visual_review_history WHERE evidence_id=? ORDER BY id',(row['id'],))]
        items.append(item)
    if not active_only:return items
    current_items=[p for p in items if p['image_matches_current'] and p['review_status']!='rejected']
    selected=[];automatic={}
    for p in current_items:
        payload=json.loads(p.get('provider_payload_json') or '{}')
        if payload.get('response_id'):
            automatic.setdefault((p['provider'],p['provider_version']),[]).append(p)
        else:selected.append(p)
    for group in automatic.values():
        anchor=next((p for p in group if p['review_status']=='accepted'),group[0])
        response=json.loads(anchor['provider_payload_json'])['response_id']
        active=[p for p in group if json.loads(p['provider_payload_json'])['response_id']==response]
        def rank(p):
            payload=json.loads(p['provider_payload_json'])
            names=payload.get('data',{}).get('possible_product_names',[])
            return next((i for i,h in enumerate(names) if normalized(h['name'])==normalized(p['possible_product_name'])),len(names))
        selected.extend(sorted(active,key=rank))
    return selected


def run_pilot(con,provider='vision_model'):
    if provider not in REGISTRY:raise ValueError('Unsupported provider')
    items=high_queue(con)
    rid=con.execute("INSERT INTO visual_pilots(created_at,provider,selected_ids_json,status) VALUES (?,?,?,'running')",
                    (now(),provider,encoded([v['video_id'] for v in items]))).lastrowid
    for v in items:
        image=image_source(con,v['video_id'])
        # No provider invoked for unavailable images. Assisted providers never fetch.
        outcome=REGISTRY[provider].identify({'image':image}) if image['status']=='available' else {'status':'not_called_image_unavailable'}
        con.execute('INSERT INTO visual_pilot_items VALUES (?,?,?,?,?,?,?)',
            (rid,v['video_id'],image['status'],image['reason'],image['source_type'],image['sha256'],outcome['status']))
    con.execute("UPDATE visual_pilots SET status='complete',completed_at=? WHERE id=?",(now(),rid))
    return rid


def gold_comparison(con):
    result=[]
    for review in gold_set.listing(con)['items']:
        if not review['human_reviewed']:continue
        vid=review['video_id'];visual=proposals(con,vid);image=image_source(con,vid)
        usable=[p for p in visual if p['review_status']!='rejected' and p['image_matches_current']]
        names={normalized(review.get(k)) for k in ('canonical_product_name','raw_product_name')} - {''}
        exact=any(normalized(p['possible_product_name']) in names or any(normalized(n) in names for n in p['hypothesis']['aliases']) for p in usable) if names else False
        assessment=con.execute('SELECT * FROM visual_gold_assessments WHERE video_id=? ORDER BY id DESC LIMIT 1',(vid,)).fetchone()
        active_ids={p['id'] for p in usable}
        valid=assessment and assessment['evidence_id'] in active_ids
        match=assessment['name_match'] in ('exact','acceptable') if valid else exact if usable and names else None
        result.append({'video_id':vid,'human_product_name':review.get('canonical_product_name'),'human_raw_name':review.get('raw_product_name'),
            'benchmark_category':review['benchmark_category'],'visual_names':[p['possible_product_name'] for p in usable],
            'visual_name_match':match,'comparison_method':'separate_human_assessment' if valid else 'literal_normalized_name_only' if match is not None else 'not_evaluable',
            'visual_helpful':bool(assessment['helpful']) if valid and assessment['helpful'] is not None else None,
            'visual_wrong':assessment['name_match']=='wrong' if valid else None,
            'visual_unavailable':image['status']!='available','unavailable_reason':image['reason'] if image['status']!='available' else None})
    return result


def metrics(con,pilot_id=None):
    pilot=con.execute('SELECT * FROM visual_pilots WHERE id=?',(pilot_id,)).fetchone() if pilot_id else con.execute('SELECT * FROM visual_pilots ORDER BY id DESC LIMIT 1').fetchone()
    items=[dict(r) for r in con.execute('SELECT * FROM visual_pilot_items WHERE pilot_id=?',(pilot['id'],))] if pilot else []
    ids=[r['video_id'] for r in items]
    rows=[r for vid in ids for r in con.execute('SELECT * FROM visual_product_evidence WHERE video_id=? AND image_sha256 IS NOT NULL',(vid,))]
    comparison=gold_comparison(con);eligible=[r for r in comparison if r['visual_name_match'] is not None]
    return {'pilot_id':pilot['id'] if pilot else None,'visual_items_attempted':len(items),
        'visual_available':sum(r['availability']=='available' for r in items),'visual_unavailable':sum(r['availability']!='available' for r in items),
        'visual_suggestions':len(rows),'human_accepted':sum(r['review_status']=='accepted' for r in rows),
        'human_rejected':sum(r['review_status']=='rejected' for r in rows),
        'visual_helpful_on_FN':sum(r['benchmark_category']=='fn' and r['visual_helpful'] is True for r in comparison),
        'visual_match_on_gold_set':sum(r['visual_name_match'] is True for r in eligible),'gold_comparison_evaluable':len(eligible),
        'gold_name_match_rate':sum(r['visual_name_match'] is True for r in eligible)/len(eligible) if eligible else None,
        'gold_visual_unavailable':sum(r['visual_unavailable'] for r in comparison),
        'gold_helpfulness_assessed':sum(r['visual_helpful'] is not None for r in comparison),
        'gold_wrong_assessed':sum(r['visual_wrong'] is not None for r in comparison),
        'visual_wrong_on_gold_set':sum(r['visual_wrong'] is True for r in comparison),
        'provider_calls':sum(r['provider_status']!='not_called_image_unavailable' for r in items),
        'provider_performance':dict(Counter(r['provider_status'] for r in items)),'pilot_items':items,
        'gold_comparison':comparison,'recall_improvement_measured':False}
