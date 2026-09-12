"""Resolução dinâmica dos caminhos do projeto.

Nada aqui é hardcoded: cada caminho pode ser sobrescrito por variável de
ambiente (útil no deploy via systemd, onde o pacote não fica na árvore do
repositório) e, na ausência dela, é inferido a partir da localização deste
módulo.
"""

import os
from pathlib import Path

from dotenv import find_dotenv

# .../src/oci_relay/config/paths.py -> .../  (raiz do repositório)
_RAIZ_INFERIDA = Path(__file__).resolve().parents[3]


def project_root() -> Path:
    """Raiz do projeto: `OCI_RELAY_HOME` ou a raiz inferida do pacote."""
    override = os.getenv("OCI_RELAY_HOME", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return _RAIZ_INFERIDA


def env_file() -> Path | None:
    """Localiza o `.env`, ou None se não houver.

    Ordem: `OCI_RELAY_ENV_FILE`, busca a partir do diretório atual para
    cima, e por último a raiz do projeto.
    """
    override = os.getenv("OCI_RELAY_ENV_FILE", "").strip()
    if override:
        caminho = Path(override).expanduser()
        return caminho if caminho.is_file() else None

    achado = find_dotenv(usecwd=True)
    if achado:
        return Path(achado)

    candidato = project_root() / ".env"
    return candidato if candidato.is_file() else None


def state_dir() -> Path:
    """Diretório de estado local: `OCI_RELAY_STATE_DIR` ou `<raiz>/state`."""
    override = os.getenv("OCI_RELAY_STATE_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return project_root() / "state"
