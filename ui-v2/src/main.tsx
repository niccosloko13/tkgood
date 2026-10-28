import {StrictMode, useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {getDiscovery, getHome, getLibrary, getLibraryDetail, getMarketRadar, getMarketTop, getMarketTrends, getOpportunities, getSystem, startMission, startSearch} from './lib/api';
import {formatCurrency, formatDetectedAt, formatNumber} from './lib/formatters';
import type {Discovery, DiscoveryData, HomeData, LibraryData, LibraryDetail, LibraryItem, MarketProduct, MarketRadarData, MarketSource, MarketTrend, OpportunitiesData, Opportunity, OpportunityV2, SystemData} from './types';
import './styles.css';

type Page = 'Visão geral' | 'Descobrir' | 'Oportunidades' | 'Biblioteca' | 'Market Radar' | 'Sistema';
const navigation: Array<{page: Page; icon: string}> = [
  {page: 'Visão geral', icon: '⌂'}, {page: 'Descobrir', icon: '⌕'}, {page: 'Oportunidades', icon: '✦'}, {page: 'Biblioteca', icon: '▤'}, {page: 'Market Radar', icon: '◉'}, {page: 'Sistema', icon: '⚙'},
];

function App() {
  const [page, setPage] = useState<Page>('Visão geral');
  const [home, setHome] = useState<HomeData | null>(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);
  const [discovery, setDiscovery] = useState<DiscoveryData | null>(null);
  const [discoveryError, setDiscoveryError] = useState(false);
  const [discoveryLoading, setDiscoveryLoading] = useState(false);
  const [opportunities, setOpportunities] = useState<OpportunitiesData | null>(null);
  const [opportunitiesError, setOpportunitiesError] = useState(false);
  const [opportunitiesLoading, setOpportunitiesLoading] = useState(false);
  const [library, setLibrary] = useState<LibraryData | null>(null);
  const [libraryError, setLibraryError] = useState(false);
  const [libraryLoading, setLibraryLoading] = useState(false);
  const [libraryCandidate, setLibraryCandidate] = useState<string | null>(null);
  const [system, setSystem] = useState<SystemData | null>(null);
  const [systemError, setSystemError] = useState(false);
  const [systemLoading, setSystemLoading] = useState(false);
  const [marketRadar, setMarketRadar] = useState<MarketRadarData | null>(null);
  const [marketRadarError, setMarketRadarError] = useState(false);
  const [marketRadarLoading, setMarketRadarLoading] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const loadHome = async () => { setLoading(true); setError(false); try { setHome(await getHome()); } catch { setError(true); } finally { setLoading(false); } };
  useEffect(() => { void loadHome(); }, []);
  const loadDiscovery = async () => { setDiscoveryLoading(true); setDiscoveryError(false); try { setDiscovery(await getDiscovery()); } catch { setDiscoveryError(true); } finally { setDiscoveryLoading(false); } };
  useEffect(() => { if (page === 'Descobrir') void loadDiscovery(); }, [page]);
  const loadOpportunities = async () => { setOpportunitiesLoading(true); setOpportunitiesError(false); try { setOpportunities(await getOpportunities()); } catch { setOpportunitiesError(true); } finally { setOpportunitiesLoading(false); } };
  useEffect(() => { if (page === 'Oportunidades') void loadOpportunities(); }, [page]);
  const loadLibrary = async (params: Record<string, string | number | boolean | undefined> = {page: 1, page_size: 20, sort: 'recent', candidate_id: libraryCandidate || undefined}) => { setLibraryLoading(true); setLibraryError(false); try { setLibrary(await getLibrary(params)); } catch { setLibraryError(true); } finally { setLibraryLoading(false); } };
  useEffect(() => { if (page === 'Biblioteca') void loadLibrary(); }, [page]);
  const loadSystem = async () => { setSystemLoading(true); setSystemError(false); try { setSystem(await getSystem()); } catch { setSystemError(true); } finally { setSystemLoading(false); } };
  useEffect(() => { if (page === 'Sistema') void loadSystem(); }, [page]);
  const loadMarketRadar = async () => { setMarketRadarLoading(true); setMarketRadarError(false); try { setMarketRadar(await getMarketRadar()); } catch { setMarketRadarError(true); } finally { setMarketRadarLoading(false); } };
  useEffect(() => { if (page === 'Market Radar') void loadMarketRadar(); }, [page]);
  const navigate = (next: Page) => { if (next !== 'Biblioteca') setLibraryCandidate(null); setPage(next); setMoreOpen(false); };
  const openLibraryForCandidate = (candidateId: string) => { setLibraryCandidate(candidateId); setPage('Biblioteca'); setMoreOpen(false); };
  return <div className="app-shell">
    <aside className="desktop-sidebar"><div className="brand">babi<span>.</span></div><p>Inteligência de produto</p><nav aria-label="Navegação principal">{navigation.map(item => <NavButton key={item.page} item={item} active={page === item.page} onClick={() => navigate(item.page)} />)}</nav><small>Pesquisa segura</small></aside>
    <main><header className="app-header"><div><div className="mobile-brand">babi<span>.</span></div><p className="eyebrow">{page}</p><h1>{page === 'Visão geral' ? 'O que merece sua atenção?' : page}</h1><p className="sub">Sinais claros para você decidir o próximo passo.</p></div><button className="mobile-more" aria-label="Abrir menu" aria-expanded={moreOpen} onClick={() => setMoreOpen(value => !value)}>•••</button></header>
      {moreOpen && <div className="more-menu"><button onClick={() => navigate('Market Radar')}>Market Radar</button><button onClick={() => navigate('Sistema')}>Sistema</button></div>}
      {page === 'Visão geral' ? <Home data={home} loading={loading} error={error} retry={loadHome} go={navigate} /> : page === 'Descobrir' ? <Discover data={discovery} loading={discoveryLoading} error={discoveryError} retry={loadDiscovery} go={navigate} /> : page === 'Oportunidades' ? <Opportunities data={opportunities} loading={opportunitiesLoading} error={opportunitiesError} retry={loadOpportunities} openEvidence={openLibraryForCandidate} /> : page === 'Market Radar' ? <MarketRadar data={marketRadar} loading={marketRadarLoading} error={marketRadarError} retry={loadMarketRadar} /> : page === 'Biblioteca' ? <Library data={library} loading={libraryLoading} error={libraryError} load={loadLibrary} go={navigate} /> : page === 'Sistema' ? <System data={system} loading={systemLoading} error={systemError} retry={loadSystem} /> : <Skeleton page={page} />}
    </main><MobileNav page={page} go={navigate} moreOpen={moreOpen} setMoreOpen={setMoreOpen} />
  </div>;
}

function NavButton({item, active, onClick}: {item: {page: Page; icon: string}; active: boolean; onClick: () => void}) { return <button className={active ? 'active' : ''} aria-current={active ? 'page' : undefined} onClick={onClick}><span aria-hidden="true">{item.icon}</span>{item.page}</button>; }
function MobileNav({page, go, moreOpen, setMoreOpen}: {page: Page; go: (page: Page) => void; moreOpen: boolean; setMoreOpen: (value: boolean) => void}) { return <nav className="mobile-nav" aria-label="Navegação móvel">{navigation.slice(0, 4).map(item => <NavButton key={item.page} item={item} active={page === item.page} onClick={() => go(item.page)} />)}<button className={moreOpen || page === 'Sistema' || page === 'Market Radar' ? 'active' : ''} onClick={() => setMoreOpen(!moreOpen)}><span aria-hidden="true">•••</span>Mais</button></nav>; }

function Discover({data, loading, error, retry, go}: {data: DiscoveryData | null; loading: boolean; error: boolean; retry: () => Promise<void>; go: (page: Page) => void}) {
  const [query, setQuery] = useState(''); const [actionError, setActionError] = useState<string | null>(null); const [starting, setStarting] = useState(false);
  const submitSearch = async () => { if (!query.trim()) return; setStarting(true); setActionError(null); try { await startSearch(query.trim()); await retry(); } catch (reason) { setActionError(reason instanceof Error ? reason.message : 'Não foi possível iniciar a descoberta.'); } finally { setStarting(false); } };
  const submitMission = async (presetId: string) => { setStarting(true); setActionError(null); try { await startMission(presetId); await retry(); } catch (reason) { setActionError(reason instanceof Error ? reason.message : 'Não foi possível iniciar a missão.'); } finally { setStarting(false); } };
  if (loading && !data) return <DiscoverSkeleton />;
  if (error || !data) return <section className="state-card error"><h2>Não foi possível carregar a descoberta.</h2><p>Tente novamente em alguns instantes.</p><button onClick={() => void retry()}>Tentar novamente</button></section>;
  if (!data.connection.ready) return <><section className="connection-notice"><div><p className="eyebrow">DESCOBRIR</p><h2>A Babi precisa de atenção no TikTok antes de continuar.</h2><p>Verifique a conexão e retorne quando ela estiver pronta.</p></div><button onClick={() => go('Sistema')}>Ver conexão</button></section><DiscoverySections data={data} onMission={submitMission} starting={starting} /></>;
  return <><section className="discover-intro"><p className="eyebrow">DESCOBRIR</p><h2>Encontre produtos, categorias ou sinais novos.</h2><div className="discover-search"><input value={query} onChange={event => setQuery(event.target.value)} onKeyDown={event => { if (event.key === 'Enter') void submitSearch(); }} aria-label="Buscar produto ou tendência" placeholder="Ex.: gadgets para cozinha" /><button disabled={starting || !query.trim()} onClick={() => void submitSearch()}>{starting ? 'Iniciando…' : 'Pesquisar'}</button></div>{actionError && <p className="action-error">{actionError}</p>}</section>{data.active_run ? <ActiveRun run={data.active_run} /> : <DiscoverySections data={data} onMission={submitMission} starting={starting} />}</>;
}
function DiscoverySections({data,onMission,starting}:{data:DiscoveryData;onMission:(id:string)=>Promise<void>;starting:boolean}) { return <><SectionTitle eyebrow="EXPLORAR POR OBJETIVO" title="Missões prontas" /> <section className="preset-list">{data.presets.map(preset => <article key={preset.id}><div><h3>{preset.name}</h3><p>{preset.description}</p><small>{preset.query_count} {preset.query_count === 1 ? 'busca' : 'buscas'}</small></div><button className="text-action" disabled={starting} onClick={() => void onMission(preset.id)}>Iniciar descoberta →</button></article>)}</section><Performance items={data.query_performance} />{data.last_run && <CompletedRun run={data.last_run} />}{!data.last_run && <section className="quiet-empty discover-empty"><h3>Comece sua primeira descoberta</h3><p>Escolha uma busca ou uma missão pronta.</p></section>}</>; }
function ActiveRun({run}:{run:DiscoveryData['active_run']}) { if (!run) return null; const percent=Math.round((run.queries_completed / Math.max(run.queries_total,1))*100); return <section className="active-run"><p className="eyebrow">DESCOBERTA EM ANDAMENTO</p><h2>Busca {Math.min(run.queries_completed + 1, run.queries_total)} de {run.queries_total}</h2><div className="progress" aria-label={`${percent}% concluído`}><span style={{width:`${percent}%`}} /></div><div className="run-stats"><span><b>{formatNumber(run.results)}</b> resultados observados</span><span><b>{formatNumber(run.new_videos)}</b> novos</span><span><b>{formatNumber(run.duplicates)}</b> já conhecidos</span>{run.identified_products !== null && <span><b>{formatNumber(run.identified_products)}</b> produtos identificados</span>}</div>{run.current_query && <p className="current-query">Buscando agora: <b>“{run.current_query}”</b></p>}</section>; }
function CompletedRun({run}:{run:DiscoveryData['last_run']}) { if (!run || run.status === 'PENDING' || run.status === 'READY') return null; return <><SectionTitle eyebrow="ÚLTIMA DESCOBERTA" title="Resumo recente" /><section className="completed-run"><div><h3>{run.status === 'SUCCEEDED' ? 'Descoberta concluída' : 'Descoberta encerrada'}</h3><p>{formatNumber(run.queries_total)} buscas · {formatNumber(run.results)} resultados · {formatNumber(run.new_videos)} novos · {formatNumber(run.duplicates)} já conhecidos</p></div>{run.identified_products !== null && <span>{formatNumber(run.identified_products)} produtos identificados</span>}</section></>; }
function Performance({items}:{items:DiscoveryData['query_performance']}) { if (!items.length) return null; return <><SectionTitle eyebrow="APRENDIZADO" title="Buscas que estão funcionando" /><section className="performance-list">{items.map(item => <article key={item.query}><div><b>{item.query}</b><span>{Math.round((item.novelty_rate || 0)*100)}% de resultados novos</span></div><p>{item.duplicates > item.new_videos ? 'Muitos resultados já conhecidos' : `${formatNumber(item.new_videos)} resultados novos`}</p></article>)}</section></>; }
function DiscoverSkeleton() { return <><section className="discover-intro skeleton-block" /><section className="preset-list">{[1,2,3].map(item => <article className="skeleton-block" key={item} />)}</section></>; }

function MarketRadar({data, loading, error, retry}: {data: MarketRadarData | null; loading: boolean; error: boolean; retry: () => Promise<void>}) {
  const [source, setSource] = useState<MarketSource | null>(null);
  const [category, setCategory] = useState<string | null>(null);
  const [period, setPeriod] = useState('1d');
  const [view, setView] = useState<'grid' | 'list'>('grid');
  const [products, setProducts] = useState<MarketProduct[]>([]);
  const [trends, setTrends] = useState<MarketTrend[]>([]);
  const [history, setHistory] = useState({availableFrom: null as string | null, complete: false});
  const [selected, setSelected] = useState<MarketProduct | null>(null);
  const [filterLoading, setFilterLoading] = useState(false);
  const [filterError, setFilterError] = useState(false);

  useEffect(() => {
    if (!data) return;
    setSource(previous => previous && data.sources.some(item => item.id === previous.id) ? previous : data.sources[0] || null);
    setCategory(previous => previous && data.categories.some(item => item.id === previous) ? previous : data.default_category);
    setProducts(data.products);
    setTrends(data.trends);
  }, [data]);

  const applyFilters = async () => {
    if (!source || source.id !== 'MERCADO_LIVRE') return;
    setFilterLoading(true); setFilterError(false);
    try {
      const [top, nextTrends] = await Promise.all([getMarketTop(category, period), getMarketTrends(category)]);
      setProducts(top.products); setTrends(nextTrends.trends);
      setHistory({availableFrom: top.history_available_from, complete: top.history_complete});
    } catch { setFilterError(true); }
    finally { setFilterLoading(false); }
  };

  if (loading && !data) return <MarketRadarSkeleton />;
  if (error || !data) return <section className="state-card error"><h2>Não foi possível carregar o Market Radar.</h2><p>Tente novamente em alguns instantes.</p><button onClick={() => void retry()}>Tentar novamente</button></section>;
  const operational = source?.id === 'MERCADO_LIVRE' && source.status === 'OPERACIONAL';
  return <>
    <section className="market-hero"><div><p className="eyebrow">MARKET RADAR</p><h2>Descubra produtos e tendências de marketplaces.</h2><p>Dados observados pela Babi a partir das fontes disponíveis.</p></div><div className="market-update"><span>{source?.quality || 'Fonte indisponível'}</span><small>{data.last_updated_at ? `Atualizado ${formatDetectedAt(data.last_updated_at).replace('Detectado pela Babi ', '')}` : 'Sem atualização real'}</small></div></section>
    <section className="market-sources" aria-label="Marketplaces disponíveis">{data.sources.map(item => <button key={item.id} className={source?.id === item.id ? 'active' : ''} aria-pressed={source?.id === item.id} onClick={() => setSource(item)}><b>{item.label}</b><span className={`market-source-status ${item.status.toLowerCase()}`}>{marketSourceLabel(item.status)}</span><small>{item.description}</small></button>)}</section>
    {(source?.id === "SHOPEE" || source?.id === "ALIEXPRESS") && <CommercialRanking marketplace={source.id} />}
    {(source?.id === "SHOPEE" || source?.id === "ALIEXPRESS") && <FreeCounterGrowth marketplace={source.id} />}
    {(source?.id === "SHOPEE" || source?.id === "ALIEXPRESS") && <ImportedMarketProducts marketplace={source.id} />}
    {!operational ? <section className="market-unavailable"><h3>{source?.label || 'Fonte'} {marketSourceLabel(source?.status || 'INDISPONIVEL')}</h3><p>{source?.id === 'ALIEXPRESS' ? 'O adapter existe apenas para fixtures de teste; ainda não há acesso à API para dados reais.' : source?.description || 'Esta fonte ainda não está disponível para consulta.'}</p></section> : <>
      <section className="market-controls"><div className="market-filter"><label>Categoria<select value={category || ''} onChange={event => setCategory(event.target.value || null)}><option value="">Todas as categorias observadas</option>{data.categories.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label><label>Período<select value={period} onChange={event => setPeriod(event.target.value)}>{['1d','3d','7d','15d','30d','60d','90d'].map(item => <option key={item} value={item}>{marketPeriodLabel(item)}</option>)}</select></label><button onClick={() => void applyFilters()} disabled={filterLoading}>{filterLoading ? 'Atualizando…' : 'Aplicar filtros'}</button></div><div className="market-view-toggle" aria-label="Visualização"><button className={view === 'grid' ? 'active' : ''} aria-pressed={view === 'grid'} onClick={() => setView('grid')}>Grade</button><button className={view === 'list' ? 'active' : ''} aria-pressed={view === 'list'} onClick={() => setView('list')}>Lista</button></div></section>
      {filterError && <p className="action-error">Não foi possível atualizar os filtros. Os dados anteriores continuam visíveis.</p>}
      {history.availableFrom && <p className="market-history-note">Histórico observado pela Babi desde {formatDetectedAt(history.availableFrom).replace('Detectado pela Babi ', '')}.{history.complete ? ' A janela selecionada está completa.' : ' A janela selecionada ainda está em construção.'}</p>}
      <VerifiedSalesWindow category={category} />
      <SectionTitle eyebrow="RANKING OFICIAL" title="Produtos mais vendidos" />
      {products.length ? <section className={`market-products ${view}`} aria-label="Produtos do ranking">{products.slice(0, 20).map(item => <MarketProductCard key={item.external_id} item={item} view={view} onSelect={() => setSelected(item)} />)}</section> : <section className="state-card empty-state"><h3>Ainda não há produtos observados nesta seleção.</h3><p>Nenhuma coleta é iniciada automaticamente por esta página.</p></section>}
      <SectionTitle eyebrow="TENDÊNCIAS DE BUSCA" title="O que as pessoas estão pesquisando" />
      {trends.length ? <section className="market-trends"><p>Tendências semanais da fonte. Não representam ranking de vendas.</p><div>{trends.map(item => <article key={`${item.trend_type}-${item.position}-${item.keyword}`}><span>{item.position}</span><div><b>{item.keyword}</b><small>{marketTrendLabel(item.trend_type)}</small></div>{item.url && <a href={item.url} target="_blank" rel="noreferrer">Ver busca</a>}</article>)}</div></section> : <section className="quiet-empty">Ainda não há tendências observadas para esta categoria.</section>}
    </>}
    {selected && <MarketProductDrawer item={selected} history={history} onClose={() => setSelected(null)} />}
  </>;
}

function VerifiedSalesWindow({category}:{category:string|null}) {
  type Entry = {external_id:string;title:string;source_category:string|null;rank:number|null;price:number|null;currency:string|null;observed_at:string;product_url:string|null;image_url:string|null;units_sold_in_window:number|null;visits_in_window:number|null;rank_movement:number|null;observation_count:number;rank_movement_label:string};
  type Payload = {products:Entry[];observation_count:number;window_hours:number;complete_window:boolean;notice:string};
  const [hours,setHours]=useState('48');
  const [sort,setSort]=useState('ranking');
  const [top,setTop]=useState('');
  const [result,setResult]=useState<Payload|null>(null);
  const [loading,setLoading]=useState(false);
  const [error,setError]=useState(false);
  useEffect(()=>{
    let active=true;
    setLoading(true);setError(false);setResult(null);
    const params=new URLSearchParams({hours,sort});
    if(category) params.set('category',category);
    if(top) params.set('top',top);
    fetch('/api/v2/market-radar/sales-window?'+params,{headers:{Accept:'application/json'}})
      .then(async response=>{if(!response.ok)throw new Error('unavailable');return response.json() as Promise<Payload>;})
      .then(value=>{if(active)setResult(value);})
      .catch(()=>{if(active)setError(true);})
      .finally(()=>{if(active)setLoading(false);});
    return ()=>{active=false;};
  },[hours,sort,top,category]);
  return <section className="market-unavailable" aria-label="Janela observada de mais vendidos">
    <h3>Mais vendidos observados · 48 horas / semanas</h3>
    <p>Posições do ranking oficial observadas pela Babi no período escolhido. Não são quantidades de vendas. Sem autorização para unidades vendidas ou visitas de concorrentes, os valores aparecem indisponíveis.</p>
    <div className="market-controls"><div className="market-filter">
      <label>Janela<select value={hours} onChange={event=>setHours(event.target.value)}><option value="48">Últimas 48 horas</option><option value="168">Últimos 7 dias</option><option value="720">Últimos 30 dias</option></select></label>
      <label>Ordenar<select value={sort} onChange={event=>setSort(event.target.value)}><option value="ranking">Posição no ranking</option><option value="rising">Subindo no ranking</option><option value="recent">Mais recente</option><option value="price_low">Menor preço disponível</option><option value="price_high">Maior preço disponível</option></select></label>
      <label>Filtro<select value={top} onChange={event=>setTop(event.target.value)}><option value="">Todas as posições</option><option value="5">Top 5</option><option value="10">Top 10</option><option value="20">Top 20</option></select></label>
    </div></div>
    {loading?<p>Consultando observações…</p>:error?<p>Falha na consulta das observações.</p>:!result?<p>Sem dados.</p>:<>
      <p>{result.observation_count} produtos observados na janela selecionada. Histórico completo: {result.complete_window?'Sim':'Ainda não comprovado'}.</p>
      <div className="market-products grid">{result.products.map(item=><article className="market-product-card" key={item.external_id+'-'+item.source_category}>
        <div className="market-product-main">
        {item.image_url&&<img src={item.image_url} alt="" loading="lazy" style={{maxWidth:'100%',maxHeight:110,objectFit:'contain'}}/>}
        <span className="market-rank">{item.rank?'#'+item.rank+' no ranking':'Sem posição'}</span>
        <h3>{item.title}</h3><small>{item.source_category||'Categoria não informada'}</small>
        <p>{item.price!==null&&item.currency?formatCurrency(item.price,item.currency):'Preço indisponível'}</p>
        <small>Movimento: {item.rank_movement===null?"Histórico insuficiente":item.rank_movement>0?"Subiu "+item.rank_movement+" posições":item.rank_movement<0?"Caiu "+Math.abs(item.rank_movement)+" posições":"Estável"} · {item.observation_count} observações</small><small>Vendas em {hours==='48'?'48h':hours==='168'?'7 dias':'30 dias'}: indisponível · Visitas: indisponível</small>
        <small>Observado: {formatDetectedAt(item.observed_at)}</small>
        {item.product_url&&<a href={item.product_url} target="_blank" rel="noreferrer">Ver produto na fonte</a>}
        </div>
      </article>)}</div>
      {result.products.length===0&&<p>Não há observações comprovadas nesta janela. Nenhum número foi estimado.</p>}
    </>}
  </section>;
}

function CommercialRanking({marketplace}:{marketplace:'SHOPEE'|'ALIEXPRESS'}) {
  type Product = {product_id:string;title:string;image_url:string|null;product_url:string|null;price:number|null;currency:string|null;rating:number|null;rating_count:number|null;metric_value:number;metric_kind:string;provider:string;observed_at:string;window_start:string|null;window_end:string|null};
  const [metric,setMetric]=useState('sold_30d');
  const [result,setResult]=useState<{products:Product[];total:number;note:string}|null>(null);
  const [loading,setLoading]=useState(false);
  const [error,setError]=useState(false);
  useEffect(()=>{
    let active=true;
    setLoading(true);setError(false);setResult(null);
    fetch('/api/v2/market-radar/commercial-ranking?'+new URLSearchParams({marketplace,metric,limit:'30'}))
      .then(async r=>{if(!r.ok)throw new Error('unavailable');return r.json() as Promise<{products:Product[];total:number;note:string}>;})
      .then(data=>{if(active)setResult(data);})
      .catch(()=>{if(active)setError(true);})
      .finally(()=>{if(active)setLoading(false);});
    return ()=>{active=false;};
  },[marketplace,metric]);
  const labels:Record<string,string>={sold_30d:'Unidades vendidas (30 dias)',estimated_sold_30d:'Vendas estimadas (30 dias)',historical_sold:'Vendas acumuladas',views_total:'Visualizações acumuladas',revenue_30d:'Faturamento (30 dias)'};
  return <section className="market-unavailable" aria-label="Ranking comercial por métricas de fornecedor">
    <h3>Ranking comercial · {marketplace==='SHOPEE'?'Shopee':'AliExpress'}</h3>
    <p>Métricas observadas por fornecedor com origem identificada. Valores estimados nunca são tratados como vendas exatas. Contadores acumulados não representam vendas em 48 horas.</p>
    <div className="market-controls"><div className="market-filter"><label>Ordenar por métrica<select value={metric} onChange={e=>setMetric(e.target.value)}>{Object.entries(labels).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label></div></div>
    {loading?<p>Consultando métricas…</p>:error?<p>Não foi possível carregar o ranking comercial.</p>:!result||result.products.length===0?<p>Ainda não temos dados comerciais reais autorizados para este filtro. Nenhum produto foi inventado.</p>:
      <div className="market-products grid">{result.products.map(item=><article className="market-product-card" key={item.product_id+'-'+item.metric_kind+'-'+item.provider}>
        <div className="market-product-main">
          {item.image_url&&<img src={item.image_url} alt="" loading="lazy" style={{maxWidth:'100%',maxHeight:120,objectFit:'contain'}}/>}
          <h3>{item.title}</h3>
          <strong>{formatNumber(item.metric_value)} {metric==='revenue_30d'?'em receita':metric==='views_total'?'visualizações':'unidades'}</strong>
          <small>{item.metric_kind==='ESTIMATED_PROVIDER'?'Estimativa do fornecedor':item.metric_kind==='CUMULATIVE_OBSERVED'?'Contador acumulado':'Métrica reportada pelo fornecedor'} · {item.provider}</small>
          <small>{item.window_start&&item.window_end?'Janela: '+item.window_start.slice(0,10)+' a '+item.window_end.slice(0,10):'Período acumulado não especificado'}</small>
          {item.price!==null&&item.currency&&<p>{formatCurrency(item.price,item.currency)}</p>}
          {item.rating!==null&&<small>Avaliação: {item.rating} · {item.rating_count??'—'} avaliações</small>}
          <small>Observado: {formatDetectedAt(item.observed_at)}</small>
          {item.product_url&&<a href={item.product_url} target="_blank" rel="noreferrer">Abrir produto</a>}
        </div>
      </article>)}</div>}
  </section>;
}

function FreeCounterGrowth({marketplace}:{marketplace:'SHOPEE'|'ALIEXPRESS'}) {
 type Growth = {product_id:string;metric:string;growth:number;growth_pct:number|null;provider:string;baseline_at:string;latest_at:string;sampled_hours:number};
 const [hours,setHours]=useState('48');const [data,setData]=useState<Growth[]>([]);const [error,setError]=useState(false);
 const [loading,setLoading]=useState(true);
 useEffect(()=>{let live=true;setLoading(true);setError(false);
 fetch('/api/v2/market-radar/commercial-growth?'+new URLSearchParams({marketplace,hours}))
 .then(async r=>{if(!r.ok)throw Error('unavailable');return r.json() as Promise<{products:Growth[]}>})
 .then(v=>{if(live)setData(v.products||[])})
 .catch(()=>{if(live)setError(true)})
 .finally(()=>{if(live)setLoading(false)});
 return()=>{live=false};},[marketplace,hours]);
 return <section className="market-unavailable" aria-label="Crescimento observado por contadores">
 <h3>Crescimento por contadores públicos</h3>
 <p>Motor próprio da Babi, sem API comercial paga. Compara duas medições do mesmo produto e fonte; não interpreta diferença como vendas exatas da janela.</p>
 <div className="market-controls"><div className="market-filter"><label>Comparar<select value={hours} onChange={e=>setHours(e.target.value)}><option value="48">48 horas</option><option value="168">7 dias</option><option value="720">30 dias</option></select></label></div></div>
 {loading?<p>Carregando histórico…</p>:error?<p>Não foi possível consultar o histórico.</p>:data.length===0?<p>Aguardando duas observações comparáveis do mesmo contador. Nenhum crescimento fictício.</p>:<div className="market-products grid">{data.map(item=><article key={item.product_id+'-'+item.metric+'-'+item.provider} className="market-product-card"><div className="market-product-main"><h3>Produto {item.product_id}</h3><strong>+{formatNumber(item.growth)} {item.metric==='views_total'?'visualizações observadas':'unidades no contador'}</strong><small>{item.growth_pct===null?'Variação percentual indisponível':item.growth_pct.toFixed(1)+'% de variação'}</small><small>Intervalo observado: {item.sampled_hours} horas · {item.provider}</small><small>{item.baseline_at.slice(0,16)} → {item.latest_at.slice(0,16)}</small></div></article>)}</div>}
 </section>;
}

function ImportedMarketProducts({marketplace}: {marketplace: 'SHOPEE' | 'ALIEXPRESS'}) {
  type Imported = {external_id:string; title:string; source_category:string|null; price:number|null; currency:string|null; product_url:string|null; imported_at:string; source_kind:string};
  const [items,setItems] = useState<Imported[]>([]);
  const [loading,setLoading] = useState(true);
  const [error,setError] = useState(false);
  useEffect(() => {
    let active = true;
    setLoading(true);setError(false);setItems([]);
    fetch('/api/v2/market-radar/offline-imports/'+marketplace,{headers:{Accept:'application/json'}})
      .then(async response => {if (!response.ok) throw new Error('not available');return response.json() as Promise<{products:Imported[]}>;})
      .then(payload => {if (active) setItems(payload.products || []);})
      .catch(() => {if (active) setError(true);})
      .finally(() => {if(active) setLoading(false);});
    return () => {active=false;};
  },[marketplace]);
  return <section className="market-unavailable" aria-label="Produtos de arquivos importados">
    <h3>Produtos importados · {marketplace === 'SHOPEE' ? 'Shopee' : 'AliExpress'}</h3>
    <p>Arquivos locais. Não representam ranking oficial, coleta ao vivo, vendas confirmadas ou visitas em 48 horas.</p>
    {loading ? <p>Carregando arquivos importados…</p> : error ? <p>Não foi possível consultar os arquivos importados.</p> :
    items.length ? <div className="market-products grid">{items.map(item => <article className="market-product-card" key={item.external_id}>
      <div className="market-product-main"><span className="market-rank">Sem posição oficial</span><h3>{item.title}</h3>
      <p>{item.source_category || 'Sem categoria'}</p>
      {item.price !== null && item.currency ? <strong>{formatCurrency(item.price,item.currency)}</strong> : <small>Preço não informado</small>}
      <small>Origem: {item.source_kind === 'FIXTURE' ? 'Fixture de teste' : 'Arquivo importado'} · {formatDetectedAt(item.imported_at)}</small>
      {item.product_url && <a href={item.product_url} target="_blank" rel="noreferrer">Abrir produto</a>}</div>
    </article>)}</div> : <p>Nenhum arquivo importado disponível. A Babi não cria produtos fictícios.</p>}
  </section>;
}

function MarketProductCard({item,view,onSelect}:{item:MarketProduct;view:'grid'|'list';onSelect:()=>void}) { const price = formatCurrency(item.price, item.currency); return <article className="market-product-card"><div className="market-product-image">{item.image_url ? <img src={item.image_url} alt="" /> : <span>Sem imagem</span>}</div><div className="market-product-main"><div className="market-product-meta"><span className="market-rank">{item.rank ? `#${item.rank}` : 'Sem posição'}</span><span>{detailStatusLabel(item.detail_status)}</span></div><h3>{item.title || 'Produto sem nome disponível'}</h3><p>{item.source_category || 'Categoria não informada'}</p>{price ? <strong>{price}</strong> : <small>Preço não informado pela fonte</small>}</div><div className="market-product-actions"><button className="text-action" onClick={onSelect}>Ver evidências →</button>{item.product_url && <a href={item.product_url} target="_blank" rel="noreferrer">Abrir fonte</a>}</div>{view === 'list' && <p className="market-list-source">Mercado Livre · {item.observed_at ? formatDetectedAt(item.observed_at) : 'Observação sem data'}</p>}</article>; }
function MarketProductDrawer({item,history,onClose}:{item:MarketProduct;history:{availableFrom:string|null;complete:boolean};onClose:()=>void}) { const price = formatCurrency(item.price,item.currency); return <div className="drawer-backdrop" role="presentation" onMouseDown={onClose}><aside className="opportunity-drawer market-drawer" role="dialog" aria-modal="true" aria-label={`Detalhes de ${item.title}`} onMouseDown={event => event.stopPropagation()}><button className="drawer-close" onClick={onClose} aria-label="Fechar detalhes">×</button>{item.image_url && <img className="drawer-image" src={item.image_url} alt=""/>}<p className="eyebrow">MERCADO LIVRE · FONTE OFICIAL</p><h2>{item.title || 'Produto sem nome disponível'}</h2><div className="drawer-state"><span>{item.rank ? `#${item.rank} no ranking oficial` : 'Posição não informada'}</span><span>{detailStatusLabel(item.detail_status)}</span></div><h3>Dados observados</h3><dl className="market-detail-list"><div><dt>Categoria</dt><dd>{item.source_category || 'Não informada'}</dd></div><div><dt>Preço</dt><dd>{price || 'Não informado pela fonte'}</dd></div><div><dt>Observado</dt><dd>{item.observed_at ? formatDetectedAt(item.observed_at) : 'Data indisponível'}</dd></div></dl>{item.product_url && <a className="market-official-link" href={item.product_url} target="_blank" rel="noreferrer">Abrir produto na fonte oficial</a>}<h3>Detalhes e evidências</h3><p>{detailStatusExplanation(item)}</p>{item.missing_detail_fields.length > 0 && <p className="market-missing">Não informado: {item.missing_detail_fields.map(marketFieldLabel).join(', ')}.</p>}<h3>Histórico do produto</h3>{history.complete ? <p>Há observações suficientes para a janela selecionada. A evolução será exibida quando houver posições ou preços comparáveis.</p> : <p>Estamos construindo o histórico deste produto.</p>}<details><summary>Detalhes técnicos</summary><dl><div><dt>ID externo</dt><dd>{item.external_id}</dd></div><div><dt>Origem</dt><dd>API oficial do Mercado Livre</dd></div><div><dt>Tipo de ranking</dt><dd>{item.evidence_json.ranking_type || 'Não informado'}</dd></div></dl></details></aside></div>; }
function marketSourceLabel(status: MarketSource['status']) { return ({OPERACIONAL:'Operacional',AGUARDANDO_AUTORIZACAO:'Aguardando autorização',EM_PREPARACAO:'Em preparação',INDISPONIVEL:'Indisponível'} as Record<MarketSource['status'],string>)[status]; }
function marketPeriodLabel(value:string) { return ({'1d':'1 dia','3d':'3 dias','7d':'7 dias','15d':'15 dias','30d':'30 dias','60d':'60 dias','90d':'90 dias'} as Record<string,string>)[value] || value; }
function marketTrendLabel(value:string) { return ({FASTEST_GROWING:'Maior crescimento',MOST_WANTED:'Mais desejada',POPULAR_TREND:'Tendência popular'} as Record<string,string>)[value] || 'Tendência observada'; }
function detailStatusLabel(status:MarketProduct['detail_status']) { return ({DETAILS_AVAILABLE:'Detalhes disponíveis',DETAILS_PARTIAL:'Detalhes parciais',DETAILS_RESTRICTED:'Detalhes restritos'} as Record<MarketProduct['detail_status'],string>)[status]; }
function marketFieldLabel(field:string) { return ({title:'nome',image:'imagem',price:'preço',url:'link oficial'} as Record<string,string>)[field] || field; }
function detailStatusExplanation(item:MarketProduct) { if (item.detail_status === 'DETAILS_RESTRICTED') return 'A fonte retornou uma restrição para detalhes adicionais. O registro do ranking oficial foi preservado.'; if (item.detail_status === 'DETAILS_PARTIAL') return 'A fonte forneceu apenas parte dos detalhes comerciais deste produto.'; return 'Os detalhes disponíveis foram obtidos pela fonte oficial.'; }
function MarketRadarSkeleton() { return <><section className="market-hero skeleton-block" /><section className="market-sources">{[1,2,3,4,5].map(item => <div className="skeleton-block" key={item} />)}</section><section className="market-products grid">{[1,2,3].map(item => <article className="skeleton-block" key={item} />)}</section></>; }

function Opportunities({data, loading, error, retry, openEvidence}: {data: OpportunitiesData | null; loading: boolean; error: boolean; retry: () => Promise<void>; openEvidence: (candidateId: string) => void}) {
  const [selected, setSelected] = useState<OpportunityV2 | null>(null);
  if (loading && !data) return <><section className="opportunities-hero skeleton-block" /><section className="primary-opportunity skeleton-block" /></>;
  if (error || !data) return <section className="state-card error"><h2>Não foi possível carregar as oportunidades.</h2><p>Tente novamente em alguns instantes.</p><button onClick={() => void retry()}>Tentar novamente</button></section>;
  const [main, ...rest] = data.top;
  return <><section className="opportunities-hero"><p className="eyebrow">OPORTUNIDADES</p><h2>Veja quais sinais estão ganhando força e por que merecem atenção.</h2></section><section className="opportunity-kpis"><Kpi value={data.summary.strong} label="Em alta" /><Kpi value={data.summary.watching} label="Em observação" /><Kpi value={data.summary.saturated} label="Saturados" /><Kpi value={data.summary.total} label="Total analisado" /></section>{main ? <><SectionTitle eyebrow="PRINCIPAL OPORTUNIDADE" title="Merecem atenção" /><OpportunityFeature item={main} onAnalyze={() => setSelected(main)} />{rest.length > 0 && <section className="opportunity-list">{rest.map(item => <OpportunityCompact key={item.id} item={item} onAnalyze={() => setSelected(item)} />)}</section>}</> : <section className="state-card empty-state"><h2>Nenhum sinal forte agora</h2><p>A Babi ainda está reunindo evidências.</p></section>}<SectionTitle eyebrow="EM OBSERVAÇÃO" title="Sinais que ainda precisam de mais evidência" />{data.watchlist.length ? <section className="opportunity-list">{data.watchlist.map(item => <OpportunityCompact key={item.id} item={item} onAnalyze={() => setSelected(item)} />)}</section> : <section className="quiet-empty">Não há sinais em observação no momento.</section>}<SectionTitle eyebrow="SINAIS SATURADOS" title="Separados para não competir com prioridades" />{data.saturated.length ? <section className="opportunity-list saturated-list">{data.saturated.map(item => <OpportunityCompact key={item.id} item={item} onAnalyze={() => setSelected(item)} />)}</section> : <section className="quiet-empty">Nenhum sinal saturado no momento.</section>}{selected && <OpportunityDrawer item={selected} onClose={() => setSelected(null)} onEvidence={() => openEvidence(selected.id)} />}</>;
}
function OpportunityFeature({item,onAnalyze}:{item:OpportunityV2;onAnalyze:()=>void}) { return <article className="primary-opportunity opportunity-feature"><div className="primary-main"><div className="opportunity-top"><span className="rank">01</span><span className="human-status">{item.state.movement}</span></div><h3>{item.display_name}</h3>{item.original_name && item.original_name !== item.display_name && <p className="original-name">{item.original_name}</p>}<h4>Por que chamou atenção</h4><ul>{item.why.slice(0,2).map(reason => <li key={reason}>✓ {reason}</li>)}</ul><p className="saturation-copy">Saturação {item.state.saturation.toLowerCase()}</p><button onClick={onAnalyze}>Analisar <span>→</span></button></div><div className="signal-grid"><Signal value={item.metrics.queries} label="tipos de busca" /><Signal value={item.metrics.creators} label="criadores" /><Signal value={item.metrics.observations} label="observações" /><div className="signal-note"><span className="status-dot" />{item.state.label}</div></div></article>; }
function OpportunityCompact({item,onAnalyze}:{item:OpportunityV2;onAnalyze:()=>void}) { return <article className="opportunity-compact"><div><span className="human-status">{item.state.label}</span><h3>{item.display_name}</h3>{item.original_name && item.original_name !== item.display_name && <small>{item.original_name}</small>}<p>{formatNumber(item.metrics.queries)} buscas · {formatNumber(item.metrics.observations)} observações</p><em>{item.why[0] || 'Evidência em formação.'}</em></div><button className="text-action" onClick={onAnalyze}>Analisar →</button></article>; }
function OpportunityDrawer({item,onClose,onEvidence}:{item:OpportunityV2;onClose:()=>void;onEvidence:()=>void}) { return <div className="drawer-backdrop" role="presentation" onMouseDown={onClose}><aside className="opportunity-drawer" role="dialog" aria-modal="true" aria-label={`Análise de ${item.display_name}`} onMouseDown={event => event.stopPropagation()}><button className="drawer-close" onClick={onClose} aria-label="Fechar análise">×</button><p className="eyebrow">PRODUTO</p><h2>{item.display_name}</h2>{item.original_name && item.original_name !== item.display_name && <p className="original-name">{item.original_name}</p>}<div className="drawer-state"><span>{item.state.label}</span><span>{item.state.movement}</span><span>Saturação {item.state.saturation.toLowerCase()}</span></div><h3>Evidência</h3><div className="drawer-metrics"><Signal value={item.metrics.observations} label="observações" /><Signal value={item.metrics.queries} label="buscas" /><Signal value={item.metrics.creators} label="criadores" /></div>{item.related_video_count > 0 && <button className="text-action evidence-link" onClick={onEvidence}>Ver evidências →</button>}<h3>Por que está aqui</h3><ul>{item.why.map(reason => <li key={reason}>{reason}</li>)}</ul><h3>Limitações</h3>{item.limits.length ? <ul>{item.limits.map(limit => <li key={limit}>{limit}</li>)}</ul> : <p className="quiet-empty">Nenhuma limitação adicional registrada.</p>}<details><summary>Análise avançada</summary><dl>{Object.entries(item.advanced).map(([key,value]) => <div key={key}><dt>{key.replaceAll('_',' ')}</dt><dd>{value === null ? 'Dados insuficientes' : String(value)}</dd></div>)}</dl></details></aside></div>; }

function System({data,loading,error,retry}:{data:SystemData|null;loading:boolean;error:boolean;retry:()=>Promise<void>}) {
  const [diagnosticsOpen,setDiagnosticsOpen]=useState(false);
  if (loading && !data) return <><section className="system-hero skeleton-block"/><section className="system-status-grid">{[1,2,3,4,5].map(item=><article className="skeleton-block" key={item}/>)}</section></>;
  if (error || !data) return <section className="state-card error"><h2>Não foi possível carregar o sistema.</h2><p>Tente novamente em alguns instantes.</p><button onClick={()=>void retry()}>Tentar novamente</button></section>;
  const statusItems=[['Babi',data.backend.label,data.backend.status],['Navegador',data.browser.label,data.browser.status],['TikTok',data.tiktok.label,data.tiktok.status],['Sessão',data.session.label,data.session.status],['Segurança',data.security.label,data.security.status]] as const;
  return <><section className={`system-hero ${data.overall.status.toLowerCase()}`}><p className="eyebrow">SISTEMA</p><h2>{data.overall.label}</h2><p>{data.overall.status==='HEALTHY'?'A Babi está pronta para pesquisa segura.':'Revise o TikTok ou a conexão antes de iniciar uma descoberta.'}</p></section><section className="system-status-grid">{statusItems.map(([name,label,status])=><article key={name}><span className={`system-dot ${status.toLowerCase()}`}/><small>{name}</small><strong>{label}</strong></article>)}</section><section className="system-detail-grid"><article><p className="eyebrow">LEITURA DIRETA DE VÍDEOS</p><h3>{data.direct_video_enrichment.label}</h3><p>{data.direct_video_enrichment.status==='PAUSED'?'A pesquisa continua disponível normalmente.':'Disponível conforme o contrato operacional.'}</p></article><article><p className="eyebrow">QUALIDADE DA BIBLIOTECA</p><h3>{formatNumber(data.data_quality.videos)} vídeos</h3><p>{formatNumber(data.data_quality.complete)} completos · {formatNumber(data.data_quality.partial)} parciais · {formatNumber(data.data_quality.minimal)} mínimos</p></article></section><section className="system-events"><SectionTitle eyebrow="ATIVIDADE" title="Eventos recentes" action="Ver logs técnicos" onAction={()=>setDiagnosticsOpen(true)}/>{data.events.length?<div>{data.events.map((event,index)=><article key={`${event.at}-${index}`}><time>{formatDetectedAt(event.at)}</time><span>{event.label}</span></article>)}</div>:<p className="quiet-empty">Nenhum evento recente disponível.</p>}</section><details className="system-accordion" open={diagnosticsOpen} onToggle={event=>setDiagnosticsOpen((event.target as HTMLDetailsElement).open)}><summary>Diagnóstico avançado</summary><pre>{JSON.stringify(data.diagnostics,null,2)}</pre></details><details className="system-accordion"><summary>Laboratório</summary><ul>{data.laboratory.map(item=><li key={item.name}><b>{item.name}</b><span>{item.status}</span></li>)}</ul></details><section className="external-sources"><SectionTitle eyebrow="FUTURO" title="Fontes externas" /><p>Nenhuma fonte de marketplace configurada.</p><div>{data.external_sources.map(item=><span key={item.name}><b>{item.name}</b>{item.status}</span>)}</div></section></>;
}

function Library({data,loading,error,load,go}:{data:LibraryData|null;loading:boolean;error:boolean;load:(params?:Record<string,string|number|boolean|undefined>)=>Promise<void>;go:(page:Page)=>void}) {
  const [text,setText]=useState(''); const [quality,setQuality]=useState(''); const [identified,setIdentified]=useState(false); const [query,setQuery]=useState(''); const [creator,setCreator]=useState(''); const [sort,setSort]=useState('recent'); const [detail,setDetail]=useState<LibraryDetail|null>(null); const [filtersOpen,setFiltersOpen]=useState(false);
  const apply=(page=1)=>void load({page,page_size:20,text,quality,identified:identified||undefined,query,creator,sort});
  const open=async(item:LibraryItem)=>{try{setDetail(await getLibraryDetail(item.video_id));}catch{/* the list remains usable if one detail is unavailable */}};
  if(loading&&!data)return <><section className="library-hero skeleton-block"/><section className="library-table skeleton-block"/></>;
  if(error||!data)return <section className="state-card error"><h2>Não foi possível carregar a biblioteca.</h2><p>Tente novamente em alguns instantes.</p><button onClick={()=>void apply()}>Tentar novamente</button></section>;
  if(!data.total&&!text&&!quality&&!identified&&!query&&!creator)return <section className="state-card empty-state"><h2>Sua biblioteca ainda está vazia.</h2><p>Comece uma descoberta para coletar evidências.</p><button onClick={()=>go('Descobrir')}>Ir para Descobrir</button></section>;
  return <><section className="library-hero"><p className="eyebrow">BIBLIOTECA</p><h2>Explore as evidências coletadas pela Babi.</h2><div className="library-search"><input value={text} onChange={event=>setText(event.target.value)} onKeyDown={event=>{if(event.key==='Enter')apply();}} placeholder="Buscar na biblioteca" aria-label="Buscar na biblioteca"/><button onClick={()=>apply()}>Buscar</button><button className="filter-mobile" onClick={()=>setFiltersOpen(!filtersOpen)}>Filtros</button></div><div className={`library-filters ${filtersOpen?'open':''}`}><select aria-label="Qualidade" value={quality} onChange={event=>setQuality(event.target.value)}><option value="">Qualidade: Todas</option><option value="COMPLETE">Completo</option><option value="PARTIAL">Parcial</option><option value="MINIMAL">Dados mínimos</option></select><label><input type="checkbox" checked={identified} onChange={event=>setIdentified(event.target.checked)}/> Produto identificado</label><select aria-label="Busca de origem" value={query} onChange={event=>setQuery(event.target.value)}><option value="">Busca: Todas</option>{data.filters.queries.map(value=><option key={value}>{value}</option>)}</select><select aria-label="Criador" value={creator} onChange={event=>setCreator(event.target.value)}><option value="">Criador: Todos</option>{data.filters.creators.map(value=><option key={value}>{value}</option>)}</select><select aria-label="Ordenação" value={sort} onChange={event=>setSort(event.target.value)}><option value="recent">Mais recentes</option><option value="oldest">Mais antigos</option><option value="views">Mais visualizações</option><option value="complete">Mais completos</option></select><button className="text-action" onClick={()=>apply()}>Aplicar filtros</button></div></section><div className="library-count"><b>{formatNumber(data.total)}</b> resultados</div>{data.items.length?<section className="library-table"><div className="library-head"><span>Conteúdo</span><span>Produto</span><span>Métricas</span><span>Busca</span><span>Detectado</span><span>Qualidade</span></div>{data.items.map(item=><LibraryRow key={item.video_id} item={item} onOpen={()=>void open(item)}/>)}</section>:<section className="state-card"><h2>Nenhum resultado encontrado</h2><p>Tente remover alguns filtros.</p></section>}<div className="library-pagination">{data.page>1&&<button className="text-action" onClick={()=>apply(data.page-1)}>Página anterior</button>}{data.total>data.page*data.page_size&&<button className="load-more" onClick={()=>apply(data.page+1)}>Carregar mais</button>}</div>{detail&&<LibraryDrawer item={detail} onClose={()=>setDetail(null)} />}</>;
}
function LibraryRow({item,onOpen}:{item:LibraryItem;onOpen:()=>void}) { const metric=Object.entries(item.metrics).find(([,value])=>value!==null); return <button className="library-row" onClick={onOpen}><span className="library-content"><span className="library-thumb">{item.thumbnail_url&&<img src={item.thumbnail_url} alt=""/>}</span><span><b>{item.creator?`@${item.creator.replace(/^@/,'')}`:'Criador indisponível'}</b><small>{item.caption||'Conteúdo sem descrição disponível.'}</small></span></span><span>{item.product.name||'Ainda não identificado'}</span><span>{metric?<><b>{formatNumber(metric[1] as number)}</b> {metricLabel(metric[0])}</>:'Sem métricas nesta captura'}</span><span>{item.query||'—'}</span><span>{formatDetectedAt(item.first_seen_at)}</span><span className={`quality-badge ${item.data_quality.toLowerCase()}`}>{({COMPLETE:'Completo',PARTIAL:'Parcial',MINIMAL:'Mínimo'} as Record<string,string>)[item.data_quality]}</span></button>; }
function LibraryDrawer({item,onClose}:{item:LibraryDetail;onClose:()=>void}) { const metrics=Object.entries(item.metrics).filter(([,value])=>value!==null); return <div className="drawer-backdrop" role="presentation" onMouseDown={onClose}><aside className="opportunity-drawer library-drawer" role="dialog" aria-modal="true" aria-label="Detalhe da evidência" onMouseDown={event=>event.stopPropagation()}><button className="drawer-close" onClick={onClose} aria-label="Fechar detalhe">×</button>{item.thumbnail_url&&<img className="drawer-image" src={item.thumbnail_url} alt=""/>}<p className="eyebrow">EVIDÊNCIA COLETADA</p><h2>{item.creator?`@${item.creator.replace(/^@/,'')}`:'Conteúdo observado'}</h2><p>{item.caption||'Descrição indisponível.'}</p><a href={item.video_url} target="_blank" rel="noreferrer">Abrir no TikTok</a><h3>Produto associado</h3><p>{item.product.name||'Ainda não identificado'}</p><h3>Métricas</h3>{metrics.length?<div className="drawer-metrics">{metrics.map(([name,value])=><div key={name}><strong>{formatNumber(value as number)}</strong><span>{metricLabel(name)}</span></div>)}</div>:<p className="quiet-empty">Sem métricas nesta captura.</p>}<h3>Histórico observado pela Babi</h3>{item.appearances.length?<ul>{item.appearances.map((entry,index)=><li key={`${entry.observed_at}-${index}`}>{entry.search_query} · {formatDetectedAt(entry.observed_at)}</li>)}</ul>:<p className="quiet-empty">Uma única observação disponível.</p>}<details><summary>Detalhes técnicos</summary><dl><div><dt>ID do vídeo</dt><dd>{item.video_id}</dd></div><div><dt>Qualidade</dt><dd>{item.data_quality}</dd></div></dl></details></aside></div>; }

function Home({data, loading, error, retry, go}: {data: HomeData | null; loading: boolean; error: boolean; retry: () => Promise<void>; go: (page: Page) => void}) {
  if (loading) return <HomeSkeleton />;
  if (error || !data) return <section className="state-card error"><h2>Não foi possível carregar os dados agora.</h2><p>Tente novamente em alguns instantes.</p><button onClick={() => void retry()}>Tentar novamente</button></section>;
  const [primary, ...secondary] = data.top_opportunities;
  const empty = data.pulse.signal_count === 0;
  return <>
    <Pulse pulse={data.pulse} go={go} />
    <SearchBar go={go} />
    <section className="kpis" aria-label="Resumo"><Kpi value={data.summary.library_videos} label="Vídeos coletados" /><Kpi value={data.summary.recently_detected} label="Detectados hoje" /><Kpi value={data.summary.identified_products} label="Produtos identificados" /><Kpi value={data.summary.strong_signals} label="Sinais fortes" /></section>
    {empty ? <section className="state-card empty-state"><p className="eyebrow">OPORTUNIDADES</p><h2>Nenhum sinal forte agora</h2><p>A Babi ainda está reunindo evidências.</p><button onClick={() => go('Descobrir')}>Iniciar descoberta</button></section> : <><SectionTitle eyebrow="PRINCIPAL SINAL" title="O que merece atenção" action="Ver oportunidades" onAction={() => go('Oportunidades')} />{primary && <PrimaryOpportunity item={primary} go={go} />}{secondary.length > 0 && <section className="secondary-opportunities">{secondary.map(item => <SecondaryOpportunity key={item.id} item={item} go={go} />)}</section>}</>}
    <SectionTitle eyebrow="RECENTE" title="Descobertas recentes" action="Ver biblioteca" onAction={() => go('Biblioteca')} />
    {data.recent_discoveries.length ? <section className="discoveries">{data.recent_discoveries.slice(0, 3).map(item => <DiscoveryRow key={item.video_id} item={item} />)}</section> : <section className="quiet-empty">Novas descobertas com conteúdo suficiente aparecerão aqui.</section>}
    <SectionTitle eyebrow="ATIVIDADE" title="Última descoberta" /><Mission mission={data.last_mission} />
  </>;
}

function Pulse({pulse, go}: {pulse: HomeData['pulse']; go: (page: Page) => void}) { const text = pulse.signal_count ? `${formatNumber(pulse.signal_count)} ${pulse.signal_count === 1 ? 'sinal merece' : 'sinais merecem'} atenção agora` : 'Nenhum sinal forte no momento.'; const detail = pulse.signal_count ? [pulse.rising_count ? `${formatNumber(pulse.rising_count)} ganhando força` : null, pulse.new_signal_count ? `${formatNumber(pulse.new_signal_count)} novo sinal detectado` : null].filter(Boolean).join(' · ') : 'A Babi ainda está reunindo evidências.'; return <section className="pulse"><div><p className="eyebrow">PULSO DA BABI</p><h2>{text}</h2><p>{detail}</p></div>{pulse.signal_count > 0 && <button className="ghost-action" onClick={() => go('Oportunidades')}>Ver oportunidades <span>→</span></button>}</section>; }
function SearchBar({go}: {go: (page: Page) => void}) { return <section className="search-bar" aria-label="Busca"><label><span aria-hidden="true">⌕</span><input aria-label="Pesquisar produto, categoria ou tendência" placeholder="Pesquisar produto, categoria ou tendência" /></label><button onClick={() => go('Descobrir')}>Pesquisar</button><button className="secondary" onClick={() => go('Descobrir')}>Iniciar descoberta</button></section>; }
function Kpi({value, label}: {value: number; label: string}) { return <article><strong>{formatNumber(value)}</strong><span>{label}</span></article>; }
function SectionTitle({eyebrow, title, action, onAction}: {eyebrow: string; title: string; action?: string; onAction?: () => void}) { return <div className="section-title"><div><p className="eyebrow">{eyebrow}</p><h2>{title}</h2></div>{action && <button className="text-action" onClick={onAction}>{action} →</button>}</div>; }
function PrimaryOpportunity({item, go}: {item: Opportunity; go: (page: Page) => void}) { return <article className="primary-opportunity"><div className="primary-main"><div className="opportunity-top"><span className="rank">01</span><span className="human-status">{item.movement_label}</span></div><h3>{item.name}</h3>{item.original_name && item.original_name !== item.name && <p className="original-name">{item.original_name}</p>}<p className="lead-why">{item.why[0] || 'A Babi continua reunindo evidências sobre este produto.'}</p><button onClick={() => go('Oportunidades')}>Analisar oportunidade <span>→</span></button></div><div className="signal-grid"><Signal value={item.query_spread} label="tipos de busca" /><Signal value={item.creator_spread} label="creators" /><Signal value={item.observation_count} label="observações" /><div className="signal-note"><span className="status-dot" />{item.lifecycle_label}</div></div></article>; }
function Signal({value, label}: {value: number; label: string}) { return <div><strong>{formatNumber(value)}</strong><span>{label}</span></div>; }
function SecondaryOpportunity({item, go}: {item: Opportunity; go: (page: Page) => void}) { return <article className="secondary-opportunity"><div><span className="human-status">{item.lifecycle_label}</span><h3>{item.name}</h3><p>{item.why[0] || 'Evidência em formação.'}</p></div><div className="secondary-metrics"><span>{formatNumber(item.query_spread)} buscas</span><span>{formatNumber(item.observation_count)} observações</span><button className="text-action" onClick={() => go('Oportunidades')}>Analisar →</button></div></article>; }
function DiscoveryRow({item}: {item: Discovery}) { const title = item.product_name || item.caption || 'Descoberta recente'; const metric = Object.entries(item.metrics)[0]; return <article className="discovery-row"><div className="thumbnail">{item.thumbnail_url && <img src={item.thumbnail_url} alt="" />}</div><div><h3>{title}</h3>{item.creator && <p>@{item.creator.replace(/^@/, '')}</p>}{metric && <strong>{formatNumber(metric[1])} <span>{metricLabel(metric[0])}</span></strong>}<small>{formatDetectedAt(item.detected_at)}</small></div></article>; }
function metricLabel(metric: string) { return ({views: 'visualizações', likes: 'curtidas', comments_count: 'comentários', shares: 'compartilhamentos', favorites: 'favoritos'} as Record<string, string>)[metric] || metric; }
function Mission({mission}: {mission: HomeData['last_mission']}) { if (!mission) return <section className="quiet-empty">Nenhuma descoberta anterior foi encontrada.</section>; return <section className="mission"><div><b>{mission.name}</b><span>{formatNumber(mission.queries)} buscas · {formatNumber(mission.results)} resultados · {formatNumber(mission.new_videos)} novos</span></div><span className="mission-status">{mission.status === 'SUCCEEDED' ? 'Concluída' : mission.status}</span></section>; }
function HomeSkeleton() { return <><section className="pulse skeleton-block" /><section className="search-bar skeleton-block" /><section className="kpis">{[1,2,3,4].map(i => <article className="skeleton-block" key={i} />)}</section><section className="primary-opportunity skeleton-block" /></>; }
function Skeleton({page}: {page: Page}) { return <section className="state-card"><h2>{page}</h2><p>Esta área será conectada ao read model V2 em uma próxima etapa, sem alterar a coleta ou a segurança.</p></section>; }
createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>);
