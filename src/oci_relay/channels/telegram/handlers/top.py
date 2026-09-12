"""Handler /top."""

import asyncio

from ....system import get_top_processes, get_top_processes_by_memory
from .. import formatter as fmt

_QUANTOS = 8


async def handle(client, token: str, chat_id: int):
    """Envia os processos que mais consomem CPU e memória."""
    from ..adapter import tg_send_text

    try:
        # Uma coleta só alimenta as duas listas; amostrar CPU custa ~0,5s.
        por_cpu, por_ram = await asyncio.gather(
            asyncio.to_thread(get_top_processes, _QUANTOS),
            asyncio.to_thread(get_top_processes_by_memory, _QUANTOS),
        )

        partes = [fmt.titulo_local("🔥", "Top processos"), ""]

        if por_cpu:
            partes.append(fmt.secao("Por CPU"))
            partes.append(fmt.bloco([
                f"{p['cpu_percent']:>5.1f}%  {p['pid']:>7}  {p['name'][:22]}"
                for p in por_cpu
            ]))

        if por_ram:
            partes.append(fmt.secao("Por memória"))
            partes.append(fmt.bloco([
                f"{p['memory_percent']:>5.1f}%  {p['pid']:>7}  {p['name'][:22]}"
                for p in por_ram
            ]))

        if not por_cpu and not por_ram:
            partes.append(f"{fmt.NEUTRO} Nenhum processo visível.")

        partes.append("__Percentual de CPU normalizado pelo número de núcleos.__")

        await tg_send_text(client, token, chat_id, "\n".join(partes))
    except Exception as e:
        await tg_send_text(client, token, chat_id, f"Erro ao obter processos: {e}")
