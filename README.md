# OCI Relay

**English** · [Português](README.pt-BR.md)

[![CI](https://github.com/Ryanleoncoder/OCI-Relay/actions/workflows/ci.yml/badge.svg)](https://github.com/Ryanleoncoder/OCI-Relay/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Operations companion for Oracle Cloud Infrastructure VPS instances, driven from Telegram.

Open Telegram and ask: is the VPS up? how much CPU is it using? did Oracle start charging? No console, no SSH.

```
🩺 Health — my-vps

State   🟢 RUNNING
Shape   VM.Standard.A1.Flex
OCPU    4
Memory  24 GB

Utilisation
CPU     🟢 0.3%
Memory  🟢 5.9%
Load    0.00

I/O (current rate)
Disk read   0.0 KB/s
Disk write  12.5 KB/s
Net in      0.3 KB/s
Net out     1.1 KB/s

Overall: 🟢 Healthy
```

---

## Why it works without SSH

Most of what matters comes from the **OCI API**, not from inside the machine. The *Compute Instance Monitoring* plugin publishes CPU, memory, load, disk and network under the `oci_computeagent` namespace, and the Relay reads it from outside.

In practice: you run the bot on your laptop, or anywhere, and it reports the real VPS. No extra agent.

What **does** require being inside the VPS: Fail2Ban, systemd, Docker, SSH sessions and listening ports. Those commands only become useful once the Relay runs on the machine itself.

---

## Current state

The project is at v0.1, under development.

### Working and verified against a real VPS

| Command | What it does |
|---|---|
| `/start`, `/help` | Lists the commands |
| `/status` | State, shape, OCPU, RAM and region |
| `/summary` | Overview: OCI plus resources, with a verdict |
| `/health` | CPU, memory, load and I/O via OCI Monitoring |
| `/usage` | Reported cost this month, by service, with budgets |
| `/oci_ip` | Public and private IP |
| `/network` | VCN, subnet, ingress rules and routes |
| `/suspender`, `/reiniciar`, `/reativar` | Power actions, with confirmation |
| `/language` | Switches the bot language |
| `/shape` | Shape, OCPU and memory |

### Working, but measuring the local host

These use `psutil` and describe **the machine running the bot**. They only describe the VPS once the Relay is installed on it.

`/cpu` · `/memory` · `/disk` · `/top` · `/ports` · `/uptime` · `/sessions`

### Implemented, but **not tested on a VPS**

They depend on `fail2ban-client`, `systemctl` and the Docker daemon. The code exists and degrades with a clear message when the dependency is missing, but **has never run on a host that has it**. Treat as unverified.

`/docker` · `/services` · `/security` · `/fail2ban` · `/failed` · `/container` · `/docker_logs`

### Not implemented yet

They answer with a notice, so they do not look broken: `/watch` · `/alerts`

Still outside the code: `/oci_events`, `/bans`, `/attacks`, `/ssh_logins`, `/updates`, `/certs`, `/backup_status`, `/resize`, drift detection and the alert engine.

---

## Installation

Requires Python 3.10+.

The target is **Linux**, where the Relay runs as a service on the VPS itself. Windows and macOS work for development: OCI commands operate normally, and the ones depending on `systemctl`, `fail2ban-client` or Docker report that they are unavailable instead of failing.

### Local (to try it)

```bash
git clone https://github.com/Ryanleoncoder/OCI-Relay.git && cd OCI-Relay
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env           # fill in .env
python -m oci_relay
```

### On the VPS (as a service)

```bash
git clone https://github.com/Ryanleoncoder/OCI-Relay.git
cd OCI-Relay && ./scripts/install-vps.sh
```

Installs into `/opt/oci-relay`, configures `/etc/oci-relay/.env` with mode `600` and registers the systemd service — automatic restart, retry limits and the `ProtectSystem`/`NoNewPrivileges` restrictions. It takes no secrets as arguments.

> This path **has not been run on a real VPS yet**. See [docs/SETUP.md](docs/SETUP.md).

### Configuration

[.env.example](.env.example) explains every field and where to find it in the console. In short:

**Telegram** — token from @BotFather and your numeric ID from @userinfobot. Leaving `TELEGRAM_ALLOWED_CHAT_IDS` empty opens the bot to anyone.

**OCI** — two modes:

- **On the VPS:** `OCI_USE_INSTANCE_PRINCIPAL=true`. No key on disk; the identity comes from the instance metadata service. Requires a Dynamic Group and a policy — see [docs/SETUP.md](docs/SETUP.md).
- **Outside the VPS:** `OCI_USE_INSTANCE_PRINCIPAL=false` and an API key. Simpler for testing, but the key inherits your user permissions.

Both modes need `OCI_REGION` and `OCI_INSTANCE_OCID`.

Startup validates the configuration before any call and reports problems explicitly — including an OCID in the wrong field, which OCI would return as a `404 NotAuthorizedOrNotFound` that is hard to diagnose.

### Language

The bot follows the language configured in your Telegram client, falling back to English. `/language pt_BR` overrides it for that conversation, and the choice persists.

Catalogues live in [`src/oci_relay/locales/`](src/oci_relay/locales/). Adding a language means adding a file — no Python changes.

---

## Security

- **Allowlist by `chat_id`.** Anyone not on the list is ignored and the attempt is logged. Usernames are never used as identity.
- **No remote shell.** There is no `/exec`, `/bash` or equivalent, by design. Calls to `systemctl` and `fail2ban-client` use a fixed argument list, never `shell=True`.
- **Power actions require confirmation.** `/suspender`, `/reiniciar` and `/reativar` show a preview with the real state and only execute after the requester approves, with a single-use nonce valid for 90s. Only `SOFTSTOP`, `SOFTRESET` and `START` — the abrupt variants can corrupt the filesystem and are not offered.
- **Token redacted from logs.** A filter strips the bot token from URLs before anything is logged.
- **Least privilege.** The design asks for read access to instance/usage/monitoring/audit and write access only to `InstanceAction`. Do not grant `manage all-resources`.

Full threat model in [SECURITY.md](SECURITY.md).

---

## Development

```bash
pip install -r requirements-dev.txt
python -m pytest
python -m flake8 src/ tests/
```

CI runs both on Linux, on Python 3.10 and 3.13, on every push.

The suite covers configuration parsing, OCID validation, message formatting, local collectors, Monitoring queries, the confirmation state machine and the handler contract — every handler must answer something and never raise into the polling loop.

### Architecture

```
src/oci_relay/
├── main.py         entry point and self-check
├── i18n.py         message catalogue
├── locales/        en.yml, pt_BR.yml
├── channels/
│   ├── telegram/   adapter, registry,
│   │               formatter, handlers/
│   └── discord/    webhook alerts
├── oci/            compute, monitoring,
│                   usage, network, auth
├── safety/         action confirmation
├── system/         psutil and systemd
├── security/       fail2ban and ports
├── docker/         Docker SDK
├── state/          SQLite
└── config/         settings and paths
```

Telegram is the first channel, not the core: the OCI layer knows nothing about Telegram.

---

## Documentation

Detailed documentation is written in Portuguese.

- [Commands](docs/commands.md) — what each one does and where the data comes from
- [OCI setup](docs/OCI-SETUP.md) — keys, policies and metrics
- [Setup and deploy](docs/SETUP.md) — installing on the VPS
- [Architecture](docs/architecture.md) — how it works and why
- [Troubleshooting](docs/troubleshooting.md) — when something does not answer
- [Security](SECURITY.md) — threat model and limitations

## License

[MIT](LICENSE)
