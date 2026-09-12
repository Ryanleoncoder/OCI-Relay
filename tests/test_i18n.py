"""Catálogo de mensagens.

O modo de falha próprio deste desenho é a chave que existe no código e não
no arquivo: só apareceria quando alguém rodasse aquele comando. Os testes
abaixo comparam os dois lados.
"""

import re
from pathlib import Path

import pytest

from oci_relay import i18n
from oci_relay.config.paths import project_root

RAIZ = project_root()

# t("chave") ou t("chave", x=1) — a chave é sempre literal, nunca variável,
# justamente para poder ser conferida estaticamente.
USO = re.compile(r"\bt\(\s*[\"']([a-z0-9_.]+)[\"']")


@pytest.fixture(autouse=True)
def idioma_limpo():
    i18n.definir_idioma(i18n.IDIOMA_PADRAO)
    yield
    i18n.definir_idioma(i18n.IDIOMA_PADRAO)


def _chaves_usadas() -> dict[str, set[str]]:
    usos: dict[str, set[str]] = {}
    for p in (RAIZ / "src").rglob("*.py"):
        if "__pycache__" in p.parts or p.name == "i18n.py":
            continue
        achadas = set(USO.findall(p.read_text(encoding="utf-8")))
        if achadas:
            usos[str(p.relative_to(RAIZ))] = achadas
    return usos


class TestCatalogo:
    def test_idioma_padrao_existe(self):
        assert i18n.IDIOMA_PADRAO in i18n.idiomas_disponiveis()

    def test_catalogo_nao_esta_vazio(self):
        assert len(i18n.chaves()) > 50

    def test_aninhamento_vira_chave_pontilhada(self):
        assert "power.suspend_title" in i18n.chaves()

    def test_nenhum_valor_vazio(self):
        catalogo = i18n.carregar(i18n.IDIOMA_PADRAO)
        vazias = [c for c, v in catalogo.items() if not v.strip()]
        assert not vazias


class TestBusca:
    def test_devolve_o_texto(self):
        assert i18n.t("confirmation.confirm") == "✅ Confirm"

    def test_interpola(self):
        texto = i18n.t("common.not_implemented", feature="Alerts")
        assert "Alerts" in texto

    def test_chave_ausente_devolve_a_chave(self):
        """Painel feio é melhor que comando sem resposta."""
        assert i18n.t("nao.existe") == "nao.existe"

    def test_placeholder_sem_valor_nao_estoura(self):
        """Texto cru chega ao usuário; a exceção não sobe ao polling."""
        assert i18n.t("common.not_implemented") == "🚧 {feature} is not implemented yet."

    def test_valor_extra_e_ignorado(self):
        assert i18n.t("common.overall", irrelevante=1) == "Overall"


class TestIdioma:
    def test_troca_e_volta(self):
        i18n.definir_idioma("pt_BR")
        assert i18n.idioma_atual() == "pt_BR"
        i18n.definir_idioma("en")
        assert i18n.idioma_atual() == "en"

    def test_idioma_inexistente_cai_no_padrao(self):
        """Catálogo faltando não pode deixar o bot mudo."""
        i18n.definir_idioma("xx")
        assert i18n.t("confirmation.confirm") == "✅ Confirm"


class TestCoerenciaComOCodigo:
    def test_toda_chave_usada_existe_no_catalogo(self):
        disponiveis = i18n.chaves()
        faltando = {
            arquivo: sorted(usadas - disponiveis)
            for arquivo, usadas in _chaves_usadas().items()
            if usadas - disponiveis
        }
        assert not faltando, f"chaves ausentes do catálogo: {faltando}"

    @pytest.mark.parametrize("idioma", i18n.idiomas_disponiveis())
    def test_traducao_cobre_o_padrao(self, idioma):
        """Idioma incompleto cai no padrão, mas a lacuna deve ser visível."""
        faltando = i18n.chaves() - set(i18n.carregar(idioma))
        assert not faltando, f"{idioma} não traduz: {sorted(faltando)}"

    @pytest.mark.parametrize("idioma", i18n.idiomas_disponiveis())
    def test_placeholders_batem_entre_idiomas(self, idioma):
        """Placeholder perdido na tradução vira texto cru para o usuário."""
        padrao = i18n.carregar(i18n.IDIOMA_PADRAO)
        traducao = i18n.carregar(idioma)
        marcador = re.compile(r"\{(\w+)\}")

        divergentes = {}
        for chave, texto in padrao.items():
            if chave not in traducao:
                continue
            esperados = set(marcador.findall(texto))
            obtidos = set(marcador.findall(traducao[chave]))
            if esperados != obtidos:
                divergentes[chave] = (sorted(esperados), sorted(obtidos))
        assert not divergentes, f"{idioma}: {divergentes}"


class TestArquivo:
    def test_acompanha_o_pacote(self):
        """Instalação sem os .yml deixaria o bot sem mensagens."""
        assert (Path(i18n.__file__).parent / "locales" / "en.yml").is_file()

    def test_declarado_como_package_data(self):
        toml = (RAIZ / "pyproject.toml").read_text(encoding="utf-8")
        assert "locales/*.yml" in toml
