# Segurança

O OCI Relay dá a uma conta de Telegram visibilidade sobre uma VPS e poder
de ligá-la e desligá-la. Este documento descreve o que o projeto faz para
limitar o estrago se algo der errado, e o que ainda não faz.

## Reportar uma vulnerabilidade

Abra uma *security advisory* privada no GitHub, ou entre em contato com o
mantenedor. **Não abra uma issue pública** para falhas exploráveis.

---

## Modelo de ameaça

O que estamos protegendo, e de quem.

| Ameaça | Mitigação |
|---|---|
| Alguém encontra o bot e o usa | Allowlist por `chat_id`; desconhecidos são ignorados |
| Conta de Telegram comprometida | Sem shell remoto; ações de energia exigem confirmação do autor |
| Credencial OCI vazada | Instance Principal não guarda chave; policy de menor privilégio |
| Token vazado em log | Redação automática nas URLs |
| Comando injetando shell | `shell=False` com lista de argumentos fixa |
| Log ou mensagem gigante | Fragmentação e limite de linhas |

O que **não** está no modelo: um invasor que já tenha acesso root à VPS, ou
acesso físico à máquina onde o bot roda. Nesses casos ele lê o `.env`
diretamente.

---

## Autorização

Acesso é controlado por `TELEGRAM_ALLOWED_CHAT_IDS`. Quem não está na lista
é ignorado e a tentativa fica registrada.

A identidade é o **ID numérico**, nunca o `@username` — usernames podem ser
trocados e reutilizados, então não servem como identidade.

> Deixar a allowlist vazia libera o bot para qualquer pessoa que o encontre.
> Bots do Telegram são descobríveis por nome.

---

## Sem shell remoto

Não existem `/exec`, `/bash`, `/shell`, `/run`, `/eval` nem `/python`, e isso
é permanente. Um bot de Telegram com shell transforma qualquer
comprometimento de conta em comprometimento total da VPS.

Chamadas a `systemctl` e `fail2ban-client` usam lista de argumentos fixa:

```python
subprocess.run(["systemctl", "is-active", unidade], shell=False)
```

Nenhum comando recebe nome de unidade, caminho ou argumento vindo do texto
da mensagem.

---

## Menor privilégio na OCI

O Relay precisa de **leitura** de instance-family, metrics,
virtual-network-family, audit-events e usage-reports.

Não conceda `manage all-resources`, nem `manage instance-family`. Esse verbo
inclui criar, terminar e reconfigurar instâncias — muito além de ligar e
desligar. Para as ações de energia, a permissão necessária é apenas:

```
Allow dynamic-group oci-relay-group to use instance-family in compartment root
  where request.operation = 'InstanceAction'
```

Veja [docs/OCI-SETUP.md](docs/OCI-SETUP.md).

### Os dois modos não têm o mesmo risco

**Instance Principal** amarra a identidade a uma instância específica via
Dynamic Group, não guarda credencial em disco e tem rotação automática.

**API Key** herda as permissões do **seu usuário**. Se você é administrador
da tenancy, o bot também é. Serve para desenvolver; não é o modelo de
produção.

---

## Controle de energia e auto-hospedagem

Rodando **na própria VPS que monitora**, o Relay enfrenta um limite de
topologia, não de implementação: para religar uma máquina é preciso estar
vivo enquanto ela está desligada.

| Ação | Na instância monitorada | Em outro host |
|---|---|---|
| `/reiniciar` (SOFTRESET) | Reversível — o systemd traz o bot de volta no boot | Reversível |
| `/suspender` (SOFTSTOP) | **Sem volta pelo Telegram** — só o console religa | Reversível |
| Religar a instância | Impossível: o bot morreu junto | Possível |

Por isso o Relay consulta o serviço de metadados em `169.254.169.254`, que
só responde de dentro de uma instância, e **compara** o OCID retornado com
`OCI_INSTANCE_OCID`. A comparação importa: rodar na VPS A monitorando a VPS
B mantém tudo reversível.

O resultado aparece no startup e na prévia de cada ação de energia. Na
dúvida — metadados inalcançáveis, timeout, resposta inesperada — a detecção
assume "não estou na instância alvo". O que se perde é o aviso extra, não a
segurança da ação, que continua exigindo confirmação.

> **Consequência adicional:** se o IP público da instância for `EPHEMERAL`
> (o padrão da OCI), pará-la e religá-la devolve **outro IP**. Qualquer DNS,
> regra de firewall externa ou configuração apontando para o endereço antigo
> deixa de funcionar. Verifique com `/oci_ip` antes de parar.

## Segredos

- O `.env` nunca vai para o git. `.gitignore` cobre `.env`, `*.pem`, `*.key`,
  `*.p12` e `.oci/`.
- O instalador cria `/etc/oci-relay/.env` com permissão `600`.
- Nenhum script aceita segredo por argumento de linha de comando: o
  histórico do shell (`ConsoleHost_history.txt`, `.bash_history`) grava
  argumentos em texto puro, fora do alcance do `.gitignore`.
- O token do bot é removido das URLs antes de qualquer log sair, aparecendo
  como `bot<redacted>`.

Restrinja a chave privada:

```bash
chmod 600 ~/.oci/oci_api_key.pem
```

---

## Endurecimento do serviço

A unit systemd em [`deploy/oci-relay.service`](deploy/oci-relay.service)
aplica `NoNewPrivileges`, `ProtectSystem=strict`, `ProtectHome`,
`PrivateTmp`, `MemoryDenyWriteExecute` e limita a escrita ao diretório de
estado.

O Relay só lê o sistema e fala com APIs externas; não precisa escrever em
mais lugar nenhum.

---

## Limitações conhecidas

- **Sem rate limiting por chat.** Um usuário autorizado pode disparar
  comandos em sequência e consumir cota da API da OCI.
- **Audit log parcial.** Cada confirmação fica registrada com autor,
  comando, alvo e desfecho, mas a tabela `audit_log` dedicada ainda não é
  escrita.
- **Comandos locais não testados numa VPS.** `/docker`, `/services`,
  `/security` e `/fail2ban` nunca rodaram num host com essas dependências.
- **Sem verificação de integridade de dependências.** O projeto usa
  `requirements.txt` com faixas de versão, sem lockfile com hashes.

---

## Boas práticas ao usar

1. Preencha `TELEGRAM_ALLOWED_CHAT_IDS`.
2. Use Instance Principal na VPS; reserve a API Key para desenvolvimento.
3. Revise a policy periodicamente — permissões tendem a crescer e nunca
   encolher.
4. Rotacione o token do bot se suspeitar de exposição (@BotFather → `/revoke`).
5. Revise capturas de tela antes de publicá-las: OCIDs e IPs aparecem nas
   respostas do bot.
