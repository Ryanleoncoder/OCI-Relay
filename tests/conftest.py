"""Configuração compartilhada dos testes.

As variáveis de ambiente são definidas antes de qualquer import de
`oci_relay`, porque `config.settings` instancia Settings() no import.
"""

import os

import pytest

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:token-de-teste")
os.environ.setdefault("TELEGRAM_ALLOWED_CHAT_IDS", "111,222")
os.environ.setdefault("OCI_USE_INSTANCE_PRINCIPAL", "false")
os.environ.setdefault("OCI_REGION", "sa-saopaulo-1")
os.environ.setdefault("OCI_INSTANCE_OCID", "ocid1.instance.oc1.sa-saopaulo-1.aaaa")
os.environ.setdefault("OCI_TENANCY_OCID", "ocid1.tenancy.oc1..aaaa")
os.environ.setdefault("OCI_USER_OCID", "ocid1.user.oc1..aaaa")
os.environ.setdefault("OCI_FINGERPRINT", "aa:bb:cc:dd:ee:ff:00:11:22:33:44:55:66:77:88:99")
os.environ.setdefault("OCI_PRIVATE_KEY_PATH", "/nao/existe.pem")


@pytest.fixture
def enviadas(monkeypatch):
    """Captura o que um handler enviaria ao Telegram."""
    from oci_relay.channels.telegram import adapter

    capturadas: list[str] = []

    async def _fake_send(client, token, chat_id, text):
        capturadas.append(text)

    monkeypatch.setattr(adapter, "tg_send_text", _fake_send)
    return capturadas
