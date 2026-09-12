"""Envio de mensagens para o Discord pela API HTTP."""

import asyncio
import logging

import httpx

from ...config.settings import settings

logger = logging.getLogger(__name__)

_MAX_MESSAGE_LENGTH = 2000
_SPLIT_THRESHOLD = 1900


def _chunk_discord(text: str) -> list[str]:
    """Quebra texto em pedaços <= 2000 chars."""
    if not text:
        return []
    if len(text) <= _MAX_MESSAGE_LENGTH:
        return [text]

    pedacos = []
    atual = ""
    for linha in text.split("\n"):
        if len(atual) + len(linha) + 1 > _SPLIT_THRESHOLD and atual:
            pedacos.append(atual.rstrip("\n"))
            atual = ""
        while len(linha) > _SPLIT_THRESHOLD:
            pedacos.append(linha[:_SPLIT_THRESHOLD])
            linha = linha[_SPLIT_THRESHOLD:]
        atual += linha + "\n"
    if atual.strip():
        pedacos.append(atual.rstrip("\n"))
    return pedacos


async def _send_discord_message(token: str, channel_id: str, content: str) -> bool:
    """Envia mensagem para Discord via API."""
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"

    payload = {"content": content}

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                json=payload,
                headers={"Authorization": f"Bot {token}"},
                timeout=20.0
            )
            if resp.status_code in (200, 201, 204):
                return True
            logger.warning("Discord API retornou status %d", resp.status_code)
            return False
    except Exception as e:
        logger.error("Erro ao enviar mensagem para Discord: %s", e)
        return False


async def send_discord_message(token: str, channel_id: str, content: str) -> bool:
    """Envia mensagem para Discord com chunking e retry."""
    if not token or not channel_id:
        logger.warning("Discord token ou channel_id não configurado.")
        return False

    for pedaco in _chunk_discord(content):
        for attempt in range(3):
            if await _send_discord_message(token, channel_id, pedaco):
                break
            if attempt < 2:
                await asyncio.sleep(1)
        else:
            return False
    return True


async def send_discord_alert(content: str) -> bool:
    """Envia alerta para Discord via webhook (se configurado)."""
    if not settings.discord_webhook:
        logger.debug("Discord webhook não configurado.")
        return False

    payload = {"content": content[:2000]}

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                settings.discord_webhook, json=payload, timeout=10.0)
            return resp.status_code in (200, 204)
    except Exception as e:
        logger.error("Erro ao enviar alerta para Discord: %s", e)
        return False
