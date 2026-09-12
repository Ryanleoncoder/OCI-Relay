#!/usr/bin/env python3
"""Entrada do OCI Relay."""

import asyncio
import logging

from dotenv import load_dotenv

from .config.paths import env_file

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger(__name__)

# Precisa rodar antes de qualquer import que leia settings.
_ENV = env_file()
if _ENV:
    load_dotenv(_ENV)
else:
    log.warning("Nenhum .env encontrado; usando apenas variáveis de ambiente.")


async def _reportar_hospedagem():
    """Diz se o Relay roda na própria instância que monitora.

    Determina se as ações de energia são reversíveis pelo Telegram: parar a
    instância que hospeda o bot o mata junto, e só o console religa.
    """
    from .oci import rodando_na_instancia_alvo

    if await rodando_na_instancia_alvo():
        log.warning(
            "Hospedagem: o Relay roda NA instância monitorada — parar a "
            "instância derruba o bot e a religação exige o console da OCI."
        )
    else:
        log.info("Hospedagem: o Relay roda fora da instância monitorada.")


async def main():
    log.info("OCI Relay v0.1.0 iniciando...")
    if _ENV:
        log.info("Config carregada de %s", _ENV)

    try:
        from .oci import validate_auth
    except (ValueError, FileNotFoundError) as e:
        log.error("Configuração inválida: %s", e)
        return

    # OCI indisponível não derruba o bot: os comandos locais seguem servindo
    # e os comandos OCI respondem com o erro.
    log.info("Validando autenticação OCI...")
    if validate_auth():
        log.info("OCI: OK")
        await _reportar_hospedagem()
    else:
        log.warning(
            "OCI: indisponível — /status e /summary vão reportar o erro; "
            "os comandos locais seguem funcionando."
        )

    from .channels.telegram.adapter import bot_manager

    log.info("Iniciando gateway Telegram...")
    bot_manager.start()

    log.info("OCI Relay rodando. Pressione Ctrl+C para parar.")

    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        log.info("OCI Relay parando...")
        bot_manager.stop()


def run():
    """Ponto de entrada sincrono (`python -m oci_relay` e console script)."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("OCI Relay parado.")


if __name__ == "__main__":
    run()
