"""Verificação de portas em escuta."""

import os
import socket

import psutil

# Endereços que aceitam conexão de qualquer origem.
_ABRANGENTES = {"0.0.0.0", "::", "*"}

DESCONHECIDO = "?"


def _nome_processo(pid: int | None) -> str:
    """Nome do processo dono do socket, ou '?' se inacessível."""
    if not pid:
        return DESCONHECIDO
    try:
        return psutil.Process(pid).name()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return DESCONHECIDO


def identificacao_limitada(portas: list) -> bool:
    """Indica se faltam nomes de processo por falta de privilégio.

    No Linux a lista de sockets vem de /proc/net/tcp, legível por qualquer
    usuário, mas associar o socket ao processo exige ler /proc/<pid>/fd —
    possível apenas para processos do próprio usuário. Rodando sem root,
    a maioria dos donos fica desconhecida.
    """
    if not portas or os.name != "posix":
        return False
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return False

    desconhecidos = sum(1 for p in portas if p["process"] == DESCONHECIDO)
    return desconhecidos > len(portas) / 2


def get_listening_ports() -> list:
    """Sockets em escuta, um por (endereço, porta, protocolo).

    Um mesmo serviço costuma escutar em IPv4 e IPv6, gerando entradas
    distintas; a deduplicação evita repetir o mesmo socket.
    """
    vistos = set()
    portas = []

    for conn in psutil.net_connections(kind="inet"):
        if conn.status != psutil.CONN_LISTEN or not conn.laddr:
            continue

        proto = "tcp" if conn.type == socket.SOCK_STREAM else "udp"
        chave = (conn.laddr.ip, conn.laddr.port, proto)
        if chave in vistos:
            continue
        vistos.add(chave)

        portas.append({
            "port": conn.laddr.port,
            "address": conn.laddr.ip,
            "proto": proto,
            "pid": conn.pid,
            "process": _nome_processo(conn.pid),
            "public": conn.laddr.ip in _ABRANGENTES,
        })

    portas.sort(key=lambda p: (p["port"], p["proto"]))
    return portas


def get_listening_ports_summary() -> list:
    """Portas agrupadas, uma entrada por porta/protocolo.

    Junta os bindings IPv4 e IPv6 do mesmo serviço e marca como pública a
    porta que escute em qualquer endereço abrangente.
    """
    agrupado: dict[tuple[int, str], dict] = {}

    for p in get_listening_ports():
        chave = (p["port"], p["proto"])
        entrada = agrupado.get(chave)
        if entrada is None:
            agrupado[chave] = {
                "port": p["port"],
                "proto": p["proto"],
                "addresses": [p["address"]],
                "process": p["process"],
                "public": p["public"],
            }
            continue

        entrada["addresses"].append(p["address"])
        entrada["public"] = entrada["public"] or p["public"]
        if entrada["process"] == "?":
            entrada["process"] = p["process"]

    return sorted(agrupado.values(), key=lambda p: (p["port"], p["proto"]))
