import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_write_access
from app.core.storage import salvar_arquivo_upload
from app.database import get_db
from app.models.enums import StatusNota, StatusProcessamentoNota, TipoNota, TipoOperacaoNota
from app.models.nota_fiscal import NotaFiscal
from app.models.usuario import Usuario
from app.schemas.nota_fiscal import ChaveAcessoManual, NotaFiscalCompletar, NotaFiscalRead
from app.services import auditoria_service
from app.services.nota_fiscal_service import NotaFiscalService
from app.workers.tasks import processar_nota_fiscal

router = APIRouter(prefix="/notas-fiscais", tags=["notas fiscais"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[NotaFiscalRead])
def listar_notas_fiscais(
    parceiro_id: uuid.UUID | None = None,
    centro_custo_id: uuid.UUID | None = None,
    status_processamento: StatusProcessamentoNota | None = None,
    status: StatusNota | None = None,
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
    if status is not None:
        query = query.filter(NotaFiscal.status == status)
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

    resultado = NotaFiscalService().cadastrar_via_upload(
        db,
        conteudo_pdf=conteudo,
        caminho_pdf=caminho_pdf,
        centro_custo_id=centro_custo_id,
        tipo_operacao=tipo_operacao,
        tipo=tipo,
        criado_por=usuario_atual.id,
        parceiro_id=parceiro_id,
        valor_total=valor_total,
        data_emissao=data_emissao,
        numero_nota=numero_nota,
        serie=serie,
        despesa_fixa=despesa_fixa,
        despesa_parcelada=despesa_parcelada,
        numero_parcelas=numero_parcelas,
    )
    if not resultado.ok:
        codigo_http = status.HTTP_409_CONFLICT if resultado.codigo_erro == "chave_duplicada" else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=codigo_http, detail=resultado.erro)

    nota = resultado.nota
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

    duplicada = NotaFiscalService().buscar_nota_pela_chave(db, dados.chave_acesso, excluir_nota_id=nota_id)
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


@router.patch("/{nota_id}", response_model=NotaFiscalRead, dependencies=[Depends(require_write_access)])
def completar_nota_fiscal(
    nota_id: uuid.UUID,
    dados: NotaFiscalCompletar,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
) -> NotaFiscal:
    """Completa campos que faltaram na captura — sobretudo centro de custo
    (nota chegada por WhatsApp nunca tem, já que só existe no app) e,
    quando a foto/PDF não tinha chave de acesso legível, parceiro/valor/data
    reais (fica no parceiro sentinela até alguém preencher aqui). Se depois
    do update a nota tiver parceiro real e valor real e ainda não tiver
    parcela nenhuma gerada, gera a parcela à vista agora — pra nota
    parcelada, use o cadastro completo (upload manual) em vez desse atalho.
    """
    nota = db.get(NotaFiscal, nota_id)
    if nota is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nota fiscal não encontrada")

    antes = auditoria_service.snapshot(nota)
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(nota, campo, valor)

    NotaFiscalService().gerar_parcela_se_dados_completos(db, nota)

    auditoria_service.registrar_edicao(db, usuario_atual.id, "notas_fiscais", antes, nota)
    db.commit()
    db.refresh(nota)
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
