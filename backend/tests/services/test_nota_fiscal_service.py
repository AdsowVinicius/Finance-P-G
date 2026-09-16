import uuid
from decimal import Decimal

from app.models.conta_financeira import ContaFinanceira
from app.models.enums import StatusConta, TipoOperacaoNota
from app.models.nota_fiscal import NotaFiscal
from app.services.nota_fiscal_service import atualizar_status_conciliacao, extrair_chave_acesso


class TestExtrairChaveAcesso:
    def test_chave_sem_separadores(self) -> None:
        texto = "Texto antes " + "1" * 44 + " texto depois"
        assert extrair_chave_acesso(texto) == "1" * 44

    def test_chave_em_grupos_de_4_com_espaco_como_no_danfe(self) -> None:
        grupos = ["3526", "0912", "3456", "7890", "0001", "5500", "1000", "0012", "3456", "7891", "2345"]
        texto = f"Chave de acesso: {' '.join(grupos)}"
        assert extrair_chave_acesso(texto) == "".join(grupos)

    def test_chave_ausente_retorna_none(self) -> None:
        texto = "DANFE sem chave legível, PDF escaneado"
        assert extrair_chave_acesso(texto) is None

    def test_sequencia_de_digitos_menor_que_44_nao_e_aceita(self) -> None:
        texto = "CNPJ: 12.345.678/0001-90"
        assert extrair_chave_acesso(texto) is None

    def test_pega_a_primeira_ocorrencia_valida(self) -> None:
        chave_1 = "1" * 44
        chave_2 = "2" * 44
        texto = f"{chave_1} ... mais adiante ... {chave_2}"
        assert extrair_chave_acesso(texto) == chave_1

    def test_sequencia_com_mais_de_44_digitos_nao_gera_falso_positivo(self) -> None:
        # ex: linha digitável de boleto (47+ dígitos) grudada na chave no PDF —
        # não pode devolver os 44 primeiros dígitos como se fosse a chave.
        texto = "Linha digitável: " + "3" * 47
        assert extrair_chave_acesso(texto) is None

    def test_chave_grudada_em_sequencia_maior_nao_e_confundida(self) -> None:
        chave_valida = "9" * 44
        texto = f"lixo{'5' * 3}{chave_valida} depois texto normal"
        assert extrair_chave_acesso(texto) is None


class TestAtualizarStatusConciliacao:
    def _nota(self) -> NotaFiscal:
        return NotaFiscal(id=uuid.uuid4())

    def _parcela(self, status: StatusConta) -> ContaFinanceira:
        return ContaFinanceira(
            id=uuid.uuid4(),
            tipo_operacao=TipoOperacaoNota.entrada,
            parceiro_id=uuid.uuid4(),
            descricao="parcela teste",
            valor=Decimal("100.00"),
            status=status,
        )

    def test_parcela_cancelada_e_ignorada_no_calculo_de_status(self, monkeypatch) -> None:
        nota = self._nota()
        pagas = [self._parcela(StatusConta.pago), self._parcela(StatusConta.pago)]
        cancelada = self._parcela(StatusConta.cancelado)
        parcelas = pagas + [cancelada]

        class _QueryFake:
            def filter(self, *_args, **_kwargs):
                return self

            def all(self):
                return parcelas

        class _DbFake:
            def get(self, _model, _id):
                return nota

            def query(self, _model):
                return _QueryFake()

        atualizar_status_conciliacao(_DbFake(), nota.id)

        assert nota.status.value == "conciliada"
