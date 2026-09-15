from datetime import date, timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session

from app.models.categoria_lancamento import CategoriaLancamento
from app.models.conta_financeira import ContaFinanceira
from app.models.enums import Periodicidade
from app.models.lancamento_recorrente import LancamentoRecorrente
from app.services.dia_util_calculator import DiaUtilCalculator


def _data_da_ocorrencia(
    data_inicio: date, indice: int, periodicidade: Periodicidade, intervalo_dias: int | None
) -> date:
    """Calcula a data da ocorrência `indice` (0-based) SEMPRE a partir da
    data-âncora original — nunca acumulando sobre a ocorrência anterior.

    Isso importa pra recorrência mensal/anual: se começar no dia 31 e passar
    por um mês sem dia 31 (ex: fevereiro), `relativedelta` ajusta pro último
    dia daquele mês (28/29) — mas o mês seguinte precisa voltar a mirar o
    dia 31 original, não ficar "preso" no 28. Calcular sempre a partir da
    âncora garante isso; acumular sobre o resultado anterior não.
    """
    if periodicidade == Periodicidade.mensal:
        return data_inicio + relativedelta(months=indice)
    if periodicidade == Periodicidade.quinzenal:
        return data_inicio + timedelta(days=15 * indice)
    if periodicidade == Periodicidade.semanal:
        return data_inicio + timedelta(days=7 * indice)
    if periodicidade == Periodicidade.anual:
        return data_inicio + relativedelta(years=indice)
    if periodicidade == Periodicidade.personalizada_dias:
        if not intervalo_dias:
            raise ValueError("periodicidade 'personalizada_dias' exige intervalo_dias")
        return data_inicio + timedelta(days=intervalo_dias * indice)
    raise ValueError(f"periodicidade desconhecida: {periodicidade}")


def gerar_datas_ocorrencias(
    data_inicio: date,
    periodicidade: Periodicidade,
    numero_ocorrencias: int | None = None,
    data_fim: date | None = None,
    intervalo_dias: int | None = None,
) -> list[date]:
    """Gera as datas 'puras' (antes do ajuste de dia útil) de cada ocorrência.

    Para em numero_ocorrencias OU data_fim, o que vier primeiro. Pelo menos
    um dos dois precisa ser informado (mesma regra do schema.sql).
    """
    if numero_ocorrencias is None and data_fim is None:
        raise ValueError("informe numero_ocorrencias e/ou data_fim")

    datas: list[date] = []
    indice = 0
    while True:
        if numero_ocorrencias is not None and len(datas) >= numero_ocorrencias:
            break
        atual = _data_da_ocorrencia(data_inicio, indice, periodicidade, intervalo_dias)
        if data_fim is not None and atual > data_fim:
            break
        datas.append(atual)
        indice += 1
    return datas


class RecorrenciaService:
    """Motor de recorrência: gera as parcelas (contas_financeiras) de um
    lançamento recorrente, sempre passando cada data pelo DiaUtilCalculator.
    """

    def __init__(self, dia_util: DiaUtilCalculator | None = None) -> None:
        self._dia_util = dia_util or DiaUtilCalculator()

    def gerar_parcelas(self, lancamento: LancamentoRecorrente, db: Session | None = None) -> list[ContaFinanceira]:
        if lancamento.parceiro_id is None:
            raise ValueError(
                "lançamento recorrente sem parceiro não pode gerar contas financeiras "
                "nesta versão (fluxo de funcionários/folha está fora do MVP atual)"
            )

        datas = gerar_datas_ocorrencias(
            data_inicio=lancamento.data_inicio,
            periodicidade=lancamento.periodicidade,
            numero_ocorrencias=lancamento.numero_ocorrencias,
            data_fim=lancamento.data_fim,
            intervalo_dias=lancamento.intervalo_dias,
        )
        total = len(datas)

        # Categoria é opcional — sem ela (ou categoria inativa), o comportamento
        # continua exatamente o padrão de sempre (proximo_dia_util).
        categoria: CategoriaLancamento | None = None
        if lancamento.categoria_id is not None and db is not None:
            categoria = db.get(CategoriaLancamento, lancamento.categoria_id)

        parcelas = []
        for indice, data_original in enumerate(datas, start=1):
            if categoria is not None and categoria.ativo:
                data_ajustada = self._dia_util.ajustar_por_categoria(data_original, categoria.regra_dia_util)
            else:
                data_ajustada = self._dia_util.proximo_dia_util(data_original)
            parcelas.append(
                ContaFinanceira(
                    tipo_operacao=lancamento.tipo_operacao,
                    lancamento_recorrente_id=lancamento.id,
                    parceiro_id=lancamento.parceiro_id,
                    centro_custo_id=lancamento.centro_custo_id,
                    categoria_id=lancamento.categoria_id,
                    descricao=lancamento.descricao,
                    numero_parcela=indice,
                    total_parcelas=total,
                    valor=lancamento.valor_parcela,
                    data_vencimento_original=data_original,
                    data_vencimento=data_ajustada,
                    conta_bancaria_id=lancamento.conta_bancaria_id,
                )
            )
        return parcelas

    def gerar_parcelas_valor_total(
        self,
        *,
        tipo_operacao,
        parceiro_id,
        centro_custo_id,
        descricao: str,
        valor_total: Decimal,
        numero_parcelas: int,
        data_inicio: date,
        nota_fiscal_id=None,
    ) -> list[ContaFinanceira]:
        """Divide um valor total em N parcelas mensais (uso: nota fiscal
        parcelada). A última parcela absorve o resto da divisão pra nunca
        perder centavo (dinheiro sempre em Decimal, soma tem que bater).
        """
        datas = gerar_datas_ocorrencias(
            data_inicio=data_inicio,
            periodicidade=Periodicidade.mensal,
            numero_ocorrencias=numero_parcelas,
        )

        valor_base = (valor_total / numero_parcelas).quantize(Decimal("0.01"))
        valor_ultima = valor_total - valor_base * (numero_parcelas - 1)

        parcelas = []
        for indice, data_original in enumerate(datas, start=1):
            data_ajustada = self._dia_util.proximo_dia_util(data_original)
            valor_parcela = valor_ultima if indice == numero_parcelas else valor_base
            parcelas.append(
                ContaFinanceira(
                    tipo_operacao=tipo_operacao,
                    nota_fiscal_id=nota_fiscal_id,
                    parceiro_id=parceiro_id,
                    centro_custo_id=centro_custo_id,
                    descricao=descricao,
                    numero_parcela=indice,
                    total_parcelas=numero_parcelas,
                    valor=valor_parcela,
                    data_vencimento_original=data_original,
                    data_vencimento=data_ajustada,
                )
            )
        return parcelas
