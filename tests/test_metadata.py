"""Detecção de auto-hospedagem.

Se o Relay roda na mesma instância que monitora, parar essa instância mata
o bot junto e a religação passa a exigir o console da OCI. A detecção é o
que permite avisar antes de agir.
"""

from types import SimpleNamespace

import httpx
import pytest

from oci_relay.config.settings import settings
from oci_relay.oci import metadata as mod

OCID_LOCAL = "ocid1.instance.oc1.sa-saopaulo-1.local"
OCID_OUTRA = "ocid1.instance.oc1.sa-saopaulo-1.outra"


class FakeClient:
    """Substitui httpx.AsyncClient no escopo do teste."""

    def __init__(self, resposta=None, erro=None):
        self._resposta = resposta
        self._erro = erro
        self.chamadas = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, headers=None):
        self.chamadas.append((url, headers))
        if self._erro:
            raise self._erro
        return self._resposta


def _resposta(status=200, corpo=None):
    return SimpleNamespace(status_code=status, json=lambda: corpo or {})


@pytest.fixture(autouse=True)
def _limpar():
    mod.limpar_cache()
    yield
    mod.limpar_cache()


def _instalar(monkeypatch, cliente):
    monkeypatch.setattr(mod.httpx, "AsyncClient", lambda **kw: cliente)
    return cliente


class TestLeituraDosMetadados:
    async def test_devolve_o_ocid(self, monkeypatch):
        _instalar(monkeypatch, FakeClient(_resposta(200, {"id": OCID_LOCAL})))
        assert await mod.get_local_instance_id() == OCID_LOCAL

    async def test_usa_o_cabecalho_exigido_pela_v2(self, monkeypatch):
        """Sem 'Authorization: Bearer Oracle' a v2 responde 401."""
        cliente = _instalar(
            monkeypatch, FakeClient(_resposta(200, {"id": OCID_LOCAL})))
        await mod.get_local_instance_id()
        _, headers = cliente.chamadas[0]
        assert headers == {"Authorization": "Bearer Oracle"}

    async def test_fora_da_oci_devolve_none(self, monkeypatch):
        """O endereço link-local não é roteável fora de uma instância."""
        _instalar(monkeypatch, FakeClient(erro=httpx.ConnectError("sem rota")))
        assert await mod.get_local_instance_id() is None

    async def test_timeout_devolve_none(self, monkeypatch):
        _instalar(monkeypatch,
                  FakeClient(erro=httpx.ConnectTimeout("estourou")))
        assert await mod.get_local_instance_id() is None

    async def test_status_inesperado_devolve_none(self, monkeypatch):
        _instalar(monkeypatch, FakeClient(_resposta(401, {})))
        assert await mod.get_local_instance_id() is None

    async def test_json_invalido_devolve_none(self, monkeypatch):
        def explode():
            raise ValueError("nao e json")

        _instalar(monkeypatch, FakeClient(
            SimpleNamespace(status_code=200, json=explode)))
        assert await mod.get_local_instance_id() is None

    async def test_consulta_uma_vez_so(self, monkeypatch):
        """A instância não muda durante a execução do processo."""
        cliente = _instalar(
            monkeypatch, FakeClient(_resposta(200, {"id": OCID_LOCAL})))
        await mod.get_local_instance_id()
        await mod.get_local_instance_id()
        assert len(cliente.chamadas) == 1

    async def test_ausencia_tambem_e_memorizada(self, monkeypatch):
        """Fora da OCI, não adianta reconsultar a cada comando."""
        cliente = _instalar(monkeypatch,
                            FakeClient(erro=httpx.ConnectError("sem rota")))
        await mod.get_local_instance_id()
        await mod.get_local_instance_id()
        assert len(cliente.chamadas) == 1


class TestAutoHospedagem:
    async def test_mesma_instancia(self, monkeypatch):
        _instalar(monkeypatch, FakeClient(_resposta(200, {"id": OCID_LOCAL})))
        monkeypatch.setattr(settings, "oci_instance_ocid", OCID_LOCAL)
        assert await mod.rodando_na_instancia_alvo() is True

    async def test_instancia_diferente(self, monkeypatch):
        """Rodar na VPS A monitorando a VPS B mantém a ação reversível."""
        _instalar(monkeypatch, FakeClient(_resposta(200, {"id": OCID_LOCAL})))
        monkeypatch.setattr(settings, "oci_instance_ocid", OCID_OUTRA)
        assert await mod.rodando_na_instancia_alvo() is False

    async def test_fora_da_oci(self, monkeypatch):
        _instalar(monkeypatch, FakeClient(erro=httpx.ConnectError("x")))
        monkeypatch.setattr(settings, "oci_instance_ocid", OCID_LOCAL)
        assert await mod.rodando_na_instancia_alvo() is False

    async def test_sem_alvo_configurado(self, monkeypatch):
        _instalar(monkeypatch, FakeClient(_resposta(200, {"id": OCID_LOCAL})))
        monkeypatch.setattr(settings, "oci_instance_ocid", None)
        assert await mod.rodando_na_instancia_alvo() is False

    async def test_falha_assume_reversivel(self, monkeypatch):
        """Na dúvida, False — é o cenário em que parar não trava ninguém.

        O aviso extra é o que se perde; o comando em si continua seguro.
        """
        _instalar(monkeypatch, FakeClient(erro=httpx.ReadTimeout("x")))
        monkeypatch.setattr(settings, "oci_instance_ocid", OCID_LOCAL)
        assert await mod.rodando_na_instancia_alvo() is False
