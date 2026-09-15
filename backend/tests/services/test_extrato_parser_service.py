from datetime import date
from decimal import Decimal

import pytest

from app.models.enums import FormatoExtrato, TipoLancamentoExtrato
from app.services.extrato_parser_service import CsvParserProvider, ExtratoParserService, OfxParserProvider

_OFX_EXEMPLO = b"""OFXHEADER:100
DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILEUID:NONE
NEWFILEUID:NONE

<OFX>
<SIGNONMSGSRSV1>
<SONRS>
<STATUS>
<CODE>0
<SEVERITY>INFO
</STATUS>
<DTSERVER>20260914120000
<LANGUAGE>POR
</SONRS>
</SIGNONMSGSRSV1>
<BANKMSGSRSV1>
<STMTTRNRS>
<TRNUID>1
<STATUS>
<CODE>0
<SEVERITY>INFO
</STATUS>
<STMTRS>
<CURDEF>BRL
<BANKACCTFROM>
<BANKID>341
<ACCTID>12345-6
<ACCTTYPE>CHECKING
</BANKACCTFROM>
<BANKTRANLIST>
<DTSTART>20260901
<DTEND>20260914
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20260910
<TRNAMT>1500.00
<FITID>ABC123
<MEMO>PIX RECEBIDO FORNECEDOR TESTE
</STMTTRN>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20260912
<TRNAMT>-300.00
<FITID>ABC124
<MEMO>PAGTO BOLETO
</STMTTRN>
</BANKTRANLIST>
<LEDGERBAL>
<BALAMT>5000.00
<DTASOF>20260914
</LEDGERBAL>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>
"""


_OFX_COM_TRANSACAO_SEM_NOME = b"""OFXHEADER:100
DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILEUID:NONE
NEWFILEUID:NONE

<OFX>
<SIGNONMSGSRSV1>
<SONRS>
<STATUS>
<CODE>0
<SEVERITY>INFO
</STATUS>
<DTSERVER>20260914120000
<LANGUAGE>POR
</SONRS>
</SIGNONMSGSRSV1>
<BANKMSGSRSV1>
<STMTTRNRS>
<TRNUID>1
<STATUS>
<CODE>0
<SEVERITY>INFO
</STATUS>
<STMTRS>
<CURDEF>BRL
<BANKACCTFROM>
<BANKID>341
<ACCTID>12345-6
<ACCTTYPE>CHECKING
</BANKACCTFROM>
<BANKTRANLIST>
<DTSTART>20260901
<DTEND>20260914
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20260910
<TRNAMT>1500.00
<FITID>ABC123
<MEMO>PIX RECEBIDO FORNECEDOR TESTE
</STMTTRN>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20260913
<TRNAMT>-15.00
<FITID>ABC125
<NAME></NAME>
<MEMO>TARIFA BANCARIA
</STMTTRN>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20260912
<TRNAMT>-300.00
<FITID>ABC124
<MEMO>PAGTO BOLETO
</STMTTRN>
</BANKTRANLIST>
<LEDGERBAL>
<BALAMT>5000.00
<DTASOF>20260914
</LEDGERBAL>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>
"""


class TestOfxParserProvider:
    def setup_method(self) -> None:
        self.provider = OfxParserProvider()

    def test_transacao_com_nome_vazio_e_ignorada_sem_derrubar_o_extrato_inteiro(self) -> None:
        """Alguns bancos exportam OFX com <NAME> vazio pra certas transações
        (tarifa, estorno etc.) — isso não pode derrubar o extrato inteiro
        (ofxparse com fail_fast=True, o padrão da lib, faz exatamente isso).
        """
        lancamentos = self.provider.parse(_OFX_COM_TRANSACAO_SEM_NOME)
        assert len(lancamentos) == 2
        assert {l.fitid for l in lancamentos} == {"ABC123", "ABC124"}

    def test_extrai_lancamentos_com_valor_sempre_positivo(self) -> None:
        lancamentos = self.provider.parse(_OFX_EXEMPLO)

        assert len(lancamentos) == 2
        credito, debito = lancamentos
        assert credito.tipo == TipoLancamentoExtrato.credito
        assert credito.valor == Decimal("1500.00")
        assert credito.data == date(2026, 9, 10)
        assert credito.fitid == "ABC123"

        assert debito.tipo == TipoLancamentoExtrato.debito
        assert debito.valor == Decimal("300.00")  # positivo mesmo vindo negativo do OFX
        assert debito.fitid == "ABC124"

    def test_descricao_vem_do_memo(self) -> None:
        lancamentos = self.provider.parse(_OFX_EXEMPLO)
        assert lancamentos[0].descricao == "PIX RECEBIDO FORNECEDOR TESTE"


class TestCsvParserProvider:
    def setup_method(self) -> None:
        self.provider = CsvParserProvider()

    def test_extrai_lancamentos_do_csv(self) -> None:
        conteudo = (
            "data,descricao,valor,tipo\n"
            "2026-09-10,PIX recebido,1500.00,credito\n"
            "2026-09-12,Pagamento boleto,300.00,debito\n"
        ).encode("utf-8")

        lancamentos = self.provider.parse(conteudo)

        assert len(lancamentos) == 2
        assert lancamentos[0].data == date(2026, 9, 10)
        assert lancamentos[0].valor == Decimal("1500.00")
        assert lancamentos[0].tipo == TipoLancamentoExtrato.credito
        assert lancamentos[1].tipo == TipoLancamentoExtrato.debito

    def test_valor_negativo_no_csv_vira_positivo(self) -> None:
        conteudo = "data,descricao,valor,tipo\n2026-09-10,teste,-50.00,debito\n".encode("utf-8")
        lancamentos = self.provider.parse(conteudo)
        assert lancamentos[0].valor == Decimal("50.00")

    def test_mesma_linha_gera_o_mesmo_fitid_determinismo_para_idempotencia(self) -> None:
        conteudo = "data,descricao,valor,tipo\n2026-09-10,teste,50.00,debito\n".encode("utf-8")
        primeira = self.provider.parse(conteudo)
        segunda = self.provider.parse(conteudo)
        assert primeira[0].fitid == segunda[0].fitid

    def test_colunas_faltando_leva_a_erro_claro(self) -> None:
        conteudo = "data,valor\n2026-09-10,50.00\n".encode("utf-8")
        with pytest.raises(ValueError, match="colunas"):
            self.provider.parse(conteudo)

    def test_tipo_invalido_leva_a_erro_claro(self) -> None:
        conteudo = "data,descricao,valor,tipo\n2026-09-10,teste,50.00,transferencia\n".encode("utf-8")
        with pytest.raises(ValueError, match="tipo inválido"):
            self.provider.parse(conteudo)


class TestExtratoParserServiceRegistry:
    def test_despacha_para_o_provider_certo_por_formato(self) -> None:
        service = ExtratoParserService()
        lancamentos = service.parse(FormatoExtrato.ofx, _OFX_EXEMPLO)
        assert len(lancamentos) == 2

    def test_formato_nao_suportado_leva_a_erro(self) -> None:
        service = ExtratoParserService()
        service._providers = {}  # simula um registry sem providers
        with pytest.raises(ValueError, match="não suportado"):
            service.parse(FormatoExtrato.ofx, b"")
