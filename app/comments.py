"""Bounded public comment observations and versioned lexical counts. No AI."""
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from .extraction import video_identity

TERMS_PATH=Path(__file__).resolve().parents[1]/'config/comment_terms.json'


def normalize(value):
    return ' '.join(unicodedata.normalize('NFKC',value).casefold().split())


def term_match(text,term):
    term=normalize(term)
    if not term:
        return False
    return bool(re.search((r'(?<!\w)' if term[0].isalnum() else '')+re.escape(term)+
                          (r'(?!\w)' if term[-1].isalnum() else ''),text))


def signals(comments, config=None):
    config=config or json.loads(TERMS_PATH.read_text(encoding='utf-8'))
    texts=[normalize(item['text']) for item in comments]
    languages=config['languages']
    by_language={language:{f'comments_with_{group}_terms':sum(any(term_match(text,term) for term in terms[group]) for text in texts)
        for group in ('price','link','buy','problem')} for language,terms in languages.items()}
    # A comment matching multiple configured languages counts once in the total.
    combined={f'comments_with_{group}_terms':sum(any(term_match(text,term) for terms in languages.values() for term in terms[group]) for text in texts)
              for group in ('price','link','buy','problem')}
    authors={normalize(item['author_username']) for item in comments if item.get('author_username')}
    return {'comments_sampled':len(comments),'unique_commenters':len(authors),
            'duplicate_ratio':round(1-len(set(texts))/len(texts),6) if texts else 0.0,
            'comments_with_question_mark':sum(any(mark in item['text'] for mark in ('?','？','¿')) for item in comments),
            **combined,'by_language':by_language,'terms_version':config['version']}


def consumer_signals(comments):
    """Identity-independent lexical observations, not demand or quality truth.

    Duplicate normalized text (including missing-author copies) counts once.
    Different authors repeating the same short word are conservatively collapsed;
    all underlying evidence IDs remain available for audit.
    """
    from .intelligence_decisions import settings
    config=json.loads((TERMS_PATH.parent/'consumer_signals.json').read_text(encoding='utf-8'))
    def folded(text):
        text=''.join(c for c in unicodedata.normalize('NFKD',normalize(text)) if not unicodedata.combining(c))
        return ' '.join(re.findall(r'\w+',text))
    unique={}
    for c in comments:
        key=folded(c['text'])
        if not key or key in config['noise']:continue
        entry=unique.setdefault(key,{'text':c['text'],'authors':set(),'evidence_ids':[]})
        if c.get('author_username'):entry['authors'].add(normalize(c['author_username']))
        if c.get('id') is not None:entry['evidence_ids'].append(c['id'])
    types={name:[] for name in config['patterns']}
    intent=[];classes={k:[] for k in ('PURCHASE_INTENT','POSITIVE_REACTION','NEGATIVE_REACTION','QUESTION','PRODUCT_COMPLAINT','QUALITY_COMPLAINT')}
    authors=set()
    for text,c in unique.items():
        hits=[name for name,patterns in config['patterns'].items() if any(re.search(pattern,text) for pattern in patterns)]
        primary_id=c['evidence_ids'][0] if c['evidence_ids'] else None
        purchase=any(name in config['purchase_types'] for name in hits)
        for name in hits:types[name].append(primary_id)
        if purchase:intent.append(c);authors.update(c['authors']);classes['PURCHASE_INTENT'].append(primary_id)
        for name in classes:
            if name!='PURCHASE_INTENT' and name.lower() in hits:classes[name].append(primary_id)
        if '?' in c['text'] or any(name in hits for name in ('where_to_buy','link_request','price_question')):
            if primary_id not in classes['QUESTION']:classes['QUESTION'].append(primary_id)
    sample=len(unique);ratio=len(intent)/sample if sample else None;p=settings()['consumer']
    status='measured' if sample>=p['minimum_sample'] else 'partial' if sample else 'insufficient_data'
    strong=bool(sample>=p['minimum_sample'] and len(authors)>=p['strong_intent_authors'] and ratio>=p['strong_intent_ratio'])
    return {'status':status,'unique_purchase_intent_comments':len(intent),'sample_size':sample,
            'raw_observations':len(comments),'intent_ratio':ratio,'unique_authors':len(authors),
            'strength':'STRONG' if strong else 'OBSERVED' if intent else 'NOT_OBSERVED' if sample else None,
            'intent_types':{k:types[k] for k in config['purchase_types']},
            'evidence_ids':sorted({i for c in intent for i in c['evidence_ids']}),
            'consumer_classes':{k:{'count':len(ids),'evidence_ids':ids} for k,ids in classes.items()},
            'dedupe_basis':'normalized text across captures and anonymous copies; conservative lower bound',
            'rules_version':config['version']}


def comment_key(comment):
    if comment.get('comment_id'):
        return 'id:'+comment['comment_id']
    value=[comment.get('author_username'),comment['text'],comment.get('timestamp'),comment.get('is_reply')]
    return 'visible:'+hashlib.sha256(json.dumps(value,ensure_ascii=False).encode()).hexdigest()


def consumer_signals_v2(comments):
    """Author-aware extension. Legacy consumer_signals stays stable for Identity.

    Known authors with the same text are distinct observations; repeated captures
    of the same author/text are not, even when platform IDs are missing. Anonymous copies of attributed
    text are retained as duplicate provenance, not independent demand.
    """
    policy=json.loads((TERMS_PATH.parent/'virality_quality.json').read_text(encoding='utf-8'))
    legacy=json.loads((TERMS_PATH.parent/'consumer_signals.json').read_text(encoding='utf-8'))
    def fold(text):
        text=''.join(c for c in unicodedata.normalize('NFKD',normalize(text)) if not unicodedata.combining(c))
        return ' '.join(re.findall(r'\w+',text))
    def author(c):return normalize(c.get('author_username') or '').lstrip('@')
    known_texts={fold(c['text']) for c in comments if author(c)}
    unique={};duplicate_ids=[]
    for c in comments:
        text=fold(c['text']);who=author(c)
        if not text or text in legacy['noise']:continue
        if not who and text in known_texts:
            if c.get('id') is not None:duplicate_ids.append(c['id'])
            continue
        # A capture may expose a platform ID only sometimes. Author/text remains
        # the stable identity across those captures and repeated identical posts.
        key=('author_text',who,text)
        entry=unique.setdefault(key,{'text':text,'raw_text':c['text'],'author':who or None,'evidence_ids':[], 'observed_at':c.get('observed_at')})
        if c.get('id') is not None:entry['evidence_ids'].append(c['id'])
        if c.get('observed_at') and (not entry['observed_at'] or c['observed_at']<entry['observed_at']):entry['observed_at']=c['observed_at']
    mappings={'WHERE_TO_BUY':'where_to_buy','LINK_REQUEST':'link_request','PRICE_QUESTION':'price_question','PURCHASE_DECLARATION':'purchase_statement',
              'POSITIVE_REACTION':'positive_reaction','NEGATIVE_REACTION':'negative_reaction','PRODUCT_COMPLAINT':'product_complaint','QUALITY_COMPLAINT':'quality_complaint','QUESTION':'question'}
    patterns={key:legacy['patterns'][value] for key,value in mappings.items()};patterns.update(policy['patterns'])
    intent_types=['WHERE_TO_BUY','LINK_REQUEST','PRICE_QUESTION','WANT','NEED','PURCHASE_DECLARATION','AVAILABILITY_QUESTION']
    types={name:{'comments':0,'authors':set(),'evidence_ids':[]} for name in patterns}
    intent_authors=set();all_authors=set();intent=[]
    for entry in unique.values():
        text=entry['text'];hits={key for key,values in patterns.items() if any(re.search(p,text) for p in values)}
        for key,values in policy['negations'].items():
            if any(re.search(p,text) for p in values):
                hits.discard(key)
                if key=='USEFUL':hits.discard('POSITIVE_REACTION');hits.add('NEGATIVE_REACTION')
        if '?' in entry['raw_text']:hits.add('QUESTION')
        if hits & {'DOES_NOT_WORK','BROKE','FAKE'}:hits.add('PRODUCT_COMPLAINT')
        if hits & {'BROKE','HARD_TO_USE'}:hits.add('QUALITY_COMPLAINT')
        entry['types']=sorted(hits)
        if entry['author']:all_authors.add(entry['author'])
        for key in hits:
            types[key]['comments']+=1;types[key]['evidence_ids'].extend(entry['evidence_ids'])
            if entry['author']:types[key]['authors'].add(entry['author'])
        if hits & set(intent_types):
            intent.append(entry)
            if entry['author']:intent_authors.add(entry['author'])
    sample=len(unique);known=sum(bool(e['author']) for e in unique.values());p=policy['purchase']
    ratio=len(intent)/sample if sample else None;author_ratio=len(intent_authors)/len(all_authors) if all_authors else None
    measured=sample>=p['measured_sample'] and known/sample>=p['known_author_coverage']
    strength=None if not sample else 'STRONG' if measured and len(intent_authors)>=p['strong_authors'] and author_ratio>=p['strong_ratio'] else 'MODERATE' if len(intent_authors)>=p['moderate_authors'] and author_ratio>=p['moderate_ratio'] else 'WEAK'
    return {'version':policy['version'],'status':'measured' if measured else 'partial' if sample else 'insufficient_data',
        'strength':strength,'sample_size':sample,'raw_observations':len(comments),'known_author_comments':known,
        'unique_authors':len(all_authors),'unique_intent_authors':len(intent_authors),'intent_comments':len(intent),
        'intent_ratio':ratio,'author_intent_ratio':author_ratio,
        'intent_types':{key:{'comments':types[key]['comments'],'unique_authors':len(types[key]['authors']),'evidence_ids':sorted(set(types[key]['evidence_ids']))} for key in intent_types},
        'consumer_types':{key:{'comments':value['comments'],'unique_authors':len(value['authors']),'authors':sorted(value['authors']),'evidence_ids':sorted(set(value['evidence_ids']))} for key,value in types.items()},
        'evidence_ids':sorted({i for e in intent for i in e['evidence_ids']}),'duplicate_evidence_ids':sorted(duplicate_ids),
        'entries':list(unique.values()),'dedupe_basis':'normalized author+text across platform IDs; anonymous attributed-text copies excluded',
        'not_sales':True}


def migrate(con):
    con.execute('''CREATE TABLE IF NOT EXISTS comment_samples (
        id INTEGER PRIMARY KEY AUTOINCREMENT,video_id INTEGER NOT NULL REFERENCES videos(id),
        command_id INTEGER NOT NULL UNIQUE,observed_at TEXT NOT NULL,target_count INTEGER NOT NULL,
        stop_reason TEXT NOT NULL,scroll_steps INTEGER NOT NULL,extractor_version TEXT NOT NULL,
        signals_json TEXT NOT NULL,terms_config_json TEXT NOT NULL,diagnostics_json TEXT NOT NULL)''')
    con.execute('''CREATE TABLE IF NOT EXISTS comment_observations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,sample_id INTEGER NOT NULL REFERENCES comment_samples(id),
        video_id INTEGER NOT NULL REFERENCES videos(id),comment_key TEXT NOT NULL,comment_id TEXT,
        author_username TEXT,text TEXT NOT NULL,likes INTEGER,likes_raw TEXT,timestamp TEXT,
        position INTEGER NOT NULL,is_reply INTEGER,reply_count INTEGER,source TEXT NOT NULL CHECK(source='comments_visible'),
        observed_at TEXT NOT NULL,raw_visible_text TEXT NOT NULL,extraction_method TEXT NOT NULL,
        confidence REAL NOT NULL,extractor_version TEXT NOT NULL,UNIQUE(sample_id,comment_key))''')
    con.execute('CREATE INDEX IF NOT EXISTS comments_video_sample ON comment_samples(video_id,id DESC)')


def save_sample(con, sample, command_id, now):
    canonical,strong_id=video_identity(sample['video_url'])
    video=con.execute('SELECT id FROM videos WHERE video_id=? AND source=?', (strong_id,'tiktok')).fetchone()
    if not video or not con.execute('SELECT 1 FROM video_detail_observations WHERE video_id=?',(video['id'],)).fetchone():
        return False
    unique={}
    for comment in sample['comments']:
        unique.setdefault(comment_key(comment),comment)
    comments=list(unique.values())
    config=json.loads(TERMS_PATH.read_text(encoding='utf-8'))
    summary=signals(comments,config)
    cursor=con.execute('''INSERT INTO comment_samples(video_id,command_id,observed_at,target_count,stop_reason,
        scroll_steps,extractor_version,signals_json,terms_config_json,diagnostics_json) VALUES (?,?,?,?,?,?,?,?,?,?)''',
        (video['id'],command_id,now,sample['target_count'],sample['stop_reason'],sample['scroll_steps'],
         sample['extractor_version'],json.dumps(summary),json.dumps(config,ensure_ascii=False),json.dumps(sample['diagnostics'])))
    for position,(key,comment) in enumerate(unique.items(),1):
        con.execute('''INSERT INTO comment_observations(sample_id,video_id,comment_key,comment_id,author_username,text,
            likes,likes_raw,timestamp,position,is_reply,reply_count,source,observed_at,raw_visible_text,extraction_method,
            confidence,extractor_version) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (cursor.lastrowid,video['id'],key,comment.get('comment_id'),comment.get('author_username'),comment['text'],
             comment.get('likes'),comment.get('likes_raw'),comment.get('timestamp'),position,comment.get('is_reply'),
             comment.get('reply_count'),'comments_visible',now,comment['raw_visible_text'],comment['extraction_method'],
             comment['confidence'],comment['extractor_version']))
    con.execute('INSERT INTO events(created_at,level,event_type,message) VALUES (?,?,?,?)',
                (now,'INFO','comments',f'Comments sample #{command_id}: {len(comments)} stored; {sample["stop_reason"]}; no engagement'))
    return True


def latest_samples(con, video_id=None, include_comments=False):
    rows=con.execute('''SELECT s.*,v.video_id AS platform_video_id FROM comment_samples s JOIN videos v ON v.id=s.video_id
        WHERE s.id=(SELECT MAX(x.id) FROM comment_samples x WHERE x.video_id=s.video_id)
        AND (? IS NULL OR v.video_id=?) ORDER BY s.id DESC''',(video_id,video_id)).fetchall()
    items=[]
    for row in rows:
        comments=[dict(r) for r in con.execute('SELECT * FROM comment_observations WHERE sample_id=? ORDER BY position',(row['id'],))]
        coverage={field:round(100*sum(comment[field] is not None for comment in comments)/len(comments),2) if comments else 0.0
                  for field in ('comment_id','author_username','text','likes','timestamp','is_reply')}
        item={key:row[key] for key in ('id','command_id','observed_at','target_count','stop_reason','scroll_steps','extractor_version')}
        item.update(video_id=row['platform_video_id'],signals=json.loads(row['signals_json']),coverage=coverage,
                    diagnostics=json.loads(row['diagnostics_json']))
        if include_comments:
            for comment in comments:
                comment['video_id']=row['platform_video_id']
                comment['is_reply']=bool(comment['is_reply']) if comment['is_reply'] is not None else None
            item['comments']=comments
        items.append(item)
    return {'items':items}
