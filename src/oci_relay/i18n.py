"""Catálogo de mensagens da interface.

As strings ficam em `locales/<idioma>.yml`, fora do código. Adicionar um
idioma é acrescentar um arquivo; nada em Python precisa mudar.

Uma chave ausente nunca interrompe uma resposta: `t()` devolve a própria
chave e registra o problema. Um painel com `health.title` no lugar do
título é ruim, mas um comando que não responde é pior.
"""

import logging
from contextvars import ContextVar
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger(__name__)

IDIOMA_PADRAO = "en"
DIRETORIO = Path(__file__).parent / "locales"

_catalogos: dict[str, dict] = {}

# ContextVar e nao variavel de modulo: o adapter processa conversas em
# tarefas distintas, e um valor global faria uma trocar o idioma da outra
# no meio da resposta.
_idioma: ContextVar[str] = ContextVar("idioma", default=IDIOMA_PADRAO)


def _achatar(dados: dict, prefixo: str = "") -> dict[str, str]:
    """Converte o YAML aninhado em chaves pontilhadas.

    `health: {title: Health}` vira `{"health.title": "Health"}`, para que
    o código referencie um identificador estável independente de como o
    arquivo está organizado.
    """
    plano: dict[str, str] = {}
    for chave, valor in dados.items():
        completa = f"{prefixo}{chave}"
        if isinstance(valor, dict):
            plano.update(_achatar(valor, f"{completa}."))
        else:
            plano[completa] = str(valor)
    return plano


def carregar(idioma: str) -> dict[str, str]:
    """Lê e memoriza o catálogo de um idioma."""
    if idioma in _catalogos:
        return _catalogos[idioma]

    arquivo = DIRETORIO / f"{idioma}.yml"
    if not arquivo.is_file():
        log.error("Catálogo de mensagens não encontrado: %s", arquivo)
        _catalogos[idioma] = {}
        return _catalogos[idioma]

    dados = yaml.safe_load(arquivo.read_text(encoding="utf-8")) or {}
    _catalogos[idioma] = _achatar(dados)
    return _catalogos[idioma]


def definir_idioma(idioma: str) -> None:
    _idioma.set(idioma)


def idioma_atual() -> str:
    return _idioma.get()


def idiomas_disponiveis() -> list[str]:
    return sorted(p.stem for p in DIRETORIO.glob("*.yml"))


def resolver(codigo: str | None) -> str | None:
    """Converte o código de idioma do Telegram no catálogo correspondente.

    O Telegram envia BCP-47 em minúsculas — `pt-br`, `en`, `es-419`. A
    correspondência é tentada primeiro completa (`pt-br` -> `pt_BR`) e
    depois só pelo idioma (`es-419` -> `es`), para que uma variante
    regional sem catálogo próprio caia no idioma base.

    Devolve None quando não há catálogo, deixando a decisão com quem chamou.
    """
    if not codigo:
        return None

    disponiveis = idiomas_disponiveis()
    por_codigo = {c.lower(): c for c in disponiveis}
    normalizado = codigo.strip().lower().replace("-", "_")

    if normalizado in por_codigo:
        return por_codigo[normalizado]

    # Sem correspondência exata, basta o idioma: `pt_pt` encontra `pt_BR`,
    # porque um português serve melhor que o inglês padrão.
    base = normalizado.split("_")[0]
    for codigo_disponivel in disponiveis:
        if codigo_disponivel.lower().split("_")[0] == base:
            return codigo_disponivel

    return None


def t(chave: str, **valores: Any) -> str:
    """Texto da chave, com os valores interpolados.

    Cai no idioma padrão quando a chave falta no idioma atual, e na
    própria chave quando falta nos dois.
    """
    atual = _idioma.get()
    catalogo = carregar(atual)
    texto = catalogo.get(chave)

    if texto is None and atual != IDIOMA_PADRAO:
        texto = carregar(IDIOMA_PADRAO).get(chave)

    if texto is None:
        log.warning("Mensagem ausente no catálogo: %s", chave)
        return chave

    if not valores:
        return texto

    try:
        return texto.format(**valores)
    except (KeyError, IndexError) as e:
        # Placeholder sem valor correspondente: entrega o texto cru em vez
        # de deixar a exceção subir até o loop de polling.
        log.warning("Interpolação falhou em %s: %s", chave, e)
        return texto


def chaves() -> set[str]:
    """Chaves do idioma padrão, para conferência pelos testes."""
    return set(carregar(IDIOMA_PADRAO))
