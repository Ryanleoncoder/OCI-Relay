# Diagnóstico

Sintomas comuns e o que costuma estar por trás deles. Vários não são o que
parecem à primeira vista.

## O bot não responde nada no Telegram

Verifique nesta ordem:

**1. O processo está rodando?**

```bash
sudo systemctl status oci-relay      # na VPS
```

**2. O token é válido e você está na allowlist?**

```powershell
./scripts/test-telegram.ps1
```

Ele valida o token via `getMe` e mostra a allowlist, sem subir o bot.

**3. Seu ID está em `TELEGRAM_ALLOWED_CHAT_IDS`?**

Quem não está na lista é ignorado com aviso no log:

```
Mensagem ignorada do chat_id=123456 (fora da whitelist)
```

Pegue seu ID com @userinfobot. Use o número, nunca o @username — username
muda e não é identidade.

**4. Esperou ~1,5s?**

O adapter agrupa mensagens numa janela de coalescência antes de processar.
A resposta não é instantânea por desenho.

---

## O menu de comandos não aparece

O botão **Menu** só aparece depois que o cliente atualiza a lista, e o
Telegram a mantém em cache por bot.

**Feche e reabra a conversa**, ou reinicie o Telegram. O log confirma se o
registro funcionou:

```
Telegram: N comandos registrados.
Telegram: botão Menu configurado.
```

Se essas linhas aparecem e o menu não, é cache do cliente — não do bot.

---

## `404 NotAuthorizedOrNotFound`

**Esse erro quase nunca é sobre permissão.** A OCI mistura de propósito "não
existe" com "não autorizado", para não revelar a existência de recursos. Na
prática, a ordem de suspeita é:

**1. OCID no campo errado.** O mais comum é o OCID da tenancy acabar em
`OCI_INSTANCE_OCID` — os dois são copiados de telas parecidas. O Relay
detecta isso no startup:

```
Configuração OCI: OCI_INSTANCE_OCID parece um 'ocid1.tenancy',
mas deveria ser 'ocid1.instance'
```

**2. Caractere extra no valor colado.** Um caractere a mais no início —
`oocid1.instance...` — é invisível numa string de 94 caracteres. A mesma
validação pega.

**3. Policy faltando ou ainda propagando.** Só depois de descartar os dois
primeiros. Propagação leva alguns minutos. Veja [OCI-SETUP.md](OCI-SETUP.md).

---

## `401 NotAuthenticated`

Diferente do 404: aqui a requisição chegou e a assinatura foi rejeitada.

- **Fingerprint não confere** com a chave em `OCI_PRIVATE_KEY_PATH`. Compare
  com a que aparece na lista de Chaves de API do console.
- **Chave trocada** — o `.pem` não corresponde à chave registrada.
- **Relógio fora de hora.** A assinatura tem validade temporal; um desvio
  grande no relógio da máquina invalida a requisição.

---

## `/health` mostra `n/d` em CPU e memória

O plugin **Compute Instance Monitoring** está desabilitado na instância, ou
a policy não inclui `read metrics`.

Console → Compute → Instâncias → sua VPS → **Oracle Cloud Agent** → habilite
o plugin. Leva alguns minutos até os primeiros pontos aparecerem.

Lembre que o Monitoring tem granularidade de 1 minuto e publica com atraso —
`n/d` logo após ligar a instância é esperado.

---

## `/health` mostra números que não são da VPS

Se a saída diz **"Health — host local"** em vez de **"Health — minha-vps"**, a OCI
não está configurada e o Relay caiu no fallback: os números são da máquina
onde o bot roda.

Preencha `OCI_REGION` e `OCI_INSTANCE_OCID`.

O mesmo vale sempre para `/cpu`, `/memory`, `/disk` e `/ports`: esses usam
`psutil` e descrevem **o host do bot**, não a VPS — a menos que o Relay
esteja instalado nela.

---

## `/ports` mostra `?` no lugar dos processos

Esperado ao rodar no Linux sem root, e não é um defeito: as portas estão
corretas, só o dono de cada socket é que não pôde ser lido.

A lista de sockets vem de `/proc/net/tcp`, acessível a qualquer usuário, mas
descobrir qual processo ocupa cada um exige ler `/proc/<pid>/fd`, permitido
apenas para processos do próprio usuário.

Rodar o serviço como root resolveria, mas conflita com o endurecimento da
unit systemd (`NoNewPrivileges`, `ProtectSystem=strict`) e daria ao bot muito
mais poder do que ele precisa. A escolha padrão é manter o privilégio baixo e
conviver com a informação parcial.

---

## `/docker`, `/services` ou `/fail2ban` dizem "não disponível"

Esperado fora da VPS. Esses comandos dependem do daemon do Docker, de
`systemctl` e de `fail2ban-client`, que o OCI Monitoring não consegue
substituir. Só funcionam com o Relay rodando na própria máquina.

---

## `Variável obrigatória não encontrada`

O `.env` não foi encontrado ou o campo está vazio. O log diz de onde a
config foi lida:

```
Config carregada de /etc/oci-relay/.env
```

Se aparecer `Nenhum .env encontrado`, aponte explicitamente:

```bash
OCI_RELAY_ENV_FILE=/etc/oci-relay/.env python -m oci_relay
```

Cuidado com aspas e espaços em volta dos valores no `.env`. Um OCID com
espaço sobrando vira um 404 confuso.

---

## Editei o `.env` e a mudança sumiu

Se o arquivo está aberto no editor e algo o altera em disco, salvar o buffer
antigo sobrescreve a alteração.

Feche e reabra o arquivo (ou aceite o *reload from disk*) antes de editar.

---

## `Instance Principal` falha no seu PC

Esperado, e não tem conserto: o signer busca um certificado em
`169.254.169.254`, endereço que só existe dentro de uma instância OCI.

Fora da VPS, use `OCI_USE_INSTANCE_PRINCIPAL=false` e uma API Key.

---

## Ver os logs

```bash
sudo journalctl -u oci-relay -f          # acompanhar
sudo journalctl -u oci-relay -n 100      # últimas 100 linhas
sudo journalctl -u oci-relay -p err      # só erros
```

O token do bot é redigido automaticamente das URLs antes de qualquer log
sair — aparece como `bot<redacted>`. Ainda assim, revise antes de colar log
em lugar público.
