# Comandos

A distinção que mais importa aqui: **de onde vem o dado**.

| Fonte | Significa | Funciona de onde |
|---|---|---|
| **OCI** | Lido da API da Oracle | Qualquer lugar |
| **Local** | Lido com `psutil`/subprocess | Descreve **a máquina onde o bot roda** |

Rodando o Relay no seu PC, `/status` fala da VPS mas `/cpu` fala do seu PC.
Instalado na VPS, os dois falam da VPS. É a diferença entre observar de fora
e estar dentro.

Para não restar dúvida, **cada resposta nomeia a máquina que está
descrevendo**:

```
🩺 Health — minha-vps     ← a VPS, via OCI
🔥 CPU — meu-desktop      ← o host onde o bot roda
```

Instalado na VPS, os dois nomes coincidem.

---

## Core

### `/start`, `/help`
Lista os comandos disponíveis. Ambos respondem igual.

O menu de comandos do Telegram é registrado automaticamente no startup — não
é preciso configurar nada no @BotFather.

### `/summary` — *OCI + Local*
Visão geral em uma mensagem: estado da instância, uso de recursos e um
veredito `Overall`.

Se a OCI estiver inacessível, o bloco dela degrada sozinho e o resto da
mensagem continua — uma falha de API não apaga o resumo inteiro.

---

## OCI

### `/status` — *OCI*
Nome, estado, shape, OCPU, memória e região da instância.

O estado vem com semáforo: 🟢 `RUNNING`, 🔴 `STOPPED`/`TERMINATED`,
🟡 `STARTING`/`STOPPING`.

### `/usage` — *OCI*
Custo reportado da tenancy no mês corrente, quebrado por serviço, mais os
orçamentos configurados e quanto de cada um já foi consumido.

O semáforo usa `ALERT_COST_WARNING_USD` e `ALERT_COST_CRITICAL_USD` do
`.env`. No free tier o esperado é zero — qualquer valor acima merece olhada.

Valores abaixo de um centavo aparecem com quatro casas decimais. Arredondar
`0.0012` para `0.00` esconderia exatamente o que o comando existe para
mostrar: uma cobrança que acabou de começar.

Serviços com custo zero são omitidos; no free tier eles são a maioria e só
gerariam ruído.

> **Os dados de faturamento da OCI são consolidados com atraso de horas.**
> Este comando responde "quanto foi reportado até agora", nunca "quanto está
> custando neste instante". A resposta traz esse aviso.

Requer `read usage-reports in tenancy` na policy. Os budgets são opcionais:
sem permissão para lê-los, o resto do comando continua funcionando.

### `/network` — *OCI*
VCN, subnet, IPs, regras de entrada das security lists, contagem de regras de
saída, rotas e NSGs.

Cada regra de entrada vem com semáforo: 🟡 quando a origem é `0.0.0.0/0` ou
`::/0` — aberta a qualquer lugar da internet. É normal o SSH aparecer assim
(é o padrão da Oracle), e é exatamente a superfície que o Fail2Ban existe
para conter.

Somente leitura. Alterar regra de rede não faz parte desta versão: uma linha
errada numa security list expõe a máquina ou derruba o próprio acesso SSH.

### `/oci_ip` — *OCI*
IP público e privado da VNIC primária, hostname e quantidade de NSGs.

> Se o IP público for **efêmero** (o padrão da OCI), ele **muda** quando a
> instância é parada e reiniciada. Um IP fixo exige reservá-lo no console.

### `/health` — *OCI*
Saúde da VPS lida do OCI Monitoring, sem SSH:

```
State / Shape / OCPU / Memory
CPU · Memory · Load
Disk read/write · Net in/out
Overall
```

Requer o plugin **Compute Instance Monitoring** habilitado — veja
[OCI-SETUP.md](OCI-SETUP.md). Sem ele, CPU e memória aparecem como `n/d`.

As métricas têm granularidade de 1 minuto e chegam com atraso. Não é leitura
instantânea; para isso é preciso estar na máquina.

Sem OCI configurada, cai num painel do host local e diz isso explicitamente.

---

## Recursos locais

Estes descrevem **a máquina onde o bot roda**.

### `/cpu` — *Local*
Uso total, por núcleo, load average e os 5 processos que mais consomem CPU.

O percentual por processo é normalizado pelo número de núcleos, como no
`top` — um processo saturando 4 núcleos de 4 aparece como 100%, não 400%.

### `/top` — *Local*
Processos que mais consomem CPU e memória, com PID.

O percentual de CPU é normalizado pelo número de núcleos: um processo
saturando 4 de 4 núcleos aparece como 100%, não 400%.

### `/memory` — *Local*
Total, usado, disponível, swap e os 5 maiores consumidores de RAM.

### `/disk` — *Local*
Uso por ponto de montagem, ordenado do mais cheio para o mais vazio, com
semáforo por limiar e veredito geral.

### `/ports` — *Local*
Portas em escuta, separadas em **públicas** e **localhost**, com o nome do
processo dono de cada uma.

Bindings IPv4 e IPv6 do mesmo serviço são agrupados numa entrada só. Uma
porta conta como pública se **qualquer** um de seus bindings escuta em
endereço abrangente (`0.0.0.0` ou `::`) — o caso perigoso domina.

> **No Linux sem root, os nomes de processo aparecem como `?`.** A lista de
> sockets vem de `/proc/net/tcp`, legível por qualquer usuário, mas associar
> o socket ao processo exige ler `/proc/<pid>/fd` — permitido apenas para
> processos do próprio usuário. As portas continuam corretas; só o dono fica
> desconhecido. A resposta avisa quando isso acontece.

---

## Serviços e segurança

> **Não testados numa VPS real.** O código existe e degrada com mensagem
> clara quando a dependência falta, mas nunca rodou num host que a tenha.

### `/docker` — *Local*
Contagem de containers por estado e a lista com semáforo. Somente leitura:
não existe `exec`, `run`, `pull` nem `remove`.

### `/services` — *Local*
Serviços críticos, unidades em falha e a lista de serviços em execução
(limitada a 30, com contagem do restante).

Os críticos vêm de `CRITICAL_SERVICES` no `.env`, com default
`ssh,docker,fail2ban`.

Usa `systemctl` com lista de argumentos fixa, nunca `shell=True`.

### `/security` — *Local*
Painel consolidado: Fail2Ban, falhas de SSH em 24h e portas públicas.

### `/fail2ban` — *Local*
Estado do serviço e as jails configuradas, via `fail2ban-client status`.
Somente leitura — não é possível banir, desbanir ou recarregar pelo bot.

---

## Ações de energia — *OCI*

`/suspender` · `/reiniciar` · `/reativar`

Nenhuma executa direto. O fluxo é sempre o mesmo:

```
comando → pré-voo → prévia → confirmação → execução
```

**Pré-voo** rejeita ação sem sentido: parar máquina já parada, ligar máquina
já ligada. Isso é engano, não intenção.

**Prévia** mostra o estado real da instância, a ação que será enviada e o
resultado esperado — para a decisão ser tomada com o dado à vista, não de
memória.

**Confirmação** vale por 90 segundos, só para quem pediu, e uma única vez.
Clique duplo não executa duas vezes, e botão esquecido na conversa não
desliga a máquina meia hora depois.

| Comando | Ação OCI | Exige | Resultado |
|---|---|---|---|
| `/suspender` | `SOFTSTOP` | `RUNNING` | `STOPPED` |
| `/reiniciar` | `SOFTRESET` | `RUNNING` | `RUNNING` |
| `/reativar` | `START` | `STOPPED` | `RUNNING` |

Só as variantes graciosas. `STOP` e `RESET` abruptos equivalem a cortar a
energia e podem corromper o sistema de arquivos — não são oferecidos.

A confirmação de sucesso traz o `opc-request-id`, que liga a execução ao
registro correspondente no Audit da OCI.

> **Se o Relay rodar na própria instância**, a prévia do `/suspender` avisa
> em vermelho: o bot morre junto com a máquina e só o console da OCI religa.
> Ver [SECURITY.md](../SECURITY.md).

---

## Ainda não implementados

Respondem avisando, para não parecerem quebrados:

`/sessions` · `/watch` · `/alerts`

---

## Comandos que não existirão

```
/exec   /bash   /shell   /run   /eval   /python
/kill   /terminate   /delete_instance
```

Decisão de projeto, não omissão: o Telegram não deve virar um shell remoto.
Uma conta de Telegram comprometida daria acesso completo à VPS.
