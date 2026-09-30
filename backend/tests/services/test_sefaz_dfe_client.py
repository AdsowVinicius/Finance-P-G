import base64
import gzip
from decimal import Decimal

import httpx
import pytest

from app.services.sefaz_dfe_client import SefazDfeClient, SefazError

CHAVE = "35260912345678000199550010000001231000001234"

RES_NFE = f"""<resNFe xmlns="http://www.portalfiscal.inf.br/nfe" versao="1.01">
<chNFe>{CHAVE}</chNFe><CNPJ>98765432000110</CNPJ><xNome>FORNECEDOR TESTE LTDA</xNome>
<dhEmi>2026-09-10T10:30:00-03:00</dhEmi><vNF>1500.50</vNF></resNFe>"""

PROC_NFE = f"""<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
<NFe><infNFe Id="NFe{CHAVE}"/></NFe></nfeProc>"""


def _zip(xml: str) -> str:
    return base64.b64encode(gzip.compress(xml.encode())).decode()


def _soap(cstat: str, motivo: str, ult: str, max_: str, docs: list[tuple[str, str, str]] = ()) -> bytes:
    lote = "".join(f'<docZip NSU="{n}" schema="{s}">{_zip(x)}</docZip>' for n, s, x in docs)
    return f"""<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"><soap:Body>
<nfeDistDFeInteresseResponse xmlns="http://www.portalfiscal.inf.br/nfe/wsdl/NFeDistribuicaoDFe">
<nfeDistDFeInteresseResult><retDistDFeInt xmlns="http://www.portalfiscal.inf.br/nfe" versao="1.01">
<tpAmb>1</tpAmb><cStat>{cstat}</cStat><xMotivo>{motivo}</xMotivo><ultNSU>{ult}</ultNSU><maxNSU>{max_}</maxNSU>
<loteDistDFeInt>{lote}</loteDistDFeInt></retDistDFeInt></nfeDistDFeInteresseResult>
</nfeDistDFeInteresseResponse></soap:Body></soap:Envelope>""".encode()


def _cliente(handler) -> SefazDfeClient:
    return SefazDfeClient("12345678000199", http_client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_envelope_por_nsu_tem_cnpj_uf_ambiente_e_nsu_com_15_digitos():
    capturado = {}

    def handler(req: httpx.Request) -> httpx.Response:
        capturado["corpo"] = req.content.decode()
        capturado["ct"] = req.headers["content-type"]
        return httpx.Response(200, content=_soap("137", "Nenhum documento", "000000000000042", "000000000000042"))

    _cliente(handler).consultar_por_nsu("42")

    assert "<CNPJ>12345678000199</CNPJ>" in capturado["corpo"]
    assert "<cUFAutor>35</cUFAutor>" in capturado["corpo"]
    assert "<tpAmb>1</tpAmb>" in capturado["corpo"]
    assert "<ultNSU>000000000000042</ultNSU>" in capturado["corpo"]
    assert "application/soap+xml" in capturado["ct"]


def test_resumo_de_nfe_e_extraido():
    corpo = _soap("138", "Documento localizado", "000000000000001", "000000000000001", [("000000000000001", "resNFe_v1.01", RES_NFE)])
    ret = _cliente(lambda r: httpx.Response(200, content=corpo)).consultar_por_nsu("0")

    assert ret.cstat == "138" and not ret.tem_mais
    (doc,) = ret.documentos
    assert doc.tipo == "resumo"
    assert doc.chave_acesso == CHAVE
    assert doc.cnpj_emitente == "98765432000110"
    assert doc.nome_emitente == "FORNECEDOR TESTE LTDA"
    assert doc.valor_total == Decimal("1500.50")
    assert doc.data_emissao.isoformat() == "2026-09-10"


def test_xml_completo_traz_a_chave_do_id_da_infnfe():
    corpo = _soap("138", "ok", "000000000000002", "000000000000002", [("000000000000002", "procNFe_v4.00", PROC_NFE)])
    (doc,) = _cliente(lambda r: httpx.Response(200, content=corpo)).consultar_por_nsu("1").documentos
    assert doc.tipo == "completo"
    assert doc.chave_acesso == CHAVE


def test_tem_mais_quando_ultnsu_menor_que_maxnsu():
    corpo = _soap("138", "ok", "000000000000050", "000000000000120")
    assert _cliente(lambda r: httpx.Response(200, content=corpo)).consultar_por_nsu("0").tem_mais


def test_consumo_indevido_e_sinalizado_como_bloqueado():
    corpo = _soap("656", "Consumo Indevido", "000000000000000", "000000000000000")
    assert _cliente(lambda r: httpx.Response(200, content=corpo)).consultar_por_nsu("0").bloqueado


def test_http_diferente_de_200_vira_sefaz_error():
    with pytest.raises(SefazError, match="500"):
        _cliente(lambda r: httpx.Response(500)).consultar_por_nsu("0")


def test_falha_de_rede_vira_sefaz_error():
    def handler(req):
        raise httpx.ConnectError("sem rede")

    with pytest.raises(SefazError, match="rede"):
        _cliente(handler).consultar_por_nsu("0")


def test_resposta_sem_retdistdfeint_vira_sefaz_error():
    with pytest.raises(SefazError):
        _cliente(lambda r: httpx.Response(200, content=b"<soap:Envelope xmlns:soap='http://www.w3.org/2003/05/soap-envelope'/>")).consultar_por_nsu("0")


def test_consulta_por_chave_valida_44_digitos():
    with pytest.raises(ValueError):
        _cliente(lambda r: httpx.Response(200)).consultar_por_chave("123")


def test_consulta_por_chave_monta_conschnfe():
    capturado = {}

    def handler(req):
        capturado["corpo"] = req.content.decode()
        return httpx.Response(200, content=_soap("138", "ok", "0", "0"))

    _cliente(handler).consultar_por_chave(CHAVE)
    assert f"<consChNFe><chNFe>{CHAVE}</chNFe></consChNFe>" in capturado["corpo"]


def test_entidade_externa_nao_e_resolvida_xxe():
    malicioso = b"""<?xml version="1.0"?><!DOCTYPE r [<!ENTITY x SYSTEM "file:///etc/passwd">]>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"><soap:Body>
<retDistDFeInt xmlns="http://www.portalfiscal.inf.br/nfe"><cStat>&x;</cStat><xMotivo>m</xMotivo></retDistDFeInt>
</soap:Body></soap:Envelope>"""
    from app.services.sefaz_dfe_client import parse_retorno

    ret = parse_retorno(malicioso)
    assert "root:" not in ret.cstat
