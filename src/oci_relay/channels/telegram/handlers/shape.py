"""Handler /shape."""

import oci

from ....i18n import t
from ....oci import compute
from .. import formatter as fmt


async def handle(client, token: str, chat_id: int,
                 actor_id: int | None = None, args: str = ""):
    """Envia a configuração de shape da instância."""
    from ..adapter import tg_send_text

    cabecalho = fmt.cabecalho(t("shape.title"))

    try:
        status = await compute.get_instance_status()

        # shape_config só existe em shapes Flex; sem ele, a configuração é
        # fixa e OCPU/memória vêm do próprio nome do shape.
        flex = status.ocpus is not None

        linhas = [(t("shape.shape"), status.shape or "n/d")]
        if flex:
            linhas += [
                (t("shape.ocpu"), fmt.gb(status.ocpus)),
                (t("shape.memory"), f"{fmt.gb(status.memory_gb)} GB"),
            ]

        await tg_send_text(client, token, chat_id, "\n".join([
            cabecalho,
            "",
            fmt.tabela(linhas),
            f"__{t('shape.flex_note' if flex else 'shape.fixed_note')}__",
        ]))
    except oci.exceptions.ServiceError as e:
        await tg_send_text(client, token, chat_id,
            f"{cabecalho}\n\n{fmt.CRITICO} "
            + t("errors.oci_refused", status=e.status, message=e.message))
    except Exception as e:
        await tg_send_text(client, token, chat_id,
            t("errors.generic", subject="shape", reason=e))
