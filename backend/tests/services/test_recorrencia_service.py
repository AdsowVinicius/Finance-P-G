import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.models.enums import Periodicidade, TipoOperacaoNota
from app.models.lancamento_recorrente import LancamentoRecorrente
from app.services.recorrencia_service import RecorrenciaService, gerar_datas_ocorrencias


class TestGerarDatasOcorrencias:
    def test_para_em_numero_ocorrencias(self) -> None:
        datas = gerar_datas_ocorrencias(
            data_inicio=date(2026, 1, 10),
            periodicidade=Periodicidade.mensal,
            numero_ocorrencias=3,
        )
        assert datas == [date(2026, 1, 10), date(2026, 2, 10), date(2026, 3, 10)]

    def test_para_em_data_fim(self) -> None:
        datas = gerar_datas_ocorrencias(
            data_inicio=date(2026, 1, 1),
            periodicidade=Periodicidade.semanal,
            data_fim=date(2026, 1, 22),
        )
        assert datas == [date(2026, 1, 1), date(2026, 1, 8), date(2026, 1, 15), date(2026, 1, 22)]

    def test_para_no_que_vier_primeiro_numero_ocorrencias_antes_de_data_fim(self) -> None:
        datas = gerar_datas_ocorrencias(
            data_inicio=date(2026, 1, 1),
            periodicidade=Periodicidade.mensal,
            numero_ocorrencias=2,
            data_fim=date(2026, 12, 31),
        )
        assert datas == [date(2026, 1, 1), date(2026, 2, 1)]

    def test_para_no_que_vier_primeiro_data_fim_antes_de_numero_ocorrencias(self) -> None:
        datas = gerar_datas_ocorrencias(
            data_inicio=date(2026, 1, 1),
            periodicidade=Periodicidade.mensal,
            numero_ocorrencias=12,
            data_fim=date(2026, 3, 15),
        )
        assert datas == [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)]

    def test_mensal_preserva_dia_atraves_de_fim_de_mes(self) -> None:
        datas = gerar_datas_ocorrencias(
            data_inicio=date(2026, 1, 31),
            periodicidade=Periodicidade.mensal,
            numero_ocorrencias=3,
        )
        # fevereiro/2026 não tem 31 — dateutil.relativedelta cai pro último dia do mês
        assert datas == [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31)]

    def test_quinzenal(self) -> None:
        datas = gerar_datas_ocorrencias(
            data_inicio=date(2026, 1, 1),
            periodicidade=Periodicidade.quinzenal,
            numero_ocorrencias=3,
        )
        assert datas == [date(2026, 1, 1), date(2026, 1, 16), date(2026, 1, 31)]

    def test_anual(self) -> None:
        datas = gerar_datas_ocorrencias(
            data_inicio=date(2026, 3, 10),
            periodicidade=Periodicidade.anual,
            numero_ocorrencias=2,
        )
        assert datas == [date(2026, 3, 10), date(2027, 3, 10)]

    def test_personalizada_dias(self) -> None:
        datas = gerar_datas_ocorrencias(
            data_inicio=date(2026, 1, 1),
            periodicidade=Periodicidade.personalizada_dias,
            numero_ocorrencias=3,
            intervalo_dias=10,
        )
        assert datas == [date(2026, 1, 1), date(2026, 1, 11), date(2026, 1, 21)]

    def test_personalizada_dias_sem_intervalo_falha(self) -> None:
        with pytest.raises(ValueError):
            gerar_datas_ocorrencias(
                data_inicio=date(2026, 1, 1),
                periodicidade=Periodicidade.personalizada_dias,
                numero_ocorrencias=3,
            )

    def test_sem_numero_ocorrencias_e_sem_data_fim_falha(self) -> None:
        with pytest.raises(ValueError):
            gerar_datas_ocorrencias(data_inicio=date(2026, 1, 1), periodicidade=Periodicidade.mensal)


class TestRecorrenciaServiceGerarParcelas:
    def setup_method(self) -> None:
        self.service = RecorrenciaService()

    def _lancamento(self, **overrides) -> LancamentoRecorrente:
        base = dict(
            id=uuid.uuid4(),
            tipo_operacao=TipoOperacaoNota.entrada,
            descricao="Aluguel do galpão",
            parceiro_id=uuid.uuid4(),
            centro_custo_id=uuid.uuid4(),
            valor_parcela=Decimal("1500.00"),
            numero_ocorrencias=3,
            data_fim=None,
            periodicidade=Periodicidade.mensal,
            intervalo_dias=None,
            data_inicio=date(2026, 9, 12),  # sábado
            conta_bancaria_id=uuid.uuid4(),
        )
        base.update(overrides)
        return LancamentoRecorrente(**base)

    def test_gera_o_numero_certo_de_parcelas_com_numeracao_e_valor(self) -> None:
        lancamento = self._lancamento()
        parcelas = self.service.gerar_parcelas(lancamento)

        assert len(parcelas) == 3
        for i, parcela in enumerate(parcelas, start=1):
            assert parcela.numero_parcela == i
            assert parcela.total_parcelas == 3
            assert parcela.valor == Decimal("1500.00")
            assert parcela.lancamento_recorrente_id == lancamento.id
            assert parcela.parceiro_id == lancamento.parceiro_id

    def test_ajusta_data_de_vencimento_por_dia_util_mas_preserva_original(self) -> None:
        lancamento = self._lancamento(data_inicio=date(2026, 9, 12))  # sábado
        parcelas = self.service.gerar_parcelas(lancamento)

        primeira = parcelas[0]
        assert primeira.data_vencimento_original == date(2026, 9, 12)
        assert primeira.data_vencimento == date(2026, 9, 14)  # empurrado pra segunda

    def test_lancamento_sem_parceiro_levanta_erro(self) -> None:
        lancamento = self._lancamento(parceiro_id=None)
        with pytest.raises(ValueError):
            self.service.gerar_parcelas(lancamento)

    def test_gerar_parcelas_valor_total_soma_bate_com_o_total_mesmo_com_arredondamento(self) -> None:
        parcelas = self.service.gerar_parcelas_valor_total(
            tipo_operacao=TipoOperacaoNota.entrada,
            parceiro_id=uuid.uuid4(),
            centro_custo_id=uuid.uuid4(),
            descricao="Nota parcelada",
            valor_total=Decimal("100.00"),
            numero_parcelas=3,
            data_inicio=date(2026, 1, 10),
        )
        assert len(parcelas) == 3
        assert sum((p.valor for p in parcelas), Decimal("0")) == Decimal("100.00")
        assert parcelas[0].valor == Decimal("33.33")
        assert parcelas[1].valor == Decimal("33.33")
        assert parcelas[2].valor == Decimal("33.34")
