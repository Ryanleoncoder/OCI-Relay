"""Todo módulo do pacote precisa importar.

Import relativo com a profundidade errada (`...system` onde cabia
`....system`) quebra o módulo inteiro, e o erro só aparece em tempo de
import — não na análise estática.
"""

import importlib
import pkgutil

import pytest

import oci_relay

MODULOS = sorted(
    m.name for m in pkgutil.walk_packages(oci_relay.__path__, "oci_relay.")
    # __main__ executa o bot ao ser importado.
    if not m.name.endswith("__main__")
)


def test_encontrou_modulos():
    assert len(MODULOS) > 20, f"poucos módulos descobertos: {MODULOS}"


@pytest.mark.parametrize("nome", MODULOS)
def test_modulo_importa(nome):
    importlib.import_module(nome)
