"""Cliente da API de consulta de NFe (opção 3, sem certificado digital).

Provedor: Meu Danfe (api.meudanfe.com.br/v2) — R$0,03 por consulta de NF-e
por chave de acesso; documentação obtida em https://meudanfe.com.br/documentacao.php

Fluxo (assíncrono do lado do provedor, por isso isto é pensado pra rodar
numa task Celery, não numa request HTTP síncrona):
  1. PUT /fd/add/{chave} — dispara a busca. Responde com status
     WAITING/SEARCHING/OK/NOT_FOUND/ERROR.
  2. Se ainda não resolveu (WAITING/SEARCHING), espera >=1s e repete o PUT
     (mesma URL faz tanto disparar quanto consultar status) até resolver
     ou esgotar as tentativas.
  3. Se status=OK, GET /fd/get/xml/{chave} — baixa o XML oficial (nfeProc).
  4. Parse do XML (lxml) pra extrair emitente/valor/data.
"""

import time
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

import httpx
from lxml import etree

from app.config import settings

_NS = {"nfe": "http://www.portalfiscal.inf.br/nfe"}

_STATUS_EM_ANDAMENTO = {"WAITING", "SEARCHING"}
_STATUS_RESOLVIDOS = {"OK", "NOT_FOUND", "ERROR"}


class NfeConsultaError(Exception):
    """Erro ao consultar a API externa (rede, auth, etc.) — distinto de
    'nota não encontrada', que é um resultado válido, não uma exceção."""


@dataclass
class ResultadoBusca:
    status: str  # OK | NOT_FOUND | ERROR | WAITING | SEARCHING
    status_message: str


@dataclass
class DadosNotaFiscalExtraidos:
    fornecedor_cnpj: str
    fornecedor_razao_social: str
    valor_total: Decimal
    data_emissao: date
    xml_bruto: str


class NfeConsultaClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 15.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.meudanfe_api_key
        self.base_url = base_url or settings.meudanfe_base_url
        self.timeout = timeout
        # injetável pra testes (httpx.Client(transport=httpx.MockTransport(...)))
        self._http = http_client or httpx.Client(timeout=timeout)

    @property
    def configurado(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise NfeConsultaError("MEUDANFE_API_KEY não configurada — consulta de NFe desativada")
        return {"Api-Key": self.api_key}

    def solicitar_busca(self, chave_acesso: str) -> ResultadoBusca:
        try:
            resp = self._http.put(f"{self.base_url}/fd/add/{chave_acesso}", headers=self._headers(), content=b"")
        except httpx.HTTPError as exc:
            raise NfeConsultaError(f"falha de rede ao consultar NFe: {exc}") from exc

        if resp.status_code == 401:
            raise NfeConsultaError("Api-Key inválida ou não autorizada")
        if resp.status_code == 402:
            raise NfeConsultaError("saldo insuficiente na conta do provedor de consulta de NFe")
        if resp.status_code == 400:
            return ResultadoBusca(status="ERROR", status_message="chave de acesso inválida")
        resp.raise_for_status()

        corpo = resp.json()
        return ResultadoBusca(status=corpo["status"], status_message=corpo.get("statusMessage", ""))

    def aguardar_resolucao(
        self, chave_acesso: str, tentativas: int = 5, intervalo_segundos: float = 1.5
    ) -> ResultadoBusca:
        resultado = self.solicitar_busca(chave_acesso)
        restantes = tentativas - 1
        while resultado.status in _STATUS_EM_ANDAMENTO and restantes > 0:
            time.sleep(intervalo_segundos)
            resultado = self.solicitar_busca(chave_acesso)
            restantes -= 1
        return resultado

    def baixar_xml(self, chave_acesso: str) -> str:
        try:
            resp = self._http.get(f"{self.base_url}/fd/get/xml/{chave_acesso}", headers=self._headers())
        except httpx.HTTPError as exc:
            raise NfeConsultaError(f"falha de rede ao baixar XML da NFe: {exc}") from exc

        if resp.status_code == 404:
            raise NfeConsultaError("NFe não encontrada na Área do Cliente do provedor (adicione antes de baixar)")
        resp.raise_for_status()
        return resp.json()["data"]

    def consultar_e_extrair(self, chave_acesso: str) -> DadosNotaFiscalExtraidos | None:
        """Orquestra o fluxo completo. Retorna None se a nota não for
        encontrada (NOT_FOUND) — não é um erro, é um resultado válido.
        """
        resultado = self.aguardar_resolucao(chave_acesso)
        if resultado.status == "NOT_FOUND":
            return None
        if resultado.status != "OK":
            raise NfeConsultaError(f"consulta não resolveu: {resultado.status} — {resultado.status_message}")

        xml_texto = self.baixar_xml(chave_acesso)
        return parse_nfe_xml(xml_texto)


def parse_nfe_xml(xml_texto: str) -> DadosNotaFiscalExtraidos:
    try:
        raiz = etree.fromstring(xml_texto.encode("utf-8"))
    except etree.XMLSyntaxError as exc:
        raise NfeConsultaError(f"XML da NFe malformado: {exc}") from exc

    def _texto(xpath: str) -> str | None:
        elementos = raiz.xpath(xpath, namespaces=_NS)
        return elementos[0].text if elementos else None

    cnpj = _texto(".//nfe:emit/nfe:CNPJ")
    razao_social = _texto(".//nfe:emit/nfe:xNome")
    valor_total_texto = _texto(".//nfe:total/nfe:ICMSTot/nfe:vNF")
    data_emissao_texto = _texto(".//nfe:ide/nfe:dhEmi") or _texto(".//nfe:ide/nfe:dEmi")

    if not (cnpj and razao_social and valor_total_texto and data_emissao_texto):
        raise NfeConsultaError("XML da NFe não trouxe todos os campos esperados (emitente/valor/data)")

    try:
        if "T" in data_emissao_texto:
            data_emissao = datetime.fromisoformat(data_emissao_texto).date()
        else:
            data_emissao = datetime.strptime(data_emissao_texto, "%Y-%m-%d").date()
        valor_total = Decimal(valor_total_texto)
    except (ValueError, ArithmeticError) as exc:
        raise NfeConsultaError(f"XML da NFe trouxe valor/data em formato inesperado: {exc}") from exc

    return DadosNotaFiscalExtraidos(
        fornecedor_cnpj=cnpj,
        fornecedor_razao_social=razao_social,
        valor_total=valor_total,
        data_emissao=data_emissao,
        xml_bruto=xml_texto,
    )
