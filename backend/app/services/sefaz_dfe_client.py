"""Cliente do web service NFeDistribuicaoDFe (SEFAZ, Ambiente Nacional).

Autenticação é mTLS com o certificado A1 — não há assinatura de XML nesse
serviço (assinar só é necessário em Manifestação do Destinatário, que não
está implementada). Duas consultas:

  - por NSU (`distNSU/ultNSU`): traz, em lotes, tudo que foi emitido contra
    o CNPJ desde o último NSU processado;
  - por chave (`consChNFe`): tenta obter uma NFe específica.

Sem Manifestação do Destinatário a SEFAZ entrega, para NFes de terceiros,
apenas o RESUMO (resNFe: chave, emitente, valor, data). O XML completo
(procNFe) só vem depois da manifestação, ou quando o CNPJ é o emitente.
Por isso o retorno distingue `resumo` de `completo`.

Regras de uso da SEFAZ que o chamador precisa respeitar:
  - cStat 137 (nenhum documento): esperar ~1h antes de consultar de novo;
  - cStat 656 (consumo indevido): bloqueio de ~1h.
"""

import base64
import gzip
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import httpx
from lxml import etree

_URLS = {
    "producao": "https://www1.nfe.fazenda.gov.br/NFeDistribuicaoDFe/NFeDistribuicaoDFe.asmx",
    "homologacao": "https://hom1.nfe.fazenda.gov.br/NFeDistribuicaoDFe/NFeDistribuicaoDFe.asmx",
}
_TP_AMB = {"producao": "1", "homologacao": "2"}
# parser endurecido: XML vem de terceiro, sem entidades externas/DTD/rede (XXE)
_PARSER_SEGURO = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False)
_NS_NFE = "http://www.portalfiscal.inf.br/nfe"
_NS_WSDL = "http://www.portalfiscal.inf.br/nfe/wsdl/NFeDistribuicaoDFe"
_SOAP_ACTION = f"{_NS_WSDL}/nfeDistDFeInteresse"
_NS = {"nfe": _NS_NFE, "soap": "http://www.w3.org/2003/05/soap-envelope", "wsdl": _NS_WSDL}

CSTAT_DOCUMENTOS_LOCALIZADOS = "138"
CSTAT_NENHUM_DOCUMENTO = "137"
CSTAT_CONSUMO_INDEVIDO = "656"


class SefazError(Exception):
    """Falha de transporte/protocolo (rede, TLS, resposta ilegível)."""


@dataclass
class DocumentoDFe:
    nsu: str
    schema: str  # ex: resNFe_v1.01, procNFe_v4.00
    xml: str
    tipo: str  # "resumo" | "completo" | "evento" | "outro"
    chave_acesso: str | None = None
    cnpj_emitente: str | None = None
    nome_emitente: str | None = None
    valor_total: Decimal | None = None
    data_emissao: date | None = None


@dataclass
class RetornoDistribuicao:
    cstat: str
    motivo: str
    ult_nsu: str
    max_nsu: str
    documentos: list[DocumentoDFe] = field(default_factory=list)

    @property
    def tem_mais(self) -> bool:
        return self.cstat == CSTAT_DOCUMENTOS_LOCALIZADOS and self.ult_nsu < self.max_nsu

    @property
    def bloqueado(self) -> bool:
        return self.cstat == CSTAT_CONSUMO_INDEVIDO


def _envelope(cnpj: str, uf_autor: int, ambiente: str, consulta_xml: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soap12:Envelope xmlns:soap12="http://www.w3.org/2003/05/soap-envelope"><soap12:Body>'
        f'<nfeDistDFeInteresse xmlns="{_NS_WSDL}"><nfeDadosMsg>'
        f'<distDFeInt xmlns="{_NS_NFE}" versao="1.01">'
        f"<tpAmb>{_TP_AMB[ambiente]}</tpAmb><cUFAutor>{uf_autor}</cUFAutor><CNPJ>{cnpj}</CNPJ>"
        f"{consulta_xml}"
        "</distDFeInt></nfeDadosMsg></nfeDistDFeInteresse></soap12:Body></soap12:Envelope>"
    ).encode("utf-8")


def _texto(no: etree._Element, xpath: str) -> str | None:
    achados = no.xpath(xpath, namespaces=_NS)
    return achados[0].text if achados else None


def _parse_documento(nsu: str, schema: str, xml_bytes: bytes) -> DocumentoDFe:
    xml = xml_bytes.decode("utf-8")
    raiz = etree.fromstring(xml_bytes, parser=_PARSER_SEGURO)

    if schema.startswith("resNFe"):
        valor = _texto(raiz, "//nfe:vNF")
        data = _texto(raiz, "//nfe:dhEmi")
        try:
            valor_dec = Decimal(valor) if valor else None
        except InvalidOperation:
            valor_dec = None
        return DocumentoDFe(
            nsu=nsu,
            schema=schema,
            xml=xml,
            tipo="resumo",
            chave_acesso=_texto(raiz, "//nfe:chNFe"),
            cnpj_emitente=_texto(raiz, "//nfe:CNPJ") or _texto(raiz, "//nfe:CPF"),
            nome_emitente=_texto(raiz, "//nfe:xNome"),
            valor_total=valor_dec,
            data_emissao=datetime.fromisoformat(data).date() if data else None,
        )

    if schema.startswith("procNFe"):
        inf = raiz.xpath("//nfe:infNFe", namespaces=_NS)
        id_attr = inf[0].get("Id", "") if inf else ""
        return DocumentoDFe(
            nsu=nsu,
            schema=schema,
            xml=xml,
            tipo="completo",
            chave_acesso=id_attr[3:] if id_attr.startswith("NFe") else None,
        )

    tipo = "evento" if "Evento" in schema else "outro"
    return DocumentoDFe(nsu=nsu, schema=schema, xml=xml, tipo=tipo)


def parse_retorno(resposta_xml: bytes) -> RetornoDistribuicao:
    try:
        raiz = etree.fromstring(resposta_xml, parser=_PARSER_SEGURO)
    except etree.XMLSyntaxError as exc:
        raise SefazError(f"resposta da SEFAZ não é XML válido: {exc}") from exc

    ret = raiz.xpath("//nfe:retDistDFeInt", namespaces=_NS)
    if not ret:
        raise SefazError("resposta da SEFAZ sem retDistDFeInt (possível erro de SOAP/Fault)")
    ret = ret[0]

    retorno = RetornoDistribuicao(
        cstat=_texto(ret, "nfe:cStat") or "",
        motivo=_texto(ret, "nfe:xMotivo") or "",
        ult_nsu=_texto(ret, "nfe:ultNSU") or "0",
        max_nsu=_texto(ret, "nfe:maxNSU") or "0",
    )
    for doc in ret.xpath("nfe:loteDistDFeInt/nfe:docZip", namespaces=_NS):
        try:
            xml_bytes = gzip.decompress(base64.b64decode(doc.text or ""))
            retorno.documentos.append(_parse_documento(doc.get("NSU", ""), doc.get("schema", ""), xml_bytes))
        except (ValueError, OSError, etree.XMLSyntaxError) as exc:
            raise SefazError(f"docZip NSU {doc.get('NSU')} ilegível: {exc}") from exc
    return retorno


class SefazDfeClient:
    def __init__(
        self,
        cnpj: str,
        uf_autor: int = 35,
        ambiente: str = "producao",
        ssl_context=None,
        http_client: httpx.Client | None = None,
        timeout: float = 30.0,
    ) -> None:
        if ambiente not in _URLS:
            raise ValueError(f"ambiente inválido: {ambiente}")
        self.cnpj = cnpj
        self.uf_autor = uf_autor
        self.ambiente = ambiente
        # injetável pra testes (httpx.Client(transport=httpx.MockTransport(...)))
        self._http = http_client or httpx.Client(verify=ssl_context if ssl_context is not None else True, timeout=timeout)

    def _enviar(self, consulta_xml: str) -> RetornoDistribuicao:
        corpo = _envelope(self.cnpj, self.uf_autor, self.ambiente, consulta_xml)
        try:
            resp = self._http.post(
                _URLS[self.ambiente],
                content=corpo,
                headers={"Content-Type": f'application/soap+xml; charset=utf-8; action="{_SOAP_ACTION}"'},
            )
        except httpx.HTTPError as exc:
            raise SefazError(f"falha de rede/TLS ao falar com a SEFAZ: {exc}") from exc
        if resp.status_code != 200:
            raise SefazError(f"SEFAZ respondeu HTTP {resp.status_code}")
        return parse_retorno(resp.content)

    def consultar_por_nsu(self, ult_nsu: str) -> RetornoDistribuicao:
        nsu = str(int(ult_nsu)).zfill(15)
        return self._enviar(f"<distNSU><ultNSU>{nsu}</ultNSU></distNSU>")

    def consultar_por_chave(self, chave_acesso: str) -> RetornoDistribuicao:
        if not (chave_acesso.isdigit() and len(chave_acesso) == 44):
            raise ValueError("chave de acesso precisa ter 44 dígitos")
        return self._enviar(f"<consChNFe><chNFe>{chave_acesso}</chNFe></consChNFe>")
