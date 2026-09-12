"""Handlers: nenhum pode estourar exceção para o loop de polling."""

import asyncio

import oci
import pytest

from oci_relay.channels.telegram import adapter
from oci_relay.channels.telegram.handlers import (
    alerts, cpu, disk, docker, fail2ban, health, memory, oci_ip, ports,
    reiniciar, security, services, sessions, status, summary, suspender,
    network, top, usage, watch,
)

TODOS = [
    ("summary", summary), ("status", status), ("health", health),
    ("cpu", cpu), ("memory", memory), ("disk", disk), ("ports", ports),
    ("docker", docker), ("services", services), ("security", security),
    ("fail2ban", fail2ban), ("oci_ip", oci_ip), ("usage", usage),
    ("network", network), ("top", top), ("sessions", sessions),
    ("watch", watch), ("alerts", alerts), ("suspender", suspender),
    ("reiniciar", reiniciar),
]

STUBS = [("sessions", sessions), ("watch", watch), ("alerts", alerts)]


@pytest.mark.parametrize("nome,mod", TODOS)
def test_handler_sempre_responde(nome, mod, enviadas, monkeypatch):
    """Mesmo sem OCI, sem Docker e sem systemd, o handler responde algo.

    Um handler que levanta exceção mataria o processamento da mensagem e o
    usuário ficaria sem resposta.
    """
    monkeypatch.setattr("oci_relay.config.settings.settings.oci_region", None)
    monkeypatch.setattr("oci_relay.config.settings.settings.oci_instance_ocid", None)

    asyncio.run(mod.handle(None, "token", 1))

    assert len(enviadas) == 1, f"{nome} não enviou resposta"
    assert enviadas[0].strip(), f"{nome} enviou mensagem vazia"


@pytest.mark.parametrize("nome,mod", TODOS)
def test_resposta_renderiza_em_html(nome, mod, enviadas, monkeypatch):
    """A conversão para HTML do Telegram não pode falhar nem deixar markdown."""
    monkeypatch.setattr("oci_relay.config.settings.settings.oci_region", None)
    monkeypatch.setattr("oci_relay.config.settings.settings.oci_instance_ocid", None)

    asyncio.run(mod.handle(None, "token", 1))
    html = adapter._markdown_to_telegram_html(enviadas[0])

    assert html.strip()
    assert "**" not in html, f"{nome} deixou negrito sem converter"
    assert "__" not in html, f"{nome} deixou itálico sem converter"
    assert "```" not in html, f"{nome} deixou bloco sem converter"


@pytest.mark.parametrize("nome,mod", STUBS)
def test_stub_se_identifica(nome, mod, enviadas):
    asyncio.run(mod.handle(None, "token", 1))
    assert "🚧" in enviadas[0]
    assert "não implementado" in enviadas[0]


class TestErrosDaOci:
    def _erro(self, status, code):
        return oci.exceptions.ServiceError(
            status=status, code=code, headers={}, message="falhou")

    def test_status_reporta_http(self, enviadas, monkeypatch):
        async def explode():
            raise self._erro(401, "NotAuthenticated")

        monkeypatch.setattr(
            "oci_relay.oci.compute.get_instance_status", explode)
        asyncio.run(status.handle(None, "token", 1))
        assert "401" in enviadas[0]

    def test_summary_degrada_mas_mostra_o_resto(self, enviadas, monkeypatch):
        """Uma falha da OCI não pode apagar o bloco local do resumo."""
        async def explode():
            raise self._erro(404, "NotAuthorizedOrNotFound")

        monkeypatch.setattr(
            "oci_relay.oci.compute.get_instance_status", explode)
        asyncio.run(summary.handle(None, "token", 1))

        texto = enviadas[0]
        assert "404" in texto
        # O bloco local sobrevive à falha da OCI.
        assert "CPU" in texto and "Disk" in texto
