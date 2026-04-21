from flask import current_app
from sqlalchemy import create_engine, text
from sshtunnel import SSHTunnelForwarder

_engine = None
_tunnel = None


def _start_ssh_tunnel():
    global _tunnel

    if _tunnel is not None and _tunnel.is_active:
        return _tunnel

    app = current_app

    ssh_host = app.config["SSH_HOST"]
    ssh_port = app.config["SSH_PORT"]
    ssh_username = app.config["SSH_USERNAME"]
    ssh_password = app.config["SSH_PASSWORD"]
    ssh_private_key = app.config["SSH_PRIVATE_KEY"]
    ssh_private_key_password = app.config["SSH_PRIVATE_KEY_PASSWORD"]

    db_host = app.config["DB_HOST"]
    db_port = app.config["DB_PORT"]

    tunnel_kwargs = {
        "ssh_address_or_host": (ssh_host, ssh_port),
        "ssh_username": ssh_username,
        "remote_bind_address": (db_host, db_port),
    }

    if ssh_private_key:
        tunnel_kwargs["ssh_pkey"] = ssh_private_key
        if ssh_private_key_password:
            tunnel_kwargs["ssh_private_key_password"] = ssh_private_key_password
    elif ssh_password:
        tunnel_kwargs["ssh_password"] = ssh_password
    else:
        raise ValueError(
            "No SSH authentication method provided. Set SSH_PASSWORD or SSH_PRIVATE_KEY."
        )

    _tunnel = SSHTunnelForwarder(**tunnel_kwargs)
    _tunnel.start()
    return _tunnel


def get_engine():
    global _engine

    if _engine is not None:
        return _engine

    tunnel = _start_ssh_tunnel()
    app = current_app

    db_user = app.config["DB_USER"]
    db_password = app.config["DB_PASSWORD"]
    db_name = app.config["DB_NAME"]
    local_port = tunnel.local_bind_port

    database_url = (
        f"postgresql+psycopg2://{db_user}:{db_password}"
        f"@127.0.0.1:{local_port}/{db_name}"
    )

    _engine = create_engine(
        database_url,
        future=True,
        pool_size=app.config["SQLALCHEMY_POOL_SIZE"],
        max_overflow=app.config["SQLALCHEMY_MAX_OVERFLOW"],
        pool_pre_ping=app.config["SQLALCHEMY_POOL_PRE_PING"],
    )
    return _engine


def fetch_all(query, params=None):
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text(query), params or {})
        return [dict(row._mapping) for row in result]


def fetch_one(query, params=None):
    rows = fetch_all(query, params)
    return rows[0] if rows else None


def execute_query(query, params=None):
    engine = get_engine()
    with engine.begin() as conn:
        result = conn.execute(text(query), params or {})
        return result.rowcount


def close_db():
    global _engine, _tunnel

    if _engine is not None:
        _engine.dispose()
        _engine = None

    if _tunnel is not None:
        _tunnel.stop()
        _tunnel = None