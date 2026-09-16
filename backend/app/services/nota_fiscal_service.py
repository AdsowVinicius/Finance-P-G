import io
import re
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.models.conta_financeira import ContaFinanceira
from app.models.enums import StatusConta, StatusNota, StatusProcessamentoNota, TipoNota, TipoOperacaoNota, TipoParceiro
from app.models.nota_fiscal import NotaFiscal
from app.models.parceiro import Parceiro
from app.services.recorrencia_service import RecorrenciaService

# Âncoras (?<!\d)/(?!\d) garantem que os 44 dígitos são a sequência inteira,
# nunca um recorte de um número maior (ex: linha digitável de boleto ao lado
# da chave no mesmo PDF, com 47+ dígitos) — sem elas, um número mais longo
# geraria uma chave falsa-positiva com os 44 primeiros dígitos dele.
_CHAVE_ACESSO_REGEX = re.compile(r"(?<!\d)(?:\d[\s.\-]?){44}(?!\d)")

# CNPJ sentinela — nunca é um CNPJ real (14 dígitos, todos zero). Marca o
# parceiro "provisório" de uma nota cuja chave foi achada mas cuja resolução
# via API ainda não voltou. Nunca é o parceiro final de uma nota concluída.
CNPJ_SENTINELA = "00000000000000"


def extrair_texto_pdf(conteudo_pdf: bytes) -> str:
    leitor = PdfReader(io.BytesIO(conteudo_pdf))
    return "\n".join(pagina.extract_text() or "" for pagina in leitor.pages)


def extrair_chave_acesso(texto: str) -> str | None:
    """Procura os 44 dígitos da chave de acesso da NFe no texto do PDF.

    No DANFE a chave costuma vir separada em grupos de 4 (com espaço),
    então aceitamos separadores opcionais entre os dígitos e removemos
    tudo que não for dígito antes de validar o tamanho.
    """
    for match in _CHAVE_ACESSO_REGEX.finditer(texto):
        candidato = re.sub(r"\D", "", match.group())
        if len(candidato) == 44:
            return candidato
    return None


def obter_ou_criar_parceiro_sentinela(db: Session) -> Parceiro:
    """Placeholder usado só entre o upload (chave achada) e a resolução da
    API — permite criar a nota_fiscal (parceiro_id é NOT NULL no schema)
    antes de sabermos quem é o fornecedor de verdade. A task substitui isso
    pelo parceiro real assim que a API resolve.
    """
    parceiro = db.query(Parceiro).filter(Parceiro.cnpj_cpf == CNPJ_SENTINELA).first()
    if parceiro is not None:
        return parceiro
    parceiro = Parceiro(
        tipo=TipoParceiro.fornecedor,
        cnpj_cpf=CNPJ_SENTINELA,
        razao_social="Aguardando identificação automática via API de NFe",
    )
    db.add(parceiro)
    db.flush()
    return parceiro


def obter_ou_criar_parceiro_por_cnpj(
    db: Session, cnpj: str, razao_social: str, tipo_operacao: TipoOperacaoNota
) -> Parceiro:
    """Acha o parceiro pelo CNPJ que veio no XML oficial da nota; cria um
    novo automaticamente se ainda não existir no cadastro (é exatamente o
    que 'sem digitação manual' promete — o usuário não precisa ter
    pré-cadastrado o fornecedor antes de subir a nota).
    """
    parceiro = db.query(Parceiro).filter(Parceiro.cnpj_cpf == cnpj).first()
    if parceiro is not None:
        return parceiro

    tipo = TipoParceiro.fornecedor if tipo_operacao == TipoOperacaoNota.entrada else TipoParceiro.cliente
    parceiro = Parceiro(tipo=tipo, cnpj_cpf=cnpj, razao_social=razao_social)
    db.add(parceiro)
    db.flush()
    return parceiro


def atualizar_status_conciliacao(db: Session, nota_fiscal_id: uuid.UUID | None) -> None:
    """Recalcula o status da nota (pendente/parcialmente_conciliada/conciliada)
    a partir do status atual de baixa das parcelas (contas_financeiras)
    vinculadas a ela. Chamado sempre que uma dessas parcelas muda de status
    (baixa manual, conciliação automática ou manual). Nunca mexe em nota
    cancelada.
    """
    if nota_fiscal_id is None:
        return
    nota = db.get(NotaFiscal, nota_fiscal_id)
    if nota is None or nota.status == StatusNota.cancelada:
        return

    parcelas = [
        p
        for p in db.query(ContaFinanceira).filter(ContaFinanceira.nota_fiscal_id == nota_fiscal_id).all()
        if p.status != StatusConta.cancelado
    ]
    if not parcelas:
        return

    pagas = [p for p in parcelas if p.status == StatusConta.pago]
    if len(pagas) == len(parcelas):
        nota.status = StatusNota.conciliada
    elif pagas:
        nota.status = StatusNota.parcialmente_conciliada
    else:
        nota.status = StatusNota.pendente


@dataclass
class ResultadoCadastroNota:
    """Result object (CLAUDE.md: evitar exceptions pra fluxo de controle
    normal) — chave duplicada e chave não encontrada são resultados
    esperados do cadastro, não exceções.
    """

    ok: bool
    nota: NotaFiscal | None = None
    codigo_erro: str | None = None  # "chave_duplicada" | "chave_nao_encontrada"
    erro: str | None = None


class NotaFiscalService:
    def extrair_chave_de_pdf(self, conteudo_pdf: bytes) -> str | None:
        texto = extrair_texto_pdf(conteudo_pdf)
        return extrair_chave_acesso(texto)

    def buscar_nota_pela_chave(
        self, db: Session, chave_acesso: str, excluir_nota_id: uuid.UUID | None = None
    ) -> NotaFiscal | None:
        query = db.query(NotaFiscal).filter(NotaFiscal.chave_acesso == chave_acesso)
        if excluir_nota_id is not None:
            query = query.filter(NotaFiscal.id != excluir_nota_id)
        return query.first()

    def cadastrar_via_upload(
        self,
        db: Session,
        *,
        conteudo_pdf: bytes,
        caminho_pdf: str,
        centro_custo_id: uuid.UUID,
        tipo_operacao: TipoOperacaoNota,
        tipo: TipoNota,
        criado_por: uuid.UUID,
        parceiro_id: uuid.UUID | None = None,
        valor_total: Decimal | None = None,
        data_emissao: date | None = None,
        numero_nota: str | None = None,
        serie: str | None = None,
        despesa_fixa: bool = False,
        despesa_parcelada: bool = False,
        numero_parcelas: int = 1,
    ) -> ResultadoCadastroNota:
        """Orquestra o fluxo de upload de nota (RF05): extrai a chave do PDF,
        decide entre o fluxo manual (usuário preencheu parceiro/valor/data) e
        o automático (chave achada, dados vêm depois via API/Celery), cria a
        nota e — só no fluxo manual, onde o valor já é conhecido — as
        parcelas. Não commita; o chamador decide a transação, o log de
        auditoria e o disparo da task Celery.
        """
        chave_acesso = self.extrair_chave_de_pdf(conteudo_pdf)

        if chave_acesso:
            existente = self.buscar_nota_pela_chave(db, chave_acesso)
            if existente is not None:
                return ResultadoCadastroNota(
                    ok=False,
                    codigo_erro="chave_duplicada",
                    erro=f"Já existe uma nota cadastrada com esta chave de acesso (id={existente.id})",
                )

        preenchido_manualmente = parceiro_id is not None and valor_total is not None and data_emissao is not None

        if not chave_acesso and not preenchido_manualmente:
            return ResultadoCadastroNota(
                ok=False,
                codigo_erro="chave_nao_encontrada",
                erro=(
                    "Não foi possível achar a chave de acesso no PDF — informe parceiro, valor e data "
                    "manualmente (campos mínimos quando a extração automática falha)."
                ),
            )

        if preenchido_manualmente:
            # usuário escolheu preencher na mão (ou a chave não foi achada e
            # isso é obrigatório) — cria a nota já completa, sem esperar a API.
            nota = NotaFiscal(
                parceiro_id=parceiro_id,
                centro_custo_id=centro_custo_id,
                tipo=tipo,
                tipo_operacao=tipo_operacao,
                numero_nota=numero_nota,
                serie=serie,
                chave_acesso=chave_acesso,
                valor_total=valor_total,
                data_emissao=data_emissao,
                despesa_fixa=despesa_fixa,
                despesa_parcelada=despesa_parcelada,
                numero_parcelas=numero_parcelas,
                arquivo_pdf_path=caminho_pdf,
                status_processamento=(
                    StatusProcessamentoNota.consultando_api
                    if chave_acesso
                    else StatusProcessamentoNota.chave_nao_encontrada
                ),
                criado_por=criado_por,
            )
            db.add(nota)
            db.flush()

            parcelas = RecorrenciaService().gerar_parcelas_valor_total(
                tipo_operacao=nota.tipo_operacao,
                parceiro_id=nota.parceiro_id,
                centro_custo_id=nota.centro_custo_id,
                descricao=f"{'NFe' if nota.tipo == TipoNota.nfe else 'NFSe'} {nota.numero_nota or ''}".strip(),
                valor_total=nota.valor_total,
                numero_parcelas=nota.numero_parcelas,
                data_inicio=nota.data_emissao,
                nota_fiscal_id=nota.id,
            )
            db.add_all(parcelas)
        else:
            # fluxo automático de verdade: chave achada, nada preenchido na
            # mão. parceiro/valor/data ainda não são conhecidos — usa um
            # parceiro sentinela só pra satisfazer a FK (NOT NULL no schema)
            # até a task resolver os dados reais via API e gerar as parcelas.
            parceiro_sentinela = obter_ou_criar_parceiro_sentinela(db)
            nota = NotaFiscal(
                parceiro_id=parceiro_sentinela.id,
                centro_custo_id=centro_custo_id,
                tipo=tipo,
                tipo_operacao=tipo_operacao,
                chave_acesso=chave_acesso,
                valor_total=Decimal("0.01"),
                data_emissao=date.today(),
                arquivo_pdf_path=caminho_pdf,
                status_processamento=StatusProcessamentoNota.consultando_api,
                criado_por=criado_por,
            )
            db.add(nota)
            db.flush()
            # parcelas só são geradas quando o valor de verdade chegar (task)

        return ResultadoCadastroNota(ok=True, nota=nota)

    def gerar_parcela_se_dados_completos(self, db: Session, nota: NotaFiscal) -> None:
        """Chamado depois de completar campos de uma nota (fallback manual ou
        WhatsApp): se agora tem parceiro real e valor real e ainda não tem
        parcela nenhuma, gera a parcela à vista. Nota parcelada usa o
        cadastro completo (upload manual) em vez desse atalho.
        """
        tem_parcela = db.query(ContaFinanceira.id).filter(ContaFinanceira.nota_fiscal_id == nota.id).first() is not None
        parceiro_sentinela = obter_ou_criar_parceiro_sentinela(db)
        dados_completos = nota.parceiro_id != parceiro_sentinela.id and nota.valor_total > Decimal("0.01")

        if dados_completos and not tem_parcela:
            parcelas = RecorrenciaService().gerar_parcelas_valor_total(
                tipo_operacao=nota.tipo_operacao,
                parceiro_id=nota.parceiro_id,
                centro_custo_id=nota.centro_custo_id,
                descricao=f"{'NFe' if nota.tipo == TipoNota.nfe else 'NFSe'} {nota.numero_nota or ''}".strip(),
                valor_total=nota.valor_total,
                numero_parcelas=1,
                data_inicio=nota.data_emissao,
                nota_fiscal_id=nota.id,
            )
            db.add_all(parcelas)
            if nota.status_processamento in (StatusProcessamentoNota.chave_nao_encontrada, StatusProcessamentoNota.erro_api):
                nota.status_processamento = StatusProcessamentoNota.concluido
