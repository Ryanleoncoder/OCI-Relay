"""Handler /docker_logs."""

import asyncio

from ....docker import get_container_logs
from ....i18n import t
from .. import formatter as fmt

# Log de container cresce sem limite; o Telegram corta a mensagem em 4096
# caracteres. O recorte acontece aqui para a resposta continuar legível.
_LINHAS = 30


async def handle(client, token: str, chat_id: int,
                 actor_id: int | None = None, args: str = ""):
    """Envia as últimas linhas do log de um container."""
    from ..adapter import tg_send_text

    cabecalho = fmt.cabecalho(t("docker_logs.title"))
    nome = args.strip()

    if not nome:
        await tg_send_text(client, token, chat_id,
            f"{cabecalho}\n\n{t('docker_logs.usage')}")
        return

    try:
        logs = await asyncio.to_thread(get_container_logs, nome, _LINHAS)

        if isinstance(logs, dict) and "error" in logs:
            await tg_send_text(client, token, chat_id,
                f"{cabecalho}\n\n{fmt.NEUTRO} {logs['error']}")
            return

        linhas = [ln for ln in (logs or "").splitlines() if ln.strip()]
        if not linhas:
            await tg_send_text(client, token, chat_id,
                f"{cabecalho}\n\n{t('docker_logs.empty')}")
            return

        await tg_send_text(client, token, chat_id, "\n".join([
            f"{cabecalho} — {nome}",
            "",
            fmt.bloco(linhas[-_LINHAS:]),
            f"__{t('docker_logs.truncated', count=min(len(linhas), _LINHAS))}__",
        ]))
    except Exception as e:
        await tg_send_text(client, token, chat_id,
            t("errors.generic", subject="logs", reason=e))
