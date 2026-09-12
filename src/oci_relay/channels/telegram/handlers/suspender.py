"""Handler /suspender."""

from . import power


async def handle(client, token: str, chat_id: int,
                 actor_id: int | None = None):
    """Mostra a prévia e pede confirmação antes de agir."""
    await power.pedir_confirmacao(client, token, chat_id, actor_id, "/suspender")
