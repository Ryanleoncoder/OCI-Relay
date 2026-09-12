"""Cálculo de CPU de um container.

O Docker entrega contadores acumulados. Sem uma amostra anterior válida
não existe delta, e tomar o acumulado como consumo instantâneo produziria
um número errado com cara de certo.
"""

import pytest

from oci_relay.channels.telegram.handlers.container import _percentual_cpu


def _stats(usado_antes, usado_agora, sistema_antes, sistema_agora, nucleos=4):
    return {
        "cpu_stats": {
            "cpu_usage": {"total_usage": usado_agora},
            "system_cpu_usage": sistema_agora,
            "online_cpus": nucleos,
        },
        "precpu_stats": {
            "cpu_usage": {"total_usage": usado_antes},
            "system_cpu_usage": sistema_antes,
        },
    }


class TestCalculo:
    def test_metade_de_um_nucleo_em_quatro(self):
        # 50 de 400 unidades de sistema, com 4 núcleos = 50%.
        assert _percentual_cpu(_stats(0 + 100, 150, 1000, 1400)) == 50.0

    def test_container_ocioso(self):
        assert _percentual_cpu(_stats(100, 100, 1000, 1400)) == 0.0


class TestAmostraInvalida:
    def test_amostra_anterior_zerada(self):
        """Caso comum em leitura sem streaming."""
        assert _percentual_cpu(_stats(0, 500, 0, 1000)) is None

    def test_sistema_anterior_ausente(self):
        stats = _stats(100, 200, 1000, 2000)
        del stats["precpu_stats"]["system_cpu_usage"]
        assert _percentual_cpu(stats) is None

    def test_sistema_sem_avanco(self):
        assert _percentual_cpu(_stats(100, 200, 1000, 1000)) is None

    def test_contador_retrocede(self):
        """Reinício do container zera o acumulado."""
        assert _percentual_cpu(_stats(500, 100, 1000, 2000)) is None

    @pytest.mark.parametrize("stats", [{}, {"cpu_stats": {}}, {"precpu_stats": {}}])
    def test_resposta_incompleta(self, stats):
        assert _percentual_cpu(stats) is None
