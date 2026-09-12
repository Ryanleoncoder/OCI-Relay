"""Consulta ao systemd."""

import subprocess
from types import SimpleNamespace

import pytest

from oci_relay.system import services as mod

LIST_UNITS = """\
ssh.service          loaded active running OpenBSD Secure Shell server
docker.service       loaded active running Docker Application Container Engine
nginx.service        loaded active running A high performance web server
"""


def _fake_run(saida="", monkeypatch=None):
    chamadas = []

    def run(args, **kwargs):
        chamadas.append(args)
        return SimpleNamespace(stdout=saida, stderr="", returncode=0)

    monkeypatch.setattr(subprocess, "run", run)
    return chamadas


class TestChamadaSegura:
    def test_nunca_usa_shell(self, monkeypatch):
        """shell=True com nome de unidade permitiria injeção de comando."""
        capturado = {}

        def run(args, **kwargs):
            capturado["args"] = args
            capturado["kwargs"] = kwargs
            return SimpleNamespace(stdout="active", stderr="", returncode=0)

        monkeypatch.setattr(subprocess, "run", run)
        mod.is_active("ssh")

        assert capturado["kwargs"].get("shell") is not True
        assert isinstance(capturado["args"], list)
        assert capturado["args"][0] == "systemctl"

    def test_tem_timeout(self, monkeypatch):
        """Sem timeout, um systemctl travado pendura o handler."""
        capturado = {}

        def run(args, **kwargs):
            capturado.update(kwargs)
            return SimpleNamespace(stdout="", stderr="", returncode=0)

        monkeypatch.setattr(subprocess, "run", run)
        mod.failed_units()
        assert capturado.get("timeout")

    def test_sem_systemd_levanta_excecao_propria(self, monkeypatch):
        def run(args, **kwargs):
            raise FileNotFoundError("systemctl")

        monkeypatch.setattr(subprocess, "run", run)
        with pytest.raises(mod.SystemdIndisponivel):
            mod.is_active("ssh")


class TestIsActive:
    @pytest.mark.parametrize("saida,esperado", [
        ("active\n", "active"),
        ("inactive\n", "inactive"),
        ("failed\n", "failed"),
        ("", "unknown"),
    ])
    def test_estados(self, monkeypatch, saida, esperado):
        _fake_run(saida, monkeypatch)
        assert mod.is_active("ssh") == esperado


class TestListagens:
    def test_running_remove_sufixo_service(self, monkeypatch):
        _fake_run(LIST_UNITS, monkeypatch)
        assert mod.running_services() == ["docker", "nginx", "ssh"]

    def test_running_vem_ordenado(self, monkeypatch):
        _fake_run(LIST_UNITS, monkeypatch)
        nomes = mod.running_services()
        assert nomes == sorted(nomes)

    def test_lista_vazia(self, monkeypatch):
        _fake_run("", monkeypatch)
        assert mod.running_services() == []
        assert mod.failed_units() == []

    def test_ignora_marcador_de_falha(self, monkeypatch):
        """systemctl prefixa unidades com falha usando '●'."""
        _fake_run("● travado.service loaded failed failed Algo\n", monkeypatch)
        assert mod.failed_units() == []

    def test_failed_preserva_sufixo(self, monkeypatch):
        _fake_run("quebrado.service loaded failed failed X\n", monkeypatch)
        assert mod.failed_units() == ["quebrado.service"]


class TestPanorama:
    def test_consulta_os_criticos_configurados(self, monkeypatch):
        chamadas = _fake_run("active\n", monkeypatch)
        mod.get_services_status(("ssh", "nginx"))

        consultados = [
            a[2] for a in chamadas if len(a) > 2 and a[1] == "is-active"
        ]
        assert consultados == ["ssh", "nginx"]

    def test_estrutura_do_retorno(self, monkeypatch):
        _fake_run("active\n", monkeypatch)
        dados = mod.get_services_status(("ssh",))
        assert set(dados) == {"criticos", "failed", "running"}
