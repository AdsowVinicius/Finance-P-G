from datetime import date
from decimal import Decimal

import httpx
import pytest

from app.models.enums import TipoLancamentoExtrato
from app.services.pluggy_client import PluggyClient, PluggyError, PluggyNaoConfigurado


def _cliente(handler, **kw) -> PluggyClient:
    return PluggyClient(
        client_id="id", client_secret="segredo", base_url="https://pluggy.test", http_client=httpx.Client(transport=httpx.MockTransport(handler)), **kw
    )


def _tx(id_, amount, tipo, data="2026-09-10T00:00:00.000Z", status="POSTED", desc="PIX"):
    return {"id": id_, "amount": amount, "type": tipo, "date": data, "status": status, "description": desc}


def test_sem_credenciais_nao_esta_configurado_e_levanta():
    c = PluggyClient(client_id=None, client_secret=None)
    assert not c.configurado
    with pytest.raises(PluggyNaoConfigurado):
        c.listar_contas("item")


def test_api_key_e_cacheada_entre_chamadas():
    chamadas = {"auth": 0}

    def handler(req):
        if req.url.path == "/auth":
            chamadas["auth"] += 1
            return httpx.Response(200, json={"apiKey": "K"})
        assert req.headers["x-api-key"] == "K"
        return httpx.Response(200, json={"results": []})

    c = _cliente(handler)
    c.listar_contas("i1")
    c.listar_contas("i2")
    assert chamadas["auth"] == 1


def test_connect_token_envia_client_user_id_e_item_quando_reconectando():
    corpos = []

    def handler(req):
        if req.url.path == "/auth":
            return httpx.Response(200, json={"apiKey": "K"})
        corpos.append(req.read())
        return httpx.Response(200, json={"accessToken": "TOKEN"})

    c = _cliente(handler)
    assert c.criar_connect_token("user-1", item_id="item-9") == "TOKEN"
    assert b"user-1" in corpos[0] and b"item-9" in corpos[0]


def test_transacoes_paginadas_convertidas_para_dto():
    def handler(req):
        if req.url.path == "/auth":
            return httpx.Response(200, json={"apiKey": "K"})
        pagina = int(req.url.params["page"])
        itens = {
            1: [_tx("t1", -150.5, "DEBIT", desc="Energia"), _tx("t2", 1000, "CREDIT")],
            2: [_tx("t3", -10, "DEBIT")],
        }[pagina]
        return httpx.Response(200, json={"total": 3, "totalPages": 2, "page": pagina, "results": itens})

    dtos = _cliente(handler).listar_transacoes("acc", date(2026, 9, 1), date(2026, 9, 30))

    assert [d.fitid for d in dtos] == ["t1", "t2", "t3"]
    assert dtos[0].valor == Decimal("150.5") and dtos[0].tipo == TipoLancamentoExtrato.debito
    assert dtos[1].valor == Decimal("1000") and dtos[1].tipo == TipoLancamentoExtrato.credito
    assert dtos[0].descricao == "Energia"
    assert dtos[0].data == date(2026, 9, 10)


def test_transacao_pending_e_ignorada():
    def handler(req):
        if req.url.path == "/auth":
            return httpx.Response(200, json={"apiKey": "K"})
        return httpx.Response(200, json={"totalPages": 1, "results": [_tx("p1", -5, "DEBIT", status="PENDING")]})

    assert _cliente(handler).listar_transacoes("acc", date(2026, 9, 1), date(2026, 9, 30)) == []


def test_valor_nunca_passa_por_float():
    def handler(req):
        if req.url.path == "/auth":
            return httpx.Response(200, json={"apiKey": "K"})
        return httpx.Response(200, json={"totalPages": 1, "results": [_tx("t", 0.1, "CREDIT")]})

    (dto,) = _cliente(handler).listar_transacoes("acc", date(2026, 9, 1), date(2026, 9, 30))
    assert dto.valor == Decimal("0.1")


def test_tipo_ausente_usa_sinal_do_valor():
    def handler(req):
        if req.url.path == "/auth":
            return httpx.Response(200, json={"apiKey": "K"})
        bruto = {"id": "x", "amount": -20, "date": "2026-09-01T00:00:00Z"}
        return httpx.Response(200, json={"totalPages": 1, "results": [bruto]})

    (dto,) = _cliente(handler).listar_transacoes("acc", date(2026, 9, 1), date(2026, 9, 30))
    assert dto.tipo == TipoLancamentoExtrato.debito and dto.valor == Decimal("20")


def test_credencial_invalida_levanta_pluggy_error():
    def handler(req):
        return httpx.Response(401, json={"message": "no"})

    with pytest.raises(PluggyError, match="inválidas"):
        _cliente(handler).listar_contas("item")
