# Setup do OCI Relay

## Visão geral

O OCI Relay requer:

1. **Instance Principal** na OCI (para autenticação sem chave)
2. **Dynamic Group** com regra para sua instância
3. **Policy** concedendo permissões ao Dynamic Group
4. **Telegram Bot Token** (e IDs autorizados)

## Configurar OCI

### 1. Criar Dynamic Group

1. Acesse **Identity & Security** → **Dynamic Groups**
2. Clique em **Create Dynamic Group**
3. Preencha:
   - **Name**: `oci-relay-group`
   - **Description**: `Dynamic group for OCI Relay bot`
   - **Matching rule**: `instance.id = 'seu-instance-ocid'`

### 2. Criar Policy

1. Acesse **Identity & Security** → **Policies**
2. Clique em **Create Policy**
3. Preencha:
   - **Name**: `oci-relay-policy`
   - **Compartment**: Selecione o compartment da sua instância

4. Adicione estas regras:
```
Allow dynamic-group oci-relay-group to read instance-family in compartment root
Allow dynamic-group oci-relay-group to read audit-events in compartment root
Allow dynamic-group oci-relay-group to read metrics in compartment root
Allow dynamic-group oci-relay-group to read usage-reports in tenancy
Allow dynamic-group oci-relay-group to read virtual-network-family in compartment root
```

> **Não use `manage instance-family`.** Esse verbo concede muito mais do que
> ligar e desligar a máquina. Quando `/suspender` e `/reiniciar` forem
> implementados, a permissão necessária é apenas a de executar ações de
> energia:
>
> ```
> Allow dynamic-group oci-relay-group to use instance-family in compartment root
>   where request.operation = 'InstanceAction'
> ```
>
> Adicione essa regra só quando for usar as ações de escrita. Enquanto o
> Relay for somente leitura, as cinco regras acima bastam.

### 3. Obter OCIDs

No Console OCI:

- **Instance OCID**: Compute → Instâncias → sua instância → OCID → Copiar.
  Começa com `ocid1.instance.` — se começar com `ocid1.tenancy.`, é o valor
  errado. O Relay valida o prefixo no startup e avisa.
- **Compartment OCID**: Identity & Security → Compartimentos. No
  compartimento root, é igual ao OCID da tenancy.

> A criação do Dynamic Group e da policy é feita pelo console, de propósito.
> Um script que cria policy IAM automaticamente pode conceder permissão
> demais por um erro de digitação, sem ninguém perceber.

## Configurar Telegram

1. Abra @BotFather no Telegram
2. Envie `/newbot`
3. Escolha nome e username
4. Copie o token

Não é preciso usar `/setcommands`: o Relay registra o menu de comandos
sozinho no startup, via `setMyCommands`.

### Obter Chat ID

1. Abra @userinfobot
2. Envie qualquer mensagem
3. Copie o número `Id:`

Deixar `TELEGRAM_ALLOWED_CHAT_IDS` vazio libera o bot para qualquer pessoa
que o encontre.

## Instalar na VPS

Na VPS, com um usuário que tenha sudo:

```bash
git clone https://github.com/Ryanleoncoder/OCI-Relay.git
cd OCI-Relay
./scripts/install-vps.sh
```

O script clona em `/opt/oci-relay`, cria a venv, instala as dependências,
prepara `/etc/oci-relay/.env` com permissão `600` e instala o serviço
systemd de [deploy/oci-relay.service](../deploy/oci-relay.service). Ele não
aceita segredos por argumento — você edita o `.env` depois.

Em seguida:

```bash
sudo nano /etc/oci-relay/.env     # credenciais
sudo systemctl start oci-relay
```

> **Ainda não testado numa VPS real.** O script foi escrito e teve a sintaxe
> validada, mas nunca executou num host Linux. Leia antes de rodar.

## Verificar

```bash
sudo systemctl status oci-relay
sudo journalctl -u oci-relay -f
```

No startup o Relay reporta o que encontrou — se a autenticação OCI falhou,
o log diz o motivo antes de qualquer comando ser usado.

Envie `/start` para o bot no Telegram.

## Diagnóstico rápido

Para conferir token, allowlist e menu sem subir o bot inteiro:

```powershell
./scripts/test-telegram.ps1            # só verifica
./scripts/test-telegram.ps1 -Enviar    # manda mensagem de teste
```

Ele lê o `.env` — nunca passe o token por parâmetro, porque o histórico do
PowerShell grava argumentos em texto puro.
