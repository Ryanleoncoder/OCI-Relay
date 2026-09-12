"""Métricas via OCI Monitoring."""

import datetime as dt
from types import SimpleNamespace

import oci
import pytest

from oci_relay.oci import monitoring as mod


class FakeMonitoring:
    """Captura as consultas MQL emitidas e devolve pontos fixos."""

    def __init__(self, valor=42.0, vazio=False, erro=None):
        self.consultas = []
        self._valor = valor
        self._vazio = vazio
        self._erro = erro

    def summarize_metrics_data(self, compartment_id,
                               summarize_metrics_data_details):
        self.consultas.append(summarize_metrics_data_details.query)
        if self._erro:
            raise self._erro
        if self._vazio:
            return SimpleNamespace(data=[])
        pontos = [
            SimpleNamespace(timestamp=dt.datetime(2026, 9, 12, 15, 0), value=1.0),
            SimpleNamespace(timestamp=dt.datetime(2026, 9, 12, 15, 1),
                            value=self._valor),
        ]
        return SimpleNamespace(
            data=[SimpleNamespace(aggregated_datapoints=pontos)])


@pytest.fixture
def fake(monkeypatch):
    cliente = FakeMonitoring()
    monkeypatch.setattr(mod, "get_monitoring_client", lambda: cliente)
    return cliente


class TestAgregacao:
    """mean() em contador cumulativo devolve o total desde o boot, não a
    taxa atual."""

    def test_gauges_usam_mean(self, fake):
        mod._coletar(15)
        por_metrica = {q.split("[")[0]: q for q in fake.consultas}
        assert por_metrica["CpuUtilization"].endswith(".mean()")
        assert por_metrica["MemoryUtilization"].endswith(".mean()")
        assert por_metrica["LoadAverage"].endswith(".mean()")

    def test_contadores_usam_rate(self, fake):
        mod._coletar(15)
        por_metrica = {q.split("[")[0]: q for q in fake.consultas}
        for metrica in ("DiskBytesRead", "DiskBytesWritten",
                        "NetworksBytesIn", "NetworksBytesOut"):
            assert por_metrica[metrica].endswith(".rate()"), metrica

    def test_toda_taxa_de_bytes_esta_declarada(self):
        for chave in mod.TAXAS_BYTES:
            _, agregacao = mod._METRICAS[chave]
            assert agregacao == "rate"


class TestConsulta:
    def test_filtra_pela_instancia(self, fake):
        from oci_relay.config.settings import settings

        mod._ultimo_valor("CpuUtilization", "mean")
        assert settings.oci_instance_ocid in fake.consultas[0]

    def test_usa_ponto_mais_recente(self, fake):
        assert mod._ultimo_valor("CpuUtilization", "mean") == 42.0

    def test_serie_vazia_devolve_none(self, monkeypatch):
        monkeypatch.setattr(mod, "get_monitoring_client",
                            lambda: FakeMonitoring(vazio=True))
        assert mod._ultimo_valor("CpuUtilization", "mean") is None

    def test_erro_de_servico_nao_propaga(self, monkeypatch):
        """Uma métrica indisponível não pode derrubar o painel inteiro."""
        erro = oci.exceptions.ServiceError(
            status=404, code="NotAuthorizedOrNotFound",
            headers={}, message="nao encontrado")
        monkeypatch.setattr(mod, "get_monitoring_client",
                            lambda: FakeMonitoring(erro=erro))
        assert mod._ultimo_valor("CpuUtilization", "mean") is None

    def test_coleta_devolve_todas_as_chaves(self, fake):
        assert set(mod._coletar(15)) == set(mod._METRICAS)


class TestSerie:
    @pytest.mark.asyncio
    async def test_metrica_desconhecida(self, fake):
        with pytest.raises(ValueError, match="desconhecida"):
            await mod.get_metric_series("nao_existe")

    @pytest.mark.asyncio
    async def test_devolve_pares_tempo_valor(self, fake):
        serie = await mod.get_metric_series("cpu", minutos=30)
        assert len(serie) == 2
        assert serie[-1][1] == 42.0
