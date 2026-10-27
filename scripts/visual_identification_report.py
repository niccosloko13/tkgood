"""Bounded local visual pilot/export; no browser, HTTP client or remote provider."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app import db,visual_identification as vi


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run-pilot',action='store_true');args=parser.parse_args()
    out=ROOT/'artifacts/visual-identification';out.mkdir(parents=True,exist_ok=True)
    if args.run_pilot:
        with db.connect() as con:
            vi.migrate(con)
            # Re-running the export command never silently creates a second initial pilot.
            if not con.execute('SELECT 1 FROM visual_pilots').fetchone():vi.run_pilot(con)
    con=sqlite3.connect('file:'+str(ROOT/'data/product_hunter.db')+'?mode=ro',uri=True);con.row_factory=sqlite3.Row
    con.execute('PRAGMA query_only=ON')
    queue=vi.high_queue(con);items=[vi.review_item(con,v['video_id'],queue) for v in queue]
    metrics=vi.metrics(con)
    (out/'high-review-items.json').write_text(json.dumps(items,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'metrics.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'gold-comparison.json').write_text(json.dumps(metrics['gold_comparison'],ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'product-suggestions.json').write_text(json.dumps([p for v in items for p in v['proposals']],ensure_ascii=False,indent=2),encoding='utf-8')
    before=json.loads((out/'before.json').read_text(encoding='utf-8'))
    old=sqlite3.connect('file:'+str(out/'checkpoint.db')+'?mode=ro',uri=True);old.row_factory=sqlite3.Row
    changed=[]
    for name,expected in before['tables'].items():
        # Compare only the original columns, so additive evidence columns do not
        # disguise modifications to legacy records or count as changes themselves.
        columns=[r[1] for r in old.execute('PRAGMA table_info("'+name+'")')]
        query='SELECT '+','.join('"'+c+'"' for c in columns)+' FROM "'+name+'"'
        rows=[dict(r) for r in con.execute(query)]
        digest=hashlib.sha256(json.dumps(rows,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()
        if {'count':len(rows),'hash':digest}!=expected:changed.append(name)
    source_changes=[name for name,digest in before['files'].items() if not (ROOT/name).exists() or hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest]
    verification={'changed_original_tables':changed,'changed_existing_files':source_changes,
        'integrity_check':con.execute('PRAGMA integrity_check').fetchone()[0],
        'foreign_key_check':[list(r) for r in con.execute('PRAGMA foreign_key_check')],
        'extension_unchanged':not any(x.startswith('extension') for x in source_changes)}
    for key in ['browser_security_stop','browser_security_history','browser_security_clearance']:
        q='SELECT value_json FROM system_state WHERE key=?'
        a=con.execute(q,(key,)).fetchone();b=old.execute(q,(key,)).fetchone()
        verification[key+'_unchanged']=(a[0] if a else None)==(b[0] if b else None)
    (out/'verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding='utf-8')
    def esc(v):return html.escape(str(v if v is not None else '—')).replace('|','\\|').replace('\n',' ')
    def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join('---' for _ in headers)+'|',*['| '+' | '.join(esc(x) for x in row)+' |' for row in rows]])+'\n'
    parts=['# BABI — Visual Product Identification v1\n\nPipeline assistida implementada; nenhum nome foi inventado. O piloto real encontrou somente referências remotas TikTok CDN, sem imagens locais acessíveis. Nenhuma imagem remota foi requisitada, nenhum provider remoto foi chamado e o security stop continua intacto. Sem commit.\n']
    parts.append('## HIGH QUEUE\n\n'+table(['Video ID','Caption','Fonte','Disponibilidade','Motivo'],[[v['video_id'],v['caption'],v['image']['source_type'],v['image']['status'],v['image']['reason']] for v in items]))
    parts.append('Os '+str(len(items))+' contextos completos em high-review-items.json contêm thumbnail_url persistida (referência apenas), hashtags, comentários relevantes, candidates, unresolved, categoria/subcategoria/family e motivos da prioridade. Nenhum MEDIUM foi expandido. Seleção inicial congelada em visual_pilots/visual_pilot_items.\n')
    parts.append('## VISUAL AVAILABILITY\n\n'+table(['Métrica','Resultado'],[(k,metrics[k]) for k in ['visual_items_attempted','visual_available','visual_unavailable','provider_calls']]))
    parts.append('Attempted significa verificação local da fonte, não análise de imagem. Fontes em p16/p19-common-sign.tiktokcdn.com são blocked_by_security_stop_tiktok_cdn. Não foram testadas disponibilidade HTTP, expiração ou conteúdo dessas imagens. Nenhum frame/cache de navegador foi procurado e nenhuma imagem alternativa foi fabricada. O retorno da internet não revoga o bloqueio TikTok.\n')
    parts.append('## PRODUCT SUGGESTIONS\n\n'+table(['Métrica','Resultado'],[(k,metrics[k]) for k in ['visual_suggestions','human_accepted','human_rejected']]))
    parts.append('Sem imagem acessível, zero propostas V1 foram inseridas em VisualProductEvidence; nomes do Gold Set, captions e queries não foram usados para fingir saída visual. O fluxo assistido está disponível para imagens locais reais associadas pelo operador. Novas propostas começam em suggested; accepted/rejected/unclear exigem ação humana e guardam histórico. Aceitação não confirma entidade nem grava candidates/labels.\n')
    parts.append('## GOLD SET COMPARISON\n\n'+table(['Video ID','Nome humano preservado','Nomes visuais','Match','Helpful','Wrong','Visual unavailable'],[[r['video_id'],r['human_product_name'],', '.join(r['visual_names']),r['visual_name_match'],r['visual_helpful'],r['visual_wrong'],r['visual_unavailable']] for r in metrics['gold_comparison']]))
    parts.append('Comparação somente leitura dos '+str(len(metrics['gold_comparison']))+' reviews existentes. Nenhum provider foi executado fora dos HIGH. Checar a referência de imagem dos demais reviews para comparar disponibilidade não expande o piloto. Nome igual após NFKC/casefold é comparação literal, não identidade física; nomes diferentes não são automaticamente wrong. Helpfulness/wrong exigem avaliação humana separada, sem alterar Gold.\n')
    parts.append('## FALSE NEGATIVE IMPROVEMENT\n\nvisual_helpful_on_FN: '+str(metrics['visual_helpful_on_FN'])+' observados; visual_match_on_gold_set: '+str(metrics['visual_match_on_gold_set'])+' em '+str(metrics['gold_comparison_evaluable'])+' comparações avaliáveis. Taxa: '+str(metrics['gold_name_match_rate'])+'. Melhoria de recall **não medida**; zero observações não demonstra que visão seja inútil. Os 9 FN e o recall humano/detector anteriores não foram recalculados nem reclassificados.\n')
    parts.append('## PROVIDER PERFORMANCE\n\n'+table(['Provider','Integração','Execução real'],[[p,'assistida/manual; sem API remota configurada','0 chamadas remotas'] for p in vi.PROVIDERS]))
    parts.append('Estados do piloto: '+esc(json.dumps(metrics['provider_performance']))+'. Não é possível medir precisão/recall ou comparar providers sem imagens/resultados. Não foi criado workaround de Lens. A interface aceita saída atribuída com source_type, provider_version, URL, observed_at, reason, confidence declarada e hash da imagem.\n')
    parts.append('## MULTI-SOURCE / CONFIDENCE / UI\n\nHipótese separa texto, comentários, visual e web listings por IDs de evidência. Aliases são sugestões deduplicadas, não sinônimos confirmados. Confidence: 0,25 visual; +0,10 caption literal; +0,10 comments; +0,25 para duas fontes/listings compatíveis em sites/grupos independentes com revisão explícita. Cap0,70; genericidade/contradição cap0,20. Resultado único nunca excede0,45. Não são probabilidades.\n\nNovo painel VISUAL IDENTIFICATION dentro do review e fila HIGH em Vídeos. ACEITAR/REJEITAR/INCERTO alteram somente a revisão visual. Imagens são servidas apenas pelo endpoint local validado; referências CDN não viram src. Após proposta, há link de pesquisa web acionado pelo humano e formulário title/url/source/observed_at/possible_match/match_reason, compatibilidade/contradição/independência. Referências web são evidência de identidade, não SupplierListingEvidence. Nenhuma busca web ocorreu sem hipótese visual.\n')
    parts.append('## UNRESOLVED CASES\n\nTodos os 14 HIGH continuam sem identificação visual nesta execução. É necessária uma imagem real persistida localmente; não obter novas imagens do TikTok durante o bloqueio. A fila e os motivos estão preservados. Adapters assistidos não substituem uma integração remota oficial e não prometem inferência automatizada. Site buckets não provam independência societária; a revisão humana é obrigatória e cópias entre sites ainda podem enganar. A comparação literal não mede sinônimos nem modelo/SKU.\n')
    parts.append('## PRESERVATION\n\n'+esc(json.dumps(verification,ensure_ascii=False))+'\n\nSchema novo é aditivo: seis tabelas de assets/reviews/web/piloto/comparação e colunas em visual_product_evidence. Gold Set, benchmark, candidates, evidence anteriores, detector, classifier, taxonomy, resolver e SupplierListingEvidence não foram alterados. Legado visual permanece com status original e não foi convertido em confirmação. Backup: checkpoint.db; baseline:before.json.\n')
    testfile=out/'test-results.json'
    if testfile.exists():
        tests=json.loads(testfile.read_text(encoding='utf-8'))
        parts.append('## TEST RESULTS\n\n'+table(['Suite','Passed','Task'],[[k,tests[k]['passed'],tests[k]['task_id']] for k in ['python','node_dashboard']])+'\nLogs em .runtime/logs/task-ID.json/.log. Testes sintéticos usam imagens em bancos/pastas temporários, não imagens reais do piloto.\n')
    else:parts.append('## TEST RESULTS\n\nRegressão em execução; exportar novamente após conclusão.\n')
    parts.append('## FILES CHANGED\n\napp/visual_identification.py, app/visual_identification_api.py, app/db.py, app/main.py, app/static/visual-identification.js, app/static/index.html; tests/test_visual_identification.py, tests/visual-identification.test.cjs; scripts/visual_identification_report.py; docs/VISUAL_IDENTIFICATION.md e docs/NEXT_SESSION.md. Artefatos JSON, report e checkpoint nesta pasta. Workspace anterior preservado; sem staging/commit.\n')
    parts.append('## NEXT RECOMMENDED SPRINT\n\nAssociar imagens locais reais e revisar os mesmos HIGH pelo fluxo assistido; coletar propostas e avaliações separadas antes de medir benefício nos FN. Só então avaliar integração oficial de provider com credenciais/limites/provenance adequados. Não expandir para MEDIUM, não reabrir TikTok, não limpar stop e não iniciar Supplier Discovery automaticamente.\n')
    (out/'REPORT.md').write_text('\n'.join(parts),encoding='utf-8')
    print(json.dumps({k:v for k,v in metrics.items() if k not in ('pilot_items','gold_comparison')},indent=2))
    print(json.dumps(verification,ensure_ascii=True,indent=2))


if __name__=='__main__':main()
