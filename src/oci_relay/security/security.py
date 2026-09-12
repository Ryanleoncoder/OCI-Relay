"""Verificação de segurança."""

import subprocess


def get_fail2ban_status():
    """Obtém status do Fail2Ban."""
    try:
        result = subprocess.run(
            ['fail2ban-client', 'status'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return {'status': 'active', 'output': result.stdout}
        return {'status': 'inactive', 'error': result.stderr}
    except FileNotFoundError:
        return {'status': 'not_installed'}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


def get_ssh_failures(hours=24):
    """Obtém falhas SSH nas últimas horas."""
    try:
        result = subprocess.run(
            ['journalctl', '-u', 'ssh', '--since', f'{hours}h ago'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            failed = [l for l in lines if 'Failed password' in l]
            return {'total': len(failed), 'lines': failed[:50]}
        return {'total': 0}
    except Exception as e:
        return {'error': str(e)}
