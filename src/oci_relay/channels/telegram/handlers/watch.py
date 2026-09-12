"""Handler /watch."""

from ....i18n import t
from .. import formatter as fmt


async def handle(client, token: str, chat_id: int,
                 actor_id: int | None = None, args: str = ""):
    """Responde que o recurso ainda não foi implementado."""
    from ..adapter import tg_send_text
    await tg_send_text(client, token, chat_id,
                       fmt.nao_implementado(t("features.watchers")))
