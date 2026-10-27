"""Independent support and conservative lexical relations, never product merges."""
import json
from collections import defaultdict
from itertools import combinations


def migrate(con):
    statements = [
        '''CREATE TABLE IF NOT EXISTS candidate_evidence_groups (
        evidence_id INTEGER PRIMARY KEY REFERENCES product_candidate_evidence(id),
        candidate_id INTEGER NOT NULL REFERENCES product_candidates(id),
        group_key TEXT NOT NULL, group_type TEXT NOT NULL, identity_support INTEGER NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS candidate_relationships (
        id INTEGER PRIMARY KEY, candidate_a INTEGER NOT NULL REFERENCES product_candidates(id),
        candidate_b INTEGER NOT NULL REFERENCES product_candidates(id), relationship_type TEXT NOT NULL,
        score REAL NOT NULL, reason TEXT NOT NULL, evidence_json TEXT NOT NULL,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL, relationship_version TEXT NOT NULL,
        CHECK(candidate_a < candidate_b), UNIQUE(candidate_a,candidate_b,relationship_type))''',
    ]
    for statement in statements:
        con.execute(statement)
    columns={r['name'] for r in con.execute('PRAGMA table_info(product_candidates)')}
    if 'signature' not in columns:
        con.execute('ALTER TABLE product_candidates ADD COLUMN signature TEXT')


def signature(phrase, config):
    from .product_detection import normalize
    tokens=normalize(phrase).split()
    # Only explicitly listed marketing bundles disappear. Model numbers survive.
    for sequence in config['relationships']['signature_remove_sequences']:
        if tokens[:len(sequence)]==sequence:
            tokens=tokens[len(sequence):]
    return ' '.join(tokens)


def lexical_relation(a, b, config):
    """Subset expansion plus specific-token guard, not a fuzzy string threshold."""
    settings=config['relationships']
    ta=signature(a,config).split(); tb=signature(b,config).split()
    if min(len(ta),len(tb))<settings['minimum_phrase_tokens']:
        return None
    sa,sb=set(ta),set(tb)
    specific=(sa & sb)-set(settings['generic_tokens'])
    if len(specific)<settings['minimum_specific_shared_tokens']:
        return None
    # Numbers and model tokens are never discarded to force a match.
    if {t for t in sa if any(ch.isdigit() for ch in t)} != {t for t in sb if any(ch.isdigit() for ch in t)}:
        return None
    if not (sa<=sb or sb<=sa):
        return None
    if len(sa ^ sb)>settings['maximum_extra_tokens']:
        return None
    if len(sa & sb)<settings['minimum_specific_combination']:
        return None
    return {'shared_specific_tokens':sorted(specific),'signature_a':signature(a,config),'signature_b':signature(b,config)}


def evidence_diversity(con, evidence, config):
    from .product_detection import normalize
    direct_types={'caption','hashtag','video_metadata'}
    context_types={'profile_link','external_link','search_query'}
    groups={}; direct_videos=set(); creator_keys=set(); commenters=set(); comment_texts=set();observed_creators=set();observed_videos=set()
    comment_by_video=defaultdict(set); creator_by_video={}; searches=set(); source_types=set(); identity_types=set();bio_owners={}
    for e in evidence:
        kind=e['evidence_type']; vid=e['video_id']; source_types.add(kind)
        if kind not in context_types:
            identity_types.add(kind)
            if vid is not None:
                observed_videos.add(vid)
            observed_creator=con.execute('SELECT username FROM creators WHERE creator_id=?',(e['creator_id'],)).fetchone()
            if not observed_creator and vid is not None:
                observed_creator=con.execute('SELECT creator_username FROM videos WHERE id=?',(vid,)).fetchone()
            if observed_creator and observed_creator[0]:
                observed_creators.add(observed_creator[0].strip().lstrip('@').casefold())
        # Creator metadata is a creator assertion, not a new video assertion each
        # time a profile observation is attached to another video.
        if kind=='creator_bio':
            key=f"creator:{e['creator_id']}" if e['creator_id'] else f"unattributed:{e['id']}"
            group_type='creator'; identity=True
            owner=con.execute('SELECT username FROM creators WHERE creator_id=?',(e['creator_id'],)).fetchone()
            if owner:
                bio_owners[key]=owner[0].strip().lstrip('@').casefold()
        elif kind=='comment':
            author=(e.get('commenter') or '').strip().lstrip('@').casefold()
            key=f'commenter:{author}' if author else f'video:{vid}'
            group_type='commenter' if author else 'video'; identity=bool(author)
            if author:
                commenters.add(author)
                text=normalize(e['raw_text'])
                comment_texts.add(text)
                comment_by_video[vid].add((author,text))
        else:
            key=f'video:{vid}'; group_type='video'; identity=kind in direct_types
        con.execute('''INSERT INTO candidate_evidence_groups VALUES (?,?,?,?,?)
            ON CONFLICT(evidence_id) DO UPDATE SET group_key=excluded.group_key,
            group_type=excluded.group_type,identity_support=excluded.identity_support''',
            (e['id'],e['candidate_id'],key,group_type,int(identity)))
        entry=groups.setdefault(key,{'group_key':key,'group_type':group_type,'identity_support':False,'evidence_ids':[]})
        entry['evidence_ids'].append(e['id']); entry['identity_support'] |= identity
        if kind in direct_types and vid is not None:
            direct_videos.add(vid)
            video=con.execute('SELECT creator_username FROM videos WHERE id=?',(vid,)).fetchone()
            creator=con.execute('SELECT username FROM creators WHERE creator_id=?',(e['creator_id'],)).fetchone()
            username=(creator['username'] if creator else video['creator_username'] if video else None)
            if username:
                creator_key=username.strip().lstrip('@').casefold()
                creator_keys.add(creator_key); creator_by_video[vid]=creator_key
            if e['source_entity_type']=='search_observations':
                row=con.execute('SELECT capture_id FROM search_observations WHERE id=?',(e['source_entity_id'].split(':')[0],)).fetchone()
                if row:
                    searches.add((row['capture_id'],vid))
    # Repeated captures of one video are one search origin for diversity.
    independent_searches=len({vid for _,vid in searches})
    # A creator's own bio/comment is not an independent endorsement of their video.
    commenters-=creator_keys
    comment_by_video={vid:{(author,text) for author,text in pairs if author not in creator_keys} for vid,pairs in comment_by_video.items()}
    comment_texts={text for pairs in comment_by_video.values() for _,text in pairs}
    for key,group in groups.items():
        overlapping=(group['group_type']=='creator' and bio_owners.get(key) in creator_keys) or (
            group['group_type']=='commenter' and key.removeprefix('commenter:') in creator_keys)
        group['independent']=bool(group['identity_support'] and not overlapping)
    values={'videos':len(direct_videos),'creators':len(creator_keys),'commenters':len(commenters),
            'search_observations':independent_searches,'evidence_types':len(identity_types)}
    settings=config['diversity']
    components={key:round(settings['weights'][key]*min(values[key]/settings['targets'][key],1),4) for key in values}
    return dict(evidence_groups=list(groups.values()),unique_evidence_groups=sum(g['independent'] for g in groups.values()),
                unique_video_count=len(observed_videos),independent_video_count=len(direct_videos),
                unique_creator_count=len(observed_creators),independent_creator_count=len(set(creator_by_video.values())),
                unique_commenter_count=len(commenters),unique_comment_text_count=len(comment_texts),source_type_count=len(source_types),
                identity_source_type_count=len(identity_types),independent_search_observation_count=independent_searches,
                search_capture_groups=[{'group_key':'search_capture:'+str(cap),'video_id':vid} for cap,vid in sorted(searches)],
                source_diversity_score=round(sum(components.values()),4),source_diversity_components=components,
                _comment_by_video=comment_by_video,_direct_videos=direct_videos)


def comment_bonus(by_video, config):
    settings=config['corroboration_v2']; total=0
    # Same text from many authors, or many texts from one author, count once.
    for pairs in by_video.values():
        independent=min(len({a for a,_ in pairs}),len({t for _,t in pairs}))
        total+=min(sum(settings['comment_steps'][:independent]),settings['comment_per_video_cap'])
    all_pairs={pair for pairs in by_video.values() for pair in pairs}
    global_independent=min(len({a for a,_ in all_pairs}),len({t for _,t in all_pairs}))
    global_cap=sum(settings['comment_steps'][:global_independent])
    return round(min(total,global_cap,settings['comment_total_cap']),4)


def summarize(con, cid, config):
    evidence=[dict(r) for r in con.execute('SELECT * FROM product_candidate_evidence WHERE candidate_id=? ORDER BY id',(cid,))]
    candidate=con.execute('SELECT * FROM product_candidates WHERE id=?',(cid,)).fetchone()
    diversity=evidence_diversity(con,evidence,config)
    settings=config['corroboration_v2']; rules=settings['rules']
    videos=diversity['independent_video_count']; creators=diversity['independent_creator_count']
    strong=any(e['evidence_type'] in ('caption','hashtag') and len(signature(e.get('extracted_text') or '',config).split())>=rules['B']['minimum_strong_phrase_tokens'] for e in evidence)
    satisfied=[]
    if videos>=rules['A']['minimum_videos'] and creators>=rules['A']['minimum_creators']:
        satisfied.append('A')
    if videos>=rules['B']['minimum_videos'] and strong and diversity['unique_commenter_count']>=rules['B']['minimum_commenters'] and diversity['unique_comment_text_count']>=rules['B']['minimum_comment_texts']:
        satisfied.append('B')
    if videos>=rules['C']['minimum_videos']:
        satisfied.append('C')
    base=max((settings['base_weights'].get(e['evidence_type'],0) for e in evidence),default=0)
    components={'base_identity':base,'cross_video':0,'cross_creator':0,'supporting_comments':0,'specific_search_context':0}
    if videos>1:
        components['cross_video']=min(settings['second_video_bonus']+max(0,videos-2)*settings['additional_video_bonus'],settings['video_bonus_cap'])
    if creators>1:
        components['cross_creator']=min(settings['second_creator_bonus']+max(0,creators-2)*settings['additional_creator_bonus'],settings['creator_bonus_cap'])
    components['supporting_comments']=comment_bonus(diversity.pop('_comment_by_video'),config)
    from .product_detection import normalize
    phrase=normalize(candidate['normalized_name'])
    # Only a literal, specific product phrase within the query gets weak context.
    if len(phrase.split())>=settings['minimum_query_tokens'] and any(e['evidence_type']=='search_query' and phrase in normalize(e['raw_text']) for e in evidence):
        components['specific_search_context']=settings['specific_query_weight']
    cap=settings['corroborated_cap'] if satisfied else settings['single_video_cap'] if videos<=1 else settings['observed_cap']
    confidence=round(min(sum(components.values()),cap),4)
    diversity.pop('_direct_videos')
    summary={**diversity,'evidence_count':len(evidence),'supporting_comment_count':len({(e['video_id'],e['source_entity_id']) for e in evidence if e['evidence_type']=='comment'}),
             'candidate_creator_count':diversity['unique_creator_count'],'candidate_independent_creator_count':creators,
             'confidence_components':{k:round(v,4) for k,v in components.items()},'confidence_cap':cap,
             'confidence_uncapped':round(sum(components.values()),4),'confidence_version':config['corroboration_version'],
             'corroboration_rules_satisfied':satisfied,
             'corroboration_reason':{'rule_ids':satisfied,'independent_videos':videos,'independent_creators':creators,
                                     'supporting_commenters':diversity['unique_commenter_count'],'strong_explicit_phrase':strong},
             'possible_related_candidate_ids':[]}
    # Respect manual decisions and reserved status values; never promote.
    status=candidate['status'] if candidate['status'] in ('promoted','rejected') else 'corroborated' if satisfied else 'observed'
    con.execute('UPDATE product_candidates SET status=?,confidence=?,summary_json=?,signature=? WHERE id=?',
                (status,confidence,json.dumps(summary),signature(candidate['normalized_name'],config),cid))
    direct=[e for e in evidence if e['evidence_type'] in ('caption','hashtag','video_metadata') and e['video_id'] is not None]
    if direct:
        best=sorted(direct,key=lambda e:(-settings['base_weights'].get(e['evidence_type'],0),e['id']))[0]
        url=con.execute('SELECT canonical_url FROM videos WHERE id=?',(best['video_id'],)).fetchone()
        if url:
            con.execute('UPDATE product_candidates SET primary_reference_url=? WHERE id=?',(url[0],cid))
    return summary


def discover_relationships(con, config, now):
    candidates=[dict(r) for r in con.execute('SELECT * FROM product_candidates ORDER BY id')]
    for c in candidates:
        c['aliases']={r[0] for r in con.execute('SELECT normalized_alias FROM product_candidate_aliases WHERE candidate_id=?',(c['id'],))}
        c['videos']={r[0] for r in con.execute("SELECT DISTINCT video_id FROM product_candidate_evidence WHERE candidate_id=? AND evidence_type IN ('caption','hashtag','video_metadata')",(c['id'],))}
        c['creators']={r[0].casefold().lstrip('@') for r in con.execute('SELECT DISTINCT creator_username FROM videos WHERE id IN (SELECT video_id FROM product_candidate_evidence WHERE candidate_id=?) AND creator_username IS NOT NULL',(c['id'],))}
    scores=config['relationships']['scores']
    for a,b in combinations(candidates,2):
        relations=[]
        shared_videos=sorted(a['videos'] & b['videos']); shared_creators=sorted(a['creators'] & b['creators'])
        if shared_videos:
            relations.append(('same_video','Shared observed video; co-occurrence does not establish product identity',{'video_ids':shared_videos}))
        if shared_creators:
            relations.append(('same_creator','Shared observed creator; no physical-product equivalence implied',{'creator_usernames':shared_creators}))
        if a['normalized_name']==b['normalized_name']:
            relations.append(('same_normalized_phrase','Identical normalized text; no physical-product merge',{'phrase':a['normalized_name']}))
        shared_aliases=[alias for alias in sorted(a['aliases'] & b['aliases']) if lexical_relation(alias,alias,config)]
        if shared_aliases:
            relations.append(('shared_alias','Shared explicit, specific alias; review relation only',{'aliases':shared_aliases}))
        lexical=lexical_relation(a['normalized_name'],b['normalized_name'],config)
        if lexical:
            relations.append(('lexically_related','Specific tokens and conservative subset expansion match',lexical))
            if not shared_videos and a['videos'] and b['videos']:
                relations.append(('possible_same_product','Lexical relation across distinct videos; unverified hypothesis, never a merge',
                                  {**lexical,'video_ids_a':sorted(a['videos']),'video_ids_b':sorted(b['videos'])}))
        for kind,reason,evidence in relations:
            con.execute('''INSERT INTO candidate_relationships(candidate_a,candidate_b,relationship_type,score,reason,evidence_json,created_at,updated_at,relationship_version)
                VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(candidate_a,candidate_b,relationship_type) DO UPDATE SET
                score=excluded.score,reason=excluded.reason,evidence_json=excluded.evidence_json,
                updated_at=CASE WHEN score!=excluded.score OR reason!=excluded.reason OR evidence_json!=excluded.evidence_json OR relationship_version!=excluded.relationship_version THEN excluded.updated_at ELSE updated_at END,
                relationship_version=excluded.relationship_version''',
                (a['id'],b['id'],kind,scores[kind],reason,json.dumps(evidence),now,now,config['corroboration_version']))
    for c in candidates:
        related={r[0] for r in con.execute('SELECT CASE WHEN candidate_a=? THEN candidate_b ELSE candidate_a END FROM candidate_relationships WHERE candidate_a=? OR candidate_b=?',(c['id'],c['id'],c['id']))}
        summary=json.loads(con.execute('SELECT summary_json FROM product_candidates WHERE id=?',(c['id'],)).fetchone()[0])
        summary['possible_related_candidate_ids']=sorted(related)
        con.execute('UPDATE product_candidates SET summary_json=? WHERE id=?',(json.dumps(summary),c['id']))


def relationships(con, cid=None):
    result=[]
    for row in con.execute('''SELECT r.*,a.canonical_name AS name_a,b.canonical_name AS name_b
        FROM candidate_relationships r JOIN product_candidates a ON a.id=r.candidate_a JOIN product_candidates b ON b.id=r.candidate_b
        WHERE (? IS NULL OR candidate_a=? OR candidate_b=?) ORDER BY candidate_a,candidate_b,relationship_type''',(cid,cid,cid)):
        item=dict(row);item['evidence']=json.loads(item.pop('evidence_json'));result.append(item)
    return result
