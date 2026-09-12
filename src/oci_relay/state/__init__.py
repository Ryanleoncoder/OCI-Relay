"""Persistência SQLite."""

import sqlite3
from pathlib import Path

from ..config.paths import state_dir

_schema_pronto = False


def db_path() -> Path:
    """Caminho do banco, resolvido em tempo de execução."""
    return state_dir() / "oci_relay.db"


def get_connection() -> sqlite3.Connection:
    """Obtém conexão com SQLite, criando o schema na primeira vez."""
    global _schema_pronto

    caminho = db_path()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(caminho))
    conn.row_factory = sqlite3.Row

    if not _schema_pronto:
        _criar_schema(conn)
        _schema_pronto = True

    return conn


def _criar_schema(conn: sqlite3.Connection):
    """Cria as tabelas se ainda não existirem."""
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS baseline (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            level TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cooldowns (
            watcher TEXT PRIMARY KEY,
            last_alert TIMESTAMP,
            state TEXT DEFAULT 'normal'
        )
    """)

    # Confirmações pendentes precisam sobreviver a restart: sem isso, um
    # reinício invalidaria uma confirmação em aberto ou, pior, permitiria
    # reaproveitar um nonce já usado.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS confirmations (
            nonce TEXT PRIMARY KEY,
            actor_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            comando TEXT NOT NULL,
            alvo TEXT,
            estado TEXT NOT NULL,
            criado_em TEXT NOT NULL,
            expira_em TEXT NOT NULL,
            resolvido_em TEXT
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_confirmations_estado
        ON confirmations (estado, expira_em)
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            target TEXT,
            result TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Não fecha: a conexão segue em uso por quem chamou get_connection().
    conn.commit()


def get_baseline(key: str) -> str | None:
    """Obtém valor do baseline."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM baseline WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row["value"] if row else None


def set_baseline(key: str, value: str):
    """Salva valor no baseline."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO baseline (key, value) VALUES (?, ?)",
        (key, value)
    )
    conn.commit()
    conn.close()


def log_alert(type_: str, level: str, message: str):
    """Registra alerta."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO alerts (type, level, message) VALUES (?, ?, ?)",
        (type_, level, message)
    )
    conn.commit()
    conn.close()


def get_cooldown(watcher: str) -> dict | None:
    """Obtém estado de cooldown."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cooldowns WHERE watcher = ?", (watcher,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def set_cooldown(watcher: str, state: str, last_alert: str | None = None):
    """Atualiza cooldown."""
    conn = get_connection()
    cursor = conn.cursor()
    if last_alert:
        cursor.execute(
            "INSERT OR REPLACE INTO cooldowns (watcher, state, last_alert)"
            " VALUES (?, ?, ?)",
            (watcher, state, last_alert)
        )
    else:
        cursor.execute(
            "INSERT OR REPLACE INTO cooldowns (watcher, state) VALUES (?, ?)",
            (watcher, state)
        )
    conn.commit()
    conn.close()


def log_audit(action: str, target: str | None = None, result: str | None = None):
    """Registra ação no audit log."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO audit_log (action, target, result) VALUES (?, ?, ?)",
        (action, target, result)
    )
    conn.commit()
    conn.close()
