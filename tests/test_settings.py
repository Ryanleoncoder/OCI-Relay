"""Configuração: parsing do ambiente e validação de OCIDs."""

import pytest

from oci_relay.config import settings as mod
from oci_relay.config.settings import get_env_bool, get_env_int, get_env_float


class TestGetEnvBool:
    """Ausência e valor vazio devem cair no default informado."""

    def test_ausente_usa_default_true(self, monkeypatch):
        monkeypatch.delenv("X_BOOL", raising=False)
        assert get_env_bool("X_BOOL", True) is True

    def test_ausente_usa_default_false(self, monkeypatch):
        monkeypatch.delenv("X_BOOL", raising=False)
        assert get_env_bool("X_BOOL", False) is False

    def test_vazio_usa_default(self, monkeypatch):
        monkeypatch.setenv("X_BOOL", "   ")
        assert get_env_bool("X_BOOL", True) is True

    @pytest.mark.parametrize("valor", ["true", "TRUE", "1", "yes", "on", "On"])
    def test_valores_verdadeiros(self, monkeypatch, valor):
        monkeypatch.setenv("X_BOOL", valor)
        assert get_env_bool("X_BOOL", False) is True

    @pytest.mark.parametrize("valor", ["false", "0", "no", "off", "qualquer"])
    def test_valores_falsos(self, monkeypatch, valor):
        monkeypatch.setenv("X_BOOL", valor)
        assert get_env_bool("X_BOOL", True) is False


class TestNumericos:
    def test_int_invalido_cai_no_default(self, monkeypatch):
        monkeypatch.setenv("X_INT", "abc")
        assert get_env_int("X_INT", 42) == 42

    def test_float_invalido_cai_no_default(self, monkeypatch):
        monkeypatch.setenv("X_FLOAT", "")
        assert get_env_float("X_FLOAT", 1.5) == 1.5


class TestSettings:
    """Código após um return no __init__ nunca executa, e os atributos
    afetados só falham quando alguém os lê."""

    @pytest.mark.parametrize("campo", [
        "alerts_enabled",
        "alert_cost_warning_usd", "alert_cost_critical_usd",
        "alert_cpu_warning_percent", "alert_cpu_critical_percent",
        "alert_cpu_window_minutes",
        "alert_memory_warning_percent", "alert_memory_critical_percent",
        "alert_disk_warning_percent", "alert_disk_critical_percent",
        "alert_attack_failures", "alert_attack_window_minutes",
        "watch_ssh_logins",
    ])
    def test_atributo_existe(self, campo):
        assert hasattr(mod.settings, campo), f"Settings perdeu {campo}"

    def test_allowlist_vira_lista_de_int(self):
        assert mod.settings.telegram_allowed_ids == [111, 222]

    def test_oci_configured_exige_os_dois(self, monkeypatch):
        s = mod.settings
        monkeypatch.setattr(s, "oci_region", "sa-saopaulo-1")
        monkeypatch.setattr(s, "oci_instance_ocid", "ocid1.instance.oc1..x")
        assert s.oci_configured is True

        monkeypatch.setattr(s, "oci_instance_ocid", None)
        assert s.oci_configured is False


class TestValidacaoOcid:
    """Um OCID no campo errado vira 404 NotAuthorizedOrNotFound, que parece
    falta de permissão. Detectar pelo prefixo evita a caça errada."""

    def test_ocids_corretos_nao_reclamam(self, monkeypatch):
        from oci_relay.oci import auth

        monkeypatch.setattr(mod.settings, "oci_user_ocid", "ocid1.user.oc1..a")
        monkeypatch.setattr(mod.settings, "oci_tenancy_ocid", "ocid1.tenancy.oc1..a")
        monkeypatch.setattr(mod.settings, "oci_instance_ocid", "ocid1.instance.oc1..a")
        monkeypatch.setattr(mod.settings, "oci_compartment_ocid", None)
        assert auth.validar_ocids() == []

    def test_tenancy_no_lugar_da_instancia(self, monkeypatch):
        from oci_relay.oci import auth

        monkeypatch.setattr(mod.settings, "oci_user_ocid", None)
        monkeypatch.setattr(mod.settings, "oci_tenancy_ocid", None)
        monkeypatch.setattr(mod.settings, "oci_compartment_ocid", None)
        monkeypatch.setattr(mod.settings, "oci_instance_ocid", "ocid1.tenancy.oc1..a")

        problemas = auth.validar_ocids()
        assert len(problemas) == 1
        assert "OCI_INSTANCE_OCID" in problemas[0]
        assert "ocid1.instance" in problemas[0]

    def test_caractere_extra_colado(self, monkeypatch):
        """Um caractere a mais no início quebra o prefixo sem saltar aos olhos."""
        from oci_relay.oci import auth

        monkeypatch.setattr(mod.settings, "oci_user_ocid", None)
        monkeypatch.setattr(mod.settings, "oci_tenancy_ocid", None)
        monkeypatch.setattr(mod.settings, "oci_compartment_ocid", None)
        monkeypatch.setattr(mod.settings, "oci_instance_ocid",
                            "oocid1.instance.oc1.sa-saopaulo-1.aaaa")
        assert auth.validar_ocids() != []

    def test_compartment_aceita_tenancy(self, monkeypatch):
        """No compartimento root, compartment_id == tenancy_id."""
        from oci_relay.oci import auth

        monkeypatch.setattr(mod.settings, "oci_user_ocid", None)
        monkeypatch.setattr(mod.settings, "oci_tenancy_ocid", None)
        monkeypatch.setattr(mod.settings, "oci_instance_ocid", None)
        monkeypatch.setattr(mod.settings, "oci_compartment_ocid",
                            "ocid1.tenancy.oc1..a")
        assert auth.validar_ocids() == []
