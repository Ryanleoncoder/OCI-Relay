"""Gateway Telegram — polling, retry, coalescência."""

import asyncio
import html
import re
import logging
import httpx

from ...config.settings import settings
from . import registry

logger = logging.getLogger(__name__)

_TG_LIMIT = 4096
_TG_CHUNK = 3800
_COALESCE_WINDOW = 1.5

logger_telegram_token_filter = logging.Filter()


def _filter_telegram_token(record):
    msg = record.getMessage()
    sanitized = re.sub(
        r"https://api\.telegram\.org/bot[^/\s\"']+",
        "https://api.telegram.org/bot<redacted>",
        msg
    )
    if sanitized != msg:
        record.msg = sanitized
        record.args = ()
    return True


logger.addFilter(_filter_telegram_token)
logging.getLogger("httpx").addFilter(_filter_telegram_token)


def _markdown_to_telegram_html(md: str) -> str:
    if not md:
        return ""

    linhas = md.split("\n")
    partes = []

    i = 0
    while i < len(linhas):
        ln = linhas[i].strip()

        if ln.startswith("```"):
            corpo = []
            i += 1
            while i < len(linhas) and not linhas[i].strip().startswith("```"):
                corpo.append(linhas[i])
                i += 1
            i += 1
            texto = html.escape("\n".join(corpo))
            partes.append(f"<pre>{texto}</pre>")
            continue

        if ln.startswith("|"):
            bloco = []
            while i < len(linhas) and linhas[i].strip().startswith("|"):
                bloco.append(linhas[i])
                i += 1
            celulas_list = []
            for linha in bloco:
                linha = linha.strip().strip("|")
                if all(set(c) <= set("-: ") for c in linha.split("|")):
                    continue
                celulas = [c.strip() for c in linha.split("|")]
                celulas_list.append(celulas)

            if celulas_list:
                larguras = [
                    max(len(r[i]) if i < len(r) else 0 for r in celulas_list)
                    for i in range(max(len(r) for r in celulas_list))
                ]
                texto = "\n".join(
                    "  ".join(c.ljust(larguras[j]) if j < len(larguras) else c
                             for j, c in enumerate(r)).rstrip()
                    for r in celulas_list
                )
                partes.append(f"<pre>{html.escape(texto)}</pre>")
            continue

        i += 1
        texto = html.escape(ln)
        texto = re.sub(r"^\s*#{1,6}\s*(.+?)\s*$", r"<b>\1</b>", texto)
        texto = re.sub(r"^(\s*)[-*]\s+", r"\1• ", texto)
        texto = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", texto)
        texto = re.sub(r"__(.+?)__", r"<i>\1</i>", texto)
        texto = re.sub(r"`([^`]+)`", r"<code>\1</code>", texto)
        partes.append(texto)

    return "\n".join(partes).strip()


def _chunk_telegram(texto: str, tamanho: int = _TG_CHUNK) -> list[str]:
    if not texto:
        return []
    if len(texto) <= tamanho:
        return [texto]

    pedacos = []
    atual = ""
    for linha in texto.split("\n"):
        if len(atual) + len(linha) + 1 > tamanho and atual:
            pedacos.append(atual.rstrip("\n"))
            atual = ""
        while len(linha) > tamanho:
            pedacos.append(linha[:tamanho])
            linha = linha[tamanho:]
        atual += linha + "\n"

    if atual.strip():
        pedacos.append(atual.rstrip("\n"))

    return pedacos


async def _tg_post(client, token: str, method: str, json: dict = None,
                   max_retries: int = 3) -> httpx.Response | None:
    url = f"https://api.telegram.org/bot{token}/{method}"
    backoff = 1.0

    for attempt in range(max_retries + 1):
        try:
            resp = await client.post(url, json=json, timeout=20.0)
        except (httpx.TimeoutException, httpx.NetworkError):
            if attempt >= max_retries:
                logger.warning("Telegram %s falhou após %d tentativas",
                               method, attempt + 1)
                return None
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 10)
            continue

        if resp.status_code == 429:
            retry_after = 1.0
            try:
                retry_after = float(
                    resp.json().get("parameters", {}).get("retry_after", 1))
            except Exception:
                pass
            logger.info("Telegram 429 — aguardando %.1fs", retry_after)
            await asyncio.sleep(min(retry_after, 30) + 0.3)
            continue

        return resp

    return None


async def _tg_send_media_and_strip(client, token: str, chat_id: int, text: str) -> str:
    img_pattern = re.compile(r"!\[[^\]]*\]\((https?://[^\s)]+)\)")

    for match in img_pattern.finditer(text or ""):
        url = match.group(1)
        base = url.lower().split("?")[0]
        if base.endswith(".gif"):
            method, key = "sendAnimation", "animation"
        else:
            method, key = "sendPhoto", "photo"
        await _tg_post(client, token, method, json={"chat_id": chat_id, key: url})

    return img_pattern.sub("", text or "").strip()


async def tg_send_text(client, token: str, chat_id: int, text: str) -> None:
    text = await _tg_send_media_and_strip(client, token, chat_id, text)
    if not text.strip():
        return

    html_text = _markdown_to_telegram_html(text)

    for pedaco in _chunk_telegram(html_text) or [text]:
        resp = await _tg_post(client, token, "sendMessage", json={
            "chat_id": chat_id,
            "text": pedaco,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        })

        if resp is None or resp.status_code != 200:
            logger.warning("Telegram rejeitou HTML; reenviando como texto puro.")
            plain = re.sub(r"<[^>]+>", "", pedaco)
            await _tg_post(client, token, "sendMessage", json={
                "chat_id": chat_id,
                "text": plain,
            })


class TelegramBotManager:
    def __init__(self):
        self.running = False
        self._buffers: dict = {}
        self._buffer_tasks: dict = {}
        # Quem falou por último em cada chat: a confirmação amarra a ação
        # a essa pessoa, não ao chat.
        self._autores: dict = {}
        self._commands = registry.para_telegram()

    async def _set_commands(self, client, token: str):
        resp = await _tg_post(client, token, "setMyCommands",
                              json={"commands": self._commands})
        if resp is None or resp.status_code != 200:
            logger.warning("Telegram não aceitou setMyCommands.")
            return
        logger.info("Telegram: %d comandos registrados.", len(self._commands))

    async def _set_menu_button(self, client, token: str):
        """Garante o botão Menu com a lista de comandos.

        Sem isso o botão fica em 'default', cujo comportamento varia por
        cliente; 'commands' força a lista a aparecer.
        """
        resp = await _tg_post(client, token, "setChatMenuButton",
                              json={"menu_button": {"type": "commands"}})
        if resp is None or resp.status_code != 200:
            logger.warning("Telegram não aceitou setChatMenuButton.")
            return
        logger.info("Telegram: botão Menu configurado.")

    async def _start_message(self, client, token: str, chat_id: int):
        await tg_send_text(client, token, chat_id, "\n".join([
            "**OCI Relay — Companion Operacional**",
            "",
            "Comandos disponíveis:",
            registry.texto_de_ajuda(),
            "",
            "Use / para ver os comandos.",
        ]))

    async def _process_message(self, client, token: str, chat_id: int,
                               text: str, actor_id: int | None = None):
        if not text.startswith("/"):
            await tg_send_text(client, token, chat_id,
                "Envie um comando. Use /help para ver a lista.")
            return

        nome = text.split()[0]
        comando = registry.buscar(nome)

        if comando is None:
            await tg_send_text(client, token, chat_id,
                f"Comando desconhecido: {nome}")
            return

        # start e help nao tem handler proprio: sao a lista de comandos.
        if comando.handler is None:
            await self._start_message(client, token, chat_id)
            return

        await comando.handler(client, token, chat_id, actor_id)

    async def _handle_message(self, token: str, client, message: dict):
        chat_id = message["chat"]["id"]
        text = message.get("text", "").strip()
        from_id = message.get("from", {}).get("id")

        if not self._autorizado(chat_id, from_id):
            logger.warning(
                "Mensagem ignorada do chat_id=%s (fora da whitelist)", chat_id)
            await tg_send_text(client, token, chat_id,
                "Este assistente está em modo restrito. Seu ID não está autorizado.")
            return

        self._autores[chat_id] = from_id
        self._buffers.setdefault(chat_id, []).append(text)
        old_task = self._buffer_tasks.get(chat_id)
        if old_task and not old_task.done():
            old_task.cancel()
        self._buffer_tasks[chat_id] = asyncio.create_task(
            self._flush_buffer(token, client, chat_id)
        )

    def _autorizado(self, chat_id: int, from_id: int | None) -> bool:
        """Autoriza uma mensagem: basta o chat ou o remetente estar na lista."""
        allowed = settings.telegram_allowed_ids
        return not allowed or chat_id in allowed or from_id in allowed

    async def _flush_buffer(self, token: str, client, chat_id: int):
        try:
            await asyncio.sleep(_COALESCE_WINDOW)
        except asyncio.CancelledError:
            return

        textos = self._buffers.pop(chat_id, [])
        self._buffer_tasks.pop(chat_id, None)
        texto = "\n".join(t for t in textos if t).strip()

        if texto:
            await self._process_message(client, token, chat_id, texto,
                                        self._autores.pop(chat_id, None))

    async def _loop(self, token: str):
        async with httpx.AsyncClient() as client:
            await self._set_commands(client, token)
            await self._set_menu_button(client, token)

            offset = 0
            url = f"https://api.telegram.org/bot{token}/getUpdates"

            while self.running:
                try:
                    params = {"offset": offset, "timeout": 20}
                    resp = await client.get(url, params=params, timeout=25.0)

                    if resp.status_code != 200:
                        logger.warning("Telegram API retornou HTTP %d",
                                       resp.status_code)
                        await asyncio.sleep(5)
                        continue

                    updates = resp.json().get("result", [])
                    for update in updates:
                        offset = update["update_id"] + 1
                        msg = update.get("message")
                        if msg and "text" in msg:
                            await self._handle_message(token, client, msg)

                except asyncio.CancelledError:
                    logger.info("Telegram polling cancelado.")
                    break
                except Exception as e:
                    logger.error("Erro no polling do Telegram: %s", e)
                    await asyncio.sleep(5)

    def start(self):
        if self.running:
            logger.info("Telegram bot já está rodando.")
            return

        self.running = True
        asyncio.create_task(self._loop(settings.telegram_token))

    def stop(self):
        self.running = False
        for task in self._buffer_tasks.values():
            task.cancel()
        logger.info("Telegram bot parado.")


bot_manager = TelegramBotManager()
