# Relatório de Gate de Segurança — App de Consulta Pública

**Story:** STORY-15 (gate obrigatório de release, `architecture.md` §5.4/§11, `prd.md` §7/§8.2/§10)
**Data da última execução:** 2026-07-12
**Executor:** Claude (dev), suíte automatizada
**Comando:** `pytest consulta-publica-api` (raiz do repo)

---

## Veredicto

## ✅ GO (automatizado) — condicionado a AC11 (gate manual, ver abaixo)

**94/94 testes passando** em todo `consulta-publica-api/`, incluindo os
**27 testes da suíte de segurança dedicada** (`tests/security_suite/`,
criada por esta story) que cobrem os 10 primeiros critérios de aceite
(AC1–AC10) desta story. Nenhum CRITICAL ou HIGH pendente.

---

## Cobertura por Acceptance Criteria

| AC | Descrição | Status | Arquivo(s) |
|----|-----------|--------|-----------|
| AC1 | POST/PUT/DELETE/PATCH → 405 em 100% das rotas | ✅ PASS | `test_no_write_verbs.py` (6 rotas reais × 4 verbos = 24 combinações, todas 405) |
| AC2 | 1000 códigos aleatórios → 100% 404/429, rate-limit dispara, zero vazamento | ✅ PASS | `test_enumeration_1000.py` — confirmado: `200 not in status_codes`, `500 not in status_codes`, `429 in status_codes` (rate-limit disparou de fato), todos os 404 têm corpo idêntico |
| AC3 | Código de obra A nunca resolve dado de obra B | ✅ PASS | `test_cross_obra_isolation.py` — 6 testes cobrindo `/resolve`, `/ficha`, `/svg`, `/obra`, `/paineis-lv` |
| AC4 | Path traversal via `code`/`nivel` → 404, nunca lê fora de `DADOS_OBRAS_ROOT` | ✅ PASS | `test_path_traversal.py` — obra_dir fabricado fora da raiz (svg + paineis-lv), payloads clássicos de traversal em `/resolve` e `/svg/{nivel}` |
| AC5 | Nenhum campo da blacklist em nenhuma resposta | ✅ PASS | `test_schema_blacklist.py` — varredura recursiva de todo o JSON de `/resolve`, `/ficha`, `/obra`, `/paineis-lv` |
| AC6 | DB aberto `mode=ro` de fato (não só por convenção) | ✅ PASS | `test_ro_db_and_imports.py::test_conexao_real_da_api_e_fisicamente_read_only` — INSERT/UPDATE/DELETE reais, todos falham com `OperationalError` |
| AC7 | Zero import de `auth`/`access`/`repository`/`connection`/`lv_generation_contract`/PySide6 | ✅ PASS | `test_ro_db_and_imports.py::test_nenhum_arquivo_da_api_publica_importa_modulo_proibido` — scan estático de TODO `.py` sob `consulta-publica-api/` |
| AC8 | Item/obra revogado → 404 idêntico a "nunca existiu" | ✅ PASS | `test_revocation.py` — 5 testes (`/resolve`, `/ficha`, `/svg`, `/obra`, e confirmação de que revogar 1 item não afeta irmãos ativos) |
| AC9 | Relatório único de gate GO/NO-GO | ✅ PASS | Este documento |
| AC10 | CORS bloqueia origem não autorizada | ✅ PASS | `test_ro_db_and_imports.py::test_cors_bloqueia_origem_nao_autorizada_em_endpoint_real_com_dado` — reconfirmado contra `/ficha/{code}` (dado real), não só `/health` |
| AC11 | Teste de usabilidade de campo (≥5 usuários, ≥3 obras) | ⏸️ **PENDENTE — gate manual, não bloqueante para este merge** | Ver seção "Gate Manual" abaixo |

---

## Resumo da suíte completa

```
94 passed in ~11.6s
```

Distribuição:
- **27 testes** em `tests/security_suite/` (novos nesta story — consolidam e expandem a cobertura de segurança das stories 01–07, 12)
- **67 testes** pré-existentes das STORY-01 a STORY-14 (schema/publisher, skeleton API, resolve, rate-limit/CORS/auditoria, ficha, svg, obra, paineis-lv, isolamento estrutural)

Nenhum teste foi removido ou enfraquecido para este gate passar — a suíte
nova é **aditiva**, reusando o mesmo padrão de fixture (`httpx.ASGITransport`,
Publisher/schema real) já estabelecido nas stories anteriores.

---

## Achados desta story

Nenhum bug de produção novo foi encontrado — a suíte confirmou que as
proteções já implementadas nas STORY-01–14 seguram sob uma bateria mais
agressiva e combinada (múltiplos endpoints × múltiplas obras × payloads
adversariais simultaneamente, em vez de testados isoladamente por story).

Único ajuste necessário foi na fixture de teste (`conftest.py`): o
primeiro rascunho tentou inserir um item "revogado" reutilizando a MESMA
identidade `(obra_id, pavimento, classe, item_id)` de um item ativo, o que
viola o índice único `idx_public_codes_item_identity` do schema real —
corrigido dando ao item revogado uma identidade própria (`P1_OBRA_A_REVOGADO`),
o que é também o comportamento correto: revogação real (`publisher.publish.revogar`)
atualiza a MESMA linha, nunca cria uma duplicata.

---

## Gate Manual (AC11) — Pendente

**Não implementável em código.** Requer coordenação humana:

- **Responsável:** @po / @ux (per Dev Notes da story)
- **Critério:** ≥5 usuários reais (funcionário de fôrma + construtor) em
  ≥3 obras distintas, ≥4 de 5 completam a consulta N1/N3 (+ painéis LV
  quando aplicável) na primeira tentativa, sem treinamento formal, em <5s
  em 4G.
- **Bloqueia:** apenas o **lançamento** do MVP (não bloqueia merge de
  código nem deploy em ambiente de staging/homologação).
- **Status:** não agendado nesta sessão — recomendação: o dono do produto
  deve coordenar este teste de campo antes do lançamento público.

---

## Débitos técnicos conhecidos (não bloqueantes para este gate)

Documentados nos Dev Agent Records de cada story individual:
- STORY-06: otimização `svgo` no publish-time não implementada (SVG servido cru do motor).
- STORY-11: pinch de 2 dedos não implementado (alternativa por botão/teclado já cobre o requisito real de acessibilidade).
- STORY-14: verificação ao vivo do cache offline de SVG não pôde ser confirmada no Browser pane sandboxado desta sessão (lógica coberta por teste automatizado; recomienda-se confirmação manual em browser real antes do lançamento).
- Sem pipeline de CI configurado ainda para `consulta-publica-api`/`consulta-publica-web` — esta suíte deve ser adicionada como gate bloqueante de deploy quando o CI for configurado (Subtask 8.1 desta story, fora do escopo de uma sessão sem acesso a infraestrutura de CI real).

---

## Como reexecutar este gate

```bash
cd "D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main"
"C:\Users\Thierry\AppData\Local\Programs\Python\Python312\python.exe" -m pytest consulta-publica-api -v

# Só a suíte de segurança dedicada:
"C:\Users\Thierry\AppData\Local\Programs\Python\Python312\python.exe" -m pytest consulta-publica-api\tests\security_suite -v
```

Este relatório deve ser regenerado/atualizado a cada execução relevante
(nova story tocando `consulta-publica-api/**`, ou antes de qualquer deploy
em produção) — conforme `prd.md` §10, a suíte verde é o único gate
inegociável de release do MVP.
