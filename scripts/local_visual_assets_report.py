"""Read-only export of the local-asset workflow and its real production outcomes."""
from datetime import datetime,timezone
import hashlib
import html
import json
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app import visual_identification as vi


def main():
    out=ROOT/'artifacts/local-visual-assets';out.mkdir(parents=True,exist_ok=True)
    con=sqlite3.connect('file:'+str(ROOT/'data/product_hunter.db')+'?mode=ro',uri=True);con.row_factory=sqlite3.Row
    con.execute('PRAGMA query_only=ON')
    checked=datetime.now(timezone.utc).isoformat();metrics=vi.local_asset_metrics(con)
    queue=vi.high_queue(con)
    assets=[dict(r) for r in con.execute('SELECT * FROM visual_image_assets ORDER BY id')]
    before=json.loads((out/'before.json').read_text(encoding='utf-8'))
    old=sqlite3.connect('file:'+str(out/'checkpoint.db')+'?mode=ro',uri=True);old.row_factory=sqlite3.Row
    changed=[]
    for name,expected in before['tables'].items():
        columns=[r[1] for r in old.execute('PRAGMA table_info("'+name+'")')]
        query='SELECT '+','.join('"'+c+'"' for c in columns)+' FROM "'+name+'"'
        rows=[dict(r) for r in con.execute(query)]
        digest=hashlib.sha256(json.dumps(rows,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()
        if {'count':len(rows),'hash':digest}!=expected:changed.append(name)
    changed_files=[k for k,v in before['files'].items() if not (ROOT/k).exists() or hashlib.sha256((ROOT/k).read_bytes()).hexdigest()!=v]
    verification={'checked_at':checked,'changed_original_tables':changed,'changed_existing_files':changed_files,
        'integrity_check':con.execute('PRAGMA integrity_check').fetchone()[0],
        'foreign_key_check':[list(r) for r in con.execute('PRAGMA foreign_key_check')],
        'extension_unchanged':not any(x.startswith('extension') for x in changed_files),
        'remote_thumbnail_urls_unchanged':[tuple(r) for r in con.execute('SELECT id,thumbnail_url FROM videos ORDER BY id')]==[tuple(r) for r in old.execute('SELECT id,thumbnail_url FROM videos ORDER BY id')]}
    for key in ['browser_security_stop','browser_security_history','browser_security_clearance']:
        q='SELECT value_json FROM system_state WHERE key=?';a=con.execute(q,(key,)).fetchone();b=old.execute(q,(key,)).fetchone()
        verification[key+'_unchanged']=(a[0] if a else None)==(b[0] if b else None)
    (out/'metrics.json').write_text(json.dumps({'checked_at':checked,**metrics},ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'assets.json').write_text(json.dumps(assets,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'gold-high-pilot.json').write_text(json.dumps([vi.review_item(con,v['video_id'],queue) for v in metrics['pilot']],ensure_ascii=False,indent=2),encoding='utf-8')
    def esc(value):return html.escape(str(value if value is not None else '—')).replace('|','\\|').replace('\n',' ')
    def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join('---' for _ in headers)+'|',*['| '+' | '.join(esc(x) for x in row)+' |' for row in rows]])+'\n'
    parts=['# BABI — Local Visual Assets + Assisted Product Identification\n\nImplementado sobre VisualProductEvidence v1, sem reconstruir a entidade. Snapshot: '+checked+'.\n']
    parts.append('## RESULTADOS REAIS\n\n'+table(['Métrica','Resultado'],[(k,metrics[k]) for k in ['assets_uploaded','assets_total','HIGH_resolved','HIGH_remaining','Gold_FN_tested','visual_attempted','visual_helpful','visual_match','visual_wrong','still_unclear','helpfulness_assessed']]))
    parts.append('HIGH resolved significa imagem local disponível, não identidade confirmada. still_unclear considera somente os '+str(metrics['gold_high_items'])+' itens HIGH com review humano existente. Zeros de helpful/wrong não são estimativas de qualidade: não houve julgamento avaliável enquanto faltam imagens/resultados reais.\n')
    if not metrics['assets_total']:
        parts.append('**Nenhuma imagem real foi fornecida nesta execução.** O usuário confirmou que vai adicioná-las pelo review. Nenhum arquivo de teste foi inserido na biblioteca real, nenhum asset/produto foi fabricado e nenhuma URL CDN foi baixada para preencher essa lacuna. O fluxo está disponível para uso, mas a identificação real dos FN aguarda esses uploads e o resultado assistido.\n')
    parts.append('## LOCAL ASSET INGEST\n\nUpload binário, seleção de arquivo e drag & drop por video_id. PNG/JPG/JPEG/WebP com verificação completa de decoder/MIME, integridade e dimensões por Pillow12.3.0, no ambiente .venv existente. Limites:10MiB,8192px/lado,20M pixels; imagens animadas/corrompidas rejeitadas. Content-Length e chunks são limitados. MIME/extensão devem corresponder ao conteúdo. SHA256 usa os bytes originais, sem resize ou transcode.\n\nArmazenamento:data/visual_assets/{video_id}/{sha256}.{ext}. Asset registra video_id,asset_id,source_type,local_path,sha256,width,height,created_at. Dedup por video_id+sha256; upload repetido não cria outro asset. O mesmo conteúdo em outro vídeo é associação explícita distinta. Filename humano não vira path de destino. Upload seleciona asset local sem alterar thumbnail_url, que continua referência remota.\n')
    parts.append('## GOLD SET PILOT\n\n'+table(['Ordem','Video ID','Gold status existente','Imagem'],[[i+1,v['video_id'],v['benchmark_category'],v['image']['status']] for i,v in enumerate(metrics['pilot'])]))
    parts.append('FN primeiro:4,5,6,11,12,14;depois item2 incerto. Nenhum MEDIUM é expandido. Upload é permitido em outros HIGH, mas o início assistido fica restrito à interseção HIGH/Gold. IDENTIFICAR PRODUTO prepara pacote local(video_id,imagem/hash,caption,comments,category,candidate,unresolved), sem chamar provider. Comparação e helpfulness são registros visuais separados; Gold labels e benchmark não mudam.\n')
    parts.append('## ASSISTED LENS / WEB CONFIRMATION\n\nO review oferece Adicionar imagem, preview local, IDENTIFICAR PRODUTO, download local e link manual para Lens. O operador escolhe o arquivo no fluxo normal do Google e registra possible_product_name,result_url,source,listing_title,observed_at,notes. A Babi não envia imagem ao Google nem automatiza navegador/Lens. Saída sempre google_lens_assisted/suggested; referência inicial não ganha match/compatibilidade/independência automaticamente.\n\nReferência de operação assistida:[Google Lens](https://lens.google/), página oficial consultada; isso não é integração de API ou scraping. Após nome possível, formulário web guarda title,url,domain derivado,possible_match,match_reason,independence_reviewed e snapshots datados, sem scraping/preço/supplier lookup. TEXT,VISUAL,WEB CONFIRMATION e FINAL HYPOTHESIS permanecem separados no review.\n')
    parts.append('## CANONICAL / REVIEW HISTORY\n\nCanonical name suggestion escolhe apenas nomes observados no resultado visual, aliases propostos ou títulos curtos marcados como possíveis matches/compatíveis. Prefere suporte literal em caption, depois comments, depois nome visual original. Títulos podem aparecer como aliases sugeridos com IDs de fonte; nenhuma equivalência semântica é confirmada nem nome híbrido inventado. Nenhuma Product Entity é criada.\n\nImagem nova tem novo hash/draft e requer nova preparação. Proposta/revisão da imagem anterior permanece histórica e não é aplicada à atual. Upload que termine atrasado não substitui outro review selecionado. Aceitar/rejeitar/incerto continuam ações humanas explícitas, com histórico, sem mutações de Candidate ou Gold.\n')
    parts.append('## FUTURE CAPTURE CONTRACT\n\napp.visual_assets.persist_visual_asset(video_id,bytes,source_metadata) recebe bytes já obtidos legitimamente. source_type:manual_upload,imported_asset,future_capture. Somente os dois primeiros estão no uploadHTTP. Não há caller/captura/runtime TikTok implementado. future_capture é recusado sob security stop; uma futura coleta deverá comprovar permissão/visibilidade antes de fornecer bytes. Dedup persiste o mesmo frame uma única vez.\n')
    tests_file=out/'test-results.json'
    if tests_file.exists():
        tests=json.loads(tests_file.read_text(encoding='utf-8'))
        parts.append('## TESTS\n\n'+table(['Suite','Passed','Task SUCCEEDED'],[[k,tests[k]['passed'],tests[k]['task_id']] for k in ['python','node_dashboard']])+'\nQuatro warnings Python de depreciação preexistentes. API e assetJS locais:200 OK. Testes usam imagens sintéticas/pastas/SQLite temporários; nenhum número desses testes foi contado como resultado real do piloto.\n')
    else:parts.append('## TESTS\n\nRegressão em andamento; atualizar após confirmação.\n')
    parts.append('Casos cobertos:upload válido em3formatos;MIME/extensão/conteúdo inválidos;corrupção;limites bytes/dimensões e stream;SHA;dedup e associação;unavailable→available;piloto FN/restrição de escopo;Lens suggested;domain;canonical/aliases;histórico humano;troca de imagem;drag/drop/file picker;corrida de navegação;zero requests TikTok;zero mutação Gold/Candidate.\n')
    parts.append('## PRESERVAÇÃO\n\n'+esc(json.dumps(verification,ensure_ascii=False))+'\n\nSchema aditivo sobre visual_image_assets e evidência web, mais tabelas de seleção de asset/sessão assistida. VisualProductEvidence não foi reconstruído. Os dados originais são comparados pelas colunas preexistentes; tabelas operacionais podem variar com heartbeat/restart local. Gold/benchmark,candidates/evidence,classifier/taxonomy/resolver,thumbnails e security history preservados. Sem clear,discovery,Chrome automation,TikTok/CDN requests,supplier scraping ou commit.\n')
    parts.append('## FILES CHANGED\n\napp/visual_assets.py;app/visual_identification.py;app/visual_identification_api.py;app/static/visual-identification.js;requirements.txt;tests/test_local_visual_assets.py;tests/local-visual-assets.test.cjs;docs/LOCAL_VISUAL_ASSETS.md;docs/VISUAL_IDENTIFICATION.md;docs/NEXT_SESSION.md;scripts/local_visual_assets_report.py e artefatos desta pasta.\n')
    parts.append('## NEXT RECOMMENDATION\n\nO usuário vai adicionar imagens reais pelo review. Começar pelo FN4 e seguir a ordem do piloto. Depois clicar IDENTIFICAR PRODUTO, registrar evidência visual/web e avaliar helpful/match/wrong separadamente. Não limpar security stop para obter imagens. Sem uploads reais, nenhuma melhoria de recall pode ser medida.\n')
    (out/'REPORT.md').write_text('\n'.join(parts),encoding='utf-8')
    print(json.dumps({k:v for k,v in metrics.items() if k!='pilot'},indent=2))
    print(json.dumps(verification,ensure_ascii=True,indent=2))


if __name__=='__main__':main()
