"""Handler /health — saúde da instância OCI, lida via Monitoring."""

import asyncio

from ....config.settings import settings
from ....i18n import t
from ....oci import compute, monitoring
from ....system import get_health as get_health_local
from .. import formatter as fmt


def _pct(valor: float | None) -> str:
    return "n/d" if valor is None else f"{valor:.1f}%"


async def _painel_vps(client, token: str, chat_id: int):
    """Saúde da VPS pelas métricas do OCI Monitoring."""
    from ..adapter import tg_send_text

    status, metricas = await asyncio.gather(
        compute.get_instance_status(),
        monitoring.get_instance_metrics(),
    )

    e_estado = fmt.emoji_estado_oci(status.state)
    e_cpu = fmt.emoji_percentual(
        metricas["cpu"], settings.alert_cpu_warning_percent,
        settings.alert_cpu_critical_percent)
    e_mem = fmt.emoji_percentual(
        metricas["memory"], settings.alert_memory_warning_percent,
        settings.alert_memory_critical_percent)

    partes = [
        fmt.cabecalho(t("health.title_vps", name=status.display_name or "n/d")),
        "",
        fmt.tabela([
            (t("instance.state"), f"{e_estado} {status.state}"),
            (t("instance.shape"), status.shape or "n/d"),
            (t("instance.ocpu"), fmt.gb(status.ocpus)),
            (t("instance.memory"), f"{fmt.gb(status.memory_gb)} GB"),
        ]),
        fmt.secao(t("health.utilisation")),
        fmt.tabela([
            (t("summary.cpu"), f"{e_cpu} {_pct(metricas['cpu'])}"),
            (t("instance.memory"), f"{e_mem} {_pct(metricas['memory'])}"),
            (t("summary.load"), "n/d" if metricas["load"] is None
                                else f"{metricas['load']:.2f}"),
        ]),
    ]

    io = [
        (t("health.disk_read"), metricas["disk_read"]),
        (t("health.disk_write"), metricas["disk_write"]),
        (t("health.net_in"), metricas["net_in"]),
        (t("health.net_out"), metricas["net_out"]),
    ]
    if any(v is not None for _, v in io):
        partes.append(fmt.secao(t("health.io")))
        partes.append(fmt.tabela([
            (rotulo, "n/d" if v is None else f"{v / 1024:.1f} KB/s")
            for rotulo, v in io
        ]))

    partes += [
        f"{t('common.overall')}: {fmt.veredito(e_estado, e_cpu, e_mem)}",
        f"__{t('common.source_monitoring')}__",
    ]

    await tg_send_text(client, token, chat_id, "\n".join(partes))


async def _painel_local(client, token: str, chat_id: int):
    """Fallback: saúde da máquina onde o Relay roda."""
    from ..adapter import tg_send_text

    health = await asyncio.to_thread(get_health_local)
    cpu, mem, disk = health["cpu"], health["memory"], health["disk"]

    e_cpu = fmt.emoji_percentual(
        cpu["percent"], settings.alert_cpu_warning_percent,
        settings.alert_cpu_critical_percent)
    e_mem = fmt.emoji_percentual(
        mem["percent"], settings.alert_memory_warning_percent,
        settings.alert_memory_critical_percent)
    e_disk = fmt.emoji_percentual(
        disk["percent"], settings.alert_disk_warning_percent,
        settings.alert_disk_critical_percent)

    await tg_send_text(client, token, chat_id, "\n".join([
        fmt.cabecalho_local(t("health.title_local")),
        "",
        fmt.tabela([
            (t("summary.uptime"), fmt.uptime(health["uptime_seconds"])),
            (t("summary.cpu"), f"{e_cpu} {cpu['percent']}%"),
            (t("instance.memory"), f"{e_mem} {mem['percent']}%"),
            (t("summary.disk"), f"{e_disk} {disk['percent']}%"),
        ]),
        f"{t('common.overall')}: {fmt.veredito(e_cpu, e_mem, e_disk)}",
        f"__{t('health.local_notice')}__",
    ]))


async def handle(client, token: str, chat_id: int,
                 actor_id: int | None = None, args: str = ""):
    """Envia saúde da VPS, ou do host local se a OCI não estiver configurada."""
    from ..adapter import tg_send_text

    try:
        if settings.oci_configured:
            await _painel_vps(client, token, chat_id)
        else:
            await _painel_local(client, token, chat_id)
    except Exception as e:
        await tg_send_text(client, token, chat_id,
            t("errors.generic", subject="health", reason=e))
