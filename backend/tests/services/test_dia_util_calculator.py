from datetime import date

from app.models.enums import RegraDiaUtilCategoria
from app.services.dia_util_calculator import DiaUtilCalculator


class TestDiaUtilCalculator:
    def setup_method(self) -> None:
        self.calc = DiaUtilCalculator()

    def test_dia_util_normal_nao_e_alterado(self) -> None:
        segunda_normal = date(2026, 9, 14)
        assert self.calc.proximo_dia_util(segunda_normal) == segunda_normal

    def test_sabado_empurra_para_segunda(self) -> None:
        sabado = date(2026, 9, 12)
        assert self.calc.proximo_dia_util(sabado) == date(2026, 9, 14)

    def test_domingo_empurra_para_segunda(self) -> None:
        domingo = date(2026, 9, 13)
        assert self.calc.proximo_dia_util(domingo) == date(2026, 9, 14)

    def test_feriado_nacional_empurra_para_proximo_dia_util(self) -> None:
        independencia_segunda = date(2026, 9, 7)
        assert self.calc.proximo_dia_util(independencia_segunda) == date(2026, 9, 8)

    def test_feriado_seguido_de_fim_de_semana_empurra_ate_segunda(self) -> None:
        dia_do_trabalho_sexta = date(2026, 5, 1)
        assert self.calc.proximo_dia_util(dia_do_trabalho_sexta) == date(2026, 5, 4)

    def test_ano_novo_empurra_para_proximo_dia_util(self) -> None:
        ano_novo = date(2026, 1, 1)
        assert self.calc.proximo_dia_util(ano_novo) == date(2026, 1, 2)

    def test_eh_dia_util_reconhece_fim_de_semana_e_feriado(self) -> None:
        assert self.calc.eh_dia_util(date(2026, 9, 14)) is True
        assert self.calc.eh_dia_util(date(2026, 9, 12)) is False
        assert self.calc.eh_dia_util(date(2026, 9, 7)) is False

    def test_nao_modifica_a_data_original_passada(self) -> None:
        sabado = date(2026, 9, 12)
        self.calc.proximo_dia_util(sabado)
        assert sabado == date(2026, 9, 12)


class TestAjustarPorCategoria:
    """Regra de deslocamento por categoria — pedido do usuário: pagamento de
    funcionário conta sábado como dia útil; conta de banco só seg-sex e
    empurra pra trás (dia útil anterior) se cair no fim de semana ou em
    feriado nacional (banco não abre em feriado).
    """

    def setup_method(self) -> None:
        self.calc = DiaUtilCalculator()

    def test_funcionario_sabado_nao_e_alterado(self) -> None:
        sabado = date(2026, 9, 12)
        assert self.calc.ajustar_por_categoria(sabado, RegraDiaUtilCategoria.funcionario) == sabado

    def test_funcionario_domingo_empurra_para_proximo_dia_util(self) -> None:
        domingo = date(2026, 9, 13)
        assert self.calc.ajustar_por_categoria(domingo, RegraDiaUtilCategoria.funcionario) == date(2026, 9, 14)

    def test_funcionario_dia_util_normal_nao_e_alterado(self) -> None:
        segunda_normal = date(2026, 9, 14)
        assert self.calc.ajustar_por_categoria(segunda_normal, RegraDiaUtilCategoria.funcionario) == segunda_normal

    def test_bancaria_sabado_empurra_para_sexta_anterior(self) -> None:
        sabado = date(2026, 9, 12)
        assert self.calc.ajustar_por_categoria(sabado, RegraDiaUtilCategoria.bancaria) == date(2026, 9, 11)

    def test_bancaria_domingo_empurra_para_sexta_anterior(self) -> None:
        domingo = date(2026, 9, 13)
        assert self.calc.ajustar_por_categoria(domingo, RegraDiaUtilCategoria.bancaria) == date(2026, 9, 11)

    def test_bancaria_dia_util_normal_nao_e_alterado(self) -> None:
        segunda_normal = date(2026, 9, 14)
        assert self.calc.ajustar_por_categoria(segunda_normal, RegraDiaUtilCategoria.bancaria) == segunda_normal

    def test_bancaria_feriado_em_dia_de_semana_empurra_para_dia_util_anterior(self) -> None:
        independencia_segunda = date(2026, 9, 7)
        assert self.calc.ajustar_por_categoria(
            independencia_segunda, RegraDiaUtilCategoria.bancaria
        ) == date(2026, 9, 4)

    def test_bancaria_feriado_emendado_com_fim_de_semana_empurra_alem_de_dois_dias(self) -> None:
        # Dia do Trabalho (sexta, 01/05/2026) emendado com o fim de semana:
        # domingo precisa voltar 3 dias (sáb + sexta feriado + só aí acha
        # quinta útil) — mais do que a regra de só-fim-de-semana previa.
        domingo_apos_feriado_na_sexta = date(2026, 5, 3)
        assert self.calc.ajustar_por_categoria(
            domingo_apos_feriado_na_sexta, RegraDiaUtilCategoria.bancaria
        ) == date(2026, 4, 30)

    def test_funcionario_feriado_em_dia_de_semana_empurra_para_proximo_dia_util(self) -> None:
        independencia_segunda = date(2026, 9, 7)
        assert self.calc.ajustar_por_categoria(
            independencia_segunda, RegraDiaUtilCategoria.funcionario
        ) == date(2026, 9, 8)

    def test_funcionario_feriado_na_sexta_empurra_para_sabado_que_conta_como_util(self) -> None:
        dia_do_trabalho_sexta = date(2026, 5, 1)
        assert self.calc.ajustar_por_categoria(
            dia_do_trabalho_sexta, RegraDiaUtilCategoria.funcionario
        ) == date(2026, 5, 2)
