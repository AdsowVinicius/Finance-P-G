"""Tipos SQLAlchemy Enum que espelham os ENUMs nativos do Postgres (schema.sql).

create_type=False em todos — os tipos já existem no banco (criados pela
migration a partir do schema.sql), o SQLAlchemy só precisa referenciá-los.
"""

from sqlalchemy import Enum

from app.models.enums import (
    FormaBaixa,
    FormatoExtrato,
    PapelUsuario,
    Periodicidade,
    StatusConciliacaoLinha,
    StatusConta,
    StatusFuncionario,
    StatusImportacao,
    StatusNota,
    StatusPreLancamentoWhatsapp,
    StatusProcessamentoNota,
    StatusProjeto,
    TipoLancamentoExtrato,
    TipoMatch,
    TipoNota,
    TipoOperacaoNota,
    TipoParceiro,
)


def _pg_enum(python_enum, name: str):
    return Enum(python_enum, name=name, create_type=False, values_callable=lambda e: [m.value for m in e])


papel_usuario_pg = _pg_enum(PapelUsuario, "papel_usuario")
tipo_parceiro_pg = _pg_enum(TipoParceiro, "tipo_parceiro")
tipo_nota_pg = _pg_enum(TipoNota, "tipo_nota")
tipo_operacao_nota_pg = _pg_enum(TipoOperacaoNota, "tipo_operacao_nota")
status_nota_pg = _pg_enum(StatusNota, "status_nota")
status_processamento_nota_pg = _pg_enum(StatusProcessamentoNota, "status_processamento_nota")
periodicidade_pg = _pg_enum(Periodicidade, "periodicidade")
status_conta_pg = _pg_enum(StatusConta, "status_conta")
forma_baixa_pg = _pg_enum(FormaBaixa, "forma_baixa")
formato_extrato_pg = _pg_enum(FormatoExtrato, "formato_extrato")
status_importacao_pg = _pg_enum(StatusImportacao, "status_importacao")
tipo_lancamento_extrato_pg = _pg_enum(TipoLancamentoExtrato, "tipo_lancamento_extrato")
status_conciliacao_linha_pg = _pg_enum(StatusConciliacaoLinha, "status_conciliacao_linha")
tipo_match_pg = _pg_enum(TipoMatch, "tipo_match")
status_projeto_pg = _pg_enum(StatusProjeto, "status_projeto")
status_funcionario_pg = _pg_enum(StatusFuncionario, "status_funcionario")
status_pre_lancamento_whatsapp_pg = _pg_enum(StatusPreLancamentoWhatsapp, "status_pre_lancamento_whatsapp")
