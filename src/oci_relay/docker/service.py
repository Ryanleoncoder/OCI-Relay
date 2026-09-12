"""Integração Docker via API."""

try:
    import docker
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False

_DAEMON_OFF = "Docker nao disponivel neste host (daemon nao esta acessivel)."


def _connect():
    """Conecta ao daemon, distinguindo 'daemon ausente' de erro real."""
    try:
        return docker.from_env()
    except docker.errors.DockerException:
        return None


def get_containers():
    if not DOCKER_AVAILABLE:
        return {"error": "Docker SDK não instalado"}

    try:
        client = _connect()
        if client is None:
            return {"error": _DAEMON_OFF}
        containers = []

        for c in client.containers.list(all=True):
            containers.append({
                'id': c.short_id,
                'name': c.name,
                'status': c.status,
                'image': c.image.tags[0] if c.image.tags else 'none',
                'uptime': (c.attrs['State']['Status'] == 'running'
                           and c.attrs['State'].get('StartedAt', '')),
                'restart_count': c.attrs['RestartCount']
            })

        return containers
    except Exception as e:
        return {'error': str(e)}


def get_container_stats(name):
    if not DOCKER_AVAILABLE:
        return {"error": "Docker SDK não instalado"}

    try:
        client = _connect()
        if client is None:
            return {"error": _DAEMON_OFF}
        container = client.containers.get(name)
        stats = container.stats(stream=False)
        return stats
    except Exception as e:
        return {'error': str(e)}


def get_container_logs(name, tail=50):
    if not DOCKER_AVAILABLE:
        return {"error": "Docker SDK não instalado"}

    try:
        client = _connect()
        if client is None:
            return {"error": _DAEMON_OFF}
        container = client.containers.get(name)
        logs = container.logs(tail=tail).decode('utf-8')
        return logs
    except Exception as e:
        return {'error': str(e)}
