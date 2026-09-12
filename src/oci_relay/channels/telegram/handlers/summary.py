"""Handler /summary."""

import asyncio

import oci

from ....config.settings import settings
from ....oci import compute
from ....system import get_health
from .. import formatter as fmt


async def _bloco_oci() -> tuple[list[str], str]:
    """Bloco OCI do resumo e seu emoji; degrada se a OCI estiver inacessível."""
    try:
        status = await compute.get_instance_status()
    except oci.exceptions.ServiceError as e:
        return ([fmt.secao("OCI"), f"{fmt.CRITICO} HTTP {e.status} — {e.message}"],
                fmt.CRITICO)
    except Exception as e:
        return ([fmt.secao("OCI"), f"{fmt.NEUTRO} indisponível ({e})"], fmt.NEUTRO)

    emoji = fmt.emoji_estado_oci(status.state)
    return ([
        fmt.secao("OCI"),
        fmt.tabela([
            ("Name", status.display_name or "n/d"),
            ("State", f"{emoji} {status.state}"),
            ("Shape", status.shape or "n/d"),
            ("OCPU", fmt.gb(status.ocpus)),
            ("Memory", f"{fmt.gb(status.memory_gb)} GB"),
        ]),
    ], emoji)


async def handle(client, token: str, chat_id: int,
                 actor_id: int | None = None):
    """Envia resumo rápido do sistema."""
    from ..adapter import tg_send_text

    try:
        # O bloco OCI degrada sozinho para não derrubar o resumo local.
        linhas_oci, e_oci = await _bloco_oci()
        health = await asyncio.to_thread(get_health)

        cpu = health["cpu"]
        mem = health["memory"]
        disk = health["disk"]

        e_cpu = fmt.emoji_percentual(
            cpu["percent"], settings.alert_cpu_warning_percent,
            settings.alert_cpu_critical_percent)
        e_mem = fmt.emoji_percentual(
            mem["percent"], settings.alert_memory_warning_percent,
            settings.alert_memory_critical_percent)
        e_disk = fmt.emoji_percentual(
            disk["percent"], settings.alert_disk_warning_percent,
            settings.alert_disk_critical_percent)

        partes = [fmt.titulo("☁️", "OCI Relay"), ""]
        partes += linhas_oci
        partes += [
            fmt.secao("Resources"),
            fmt.tabela([
                ("Uptime", fmt.uptime(health["uptime_seconds"])),
                ("CPU", f"{e_cpu} {cpu['percent']}%"),
                ("RAM", f"{e_mem} {fmt.gb(mem['used_gb'])} / "
                        f"{fmt.gb(mem['total_gb'])} GB"),
                ("Disk", f"{e_disk} {fmt.gb(disk['used_gb'])} / "
                         f"{fmt.gb(disk['total_gb'])} GB"),
                ("Load", fmt.carga(cpu["load_avg"])),
            ]),
            f"Overall: {fmt.veredito(e_oci, e_cpu, e_mem, e_disk)}",
        ]

        await tg_send_text(client, token, chat_id, "\n".join(partes))
    except Exception as e:
        await tg_send_text(client, token, chat_id, f"Erro ao obter resumo: {e}")
