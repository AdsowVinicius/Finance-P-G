import io
import re

from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.models.enums import TipoOperacaoNota, TipoParceiro
from app.models.parceiro import Parceiro

_CHAVE_ACESSO_REGEX = re.compile(r"(?:\d[\s.\-]?){44}")

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


class NotaFiscalService:
    def extrair_chave_de_pdf(self, conteudo_pdf: bytes) -> str | None:
        texto = extrair_texto_pdf(conteudo_pdf)
        return extrair_chave_acesso(texto)
