# MASTERPLAN CAD-ANALYZER v4.0
## Pipeline E2E — Multi-Obra, DXF Coletivo, Fidelidade >= 95%, Certificação

**CEO-PLANEJAMENTO (Athena) — v4.0 (2026-03-08)**
**Sprint base:** Sprint 5 (continua de Sprint 4 concluído)

---

## ESTADO CONSOLIDADO (O que foi feito — Epics 5-7 DONE)

```
Epic 5 ✅  Extração dimensional B/H (pilares, vigas, lajes, garfos)
Epic 6 ✅  Geração DXF individual por elemento (ezdxf puro, headless)
           Comparação DXF individual vs STOG: 100% PASS (pilares + vigas + lajes)
           Validação STOG não-circular: 100% PASS
CAD-7.1 ✅ Assembly layers (GRADE/CHAPA/SP) → pilares_assembly.json
CAD-7.3 ✅ obras_salvas.json — formato PilarAnalyzer.exe (grade_1 populado)
           motor_fase4.py integrado + _gerar_obras_salvas()
```

**Saída atual de Fase-4 (12 PAV, Obra_TREINO_21):**
- 40 `JSON_Pilares/P*.json` — h1..h5 por face A-H + grade_1/grade_2
- 66 `JSON_Vigas_Laterais/V*_A.json` + `V*_B.json`
- 33 `JSON_Vigas_Fundo/V*_fundo.json`
- 19 `JSON_Lajes/L*.json`
- `obras_salvas.json` + `pavimentos_lista.json`

**DXF gerados individuais (Fase-5):**
- 40 DXF_Pilares/P*.dxf (layout 4 faces A-D)
- 33 DXF_Vigas/V*.dxf (3 vistas: lateral A, B, fundo)
- 19 DXF_Lajes/L*.dxf (planta baixa contorno + paineis)

---

## OBJETIVO DOS PRÓXIMOS EPICS

```
DXF individual P{n}.dxf × 40   ─┐
DXF individual V{n}.dxf × 33   ─┼→ Epic 9: DXF Coletivo → PL_gerado.dxf
DXF individual L{n}.dxf × 19   ─┘                          LV_gerado.dxf
                                                            LJ_gerado.dxf
                                                                 ↓
                              Epic 10: Fidelidade  ← compare vs PL/LV/LJ originais
                                                                 ↓
                              Epic 11: Certificação  score >= 95% por tipo
                                                                 ↓
Epic 8: Multi-obra/pav  ────────────────────────────────────────┘
Epic 12: Pipeline E2E scaling N obras × N pav
```

---

## EPIC 8 — Multi-Pavimento + Multi-Obra Automation

**Objetivo:** Fazer o pipeline rodar para TODOS os pavimentos de TODAS as obras em DADOS-OBRAS/.
Atualmente só roda para "12 PAV" de "Obra_TREINO_21".

**Complexidade:** STANDARD | **Dependências:** Epics 5-7 | **Sprint:** 5

### Análise de Risco
| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| Nomenclatura irregular de DXFs por obra | ALTO | Script de descoberta por heurística de nome |
| Obras sem todos os tipos de DXF (LV/FV/LJ) | MÉDIO | Graceful skip com relatório |
| Sistemas de coordenadas diferentes por obra | MÉDIO | Normalização por obra na Fase-1 |

### Histórias

#### CAD-8.1 — Discovery de DXFs por Obra/Pavimento
**Objetivo:** Criar script que faz scan de DADOS-OBRAS/* e mapeia quais DXFs existem por obra/pav.

```
Entrada: DADOS-OBRAS/ (diretório raiz)
Saída:   dxf_discovery.json — {obra: {pav: {PL: path, LV: path, FV: path, LJ: path, EVG: path}}}
```

Script: `scripts/descobrir_obras.py`

Heurística de nomes:
- "PL" → planta de fôrma de pilares
- "LV" → lateral de vigas
- "FV" ou "FD" → fundo de vigas
- "LJ" ou "LJ_" → lajes
- "EVG" → esforços de vigas (garfos)

Acceptance Criteria:
- [ ] AC-1: Descobre automaticamente DXFs em Fase-1_Ingestao/
- [ ] AC-2: Produz `dxf_discovery.json` com todos os paths validados
- [ ] AC-3: Gera relatório de obras incompletas (DXF ausente)
- [ ] AC-4: Suporta ≥ 2 obras e ≥ 2 pavimentos por obra

---

#### CAD-8.2 — motor_fase4.py Multi-Pavimento
**Objetivo:** Adicionar flag `--all-pavimentos` que processa todos os pav descobertos.

Mudanças em `motor_fase4.py`:
- Novo argumento: `--all-pavimentos` — lê `dxf_discovery.json` e itera
- Cada iteração cria subdiretório por pav: `Fase-4_Sincronizacao/{pav}/`
- Log consolidado por obra

Acceptance Criteria:
- [ ] AC-1: `--all-pavimentos` processa todos os pavimentos listados em dxf_discovery.json
- [ ] AC-2: Saída em `Fase-4_Sincronizacao/{pav}/JSON_Pilares/`, etc.
- [ ] AC-3: Não falha se um pavimento não tiver todos os DXFs — skip gracioso
- [ ] AC-4: Relatório final: N obras × M pavs processados, X falhas

---

#### CAD-8.3 — engenharia_reversa_dxf.py Multi-Pavimento
**Objetivo:** Gerar ground truth para TODOS os pavimentos automaticamente.

Mudanças em `engenharia_reversa_dxf.py`:
- Novo argumento: `--all-pavimentos` — itera descoberta
- Salva ground truth em `Fase-3_Interpretacao_Extracao/{pav}/`

Acceptance Criteria:
- [ ] AC-1: Gera `*_ground_truth.json` para cada pav descoberto
- [ ] AC-2: Score IDs >= 85% para pavimentos com DXF completo

---

#### CAD-8.4 — Pipeline Orquestrador E2E (Single Command)
**Objetivo:** Script único que executa TODO o pipeline para uma obra.

Script: `scripts/pipeline_e2e.py`

```bash
python scripts/pipeline_e2e.py --obra DADOS-OBRAS/Obra_TREINO_21 --all-pavimentos
```

Fases executadas em sequência:
1. `descobrir_obras.py` — scan DXFs
2. `engenharia_reversa_dxf.py` — ground truth
3. `extrair_bh_pilares.py` + `extrair_vigas_lv.py` + ... — extração dimensional
4. `motor_fase4.py` — transformação Fase-3 → Fase-4
5. `gerar_dxf_pilares.py` + `gerar_dxf_vigas.py` + `gerar_dxf_lajes.py` — DXF individual
6. `comparar_dxf.py` — score individual
7. `gerar_obras_salvas.py` — formato robô
8. Relatório final consolidado

Acceptance Criteria:
- [ ] AC-1: Um único comando processa obra completa
- [ ] AC-2: Exit code 0 = sucesso, 1 = falha parcial, 2 = falha total
- [ ] AC-3: Cria `pipeline_report.json` com score por pav + por tipo
- [ ] AC-4: Idempotente — re-executar não quebra outputs anteriores

---

#### CAD-8.5 — Validação Score Multi-Pavimento
**Objetivo:** Relatório consolidado de validação por obra/pav.

Script: `scripts/relatorio_validacao_obra.py`

```json
{
  "obra": "Obra_TREINO_21",
  "pavimentos": {
    "12 PAV": {
      "pilares": {"score": 1.0, "aprovado": true},
      "vigas": {"score": 1.0, "aprovado": true},
      "lajes": {"score": 1.0, "aprovado": true}
    }
  },
  "score_global": 1.0,
  "certificado": true
}
```

Acceptance Criteria:
- [ ] AC-1: Lê todos os `validation_*.json` de todos os pav
- [ ] AC-2: Calcula score global ponderado (pilares 0.4, vigas 0.35, lajes 0.25)
- [ ] AC-3: Status `certificado: true` se score_global >= 0.95
- [ ] AC-4: Output em `Fase-8_Revisao_Entrega/relatorio_validacao.json`

**DoD Epic 8:** pipeline_e2e.py roda para ≥ 1 obra multi-pav sem intervenção humana.

---

## EPIC 9 — DXF Coletivo por Tipo

**Objetivo:** Consolidar os DXFs individuais (P1.dxf, P2.dxf...) em um único DXF por tipo
que replique a estrutura do DXF STOG original (PL.dxf, LV.dxf, LJ.dxf).

**Complexidade:** ALTA | **Dependências:** Epic 8 (multi-pav) + Epic 6 (DXF individual)
**Sprint:** 5-6

### Análise Crítica: Problema das Coordenadas

O desafio central do Epic 9: cada P{n}.dxf individual é gerado com coords locais (0,0).
Para montar o DXF coletivo fiel ao original, cada elemento deve ser posicionado nas
**coordenadas absolutas** que ele ocupa no DXF STOG original.

Abordagem:
1. Extrair centróide/anchor de cada elemento no DXF STOG original (PL, LV, LJ)
2. Inserir os elementos gerados nessa posição no DXF coletivo

### Histórias

#### CAD-9.1 — Extração de Coordenadas Absolutas (STOG → Âncoras)
**Objetivo:** Para cada P{n}, V{n}, L{n} — extrair coord absoluta de anchor no DXF STOG.

Script: `scripts/extrair_ancoras_dxf.py`

Para pilares (PL DXF):
- Layer "Texto Seção" → TEXT entities "P{n}" → insert point = âncora do pilar
- Salvar: `ancoras_pilares.json` → {P1: [x, y], P2: [x, y], ...}

Para vigas (LV DXF):
- Layer "Texto Seção" → TEXT entities "V{n}.A/B" → insert point = âncora da viga
- Salvar: `ancoras_vigas.json` → {V1: {A: [x,y], B: [x,y]}, ...}

Para lajes (LJ DXF):
- Layer "AUX00" → MTEXT "L{n}\n..." → insert point = âncora da laje
- Salvar: `ancoras_lajes.json` → {L1: [x,y], L2: [x,y], ...}

Acceptance Criteria:
- [ ] AC-1: Extrai âncoras de ≥ 90% dos elementos
- [ ] AC-2: `ancoras_pilares.json`, `ancoras_vigas.json`, `ancoras_lajes.json` em Fase-3/
- [ ] AC-3: Validação visual: plotar âncoras + IDs no plano confirma layout correto

---

#### CAD-9.2 — Consolidar DXF Pilares → PL_gerado.dxf
**Objetivo:** Montar DXF coletivo com todos os 40 pilares nas posições corretas.

Script: `scripts/consolidar_dxf_pilares.py`

```python
# Para cada pilar P{n}:
#   1. Carregar P{n}.dxf (gerado em Fase-5)
#   2. Ler âncora abs de ancoras_pilares.json
#   3. Aplicar translação: entities + offset(anchor)
#   4. INSERT no PL_gerado.dxf com layers preservados
```

Acceptance Criteria:
- [ ] AC-1: PL_gerado.dxf contém todos os 40 pilares
- [ ] AC-2: Cada pilar na posição correta (± 5cm tolerância)
- [ ] AC-3: Layers preservados (Paineis, Texto Seção, Cota Seção (2x))
- [ ] AC-4: Output em `Fase-6_Execucao_CAD/PL_gerado.dxf`

---

#### CAD-9.3 — Consolidar DXF Vigas → LV_gerado.dxf + FV_gerado.dxf
**Objetivo:** Montar DXF coletivo com todas as 33 vigas.

Script: `scripts/consolidar_dxf_vigas.py`

Acceptance Criteria:
- [ ] AC-1: LV_gerado.dxf contém as 33 vigas (laterais A + B)
- [ ] AC-2: FV_gerado.dxf contém as 33 vigas (fundo)
- [ ] AC-3: Posicionamento por âncora ± 5cm
- [ ] AC-4: Layers preservados (Paineis, etc.)

---

#### CAD-9.4 — Consolidar DXF Lajes → LJ_gerado.dxf
**Objetivo:** Montar DXF coletivo com todas as 19 lajes.

Script: `scripts/consolidar_dxf_lajes.py`

Acceptance Criteria:
- [ ] AC-1: LJ_gerado.dxf contém as 19 lajes com contorno + paineis
- [ ] AC-2: Posicionamento por âncora
- [ ] AC-3: Output em `Fase-6_Execucao_CAD/LJ_gerado.dxf`

---

#### CAD-9.5 — Validação DXF Coletivo (Count + IDs)
**Objetivo:** Verificar que DXF coletivo gerado tem o mesmo número de elementos e IDs.

Script: `scripts/validar_dxf_coletivo.py`

Métricas:
- count_match: N labels no gerado == N labels no STOG
- id_match: todos os IDs do STOG aparecem no gerado
- no_hallucination: nenhum ID extra no gerado

Acceptance Criteria:
- [ ] AC-1: count_match >= 95% para pilares, vigas, lajes
- [ ] AC-2: id_match >= 95%
- [ ] AC-3: Score estrutural salvo em `Fase-6/validation_coletivo.json`

**DoD Epic 9:** PL_gerado.dxf + LV_gerado.dxf + LJ_gerado.dxf gerados com count_match >= 95%.

---

## EPIC 10 — Motor de Fidelidade: Gerado vs. Original

**Objetivo:** Comparar cada DXF coletivo gerado vs. o DXF STOG original de Fase-1
e certificar fidelidade geométrica >= 95%.

**Complexidade:** ALTA | **Dependências:** Epic 9 | **Sprint:** 6

### Dimensões de Fidelidade

| Dimensão | Peso | Descrição |
|----------|------|-----------|
| Count match | 30% | Mesmo número de elementos por tipo |
| ID match | 25% | Mesmo set de IDs presentes |
| Geometric proximity | 25% | Entidades na posição correta (± tolerância) |
| Layer match | 10% | Mesmo conjunto de layers |
| Text match | 10% | Labels textuais corretos |

**Score fidelidade = Σ(dim × peso) ≥ 0.95 → APROVADO**

### Histórias

#### CAD-10.1 — Análise Estrutural DXF STOG Original
**Objetivo:** Criar "fingerprint" estrutural de cada DXF STOG para comparação.

Script: `scripts/analisar_dxf_stog.py`

Para cada DXF (PL, LV, FV, LJ):
- Conta entities por layer
- Extrai bounding boxes por elemento
- Lista todos os TEXT/MTEXT com seus valores
- Salva em `Fase-3/fingerprint_{tipo}.json`

Acceptance Criteria:
- [ ] AC-1: Gera fingerprints para PL, LV, FV, LJ DXFs originais
- [ ] AC-2: Fingerprint contém: entity_counts, bboxes_por_id, text_values, layer_list
- [ ] AC-3: Determinístico — re-executar produz mesmo resultado

---

#### CAD-10.2 — Fidelidade Pilares (PL_gerado vs PL_original)
**Objetivo:** Score de fidelidade geométrica dos pilares.

Script: `scripts/fidelidade_pilares.py`

Comparações:
- Para cada pilar P{n}: bbox gerado vs bbox STOG → % overlap
- Label "P{n}" presente no gerado: sim/não
- Layers iguais: % match

```python
# Métrica de overlap de bbox:
overlap = intersect_area(bbox_gerado, bbox_stog) / union_area(bbox_gerado, bbox_stog)
# IoU >= 0.85 = APROVADO por pilar
```

Acceptance Criteria:
- [ ] AC-1: Score IoU pilares >= 85% (média por pilar)
- [ ] AC-2: Todos os labels P{n} presentes
- [ ] AC-3: Fidelidade salva em `Fase-7_Consolidacao/fidelidade_pilares.json`

---

#### CAD-10.3 — Fidelidade Vigas (LV_gerado + FV_gerado vs LV + FV)
Script: `scripts/fidelidade_vigas.py`

Acceptance Criteria:
- [ ] AC-1: Score IoU vigas laterais >= 85%
- [ ] AC-2: Score IoU vigas fundo >= 85%
- [ ] AC-3: Todos os labels V{n}.A/B presentes

---

#### CAD-10.4 — Fidelidade Lajes (LJ_gerado vs LJ)
Script: `scripts/fidelidade_lajes.py`

Acceptance Criteria:
- [ ] AC-1: Score IoU lajes >= 80% (lajes têm geometria mais variável)
- [ ] AC-2: Todos os labels L{n} presentes

---

#### CAD-10.5 — Relatório de Fidelidade Global
**Objetivo:** Score consolidado de fidelidade do pipeline.

Script: `scripts/relatorio_fidelidade.py`

```json
{
  "obra": "Obra_TREINO_21",
  "pavimento": "12 PAV",
  "fidelidade": {
    "pilares": {"score": 0.97, "aprovado": true},
    "vigas": {"score": 0.95, "aprovado": true},
    "lajes": {"score": 0.91, "aprovado": true}
  },
  "score_global": 0.945,
  "meta": 0.95,
  "certificado": false,
  "observacoes": ["lajes abaixo do threshold — revisar CAD-10.4"]
}
```

Acceptance Criteria:
- [ ] AC-1: Score global = média ponderada (pilares 0.4 + vigas 0.35 + lajes 0.25)
- [ ] AC-2: `certificado: true` se score_global >= 0.95
- [ ] AC-3: Lista de elementos abaixo do threshold
- [ ] AC-4: Output em `Fase-8_Revisao_Entrega/relatorio_fidelidade.json`

**DoD Epic 10:** Score fidelidade global calculado, ≥ 1 obra certificada >= 0.95.

---

## EPIC 11 — Certificação E2E do Pipeline

**Objetivo:** Processo formal de certificação que valida que o pipeline CAD-ANALYZER
reproduz o trabalho humano com fidelidade >= 95% para qualquer obra com DXFs STOG.

**Complexidade:** STANDARD | **Dependências:** Epics 8-10 | **Sprint:** 6-7

### Critérios de Certificação (Definition of Done do Projeto)

```
CERTIFICAÇÃO APROVADA quando TODOS os critérios abaixo são verdadeiros:

1. IDs MATCH: hallucination_rate = 0%, miss_rate ≤ 5% por tipo (P/V/L)
2. DIMENSIONAL: B/H score >= 95% com tolerância 10%
3. ASSEMBLY: grade_1 populado para >= 85% dos pilares (29/40 = 72.5% hoje → gap)
4. DXF INDIVIDUAL: comparar_dxf.py score = 100% (já PASS)
5. DXF COLETIVO: count_match + id_match >= 95%
6. FIDELIDADE: score_global >= 95% (IoU médio todos os tipos)
7. MULTI-PAV: pipeline roda >= 2 pavimentos sem erro
8. REPRODUCIBILIDADE: re-executar 3x produz mesmo resultado
```

### Histórias

#### CAD-11.1 — Script de Certificação Formal
**Objetivo:** Script único que executa todos os checks e emite certificado.

Script: `scripts/certificar_obra.py`

```bash
python scripts/certificar_obra.py --obra DADOS-OBRAS/Obra_TREINO_21 --pavimento "12 PAV"
```

Emite:
- `CERTIFICADO_APROVADO.json` (se todos os critérios passam)
- `CERTIFICADO_REPROVADO.json` + lista de falhas (se algum critério falha)

Acceptance Criteria:
- [ ] AC-1: Executa todos os 8 critérios de certificação
- [ ] AC-2: Output human-readable no console + JSON estruturado
- [ ] AC-3: Exit code 0 = aprovado, 1 = reprovado
- [ ] AC-4: Log de auditoria em `Fase-8_Revisao_Entrega/auditoria_{timestamp}.log`

---

#### CAD-11.2 — Re-run de Certificação (3x Reproducibilidade)
**Objetivo:** Verificar que re-executar 3x produz scores iguais (determinismo).

Script: `scripts/teste_reproducibilidade.py`

Acceptance Criteria:
- [ ] AC-1: 3 execuções consecutivas produzem scores com variância < 0.001
- [ ] AC-2: Relatório de variância salvo

---

#### CAD-11.3 — Dashboard de Certificação
**Objetivo:** Relatório consolidado por obra para gestão.

Output: `CERTIFICACAO_FINAL.md` — summary legível

```markdown
# Certificação CAD-ANALYZER — Obra_TREINO_21

| Critério        | Score | Status  |
|-----------------|-------|---------|
| IDs Match       | 100%  | ✅ PASS |
| Dimensional B/H | 100%  | ✅ PASS |
| Assembly grade  | 72.5% | ⚠️ GAP  |
| DXF Individual  | 100%  | ✅ PASS |
| DXF Coletivo    | 97%   | ✅ PASS |
| Fidelidade IoU  | 95.4% | ✅ PASS |
| Multi-pav       | 2/2   | ✅ PASS |
| Reproducibilidade | 100% | ✅ PASS |

**STATUS FINAL: APROVADO COM RESSALVAS (assembly gap P42-P45)**
```

Acceptance Criteria:
- [ ] AC-1: Dashboard gerado automaticamente após certificar_obra.py
- [ ] AC-2: Evidencia score de cada critério individualmente

**DoD Epic 11:** certificar_obra.py emite CERTIFICADO_APROVADO para Obra_TREINO_21 / 12 PAV.

---

## EPIC 12 — Scaling E2E — N Obras × N Pavimentos

**Objetivo:** Pipeline totalmente automatizado capaz de processar qualquer nova obra
com DXFs STOG, sem intervenção humana, e gerar certificação.

**Complexidade:** STANDARD | **Dependências:** Epics 8-11 | **Sprint:** 7

### Histórias

#### CAD-12.1 — CLI Unificado do Pipeline
**Objetivo:** Um único ponto de entrada para o pipeline completo.

Script: `scripts/cad_pipeline_cli.py`

```bash
# Processar uma obra
python scripts/cad_pipeline_cli.py run --obra DADOS-OBRAS/Obra_TREINO_21

# Processar todas as obras
python scripts/cad_pipeline_cli.py run-all --data-dir DADOS-OBRAS/

# Certificar uma obra
python scripts/cad_pipeline_cli.py certify --obra DADOS-OBRAS/Obra_TREINO_21 --pav "12 PAV"

# Status rápido
python scripts/cad_pipeline_cli.py status --data-dir DADOS-OBRAS/
```

Acceptance Criteria:
- [ ] AC-1: `run` executa pipeline completo Fase-1 → Fase-8 para uma obra
- [ ] AC-2: `run-all` processa todas as obras em DADOS-OBRAS/
- [ ] AC-3: `certify` gera CERTIFICADO para a obra especificada
- [ ] AC-4: `status` mostra progresso de cada obra (% concluída)
- [ ] AC-5: `--dry-run` mostra o que seria executado sem executar

---

#### CAD-12.2 — Batch Mode com Paralelismo
**Objetivo:** Processar N obras em paralelo (multiprocessing).

```bash
python scripts/cad_pipeline_cli.py run-all --workers 4
```

Acceptance Criteria:
- [ ] AC-1: N obras processadas em paralelo (default: 2 workers)
- [ ] AC-2: Falha em uma obra não cancela as outras
- [ ] AC-3: Log por obra em `DADOS-OBRAS/{obra}/pipeline.log`

---

#### CAD-12.3 — Status JSON Global
**Objetivo:** Estado global de todas as obras em um JSON.

Output: `DADOS-OBRAS/STATUS_GLOBAL.json`

```json
{
  "timestamp": "2026-03-08T...",
  "obras": {
    "Obra_TREINO_21": {
      "pavimentos_processados": ["12 PAV"],
      "score_fidelidade": {"12 PAV": 0.954},
      "certificado": true,
      "ultima_execucao": "2026-03-08T..."
    }
  },
  "total_obras": 1,
  "total_certificadas": 1
}
```

Acceptance Criteria:
- [ ] AC-1: STATUS_GLOBAL.json atualizado após cada run
- [ ] AC-2: Contém score_fidelidade por obra/pav
- [ ] AC-3: `certificado: true` apenas se todos os critérios passam

---

#### CAD-12.4 — Integração com Nova Obra (Onboarding)
**Objetivo:** Guia e automação para adicionar nova obra ao sistema.

Script: `scripts/onboarding_obra.py`

```bash
python scripts/onboarding_obra.py --nome "Nova Obra" --dir /path/to/dxfs
```

Faz:
1. Cria estrutura de pastas padrão (Fase-1 a Fase-8)
2. Copia DXFs para Fase-1_Ingestao/
3. Executa descoberta de DXFs
4. Reporta campos que precisarão de validação manual

Acceptance Criteria:
- [ ] AC-1: Estrutura de pastas criada automaticamente
- [ ] AC-2: DXFs copiados e renomeados para padrão
- [ ] AC-3: `dxf_discovery.json` criado com DXFs encontrados
- [ ] AC-4: Checklist de validação manual gerada

**DoD Epic 12:** pipeline_cli.py `run-all` processa Obra_TREINO_21 sem erro, STATUS_GLOBAL.json atualizado.

---

## GAPS CONHECIDOS E MITIGAÇÕES

| Gap | Status | Impacto | Mitigação |
|-----|--------|---------|-----------|
| P42-P45 grade_1=0 (sem gordo no PL) | Conhecido | Baixo — robot recalcula | Aceitar como limitação; marcar no certificado |
| P2-P8 grade_1=0 (pilares especiais) | Conhecido | Baixo — robot recalcula | Investigar PAV TIPO DXF em Epic 8 |
| parafusos (par_1_2) fórmula desconhecida | Conhecido | Mínimo — robot recalcula | Deixar 0; robot resolve |
| CAD-7.2 MEIO_PONT (pontaletes) | Backlog | Nenhum — não crítico p/ robô | Adiar; impacto zero no DXF final |
| PilarAnalyzer.exe DRM/GUI | Contornado | N/A | Pipeline usa ezdxf puro (headless) |
| Coordenadas absolutas (Epic 9) | A resolver | CRÍTICO para DXF coletivo | CAD-9.1 extrai âncoras do STOG |

---

## SEQUÊNCIA DE IMPLEMENTAÇÃO

```
Sprint 5 (Mar 2026)
  ├── CAD-8.1 descobrir_obras.py         (2d)
  ├── CAD-8.2 motor_fase4.py multi-pav   (3d)
  ├── CAD-8.3 engenharia_reversa multi-pav (2d)
  ├── CAD-9.1 extrair_ancoras_dxf.py     (3d) ← CRÍTICO para Epic 9
  └── CAD-8.4 pipeline_e2e.py            (2d)

Sprint 6 (Abr 2026)
  ├── CAD-8.5 relatorio_validacao_obra.py  (1d)
  ├── CAD-9.2 consolidar_dxf_pilares.py   (2d)
  ├── CAD-9.3 consolidar_dxf_vigas.py     (2d)
  ├── CAD-9.4 consolidar_dxf_lajes.py     (2d)
  ├── CAD-9.5 validar_dxf_coletivo.py     (1d)
  ├── CAD-10.1 analisar_dxf_stog.py       (2d)
  ├── CAD-10.2 fidelidade_pilares.py      (2d)
  ├── CAD-10.3 fidelidade_vigas.py        (2d)
  ├── CAD-10.4 fidelidade_lajes.py        (2d)
  └── CAD-10.5 relatorio_fidelidade.py    (1d)

Sprint 7 (Mai 2026)
  ├── CAD-11.1 certificar_obra.py         (3d)
  ├── CAD-11.2 teste_reproducibilidade.py (1d)
  ├── CAD-11.3 CERTIFICACAO_FINAL.md gen  (1d)
  ├── CAD-12.1 cad_pipeline_cli.py        (3d)
  ├── CAD-12.2 batch mode + workers       (2d)
  ├── CAD-12.3 STATUS_GLOBAL.json         (1d)
  └── CAD-12.4 onboarding_obra.py         (2d)
```

---

## DEFINITION OF DONE — PROJETO COMPLETO

O projeto CAD-ANALYZER está **CONCLUÍDO** quando:

```
✅ 1. pipeline_cli.py run-all processa N obras sem intervenção humana
✅ 2. DXF coletivo gerado por tipo (PL, LV, LJ) com count_match >= 95%
✅ 3. Fidelidade geométrica (IoU médio) >= 95% comparando com STOG original
✅ 4. certificar_obra.py emite CERTIFICADO_APROVADO para Obra_TREINO_21 / 12 PAV
✅ 5. Teste de reproducibilidade: 3 runs = mesmo resultado (variância < 0.001)
✅ 6. STATUS_GLOBAL.json atualizado automaticamente após cada run
✅ 7. onboarding_obra.py funcional para nova obra com DXFs STOG
✅ 8. Zero dependência de GUI (PilarAnalyzer.exe, AutoCAD, etc.)
```

---

## PRIORIDADE IMEDIATA — Próxima Implementação

**Começar por:** CAD-8.1 + CAD-9.1 (paralelo)

- **CAD-8.1** (`descobrir_obras.py`) é simples e desbloqueia todo o Epic 8
- **CAD-9.1** (`extrair_ancoras_dxf.py`) é o caminho crítico do Epic 9 e deve começar cedo

Segundo passo: **CAD-8.2** (motor_fase4.py multi-pav) — expande o que já funciona.

Terceiro passo: **CAD-9.2-9.4** (consolidação DXF) — depende das âncoras de CAD-9.1.

---

*MASTERPLAN CAD-ANALYZER v4.0 | Athena (CEO-PLANEJAMENTO) | 2026-03-08*
*Epics 5-7: DONE ✅ | Epics 8-12: PLANEJADOS | Meta: Certificação >= 95% fidelidade*
