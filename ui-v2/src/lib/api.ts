import type {DiscoveryData, HomeData, LibraryData, LibraryDetail, MarketRadarData, MarketTopData, MarketTrendData, OpportunitiesData, SystemData} from '../types';
export async function getHome(): Promise<HomeData> {
  const response = await fetch('/api/v2/home', {headers: {Accept: 'application/json'}});
  if (!response.ok) throw new Error(`Não foi possível carregar a Home (${response.status}).`);
  return response.json() as Promise<HomeData>;
}

export async function getDiscovery(): Promise<DiscoveryData> {
  const response = await fetch('/api/v2/discovery', {headers: {Accept: 'application/json'}});
  if (!response.ok) throw new Error('Não foi possível carregar a descoberta.');
  return response.json() as Promise<DiscoveryData>;
}

async function discoveryAction(path: string, body: Record<string, string>) {
  const response = await fetch(`/api/v2/discovery/${path}`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(detail?.detail || 'Não foi possível iniciar a descoberta.');
  }
  return response.json();
}
export const startSearch = (query: string) => discoveryAction('search', {query});
export const startMission = (preset_id: string) => discoveryAction('mission', {preset_id});
export async function getOpportunities(): Promise<OpportunitiesData> {
  const response = await fetch('/api/v2/opportunities', {headers: {Accept: 'application/json'}});
  if (!response.ok) throw new Error('Não foi possível carregar as oportunidades.');
  return response.json() as Promise<OpportunitiesData>;
}
export async function getLibrary(params: Record<string, string | number | boolean | undefined>): Promise<LibraryData> {
  const query = new URLSearchParams(); Object.entries(params).forEach(([key, value]) => { if (value !== undefined && value !== '') query.set(key, String(value)); });
  const response = await fetch(`/api/v2/library?${query}`, {headers: {Accept: 'application/json'}});
  if (!response.ok) throw new Error('Não foi possível carregar a biblioteca.'); return response.json() as Promise<LibraryData>;
}
export async function getLibraryDetail(videoId: string): Promise<LibraryDetail> {
  const response = await fetch(`/api/v2/library/${encodeURIComponent(videoId)}`, {headers: {Accept: 'application/json'}});
  if (!response.ok) throw new Error('Não foi possível carregar o detalhe.'); return response.json() as Promise<LibraryDetail>;
}
export async function getSystem(): Promise<SystemData> {
  const response = await fetch('/api/v2/system', {headers: {Accept: 'application/json'}});
  if (!response.ok) throw new Error('Não foi possível carregar o sistema.'); return response.json() as Promise<SystemData>;
}
export async function getMarketRadar(): Promise<MarketRadarData> {
  const response = await fetch('/api/v2/market-radar/overview', {headers: {Accept: 'application/json'}});
  if (!response.ok) throw new Error('NÃ£o foi possÃ­vel carregar o Market Radar.');
  return response.json() as Promise<MarketRadarData>;
}
export async function getMarketTop(category: string | null, period: string): Promise<MarketTopData> {
  const query = new URLSearchParams({period}); if (category) query.set('category', category);
  const response = await fetch(`/api/v2/market-radar/mercado-livre/top?${query}`, {headers: {Accept: 'application/json'}});
  if (!response.ok) throw new Error('NÃ£o foi possÃ­vel carregar os produtos do Mercado Livre.');
  return response.json() as Promise<MarketTopData>;
}
export async function getMarketTrends(category: string | null): Promise<MarketTrendData> {
  const query = category ? `?category=${encodeURIComponent(category)}` : '';
  const response = await fetch(`/api/v2/market-radar/mercado-livre/trends${query}`, {headers: {Accept: 'application/json'}});
  if (!response.ok) throw new Error('NÃ£o foi possÃ­vel carregar as tendÃªncias do Mercado Livre.');
  return response.json() as Promise<MarketTrendData>;
}
