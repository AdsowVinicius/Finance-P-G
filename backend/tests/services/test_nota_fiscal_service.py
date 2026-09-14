from app.services.nota_fiscal_service import extrair_chave_acesso


class TestExtrairChaveAcesso:
    def test_chave_sem_separadores(self) -> None:
        texto = "Texto antes " + "1" * 44 + " texto depois"
        assert extrair_chave_acesso(texto) == "1" * 44

    def test_chave_em_grupos_de_4_com_espaco_como_no_danfe(self) -> None:
        grupos = ["3526", "0912", "3456", "7890", "0001", "5500", "1000", "0012", "3456", "7891", "2345"]
        texto = f"Chave de acesso: {' '.join(grupos)}"
        assert extrair_chave_acesso(texto) == "".join(grupos)

    def test_chave_ausente_retorna_none(self) -> None:
        texto = "DANFE sem chave legível, PDF escaneado"
        assert extrair_chave_acesso(texto) is None

    def test_sequencia_de_digitos_menor_que_44_nao_e_aceita(self) -> None:
        texto = "CNPJ: 12.345.678/0001-90"
        assert extrair_chave_acesso(texto) is None

    def test_pega_a_primeira_ocorrencia_valida(self) -> None:
        chave_1 = "1" * 44
        chave_2 = "2" * 44
        texto = f"{chave_1} ... mais adiante ... {chave_2}"
        assert extrair_chave_acesso(texto) == chave_1
