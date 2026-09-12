"""Handler /container."""

import asyncio

from ....docker import get_container_stats
from ....i18n import t
from .. import formatter as fmt


def _percentual_cpu(stats: dict) -> float | None:
    """Uso de CPU a partir do delta entre duas amostras do daemon.

    O Docker entrega contadores acumulados; a fração é a variação do tempo
    gasto pelo container sobre a variação do tempo total do sistema.
    """
    try:
        cpu = stats["cpu_stats"]
        anterior = stats["precpu_stats"]
        delta = cpu["cpu_usage"]["total_usage"] - anterior["cpu_usage"]["total_usage"]
        delta_sistema = cpu["system_cpu_usage"] - anterior["system_cpu_usage"]
        if delta_sistema <= 0:
            return None
        nucleos = cpu.get("online_cpus") or 1
        return round(delta / delta_sistema * nucleos * 100, 1)
    except (KeyError, TypeError, ZeroDivisionError):
        return None


async def handle(client, token: str, chat_id: int,
                 actor_id: int | None = None, args: str = ""):
    """Envia consumo de um container específico."""
    from ..adapter import tg_send_text

    cabecalho = fmt.cabecalho(t("container.title"))
    nome = args.strip()

    if not nome:
        await tg_send_text(client, token, chat_id,
            f"{cabecalho}\n\n{t('container.usage')}")
        return

    try:
        stats = await asyncio.to_thread(get_container_stats, nome)

        if isinstance(stats, dict) and "error" in stats:
            await tg_send_text(client, token, chat_id,
                f"{cabecalho}\n\n{fmt.NEUTRO} {stats['error']}")
            return

        cpu = _percentual_cpu(stats)
        mem = stats.get("memory_stats", {})
        usado = mem.get("usage")
        limite = mem.get("limit")

        linhas = [(t("container.status"), stats.get("name", nome).lstrip("/"))]
        if cpu is not None:
            linhas.append((t("container.cpu"), f"{cpu}%"))
        if usado and limite:
            linhas.append((t("container.memory"),
                           f"{fmt.gb(usado / 1024**3)} / "
                           f"{fmt.gb(limite / 1024**3)} GB"))

        await tg_send_text(client, token, chat_id,
                           "\n".join([cabecalho, "", fmt.tabela(linhas)]))
    except Exception as e:
        await tg_send_text(client, token, chat_id,
            t("errors.generic", subject="container", reason=e))
