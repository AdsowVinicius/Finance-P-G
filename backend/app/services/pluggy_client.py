"""Cliente da API da Pluggy (agregador de Open Finance).

Fluxo:
  1. POST /auth {clientId, clientSecret} -> apiKey (vale ~2h, cacheada aqui)
  2. POST /connect_token -> accessToken de curta duração, que o FRONTEND usa
     pra abrir o Pluggy Connect (widget onde o usuário escolhe o banco e
     dá o consentimento — credenciais do banco nunca passam por aqui);
  3. O widget devolve um `itemId`; com ele: GET /accounts?itemId=,
     GET /transactions?accountId=&from=&to= (paginado).

Só transações POSTED entram: as PENDING podem mudar de id/valor e
duplicariam depois.
"""

import time
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import httpx

from app.config import settings
from app.models.enums import TipoLancamentoExtrato
from app.services.extrato_parser_service import LancamentoExtratoDTO

_VALIDADE_API_KEY_SEGUNDOS = 100 * 60  # a Pluggy emite por 2h; renova antes


class PluggyError(Exception):
    pass


class PluggyNaoConfigurado(PluggyError):
    pass


class PluggyClient:
    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        base_url: str | None = None,
        timeout: float = 30.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.client_id = client_id if client_id is not None else settings.pluggy_client_id
        self.client_secret = client_secret if client_secret is not None else settings.pluggy_client_secret
        self.base_url = (base_url or settings.pluggy_base_url).rstrip("/")
        self._http = http_client or httpx.Client(timeout=timeout)
        self._api_key: str | None = None
        self._api_key_expira_em: float = 0.0

    @property
    def configurado(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def _chave(self) -> str:
        if not self.configurado:
            raise PluggyNaoConfigurado("PLUGGY_CLIENT_ID/PLUGGY_CLIENT_SECRET não configurados")
        if self._api_key is None or time.monotonic() >= self._api_key_expira_em:
            corpo = self._chamar("POST", "/auth", json={"clientId": self.client_id, "clientSecret": self.client_secret}, auth=False)
            self._api_key = corpo["apiKey"]
            self._api_key_expira_em = time.monotonic() + _VALIDADE_API_KEY_SEGUNDOS
        return self._api_key

    def _chamar(self, metodo: str, caminho: str, *, auth: bool = True, **kwargs) -> dict:
        headers = {"X-API-KEY": self._chave()} if auth else {}
        try:
            resp = self._http.request(metodo, f"{self.base_url}{caminho}", headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            raise PluggyError(f"falha de rede ao falar com a Pluggy: {exc}") from exc
        if resp.status_code in (401, 403):
            self._api_key = None
            raise PluggyError("credenciais da Pluggy inválidas ou sem permissão")
        if resp.status_code == 404:
            raise PluggyError(f"recurso não encontrado na Pluggy: {caminho}")
        if resp.status_code >= 400:
            raise PluggyError(f"Pluggy respondeu HTTP {resp.status_code}: {resp.text[:200]}")
        return resp.json()

    def criar_connect_token(self, client_user_id: str, item_id: str | None = None) -> str:
        corpo: dict = {"options": {"clientUserId": client_user_id}}
        if item_id:
            corpo["itemId"] = item_id  # reconectar/atualizar um item existente
        return self._chamar("POST", "/connect_token", json=corpo)["accessToken"]

    def obter_item(self, item_id: str) -> dict:
        return self._chamar("GET", f"/items/{item_id}")

    def listar_contas(self, item_id: str) -> list[dict]:
        return self._chamar("GET", "/accounts", params={"itemId": item_id}).get("results", [])

    def listar_transacoes(self, conta_id: str, desde: date, ate: date) -> list[LancamentoExtratoDTO]:
        dtos: list[LancamentoExtratoDTO] = []
        pagina = 1
        while True:
            corpo = self._chamar(
                "GET",
                "/transactions",
                params={"accountId": conta_id, "from": desde.isoformat(), "to": ate.isoformat(), "pageSize": 500, "page": pagina},
            )
            for bruto in corpo.get("results", []):
                dto = _transacao_para_dto(bruto)
                if dto is not None:
                    dtos.append(dto)
            if pagina >= corpo.get("totalPages", 1):
                return dtos
            pagina += 1


def _transacao_para_dto(bruto: dict) -> LancamentoExtratoDTO | None:
    if bruto.get("status", "POSTED") != "POSTED":
        return None
    try:
        valor = Decimal(str(bruto["amount"]))
        data = datetime.fromisoformat(str(bruto["date"]).replace("Z", "+00:00")).date()
        fitid = str(bruto["id"])
    except (KeyError, InvalidOperation, ValueError):
        return None

    tipo_pluggy = bruto.get("type")
    if tipo_pluggy in ("CREDIT", "DEBIT"):
        tipo = TipoLancamentoExtrato.credito if tipo_pluggy == "CREDIT" else TipoLancamentoExtrato.debito
    else:
        tipo = TipoLancamentoExtrato.credito if valor >= 0 else TipoLancamentoExtrato.debito

    return LancamentoExtratoDTO(
        data=data,
        descricao=(bruto.get("description") or bruto.get("descriptionRaw") or "").strip(),
        valor=abs(valor),
        tipo=tipo,
        fitid=fitid,
    )
