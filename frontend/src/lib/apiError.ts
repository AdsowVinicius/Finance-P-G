/** Extrai a mensagem de erro (`detail`) de uma resposta de erro do Axios/FastAPI,
 * caindo pra `fallback` quando a resposta não tem o formato esperado (erro de
 * rede, timeout, resposta sem `detail` string).
 */
export function extractApiError(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  return typeof detail === 'string' ? detail : fallback
}
