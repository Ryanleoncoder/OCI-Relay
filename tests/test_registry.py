"""Registro de comandos.

Menu, ajuda e roteamento precisam descrever exatamente o mesmo conjunto:
comando anunciado que não responde, e comando que responde sem ser
anunciado, são os dois defeitos que estes testes impedem.
"""

import asyncio
import inspect

import pytest

from oci_relay.channels.telegram import registry


class TestFonteUnica:
    def test_menu_e_ajuda_cobrem_os_mesmos_comandos(self):
        menu = {c["command"] for c in registry.para_telegram()}
        ajuda = {
            linha.split(" ")[0].lstrip("/")
            for linha in registry.texto_de_ajuda().splitlines()
        }
        assert menu == ajuda

    def test_tudo_que_aparece_no_menu_e_roteavel(self):
        """Comando anunciado que não responde é pior que comando ausente."""
        for entrada in registry.para_telegram():
            assert registry.buscar(entrada["command"]) is not None

    def test_tudo_que_e_roteavel_aparece(self):
        """O caminho inverso: comando que responde precisa ser descobrível.

        Apelidos são a exceção deliberada: existem para não quebrar quem
        digita o nome antigo, e anunciá-los duplicaria o menu.
        """
        visiveis = {c.nome for c in registry.visiveis()}
        apelidos = {a for c in registry.COMANDOS for a in c.apelidos}

        for nome, comando in registry.POR_NOME.items():
            if comando.oculto or nome in apelidos:
                continue
            assert nome in visiveis


class TestApelidos:
    @pytest.mark.parametrize("antigo,novo", [
        ("suspender", "stop"),
        ("reiniciar", "restart"),
        ("reativar", "poweron"),
    ])
    def test_nome_antigo_continua_respondendo(self, antigo, novo):
        assert registry.buscar(antigo) is registry.buscar(novo)

    def test_apelido_nao_aparece_no_menu(self):
        """Menu duplicado confunde; o apelido serve só à memória muscular."""
        menu = {c["command"] for c in registry.para_telegram()}
        for comando in registry.COMANDOS:
            for apelido in comando.apelidos:
                assert apelido not in menu

    def test_apelido_nao_colide_com_comando(self):
        nomes = {c.nome for c in registry.COMANDOS}
        for comando in registry.COMANDOS:
            for apelido in comando.apelidos:
                assert apelido not in nomes


class TestDefinicoes:
    def test_nao_ha_nome_repetido(self):
        nomes = [c.nome for c in registry.COMANDOS]
        assert len(nomes) == len(set(nomes))

    @pytest.mark.parametrize("comando", registry.COMANDOS, ids=lambda c: c.nome)
    def test_nome_valido_para_o_telegram(self, comando):
        """O Telegram aceita só minúsculas, dígitos e underscore, até 32."""
        assert comando.nome.islower()
        assert 1 <= len(comando.nome) <= 32
        assert comando.nome.replace("_", "").isalnum()

    @pytest.mark.parametrize("comando", registry.COMANDOS, ids=lambda c: c.nome)
    def test_descricao_dentro_do_limite(self, comando):
        """Descrição acima de 256 caracteres faz o setMyCommands falhar."""
        assert 1 <= len(comando.descricao) <= 256

    @pytest.mark.parametrize("comando", registry.COMANDOS, ids=lambda c: c.nome)
    def test_handler_tem_a_assinatura_esperada(self, comando):
        if comando.handler is None:
            return
        assert asyncio.iscoroutinefunction(comando.handler)
        parametros = list(inspect.signature(comando.handler).parameters)
        assert parametros == ["client", "token", "chat_id", "actor_id", "args"]

    @pytest.mark.parametrize("comando", registry.COMANDOS, ids=lambda c: c.nome)
    def test_handler_recebe_quem_pediu(self, comando):
        """actor_id amarra confirmações à pessoa, não ao chat."""
        if comando.handler is None:
            return
        assert "actor_id" in inspect.signature(comando.handler).parameters

    @pytest.mark.parametrize("comando", registry.COMANDOS, ids=lambda c: c.nome)
    def test_handler_recebe_argumentos(self, comando):
        """Comandos como /language e /container leem o resto da mensagem."""
        if comando.handler is None:
            return
        assert "args" in inspect.signature(comando.handler).parameters


class TestBusca:
    @pytest.mark.parametrize("entrada", ["/health", "health", "/HEALTH", "Health"])
    def test_aceita_variacoes(self, entrada):
        assert registry.buscar(entrada).nome == "health"

    def test_desconhecido_devolve_none(self):
        assert registry.buscar("/naoexiste") is None

    def test_start_e_help_nao_tem_handler(self):
        """Os dois respondem com a própria lista, montada pelo adapter."""
        assert registry.buscar("start").handler is None
        assert registry.buscar("help").handler is None


class TestCoberturaDosHandlers:
    def test_todo_handler_esta_registrado(self):
        """Um handler novo sem entrada no registro é código inalcançável."""
        import importlib
        from pathlib import Path

        from oci_relay.channels.telegram import handlers

        # Módulos sem `handle` são auxiliares compartilhados, não comandos.
        modulos = set()
        for p in Path(handlers.__file__).parent.glob("*.py"):
            if p.stem == "__init__":
                continue
            mod = importlib.import_module(f"{handlers.__name__}.{p.stem}")
            if hasattr(mod, "handle"):
                modulos.add(p.stem)
        registrados = {
            c.handler.__module__.rsplit(".", 1)[-1]
            for c in registry.COMANDOS if c.handler is not None
        }
        assert modulos == registrados, (
            f"handlers sem comando: {sorted(modulos - registrados)}; "
            f"comandos sem handler: {sorted(registrados - modulos)}"
        )
