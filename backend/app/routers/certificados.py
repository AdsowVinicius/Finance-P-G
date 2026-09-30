import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import settings
from app.core.dependencies import get_current_user, require_admin, require_write_access
from app.database import get_db
from app.models.certificado_digital import CertificadoDigital
from app.models.nfe_sefaz_recebida import NfeSefazRecebida
from app.models.nota_fiscal import NotaFiscal
from app.models.usuario import Usuario
from app.schemas.integracoes import CertificadoRead, CertificadoStatus, EnfileiradoRead, NfeSefazRecebidaRead
from app.services import auditoria_service, certificado_service
from app.workers.tasks import sincronizar_dfe

router = APIRouter(prefix="/certificados", tags=["certificado A1 / SEFAZ"], dependencies=[Depends(get_current_user)])

_TAMANHO_MAXIMO_PFX = 512 * 1024


@router.get("/status", response_model=CertificadoStatus)
def status_certificado(db: Session = Depends(get_db)) -> CertificadoStatus:
    cert = certificado_service.obter_ativo(db)
    return CertificadoStatus(
        criptografia_configurada=bool(settings.cert_encryption_key),
        ambiente=settings.sefaz_ambiente,
        certificado=CertificadoRead.model_validate(cert) if cert else None,
        dias_para_vencer=certificado_service.dias_para_vencer(cert) if cert else None,
        vencendo_em_breve=certificado_service.vencendo_em_breve(cert) if cert else False,
    )


@router.get("", response_model=list[CertificadoRead])
def listar_certificados(db: Session = Depends(get_db)) -> list[CertificadoDigital]:
    return db.query(CertificadoDigital).order_by(CertificadoDigital.created_at.desc()).all()


@router.post("", response_model=CertificadoRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_admin)])
async def cadastrar_certificado(
    arquivo: UploadFile = File(...),
    senha: str = Form(...),
    uf_autor: int = Form(35),
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
) -> CertificadoDigital:
    if not settings.cert_encryption_key:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail="CERT_ENCRYPTION_KEY não configurada no servidor"
        )
    pfx = await arquivo.read(_TAMANHO_MAXIMO_PFX + 1)
    resultado = certificado_service.cadastrar(db, pfx=pfx, senha=senha, criado_por=usuario_atual.id, uf_autor=uf_autor)
    if not resultado.ok:
        codigo = status.HTTP_409_CONFLICT if resultado.codigo_erro == "duplicado" else status.HTTP_400_BAD_REQUEST
        raise HTTPException(codigo, detail=resultado.erro)

    cert = resultado.certificado
    # auditoria sem o material cifrado
    auditoria_service.registrar_criacao(
        db, usuario_atual.id, "certificados_digitais", cert, excluir={"arquivo_cifrado", "senha_cifrada"}
    )
    db.commit()
    db.refresh(cert)
    return cert


@router.post("/{certificado_id}/desativar", response_model=CertificadoRead, dependencies=[Depends(require_admin)])
def desativar_certificado(
    certificado_id: uuid.UUID, db: Session = Depends(get_db), usuario_atual: Usuario = Depends(get_current_user)
) -> CertificadoDigital:
    cert = db.get(CertificadoDigital, certificado_id)
    if cert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Certificado não encontrado")
    excluir = {"arquivo_cifrado", "senha_cifrada"}
    antes = auditoria_service.snapshot(cert, excluir)
    cert.ativo = False
    auditoria_service.registrar_edicao(db, usuario_atual.id, "certificados_digitais", antes, cert, excluir)
    db.commit()
    db.refresh(cert)
    return cert


@router.post("/sincronizar", response_model=EnfileiradoRead, status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_write_access)])
def sincronizar_notas_sefaz(db: Session = Depends(get_db)) -> EnfileiradoRead:
    if certificado_service.obter_ativo(db) is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Nenhum certificado A1 ativo")
    sincronizar_dfe.delay()
    return EnfileiradoRead(mensagem="Sincronização com a SEFAZ enfileirada")


@router.get("/nfes-recebidas", response_model=list[NfeSefazRecebidaRead])
def listar_nfes_recebidas(limite: int = 200, db: Session = Depends(get_db)) -> list[NfeSefazRecebidaRead]:
    recebidas = (
        db.query(NfeSefazRecebida).order_by(NfeSefazRecebida.data_emissao.desc().nullslast()).limit(min(limite, 500)).all()
    )
    cadastradas = {
        chave
        for (chave,) in db.query(NotaFiscal.chave_acesso).filter(
            NotaFiscal.chave_acesso.in_([r.chave_acesso for r in recebidas])
        )
    }
    return [
        NfeSefazRecebidaRead.model_validate(r).model_copy(update={"nota_cadastrada": r.chave_acesso in cadastradas})
        for r in recebidas
    ]
