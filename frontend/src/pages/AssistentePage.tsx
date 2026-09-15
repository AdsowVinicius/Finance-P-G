import { Bot, Send, User } from 'lucide-react'
import { useRef, useState, type FormEvent } from 'react'
import { api } from '../lib/api'

interface Mensagem {
  autor: 'usuario' | 'assistente'
  texto: string
}

const SUGESTOES = ['Quanto gastei esse mês?', 'O que vence essa semana?', 'Quais contas estão atrasadas?', 'Qual o saldo desse mês?']

function TextoFormatado({ texto }: { texto: string }) {
  const partes = texto.split(/(\*\*[^*]+\*\*)/g)
  return (
    <>
      {partes.map((parte, i) =>
        parte.startsWith('**') && parte.endsWith('**') ? (
          <strong key={i}>{parte.slice(2, -2)}</strong>
        ) : (
          <span key={i}>{parte}</span>
        ),
      )}
    </>
  )
}

export function AssistentePage() {
  const [mensagens, setMensagens] = useState<Mensagem[]>([
    {
      autor: 'assistente',
      texto: 'Olá! Pode me perguntar sobre vencimentos, gastos, recebimentos ou notas fiscais. Ex: "quanto gastei esse mês?"',
    },
  ])
  const [pergunta, setPergunta] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const fimRef = useRef<HTMLDivElement>(null)

  async function enviar(texto: string) {
    const perguntaLimpa = texto.trim()
    if (!perguntaLimpa || enviando) return

    setErro(null)
    setMensagens((atual) => [...atual, { autor: 'usuario', texto: perguntaLimpa }])
    setPergunta('')
    setEnviando(true)

    try {
      const { data } = await api.post<{ resposta: string }>('/assistente/perguntar', { pergunta: perguntaLimpa })
      setMensagens((atual) => [...atual, { autor: 'assistente', texto: data.resposta }])
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      const mensagemErro =
        typeof detail === 'string' ? detail : 'Não consegui falar com o assistente agora. Tente de novo.'
      setErro(mensagemErro)
    } finally {
      setEnviando(false)
      setTimeout(() => fimRef.current?.scrollIntoView({ behavior: 'smooth' }), 50)
    }
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    enviar(pergunta)
  }

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col">
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-slate-800">Assistente Financeiro</h2>
        <p className="text-sm text-slate-500">Pergunte em linguagem natural sobre vencimentos, gastos e notas fiscais.</p>
      </div>

      <div className="flex flex-1 flex-col overflow-hidden rounded-xl bg-white shadow-sm ring-1 ring-slate-200/70">
        <div className="flex-1 space-y-4 overflow-y-auto p-6">
          {mensagens.map((msg, i) => (
            <div key={i} className={`flex gap-3 ${msg.autor === 'usuario' ? 'flex-row-reverse' : ''}`}>
              <div
                className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
                  msg.autor === 'usuario' ? 'bg-brand-700 text-white' : 'bg-brand-100 text-brand-700'
                }`}
              >
                {msg.autor === 'usuario' ? <User size={16} /> : <Bot size={16} />}
              </div>
              <div
                className={`max-w-[75%] whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-sm ${
                  msg.autor === 'usuario'
                    ? 'bg-brand-700 text-white'
                    : 'bg-slate-100 text-slate-800'
                }`}
              >
                <TextoFormatado texto={msg.texto} />
              </div>
            </div>
          ))}
          {enviando && (
            <div className="flex gap-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-100 text-brand-700">
                <Bot size={16} />
              </div>
              <div className="flex items-center gap-1 rounded-2xl bg-slate-100 px-4 py-3">
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.3s]" />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.15s]" />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400" />
              </div>
            </div>
          )}
          <div ref={fimRef} />
        </div>

        {mensagens.length === 1 && (
          <div className="flex flex-wrap gap-2 border-t border-slate-100 px-6 py-3">
            {SUGESTOES.map((s) => (
              <button
                key={s}
                onClick={() => enviar(s)}
                className="rounded-full bg-slate-100 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-200"
              >
                {s}
              </button>
            ))}
          </div>
        )}

        {erro && <div className="border-t border-red-100 bg-red-50 px-6 py-2 text-sm text-red-700">{erro}</div>}

        <form onSubmit={handleSubmit} className="flex items-center gap-2 border-t border-slate-100 p-4">
          <input
            value={pergunta}
            onChange={(e) => setPergunta(e.target.value)}
            placeholder="Pergunte algo sobre suas finanças..."
            className="flex-1 rounded-full border border-slate-300 px-4 py-2.5 text-sm focus:border-brand-500 focus:outline-none"
            disabled={enviando}
          />
          <button
            type="submit"
            disabled={enviando || !pergunta.trim()}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-700 text-white hover:bg-brand-800 disabled:opacity-40"
          >
            <Send size={16} />
          </button>
        </form>
      </div>
    </div>
  )
}
