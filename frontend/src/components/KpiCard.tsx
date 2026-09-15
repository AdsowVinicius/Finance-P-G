import type { ReactNode } from 'react'

interface KpiCardProps {
  titulo: string
  valor: string
  icone: React.ElementType
  corIcone: string
  corFundo: string
  onClick?: () => void
  extra?: ReactNode
}

export function KpiCard({ titulo, valor, icone: Icone, corIcone, corFundo, onClick, extra }: KpiCardProps) {
  const Tag = onClick ? 'button' : 'div'
  return (
    <Tag
      onClick={onClick}
      className={`rounded-xl bg-white p-5 text-left shadow-sm ring-1 ring-slate-200/70 ${
        onClick ? 'transition hover:-translate-y-0.5 hover:shadow-md hover:ring-brand-300' : ''
      }`}
    >
      <div className="flex items-start gap-3">
        <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${corFundo}`}>
          <Icone size={20} className={corIcone} />
        </div>
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{titulo}</p>
          <p className="text-lg font-semibold leading-tight text-slate-800">{valor}</p>
          {extra}
        </div>
      </div>
    </Tag>
  )
}
