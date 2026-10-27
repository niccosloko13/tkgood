export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '';
  return new Intl.NumberFormat('pt-BR', {maximumFractionDigits: 0}).format(value);
}

export function formatDetectedAt(value: string | null | undefined): string {
  if (!value) return 'Data de detecção indisponível';
  const stamp = new Date(value);
  if (Number.isNaN(stamp.getTime())) return 'Data de detecção indisponível';
  const delta = Date.now() - stamp.getTime();
  if (delta >= 0 && delta < 60_000) return 'Detectado pela Babi agora';
  if (delta >= 0 && delta < 3_600_000) return `Detectado pela Babi há ${Math.floor(delta / 60_000)} min`;
  if (delta >= 0 && delta < 86_400_000) return `Detectado pela Babi há ${Math.floor(delta / 3_600_000)} h`;
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);
  if (stamp.toDateString() === yesterday.toDateString()) {
    return `Detectado pela Babi ontem, ${stamp.toLocaleTimeString('pt-BR', {hour: '2-digit', minute: '2-digit'})}`;
  }
  return `Detectado pela Babi em ${stamp.toLocaleDateString('pt-BR')}`;
}
