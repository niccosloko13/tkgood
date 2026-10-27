"""Evaluation boundary: labels are read here, never passed back to production.

Literal name agreement is an observable naming metric, not proof of physical
identity. False merge rate needs separately adjudicated entity-pair labels.
"""
import json
from .candidate_semantics import normalize


def evaluate(con):
    from .intelligence_core import latest
    decisions={r['video_id']:r for r in latest(con)}
    labels=[dict(r) for r in con.execute("SELECT * FROM gold_video_labels WHERE review_status='reviewed'")]
    eligible=[r for r in labels if r['product_presence']=='yes' and (r['canonical_product_name'] or r['raw_product_name'])]
    comparisons=[]
    for label in eligible:
        decision=decisions.get(label['video_id'])
        names=[]
        if decision:
            signals=json.loads(decision['evidence_json'])['signals']
            names=[x for x in [decision['name'],*signals.get('alternatives',[])] if x][:3]
        expected={normalize(n) for n in (label['canonical_product_name'],label['raw_product_name']) if n}
        comparisons.append({'video_id':label['video_id'],'human_names':sorted(expected),'suggestions':names,
                            'top_1_match':bool(names and normalize(names[0]) in expected),
                            'top_3_match':any(normalize(n) in expected for n in names),
                            'status':decision['status'] if decision else 'not_processed'})
    measured=[r for r in comparisons if r['suggestions']]
    auto=[r for r in comparisons if r['status']=='AUTO']
    total=len(decisions)
    presence=[]
    for label in labels:
        if label['product_presence'] not in ('yes','no'):continue
        decision=decisions.get(label['video_id'])
        predicted=bool(decision and decision['status'] in ('AUTO','REVIEW') and decision['name'])
        presence.append((label['product_presence']=='yes',predicted))
    tp=sum(a and b for a,b in presence);fp=sum(not a and b for a,b in presence);fn=sum(a and not b for a,b in presence)
    retrieval=[]
    for label in eligible:
        rows=con.execute('''SELECT source_json FROM intelligence_retrievals WHERE video_id=? AND index_version=(SELECT index_version FROM intelligence_retrievals WHERE video_id=? ORDER BY id DESC LIMIT 1) ORDER BY similarity DESC,id DESC LIMIT 3''',(label['video_id'],label['video_id'])).fetchall()
        if not rows:continue
        references=[json.loads(r[0]) for r in rows]
        expected={normalize(n) for n in (label['canonical_product_name'],label['raw_product_name']) if n}
        hits=[normalize(r.get('name') or '') in expected for r in references]
        retrieval.append({'video_id':label['video_id'],'top_1_match':hits[0],'top_3_match':any(hits),'reference_kinds':[r['reference_kind'] for r in references]})
    return {'reviewed_labels':len(labels),'eligible_positive_labels':len(eligible),'naming_comparisons':comparisons,
            'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/(tp+fn) if tp+fn else None,'presence_tp':tp,'presence_fp':fp,'presence_fn':fn,
            'presence_evaluation_definition':'Named AUTO/REVIEW hypotheses versus reviewed yes/no presence; not final identity accuracy',
            'presence_negative_labels':sum(not a for a,b in presence),
            'top_1_accuracy':sum(r['top_1_match'] for r in retrieval)/len(retrieval) if retrieval else None,
            'top_3_recall':sum(r['top_3_match'] for r in retrieval)/len(retrieval) if retrieval else None,
            'retrieval_evaluation_status':'literal_reference_name_agreement_on_queried_gold_items' if retrieval else 'insufficient_retrieval_results',
            'retrieval_denominator':len(retrieval),'retrieval_comparisons':retrieval,
            'name_top_1_accuracy':sum(r['top_1_match'] for r in measured)/len(measured) if measured else None,
            'top_1_denominator':len(measured),
            'name_top_3_recall':sum(r['top_3_match'] for r in comparisons)/len(comparisons) if comparisons else None,
            'auto_decision_accuracy':sum(r['top_1_match'] for r in auto)/len(auto) if auto else None,
            'auto_denominator':len(auto),'false_merge_rate':None,'false_merge_reason':'No human-adjudicated entity-pair labels; Gold names alone do not establish same product',
            'review_rate':sum(r['status']=='REVIEW' for r in decisions.values())/total if total else None,
            'unresolved_rate':sum(r['status']=='UNRESOLVED' for r in decisions.values())/total if total else None,
            'definition':'top_1/top_3: literal reference-name agreement on actually queried Gold items, including candidate references; not physical identity accuracy. name_top_*: literal hypothesis-name diagnostics. False-merge evaluation still requires adjudicated entity pairs.'}


def evaluate_visual(con):
    """Post-inference literal-name ablation; never produces human identity labels."""
    from . import intelligence_core as core,visual_identification as vi
    from .intelligence_decisions import decide
    text_only={}
    for row in con.execute('SELECT id FROM videos').fetchall():
        item=core.observation(con,row[0]);item['proposals']=[]
        signals=core.evidence_for(item)
        text_only[row[0]]=[n for n in [signals['name'],*signals['alternatives']] if n]
    decisions={r['video_id']:r for r in core.latest(con)}
    # Gold is opened only after production outputs and text-only ablations exist.
    labels=[dict(r) for r in con.execute("SELECT * FROM gold_video_labels WHERE review_status='reviewed' AND product_presence='yes'")]
    rows=[]
    for label in labels:
        names={vi.normalized(label[k]) for k in ('canonical_product_name','raw_product_name') if label[k]}
        visual=vi.proposals(con,label['video_id'],active_only=True)
        if not names or not visual:continue
        groups=[{vi.normalized(n) for n in [p['possible_product_name'],*json.loads(p['aliases_json'])]} for p in visual[:3]]
        decision=decisions.get(label['video_id']);signals=json.loads(decision['evidence_json'])['signals'] if decision else {}
        multimodal=[n for n in [decision['name'] if decision else None,*signals.get('alternatives',[])] if n][:3]
        text=text_only[label['video_id']][:3]
        rows.append({'video_id':label['video_id'],'visual_names':[p['possible_product_name'] for p in visual[:3]],
            'visual_top1':bool(groups[0]&names),'visual_top3':any(g&names for g in groups),
            'text_top1':bool(text and vi.normalized(text[0]) in names),'text_top3':any(vi.normalized(n) in names for n in text),
            'multimodal_top1':bool(multimodal and vi.normalized(multimodal[0]) in names),'multimodal_top3':any(vi.normalized(n) in names for n in multimodal),
            'decision':decision['status'] if decision else None})
    metric=lambda key:sum(r[key] for r in rows)/len(rows) if rows else None
    return {'cohort_size':len(rows),'rows':rows,'text_only':{'top1':metric('text_top1'),'top3':metric('text_top3')},
            'visual_only':{'top1':metric('visual_top1'),'top3':metric('visual_top3')},
            'multimodal':{'top1':metric('multimodal_top1'),'top3':metric('multimodal_top3')},
            'false_identity_rate':None,'AUTO_accuracy':None if not any(r['decision']=='AUTO' for r in rows) else metric('multimodal_top1'),
            'REVIEW_accuracy':None,'reason':'Literal naming agreement is not physical identity adjudication. No automatic human labels or false-identity labels are assigned.'}
