"""Registry pattern: um provider por formato de extrato (OFX, CSV, e no
futuro por banco). Adicionar um formato novo = registrar uma classe nova
aqui, sem tocar no ConciliacaoMatcher nem no resto do core.
"""

import csv
import hashlib
import io
import logging
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Protocol

import ofxparse

from app.models.enums import FormatoExtrato, TipoLancamentoExtrato

logger = logging.getLogger(__name__)


@dataclass
class LancamentoExtratoDTO:
    data: date
    descricao: str
    valor: Decimal  # sempre positivo — a direção vem de `tipo`
    tipo: TipoLancamentoExtrato
    fitid: str


class ExtratoParserProvider(Protocol):
    def parse(self, conteudo: bytes) -> list[LancamentoExtratoDTO]: ...


class OfxParserProvider:
    def parse(self, conteudo: bytes) -> list[LancamentoExtratoDTO]:
        # fail_fast=False: alguns bancos exportam OFX com <NAME> vazio em
        # certas transações (tarifa, estorno etc.) — sem isso, uma única
        # transação malformada derruba a importação do extrato inteiro.
        # Com fail_fast=False o ofxparse pula só a transação ruim e segue.
        ofx = ofxparse.OfxParser.parse(io.BytesIO(conteudo), fail_fast=False)
        descartadas = ofx.account.statement.discarded_entries
        if descartadas:
            logger.warning("extrato OFX: %d transação(ões) ignorada(s) por erro de formato: %s", len(descartadas), [d["error"] for d in descartadas])
        lancamentos = []
        for indice, transacao in enumerate(ofx.account.statement.transactions, start=1):
            tipo = TipoLancamentoExtrato.credito if transacao.type == "credit" else TipoLancamentoExtrato.debito
            data = transacao.date.date() if isinstance(transacao.date, datetime) else transacao.date
            descricao = (transacao.memo or transacao.payee or "").strip()
            valor = abs(transacao.amount)
            # alguns bancos exportam <FITID> vazio. fitid=None faz o filtro de
            # idempotência em processar_importacao_extrato (fitid == None)
            # virar "fitid IS NULL" e colidir com QUALQUER outro lançamento
            # sem FITID da mesma conta — tratando transações distintas como
            # duplicata da primeira. Deriva um fitid sintético (mesma
            # estratégia do CsvParserProvider) em vez de propagar None.
            fitid = transacao.id or hashlib.sha256(
                f"{indice}|{data}|{descricao}|{valor}|{tipo.value}".encode("utf-8")
            ).hexdigest()[:32]
            lancamentos.append(
                LancamentoExtratoDTO(
                    data=data,
                    descricao=descricao,
                    valor=valor,
                    tipo=tipo,
                    fitid=fitid,
                )
            )
        return lancamentos


class CsvParserProvider:
    """Formato CSV esperado (cabeçalho obrigatório):
    data,descricao,valor,tipo
    2026-09-10,PIX recebido,1500.00,credito

    - data: AAAA-MM-DD
    - valor: sempre positivo
    - tipo: 'credito' ou 'debito'

    CSV não tem um ID de transação nativo como o FITID do OFX, então o
    fitid é derivado (hash determinístico da própria linha) — reimportar
    o mesmo arquivo gera os mesmos fitids e não duplica, mas isso é
    best-effort (não é um ID emitido pelo banco).
    """

    def parse(self, conteudo: bytes) -> list[LancamentoExtratoDTO]:
        texto = conteudo.decode("utf-8-sig")
        leitor = csv.DictReader(io.StringIO(texto))

        colunas_esperadas = {"data", "descricao", "valor", "tipo"}
        if leitor.fieldnames is None or not colunas_esperadas.issubset({c.strip().lower() for c in leitor.fieldnames}):
            raise ValueError(f"CSV precisa ter as colunas {sorted(colunas_esperadas)} (encontrado: {leitor.fieldnames})")

        lancamentos = []
        for indice, linha_bruta in enumerate(leitor, start=1):
            linha = {k.strip().lower(): (v or "").strip() for k, v in linha_bruta.items()}
            try:
                data = datetime.strptime(linha["data"], "%Y-%m-%d").date()
                valor = abs(Decimal(linha["valor"]))
                tipo_raw = linha["tipo"].lower()
                if tipo_raw not in ("credito", "debito"):
                    raise ValueError(f"tipo inválido: {tipo_raw!r} (use 'credito' ou 'debito')")
            except (ValueError, InvalidOperation) as exc:
                # uma linha ruim não pode derrubar o CSV inteiro — mesma
                # filosofia do fail_fast=False do provider OFX: loga e pula
                # só essa linha, segue processando as demais.
                logger.warning("extrato CSV: linha #%d ignorada por erro de formato: %r (%s)", indice, linha, exc)
                continue

            descricao = linha["descricao"]
            # inclui o índice da linha no hash: sem isso, duas transações
            # idênticas no mesmo arquivo (mesma data/descrição/valor/tipo —
            # plausível em tarifas recorrentes) colidiriam no mesmo fitid e
            # a segunda seria descartada como falsa duplicata.
            fitid = hashlib.sha256(f"{indice}|{data}|{descricao}|{valor}|{tipo_raw}".encode("utf-8")).hexdigest()[:32]

            lancamentos.append(
                LancamentoExtratoDTO(
                    data=data,
                    descricao=descricao,
                    valor=valor,
                    tipo=TipoLancamentoExtrato(tipo_raw),
                    fitid=fitid,
                )
            )
        return lancamentos


class ExtratoParserService:
    _providers: dict[FormatoExtrato, ExtratoParserProvider] = {
        FormatoExtrato.ofx: OfxParserProvider(),
        FormatoExtrato.csv: CsvParserProvider(),
    }

    def parse(self, formato: FormatoExtrato, conteudo: bytes) -> list[LancamentoExtratoDTO]:
        provider = self._providers.get(formato)
        if provider is None:
            raise ValueError(f"formato de extrato não suportado: {formato}")
        return provider.parse(conteudo)
