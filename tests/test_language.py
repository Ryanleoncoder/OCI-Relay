"""Seleção de idioma.

A escolha explícita vence a detecção automática, e ambas caem no padrão
quando não há catálogo — um código desconhecido não pode deixar o bot mudo.
"""

import asyncio

import pytest

from oci_relay import i18n
from oci_relay.channels.telegram import adapter
from oci_relay.channels.telegram.handlers import language

CHAT = 111


@pytest.fixture(autouse=True)
def ambiente(tmp_path, monkeypatch):
    from oci_relay import state

    monkeypatch.setattr(state, "db_path", lambda: tmp_path / "teste.db")
    monkeypatch.setattr(state, "_schema_pronto", False)
    i18n.definir_idioma(i18n.IDIOMA_PADRAO)
    yield
    i18n.definir_idioma(i18n.IDIOMA_PADRAO)


@pytest.fixture
def enviadas(monkeypatch):
    capturadas = []

    async def envio(client, token, chat_id, texto):
        capturadas.append(texto)

    monkeypatch.setattr(adapter, "tg_send_text", envio)
    return capturadas


class TestResolucaoDeCodigo:
    @pytest.mark.parametrize("codigo,esperado", [
        ("en", "en"),
        ("EN", "en"),
        ("pt-br", "pt_BR"),
        ("pt_BR", "pt_BR"),
        ("PT-BR", "pt_BR"),
    ])
    def test_codigos_conhecidos(self, codigo, esperado):
        assert i18n.resolver(codigo) == esperado

    def test_variante_regional_cai_no_idioma_base(self):
        """`pt-pt` não tem catálogo próprio, mas `pt` identifica a família."""
        assert i18n.resolver("pt-pt") == "pt_BR"

    @pytest.mark.parametrize("codigo", [None, "", "  ", "xx", "klingon"])
    def test_sem_catalogo_devolve_none(self, codigo):
        """Quem chama decide o fallback; resolver não inventa idioma."""
        assert i18n.resolver(codigo) is None


class TestPrecedencia:
    def _aplicar(self, codigo_cliente=None, chat=CHAT):
        """Resolve e lê o idioma dentro do mesmo contexto assíncrono.

        Ler de fora daria o valor do contexto do chamador, e não o que o
        handler enxergaria — que foi justamente onde o idioma se perdia.
        """
        async def executar():
            gerente = adapter.TelegramBotManager()
            await gerente._aplicar_idioma(chat, codigo_cliente)
            return i18n.idioma_atual()

        return asyncio.run(executar())

    def test_sem_nada_fica_no_padrao(self):
        assert self._aplicar() == i18n.IDIOMA_PADRAO

    def test_idioma_do_cliente_e_adotado(self):
        assert self._aplicar("pt-br") == "pt_BR"

    def test_escolha_explicita_vence_o_cliente(self):
        from oci_relay.state import set_preferencia

        set_preferencia(CHAT, "idioma", "en")
        assert self._aplicar("pt-br") == "en"

    def test_cliente_desconhecido_cai_no_padrao(self):
        assert self._aplicar("klingon") == i18n.IDIOMA_PADRAO

    def test_idioma_anterior_nao_contamina(self):
        """Sem catálogo para o cliente, o padrão é aplicado, não herdado.

        Uma conversa em português antes não pode fazer um usuário de idioma
        não catalogado receber português.
        """
        assert self._aplicar("pt-br") == "pt_BR"
        assert self._aplicar("es-419") == i18n.IDIOMA_PADRAO

    def test_preferencia_de_uma_conversa_nao_vaza_para_outra(self):
        from oci_relay.state import set_preferencia

        set_preferencia(CHAT, "idioma", "pt_BR")
        assert self._aplicar() == "pt_BR"
        assert self._aplicar(chat=CHAT + 1) == i18n.IDIOMA_PADRAO


class TestComando:
    def _rodar(self, args=""):
        asyncio.run(language.handle(None, "t", CHAT, actor_id=1, args=args))

    def test_sem_argumento_lista_os_idiomas(self, enviadas):
        self._rodar()
        texto = enviadas[0]
        for codigo in i18n.idiomas_disponiveis():
            assert codigo in texto

    def test_troca_e_persiste(self, enviadas):
        from oci_relay.state import get_preferencia

        self._rodar("pt_BR")
        assert get_preferencia(CHAT, "idioma") == "pt_BR"

    def test_confirmacao_sai_no_idioma_novo(self, enviadas):
        """A própria resposta é a prova de que a troca pegou."""
        self._rodar("pt_BR")
        assert "Idioma alterado" in enviadas[0]

    def test_idioma_invalido_nao_troca(self, enviadas):
        from oci_relay.state import get_preferencia

        self._rodar("klingon")
        assert get_preferencia(CHAT, "idioma") is None
        assert "klingon" in enviadas[0]

    def test_espacos_sao_ignorados(self, enviadas):
        from oci_relay.state import get_preferencia

        self._rodar("  pt_BR  ")
        assert get_preferencia(CHAT, "idioma") == "pt_BR"


class TestPropagacao:
    """A troca precisa alcançar o handler, não só a função que a aplica.

    `definir_idioma` chamado dentro de `asyncio.to_thread` grava numa cópia
    do contexto: o valor se perde na volta, e o comando seguinte responde
    no idioma anterior.
    """

    def test_idioma_alcanca_quem_roda_depois(self):
        from oci_relay.state import set_preferencia

        set_preferencia(CHAT, "idioma", "pt_BR")

        async def fluxo():
            gerente = adapter.TelegramBotManager()
            await gerente._aplicar_idioma(CHAT, "en")
            # O que um handler veria ao formatar a resposta.
            return i18n.t("confirmation.confirm")

        assert asyncio.run(fluxo()) == "✅ Confirmar"


class TestIsolamentoEntreConversas:
    def test_idioma_nao_vaza_entre_tarefas(self):
        """Duas conversas em idiomas distintos não podem se sobrepor."""
        async def conversa(idioma, chave):
            i18n.definir_idioma(idioma)
            await asyncio.sleep(0)  # cede a vez para a outra tarefa
            return i18n.t(chave)

        async def ambas():
            return await asyncio.gather(
                conversa("en", "confirmation.confirm"),
                conversa("pt_BR", "confirmation.confirm"),
            )

        ingles, portugues = asyncio.run(ambas())
        assert ingles == "✅ Confirm"
        assert portugues == "✅ Confirmar"
