"""Motor de matching da conciliação bancária.

Regra de negócio (CLAUDE.md): matching por VALOR EXATO + tolerância de
DATA — nunca tolerância de valor. Duas camadas automáticas:
  - automatico_exato: valor igual e mesma data de vencimento.
  - automatico_tolerancia: valor igual, data dentro da janela de tolerância
    (a nota pode ser emitida/vencer dias antes do pagamento cair na conta).
Mais uma camada de matching parcial (split): um lançamento do extrato
quita várias contas cuja soma bate exatamente com o valor do lançamento.

O caso inverso — vários lançamentos do extrato somados quitando uma única
conta — fica fora desta primeira versão (precisa de estado entre múltiplos
lançamentos, não só o candidato-a-candidato daqui). Documentado como
próximo passo; o schema (`conciliacoes` N:N) já suporta isso quando for
implementado.
"""

import itertools
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.models.conta_financeira import ContaFinanceira
from app.models.enums import StatusConta, TipoLancamentoExtrato, TipoMatch, TipoOperacaoNota

# Acima desse número de candidatas, não tentamos matching parcial (o custo
# combinatório de testar subconjuntos cresce rápido demais pra valer a pena
# aqui — na prática, dificilmente alguém divide um pagamento em tantas parcelas).
_MAX_CANDIDATAS_PARA_PARCIAL = 8


@dataclass
class LancamentoParaConciliar:
    data: date
    valor: Decimal
    tipo: TipoLancamentoExtrato


@dataclass
class ResultadoConciliacao:
    tipo_match: TipoMatch | None
    contas: list[ContaFinanceira] = field(default_factory=list)

    @property
    def encontrou_match(self) -> bool:
        return self.tipo_match is not None


def _direcao_esperada(tipo_lancamento: TipoLancamentoExtrato) -> TipoOperacaoNota:
    # crédito no extrato = dinheiro entrando = quita uma conta a RECEBER (saida)
    # débito no extrato = dinheiro saindo = quita uma conta a PAGAR (entrada)
    return TipoOperacaoNota.saida if tipo_lancamento == TipoLancamentoExtrato.credito else TipoOperacaoNota.entrada


class ConciliacaoMatcher:
    def __init__(self, tolerancia_dias: int = 5) -> None:
        self.tolerancia_dias = tolerancia_dias

    def conciliar(
        self, lancamento: LancamentoParaConciliar, contas_candidatas: list[ContaFinanceira]
    ) -> ResultadoConciliacao:
        direcao = _direcao_esperada(lancamento.tipo)
        candidatas = [
            c
            for c in contas_candidatas
            if c.tipo_operacao == direcao and c.status in (StatusConta.pendente, StatusConta.atrasado)
        ]

        exatas = [c for c in candidatas if c.valor == lancamento.valor and c.data_vencimento == lancamento.data]
        if len(exatas) == 1:
            return ResultadoConciliacao(TipoMatch.automatico_exato, exatas)

        na_tolerancia = [
            c
            for c in candidatas
            if c.valor == lancamento.valor and abs((c.data_vencimento - lancamento.data).days) <= self.tolerancia_dias
        ]
        if len(na_tolerancia) == 1:
            return ResultadoConciliacao(TipoMatch.automatico_tolerancia, na_tolerancia)

        dentro_da_janela = [
            c for c in candidatas if abs((c.data_vencimento - lancamento.data).days) <= self.tolerancia_dias
        ]
        combinacao = self._buscar_combinacao_com_soma_exata(dentro_da_janela, lancamento.valor)
        if combinacao:
            return ResultadoConciliacao(TipoMatch.parcial, combinacao)

        # valor bateu mas em mais de uma conta (ambíguo) ou nada bateu:
        # em ambos os casos não arriscamos escolher sozinho — fica pendente
        # pra conciliação manual.
        return ResultadoConciliacao(None, [])

    def _buscar_combinacao_com_soma_exata(
        self, candidatas: list[ContaFinanceira], valor_alvo: Decimal
    ) -> list[ContaFinanceira] | None:
        """Busca combinações de candidatas cuja soma bate exatamente com o
        valor alvo. Se mais de uma combinação bater, é ambíguo — mesma
        política do match exato/tolerância, não arriscamos escolher sozinho.
        """
        if len(candidatas) < 2 or len(candidatas) > _MAX_CANDIDATAS_PARA_PARCIAL:
            return None

        encontradas: list[list[ContaFinanceira]] = []
        for tamanho in range(2, len(candidatas) + 1):
            for combinacao in itertools.combinations(candidatas, tamanho):
                if sum((c.valor for c in combinacao), Decimal("0")) == valor_alvo:
                    encontradas.append(list(combinacao))
                    if len(encontradas) > 1:
                        return None
        return encontradas[0] if len(encontradas) == 1 else None
