from datetime import date
from decimal import Decimal

import httpx
import pytest

from app.services.nfe_consulta_client import (
    NfeConsultaClient,
    NfeConsultaError,
    parse_nfe_xml,
)

_XML_EXEMPLO = """<?xml version="1.0" encoding="UTF-8"?>
<nfeProc versao="4.00" xmlns="http://www.portalfiscal.inf.br/nfe">
  <NFe>
    <infNFe Id="NFe35260912345678000190550010000000011234567890" versao="4.00">
      <ide>
        <dhEmi>2026-09-10T09:00:00-03:00</dhEmi>
      </ide>
      <emit>
        <CNPJ>12345678000190</CNPJ>
        <xNome>Fornecedor Teste LTDA</xNome>
      </emit>
      <total>
        <ICMSTot>
          <vNF>1234.56</vNF>
        </ICMSTot>
      </total>
    </infNFe>
  </NFe>
  <protNFe>
    <infProt>
      <chNFe>35260912345678000190550010000000011234567890</chNFe>
      <cStat>100</cStat>
      <xMotivo>Autorizado o uso da NF-e</xMotivo>
    </infProt>
  </protNFe>
</nfeProc>
"""


def _client_mockado(handler) -> NfeConsultaClient:
    transporte = httpx.MockTransport(handler)
    return NfeConsultaClient(
        api_key="chave-de-teste",
        base_url="https://fake.meudanfe.test/v2",
        http_client=httpx.Client(transport=transporte),
    )


class TestParseNfeXml:
    def test_extrai_emitente_valor_e_data(self) -> None:
        dados = parse_nfe_xml(_XML_EXEMPLO)

        assert dados.fornecedor_cnpj == "12345678000190"
        assert dados.fornecedor_razao_social == "Fornecedor Teste LTDA"
        assert dados.valor_total == Decimal("1234.56")
        assert dados.data_emissao == date(2026, 9, 10)

    def test_xml_incompleto_levanta_erro_claro(self) -> None:
        xml_incompleto = """<?xml version="1.0"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">
  <NFe><infNFe><ide><dhEmi>2026-09-10T09:00:00-03:00</dhEmi></ide></infNFe></NFe>
</nfeProc>"""
        with pytest.raises(NfeConsultaError, match="não trouxe todos os campos"):
            parse_nfe_xml(xml_incompleto)


class TestNfeConsultaClientSemChaveConfigurada:
    def test_sem_api_key_levanta_erro_ao_chamar(self) -> None:
        # api_key="" (não None) pra isolar do fallback em settings.meudanfe_api_key,
        # que pode estar configurada de verdade no .env desta máquina.
        client = NfeConsultaClient(api_key="", http_client=httpx.Client())
        assert client.configurado is False
        with pytest.raises(NfeConsultaError, match="não configurada"):
            client.solicitar_busca("3526" * 11)


class TestNfeConsultaClientComMock:
    def test_status_ok_resolve_de_primeira(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"value": "x", "type": "NFE", "status": "OK", "statusMessage": "Ok"})

        resultado = _client_mockado(handler).aguardar_resolucao("chave", tentativas=3, intervalo_segundos=0)

        assert resultado.status == "OK"

    def test_status_401_levanta_erro(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401)

        with pytest.raises(NfeConsultaError, match="não autorizada"):
            _client_mockado(handler).solicitar_busca("chave")

    def test_status_402_levanta_erro_de_saldo(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(402)

        with pytest.raises(NfeConsultaError, match="saldo insuficiente"):
            _client_mockado(handler).solicitar_busca("chave")

    def test_waiting_depois_ok_apos_poll(self) -> None:
        respostas = iter(
            [
                {"value": "x", "type": "NFE", "status": "WAITING", "statusMessage": "Na fila"},
                {"value": "x", "type": "NFE", "status": "OK", "statusMessage": "Ok"},
            ]
        )

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=next(respostas))

        resultado = _client_mockado(handler).aguardar_resolucao("chave", tentativas=5, intervalo_segundos=0)

        assert resultado.status == "OK"

    def test_para_de_tentar_apos_esgotar_tentativas(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"value": "x", "type": "NFE", "status": "WAITING", "statusMessage": "Na fila"})

        resultado = _client_mockado(handler).aguardar_resolucao("chave", tentativas=3, intervalo_segundos=0)

        assert resultado.status == "WAITING"

    def test_not_found_nao_e_erro_retorna_none_no_fluxo_completo(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "PUT":
                return httpx.Response(
                    200, json={"value": "x", "type": "NFE", "status": "NOT_FOUND", "statusMessage": "Não encontrada"}
                )
            raise AssertionError("não deveria baixar XML quando NOT_FOUND")

        resultado = _client_mockado(handler).consultar_e_extrair("chave")

        assert resultado is None

    def test_fluxo_completo_ok_baixa_e_faz_parse_do_xml(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "PUT":
                return httpx.Response(200, json={"value": "x", "type": "NFE", "status": "OK", "statusMessage": "Ok"})
            return httpx.Response(200, json={"name": "x.xml", "type": "NFE", "format": "XML", "data": _XML_EXEMPLO})

        resultado = _client_mockado(handler).consultar_e_extrair("chave")

        assert resultado is not None
        assert resultado.fornecedor_razao_social == "Fornecedor Teste LTDA"
        assert resultado.valor_total == Decimal("1234.56")
