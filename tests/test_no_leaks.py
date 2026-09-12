"""O código publicado não pode citar planejamento interno.

O planejamento do projeto não é público. Referências às suas seções (§) ou
aos identificadores de task não dizem nada a quem lê o repositório e expõem
a estrutura interna — inclusive dentro das mensagens que o bot envia no
Telegram.

O conjunto auditado vem do `.gitignore`, não de uma lista fixa: se um
arquivo interno for renomeado sem atualizar a regra que o exclui, ele passa
a ser publicável e estes testes falham — que é justamente o alarme
desejado.
"""

import re
from fnmatch import fnmatch
from pathlib import Path

import pytest

from oci_relay.config.paths import project_root

RAIZ = project_root()


def _padroes_ignorados() -> list[str]:
    arquivo = RAIZ / ".gitignore"
    if not arquivo.is_file():
        return []
    return [
        linha.strip()
        for linha in arquivo.read_text(encoding="utf-8").splitlines()
        if linha.strip() and not linha.lstrip().startswith("#")
    ]


_IGNORADOS = _padroes_ignorados()


def _ignorado(caminho: Path) -> bool:
    """Aproxima a semântica do .gitignore para os padrões usados aqui."""
    rel = caminho.relative_to(RAIZ).as_posix()
    for padrao in _IGNORADOS:
        alvo = padrao.rstrip("/")
        if fnmatch(rel, alvo) or rel.startswith(f"{alvo}/"):
            return True
        # Padrão sem barra casa o nome em qualquer nível da árvore.
        if "/" not in alvo and fnmatch(caminho.name, alvo):
            return True
    return False


def _publicos() -> list[Path]:
    candidatos = [
        *(RAIZ / "src").rglob("*.py"),
        RAIZ / "README.md",
        RAIZ / "SECURITY.md",
        *(RAIZ / "docs").glob("*.md"),
    ]
    return sorted(
        p for p in candidatos
        if p.is_file() and "__pycache__" not in p.parts and not _ignorado(p)
    )


FONTES = [p for p in _publicos() if p.suffix == ".py"]
PUBLICOS = _publicos()

TASK = re.compile(r"\b(?:R0|B1|O2|S3|T4|T5|D6|A7|M8|U9|H10|TEST|DOC|DEP)-\d{3}\b")
SECAO_PLANO = re.compile(r"(?:plano|plan)\s*§|§\s*\d+", re.IGNORECASE)


def test_o_conjunto_auditado_nao_esta_vazio():
    """Um filtro largo demais faria os testes abaixo passarem sem checar nada."""
    assert len(PUBLICOS) > 10, f"poucos arquivos auditados: {PUBLICOS}"


def test_arquivo_interno_fica_fora_da_auditoria():
    """Documento interno precisa estar coberto por alguma regra de exclusão."""
    internos = [
        p for p in (RAIZ / "docs").glob("*.md")
        if TASK.search(p.read_text(encoding="utf-8"))
    ]
    for p in internos:
        assert _ignorado(p), (
            f"{p.name} cita tasks internas mas não está no .gitignore — "
            "seria publicado"
        )


@pytest.mark.parametrize("caminho", PUBLICOS, ids=lambda p: p.name)
def test_sem_id_de_task(caminho):
    achados = TASK.findall(caminho.read_text(encoding="utf-8"))
    assert not achados, f"{caminho.name} cita task interna: {achados}"


@pytest.mark.parametrize("caminho", PUBLICOS, ids=lambda p: p.name)
def test_sem_referencia_a_secao_do_plano(caminho):
    achados = SECAO_PLANO.findall(caminho.read_text(encoding="utf-8"))
    assert not achados, f"{caminho.name} referencia o planejamento: {achados}"


@pytest.mark.parametrize("caminho", FONTES, ids=lambda p: p.name)
def test_sem_marcador_de_trabalho_pendente(caminho):
    """TODO/FIXME sinalizam trabalho inacabado para quem lê o repositório."""
    texto = caminho.read_text(encoding="utf-8")
    achados = re.findall(r"\b(?:TODO|FIXME|XXX|HACK)\b", texto)
    assert not achados, f"{caminho.name} tem marcador pendente: {achados}"
