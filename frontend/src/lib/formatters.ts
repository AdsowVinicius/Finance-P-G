export function formatarMoeda(valor: string | null | undefined): string {
  if (valor === null || valor === undefined) return '—'
  return Number(valor).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

export function formatarMoedaCompacta(valor: number): string {
  return valor.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', notation: 'compact' })
}

export function formatarData(data: string): string {
  const [ano, mes, dia] = data.split('-')
  return `${dia}/${mes}/${ano}`
}
