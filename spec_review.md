# Relatório de Revisão de Especificações (Spec Review)

**Change:** `webhook-receiver-idempotent`  
**Data:** 28 de Agosto de 2026  
**Status:** Auditado (Sem correções automáticas aplicadas)

Este relatório atualizado analisa a implementação da change `webhook-receiver-idempotent` após as últimas modificações, confrontando o código e os testes contra as especificações (`specs/`), o design (`design.md`) e as regras gerais do agente definidas em `AGENTS.md`.

---

## Modificações/Correções Verificadas (Problemas Resolvidos)

1. **API não sobrescreve status de eventos já processados com sucesso:** Confirmado em [`app/main.py`](file:///home/dreian/lab/webhook-lab/app/main.py#L71-L76). A rota agora checa `existing_status` e evita regredir o status de `"succeeded"` para `"pending"`.
2. **Correção do primeiro atraso de backoff:** Confirmado em [`worker/worker_loop.py`](file:///home/dreian/lab/webhook-lab/worker/worker_loop.py#L88). O primeiro atraso utiliza `attempt - 1` na potência de 2, respeitando o atraso base inicial.
3. **Atomicidade no consumo da fila de atrasados:** Confirmado em [`worker/worker_loop.py`](file:///home/dreian/lab/webhook-lab/worker/worker_loop.py#L106-L107). O worker executa o `zrem` primeiro e só realiza o `rpush` se a remoção for bem-sucedida.
4. **Remoção de imports não utilizados em código produtivo:** Os imports mortos de `Optional`, `Any` e `uvicorn` foram limpos dos arquivos de produção.
5. **Estratégia de isolamento de testes:** Agora devidamente documentada no [`README.md`](file:///home/dreian/lab/webhook-lab/README.md#L50-L55).
6. **Testes de rejeição verificam ausência de enfileiramento:** Confirmado em [`tests/test_webhook_ingestion.py:52-102`](file:///home/dreian/lab/webhook-lab/tests/test_webhook_ingestion.py#L52-L102) (commit `d54ef31`). `test_missing_event_id_returns_400` e `test_blank_event_id_is_not_usable_and_returns_400` agora comparam `redis.llen(QUEUE_KEY)` antes e depois da requisição rejeitada, provando que nada foi enfileirado — não apenas o status HTTP. Suíte completa roda contra Redis real (8/8 passou).

---

## Divergências e Inconformidades Identificadas

### 1. Imports Não Utilizados em Arquivos de Teste (Código Morto)
- **Arquivo e linha:** 
  - [`tests/test_event_processing.py:L8`](file:///home/dreian/lab/webhook-lab/tests/test_event_processing.py#L8) — Import não utilizado de `check_delayed_queue`.
  - [`tests/test_e2e_visibility.py:L8`](file:///home/dreian/lab/webhook-lab/tests/test_e2e_visibility.py#L8) — Imports não utilizados de `QUEUE_KEY` e `EVENT_STORE_PREFIX`.
- **O que diverge:** Violação direta da **Regra #14 de `AGENTS.md`**: *"Não deixe código morto, import não usado, arquivo vazio criado 'por precaução' ou print de debug."*
- **Como verificar:** Remover os imports não utilizados e certificar-se de que os testes continuam passando.

---

### 2. Duplicidade na Declaração de Dependências
- **Arquivo e linha:** [`pyproject.toml:L6-18`](file:///home/dreian/lab/webhook-lab/pyproject.toml#L6-L18) e [`requirements.txt`](file:///home/dreian/lab/webhook-lab/requirements.txt)
- **O que diverge:** Violação direta da **Regra #9 de `AGENTS.md`**: *"Dependência se declara em um lugar só."* O projeto declara dependências completas tanto no arquivo de configuração do pacote Python (`pyproject.toml`) quanto no arquivo clássico de dependências (`requirements.txt`).
- **Como verificar:** Manter as dependências declaradas em apenas um dos arquivos (recomenda-se manter no `pyproject.toml`) e fazer com que o `requirements.txt` apenas referencie o pacote em modo editável com dependências opcionais (ex: `-e .[dev]`).

---

### 3. Comentários nos Testes Referenciando Tarefas Temporárias
- **Arquivo e linha:** [`tests/test_event_processing.py`](file:///home/dreian/lab/webhook-lab/tests/test_event_processing.py), [`tests/test_e2e_verification.py`](file:///home/dreian/lab/webhook-lab/tests/test_e2e_verification.py) e [`tests/test_e2e_visibility.py`](file:///home/dreian/lab/webhook-lab/tests/test_e2e_visibility.py)
- **O que diverge:** Inconformidade sutil com a **Regra #15 de `AGENTS.md`**: *"Não deixe comentário narrando o que você fez ('aqui eu corrijo o bug'). Comentário explica o código, não a sessão."*
  Diversos testes possuem comentários que fazem referência explícita aos números de tasks do plano de mudança (`tasks.md`) (ex: `# 4.1: only executes if claim succeeds`, `# 5.1 Send the same event ID twice...`). Como o plano de tarefas é arquivado e removido ao final da change, essas referências numéricas perdem o contexto no código permanente.
- **Como verificar:** Remover as menções a números de tarefas específicas nos comentários e substituílas apenas pela explicação direta da especificação que o teste cobre.

---

### 4. Falta de Confirmação Visual da Dashboard HTML
- **Arquivo e linha:** [`static/index.html`](file:///home/dreian/lab/webhook-lab/static/index.html) e [`tasks.md`](file:///home/dreian/lab/webhook-lab/openspec/changes/webhook-receiver-idempotent/tasks.md)
- **O que diverge:** A **Regra #8 de `AGENTS.md`** especifica: *"'Confirmar visualmente' é renderizar e olhar. Buscar o conteúdo da URL não é confirmação visual."* A tarefa 6.3 de `tasks.md` está marcada como concluída, mas não há um registro ou mecanismo automatizado para que o agente execute essa renderização e inspeção visual direta.
- **Como verificar:** O desenvolvedor (USER) deve rodar o servidor (`python3 -m app`), abrir `http://localhost:8000/` no navegador e certificar-se de que o design, listagem e cores dos status renderizam corretamente.
---

Nenhuma divergência de spec pendente para a branch `review/edge-case` após o commit `d54ef31` (ver item 6 em Correções Verificadas).
