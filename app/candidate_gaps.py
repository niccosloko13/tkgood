"""Explain missed coverage and retain unverified lexical suggestions for local review."""
import json
import re
from collections import Counter, defaultdict

REASONS=('no_text','generic_only','unknown_product_phrase','insufficient_evidence','noise_filtered','unsupported_language','other')


def migrate(con):
    for statement in [
        '''CREATE TABLE IF NOT EXISTS product_detection_gaps (
        run_id INTEGER NOT NULL REFERENCES product_detection_runs(id),video_id INTEGER NOT NULL REFERENCES videos(id),
        reason TEXT NOT NULL,explanation TEXT NOT NULL,source_snapshot_json TEXT NOT NULL,analyzed_at TEXT NOT NULL,
        analysis_version TEXT NOT NULL,PRIMARY KEY(run_id,video_id))''',
        '''CREATE TABLE IF NOT EXISTS unresolved_product_phrases (
        id INTEGER PRIMARY KEY,video_id INTEGER NOT NULL REFERENCES videos(id),raw_phrase TEXT NOT NULL,
        normalized_phrase TEXT NOT NULL,signature TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending'
        CHECK(status IN ('pending','approved','rejected')),first_seen_at TEXT NOT NULL,last_seen_at TEXT NOT NULL,
        discovery_version TEXT NOT NULL,UNIQUE(video_id,normalized_phrase))''',
        '''CREATE TABLE IF NOT EXISTS unresolved_phrase_observations (
        id INTEGER PRIMARY KEY,phrase_id INTEGER NOT NULL REFERENCES unresolved_product_phrases(id),
        source_entity_type TEXT NOT NULL,source_entity_id TEXT NOT NULL,raw_text TEXT NOT NULL,source_url TEXT NOT NULL,
        observed_at TEXT NOT NULL,method TEXT NOT NULL,
        UNIQUE(phrase_id,source_entity_type,source_entity_id,raw_text))''',
        '''CREATE TABLE IF NOT EXISTS product_vocabulary_reviews (
        id INTEGER PRIMARY KEY,phrase_id INTEGER NOT NULL REFERENCES unresolved_product_phrases(id),
        normalized_phrase TEXT NOT NULL,decision TEXT NOT NULL CHECK(decision IN ('approved','rejected')),
        note TEXT NOT NULL,reviewed_at TEXT NOT NULL)''',
    ]:
        con.execute(statement)


def unresolved_suggestions(sources, config):
    from .product_detection import normalize,extractProductCandidatePhrases
    settings=config['gap_discovery']; results={};recurring=defaultdict(set);raw_ngrams={}
    ignored=set(settings['ignored_tokens']);heads=set(settings['noun_heads'])
    for source in sources:
        if source['kind'] not in settings['recurring_sources']:
            continue
        text=source['text']
        for pattern in settings['unknown_noun_patterns']:
            for match in re.finditer(r'(?<!\w)(?:'+pattern+r')(?!\w)',text,re.I):
                raw=match.group(); normalized=normalize(raw);tokens=normalized.split()
                if not settings['minimum_tokens']<=len(tokens)<=settings['maximum_tokens']:
                    continue
                if extractProductCandidatePhrases(raw,config) or tokens[0] in ignored:
                    continue
                results[(normalized,source['entity'],source['key'])]=(raw,source,'lexical_noun_pattern')
        # Recurrence is inspected across distinct text, not repeated captures.
        words=list(re.finditer(r'[^\W_]+',text,re.UNICODE))
        for size in range(settings['minimum_tokens'],settings['maximum_tokens']+1):
            for index in range(len(words)-size+1):
                group=words[index:index+size];raw=text[group[0].start():group[-1].end()]
                tokens=normalize(raw).split();norm=' '.join(tokens)
                if any(t in ignored for t in tokens) or (settings['require_head_for_recurring'] and tokens[-1] not in heads):
                    continue
                if norm in settings['generic_phrases'] or norm in settings['noise_phrases'] or extractProductCandidatePhrases(raw,config):
                    continue
                recurring[norm].add(normalize(text));raw_ngrams[(norm,source['entity'],source['key'])]=(raw,source,'recurring_phrase')
    for key,value in raw_ngrams.items():
        if len(recurring[key[0]])>=settings['recurrence_minimum']:
            results.setdefault(key,value)
    # Bound distinct phrases per video while retaining all their source records.
    allowed=set(sorted({key[0] for key in results})[:settings['maximum_phrases_per_video']])
    return [value for key,value in results.items() if key[0] in allowed]


def classify_gap(sources, suggestions, config):
    from .product_detection import normalize
    settings=config['gap_discovery']
    texts=[s['text'] for s in sources if s['kind'] in settings['recurring_sources']]
    useful=[normalize(t) for t in texts if normalize(t)]
    if not useful:
        return 'no_text','No useful persisted caption or sampled comment text'
    if suggestions:
        return 'unknown_product_phrase','Unverified noun-like phrase outside the approved detector vocabulary'
    # Script coverage, not guessed language: Arabic and Latin are supported.
    if not any(re.search(pattern,t) for pattern in settings['supported_script_patterns'] for t in texts) and any(any(ch.isalpha() for ch in t) for t in texts):
        return 'unsupported_language','Text uses a script outside the configured lexical foundation'
    captions=[normalize(s['text']) for s in sources if s['kind']=='caption' and normalize(s['text'])]
    if captions:
        generic=set(settings['generic_tokens'])
        if all(t in settings['generic_phrases'] or set(t.split())<=generic for t in captions):
            return 'generic_only','Only generic category words, without a specific product phrase'
        remaining=[]
        for text in captions:
            for phrase in sorted(settings['noise_phrases'],key=len,reverse=True):
                text=re.sub(r'(?<!\w)'+re.escape(phrase)+r'(?!\w)',' ',text)
            remaining.append(normalize(text))
        if not any(remaining):
            return 'noise_filtered','Caption consists only of promotional or navigation noise'
        if all(not t or t in settings['generic_phrases'] or set(t.split())<=generic for t in remaining):
            return 'generic_only','Promotional context removed; remaining text is only a generic category'
    return 'insufficient_evidence','Persisted text describes a use, reaction or question without an identifiable product phrase'


def analyze_gaps(con, videos, run_id, config, now):
    from .product_detection import inputs,normalize
    from .candidate_corroboration import signature
    counts=Counter(); gaps=[]
    for video in videos:
        # Use all retained identity evidence, not only matches produced this run.
        if con.execute("SELECT 1 FROM product_candidate_evidence WHERE video_id=? AND evidence_type NOT IN ('profile_link','external_link','search_query')",(video['id'],)).fetchone():
            continue
        _,sources=inputs(con,video)
        suggestions=unresolved_suggestions(sources,config)
        reason,explanation=classify_gap(sources,suggestions,config)
        phrase_ids=set()
        for raw,source,method in suggestions:
            normalized=normalize(raw)
            con.execute('''INSERT INTO unresolved_product_phrases(video_id,raw_phrase,normalized_phrase,signature,first_seen_at,last_seen_at,discovery_version)
                VALUES (?,?,?,?,?,?,?) ON CONFLICT(video_id,normalized_phrase) DO UPDATE SET
                first_seen_at=min(first_seen_at,excluded.first_seen_at),last_seen_at=max(last_seen_at,excluded.last_seen_at)''',
                (video['id'],raw,normalized,signature(normalized,config),source['at'],source['at'],config['corroboration_version']))
            pid=con.execute('SELECT id FROM unresolved_product_phrases WHERE video_id=? AND normalized_phrase=?',(video['id'],normalized)).fetchone()[0]
            phrase_ids.add(pid)
            con.execute('''INSERT OR IGNORE INTO unresolved_phrase_observations(phrase_id,source_entity_type,source_entity_id,raw_text,source_url,observed_at,method)
                VALUES (?,?,?,?,?,?,?)''',(pid,source['entity'],source['key'],source['text'],source['url'],source['at'],method))
        snapshot=[{k:s[k] for k in ('kind','entity','key','text','at','url')} for s in sources if s['kind'] in config['gap_discovery']['recurring_sources']]
        con.execute('INSERT INTO product_detection_gaps VALUES (?,?,?,?,?,?,?)',
                    (run_id,video['id'],reason,explanation,json.dumps(snapshot),now,config['corroboration_version']))
        counts[reason]+=1
        gaps.append({'video_id':video['id'],'video_url':video['canonical_url'],'reason':reason,'explanation':explanation,'unresolved_phrase_ids':sorted(phrase_ids)})
    return {'no_candidate_reasons':{reason:counts[reason] for reason in REASONS},'detection_gaps':gaps,
            'unresolved_phrases_total':con.execute('SELECT count(*) FROM unresolved_product_phrases').fetchone()[0]}


def unresolved_records(con):
    items=[]
    for row in con.execute('SELECT u.*,v.canonical_url AS video_url FROM unresolved_product_phrases u JOIN videos v ON v.id=u.video_id ORDER BY u.id'):
        item=dict(row)
        item['observations']=[dict(r) for r in con.execute('SELECT * FROM unresolved_phrase_observations WHERE phrase_id=? ORDER BY id',(row['id'],))]
        item['reviews']=[dict(r) for r in con.execute('SELECT * FROM product_vocabulary_reviews WHERE phrase_id=? ORDER BY id',(row['id'],))]
        items.append(item)
    return items


def gap_report(con):
    row=con.execute("SELECT * FROM product_detection_runs WHERE status='succeeded' ORDER BY id DESC LIMIT 1").fetchone()
    if not row:
        return {'run_id':None,'detection_gaps':[],'no_candidate_reasons':{r:0 for r in REASONS}}
    return json.loads(row['report_json'])


def review_phrase(con, phrase_id, decision, note, now):
    row=con.execute('SELECT * FROM unresolved_product_phrases WHERE id=?',(phrase_id,)).fetchone()
    if not row:
        return None
    previous=con.execute('SELECT decision,note FROM product_vocabulary_reviews WHERE phrase_id=? ORDER BY id DESC LIMIT 1',(phrase_id,)).fetchone()
    if not previous or previous['decision']!=decision or previous['note']!=note:
        con.execute('INSERT INTO product_vocabulary_reviews(phrase_id,normalized_phrase,decision,note,reviewed_at) VALUES (?,?,?,?,?)',
                    (phrase_id,row['normalized_phrase'],decision,note,now))
    con.execute('UPDATE unresolved_product_phrases SET status=? WHERE id=?',(decision,phrase_id))
    from .product_vocabulary import apply_decision,version
    changed=apply_decision(con,row,decision,now)
    return {'phrase_id':phrase_id,'status':decision,'detector_vocabulary_changed':changed,
            'vocabulary_version':version(con),'detection_run_required':True}
