"""Handler /oci_ip."""

import oci

from ....oci import compute
from .. import formatter as fmt


async def handle(client, token: str, chat_id: int,
                 actor_id: int | None = None):
    """Envia os IPs da instância conhecidos pela OCI."""
    from ..adapter import tg_send_text

    try:
        ips = await compute.get_instance_ips()

        if not ips:
            await tg_send_text(client, token, chat_id,
                f"🌐 **OCI IPs**\n\n{fmt.NEUTRO} Nenhuma VNIC primária encontrada.")
            return

        linhas = [
            ("Public", ips.get("public_ip") or "sem IP público"),
            ("Private", ips.get("private_ip") or "n/d"),
        ]
        if ips.get("hostname"):
            linhas.append(("Hostname", ips["hostname"]))
        linhas.append(("NSGs", str(ips.get("nsg_count", 0))))

        await tg_send_text(client, token, chat_id, "\n".join([
            fmt.titulo("🌐", "OCI IPs"), "", fmt.tabela(linhas),
        ]))
    except oci.exceptions.ServiceError as e:
        await tg_send_text(client, token, chat_id,
            f"🌐 **OCI IPs**\n\n{fmt.CRITICO} HTTP {e.status} — {e.message}")
    except Exception as e:
        await tg_send_text(client, token, chat_id, f"Erro ao obter IPs: {e}")
