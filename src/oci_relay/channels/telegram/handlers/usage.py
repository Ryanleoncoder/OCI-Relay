"""Handler /usage."""

import asyncio

import oci

from ....config.settings import settings
from ....oci import usage
from .. import formatter as fmt

_MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
          "agosto", "setembro", "outubro", "novembro", "dezembro")


def _emoji_custo(total: float) -> str:
    """Semáforo de custo pelos limiares do .env."""
    if total >= settings.alert_cost_critical_usd:
        return fmt.CRITICO
    if total >= settings.alert_cost_warning_usd:
        return fmt.AVISO
    return fmt.OK


def _moeda(valor: float, moeda: str) -> str:
    return f"{moeda} {valor:.2f}" if valor >= 0.01 else f"{moeda} {valor:.4f}"


async def handle(client, token: str, chat_id: int,
                 actor_id: int | None = None):
    """Envia o custo reportado da tenancy no mês corrente."""
    from ..adapter import tg_send_text

    try:
        custo, budgets = await asyncio.gather(
            usage.get_current_period_usage(),
            usage.get_budgets(),
        )

        emoji = _emoji_custo(custo.total)
        periodo = f"{_MESES[custo.inicio.month - 1]} de {custo.inicio.year}"

        partes = [
            fmt.titulo("💳", "OCI Usage"),
            "",
            f"Período: {periodo}",
            "",
            fmt.tabela([("Total", f"{emoji} {_moeda(custo.total, custo.moeda)}")]),
        ]

        if custo.por_servico:
            partes.append(fmt.secao("Por serviço"))
            partes.append(fmt.tabela([
                (nome[:24], _moeda(valor, custo.moeda))
                for nome, valor in custo.por_servico[:8]
            ]))

        if budgets:
            partes.append(fmt.secao("Budgets"))
            linhas = []
            for b in budgets:
                pct = f"{b.percentual}%" if b.percentual is not None else "n/d"
                linhas.append((
                    b.nome[:20],
                    f"{_moeda(b.gasto, custo.moeda)} / "
                    f"{_moeda(b.limite, custo.moeda)}  ({pct})",
                ))
            partes.append(fmt.tabela(linhas))

        partes.append(
            "__Os dados de faturamento da OCI são consolidados com atraso; "
            "este não é o custo deste instante.__")

        await tg_send_text(client, token, chat_id, "\n".join(partes))
    except oci.exceptions.ServiceError as e:
        await tg_send_text(client, token, chat_id,
            f"💳 **OCI Usage**\n\n{fmt.CRITICO} OCI recusou a chamada\n"
            f"HTTP {e.status} — {e.message}")
    except Exception as e:
        await tg_send_text(client, token, chat_id,
            f"💳 **OCI Usage**\n\n{fmt.NEUTRO} Indisponível\n{e}")
