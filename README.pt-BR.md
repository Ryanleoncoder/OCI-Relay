# OCI Relay

**Português** · [English](README.md)

[![CI](https://github.com/Ryanleoncoder/OCI-Relay/actions/workflows/ci.yml/badge.svg)](https://github.com/Ryanleoncoder/OCI-Relay/actions/workflows/ci.yml)
[![Licença: MIT](https://img.shields.io/badge/licen%C3%A7a-MIT-blue.svg)](LICENSE)

Companion operacional para VPS na Oracle Cloud Infrastructure, controlado pelo Telegram.

Abra o Telegram e pergunte: a VPS está de pé? quanto de CPU está usando? a Oracle começou a cobrar? Sem console, sem SSH.

```
🩺 Health — minha-vps

State   🟢 RUNNING
Shape   VM.Standard.A1.Flex
OCPU    4
Memory  24 GB

Utilização
CPU     🟢 0.3%
Memory  🟢 5.9%
Load    0.00

I/O (taxa atual)
Disk read   0.0 KB/s
Disk write  12.5 KB/s
Net in      0.3 KB/s
Net out     1.1 KB/s

Overall: 🟢 Healthy
```

---

## Por que ele funciona sem SSH

A maior parte do que interessa vem da **API da OCI**, não de dentro da máquina. O plugin *Compute Instance Monitoring* publica CPU, memória, load, disco e rede no namespace `oci_computeagent`, e o Relay lê isso de fora.

Na prática: você roda o bot no seu PC, ou em qualquer lugar, e ele reporta a VPS de verdade. Nada de agente extra.

O que **exige** estar dentro da VPS: Fail2Ban, systemd, Docker, sessões SSH e portas em escuta. Esses comandos só passam a ser úteis quando o Relay roda na própria máquina.

---

## Estado atual

O projeto está em v0.1, em desenvolvimento.

### Funcionando e verificado contra uma VPS real

| Comando | O que faz |
|---|---|
| `/start`, `/help` | Lista os comandos |
| `/status` | Estado, shape, OCPU, RAM e região da instância |
| `/summary` | Visão geral: OCI + recursos, com veredito |
| `/health` | CPU, memória, load e I/O da VPS via OCI Monitoring |
| `/usage` | Custo reportado no mês, por serviço, com budgets |
| `/oci_ip` | IP público e privado |
| `/suspender`, `/reiniciar`, `/reativar` | Ações de energia, com confirmação |
| `/network` | VCN, subnet, regras de entrada e rotas |
| `/shape` | Shape, OCPU e memória |
| `/language` | Troca o idioma do bot |

### Funcionando, mas medindo o host local

Estes usam `psutil` e descrevem **a máquina onde o bot roda**. Só descrevem a VPS quando o Relay estiver instalado nela.

`/cpu` · `/memory` · `/disk` · `/top` · `/ports` · `/uptime` · `/sessions`

### Implementados, porém **não testados numa VPS**

Dependem de `fail2ban-client`, `systemctl` e do daemon do Docker. O código existe e degrada com mensagem clara quando a dependência não está presente, mas **nunca rodou num host que a tenha**. Trate como não verificado.

`/docker` · `/services` · `/security` · `/fail2ban` · `/failed` · `/container` · `/docker_logs`

### Ainda não implementados

Respondem avisando, para não parecerem quebrados: `/watch` · `/alerts`

Fora do código por enquanto: `/oci_events`, `/bans`, `/attacks`, `/ssh_logins`, `/updates`, `/certs`, `/backup_status`, `/resize`, detecção de drift e o motor de alertas.

---

## Instalação

Requer Python 3.10+.

O alvo é **Linux**, onde o Relay roda como serviço na própria VPS. Windows e
macOS funcionam para desenvolvimento: os comandos OCI operam normalmente, e
os que dependem de `systemctl`, `fail2ban-client` ou do Docker respondem que
não estão disponíveis, em vez de falhar.

### Local (para testar)

```bash
git clone https://github.com/Ryanleoncoder/OCI-Relay.git && cd OCI-Relay
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env           # preencha o .env
python -m oci_relay
```

### Na VPS (como serviço)

```bash
git clone https://github.com/Ryanleoncoder/OCI-Relay.git
cd OCI-Relay && ./scripts/install-vps.sh
```

Instala em `/opt/oci-relay`, configura em `/etc/oci-relay/.env` com permissão
`600` e registra o serviço systemd — com restart automático, limite de
tentativas e as restrições de `ProtectSystem`/`NoNewPrivileges`. Não recebe
segredos por argumento.

> Este caminho **ainda não foi executado numa VPS real**. Ver [docs/SETUP.md](docs/SETUP.md).

### Configuração

O [.env.example](.env.example) explica cada campo e onde encontrá-lo no console. O resumo:

**Telegram** — token do @BotFather e seu ID numérico do @userinfobot. Deixar `TELEGRAM_ALLOWED_CHAT_IDS` vazio libera o bot para qualquer pessoa.

**OCI** — dois modos:

- **Na VPS:** `OCI_USE_INSTANCE_PRINCIPAL=true`. Nenhuma chave em disco; a identidade vem do serviço de metadados da instância. Exige Dynamic Group e policy — veja [docs/SETUP.md](docs/SETUP.md).
- **Fora da VPS:** `OCI_USE_INSTANCE_PRINCIPAL=false` e uma chave de API. Mais simples para testar, mas a chave herda as suas permissões de usuário.

Nos dois modos: `OCI_REGION` e `OCI_INSTANCE_OCID`.

O startup valida a configuração antes de qualquer chamada e reporta problemas de forma explícita — inclusive OCID no campo errado, que a OCI devolveria como um `404 NotAuthorizedOrNotFound` difícil de diagnosticar.

---

## Segurança

- **Allowlist por `chat_id`.** Quem não está na lista é ignorado e a tentativa fica registrada. Username nunca é usado como identidade.
- **Sem shell remoto.** Não existe `/exec`, `/bash` ou equivalente, e isso é deliberado. Chamadas a `systemctl` e `fail2ban-client` usam lista de argumentos fixa, nunca `shell=True`.
- **Ações de energia exigem confirmação.** `/suspender`, `/reiniciar` e `/reativar` mostram uma prévia com o estado real e só executam após aprovação do próprio autor, com nonce de uso único e validade de 90s. Apenas `SOFTSTOP`, `SOFTRESET` e `START` — as variantes abruptas podem corromper o sistema de arquivos e não são oferecidas.
- **Token redigido nos logs.** Um filtro remove o token do bot das URLs antes de qualquer log sair.
- **Menor privilégio.** O desenho pede leitura de instance/usage/monitoring/audit e escrita apenas de `InstanceAction`. Não conceda `manage all-resources`.

---

## Desenvolvimento

```bash
pip install -r requirements-dev.txt
python -m pytest
python -m flake8 src/ tests/
```

O CI roda os dois no Linux, em Python 3.10 e 3.13, a cada push.

A suíte cobre parsing de configuração, validação de OCID, formatação das mensagens, os coletores locais, as consultas ao Monitoring e o contrato dos handlers — todo handler precisa responder algo e nunca estourar exceção para o loop de polling.

### Arquitetura

```
src/oci_relay/
├── main.py         entrada e self-check
├── channels/
│   ├── telegram/   adapter, formatter,
│   │               handlers/
│   └── discord/    alertas por webhook
├── oci/            compute, monitoring,
│                   usage, network, auth
├── system/         psutil e systemd
├── security/       fail2ban e portas
├── docker/         Docker SDK
├── state/          SQLite
└── config/         settings e caminhos
```

O Telegram é o primeiro canal, não o núcleo: a lógica de OCI não conhece Telegram.

---

## Documentação

A documentação detalhada está em português.

- [Comandos](docs/commands.md) — o que cada um faz e de onde vem o dado
- [Configuração da OCI](docs/OCI-SETUP.md) — chaves, policies e métricas
- [Setup e deploy](docs/SETUP.md) — instalação na VPS
- [Arquitetura](docs/architecture.md) — como funciona e por quê
- [Diagnóstico](docs/troubleshooting.md) — quando algo não responde
- [Segurança](SECURITY.md) — modelo de ameaça e limitações

## Licença

[MIT](LICENSE)
