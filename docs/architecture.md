# Arquitetura

## O problema

Monitorar uma VPS normalmente exige estar dentro dela: um agente, uma porta
aberta, uma sessão SSH. Cada uma dessas coisas é mais superfície de ataque
numa máquina cujo ponto fraco já é o SSH exposto.

O OCI Relay inverte parte disso. A OCI já sabe o estado da sua instância —
CPU, memória, rede, custo, mudanças de configuração — e expõe isso por API.
O Relay lê dali e entrega no Telegram.

Consequência prática: **a maior parte do valor não exige acesso à máquina**.

---

## Fluxo

```
Telegram
   │  getUpdates (long polling)
   ▼
adapter
   ├─ allowlist por chat_id
   ├─ coalescência de mensagens
   ▼
roteador
   ▼
handler ──► formatter ──► Telegram
   │
   ├─► oci/        API da Oracle:
   │               compute, monitoring,
   │               usage, network, auth
   │
   └─► system/     psutil e subprocess:
       security/   descrevem a máquina
       docker/     onde o bot roda
```

### Por que long polling

O bot chama `getUpdates` e espera. Sem webhook, sem endpoint público, sem
certificado, sem porta aberta. Numa VPS cujo objetivo é reduzir exposição,
não abrir uma porta de entrada é o ponto principal — e o custo é latência
irrelevante para este uso.

### Coalescência de mensagens

Mensagens do mesmo chat são agrupadas numa janela de ~1,5s antes de serem
processadas. Isso evita disparar cinco consultas à OCI quando alguém manda
cinco linhas seguidas. O preço é a resposta não ser instantânea.

---

## Camadas

### `channels/`

O Telegram é o **primeiro canal, não o núcleo**. A lógica de OCI não conhece
Telegram: os handlers recebem `(client, token, chat_id)` e devolvem texto.

- **`adapter.py`** — polling, retry com backoff, tratamento de 429,
  fragmentação de mensagens longas, conversão markdown → HTML e redação do
  token nos logs.
- **`formatter.py`** — semáforos, tabelas alinhadas e vereditos. Existe para
  que os handlers não reinventem formatação cada um do seu jeito.
- **`handlers/`** — um arquivo por comando.

Um detalhe que amarra os dois: o conversor aplica `strip()` por linha, então
**alinhamento em colunas só sobrevive dentro de blocos ```` ``` ````, que
viram `<pre>`**. É por isso que `formatter.tabela()` sempre embrulha a saída.

### `oci/`

- **`auth.py`** — resolve `(config, signer)` uma vez por processo e fabrica
  os clients. Dois modos: Instance Principal (signer, sem chave em disco) e
  API Key (config dict validado). Também valida o *tipo* de cada OCID antes
  de qualquer chamada sair.
- **`compute.py`** — estado da instância e IPs.
- **`monitoring.py`** — métricas via `oci_computeagent`.

### `system/`, `security/`, `docker/`

Coletores locais. Só descrevem a máquina onde o processo roda — o que é a
distinção central para entender a saída dos comandos.

### `config/`

- **`settings.py`** — lê o ambiente. Instanciado no import: configuração
  inválida falha no startup, com mensagem clara, em vez de estourar no meio
  de um comando.
- **`paths.py`** — resolve raiz, `.env` e diretório de estado. Nada
  hardcoded: cada caminho aceita override por variável de ambiente, com
  fallback inferido da localização do pacote. É o que permite o deploy via
  systemd manter o `.env` em `/etc/oci-relay/` fora da árvore do código.

### `state/`

SQLite para baseline, alertas, cooldown e audit. **Escrito, ainda não
usado** — passa a ser necessário com o motor de alertas.

O schema é criado na primeira conexão, não no import: importar um módulo não
deve criar arquivos em disco.

---

## Decisões que valem explicação

### Instance Principal é o alvo, API Key é a ponte

Instance Principal não guarda credencial nenhuma em disco e a Oracle rotaciona
os certificados. Mas o signer busca esse certificado em `169.254.169.254`,
endereço que só existe **dentro** de uma instância OCI.

Por isso os dois modos coexistem: API Key para desenvolver de fora,
Instance Principal para produção. Não é indecisão — são contextos diferentes,
com perfis de risco diferentes.

### Gauge e contador não se agregam igual

No `oci_computeagent`, `CpuUtilization` e `MemoryUtilization` são valores
instantâneos, mas `DiskBytesWritten` e `NetworksBytesOut` são **contadores
cumulativos desde o boot**.

Consultar um contador com `mean()` devolve o total histórico — centenas de
gigabytes — apresentado como se fosse a taxa atual. `monitoring.py` marca
cada métrica com sua agregação e usa `rate()` nos contadores, o que dá
bytes por segundo.

### Falha parcial não apaga a resposta inteira

`/summary` monta o bloco da OCI separadamente e o degrada sozinho. Um erro
de API vira uma linha dizendo isso, e o resto da mensagem continua.

O mesmo princípio nos testes: todo handler precisa **sempre responder algo**
e nunca estourar exceção para o loop de polling. Um handler que levanta
exceção deixa o usuário sem resposta e sem explicação.

### O veredito não mente por otimismo

`formatter.veredito()` propaga o **pior** estado entre os componentes, e
"desconhecido" supera "saudável": sem dado, o painel não afirma que está
tudo bem.

### Validar OCID antes de chamar a API

A OCI responde `404 NotAuthorizedOrNotFound` tanto para "não existe" quanto
para "sem permissão" — de propósito, para não revelar recursos. O efeito
colateral é que um OCID colado no campo errado parece problema de policy, e
manda você mexer em IAM atrás de um erro de digitação.

Conferir o prefixo `ocid1.<tipo>` no startup transforma isso numa mensagem
direta.

---

## Testes

```bash
python -m pytest
```

A suíte cobre parsing de configuração, validação de OCID, formatação,
coletores locais, consultas ao Monitoring (com client falso, sem rede) e o
contrato dos handlers.

Dois grupos existem por motivo específico:

- **`test_imports.py`** importa todos os módulos. Imports relativos com a
  profundidade errada quebram metade do pacote e só aparecem em tempo de
  import.
- **`test_no_leaks.py`** garante que o código publicado não cite
  planejamento interno nem deixe `TODO`.
