"""Handler /suspender."""

from .. import formatter as fmt


async def handle(client, token: str, chat_id: int,
                 actor_id: int | None = None):
    """Responde que o recurso ainda não foi implementado."""
    from ..adapter import tg_send_text
    await tg_send_text(client, token, chat_id,
        fmt.nao_implementado("Suspensão da instância"))
