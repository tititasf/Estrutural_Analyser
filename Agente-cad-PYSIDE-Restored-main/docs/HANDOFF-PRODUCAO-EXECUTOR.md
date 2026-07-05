# HANDOFF — Executor de Stories (Produção & Qualidade)
**De:** Fable (Estrategista) | **Para:** sessão executora (modelo menor)
**Data:** 2026-07-03 | **Modo:** autônomo DENTRO da story; parar e perguntar FORA dela

> Este handoff existe para você executar UMA story por sessão, sem precisar entender o
> projeto inteiro. Cada story em `docs/stories/STORY-EXEC-*.md` é autocontida: diz o que
> ler, o que pode tocar, o que é proibido e como provar que terminou.

---

## 1. Regra número zero

**Execute APENAS a story que o dono te passar. Uma por sessão.**
Se no meio do caminho você achar que precisa de algo fora da story (outro arquivo,
outra decisão, outro escopo): **PARE e pergunte**. Não improvise. Não "aproveite para
melhorar" nada que a story não pediu.

## 2. Leia antes de agir (nesta ordem, só isto)

1. `CLAUDE.md` (raiz do repo) — regras inegociáveis + fatos do ambiente
2. A sua story (`docs/stories/STORY-EXEC-*.md`)
3. Os docs que a PRÓPRIA story listar (nunca mais que 3)

## 3. Fatos do ambiente (verificados 2026-07-03 — use, não redescubra)

| Item | Valor |
|------|-------|
| Python obrigatório | `C:\Users\Thierry\AppData\Local\Programs\Python\Python312\python.exe` (NUNCA 3.13/3.14) |
| DB real (read-only p/ você) | `D:/Agente-cad-PYSIDE/project_data.vision` |
| Status real do projeto | rode `python scripts/arete/gerar_status.py` → `docs/STATUS.md` (fonte de verdade; números em docs escritos à mão podem estar velhos) |
| Harness Arete | `scripts/arete/` (runner: `arete_runner.py`; relatórios: `scripts/arete/relatorios/`) |
| Golden set | `GOLDEN/{obra}/{pav}/{classe}/` — NUNCA selar com FAIL |
| Log de triagem | `scripts/arete/relatorios/triagem_erros/*.jsonl` — LER antes de qualquer fix |
| Headless: 1 por vez | Trava anti-OOM ativa. Rode SEMPRE com `--wait` em automação; se abortar dizendo "já existe execução", aguarde — **PROIBIDO matar o processo detentor** |

## 4. Proibições globais (valem em TODA story, sem exceção)

- ❌ Hardcode de valor medido de um item/recorte. Todo fix é FÓRMULA GERAL a partir da
  ficha (Regra de Ouro do `MASTERPLAN-ARETE-QUALITY-GATES.md`).
- ❌ Editar arquivos de UI (`src/ui/...`) — EXCETO se a story disser explicitamente qual
  arquivo e o dono confirmou que nenhuma outra sessão o está editando.
- ❌ Modificar geradores STOG / motores reversos sem causa comprovada por G1/G2 — e todo
  toque neles exige regressão do golden (`arete_runner.py --regressao`) verde antes de fechar.
- ❌ Selar golden com qualquer gate FAIL. ❌ Criar exceção de divergência sem aprovação
  humana. ❌ Concluir "não podem ser idênticos" — a frase certa é "parte X diverge em Y,
  hipóteses A/B, preciso de decisão".
- ❌ Expandir escopo (outra classe, outro pavimento, outra obra) além do que a story define.
- ❌ Tocar em `project_data.vision` para ESCRITA, em JSONs Fase-4, ou em DXFs de obras.
- ❌ Git: sem push para main; commits locais na branch de sessão.

## 5. Como fechar a sessão (obrigatório)

1. Critério de PASS da story atendido e PROVADO (comando + saída, não afirmação).
2. `python scripts/arete/gerar_status.py` rodado de novo (STATUS.md atualizado).
3. Se a story tocou motor/gerador: entradas correspondentes do log de triagem
   atualizadas (`fix_aplicado`, `status`) — omissão disso já causou retrabalho real.
4. Relatório curto no final da conversa: o que mudou (arquivos), o que foi provado
   (comandos/saídas), o que ficou aberto.

## 6. Stories prontas

| Story | O que faz | Risco |
|-------|-----------|-------|
| ~~`STORY-EXEC-01-FV-SARR5CM.md`~~ | **CONCLUÍDA 03/07 (Fable):** fix no comparador (`SKIP_LAYERS_G2['FV']` + `SARR_5cm`/`SARR_CONTORNO_10cm`); FV 26/26, golden re-selado | — |
| ~~`STORY-EXEC-04-LAJ-LINHAS-HORIZONTAIS.md`~~ | **CONCLUÍDA 03/07:** gerador emitia uniões como LWPOLYLINE, motor reextrai como LINE; fix de 8 linhas em `gerar_lj_dxf_stog.py` (~L501), motor intocado. LAJ 31/31 + regressão FV 26/26 e PIL 35/35; golden re-selado; JSONL atualizado (23 verificados) | — |
| ~~`STORY-EXEC-05-RECONCILIACAO-CONCORDANCIA.md`~~ | **CONCLUÍDA 03/07:** PIL 24→13 reais, FV 34→22, LV 20→14 (resto estrutural); achados N1 com evidência visual em `RECONCILIACAO-2026-07-03.md`; `triagem_concordancia.py` entregue com testes; convergência dupla em L312/L315 | — |
| ~~`STORY-EXEC-02-FLAG-SECAO.md`~~ | **CONCLUÍDA 03/07:** `_export_html_snapshot(sections=None)` (default idêntico, provado por diff vazio vs rodada de referência) + `--secao` no headless com fail-fast; ~100s vs ~315s (3x); 12/12 testes | — |

> **Follow-up de performance anotado (não é story ainda):** `_generate_fv_n3_nova_previews`
> (subprocessos N3 NOVA por viga FV) ainda roda incondicionalmente mesmo com
> `--secao lajes` — é o próximo gargalo óbvio se quiserem espremer mais velocidade.
> Fora do escopo da EXEC-02 por decisão correta do executor.
| ~~`STORY-EXEC-03-DIAG-LAJ-HEADLESS.md`~~ | **CONCLUÍDA 03/07:** pós-processo generalizado (`_run_section_diagnostics`, manifesto schema v2 com as 4 classes, bloco injetado até em subpastas via rglob); 5/5 testes; run real confirmado | — |

---
*Fable — 2026-07-03. Dúvida sobre intenção do plano: `docs/MASTERPLAN-PRODUCAO-SOBERANIA.md`.*
