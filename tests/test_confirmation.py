"""Confirmação de ações destrutivas.

Cada teste aqui corresponde a uma forma de alguém desligar uma máquina sem
ter autorizado aquilo: clique de terceiro, botão vencido, clique repetido,
confirmação inventada.
"""

import datetime as dt

import pytest

from oci_relay.safety import confirmation as mod
from oci_relay.safety.confirmation import Estado, Recusa

AUTOR = 111
OUTRO = 222
CHAT = 999


@pytest.fixture(autouse=True)
def banco_temporario(tmp_path, monkeypatch):
    """Cada teste usa um banco próprio, descartado no fim."""
    from oci_relay import state

    monkeypatch.setattr(state, "db_path", lambda: tmp_path / "teste.db")
    monkeypatch.setattr(state, "_schema_pronto", False)
    yield


def _criar(**kwargs):
    base = dict(actor_id=AUTOR, chat_id=CHAT, comando="/suspender",
                alvo="ocid1.instance.oc1..alvo")
    base.update(kwargs)
    return mod.criar(**base)


class TestCriacao:
    def test_nasce_pendente(self):
        c = _criar()
        assert c.estado is Estado.PENDENTE

    def test_nonce_e_imprevisivel(self):
        """Nonce adivinhável permitiria confirmar ação alheia."""
        nonces = {_criar().nonce for _ in range(50)}
        assert len(nonces) == 50
        assert all(len(n) >= 20 for n in nonces)

    def test_cabe_no_callback_data_do_telegram(self):
        """O limite é 64 bytes, contando o prefixo da ação."""
        c = _criar()
        assert len(f"confirmar:{c.nonce}".encode()) <= 64

    def test_persiste(self):
        c = _criar()
        assert mod.buscar(c.nonce).comando == "/suspender"

    def test_guarda_o_alvo(self):
        """A aprovação vale para aquela máquina, não para qualquer uma."""
        c = _criar(alvo="ocid1.instance.oc1..especifica")
        assert mod.buscar(c.nonce).alvo == "ocid1.instance.oc1..especifica"


class TestAutorizacao:
    def test_autor_confirma(self):
        c = _criar()
        resolvida, recusa = mod.confirmar(c.nonce, AUTOR)
        assert recusa is None
        assert resolvida.estado is Estado.CONFIRMADA

    def test_terceiro_nao_confirma(self):
        """Num grupo, ninguém aprova a ação de outra pessoa."""
        c = _criar()
        _, recusa = mod.confirmar(c.nonce, OUTRO)
        assert recusa is Recusa.OUTRO_ATOR
        assert mod.buscar(c.nonce).estado is Estado.PENDENTE

    def test_terceiro_nao_cancela(self):
        """Cancelar alheio também é interferir na ação de outro."""
        c = _criar()
        _, recusa = mod.cancelar(c.nonce, OUTRO)
        assert recusa is Recusa.OUTRO_ATOR
        assert mod.buscar(c.nonce).estado is Estado.PENDENTE


class TestExpiracao:
    def _vencer(self, monkeypatch, segundos=120):
        futuro = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=segundos)
        monkeypatch.setattr(mod, "_agora", lambda: futuro)

    def test_vencida_nao_confirma(self, monkeypatch):
        """Botão esquecido na conversa não desliga a máquina depois."""
        c = _criar(ttl_segundos=60)
        self._vencer(monkeypatch)
        _, recusa = mod.confirmar(c.nonce, AUTOR)
        assert recusa is Recusa.EXPIRADA

    def test_vencida_fica_marcada(self, monkeypatch):
        c = _criar(ttl_segundos=60)
        self._vencer(monkeypatch)
        mod.confirmar(c.nonce, AUTOR)
        assert mod.buscar(c.nonce).estado is Estado.EXPIRADA

    def test_dentro_do_prazo_passa(self, monkeypatch):
        c = _criar(ttl_segundos=60)
        self._vencer(monkeypatch, segundos=30)
        _, recusa = mod.confirmar(c.nonce, AUTOR)
        assert recusa is None

    def test_varredura_marca_vencidas(self, monkeypatch):
        _criar(ttl_segundos=10)
        _criar(ttl_segundos=10)
        viva = _criar(ttl_segundos=3600)
        self._vencer(monkeypatch, segundos=60)

        assert mod.expirar_vencidas() == 2
        assert mod.buscar(viva.nonce).estado is Estado.PENDENTE

    def test_ttl_padrao_e_curto(self):
        """TTL longo transforma o botão em bomba-relógio."""
        assert 30 <= mod.TTL_PADRAO_SEGUNDOS <= 120


class TestUsoUnico:
    def test_confirmar_duas_vezes_nao_repete(self):
        """Clique duplo não pode executar a ação duas vezes."""
        c = _criar()
        _, primeira = mod.confirmar(c.nonce, AUTOR)
        _, segunda = mod.confirmar(c.nonce, AUTOR)
        assert primeira is None
        assert segunda is Recusa.JA_RESOLVIDA

    def test_confirmar_apos_cancelar(self):
        c = _criar()
        mod.cancelar(c.nonce, AUTOR)
        _, recusa = mod.confirmar(c.nonce, AUTOR)
        assert recusa is Recusa.JA_RESOLVIDA
        assert mod.buscar(c.nonce).estado is Estado.CANCELADA

    def test_cancelar_apos_confirmar(self):
        c = _criar()
        mod.confirmar(c.nonce, AUTOR)
        _, recusa = mod.cancelar(c.nonce, AUTOR)
        assert recusa is Recusa.JA_RESOLVIDA
        assert mod.buscar(c.nonce).estado is Estado.CONFIRMADA

    def test_nonce_executado_nao_volta(self):
        c = _criar()
        mod.confirmar(c.nonce, AUTOR)
        mod.marcar_resultado(c.nonce, sucesso=True)
        _, recusa = mod.confirmar(c.nonce, AUTOR)
        assert recusa is Recusa.JA_RESOLVIDA


class TestNonceInvalido:
    def test_inexistente(self):
        confirmacao, recusa = mod.confirmar("inventado", AUTOR)
        assert confirmacao is None
        assert recusa is Recusa.DESCONHECIDA

    def test_vazio(self):
        _, recusa = mod.confirmar("", AUTOR)
        assert recusa is Recusa.DESCONHECIDA


class TestResultado:
    def test_sucesso(self):
        c = _criar()
        mod.confirmar(c.nonce, AUTOR)
        mod.marcar_resultado(c.nonce, sucesso=True)
        assert mod.buscar(c.nonce).estado is Estado.EXECUTADA

    def test_falha(self):
        c = _criar()
        mod.confirmar(c.nonce, AUTOR)
        mod.marcar_resultado(c.nonce, sucesso=False)
        assert mod.buscar(c.nonce).estado is Estado.FALHOU


class TestPersistencia:
    def test_sobrevive_a_reinicio(self, monkeypatch):
        """Reiniciar o bot não pode perder nem ressuscitar confirmações."""
        from oci_relay import state

        c = _criar()
        mod.confirmar(c.nonce, AUTOR)

        # Simula processo novo: schema reavaliado, nada em memória.
        monkeypatch.setattr(state, "_schema_pronto", False)

        assert mod.buscar(c.nonce).estado is Estado.CONFIRMADA
        _, recusa = mod.confirmar(c.nonce, AUTOR)
        assert recusa is Recusa.JA_RESOLVIDA


class TestTempoRestante:
    def test_conta_regressiva(self):
        c = _criar(ttl_segundos=90)
        assert 80 <= c.segundos_restantes <= 90

    def test_nunca_negativo(self, monkeypatch):
        c = _criar(ttl_segundos=10)
        futuro = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)
        monkeypatch.setattr(mod, "_agora", lambda: futuro)
        assert c.segundos_restantes == 0
