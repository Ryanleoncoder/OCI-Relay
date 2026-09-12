# Configuração da OCI

Como dar ao OCI Relay acesso de leitura à sua instância, sem conceder mais
do que o necessário.

## Escolha o modo de autenticação primeiro

Essa decisão muda tudo o que vem depois.

| | Instance Principal | API Key |
|---|---|---|
| Onde funciona | Só **dentro** de uma instância OCI | Qualquer lugar |
| Chave em disco | Nenhuma | Um `.pem` privado |
| Identidade | Da instância, via Dynamic Group | A **sua**, de usuário |
| Rotação | Automática, pela Oracle | Manual |
| Indicado para | Produção, na VPS | Desenvolvimento, no seu PC |

O Instance Principal funciona porque o SDK busca um certificado no serviço
de metadados da máquina (`169.254.169.254`), acessível apenas de dentro
dela. Fora da OCI esse endereço não existe — por isso, no seu PC, a única
opção é API Key.

> **Cuidado com a API Key:** ela herda as permissões do **seu usuário**. Se
> você é administrador da tenancy, o bot também será. É aceitável para
> testar; não é o modelo para produção.

---

## Opção A — API Key (rodando fora da VPS)

### 1. Criar o par de chaves

Console → avatar no canto superior direito → **Meu perfil** → **Chaves de API**
→ **Adicionar chave de API**.

1. Deixe marcado **Gerar par de chaves de API**
2. **Faça download da chave privada** — e faça isso **antes** do passo 3.
   Depois de adicionar, a chave privada não pode mais ser baixada; só resta
   gerar outra.
3. **Adicionar**

Guarde o `.pem` em `~/.oci/` e restrinja o acesso:

```bash
chmod 600 ~/.oci/oci_api_key.pem
```

### 2. Copiar os identificadores

Ao adicionar, aparece a **Visualização do arquivo de configuração**. Dela
saem três valores do `.env`:

| No preview | No `.env` |
|---|---|
| `user=` | `OCI_USER_OCID` |
| `tenancy=` | `OCI_TENANCY_OCID` |
| `fingerprint=` | `OCI_FINGERPRINT` |
| `region=` | `OCI_REGION` |

A linha `key_file=<path to your private keyfile> # TODO` pode ser ignorada:
ela pertence ao arquivo `~/.oci/config` do CLI da Oracle, que o Relay não
usa. Esse papel aqui é do `OCI_PRIVATE_KEY_PATH`.

O **OCID da instância não está nesse preview** — ele descreve só a sua
identidade. Pegue em Compute → Instâncias → sua VPS → **OCID**.

### 3. Permissões

Se você é administrador da tenancy, não precisa de nada: a chave já tem os
acessos. Caso contrário, peça ao administrador uma policy equivalente à da
Opção B, trocando `dynamic-group oci-relay-group` pelo seu grupo.

---

## Opção B — Instance Principal (rodando na VPS)

### 1. Dynamic Group

Console → **Identity & Security** → **Dynamic Groups** → **Create**.

- **Name:** `oci-relay-group`
- **Matching rule:** `instance.id = 'ocid1.instance.oc1...'`

A regra amarra o grupo a **uma instância específica**. Evite regras amplas
como `instance.compartment.id = '...'`, que incluiriam qualquer máquina
criada depois no mesmo compartimento.

### 2. Policy

Console → **Identity & Security** → **Policies** → **Create**.

```
Allow dynamic-group oci-relay-group to read instance-family in compartment root
Allow dynamic-group oci-relay-group to read metrics in compartment root
Allow dynamic-group oci-relay-group to read virtual-network-family in compartment root
Allow dynamic-group oci-relay-group to read audit-events in compartment root
Allow dynamic-group oci-relay-group to read usage-reports in tenancy
```

O que cada uma habilita:

| Regra | Comandos |
|---|---|
| `instance-family` | `/status`, `/summary`, `/health` |
| `metrics` | `/health` — sem ela, CPU e memória vêm vazios |
| `virtual-network-family` | `/oci_ip` |
| `audit-events` | `/oci_events` (ainda não implementado) |
| `usage-reports` | `/usage` (ainda não implementado) |

> **Nunca use `manage instance-family`.** Esse verbo concede muito mais do
> que ligar e desligar a máquina — inclui criar, terminar e reconfigurar
> instâncias.
>
> Quando `/suspender` e `/reiniciar` forem implementados, a permissão
> correta é apenas a de executar ações de energia:
>
> ```
> Allow dynamic-group oci-relay-group to use instance-family in compartment root
>   where request.operation = 'InstanceAction'
> ```
>
> Adicione só quando for usar essas ações.

A propagação de policy leva alguns minutos. Um `404 NotAuthorizedOrNotFound`
logo após criar costuma ser só isso.

---

## Habilitar as métricas

Este passo é o que permite ao `/health` reportar a VPS **sem SSH**.

Console → Compute → Instâncias → sua VPS → aba **Oracle Cloud Agent** →
o plugin **Compute Instance Monitoring** precisa estar **Enabled**.

Com ele ligado, a instância publica no namespace `oci_computeagent`:

```
CpuUtilization      MemoryUtilization    LoadAverage
DiskBytesRead       DiskBytesWritten     DiskIopsRead/Written
NetworksBytesIn     NetworksBytesOut
```

Sem o plugin, os comandos OCI continuam funcionando, mas `/health` mostra
`n/d` em CPU e memória.

### Detalhe que importa

`CpuUtilization`, `MemoryUtilization` e `LoadAverage` são **gauges** — valor
instantâneo. Já as métricas de disco e rede são **contadores cumulativos
desde o boot**: consultá-las com `mean()` devolve o total histórico (centenas
de GB), não a taxa. O Relay usa `rate()` para essas, o que dá bytes por
segundo. Isso está codificado em [`oci/monitoring.py`](../src/oci_relay/oci/monitoring.py).

---

## Verificar

Com o `.env` preenchido:

```bash
python -m oci_relay
```

O startup valida a configuração **antes** de qualquer chamada e diz o que
encontrou:

```
OCI autenticada via API Key — instância 'minha-vps' está RUNNING
OCI: OK
```

Se algo estiver errado, veja [troubleshooting.md](troubleshooting.md) — em
especial o caso do `404`, que costuma não ser o que parece.
