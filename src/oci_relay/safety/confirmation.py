"""Confirmação de ações que alteram a infraestrutura.

Nenhuma mutação acontece por um único toque. O comando cria uma confirmação
pendente, o usuário aprova, e só então a ação executa.

O que a confirmação amarra, e por quê:

- **actor** — só quem pediu pode confirmar. Num grupo, ninguém aprova a
  ação alheia.
- **comando e alvo** — a aprovação vale para aquela ação naquela máquina,
  não para "a última coisa pendente".
- **nonce** — identificador aleatório que viaja no botão. Serve para o
  clique apontar a confirmação exata, sem depender de ordem ou de estado
  na memória do processo.
- **expiração** — botão antigo numa conversa rolada para cima não pode
  desligar uma máquina meia hora depois.
- **uso único** — confirmar duas vezes não executa duas vezes.

O estado é persistido: reiniciar o bot não pode ressuscitar um nonce já
gasto nem invalidar silenciosamente uma confirmação em aberto.
"""

import datetime as dt
import logging
import secrets
from dataclasses import dataclass
from enum import Enum

from ..state import get_connection

log = logging.getLogger(__name__)

# Curto o bastante para que um botão esquecido na conversa não sirva mais.
TTL_PADRAO_SEGUNDOS = 90

# 16 bytes urlsafe. O nonce viaja no callback_data do Telegram, limitado a
# 64 bytes no total, contando o prefixo da ação.
_TAMANHO_NONCE = 16


class Estado(str, Enum):
    PENDENTE = "PENDING"
    CONFIRMADA = "CONFIRMED"
    CANCELADA = "CANCELLED"
    EXPIRADA = "EXPIRED"
    EXECUTADA = "EXECUTED"
    FALHOU = "FAILED"


class Recusa(str, Enum):
    """Motivo pelo qual uma confirmação não pôde ser aceita."""
    DESCONHECIDA = "desconhecida"
    EXPIRADA = "expirada"
    OUTRO_ATOR = "outro_ator"
    JA_RESOLVIDA = "ja_resolvida"


@dataclass(frozen=True)
class Confirmacao:
    nonce: str
    actor_id: int
    chat_id: int
    comando: str
    alvo: str | None
    estado: Estado
    criado_em: dt.datetime
    expira_em: dt.datetime

    @property
    def segundos_restantes(self) -> int:
        delta = (self.expira_em - _agora()).total_seconds()
        return max(0, int(delta))


def _agora() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _texto(momento: dt.datetime) -> str:
    return momento.isoformat()


def _momento(texto: str) -> dt.datetime:
    return dt.datetime.fromisoformat(texto)


def _da_linha(linha) -> Confirmacao:
    return Confirmacao(
        nonce=linha["nonce"],
        actor_id=linha["actor_id"],
        chat_id=linha["chat_id"],
        comando=linha["comando"],
        alvo=linha["alvo"],
        estado=Estado(linha["estado"]),
        criado_em=_momento(linha["criado_em"]),
        expira_em=_momento(linha["expira_em"]),
    )


def criar(actor_id: int, chat_id: int, comando: str, alvo: str | None = None,
          ttl_segundos: int = TTL_PADRAO_SEGUNDOS) -> Confirmacao:
    """Registra uma confirmação pendente e devolve o nonce a enviar."""
    agora = _agora()
    confirmacao = Confirmacao(
        nonce=secrets.token_urlsafe(_TAMANHO_NONCE),
        actor_id=actor_id,
        chat_id=chat_id,
        comando=comando,
        alvo=alvo,
        estado=Estado.PENDENTE,
        criado_em=agora,
        expira_em=agora + dt.timedelta(seconds=ttl_segundos),
    )

    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO confirmations"
            " (nonce, actor_id, chat_id, comando, alvo, estado,"
            "  criado_em, expira_em)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (confirmacao.nonce, actor_id, chat_id, comando, alvo,
             Estado.PENDENTE.value, _texto(agora), _texto(confirmacao.expira_em)),
        )
        conn.commit()
    finally:
        conn.close()

    log.info("Confirmação pendente: %s para %s (ator %s)",
             confirmacao.nonce[:8], comando, actor_id)
    return confirmacao


def buscar(nonce: str) -> Confirmacao | None:
    conn = get_connection()
    try:
        linha = conn.execute(
            "SELECT * FROM confirmations WHERE nonce = ?", (nonce,)).fetchone()
    finally:
        conn.close()
    return _da_linha(linha) if linha else None


def _resolver(nonce: str, actor_id: int, novo_estado: Estado
              ) -> tuple[Confirmacao | None, Recusa | None]:
    """Transição atômica de PENDENTE para o estado pedido.

    A checagem e a escrita acontecem na mesma transação: duas confirmações
    simultâneas do mesmo nonce não podem passar as duas.
    """
    conn = get_connection()
    try:
        with conn:  # BEGIN/COMMIT automático, ROLLBACK em exceção
            linha = conn.execute(
                "SELECT * FROM confirmations WHERE nonce = ?", (nonce,)
            ).fetchone()

            if linha is None:
                return None, Recusa.DESCONHECIDA

            confirmacao = _da_linha(linha)

            if confirmacao.actor_id != actor_id:
                log.warning("Confirmação %s recusada: ator %s não é o autor %s",
                            nonce[:8], actor_id, confirmacao.actor_id)
                return confirmacao, Recusa.OUTRO_ATOR

            if confirmacao.estado is not Estado.PENDENTE:
                return confirmacao, Recusa.JA_RESOLVIDA

            if _agora() >= confirmacao.expira_em:
                conn.execute(
                    "UPDATE confirmations SET estado = ?, resolvido_em = ?"
                    " WHERE nonce = ? AND estado = ?",
                    (Estado.EXPIRADA.value, _texto(_agora()), nonce,
                     Estado.PENDENTE.value),
                )
                return confirmacao, Recusa.EXPIRADA

            alterados = conn.execute(
                "UPDATE confirmations SET estado = ?, resolvido_em = ?"
                " WHERE nonce = ? AND estado = ?",
                (novo_estado.value, _texto(_agora()), nonce,
                 Estado.PENDENTE.value),
            ).rowcount

            if alterados != 1:
                # Outra transação resolveu entre a leitura e a escrita.
                return confirmacao, Recusa.JA_RESOLVIDA

        return buscar(nonce), None
    finally:
        conn.close()


def confirmar(nonce: str, actor_id: int
              ) -> tuple[Confirmacao | None, Recusa | None]:
    """Aprova uma confirmação pendente. Só o autor pode."""
    return _resolver(nonce, actor_id, Estado.CONFIRMADA)


def cancelar(nonce: str, actor_id: int
             ) -> tuple[Confirmacao | None, Recusa | None]:
    """Cancela uma confirmação pendente. Só o autor pode."""
    return _resolver(nonce, actor_id, Estado.CANCELADA)


def marcar_resultado(nonce: str, sucesso: bool) -> None:
    """Registra o desfecho da ação executada após a confirmação."""
    estado = Estado.EXECUTADA if sucesso else Estado.FALHOU
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE confirmations SET estado = ?, resolvido_em = ?"
            " WHERE nonce = ?",
            (estado.value, _texto(_agora()), nonce),
        )
        conn.commit()
    finally:
        conn.close()


def expirar_vencidas() -> int:
    """Marca como expiradas as pendentes cujo prazo passou."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "UPDATE confirmations SET estado = ?, resolvido_em = ?"
            " WHERE estado = ? AND expira_em <= ?",
            (Estado.EXPIRADA.value, _texto(_agora()),
             Estado.PENDENTE.value, _texto(_agora())),
        )
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()
