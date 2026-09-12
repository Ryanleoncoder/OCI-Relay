"""Custo e orçamentos via Usage API."""

import datetime as dt
from types import SimpleNamespace

import oci
import pytest

from oci_relay.oci import usage as mod


def _item(valor, servico="Compute", moeda="BRL"):
    return SimpleNamespace(
        computed_amount=valor, currency=moeda, service=servico)


class FakeUsage:
    def __init__(self, itens=None, erro=None):
        self.detalhes = None
        self._itens = itens if itens is not None else []
        self._erro = erro

    def request_summarized_usages(self, request_summarized_usages_details):
        self.detalhes = request_summarized_usages_details
        if self._erro:
            raise self._erro
        return SimpleNamespace(data=SimpleNamespace(items=self._itens))


def _usar(monkeypatch, itens=None, erro=None):
    cliente = FakeUsage(itens, erro)
    monkeypatch.setattr(mod, "get_usage_client", lambda: cliente)
    return cliente


class TestPeriodo:
    def test_intervalo_comeca_no_dia_1(self):
        inicio, fim = mod._inicio_do_mes()
        assert inicio.day == 1
        assert (inicio.hour, inicio.minute, inicio.second) == (0, 0, 0)

    def test_bordas_em_utc(self):
        """A Usage API exige meia-noite UTC nas bordas do intervalo."""
        inicio, fim = mod._inicio_do_mes()
        assert inicio.tzinfo == dt.timezone.utc
        assert fim.tzinfo == dt.timezone.utc
        assert (fim.hour, fim.minute, fim.second) == (0, 0, 0)

    def test_fim_cobre_o_dia_de_hoje(self):
        inicio, fim = mod._inicio_do_mes()
        assert fim > dt.datetime.now(dt.timezone.utc)


class TestConsulta:
    def test_parametros_enviados(self, monkeypatch):
        from oci_relay.config.settings import settings

        cliente = _usar(monkeypatch, [_item(1.0)])
        mod._consultar_custo()

        d = cliente.detalhes
        assert d.tenant_id == settings.oci_tenancy_ocid
        assert d.granularity == "MONTHLY"
        assert d.query_type == "COST"
        assert d.group_by == ["service"]

    def test_soma_os_itens(self, monkeypatch):
        _usar(monkeypatch, [_item(1.5), _item(2.25, "Storage")])
        assert mod._consultar_custo().total == 3.75

    def test_agrupa_por_servico_e_ordena(self, monkeypatch):
        _usar(monkeypatch, [
            _item(1.0, "Compute"), _item(5.0, "Storage"), _item(2.0, "Compute"),
        ])
        ranking = mod._consultar_custo().por_servico
        assert ranking == [("Storage", 5.0), ("Compute", 3.0)]

    def test_omite_servico_sem_custo(self, monkeypatch):
        """Free tier reporta muitos serviços zerados; mostrar tudo é ruído."""
        _usar(monkeypatch, [_item(0.0, "Compute"), _item(1.0, "Storage")])
        assert mod._consultar_custo().por_servico == [("Storage", 1.0)]

    def test_sem_itens_nao_quebra(self, monkeypatch):
        """Início de mês ou dados ainda não consolidados."""
        _usar(monkeypatch, [])
        custo = mod._consultar_custo()
        assert custo.total == 0.0
        assert custo.por_servico == []
        assert custo.moeda == "USD"

    def test_valor_nulo_conta_como_zero(self, monkeypatch):
        _usar(monkeypatch, [SimpleNamespace(
            computed_amount=None, currency="BRL", service="Compute")])
        assert mod._consultar_custo().total == 0.0

    def test_erro_de_servico_propaga(self, monkeypatch):
        """O handler precisa distinguir falha de custo zero."""
        erro = oci.exceptions.ServiceError(
            status=401, code="NotAuthenticated", headers={}, message="x")
        _usar(monkeypatch, erro=erro)
        with pytest.raises(oci.exceptions.ServiceError):
            mod._consultar_custo()


class TestBudgets:
    def _fake(self, registros=None, erro=None):
        class FakeBudget:
            def list_budgets(self, compartment_id):
                if erro:
                    raise erro
                return SimpleNamespace(data=registros or [])
        return FakeBudget()

    def test_converte_registros(self, monkeypatch):
        registros = [SimpleNamespace(
            display_name="teto", amount=5.0, actual_spend=1.25)]
        monkeypatch.setattr(mod, "get_budget_client",
                            lambda: self._fake(registros))
        b = mod._consultar_budgets()[0]
        assert (b.nome, b.limite, b.gasto) == ("teto", 5.0, 1.25)
        assert b.percentual == 25.0

    def test_limite_zero_nao_divide(self, monkeypatch):
        registros = [SimpleNamespace(
            display_name="x", amount=0, actual_spend=0)]
        monkeypatch.setattr(mod, "get_budget_client",
                            lambda: self._fake(registros))
        assert mod._consultar_budgets()[0].percentual is None

    def test_nenhum_budget_nao_e_erro(self, monkeypatch):
        monkeypatch.setattr(mod, "get_budget_client", lambda: self._fake([]))
        assert mod._consultar_budgets() == []

    def test_sem_permissao_degrada(self, monkeypatch):
        """Budgets são opcionais; sem acesso, /usage continua respondendo."""
        erro = oci.exceptions.ServiceError(
            status=404, code="NotAuthorizedOrNotFound", headers={}, message="x")
        monkeypatch.setattr(mod, "get_budget_client",
                            lambda: self._fake(erro=erro))
        assert mod._consultar_budgets() == []


class TestSemaforoDeCusto:
    @pytest.mark.parametrize("total,esperado", [
        (0.0, "🟢"),
        (0.09, "🟢"),
        (0.10, "🟡"),
        (0.99, "🟡"),
        (1.00, "🔴"),
        (50.0, "🔴"),
    ])
    def test_limiares_do_env(self, total, esperado):
        from oci_relay.channels.telegram.handlers.usage import _emoji_custo
        assert _emoji_custo(total) == esperado


class TestFormatacaoDeMoeda:
    def test_valor_pequeno_mantem_precisao(self):
        """Arredondar 0.0012 para 0.00 esconderia cobrança recém-iniciada."""
        from oci_relay.channels.telegram.handlers.usage import _moeda
        assert _moeda(0.0012, "BRL") == "BRL 0.0012"

    def test_valor_normal_usa_duas_casas(self):
        from oci_relay.channels.telegram.handlers.usage import _moeda
        assert _moeda(12.5, "BRL") == "BRL 12.50"
