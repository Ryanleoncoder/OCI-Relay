"""Handler /top."""

import asyncio

from ....i18n import t
from ....system import get_top_processes, get_top_processes_by_memory
from .. import formatter as fmt

_QUANTOS = 8


async def handle(client, token: str, chat_id: int,
                 actor_id: int | None = None, args: str = ""):
    """Envia os processos que mais consomem CPU e memória."""
    from ..adapter import tg_send_text

    try:
        por_cpu, por_ram = await asyncio.gather(
            asyncio.to_thread(get_top_processes, _QUANTOS),
            asyncio.to_thread(get_top_processes_by_memory, _QUANTOS),
        )

        partes = [fmt.cabecalho_local(t("top.title")), ""]

        if por_cpu:
            partes.append(fmt.secao(t("top.by_cpu")))
            partes.append(fmt.bloco([
                f"{p['cpu_percent']:>5.1f}%  {p['pid']:>7}  {p['name'][:22]}"
                for p in por_cpu
            ]))

        if por_ram:
            partes.append(fmt.secao(t("top.by_memory")))
            partes.append(fmt.bloco([
                f"{p['memory_percent']:>5.1f}%  {p['pid']:>7}  {p['name'][:22]}"
                for p in por_ram
            ]))

        if not por_cpu and not por_ram:
            partes.append(f"{fmt.NEUTRO} {t('top.none')}")

        partes.append(f"__{t('top.normalised')}__")

        await tg_send_text(client, token, chat_id, "\n".join(partes))
    except Exception as e:
        await tg_send_text(client, token, chat_id,
            t("errors.generic", subject="processes", reason=e))
