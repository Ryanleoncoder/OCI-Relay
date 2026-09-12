"""Coletores locais: portas e processos."""

import socket
from types import SimpleNamespace

import psutil
import pytest

from oci_relay.security import ports as mod_ports
from oci_relay.system import health as mod_health


def _conn(ip, porta, pid, tipo=socket.SOCK_STREAM):
    return SimpleNamespace(
        status=psutil.CONN_LISTEN,
        laddr=SimpleNamespace(ip=ip, port=porta),
        type=tipo,
        pid=pid,
    )


@pytest.fixture
def sem_nomes(monkeypatch):
    """Evita consultar processos reais do sistema."""
    monkeypatch.setattr(mod_ports, "_nome_processo", lambda pid: f"proc{pid}")


class TestPortas:
    def test_dedup_de_socket_repetido(self, monkeypatch, sem_nomes):
        """O mesmo socket não pode render mais de uma entrada."""
        monkeypatch.setattr(psutil, "net_connections",
                            lambda kind: [_conn("0.0.0.0", 80, 1)] * 3)
        assert len(mod_ports.get_listening_ports()) == 1

    def test_ipv4_e_ipv6_sao_sockets_distintos(self, monkeypatch, sem_nomes):
        monkeypatch.setattr(psutil, "net_connections", lambda kind: [
            _conn("0.0.0.0", 80, 1), _conn("::", 80, 1),
        ])
        assert len(mod_ports.get_listening_ports()) == 2

    def test_agrupamento_junta_ipv4_e_ipv6(self, monkeypatch, sem_nomes):
        """O mesmo serviço nas duas famílias é uma porta só para o usuário."""
        monkeypatch.setattr(psutil, "net_connections", lambda kind: [
            _conn("0.0.0.0", 80, 1), _conn("::", 80, 1),
        ])
        agrupado = mod_ports.get_listening_ports_summary()
        assert len(agrupado) == 1
        assert sorted(agrupado[0]["addresses"]) == ["0.0.0.0", "::"]

    @pytest.mark.parametrize("ip,publico", [
        ("0.0.0.0", True),
        ("::", True),
        ("127.0.0.1", False),
        ("::1", False),
        ("192.168.0.10", False),
    ])
    def test_classificacao_publica(self, monkeypatch, sem_nomes, ip, publico):
        monkeypatch.setattr(psutil, "net_connections",
                            lambda kind: [_conn(ip, 5432, 1)])
        assert mod_ports.get_listening_ports()[0]["public"] is publico

    def test_porta_publica_contamina_o_grupo(self, monkeypatch, sem_nomes):
        """Se qualquer binding é abrangente, a porta conta como pública."""
        monkeypatch.setattr(psutil, "net_connections", lambda kind: [
            _conn("127.0.0.1", 6379, 1), _conn("0.0.0.0", 6379, 1),
        ])
        assert mod_ports.get_listening_ports_summary()[0]["public"] is True

    def test_ignora_conexoes_nao_listen(self, monkeypatch, sem_nomes):
        estabelecida = _conn("0.0.0.0", 80, 1)
        estabelecida.status = psutil.CONN_ESTABLISHED
        monkeypatch.setattr(psutil, "net_connections",
                            lambda kind: [estabelecida])
        assert mod_ports.get_listening_ports() == []

    def test_ordenado_por_porta(self, monkeypatch, sem_nomes):
        monkeypatch.setattr(psutil, "net_connections", lambda kind: [
            _conn("0.0.0.0", 443, 1), _conn("0.0.0.0", 22, 2),
            _conn("0.0.0.0", 80, 3),
        ])
        portas = [p["port"] for p in mod_ports.get_listening_ports()]
        assert portas == sorted(portas)

    def test_processo_inacessivel_nao_quebra(self, monkeypatch):
        def explode(pid):
            raise psutil.AccessDenied(pid)

        monkeypatch.setattr(psutil, "Process", explode)
        monkeypatch.setattr(psutil, "net_connections",
                            lambda kind: [_conn("0.0.0.0", 80, 999)])
        assert mod_ports.get_listening_ports()[0]["process"] == "?"


class TestIdentificacaoLimitada:
    """No Linux sem root, o dono da maioria dos sockets é inacessível."""

    def _portas(self, conhecidos, desconhecidos):
        return (
            [{"process": "nginx"} for _ in range(conhecidos)]
            + [{"process": "?"} for _ in range(desconhecidos)]
        )

    def test_maioria_desconhecida_em_posix_sem_root(self, monkeypatch):
        monkeypatch.setattr(mod_ports.os, "name", "posix")
        monkeypatch.setattr(mod_ports.os, "geteuid", lambda: 1000, raising=False)
        assert mod_ports.identificacao_limitada(self._portas(1, 5)) is True

    def test_minoria_desconhecida_nao_alerta(self, monkeypatch):
        monkeypatch.setattr(mod_ports.os, "name", "posix")
        monkeypatch.setattr(mod_ports.os, "geteuid", lambda: 1000, raising=False)
        assert mod_ports.identificacao_limitada(self._portas(5, 1)) is False

    def test_root_enxerga_tudo(self, monkeypatch):
        monkeypatch.setattr(mod_ports.os, "name", "posix")
        monkeypatch.setattr(mod_ports.os, "geteuid", lambda: 0, raising=False)
        assert mod_ports.identificacao_limitada(self._portas(0, 6)) is False

    def test_windows_nao_tem_essa_limitacao(self, monkeypatch):
        monkeypatch.setattr(mod_ports.os, "name", "nt")
        assert mod_ports.identificacao_limitada(self._portas(0, 6)) is False

    def test_lista_vazia(self, monkeypatch):
        monkeypatch.setattr(mod_ports.os, "name", "posix")
        assert mod_ports.identificacao_limitada([]) is False


class TestTopProcessos:
    def test_cpu_normalizado_por_nucleo(self, monkeypatch):
        """Sem a leitura de baseline, cpu_percent() devolve o acumulado
        desde o boot — valor sem relação com o uso atual."""

        class FakeProc:
            def __init__(self, pid, cpu):
                self.pid = pid
                self._cpu = cpu
                self._chamadas = 0

            def cpu_percent(self):
                self._chamadas += 1
                # A primeira leitura apenas estabelece a linha de base.
                return 0.0 if self._chamadas == 1 else self._cpu

            def name(self):
                return f"p{self.pid}"

            def memory_percent(self):
                return 1.0

        procs = [FakeProc(1, 400.0), FakeProc(2, 100.0)]
        monkeypatch.setattr(psutil, "process_iter", lambda attrs: procs)
        monkeypatch.setattr(psutil, "cpu_count", lambda: 4)
        monkeypatch.setattr(mod_health.time, "sleep", lambda s: None)

        top = mod_health.get_top_processes(limite=5)
        # 400% somados em 4 núcleos = 100% do sistema.
        assert top[0]["cpu_percent"] == 100.0
        assert top[1]["cpu_percent"] == 25.0

    def test_ordenacao_por_memoria(self, monkeypatch):
        amostra = [
            {"pid": 1, "name": "a", "cpu_percent": 90.0, "memory_percent": 1.0},
            {"pid": 2, "name": "b", "cpu_percent": 1.0, "memory_percent": 50.0},
        ]
        monkeypatch.setattr(mod_health, "_amostrar_processos", lambda: amostra)
        assert mod_health.get_top_processes_by_memory(2)[0]["name"] == "b"
        assert mod_health.get_top_processes(2)[0]["name"] == "a"
