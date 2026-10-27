"""Human-only gold labels and offline benchmark; never runs or modifies detection."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json

VERSION='gold-set-v1'
PROTOCOL='detection-benchmark-v1'
REVIEW_METHODS=('persisted_only','video_opened','lens_assisted')
FN_REASONS=('visual_only','visual_helped','generic_caption','missing_enrichment','unknown_vocabulary','caption_missing','product_only_in_comments','generic_phrase','unsupported_language','insufficient_text','normalization_failure','other')
FP_REASONS=('generic_term','wrong_context','creator_context_leak','search_query_leak','comment_noise','other')
LANGUAGES=('pt','en','ar','es','unknown')
LANGUAGE_MIN_REVIEWED=5
AUTO_BENCHMARK_MIN_REVIEWS=15


def now():return datetime.now(timezone.utc).isoformat()
def encoded(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'))
def digest(value):return hashlib.sha256(encoded(value).encode()).hexdigest()


def migrate(con):
    con.execute('''CREATE TABLE IF NOT EXISTS gold_video_labels (
      video_id INTEGER NOT NULL REFERENCES videos(id),review_version TEXT NOT NULL,
      review_status TEXT NOT NULL DEFAULT 'pending' CHECK(review_status IN ('pending','reviewed')),
      product_presence TEXT CHECK(product_presence IN ('yes','no','unclear')),canonical_product_name TEXT,raw_product_name TEXT,
      specificity TEXT CHECK(specificity IN ('specific','broad','unclear')),review_notes TEXT NOT NULL DEFAULT '',
      language TEXT NOT NULL DEFAULT 'unknown' CHECK(language IN ('pt','en','ar','es','unknown')),
      fn_reason TEXT,fp_reason TEXT,reviewed_at TEXT,reviewer_type TEXT CHECK(reviewer_type='human'),
      PRIMARY KEY(video_id,review_version))''')
    con.execute('''CREATE TABLE IF NOT EXISTS gold_candidate_reviews (
      video_id INTEGER NOT NULL REFERENCES videos(id),candidate_id INTEGER NOT NULL REFERENCES product_candidates(id),
      review_version TEXT NOT NULL,name_match TEXT NOT NULL CHECK(name_match IN ('exact','acceptable','wrong','unreviewed')),
      evidence_quality TEXT CHECK(evidence_quality IN ('strong','weak','wrong')),notes TEXT NOT NULL,
      reviewed_at TEXT NOT NULL,reviewer_type TEXT NOT NULL CHECK(reviewer_type='human'),
      PRIMARY KEY(video_id,candidate_id,review_version))''')
    con.execute('''CREATE TABLE IF NOT EXISTS gold_review_history (
      id INTEGER PRIMARY KEY,video_id INTEGER NOT NULL REFERENCES videos(id),review_version TEXT NOT NULL,
      snapshot_json TEXT NOT NULL,reviewed_at TEXT NOT NULL)''')
    con.execute('''CREATE TABLE IF NOT EXISTS detection_benchmark_runs (
      id INTEGER PRIMARY KEY,created_at TEXT NOT NULL,gold_set_version TEXT NOT NULL,detector_version TEXT NOT NULL,
      vocabulary_version TEXT NOT NULL,rules_version TEXT NOT NULL,reviewed_videos INTEGER NOT NULL,
      tp INTEGER NOT NULL,fp INTEGER NOT NULL,fn INTEGER NOT NULL,tn INTEGER NOT NULL,precision REAL,recall REAL,f1 REAL,
      fingerprint TEXT NOT NULL UNIQUE,report_json TEXT NOT NULL)''')
    if 'review_method' not in {r[1] for r in con.execute('PRAGMA table_info(gold_video_labels)')}:
        con.execute("ALTER TABLE gold_video_labels ADD COLUMN review_method TEXT CHECK(review_method IN ('persisted_only','video_opened','lens_assisted'))")
    con.execute('INSERT OR IGNORE INTO gold_video_labels(video_id,review_version) SELECT id,? FROM videos',(VERSION,))
    con.execute('INSERT OR IGNORE INTO schema_migrations(name) VALUES (?)',(VERSION,))


def predictions(con):
    grouped={}
    for row in con.execute('''SELECT DISTINCT e.video_id,c.id,c.canonical_name,c.detection_version,c.manual_status
      FROM product_candidate_evidence e JOIN product_candidates c ON c.id=e.candidate_id
      WHERE e.video_id IS NOT NULL ORDER BY e.video_id,c.id'''):
        # Baseline measures emitted hypotheses, including later local rejection; never rewrites predictions.
        grouped.setdefault(row['video_id'],[]).append(dict(row))
    return grouped


def review_category(c):
    """Same strict name-aware eligibility as benchmark; no inferred human labels."""
    if not c['human_reviewed']:return 'pending'
    if c['product_presence']=='unclear':return 'unclear'
    detected=bool(c['candidates'])
    if c['product_presence']=='yes' and detected:
        matches=[p['human_review']['name_match'] if p.get('human_review') else 'unreviewed' for p in c['candidates']]
        if any(m in ('exact','acceptable') for m in matches):return 'tp'
        if not all(m=='wrong' for m in matches):return 'pending_name_match'
        detected=False
    return ('tp' if detected else 'fn') if c['product_presence']=='yes' else ('fp' if detected else 'tn')


def listing(con):
    predicted=predictions(con);items=[]
    reviews={(r['video_id'],r['candidate_id']):dict(r) for r in con.execute('SELECT * FROM gold_candidate_reviews WHERE review_version=?',(VERSION,))}
    for row in con.execute('''SELECT v.id AS video_id,v.video_id AS platform_video_id,v.canonical_url AS url,v.caption,v.creator_username,
      v.thumbnail_url,g.* FROM videos v LEFT JOIN gold_video_labels g ON g.video_id=v.id AND g.review_version=? ORDER BY v.id''',(VERSION,)):
        item=dict(row);item['review_status']=item['review_status'] or 'pending';item['review_version']=VERSION
        item['candidates']=[{**p,'human_review':reviews.get((item['video_id'],p['id']))} for p in predicted.get(item['video_id'],[])]
        item['human_reviewed']=item['review_status']=='reviewed' and item['reviewer_type']=='human'
        item['benchmark_category']=review_category(item)
        items.append(item)
    counts=Counter(i['product_presence'] for i in items if i['human_reviewed'])
    return {'gold_set_version':VERSION,'items':items,'progress':{'total':len(items),'reviewed':sum(i['human_reviewed'] for i in items),
      'pending':sum(not i['human_reviewed'] for i in items),'yes':counts['yes'],'no':counts['no'],'unclear':counts['unclear']},
      'filter_counts':dict(Counter(i['benchmark_category'] for i in items)), 'review_methods':REVIEW_METHODS,'fn_reasons':FN_REASONS,'fp_reasons':FP_REASONS,'languages':LANGUAGES}


def detail(con,video_id):
    item=next((i for i in listing(con)['items'] if i['video_id']==video_id),None)
    if item is None:return None
    sample=con.execute('SELECT * FROM comment_samples WHERE video_id=? ORDER BY id DESC LIMIT 1',(video_id,)).fetchone()
    item['comment_sample']=dict(sample) if sample else None
    item['comments']=[dict(r) for r in con.execute('SELECT id,author_username,text,sample_id FROM comment_observations WHERE sample_id=? ORDER BY position',(sample['id'],))] if sample else []
    item['evidence']=[dict(r) for r in con.execute('SELECT * FROM product_candidate_evidence WHERE video_id=? ORDER BY id',(video_id,))]
    item['unresolved_phrases']=[dict(r) for r in con.execute('SELECT * FROM unresolved_product_phrases WHERE video_id=? ORDER BY id',(video_id,))]
    gap=con.execute('SELECT * FROM product_detection_gaps WHERE video_id=? ORDER BY run_id DESC LIMIT 1',(video_id,)).fetchone() if con.execute("SELECT 1 FROM sqlite_master WHERE name='product_detection_gaps'").fetchone() else None
    item['detection_gap']=dict(gap) if gap else None
    item['source_observations']={}
    for table in ('search_observations','video_detail_observations'):
        source=con.execute(f'SELECT id,observed_at,extractor_version,fields_json,field_evidence_json FROM {table} WHERE video_id=? ORDER BY id DESC LIMIT 1',(video_id,)).fetchone()
        if source:item['source_observations'][table]=dict(source)
    profile=con.execute('''SELECT p.* FROM creator_profile_observations p JOIN video_creators vc ON vc.creator_id=p.creator_id
      WHERE vc.video_id=? ORDER BY p.id DESC LIMIT 1''',(video_id,)).fetchone()
    item['creator_profile_context']=dict(profile) if profile else None
    return item


def save_review(con,video_id,payload):
    if not con.execute('SELECT 1 FROM videos WHERE id=?',(video_id,)).fetchone():raise KeyError('Video not found')
    if payload.get('human_reviewed') is not True:raise ValueError('Explicit human review is required')
    if payload.get('review_version')!=VERSION:raise ValueError('Unsupported gold set version')
    if payload.get('product_presence') not in ('yes','no','unclear'):raise ValueError('Product presence must be explicitly selected')
    if payload.get('specificity') not in ('specific','broad','unclear'):raise ValueError('Specificity must be explicitly selected')
    if payload.get('language','unknown') not in LANGUAGES:raise ValueError('Unsupported language')
    if payload.get('fn_reason') is not None and payload['fn_reason'] not in FN_REASONS:raise ValueError('Invalid FN reason')
    if payload.get('review_method') is not None and payload['review_method'] not in REVIEW_METHODS:raise ValueError('Invalid review method')
    if payload.get('fp_reason') is not None and payload['fp_reason'] not in FP_REASONS:raise ValueError('Invalid FP reason')
    allowed={p['id'] for p in predictions(con).get(video_id,[])};seen=set()
    for c in payload.get('candidate_reviews',[]):
        if c['candidate_id'] not in allowed or c['candidate_id'] in seen:raise ValueError('Candidate is not unique and observed in this video')
        seen.add(c['candidate_id'])
        if c['name_match'] not in ('exact','acceptable','wrong','unreviewed'):raise ValueError('Invalid name match')
        if c.get('evidence_quality') not in (None,'strong','weak','wrong'):raise ValueError('Invalid evidence quality')
    # Omitted candidate reviews preserve prior human decisions.
    current=detail(con,video_id);at=now()
    fields=['product_presence','canonical_product_name','raw_product_name','specificity','review_notes','language','fn_reason','fp_reason','review_method']
    values={k:payload.get(k, 'unknown' if k=='language' else '' if k=='review_notes' else None) for k in fields}
    if 'review_method' not in payload:values['review_method']=current.get('review_method')
    changed=not current['human_reviewed'] or any(current.get(k)!=v for k,v in values.items())
    old_reviews={c['id']:c['human_review'] for c in current['candidates']}
    for c in payload.get('candidate_reviews',[]):
        old=old_reviews.get(c['candidate_id'])
        if old is None and c['name_match']=='unreviewed' and c.get('evidence_quality') is None and not c.get('notes'):continue
        if old is None or any(old.get(k)!=c.get(k,'' if k=='notes' else None) for k in ('name_match','evidence_quality','notes')):changed=True
    if not changed:return current
    con.execute('''INSERT INTO gold_video_labels(video_id,review_version,review_status,product_presence,canonical_product_name,
      raw_product_name,specificity,review_notes,language,fn_reason,fp_reason,review_method,reviewed_at,reviewer_type)
      VALUES (?,?,'reviewed',?,?,?,?,?,?,?,?,?,?,'human') ON CONFLICT(video_id,review_version) DO UPDATE SET
      review_status=excluded.review_status,product_presence=excluded.product_presence,canonical_product_name=excluded.canonical_product_name,
      raw_product_name=excluded.raw_product_name,specificity=excluded.specificity,review_notes=excluded.review_notes,language=excluded.language,
      fn_reason=excluded.fn_reason,fp_reason=excluded.fp_reason,review_method=excluded.review_method,reviewed_at=excluded.reviewed_at,reviewer_type=excluded.reviewer_type''',
      (video_id,VERSION,*[values[k] for k in fields],at))
    for c in payload.get('candidate_reviews',[]):
        old=old_reviews.get(c['candidate_id'])
        if old is None and c['name_match']=='unreviewed' and c.get('evidence_quality') is None and not c.get('notes'):continue
        if old and all(old.get(k)==c.get(k,'' if k=='notes' else None) for k in ('name_match','evidence_quality','notes')):continue
        con.execute('''INSERT INTO gold_candidate_reviews VALUES (?,?,?,?,?,?,?,'human') ON CONFLICT(video_id,candidate_id,review_version)
          DO UPDATE SET name_match=excluded.name_match,evidence_quality=excluded.evidence_quality,notes=excluded.notes,reviewed_at=excluded.reviewed_at''',
          (video_id,c['candidate_id'],VERSION,c['name_match'],c.get('evidence_quality'),c.get('notes',''),at))
    result=detail(con,video_id)
    con.execute('INSERT INTO gold_review_history(video_id,review_version,snapshot_json,reviewed_at) VALUES (?,?,?,?)',
      (video_id,VERSION,encoded({'label':values,'candidate_reviews':[c['human_review'] for c in result['candidates']]}),at))
    return result


def ratio(n,d):return n/d if d else None


def metrics(cases,strict=False):
    counts=Counter();excluded=Counter();fn_reasons=Counter();fp_reasons=Counter()
    for c in cases:
        if not c['human_reviewed']:excluded['pending_review']+=1;continue
        presence=c['product_presence']
        if presence=='unclear':excluded['unclear']+=1;continue
        detected=bool(c['candidates'])
        if strict and presence=='yes' and detected:
            if c['detected_name_match']=='unreviewed':excluded['pending_name_match']+=1;continue
            detected=c['detected_name_match'] in ('exact','acceptable')
        kind=('tp' if detected else 'fn') if presence=='yes' else ('fp' if detected else 'tn')
        counts[kind]+=1
        if kind=='fn':fn_reasons[c.get('fn_reason') or ('wrong_name' if strict and c['candidates'] else 'unclassified')]+=1
        if kind=='fp':fp_reasons[c.get('fp_reason') or 'unclassified']+=1
    tp,fp,fn,tn=(counts[k] for k in ('tp','fp','fn','tn'))
    precision=ratio(tp,tp+fp);recall=ratio(tp,tp+fn)
    return {'tp':tp,'fp':fp,'fn':fn,'tn':tn,'precision':precision,'recall':recall,
      'f1':ratio(2*tp,2*tp+fp+fn),'accuracy':ratio(tp+tn,tp+fp+fn+tn),
      'evaluated_videos':tp+fp+fn+tn,'excluded':dict(excluded),'fn_reasons':dict(fn_reasons),'fp_reasons':dict(fp_reasons)}


def benchmark(con,persist=True):
    from .product_detection import configuration
    from .product_vocabulary import version
    from .candidate_semantics import configuration as identity_configuration
    config=configuration();gold=listing(con);cases=gold['items']
    for c in cases:
        matches=[p['human_review']['name_match'] if p['human_review'] else 'unreviewed' for p in c['candidates']]
        c['detected_name_match']='exact' if 'exact' in matches else 'acceptable' if 'acceptable' in matches else 'wrong' if matches and all(m=='wrong' for m in matches) else 'unreviewed'
        c['detection_presence_correct']=(bool(c['candidates'])==(c['product_presence']=='yes')) if c['human_reviewed'] and c['product_presence'] in ('yes','no') else None
    presence=metrics(cases);strict=metrics(cases,strict=True)
    named=[p['human_review'] for c in cases if c['human_reviewed'] and c['product_presence']=='yes' for p in c['candidates'] if p['human_review'] and p['human_review']['name_match']!='unreviewed']
    naming_counts=Counter(r['name_match'] for r in named)
    language_breakdown={}
    for language in LANGUAGES:
        subset=[c for c in cases if c.get('language')==language]
        p=metrics(subset);s=metrics(subset,True);enough=p['evaluated_videos']>=LANGUAGE_MIN_REVIEWED
        if not enough:
            for values in (p,s):
                for field in ('precision','recall','f1','accuracy'):values[field]=None
        language_breakdown[language]={'presence':p,'strict_name_aware':s,'sufficient_data':enough,
          'minimum_reviewed_for_rates':LANGUAGE_MIN_REVIEWED}
    reviewed=gold['progress']['reviewed'];total=gold['progress']['total']
    stage='final' if total and reviewed==total else 'partial' if reviewed else 'baseline'
    versions={'gold_set_version':VERSION,'benchmark_protocol_version':PROTOCOL,'report_schema_version':'gold-benchmark-report-v1',
      'evaluation_stage':stage,
      'primary_metric':'strict_name_aware','detector_version':config['version'],
      'vocabulary_version':version(con),'rules_version':config['corroboration_version']}
    fingerprint=digest({'versions':versions,'gold':cases,'detector_config':config,'identity_config':identity_configuration(),
      'vocabulary_terms':[dict(r) for r in con.execute('SELECT * FROM product_vocabulary_terms ORDER BY normalized_phrase')]})
    report={**versions,'progress':gold['progress'],'reviewed_videos':gold['progress']['reviewed'],
      'evaluation_label':{'partial':'PARTIAL GOLD SET','final':'FINAL GOLD SET','baseline':'UNREVIEWED BASELINE'}[stage],
      'configuration_snapshot':{'detector':config,'identity':identity_configuration(),
        'vocabulary_terms':[dict(r) for r in con.execute('SELECT * FROM product_vocabulary_terms ORDER BY normalized_phrase')]},
      'primary_metric':'strict_name_aware','presence':presence,'strict_name_aware':strict,**strict,
      'accepted_candidate_tp':strict['tp'],'presence_detection_accuracy':presence['accuracy'],
      'product_naming_accuracy':ratio(naming_counts['exact']+naming_counts['acceptable'],len(named)),
      'naming':{'reviewed_candidate_occurrences':len(named),'counts':dict(naming_counts)},
      'candidate_coverage':ratio(sum(bool(c['candidates']) for c in cases),len(cases)),
      'candidate_coverage_videos':sum(bool(c['candidates']) for c in cases),'library_videos':len(cases),
      'language_breakdown':language_breakdown,
      'metric_definitions':{'presence':'Presence only: yes + any emitted candidate = TP; no + candidate = FP; yes + no candidate = FN; no + no candidate = TN',
        'primary':'Strict name-aware detection: a TP requires an exact/acceptable human-reviewed candidate name',
        'strict':'TP requires a human exact/acceptable name; wrong-name positive becomes strict FN (no acceptable candidate); pending name match excluded',
        'naming':'Human exact/acceptable / human named candidate occurrences on product-presence=yes videos; unreviewed excluded'},
      'candidate_audit':[{'candidate_id':p['id'],'candidate_name':p['canonical_name'],'video_id':c['video_id'],'url':c['url'],
        'human_product_presence':c['product_presence'] if c['human_reviewed'] else None,
        'name_match':p['human_review']['name_match'] if p['human_review'] else 'unreviewed',
        'evidence_quality':p['human_review']['evidence_quality'] if p['human_review'] else None,
        'notes':p['human_review']['notes'] if p['human_review'] else '',
        'review_status':'human-reviewed' if p['human_review'] else 'pending'} for c in cases for p in c['candidates']],
      'cases':cases,'fingerprint':fingerprint,'limitations':['Human labels only; unclear/pending excluded','Presence is not name correctness','Coverage is not quality','Small or unreviewed language groups do not establish performance']}
    if persist:
        old=con.execute('SELECT id,created_at,report_json FROM detection_benchmark_runs WHERE fingerprint=?',(fingerprint,)).fetchone()
        if old:return json.loads(old['report_json'])
        at=now()
        run=con.execute('''INSERT INTO detection_benchmark_runs(created_at,gold_set_version,detector_version,vocabulary_version,rules_version,
          reviewed_videos,tp,fp,fn,tn,precision,recall,f1,fingerprint,report_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
          (at,VERSION,versions['detector_version'],versions['vocabulary_version'],versions['rules_version'],gold['progress']['reviewed'],
           strict['tp'],strict['fp'],strict['fn'],strict['tn'],strict['precision'],strict['recall'],strict['f1'],fingerprint,'{}')).lastrowid
        report.update(run_id=run,created_at=at)
        con.execute('UPDATE detection_benchmark_runs SET report_json=? WHERE id=?',(encoded(report),run))
    return report


def automatic_benchmark(con):
    progress=listing(con)['progress']
    if progress['reviewed']>=AUTO_BENCHMARK_MIN_REVIEWS or (progress['total'] and progress['reviewed']==progress['total']):
        return benchmark(con)
    return None


def export_files(gold,report):
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]/'data'
    root.mkdir(exist_ok=True)
    for name,value in [('gold_set_v1.json',gold),('detection_benchmark_v1.json',report)]:
        path=root/name;temp=path.with_suffix('.tmp')
        temp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)
