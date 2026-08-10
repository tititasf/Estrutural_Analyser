# QA Global — Ciclo treino×validação, eficiência e autoridade (permitido vs proibido)

**SoT operacional** para o loop que o dono pediu:

> Usar o agente para **criar/refinar motores** de desenho e interpretação,
> decidir ajustes com **validade visual**, e **autoavaliar** se o ciclo de
> treino/validação do item foi eficiente — otimizando o processo ao longo do tempo.

Complementa (não substitui): `LOOPING-CANONICO.md`, `CONVENCAO-SELOS-VALIDACAO.md`,
`MASTERPLAN-AGENTE-QA-GLOBAL.md`, skill `qa-global-evidencias`.

---

## 1. O loop desejado (alinhado)

```text
item / família
  → TREINO: observar N1, achar causa, propor fórmula no motor (interpretação ou desenho)
  → REGEN:  gerar artefato afetado (N1 reprocess / N3 / N4 / ficha)
  → VISUAL: G2-V CLI + leitura (agente ou humano) dos SVGs/PNGs do manifesto
  → VALIDAR: adaptador/probe/dossiê — CONFIRMAR só com prova; origem qa_agente → 🟠
  → META:   rubrica de eficiência do ciclo → encurtar rota na próxima vez
```

Isso **é** o desenho correto. As proibições abaixo não matam o loop; evitam
degenerações (super-selo, hardcode, reescrita cega).

---

## 2. LLM / agente como juiz e o selo 🟠 laranja

### Concordância com o dono

O agente **está aí para julgar** campos e vínculos com evidência, e o sistema
já tem um selo **próprio** para isso:

| Selo | Origem | Quem emite | Significado |
|------|--------|------------|-------------|
| 🔵 Azul | `humano_app` | Humano no desktop | Campo confirmado na UI |
| 🌸 Rosa | `humano_portal` | Humano no portal | Campo confirmado na web |
| 🟠 Laranja | `qa_agente` | Agente QA Global | Campo confirmado pelo **juiz automatizado** com contrato SA |
| ✅ Verde | `is_validated` | Geral (fraco) | Validação grossa, sem granularidade |

Fonte: `docs/CONVENCAO-SELOS-VALIDACAO.md`.

O laranja:

- exige **100% dos campos obrigatórios** com origem `qa_agente` (ou N/A) — **isolado**;
- **não** se mistura com azul/rosa para “completar” cobertura;
- é o sinal de progresso da automação (peso pleno de propósito);
- só nasce de decisões do fluxo de evidência (`CONFIRMAR` / `N/A_CONFIRMADO` com
  adaptador + prova), **nunca** de “achei que está bom” sem grafo de prova.

### O que o juiz 🟠 pode (e deve) fazer

| Papel do LLM/agente | OK? | Selo / efeito |
|---------------------|-----|----------------|
| Ler SVGs/PNGs do G2-V, checklist visual, registrar PASS/FAIL/SUSPEITO | **Sim** | Veredito visual registrado (não é Arete completo sozinho) |
| Re-derivar geometria/contrato no adaptador e emitir `CONFIRMAR` | **Sim** | Origem `qa_agente` → caminho do 🟠 |
| Decidir ajuste de motor com base no visual (bug gerador/extrator/cota) | **Sim** | Entrada de engenharia → fix universal + teste |
| Aplicar (`apply`) campos já provados com comando explícito | **Sim** | Grava `qa_agente` nos campos; 🟠 quando 100% |
| Autoavaliar eficiência do ciclo (métricas) e encurtar rota | **Sim** | Meta-processo; não grava selo sozinho |

### Onde o “LLM-as-judge” era o hype a evitar

Não é “proibir o juiz laranja”. É proibir **dois abusos**:

1. **Juiz sem prova** — modelo dá PASS genérico e isso vira selo/Arete sem
   adaptador, sem SVG lido, sem checklist, sem dossiê.
2. **Juiz errado** — NIM/API de visão como scorer (já vetado no handoff);
   N2/N4 como prova de N1; ficha HTML como prova de si mesma.

**Regra curta:**  
🟠 = juiz **autorizado** do agente, com **contrato de evidência**.  
LLM solto sem contrato = **não** é 🟠.

---

## 3. Quadro permitido vs proibido

### Treino (refino de motor)

| Permitido | Proibido |
|-----------|----------|
| Usar item real (P35, V327…) como **caso de treino** | `if item == "P35": return OK` no motor |
| Fix por **fórmula geral** + teste +/− | Hardcode de obra/pavimento/cota medida de um recorte |
| Um fix por hipótese; regenerar e reabrir prova | “Subir score” da classe cosmético no golden |
| Teach com regra reutilizável + exemplos | Promover teach a RAG T2 sem humano |
| Consultar RAG T1/T2 citado | RAG como única prova de coordenada/nível |

### Validação / selo

| Permitido | Proibido |
|-----------|----------|
| `CONFIRMAR` com adaptador + evidência CAD/contrato | `CONFIRMAR` por similaridade textual ou bbox grosseiro em L/U |
| 🟠 `qa_agente` via apply do fluxo aprovado | Inventar 🔵/🌸/✅; laranja por maioria de indícios |
| G2-V CLI + checklist + pack de veredito | “Olhei o HTML” sem manifesto/SVGs |
| PASS de probe/campo **não** = ficha inteira Arete | Super-selo (score S / arquivo aberto = Arete ok) |
| N2/N4 só como **comparador** | N2/N4 alimentando N1/N3 ou “provar ficha com a ficha” |

### Visual (validade para ajustar motor)

| Permitido | Proibido |
|-----------|----------|
| Agente **lê** PNG/SVG do harness e decide FAIL→ajuste | API visual / NIM scorer sem ordem do dono |
| Visual como **gatilho de engenharia** | Visual LLM genérico como único selo de fôrma sem checklist |
| Registrar veredito (`qa_g2v_record_verdict`) | PASS visual sem G2-V = golden |
| Humano como juiz final em conflito novo / QG7 | Substituir dono em ambiguidade de manual |

### Meta / auto-evolução do processo

| Permitido | Proibido |
|-----------|----------|
| Rubrica de eficiência do ciclo (`cycle_efficiency`) | Reescrever código do motor/QA sem teste + golden |
| Otimizar **rota** (menos headless à toa, melhor probe) | Auto-promote de selo/RAG porque “o ciclo se avaliou bem” |
| Registrar tokens/custo (`record-llm`) | Ocultar custo e declarar eficiência |
| Evoluir perfis/docs/checklists com evidência | Self-rewrite de pesos/prompts sem regressão Arete |

---

## 4. Rubrica de eficiência do ciclo (treino × validação)

**Schema:** `arete.qa_cycle_efficiency/v1`  
**Emitido em:** `session_metrics.json` (campo `cycle_efficiency`) e bloco no `RESUME.md`.  
**Implementação:** `scripts/arete/qa_cycle_efficiency.py` + `qa_loop_executor.py`.

### 4.1 Sinais coletados (por run / item)

| Sinal | Como entra | Bom | Ruim |
|-------|------------|-----|------|
| `cycles_used` / `max_cycles` | state | baixo para fechar | esgota budget sem fecho |
| `train_steps` | eventos `cycle_phase=train` | ≥1 se houve bug | 0 com FAIL visual ignorado |
| `validate_steps` | `cycle_phase=validate` | ≥1 antes de apply/selo | apply sem validate |
| `visual_rounds` | `cycle_phase=visual` ou record visual | 1–2 por hipótese | N rodadas sem fix |
| `regen_count` | `cycle_phase=regen` | casa com fix | regen sem revalidar |
| `fix_count` | record kind=fix | 1 fix universal | muitos fixes locais |
| `routing_ok` | review/probe sem headless extra | rota mínima | headless “por padrão” |
| `rediscovery` | start new-run vs resume | resume | redescobrir do zero |
| `llm_tokens` / `cost_usd` | llm_usage | proporcional ao fecho | alto sem decisão |
| `closed_loop` | train→regen→visual→validate encadeados | true | visual órfão / fix sem visual |
| `outcome` | status final | CONFIRMAR/visual PASS / PENDENTE honesto | COMPLETE falso |

### 4.2 Notas (0–100) e grade

| Nota | Grade | Interpretação |
|-----:|:-----:|---------------|
| ≥ 85 | A | Ciclo fechado, rota enxuta, prova alinhada ao resultado |
| 70–84 | B | Fechou com desperdício moderado (ciclos/tokens/visual extra) |
| 50–69 | C | Resultado frágil ou loop incompleto |
| < 50 | D | Budget estourado, sem prova, ou super-selo |

Fórmula (pesos fixos, transparente):

```text
score =
  0.25 * closed_loop_score      # 100 se train→regen→visual→validate; 0 se faltar elo crítico
+ 0.20 * budget_score           # 100 * (1 - cycles_used/max_cycles) clamp
+ 0.15 * routing_score          # 100 se rota mínima; penaliza headless/probes em excesso
+ 0.15 * visual_discipline      # 100 se visual registrado; penaliza N rounds sem fix
+ 0.15 * outcome_honesty        # 100 se status coerente com tasks; 0 se COMPLETE sem visual quando exigido
+ 0.10 * cost_score             # tokens/custo normalizados (neutro se zero)
```

### 4.3 O que a rubrica **não** faz

- Não emite 🟠, 🔵, Arete nem promove RAG.
- Não autoriza apply.
- Não substitui G2-V nem adaptador.
- Serve para o agente **otimizar o processo** (próxima rota, quantos probes, quando abrir visual).

### 4.4 CLI e ganchos automáticos

**Automático (sem disciplina manual do agente):**

| Evento do executor | phase auto |
|--------------------|------------|
| `review` (evidence_review) concluiu | `validate` |
| `qa_pil_coverage` concluiu | `validate` |
| `record --kind visual` | `visual` |
| `record --kind fix` | `fix` + flag `pending_regen_after_fix` |
| próximo `advance` após fix | `regen` (assumido) e depois novo `validate` |
| `record --kind test` | `validate` |
| `teach` | `train` |
| `question` (pergunta estruturada) | `train` |

**Manual (quando o agente fez algo fora do executor):**

```text
python scripts/arete/qa_loop_executor.py record-cycle \
  --run RUN_ID --phase train|validate|visual|fix|regen \
  --result PASS|FAIL|DONE|SKIP --message "..."
```

```text
# tokens
python scripts/arete/qa_loop_executor.py record-llm --run RUN_ID --prompt-tokens N ...

# métricas
# → session_metrics.json → cycle_efficiency
# → RESUME.md seção "## Eficiência do ciclo"
```

---

## 5. Anti-super-selo (resumo de uma linha)

**Score de eficiência A + dossiê verde + 🟠 em um campo ≠ obra Arete.**  
🟠 é o juiz do **agente por campo/cobertura**; Arete de fôrma ainda exige gates de classe, G2-V quando aplicável e QG7/RAG quando for promoção.

---

## 6. Histórico

| Data | Nota |
|------|------|
| 2026-07-16 | Doc criado: loop dono + 🟠 como juiz autorizado + rubrica + permitido/proibido |
