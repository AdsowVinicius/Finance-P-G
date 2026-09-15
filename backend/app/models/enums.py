import enum


class PapelUsuario(str, enum.Enum):
    financeiro = "financeiro"
    admin = "admin"
    master = "master"
    sub = "sub"


class TipoParceiro(str, enum.Enum):
    fornecedor = "fornecedor"
    cliente = "cliente"
    ambos = "ambos"


class TipoNota(str, enum.Enum):
    nfe = "nfe"
    nfse = "nfse"


class TipoOperacaoNota(str, enum.Enum):
    entrada = "entrada"
    saida = "saida"


class StatusNota(str, enum.Enum):
    pendente = "pendente"
    parcialmente_conciliada = "parcialmente_conciliada"
    conciliada = "conciliada"
    cancelada = "cancelada"


class StatusProcessamentoNota(str, enum.Enum):
    aguardando_extracao = "aguardando_extracao"
    chave_nao_encontrada = "chave_nao_encontrada"
    consultando_api = "consultando_api"
    concluido = "concluido"
    erro_api = "erro_api"


class Periodicidade(str, enum.Enum):
    mensal = "mensal"
    quinzenal = "quinzenal"
    semanal = "semanal"
    anual = "anual"
    personalizada_dias = "personalizada_dias"


class StatusConta(str, enum.Enum):
    pendente = "pendente"
    pago = "pago"
    atrasado = "atrasado"
    cancelado = "cancelado"


class FormaBaixa(str, enum.Enum):
    manual = "manual"
    conciliacao_automatica = "conciliacao_automatica"


class FormatoExtrato(str, enum.Enum):
    ofx = "ofx"
    csv = "csv"


class StatusImportacao(str, enum.Enum):
    processando = "processando"
    concluido = "concluido"
    erro = "erro"


class TipoLancamentoExtrato(str, enum.Enum):
    credito = "credito"
    debito = "debito"


class StatusConciliacaoLinha(str, enum.Enum):
    pendente = "pendente"
    conciliado = "conciliado"
    parcial = "parcial"
    divergente = "divergente"
    ignorado = "ignorado"


class TipoMatch(str, enum.Enum):
    automatico_exato = "automatico_exato"
    automatico_tolerancia = "automatico_tolerancia"
    parcial = "parcial"
    manual = "manual"


class StatusProjeto(str, enum.Enum):
    ativo = "ativo"
    concluido = "concluido"
    cancelado = "cancelado"


class StatusFuncionario(str, enum.Enum):
    ativo = "ativo"
    demitido = "demitido"


class StatusPreLancamentoWhatsapp(str, enum.Enum):
    pendente_revisao = "pendente_revisao"
    confirmado = "confirmado"
    descartado = "descartado"


class FormaPagamento(str, enum.Enum):
    pix = "pix"
    dinheiro = "dinheiro"
    cartao_credito = "cartao_credito"
    cartao_debito = "cartao_debito"
    boleto = "boleto"
    transferencia = "transferencia"
    outro = "outro"


class RegraDiaUtilCategoria(str, enum.Enum):
    """Como uma categoria de lançamento desloca a data de vencimento quando
    ela cai num fim de semana — usado só quando o lançamento tem categoria
    vinculada (ver DiaUtilCalculator.ajustar_por_categoria).
    """

    funcionario = "funcionario"  # pagamento de funcionário: sábado conta como dia útil
    bancaria = "bancaria"  # conta de banco: só seg-sex, sáb/dom empurra pra sexta anterior
