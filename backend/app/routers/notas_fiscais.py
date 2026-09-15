import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_write_access
from app.core.storage import salvar_arquivo_upload
from app.database import get_db
from app.models.enums import StatusProcessamentoNota, TipoNota, TipoOperacaoNota
from app.models.nota_fiscal import NotaFiscal
from app.models.usuario import Usuario
from app.schemas.nota_fiscal import ChaveAcessoManual, NotaFiscalRead
from app.services import auditoria_service
from app.services.nota_fiscal_service import NotaFiscalService, obter_ou_criar_parceiro_sentinela
from app.services.recorrencia_service import RecorrenciaService
from app.workers.tasks import processar_nota_fiscal

router = APIRouter(prefix="/notas-fiscais", tags=["notas fiscais"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[NotaFiscalRead])
def listar_notas_fiscais(
    parceiro_id: uuid.UUID | None = None,
    centro_custo_id: uuid.UUID | None = None,
    status_processamento: StatusProcessamentoNota | None = None,
    data_emissao_de: date | None = None,
    data_emissao_ate: date | None = None,
    db: Session = Depends(get_db),
) -> list[NotaFiscal]:
    query = db.query(NotaFiscal)
    if parceiro_id is not None:
        query = query.filter(NotaFiscal.parceiro_id == parceiro_id)
    if centro_custo_id is not None:
        query = query.filter(NotaFiscal.centro_custo_id == centro_custo_id)
    if status_processamento is not None:
        query = query.filter(NotaFiscal.status_processamento == status_processamento)
    if data_emissao_de is not None:
        query = query.filter(NotaFiscal.data_emissao >= data_emissao_de)
    if data_emissao_ate is not None:
        query = query.filter(NotaFiscal.data_emissao <= data_emissao_ate)
    return query.order_by(NotaFiscal.data_emissao.desc()).all()


@router.get("/{nota_id}", response_model=NotaFiscalRead)
def obter_nota_fiscal(nota_id: uuid.UUID, db: Session = Depends(get_db)) -> NotaFiscal:
    nota = db.get(NotaFiscal, nota_id)
    if nota is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nota fiscal não encontrada")
    return nota


@router.post(
    "",
    response_model=NotaFiscalRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_write_access)],
)
async def cadastrar_nota_fiscal(
    arquivo: UploadFile = File(...),
    centro_custo_id: uuid.UUID = Form(...),
    tipo_operacao: TipoOperacaoNota = Form(TipoOperacaoNota.entrada),
    # Os campos abaixo são OPCIONAIS: RF05/"único input manual é o PDF" — se a
    # chave de acesso for achada no PDF, fornecedor/valor/data vêm da API de
    # consulta automaticamente. Só viram obrigatórios no fallback (chave não
    # encontrada) ou se o usuário preferir preencher na mão mesmo com a chave
    # achada (ex: já sabe os dados e não quer esperar a API resolver).
    parceiro_id: uuid.UUID | None = Form(None),
    tipo: TipoNota = Form(TipoNota.nfe),
    valor_total: Decimal | None = Form(None, gt=0),
    data_emissao: date | None = Form(None),
    numero_nota: str | None = Form(None),
    serie: str | None = Form(None),
    despesa_fixa: bool = Form(False),
    despesa_parcelada: bool = Form(False),
    numero_parcelas: int = Form(1, ge=1),
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
) -> NotaFiscal:
    conteudo = await arquivo.read()
    try:
        caminho_pdf = salvar_arquivo_upload(arquivo, "notas", conteudo)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    chave_acesso = NotaFiscalService().extrair_chave_de_pdf(conteudo)

    if chave_acesso:
        existente = db.query(NotaFiscal).filter(NotaFiscal.chave_acesso == chave_acesso).first()
        if existente is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Já existe uma nota cadastrada com esta chave de acesso (id={existente.id})",
            )

    preenchido_manualmente = parceiro_id is not None and valor_total is not None and data_emissao is not None

    if not chave_acesso and not preenchido_manualmente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Não foi possível achar a chave de acesso no PDF — informe parceiro, valor e data "
                "manualmente (campos mínimos quando a extração automática falha)."
            ),
        )

    if preenchido_manualmente:
        # usuário escolheu preencher na mão (ou a chave não foi achada e isso
        # é obrigatório) — cria a nota já completa, sem esperar a API.
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
                StatusProcessamentoNota.consultando_api if chave_acesso else StatusProcessamentoNota.chave_nao_encontrada
            ),
            criado_por=usuario_atual.id,
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
        # fluxo automático de verdade: chave achada, nada preenchido na mão.
        # parceiro/valor/data ainda não são conhecidos — usa um parceiro
        # sentinela só pra satisfazer a FK (NOT NULL no schema) até a task
        # resolver os dados reais via API e gerar as parcelas de verdade.
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
            criado_por=usuario_atual.id,
        )
        db.add(nota)
        db.flush()
        # parcelas só são geradas quando o valor de verdade chegar (task)

    auditoria_service.registrar_criacao(db, usuario_atual.id, "notas_fiscais", nota)
    db.commit()
    db.refresh(nota)

    if nota.status_processamento == StatusProcessamentoNota.consultando_api:
        processar_nota_fiscal.delay(str(nota.id))

    return nota


@router.patch("/{nota_id}/chave-acesso", response_model=NotaFiscalRead, dependencies=[Depends(require_write_access)])
def informar_chave_manual(
    nota_id: uuid.UUID,
    dados: ChaveAcessoManual,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
) -> NotaFiscal:
    """Fallback não-bloqueante do RF05: se a extração automática falhar
    (ex: PDF escaneado sem camada de texto), o usuário cola a chave aqui.
    """
    nota = db.get(NotaFiscal, nota_id)
    if nota is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nota fiscal não encontrada")

    duplicada = (
        db.query(NotaFiscal)
        .filter(NotaFiscal.chave_acesso == dados.chave_acesso, NotaFiscal.id != nota_id)
        .first()
    )
    if duplicada is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Já existe uma nota cadastrada com esta chave de acesso (id={duplicada.id})",
        )

    antes = auditoria_service.snapshot(nota)
    nota.chave_acesso = dados.chave_acesso
    nota.status_processamento = StatusProcessamentoNota.consultando_api
    auditoria_service.registrar_edicao(db, usuario_atual.id, "notas_fiscais", antes, nota)
    db.commit()
    db.refresh(nota)

    processar_nota_fiscal.delay(str(nota.id))

    return nota


@router.post("/{nota_id}/reprocessar", response_model=NotaFiscalRead, dependencies=[Depends(require_write_access)])
def reprocessar_nota_fiscal(
    nota_id: uuid.UUID, db: Session = Depends(get_db), usuario_atual: Usuario = Depends(get_current_user)
) -> NotaFiscal:
    """Retry manual — só faz sentido quando a última tentativa falhou
    (erro_api). Idempotente: a task não rechama a API se já 'concluido'.
    """
    nota = db.get(NotaFiscal, nota_id)
    if nota is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nota fiscal não encontrada")
    if not nota.chave_acesso:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nota ainda não tem chave de acesso")

    antes = auditoria_service.snapshot(nota)
    nota.status_processamento = StatusProcessamentoNota.consultando_api
    auditoria_service.registrar_edicao(db, usuario_atual.id, "notas_fiscais", antes, nota)
    db.commit()
    db.refresh(nota)

    processar_nota_fiscal.delay(str(nota.id))

    return nota
