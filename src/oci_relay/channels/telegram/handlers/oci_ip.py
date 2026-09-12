"""Handler /oci_ip."""

import oci

from ....i18n import t
from ....oci import compute
from .. import formatter as fmt


async def handle(client, token: str, chat_id: int,
                 actor_id: int | None = None, args: str = ""):
    """Envia os IPs da instância conhecidos pela OCI."""
    from ..adapter import tg_send_text

    cabecalho = fmt.cabecalho(t("oci_ip.title"))

    try:
        ips = await compute.get_instance_ips()

        if not ips:
            await tg_send_text(client, token, chat_id,
                f"{cabecalho}\n\n{fmt.NEUTRO} {t('oci_ip.no_vnic')}")
            return

        linhas = [
            (t("oci_ip.public"), ips.get("public_ip") or t("oci_ip.no_public")),
            (t("oci_ip.private"), ips.get("private_ip") or "n/d"),
        ]
        if ips.get("hostname"):
            linhas.append((t("oci_ip.hostname"), ips["hostname"]))
        linhas.append((t("oci_ip.nsgs"), str(ips.get("nsg_count", 0))))

        await tg_send_text(client, token, chat_id,
                           "\n".join([cabecalho, "", fmt.tabela(linhas)]))
    except oci.exceptions.ServiceError as e:
        await tg_send_text(client, token, chat_id,
            f"{cabecalho}\n\n{fmt.CRITICO} "
            + t("errors.oci_refused", status=e.status, message=e.message))
    except Exception as e:
        await tg_send_text(client, token, chat_id,
            t("errors.generic", subject="IPs", reason=e))
