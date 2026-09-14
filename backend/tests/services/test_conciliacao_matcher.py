import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.models.conta_financeira import ContaFinanceira
from app.models.enums import StatusConta, TipoLancamentoExtrato, TipoOperacaoNota
from app.services.conciliacao_matcher import ConciliacaoMatcher, LancamentoParaConciliar


def _conta(
    valor: str,
    data_vencimento: date,
    tipo_operacao: TipoOperacaoNota = TipoOperacaoNota.entrada,
    status: StatusConta = StatusConta.pendente,
) -> ContaFinanceira:
    return ContaFinanceira(
        id=uuid.uuid4(),
        tipo_operacao=tipo_operacao,
        parceiro_id=uuid.uuid4(),
        descricao="conta teste",
        valor=Decimal(valor),
        data_vencimento_original=data_vencimento,
        data_vencimento=data_vencimento,
        status=status,
    )


def _lancamento(
    valor: str, data_lanc: date, tipo: TipoLancamentoExtrato = TipoLancamentoExtrato.debito
) -> LancamentoParaConciliar:
    return LancamentoParaConciliar(data=data_lanc, valor=Decimal(valor), tipo=tipo)


class TestMatchExato:
    def setup_method(self) -> None:
        self.matcher = ConciliacaoMatcher(tolerancia_dias=5)

    def test_valor_e_data_iguais_da_match_exato(self) -> None:
        hoje = date(2026, 9, 14)
        conta = _conta("500.00", hoje)
        resultado = self.matcher.conciliar(_lancamento("500.00", hoje), [conta])

        assert resultado.tipo_match.value == "automatico_exato"
        assert resultado.contas == [conta]

    def test_credito_no_extrato_so_casa_com_conta_a_receber(self) -> None:
        hoje = date(2026, 9, 14)
        conta_a_pagar = _conta("500.00", hoje, tipo_operacao=TipoOperacaoNota.entrada)
        conta_a_receber = _conta("500.00", hoje, tipo_operacao=TipoOperacaoNota.saida)

        resultado = self.matcher.conciliar(
            _lancamento("500.00", hoje, tipo=TipoLancamentoExtrato.credito), [conta_a_pagar, conta_a_receber]
        )

        assert resultado.contas == [conta_a_receber]

    def test_debito_no_extrato_so_casa_com_conta_a_pagar(self) -> None:
        hoje = date(2026, 9, 14)
        conta_a_pagar = _conta("500.00", hoje, tipo_operacao=TipoOperacaoNota.entrada)
        conta_a_receber = _conta("500.00", hoje, tipo_operacao=TipoOperacaoNota.saida)

        resultado = self.matcher.conciliar(
            _lancamento("500.00", hoje, tipo=TipoLancamentoExtrato.debito), [conta_a_pagar, conta_a_receber]
        )

        assert resultado.contas == [conta_a_pagar]

    def test_conta_ja_paga_nao_entra_como_candidata(self) -> None:
        hoje = date(2026, 9, 14)
        conta_paga = _conta("500.00", hoje, status=StatusConta.pago)

        resultado = self.matcher.conciliar(_lancamento("500.00", hoje), [conta_paga])

        assert resultado.encontrou_match is False

    def test_duas_contas_identicas_no_mesmo_dia_e_ambiguo_nao_casa_sozinho(self) -> None:
        hoje = date(2026, 9, 14)
        conta1 = _conta("500.00", hoje)
        conta2 = _conta("500.00", hoje)

        resultado = self.matcher.conciliar(_lancamento("500.00", hoje), [conta1, conta2])

        assert resultado.encontrou_match is False


class TestMatchTolerancia:
    def setup_method(self) -> None:
        self.matcher = ConciliacaoMatcher(tolerancia_dias=5)

    def test_valor_igual_data_proxima_dentro_da_tolerancia(self) -> None:
        vencimento = date(2026, 9, 10)
        pagamento = date(2026, 9, 14)  # 4 dias depois
        conta = _conta("500.00", vencimento)

        resultado = self.matcher.conciliar(_lancamento("500.00", pagamento), [conta])

        assert resultado.tipo_match.value == "automatico_tolerancia"
        assert resultado.contas == [conta]

    def test_no_limite_exato_da_tolerancia_ainda_casa(self) -> None:
        vencimento = date(2026, 9, 10)
        pagamento = vencimento + timedelta(days=5)
        conta = _conta("500.00", vencimento)

        resultado = self.matcher.conciliar(_lancamento("500.00", pagamento), [conta])

        assert resultado.encontrou_match is True

    def test_um_dia_alem_da_tolerancia_nao_casa(self) -> None:
        vencimento = date(2026, 9, 10)
        pagamento = vencimento + timedelta(days=6)
        conta = _conta("500.00", vencimento)

        resultado = self.matcher.conciliar(_lancamento("500.00", pagamento), [conta])

        assert resultado.encontrou_match is False

    def test_pagamento_antes_do_vencimento_tambem_conta_na_tolerancia(self) -> None:
        vencimento = date(2026, 9, 14)
        pagamento = date(2026, 9, 10)  # nota emitida/paga antes de vencer
        conta = _conta("500.00", vencimento)

        resultado = self.matcher.conciliar(_lancamento("500.00", pagamento), [conta])

        assert resultado.encontrou_match is True

    def test_nunca_ha_tolerancia_de_valor(self) -> None:
        hoje = date(2026, 9, 14)
        conta = _conta("500.01", hoje)

        resultado = self.matcher.conciliar(_lancamento("500.00", hoje), [conta])

        assert resultado.encontrou_match is False


class TestMatchParcial:
    def setup_method(self) -> None:
        self.matcher = ConciliacaoMatcher(tolerancia_dias=5)

    def test_um_pagamento_quita_duas_parcelas_com_soma_exata(self) -> None:
        hoje = date(2026, 9, 14)
        conta1 = _conta("300.00", hoje)
        conta2 = _conta("200.00", hoje)

        resultado = self.matcher.conciliar(_lancamento("500.00", hoje), [conta1, conta2])

        assert resultado.tipo_match.value == "parcial"
        assert set(resultado.contas) == {conta1, conta2}

    def test_um_pagamento_quita_tres_parcelas(self) -> None:
        hoje = date(2026, 9, 14)
        contas = [_conta("100.00", hoje), _conta("150.00", hoje), _conta("250.00", hoje)]

        resultado = self.matcher.conciliar(_lancamento("500.00", hoje), contas)

        assert resultado.tipo_match.value == "parcial"
        assert len(resultado.contas) == 3

    def test_nao_forca_combinacao_quando_soma_nao_bate(self) -> None:
        hoje = date(2026, 9, 14)
        contas = [_conta("100.00", hoje), _conta("150.00", hoje)]

        resultado = self.matcher.conciliar(_lancamento("999.00", hoje), contas)

        assert resultado.encontrou_match is False

    def test_prefere_match_exato_a_combinacao_parcial_quando_os_dois_existem(self) -> None:
        hoje = date(2026, 9, 14)
        conta_exata = _conta("500.00", hoje)
        conta_a = _conta("300.00", hoje)
        conta_b = _conta("200.00", hoje)

        resultado = self.matcher.conciliar(_lancamento("500.00", hoje), [conta_exata, conta_a, conta_b])

        assert resultado.tipo_match.value == "automatico_exato"
        assert resultado.contas == [conta_exata]
