"""Configurações carregadas do .env."""

import os


def get_env(key: str) -> str:
    value = os.getenv(key, "").strip()
    if not value:
        raise ValueError(
            f"Variável obrigatória não encontrada: {key}. "
            "Defina-a no .env (veja .env.example)."
        )
    return value


def get_env_or_none(key: str) -> str | None:
    return os.getenv(key, "").strip() or None


def get_env_bool(key: str, default: bool = False) -> bool:
    raw = os.getenv(key, "").strip().lower()
    if not raw:
        return default
    return raw in ("true", "1", "yes", "on")


def get_env_float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, str(default)))
    except ValueError:
        return default


def get_env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


class Settings:
    def __init__(self):
        self.telegram_token = get_env("TELEGRAM_BOT_TOKEN")
        self.telegram_allowed_ids = [
            int(x.strip())
            for x in (get_env_or_none("TELEGRAM_ALLOWED_CHAT_IDS") or "").split(",")
            if x.strip()
        ]

        self.discord_bot_token = get_env_or_none("DISCORD_BOT_TOKEN")
        self.discord_channel_id = get_env_or_none("DISCORD_CHANNEL_ID")
        self.discord_webhook = get_env_or_none("DISCORD_WEBHOOK_URL")

        # Config OCI é opcional aqui: sem ela o bot sobe e serve os comandos
        # locais. A validação com mensagem clara fica na camada oci/auth.py.
        self.oci_use_instance_principal = get_env_bool(
            "OCI_USE_INSTANCE_PRINCIPAL", True)

        self.oci_user_ocid = get_env_or_none("OCI_USER_OCID")
        self.oci_tenancy_ocid = get_env_or_none("OCI_TENANCY_OCID")
        self.oci_fingerprint = get_env_or_none("OCI_FINGERPRINT")
        self.oci_private_key_path = get_env_or_none("OCI_PRIVATE_KEY_PATH")

        self.oci_region = get_env_or_none("OCI_REGION")
        self.oci_instance_ocid = get_env_or_none("OCI_INSTANCE_OCID")

        # Opcional: as consultas de métricas caem na tenancy quando vazio.
        self.oci_compartment_ocid = get_env_or_none("OCI_COMPARTMENT_OCID")

        self.alerts_enabled = get_env_bool("ALERTS_ENABLED", True)

        self.alert_cost_warning_usd = get_env_float("ALERT_COST_WARNING_USD", 0.10)
        self.alert_cost_critical_usd = get_env_float("ALERT_COST_CRITICAL_USD", 1.00)

        self.alert_cpu_warning_percent = get_env_int("ALERT_CPU_WARNING_PERCENT", 85)
        self.alert_cpu_critical_percent = get_env_int("ALERT_CPU_CRITICAL_PERCENT", 95)
        self.alert_cpu_window_minutes = get_env_int("ALERT_CPU_WINDOW_MINUTES", 15)

        self.alert_memory_warning_percent = get_env_int(
            "ALERT_MEMORY_WARNING_PERCENT", 85)
        self.alert_memory_critical_percent = get_env_int(
            "ALERT_MEMORY_CRITICAL_PERCENT", 95)

        self.alert_disk_warning_percent = get_env_int("ALERT_DISK_WARNING_PERCENT", 80)
        self.alert_disk_critical_percent = get_env_int(
            "ALERT_DISK_CRITICAL_PERCENT", 95)

        self.alert_attack_failures = get_env_int("ALERT_ATTACK_FAILURES", 100)
        self.alert_attack_window_minutes = get_env_int(
            "ALERT_ATTACK_WINDOW_MINUTES", 10)

        self.watch_ssh_logins = get_env_bool("WATCH_SSH_LOGINS", False)

        self.critical_services = tuple(
            s.strip() for s in
            (get_env_or_none("CRITICAL_SERVICES") or "ssh,docker,fail2ban").split(",")
            if s.strip()
        )

    @property
    def oci_configured(self) -> bool:
        """OCI só é utilizável com região e OCID da instância definidos."""
        return bool(self.oci_region and self.oci_instance_ocid)


settings = Settings()
