"""Handler /usage."""

import asyncio

import oci

from ....config.settings import settings
from ....i18n import t
from ....oci import usage
from .. import formatter as fmt

_MESES = ("January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December")


def _emoji_custo(total: float) -> str:
    """Semáforo de custo pelos limiares do .env."""
    if total >= settings.alert_cost_critical_usd:
        return fmt.CRITICO
    if total >= settings.alert_cost_warning_usd:
        return fmt.AVISO
    return fmt.OK


def _moeda(valor: float, moeda: str) -> str:
    """Abaixo de um centavo mantém quatro casas.

    Arredondar 0.0012 para 0.00 esconderia exatamente o que este comando
    existe para mostrar: uma cobrança que acabou de começar.
    """
    return f"{moeda} {valor:.2f}" if valor >= 0.01 else f"{moeda} {valor:.4f}"


async def handle(client, token: str, chat_id: int,
                 actor_id: int | None = None, args: str = ""):
    """Envia o custo reportado da tenancy no mês corrente."""
    from ..adapter import tg_send_text

    cabecalho = fmt.cabecalho(t("usage.title"))

    try:
        custo, budgets = await asyncio.gather(
            usage.get_current_period_usage(),
            usage.get_budgets(),
        )

        emoji = _emoji_custo(custo.total)
        periodo = f"{_MESES[custo.inicio.month - 1]} {custo.inicio.year}"

        partes = [
            cabecalho,
            "",
            t("usage.period", period=periodo),
            "",
            fmt.tabela([
                (t("usage.total"),
                 f"{emoji} {_moeda(custo.total, custo.moeda)}"),
            ]),
        ]

        if custo.por_servico:
            partes.append(fmt.secao(t("usage.by_service")))
            partes.append(fmt.tabela([
                (nome[:24], _moeda(valor, custo.moeda))
                for nome, valor in custo.por_servico[:8]
            ]))

        if budgets:
            partes.append(fmt.secao(t("usage.budgets")))
            partes.append(fmt.tabela([
                (b.nome[:20],
                 f"{_moeda(b.gasto, custo.moeda)} / "
                 f"{_moeda(b.limite, custo.moeda)}  "
                 f"({b.percentual}%)" if b.percentual is not None
                 else f"{_moeda(b.gasto, custo.moeda)} / "
                      f"{_moeda(b.limite, custo.moeda)}")
                for b in budgets
            ]))

        partes.append(f"__{t('usage.delayed')}__")

        await tg_send_text(client, token, chat_id, "\n".join(partes))
    except oci.exceptions.ServiceError as e:
        await tg_send_text(client, token, chat_id,
            f"{cabecalho}\n\n{fmt.CRITICO} "
            + t("errors.oci_refused", status=e.status, message=e.message))
    except Exception as e:
        await tg_send_text(client, token, chat_id,
            f"{cabecalho}\n\n{fmt.NEUTRO} "
            + t("errors.oci_unavailable", reason=e))
