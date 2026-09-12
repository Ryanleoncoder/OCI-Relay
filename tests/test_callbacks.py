"""Cliques nos botões de confirmação.

O caminho do callback tem as mesmas exigências do caminho das mensagens:
allowlist, autoria e uso único. Um botão é só outra forma de mandar um
comando, e precisa ser tratado como tal.
"""

import asyncio

import pytest

from oci_relay.channels.telegram import adapter
from oci_relay.i18n import t as msg
from oci_relay.safety import confirmation as conf
from oci_relay.safety.confirmation import Estado

AUTOR = 111
OUTRO = 222
CHAT = 111
MSG_ID = 55


@pytest.fixture(autouse=True)
def banco_temporario(tmp_path, monkeypatch):
    from oci_relay import state

    monkeypatch.setattr(state, "db_path", lambda: tmp_path / "teste.db")
    monkeypatch.setattr(state, "_schema_pronto", False)


@pytest.fixture
def telegram(monkeypatch):
    """Captura as chamadas que iriam para o Telegram."""
    registro = {"answers": [], "edits": [], "sends": []}

    async def answer(client, token, callback_id, texto=""):
        registro["answers"].append(texto)

    async def edit(client, token, chat_id, message_id, texto):
        registro["edits"].append(texto)

    async def send(client, token, chat_id, texto):
        registro["sends"].append(texto)

    monkeypatch.setattr(adapter, "tg_answer_callback", answer)
    monkeypatch.setattr(adapter, "tg_edit_message", edit)
    monkeypatch.setattr(adapter, "tg_send_text", send)
    monkeypatch.setattr(adapter, "_executores", dict)
    return registro


def _callback(nonce, acao="ok", from_id=AUTOR):
    return {
        "id": "cb1",
        "from": {"id": from_id},
        "data": f"{acao}:{nonce}",
        "message": {"message_id": MSG_ID, "chat": {"id": CHAT}},
    }


def _pendente():
    return conf.criar(actor_id=AUTOR, chat_id=CHAT, comando="/suspender",
                      alvo="ocid1.instance.oc1..alvo")


def _processar(callback, monkeypatch, permitidos=(AUTOR,)):
    from oci_relay.config.settings import settings

    monkeypatch.setattr(settings, "telegram_allowed_ids", list(permitidos))
    gerente = adapter.TelegramBotManager()
    asyncio.run(gerente._handle_callback("token", None, callback))


class TestAutorizacao:
    def test_fora_da_allowlist_nao_resolve(self, telegram, monkeypatch):
        c = _pendente()
        _processar(_callback(c.nonce, from_id=999), monkeypatch)

        assert conf.buscar(c.nonce).estado is Estado.PENDENTE
        assert msg("confirmation.unauthorised") in telegram["answers"]

    def test_chat_autorizado_nao_autoriza_o_membro(self, telegram, monkeypatch):
        """Num grupo permitido, a allowlist do chat não vale para o clique.

        Botão decide ação destrutiva: o que conta é quem clicou.
        """
        c = _pendente()
        # A allowlist contém o chat, mas não quem está clicando.
        _processar(_callback(c.nonce, from_id=999), monkeypatch,
                   permitidos=(CHAT,))

        assert conf.buscar(c.nonce).estado is Estado.PENDENTE
        assert msg("confirmation.unauthorised") in telegram["answers"]

    def test_autorizado_mas_nao_autor_nao_resolve(self, telegram, monkeypatch):
        """Estar na allowlist não dá direito de aprovar ação alheia."""
        c = _pendente()
        _processar(_callback(c.nonce, from_id=OUTRO), monkeypatch,
                   permitidos=(AUTOR, OUTRO))

        assert conf.buscar(c.nonce).estado is Estado.PENDENTE

    def test_recusa_de_terceiro_preserva_o_pedido(self, telegram, monkeypatch):
        """A confirmação segue disponível para quem de fato pediu."""
        c = _pendente()
        _processar(_callback(c.nonce, from_id=OUTRO), monkeypatch,
                   permitidos=(AUTOR, OUTRO))

        assert telegram["edits"] == []
        assert conf.buscar(c.nonce).estado is Estado.PENDENTE


class TestCancelamento:
    def test_cancela(self, telegram, monkeypatch):
        c = _pendente()
        _processar(_callback(c.nonce, acao="no"), monkeypatch)

        assert conf.buscar(c.nonce).estado is Estado.CANCELADA
        assert msg("confirmation.cancelled_message") in telegram["edits"]


class TestConfirmacao:
    def test_sem_executor_nao_executa(self, telegram, monkeypatch):
        """Comando sem executor registrado não pode virar ação silenciosa."""
        c = _pendente()
        _processar(_callback(c.nonce), monkeypatch)

        assert conf.buscar(c.nonce).estado is Estado.FALHOU
        assert msg("confirmation.no_executor") in telegram["edits"]

    def test_executor_recebe_a_confirmacao(self, telegram, monkeypatch):
        recebidas = []

        async def executor(confirmacao):
            recebidas.append(confirmacao)
            return "🟢 Feito."

        monkeypatch.setattr(adapter, "_executores",
                        lambda: {"/suspender": executor})
        c = _pendente()
        _processar(_callback(c.nonce), monkeypatch)

        assert len(recebidas) == 1
        assert recebidas[0].alvo == "ocid1.instance.oc1..alvo"
        assert conf.buscar(c.nonce).estado is Estado.EXECUTADA

    def test_falha_do_executor_fica_registrada(self, telegram, monkeypatch):
        async def executor(confirmacao):
            raise RuntimeError("OCI recusou")

        monkeypatch.setattr(adapter, "_executores",
                        lambda: {"/suspender": executor})
        c = _pendente()
        _processar(_callback(c.nonce), monkeypatch)

        assert conf.buscar(c.nonce).estado is Estado.FALHOU
        assert any("OCI recusou" in e for e in telegram["edits"])

    def test_clique_repetido_executa_uma_vez(self, telegram, monkeypatch):
        execucoes = []

        async def executor(confirmacao):
            execucoes.append(1)
            return "🟢 Feito."

        monkeypatch.setattr(adapter, "_executores",
                        lambda: {"/suspender": executor})
        c = _pendente()
        _processar(_callback(c.nonce), monkeypatch)
        _processar(_callback(c.nonce), monkeypatch)

        assert len(execucoes) == 1


class TestDadosInvalidos:
    @pytest.mark.parametrize("dados", ["", "ok:", "lixo", "ok", ":abc"])
    def test_callback_malformado(self, telegram, monkeypatch, dados):
        callback = _callback("x")
        callback["data"] = dados
        _processar(callback, monkeypatch)

        assert msg("confirmation.unrecognised") in telegram["answers"]

    def test_nonce_inexistente(self, telegram, monkeypatch):
        _processar(_callback("inventado"), monkeypatch)
        assert msg("confirmation.refused.desconhecida") in telegram["answers"]


class TestRespostaAoBotao:
    def test_sempre_responde_o_callback(self, telegram, monkeypatch):
        """Sem answerCallbackQuery o botão fica girando e o usuário reclica."""
        c = _pendente()
        _processar(_callback(c.nonce), monkeypatch)
        assert telegram["answers"]
