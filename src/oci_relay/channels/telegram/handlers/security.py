"""Handler /security."""

import asyncio

from ....security import (
    get_fail2ban_status,
    get_listening_ports_summary,
    get_ssh_failures,
)
from .. import formatter as fmt

_EMOJI_F2B = {
    "active": fmt.OK,
    "inactive": fmt.CRITICO,
    "not_installed": fmt.NEUTRO,
    "error": fmt.CRITICO,
}


async def handle(client, token: str, chat_id: int,
                 actor_id: int | None = None):
    """Envia dashboard de segurança."""
    from ..adapter import tg_send_text

    try:
        f2b = await asyncio.to_thread(get_fail2ban_status)
        portas = await asyncio.to_thread(get_listening_ports_summary)
        ssh = await asyncio.to_thread(get_ssh_failures)

        status_f2b = f2b.get("status", "error")
        e_f2b = _EMOJI_F2B.get(status_f2b, fmt.NEUTRO)

        publicas = [p for p in portas if p["public"]]
        e_portas = fmt.AVISO if publicas else fmt.OK

        partes = [
            fmt.titulo("🛡️", "Security"),
            "",
            f"Fail2Ban: {e_f2b} {status_f2b}",
            "",
            fmt.secao("SSH"),
        ]

        if "error" in ssh:
            partes.append(f"{fmt.NEUTRO} logs indisponíveis neste host")
            e_ssh = fmt.NEUTRO
        else:
            falhas = ssh.get("total", 0)
            e_ssh = fmt.OK
            partes.append(fmt.tabela([("Failed logins (24h)", str(falhas))]))

        partes += [
            fmt.secao("Network"),
            fmt.tabela([
                ("Listening ports", str(len(portas))),
                ("Públicas", f"{e_portas} {len(publicas)}"),
            ]),
            f"Overall: {fmt.veredito(e_f2b, e_ssh, e_portas)}",
        ]

        await tg_send_text(client, token, chat_id, "\n".join(partes))
    except Exception as e:
        await tg_send_text(client, token, chat_id, f"Erro ao obter segurança: {e}")
