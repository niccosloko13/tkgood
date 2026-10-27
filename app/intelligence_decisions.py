"""Central offline decision policy. Similarity is supporting evidence, never identity.

Production inputs are observations only. Gold labels are deliberately not imported.
Legacy resolver remains responsible for provenance-bound lexical comparisons.
"""
import json
import re
from pathlib import Path


def settings():
    return json.loads((Path(__file__).resolve().parents[1] / 'config/intelligence_core.json').read_text(encoding='utf-8'))


def specificity(phrase,caption='',comments=(),candidate_recurrence=0):
    from .candidate_semantics import product_signature,normalize,configuration
    p=settings()['text'];n=normalize(phrase);tokens=n.split();sig=product_signature(phrase)
    lexical=configuration();heads=set(lexical['generic_heads'])|set(p['extra_heads'])
    literal=lambda text:bool(n and re.search(r'(?<!\w)'+re.escape(n)+r'(?!\w)',normalize(text)))
    def contradicted(text):
        return bool(n and re.search(r'(?<!\w)(?:not|nao e|não é|no es)\s+(?:(?:a|an|um|uma|un|una)\s+)?'+re.escape(n)+r'(?!\w)',normalize(text)))
    # Deduplicate text before counting; repeated captures are not independent support.
    contradicted_ids=[c['id'] for c in comments if contradicted(c['text']) and 'id' in c]
    matched={normalize(c['text']):c for c in comments if literal(c['text']) and not contradicted(c['text'])}
    authors={normalize(c.get('author_username') or '') for c in matched.values()}-{''}
    head_position=max((i for i,t in enumerate(tokens) if t in heads),default=-1)
    modifiers=[t for i,t in enumerate(tokens) if i!=head_position and t not in p['weak'] and t not in p['generic'] and t not in lexical['function_tokens'] and not t.isdigit()]
    known_head=any(t in heads for t in tokens)
    compound=len(tokens)>=p['min_compound_tokens']
    caption_support=literal(caption)
    structural=compound and bool(modifiers) and (known_head or caption_support and bool(matched))
    specific=bool(n and n not in p['generic'] and structural)
    return {'phrase':phrase,'specific':specific,'compound_tokens':len(tokens),'known_head':known_head,
            'specific_modifiers':modifiers,'caption_literal_support':caption_support,
            'comment_recurrence':len(matched),'comment_authors':len(authors),'comment_evidence_ids':[c['id'] for c in matched.values() if 'id' in c],
            'candidate_recurrence':candidate_recurrence,'contradicting_comment_ids':contradicted_ids,'caption_contradiction':contradicted(caption),
            'reason':'SPECIFIC_COMPOUND_WITH_CONTEXT' if specific else 'GENERIC_OR_UNSUPPORTED_PHRASE'}


def same_product(evidence):
    p = settings()['decision']
    conflicts = evidence.get('conflicts', [])
    if 'brand' in conflicts or 'model' in conflicts:
        return 'different_product'
    if conflicts:
        return 'possible_same_product'
    resolver = evidence.get('resolver') or {}
    image = evidence.get('image_similarity')
    text = evidence.get('text_similarity')
    # Explicit binding and lexical specificity are essential even at cosine 1.0.
    strong = (resolver.get('identity_score', 0) >= p['identity_score']
              and resolver.get('semantic_result') == 'possible_same_product'
              and evidence.get('specific_terms') and evidence.get('brand_model_match')
              and evidence.get('independent_listings', 0) >= p['independent_listings'])
    if strong and image is not None and image >= p['image_similarity'] and text is not None and text >= p['text_similarity']:
        return 'same_product_likely'
    if resolver.get('semantic_result') == 'different':
        return 'different_product'
    if (resolver.get('semantic_result')=='possible_same_product'
        or image is not None and image>=p['image_similarity']
        or text is not None and text>=p['text_similarity']):
        return 'possible_same_product'
    return 'insufficient'


def decide(evidence):
    p = settings()['decision']
    name = evidence.get('name')
    if evidence.get('conflicts'):
        code = 'REVIEW_POSSIBLE_VARIANT' if 'variant' in evidence['conflicts'] else 'REVIEW_CONFLICTING_TEXT_EVIDENCE' if 'text_contradiction' in evidence['conflicts'] else 'REVIEW_CONFLICTING_VISUAL_RESULTS'
        state = 'REVIEW'
    elif evidence.get('text_identity_specific'):
        if evidence.get('composition'):
            state,code='REVIEW','REVIEW_TEXT_COMPOSITE_PRODUCT'
        elif evidence.get('text_caption_supported') and evidence.get('text_candidate_supported'):
            if (evidence.get('compatible_comment_authors',0)>=settings()['text']['auto_comment_authors']
                and evidence.get('candidate_recurrence',0)>=settings()['text']['auto_candidate_occurrences']):
                state,code='AUTO','AUTO_STRONG_TEXT_IDENTITY'
            else:state,code='REVIEW','REVIEW_SPECIFIC_TEXT_IDENTITY'
        else:
            state,code='REVIEW','REVIEW_SPECIFIC_COMMENT_HYPOTHESIS'
    elif not evidence.get('visual_available'):
        state, code = 'UNRESOLVED', 'UNRESOLVED_NO_VISUAL'
    elif not name or evidence.get('generic_text'):
        state, code = 'UNRESOLVED', 'UNRESOLVED_GENERIC_TEXT'
    elif (evidence.get('visual_supported') and evidence.get('text_supported')
          and evidence.get('independent_listings', 0) >= p['independent_listings']
          and evidence.get('specific_terms') and not evidence.get('retrieval_conflict')):
        state, code = 'AUTO', 'AUTO_STRONG_MULTISOURCE_MATCH'
    elif evidence.get('visual_supported'):
        state, code = 'REVIEW', 'REVIEW_INSUFFICIENT_CORROBORATION'
    else:
        state, code = 'UNRESOLVED', 'UNRESOLVED_INSUFFICIENT_EVIDENCE'
    if evidence.get('retrieval_unavailable') and evidence.get('visual_supported'):
        state, code = 'REVIEW', 'REVIEW_RETRIEVAL_UNAVAILABLE'
    elif evidence.get('retrieval_conflict'):
        state, code = 'REVIEW', 'REVIEW_POSSIBLE_VARIANT'
    return {'status': state, 'reason_code': code, 'possible_product_name': name,
            'same_product': same_product(evidence), 'policy_version': settings()['version'],
            'confidence_is_probability': False}
