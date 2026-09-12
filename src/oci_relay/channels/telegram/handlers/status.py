"""Handler /status."""

import oci

from ....oci import compute
from .. import formatter as fmt


async def handle(client, token: str, chat_id: int,
                 actor_id: int | None = None):
    """Envia estado da instância OCI."""
    from ..adapter import tg_send_text

    try:
        status = await compute.get_instance_status()
        emoji = fmt.emoji_estado_oci(status.state)

        partes = [
            fmt.titulo("☁️", "Instance Status"),
            "",
            fmt.tabela([
                ("Name", status.display_name or "n/d"),
                ("State", f"{emoji} {status.state}"),
                ("Shape", status.shape or "n/d"),
                ("OCPU", fmt.gb(status.ocpus)),
                ("Memory", f"{fmt.gb(status.memory_gb)} GB"),
                ("Region", status.region or "n/d"),
            ]),
        ]

        await tg_send_text(client, token, chat_id, "\n".join(partes))
    except oci.exceptions.ServiceError as e:
        await tg_send_text(client, token, chat_id,
            f"☁️ **Instance Status**\n\n{fmt.CRITICO} OCI recusou a chamada\n"
            f"HTTP {e.status} — {e.message}")
    except Exception as e:
        await tg_send_text(client, token, chat_id,
            f"☁️ **Instance Status**\n\n{fmt.NEUTRO} Indisponível\n{e}")
