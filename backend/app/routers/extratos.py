import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_write_access
from app.core.storage import salvar_arquivo_upload
from app.database import get_db
from app.models.enums import FormatoExtrato, StatusImportacao
from app.models.extrato_importado import ExtratoImportado
from app.models.lancamento_extrato import LancamentoExtrato
from app.models.usuario import Usuario
from app.schemas.extrato import ExtratoImportadoRead, LancamentoExtratoRead
from app.workers.tasks import processar_importacao_extrato

router = APIRouter(prefix="/extratos", tags=["extrato bancário"], dependencies=[Depends(get_current_user)])

_EXTENSOES_EXTRATO = {".ofx", ".csv"}


@router.get("", response_model=list[ExtratoImportadoRead])
def listar_extratos_importados(conta_bancaria_id: uuid.UUID | None = None, db: Session = Depends(get_db)):
    query = db.query(ExtratoImportado)
    if conta_bancaria_id is not None:
        query = query.filter(ExtratoImportado.conta_bancaria_id == conta_bancaria_id)
    return query.order_by(ExtratoImportado.created_at.desc()).all()


@router.get("/{extrato_id}/lancamentos", response_model=list[LancamentoExtratoRead])
def listar_lancamentos_do_extrato(extrato_id: uuid.UUID, db: Session = Depends(get_db)):
    return (
        db.query(LancamentoExtrato)
        .filter(LancamentoExtrato.extrato_importado_id == extrato_id)
        .order_by(LancamentoExtrato.data)
        .all()
    )


@router.post(
    "",
    response_model=ExtratoImportadoRead,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_write_access)],
)
async def importar_extrato(
    arquivo: UploadFile = File(...),
    conta_bancaria_id: uuid.UUID = Form(...),
    formato: FormatoExtrato = Form(...),
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
) -> ExtratoImportado:
    conteudo = await arquivo.read()
    try:
        caminho = salvar_arquivo_upload(arquivo, "extratos", conteudo, extensoes_permitidas=_EXTENSOES_EXTRATO)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    extrato = ExtratoImportado(
        conta_bancaria_id=conta_bancaria_id,
        arquivo_original_path=caminho,
        formato=formato,
        status=StatusImportacao.processando,
        importado_por=usuario_atual.id,
    )
    db.add(extrato)
    db.commit()
    db.refresh(extrato)

    processar_importacao_extrato.delay(str(extrato.id))

    return extrato
