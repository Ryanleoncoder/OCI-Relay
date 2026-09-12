"""Formatação das mensagens e conversão markdown -> HTML do Telegram."""

import pytest

from oci_relay.channels.telegram import formatter as fmt
from oci_relay.channels.telegram.adapter import _markdown_to_telegram_html


class TestSemaforo:
    @pytest.mark.parametrize("valor,esperado", [
        (10.0, fmt.OK),
        (84.9, fmt.OK),
        (85.0, fmt.AVISO),
        (94.9, fmt.AVISO),
        (95.0, fmt.CRITICO),
        (100.0, fmt.CRITICO),
        (None, fmt.NEUTRO),
    ])
    def test_limiares(self, valor, esperado):
        assert fmt.emoji_percentual(valor, 85, 95) == esperado

    def test_zero_e_saudavel_nao_desconhecido(self):
        """0.0 é um valor válido e não pode cair no ramo de None."""
        assert fmt.emoji_percentual(0.0, 85, 95) == fmt.OK


class TestEstadoOci:
    @pytest.mark.parametrize("estado,esperado", [
        ("RUNNING", fmt.OK),
        ("running", fmt.OK),
        ("STOPPED", fmt.CRITICO),
        ("STARTING", fmt.AVISO),
        ("ALGO_NOVO", fmt.NEUTRO),
        (None, fmt.NEUTRO),
    ])
    def test_estados(self, estado, esperado):
        assert fmt.emoji_estado_oci(estado) == esperado


class TestVeredito:
    def test_pior_estado_vence(self):
        assert fmt.CRITICO in fmt.veredito(fmt.OK, fmt.AVISO, fmt.CRITICO)
        assert fmt.AVISO in fmt.veredito(fmt.OK, fmt.AVISO)
        assert fmt.OK in fmt.veredito(fmt.OK, fmt.OK)

    def test_desconhecido_supera_ok(self):
        """Sem dado não se afirma saudável."""
        assert fmt.NEUTRO in fmt.veredito(fmt.OK, fmt.NEUTRO)

    def test_critico_supera_desconhecido(self):
        assert fmt.CRITICO in fmt.veredito(fmt.NEUTRO, fmt.CRITICO)

    def test_sem_argumentos(self):
        assert fmt.NEUTRO in fmt.veredito()


class TestUptime:
    @pytest.mark.parametrize("segundos,esperado", [
        (0, "desconhecido"),
        (None, "desconhecido"),
        (-5, "desconhecido"),
        (90, "1m"),
        (3700, "1h 01m"),
        (1566000, "18d 03h"),
    ])
    def test_formatos(self, segundos, esperado):
        assert fmt.uptime(segundos) == esperado


class TestCarga:
    def test_tupla_vira_texto(self):
        """O load average do psutil é uma tupla e precisa virar texto."""
        assert fmt.carga((0.82, 0.64, 0.51)) == "0.82 / 0.64 / 0.51"

    def test_vazio(self):
        assert fmt.carga(None) == "n/d"


class TestTabela:
    def test_alinha_rotulos(self):
        saida = fmt.tabela([("CPU", "1%"), ("Memory", "2%")])
        assert "```" in saida
        linhas = [l for l in saida.split("\n") if l and "```" not in l]
        # Os valores começam na mesma coluna.
        assert linhas[0].index("1%") == linhas[1].index("2%")

    def test_vazia(self):
        assert fmt.tabela([]) == ""


class TestMarkdownParaHtml:
    def test_negrito(self):
        assert _markdown_to_telegram_html("**oi**") == "<b>oi</b>"

    def test_italico(self):
        """Sem a conversão, os underscores aparecem literais na mensagem."""
        assert _markdown_to_telegram_html("__oi__") == "<i>oi</i>"

    def test_bloco_vira_pre(self):
        saida = _markdown_to_telegram_html("```\na  1\nb  2\n```")
        assert saida == "<pre>a  1\nb  2</pre>"

    def test_bloco_preserva_espacos(self):
        """Fora de <pre> o conversor faz strip() e o alinhamento se perde."""
        saida = _markdown_to_telegram_html("```\nCPU     1%\n```")
        assert "CPU     1%" in saida

    def test_escapa_html(self):
        saida = _markdown_to_telegram_html("a < b & c")
        assert "&lt;" in saida and "&amp;" in saida

    def test_nao_implementado_sobrevive(self):
        saida = _markdown_to_telegram_html(fmt.nao_implementado("Teste"))
        assert "🚧" in saida and "Teste" in saida
        assert "__" not in saida
