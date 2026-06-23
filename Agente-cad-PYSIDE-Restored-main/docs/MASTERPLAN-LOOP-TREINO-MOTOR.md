# MASTERPLAN — Loop de Treino do Motor (Análise Geral → Gabarito Eng. Reversa)

**Versão:** 1.0
**Data:** 2026-06-20
**Orquestração:** Athena (CEO-Planejamento)
**Companion de:** `MASTERPLAN-FICHAS-F1-F9-HARMONIZACAO.md`
**Destinatário de execução:** modelo menor + squads responsáveis (§7). Cada etapa é auto-contida, com entrada/saída/critério.
**Status:** PLANEJAMENTO — pronto para execução incremental, sem migração destrutiva de DB.

---

## 0. Objetivo (uma frase)

Fazer o **"Análise Geral"** (motor dinâmico, zero hardcode) **convergir para o resultado do "Analisar com Eng Reversa"** (gabarito N2/F5) em **múltiplas obras**, usando o **Comparison Engine** como juiz e o **`domain_knowledge`** como validador semântico das regras.

---

## 1. Princípios Inegociáveis

1. **Eng. Reversa = consulta, nunca geração.** Consome fichas N2/F5 como gabarito. **NÃO gera nem sobrescreve F5** (`reverse_eng_fichas` são imutáveis; se reextrair, versionar via `status`). O **comparativo F7×F5** do loop é gravado em `engrev_*_learning.vision` + `*_calibrator_versions`, **nunca** em cima da F5. O que melhora é o **motor** (`transformation_rules`) e a **F7/N1**; a F5 fica fixa. Hoje o botão Eng Reversa faz só consulta+confirmação — ligar o `autovalidate_v3` para produzir o comparativo é o **S0**.
2. **Coordenadas do N2 = verdade.** `comprimento`/`largura` do N2 podem estar errados (5/98 lajes inconsistentes). Em conflito, a geometria de coordenadas vence.
3. **Zero hardcode.** Toda tolerância escala com as dims do teacher. Nenhuma constante fixa por obra.
4. **Generalização gated.** Parâmetro só vira default global após passar em **≥ 2 obras**.
5. **Validação semântica antes de ajustar.** Ao corrigir um campo divergente, consultar `domain_knowledge` para confirmar a regra (ex.: `grade_1 = comprimento+22`).
6. **Nada destrutivo de DB.** Aprendizado grava parâmetros versionados, nunca sobrescreve gabarito nem fichas validadas.
7. **Humano validado vence sempre.** Campos, recortes, contornos, links e itens com validacao humana (`is_validated=1`, `validated_fields_json`, `status='aprovado'` ou equivalente) sao fonte de verdade operacional. O loop pode ler esses dados como professor, pode registrar divergencias e pode propor ajustes no motor, mas **nunca sobrescreve, apaga ou rebaixa dado validado por humano**. Quando houver conflito entre N1 automatico, N2 reverso e validacao humana, a decisao humana validada prevalece.
8. **Entrevista e acao manual sao parte do loop.** O agente executor pode fazer perguntas pontuais ao dono ou pedir uma acao manual pequena (ex.: validar um item, marcar um contorno correto, confirmar uma regra de campo, enviar print/PNG ou aprovar/reprovar um caso) quando isso reduzir ambiguidade e aumentar a compreensao do motor. Essas intervencoes devem ser registradas como aprendizado reutilizavel (`training_events`, `engrev_*_learning.vision`, `domain_knowledge` ou documentacao da classe), nao como hardcode silencioso.

---

## 2. O Loop (algoritmo de referência)

```
PARA cada OBRA:
  PARA cada PAVIMENTO:
    PARA cada CLASSE (PIL, VF, VL, LAJ):

      1. GABARITO   = F5/N2 da classe (coordenadas = verdade)
      2. CANDIDATO  = "Análise Geral" reproduz SEM teacher_coords direto
                      (usa só parâmetros aprendidos: search_radius, layers, tolerâncias)
      3. JUÍZO      = Comparison Engine: N1(F7) vs N2(F5)
                      → hit-rate por item + lista de campos divergentes
      4. DIAGNÓSTICO= para cada divergência, classificar:
                      (a) erro de parâmetro do motor   → ajustar parâmetro dinâmico
                      (b) regra semântica mal aplicada  → consultar domain_knowledge (ex: ignorar pilares NASCE e VISAO_CORTE no Fundo de Viga)
                      (c) gabarito inconsistente (comp/larg) → confiar na coordenada
                      (d) dado humano validado existente → preservar e usar como verdade
                      (e) ambiguidade operacional → perguntar ao dono ou pedir validacao manual pontual
      5. AJUSTE     = atualizar parâmetros dinâmicos do motor (NÃO constantes):
                      - tolerâncias ∝ dims do teacher
                      - filtro de camadas de cota (rejeita linhas de camadas c/ textos numéricos)
                      - _should_prefer_n2_axes_outline (comparação bidirecional de dims)
                      - nunca escrever por cima de campos/itens validados por humano
      6. GATE-CLASSE= repetir 2–5 até hit-rate = 100% na classe
                      → registrar parâmetros aprendidos (com proveniência: obra/pav/classe)

    GATE-PAVIMENTO = todas as 4 classes em 100%
  GATE-OBRA        = todos pavimentos em 100% → candidatar parâmetros ao "teacher global"

PROMOÇÃO GLOBAL    = parâmetro só vira default após validar em ≥ 2 obras (princípio #4)
```

---

## 2.5 Auditoria de Coerência (2026-06-20) — Como o motor REALMENTE aprende

> Auditoria dos stores reais (`project_data.vision`, Chroma, learning DBs) contra o objetivo: compreensão global, zero hardcode exceto RAG da própria obra.

**✅ Motor data-driven (zero hardcode):** `transformation_rules.rule_logic` = `dna_frequency_map` — para cada assinatura geométrica (DNA, ex. `"1.0,0.0,0.0,1000.0"`) guarda `most_common` + `distribution` + `global_frequency_map` + `global_default`. Aprende por frequência a partir de eventos; nenhuma constante fixa.

**✅ Loop adaptativo fechado e conectado:** `training_events` (901) captura `user_validation` / `user_rejection` / `user_na` por campo (ex.: `Laje_laje_outline_segs` = 202 validações + 20 rejeições + 14 NA). Esses eventos atualizam (a) o `dna_frequency_map` das regras e (b) os `learned_dx/dy` no Chroma.

**✅ Chroma = retrieval espacial (2282 emb):** por campo guarda `local_geometry` + `learned_dx/dy`. Item novo → busca geometria semelhante → aplica offset aprendido. Per-obra via `project_id` na metadata.

**✅ `domain_knowledge`** (66 chunks `field_semantics`) = âncora semântica de ambos os fluxos.

### ⚠️ GAP CRÍTICO #V — Dois vocabulários de campo sem tradução

O fluxo **Análise Geral (N1)** e o **Eng. Reversa (N2/F5)** usam nomes de campo **incompatíveis**:

| Classe | N1 (regras/Chroma/training) | N2 (`reverse_eng_fichas.campos_json`) |
|--------|------------------------------|----------------------------------------|
| PIL | `Pilar_p_sA_l1_n`, `Pilar_p_sA_l1_h`, `Pilar_dim` (granular por linha/lado) | `h1_A..h5_A`, `larg1_A..larg3_A`, `laje_A`, `comprimento` (colunas consolidadas) |
| VIG/FV | `Viga_name`, `Viga_dim`, `Viga_viga_a_seg_1_ini_name` | `total_width`, `total_height`, `segments_rich`, `holes`, `sarrafo_left/right_id` |
| LAJ | `Laje_laje_dim`, `Laje_laje_visao_corte`, `Laje_laje_vizinhas_niveis`, `Laje_laje_pilares_apoio`, `Laje_laje_nivel`, `Laje_laje_outline_segs` | `comprimento`, `largura`, `linhas_verticais/horizontais`, `obstaculos`, `coordenadas`, `visao_corte`, `vizinhas_niveis`, `pilares_apoio` |

**Consequência:** o Comparison Engine alinha **geometria (coordenadas)** mas não os **campos** → hit-rate de coordenada OK, campos não convergem. **Bloqueia a convergência field-level do loop.**

**Correção (não hardcoded):** o **Mapa de Equivalência de Vocabulário** (FASE 0.5, §5.2) é **derivado do `domain_knowledge`** (que descreve ambos os nomes e fórmulas, ex. `grade_1 = comprimento+22`), não escrito à mão.

---

## 3. Métricas & Quality Gates

| Gate | Métrica | Threshold | Fonte |
|------|---------|-----------|-------|
| G-Item | hit-rate de item (match coordenada) | 100% | Comparison Engine (autovalidate_v3) |
| G-Campo | campos preenchidos corretos / total | ≥ 95% | F7 vs F5 |
| G-Semântico | campos com `semantic_ref` válido | ≥ 90% | domain_knowledge |
| G-Generalização | obras em que o parâmetro mantém 100% | ≥ 2 | cross-obra |
| G-Regressão | obras já certificadas que NÃO pioram | 0 regressões | suíte de obras-treino |

**Referência de qualidade:** Obra_TREINO_20 (score 100%, fid 87.7). Obra-piloto do loop: **Obra_TREINO_1, pavimento 13** (`project_id 4869be2b-f17c-410b-a9c8-98a887ec1c95`, 101 lajes).

---

## 4. Artefatos & INFRA REAL (auditoria 2026-06-20 — NÃO RECRIAR)

> ⚠️ A infra de treino **já existe** no banco. O loop **estende** o que está aqui; não cria `learned_params.json` nem tabelas novas.

| Componente | Real | Estado |
|-----------|------|--------|
| Motor Cego (SlabTracer) | `src/core/slab_tracer.py` (~1300 L) | gera o CANDIDATO |
| Análise Geral | `main.py · process_pillars_action()` (~L4450) | dispara motor dinâmico |
| Eng. Reversa (consulta gabarito) | `main.py · _process_with_reverse_engineering()` (~L5189) | lê N2 |
| **Motor dinâmico de regras** | tabela `transformation_rules` (**23 regras**, `coverage_pct`/`accuracy_pct`/`version`/`is_production`) | ATIVO — coverage baixa (1–20%) na maioria |
| **A/B de regras** | tabela `ab_test_batch` (0) + `rule_evaluation_log` (0) | infra pronta, sem uso |
| **Eventos de treino** | tabela `training_events` (**901**, `context_dna_json`+`target_value`) | capturando |
| **Loop N1↔N2 (laje)** | `engrev_laj_n1_interpretacao_learning.vision` (**14 eventos**: `bbox_n1` vs `bbox_n2`, `accepted_line_count`) | iniciado |
| **Calibração de recorte (laje)** | `engrev_laj_recorte_learning.vision` (**130 eventos**: `delta_left/right/bottom/top` motor vs aprovado) | iniciado |
| **Promoção de versão** | tabelas `*_calibrator_versions` (`params_json`/`metrics_json`/`status`) | **0 promovidos** |
| Juiz | `learning_engine_code/autovalidate_v3.py` | compara Motor vs N2 |
| Consolidação F6 | `scripts/motor_reverso_obra.py` | fix `consolidar_obra_er` |
| Validador semântico | `domain_knowledge` (217) + `scripts/domain_knowledge_ingestor.py --query` | confirma regras |
| Gabarito N2 | `reverse_eng_fichas` (902) + `projects_repo/<id>/laje_data/obras.json` | fonte da verdade |

---

## 5. Política de Parâmetros Aprendidos (zero hardcode) — usa a infra existente

Os parâmetros aprendidos **NÃO** vão para um JSON novo. Vivem nas tabelas que já existem:

- **Regras** → `transformation_rules` (campos `rule_logic`, `version`, `coverage_pct`, `accuracy_pct`, `ab_test_id`, `is_production`). Cada refinamento = nova `version` da regra; promoção = `is_production=1`.
- **Calibração por classe** → `*_calibrator_versions` (`params_json` = parâmetros que escalam com dims do teacher; `metrics_json` = hit-rate; `status` = candidate→promoted).
- **Pattern atual = laje** (`engrev_laj_*`). **As demais classes (PIL/VF/VL) replicam este pattern** — criar `engrev_pil_*`, `engrev_fv_*`, `engrev_lv_*` seguindo o mesmo schema, **só quando** a classe entrar no loop (S2).

**Regra de promoção (princípio #4):** `calibrator_versions.status` só vira `promoted` após `metrics_json` manter 100% em **≥2 obras**; antes disso, `is_production=0`. Promoção dispara G-Regressão em todas as obras-treino.

---

## 5.1 PROCEDIMENTO — Execução do Loop (usando a infra real)

> Para o modelo menor executar. Cada passo aponta para a tabela/arquivo real. **Nada de estrutura nova.**

**PASSO 1 — Ingestão de evento.** Ao usuário validar/rejeitar/marcar NA um campo no Structural Analyzer ou Diagnostic Reverse Hub → gravar em `training_events` (`type` ∈ {user_validation, user_rejection, user_na}, `role`=`{Classe}_{campo}`, `context_dna_json`, `target_value`).

**PASSO 2 — Atualização da regra.** Recalcular `transformation_rules.rule_logic.dna_frequency_map` para o `role` afetado: incrementar `distribution[target]` no bucket da DNA; recomputar `most_common`, `global_default`, `coverage_pct`, `accuracy_pct`. **Nova `version`** da regra (nunca sobrescrever a anterior).

**PASSO 3 — Atualização do offset espacial.** Se o campo tem posição → atualizar/inserir no Chroma (`local_geometry` + `learned_dx/dy` + `project_id`). Item futuro consulta por geometria semelhante.

**PASSO 4 — Candidato vs Gabarito.** "Análise Geral" produz N1(F7); `autovalidate_v3` compara contra N2(F5) via Comparison Engine. Gravar deltas em `engrev_{classe}_n1_interpretacao_learning.vision` (`bbox_n1` vs `bbox_n2`, `accepted_line_count`).

**PASSO 5 — Calibração.** Quando hit-rate da classe sobe, registrar `*_calibrator_versions` (`params_json` com k's que escalam com dims do teacher, `metrics_json`, `status=candidate`).

**PASSO 6 — Promoção.** `status candidate→promoted` + `transformation_rules.is_production=1` somente após manter 100% em **≥2 obras** (G-Generalização) sem regressão (G-Regressão).

**PASSO 7 — Preservacao humana.** Antes de qualquer UPSERT em N1/F7 ou tabela espelho (`beam_elements`, `slab_elements` etc.), verificar se existe dado humano validado no item/campo correspondente. Se existir, preservar o valor validado, gravar o delta como evento de aprendizado e ajustar o motor para convergir futuramente. O loop nao deve "corrigir" a decisao humana automaticamente.

**PASSO 8 — Perguntas e microtarefas ao dono.** Se o diagnostico numerico/visual nao explicar uma divergencia, o agente pode pedir ao dono uma decisao ou acao manual pequena e objetiva: validar/reprovar um elemento, selecionar o boundary certo, confirmar qual campo e fonte de verdade, ou explicar uma convencao de desenho. A resposta vira conhecimento persistente antes da proxima iteracao.

## 5.1.1 PROCEDIMENTO — Interpretacao Visual no Loop (ferramenta obrigatoria da Fase A)

> A interpretacao visual complementa o score numerico. Ela serve para o agente entender **o que esta sendo analisado** no desenho estrutural limpo e verificar se os vinculos/contornos detectados pela aba da classe em teste realmente correspondem ao item estrutural correto.

Para cada rodada relevante do loop de uma classe (LAJ, FV, LV, PIL), o agente deve poder gerar e inspecionar tres tipos de imagem headless:

1. **Estrutural limpo.** Render do pavimento/DXF limpo, sem contornos, sem overlays de itens e sem vinculos destacados. Objetivo: enxergar a geometria base como o motor recebeu, avaliar densidade, linhas auxiliares, cotas, vazios, regiões conectadas e possiveis fontes de poluicao.
2. **Estrutural + vinculos da classe em teste.** Mesmo render limpo, mas com destaque dos contornos/vinculos detectados pela aba da classe da Análise Geral que esta no loop. Exemplos: poligonos de LAJ, segmentos de fundo FV, laterais LV, contornos/arestas PIL. Objetivo: validar visualmente se o motor fechou o boundary correto, se pegou vizinho, se cortou borda, se incluiu linhas/cotas/pontaletes indevidos, ou se perdeu parte do item.
3. **Estrutural + vinculos de um unico item.** Quando o diagnostico por classe ficar poluido ou ambiguo, gerar uma imagem focada em um item especifico (`L302`, `V302`, `P12` etc.), mantendo o estrutural limpo de fundo e destacando apenas os vinculos/contornos daquele item. Objetivo: isolar a causa do erro sem interferencia visual de outros itens.

### Uso no diagnostico

- O agente deve comparar o diagnostico numerico N1xN2 com a imagem correspondente antes de alterar o motor em problemas de geometria.
- Se o PNG de classe mostrar muitos overlays, o agente deve gerar o modo de item unico para pelo menos um caso representativo do erro.
- Se ainda houver ambiguidade visual, o agente pode pedir ao dono uma microacao manual: confirmar boundary correto, validar/reprovar o item, apontar qual linha pertence ao item, ou explicar uma convencao do desenho.
- As conclusoes visuais devem virar evento/nota de aprendizado: exemplo, "boundary pequeno por crop cortando borda", "region growing vazou para componente vizinho", "linha de cota foi confundida com borda", "texto de dimensao capturado longe do label".

### Artefatos esperados

- PNG limpo: `{classe}_{obra}_{pav}_limpo.png`
- PNG da classe: `{classe}_{obra}_{pav}_vinculos.png`
- PNG de item unico: `{classe}_{obra}_{pav}_{item}_vinculos.png`

Esses renders devem ser headless, sem PySide6/Qt, e nao podem depender de filtro fixo por layer. Eles sao ferramenta de interpretacao do loop, nao fonte de verdade por si so; a fonte de verdade continua sendo N2/F5 e qualquer validacao humana existente.

## 5.1.2 PROCEDIMENTO LAJ — Nivel por visao de corte de vigas

Para LAJ, o campo `laje_nivel` deve representar apenas o texto de nivel proprio da laje. A visao de corte das vigas ao redor da laje e os pilares de apoio sao vinculos semanticos separados, processados antes do nivel textual quando o texto proprio nao existe.

Regras operacionais:

- `laje_nivel` aceita somente `label` (`Vinculo Texto (Nivel)`). Nao registrar geometria de corte nem pilar neste campo.
- `laje_visao_corte` deve aceitar multiplos vinculos `cut_view_geom`, pois uma laje pode ser contornada por 4 ou mais vigas e ter mais de uma visao de corte relevante. Cada vinculo pode ter ficha propria editavel com direcao, viga, lajes lado A/B, alturas e distancias.
- `laje_vizinhas_niveis` e campo proprio, separado da visao de corte. Suas classes de vinculo sao `neighbor_north` (↑ Vizinha Norte), `neighbor_east` (→ Vizinha Leste), `neighbor_west` (← Vizinha Oeste) e `neighbor_south` (↓ Vizinha Sul).
- `laje_vizinhas_niveis` deve ser preenchido com nomes, alturas e niveis das lajes vizinhas ortogonais, mesmo quando a laje atual nao possui `cut_view_geom`. A visao de corte nao e pre-condicao para capturar esses textos; ela apenas muda como a inferencia usa o contexto.
- `laje_pilares_apoio` deve aceitar `pillar_geom` e `pillar_label`, separando pilares retangulares, circulares, L, U ou T das geometrias de visao de corte.
- Diferenca visual esperada: pilares sao geometrias compactas/fechadas de apoio e nao carregam cotas/referencias de lajes; visao de corte tem marco de corte/desnivel, cotas/textos e referencias das lajes vizinhas.
- Se a laje tem texto explicito de nivel validado por humano, esse valor vence e nao pode ser sobrescrito.
- Se a laje nao tem texto explicito, mas tem `laje_visao_corte`, ela e tratada como laje especial. O motor deve primeiro tentar parear a mesma geometria de corte com outra laje que tenha nivel validado, ou ler textos/medidas da ficha do proprio corte e do campo `laje_vizinhas_niveis`. Nao usar automaticamente o nivel de uma vizinha comum so porque esta encostada.
- Se a laje nao tem visao de corte, o motor pode buscar vizinhas sem visao de corte e com nivel textual/validado. Havendo consenso, preencher `laje_nivel` como inferido e deixar para validacao humana.
- Vizinhas com visao de corte nao entram como referencia de nivel comum, porque provavelmente representam descontinuidade/desnivel especial.
- Toda conclusao inferida deve registrar proveniencia (`level_inference`, fonte da laje vizinha, tipo de vinculo, confianca) e ficar revisavel; nao marcar como humano-validado automaticamente.
- Migração: vinculos humanos antigos em `laje_nivel.cut_view_geom` devem ser reaproveitados em `laje_visao_corte`; textos antigos de `laje_visao_corte.neighbor_level_text` devem ser migrados logicamente para `laje_vizinhas_niveis`, sem exigir nova validacao manual.

### Registro LAJ — Obra_TREINO_1 pav. 13 (checkpoint 2026-06-21)

Comando de loop:

```bash
python -X utf8 scripts/laje_analise_geral_headless.py --obra Obra_TREINO_1 --pav 13
```

Iteracoes registradas:

- Baseline inicial do clone LAJ: 12,2% de score medio.
- Remocao de filtro implicito por layer de cota no `SlabTracer`: queda temporaria para 11,1%, confirmando que layer numerico nao pode ser usado como filtro fixo.
- Preferencia de eixos estruturais, crop adaptativo e fallback de linhas/cotas: subida para 67,8%.
- Selecao por eixos elite + fallback de linhas: 71,1%.
- Selecao por pares de bordas paralelas: 80,0%.
- Ajuste de contagem de linhas para preservar `raw = estimado + 1` em painéis altos: L323 passou de 70% para 100%, score medio 81,1%.
- Aumento da penalizacao de `pair_gap` na selecao por pares: L309 e L320 passaram para 100%, score medio 85,6%.
- Tentativa rejeitada: heuristica de "faixa baixa" com eixos completos regrediu para 75,6% por estreitar L327/L330; foi revertida.
- UI alinhada ao loop: o botao Análise Geral agora executa LAJ com `valid_layers=None` e `teacher_dims=None`, e FV com `BeamTracer` cru, sem parametros de learning store como entrada do N1. N2/F5 permanece apenas para consulta/comparacao posterior.

Estado atual:

- N1 detectado: 31 lajes.
- N2 comparado: 27 fichas LAJ.
- Score medio: 85,6%.
- Falhas restantes principais: L308, L312, L319, L326, L329, L331.
- Diagnostico agregado: 6/27 fora de CxL/area (+-5%), 1/27 com linhas/cotas divergentes, 0/27 pontaletes divergentes.
- Renders headless gerados em `sandbox_laje_loop/`: estrutural limpo, overlay da classe LAJ e focos por item (`--debug-laje L319`, `--debug-laje L329`, etc.).

## 5.2 PROCEDIMENTO — Fase C por classe: Entrevista & Mapa de Campos (resolve GAP #V, POR CLASSE)

> **NÃO é fase global.** Roda **por classe, depois que a geometria (Fase A) e os campos básicos (Fase B) já dão base.** Deriva o mapa N1↔N2 do `domain_knowledge` + **entrevista ao dono** para campos sem semântica clara.

0. **Gatilho:** só iniciar para uma classe após Fase A (geometria 100%) + Fase B (campos básicos: nome, nº itens, nº segmentos, dims).
1. **Extrair vocabulários da classe:** campos N1 (`SELECT DISTINCT name FROM transformation_rules WHERE name LIKE '{Classe}_%'`) e N2 (`keys(campos_json)` da classe em `reverse_eng_fichas`).
2. **Consultar semântica:** para cada par candidato, `python scripts/domain_knowledge_ingestor.py --query "<campo>"` → obter a definição/fórmula que liga os dois nomes (ex.: `Pilar_p_sA_l1_h` ↔ `h1_A`; `Viga_dim` ↔ `total_height`+`total_width`).
2b. **Entrevista (campos sem semântica clara) — UMA A UMA:** quando o domain_knowledge não explicar um campo/vínculo, **perguntar ao dono no momento em que a dúvida surge** (não em lote), uma pergunta de cada vez; gravar cada resposta como novo chunk no domain_knowledge (vira conhecimento reutilizável) antes de seguir para o próximo campo.
3. **Materializar:** gravar o mapa em `semantic_rag_kb` (tabela SQLite **vazia hoje**, cols `classe/regra_semantica/obra_contexto/confianca`) — um registro por equivalência, com `regra_semantica` = JSON `{n1_field, n2_field, transform, domain_ref}`.
4. **Decomposição/agregação:** registrar quando N1 é granular (por linha/lado) e N2 é consolidado (colunas `h1_A..h5_A`) → o mapa carrega a regra de agregação/expansão.
5. **DoD:** Comparison Engine passa a alinhar **campo a campo** (não só geometria) usando `semantic_rag_kb` como dicionário. Cobertura ≥90% dos campos por classe.

**Invariante:** o único dado "fixo por obra" permitido é o **RAG da própria obra** (contexto per-`project_id` no `dna_frequency_map` e na metadata do Chroma). Tudo mais é frequência/geometria aprendida.

---

## 6. Roadmap — ATAQUE POR CLASSE (decisão do dono 2026-06-20)

> **O trabalho é particionado por CLASSE.** Cada classe é um caso independente e segue o mesmo trilho A→B→C. **Geometria primeiro, campos depois.** Não há fase global única bloqueando tudo — o GAP #V (vocabulário) vira a **Fase B/C de cada classe**, não um pré-requisito do todo.

### Trilho por classe (aplica-se a LAJ, FV, LV, PIL)

| Fase | Foco | DoD | Infra |
|------|------|-----|-------|
| **A — Geometria** | Motor reproduz os MESMOS itens/contornos/coordenadas que o N2 (vínculo geométrico da classe) | hit-rate geométrico = 100% vs N2 na obra-piloto | `engrev_{classe}_n1_interpretacao_learning.vision` (bbox_n1 vs bbox_n2) |
| **B — Campos básicos** | Após geometria: nome, nº de itens, nº de segmentos, dimensões corretos | campos básicos ≥95% vs N2 | `transformation_rules` + `training_events` |
| **C — Entrevista de campos** | Para campos/vínculos divergentes entre N1 e N2: **entrevistar o dono** o significado e a regra de validação; mapear N1↔N2 via `domain_knowledge` → `semantic_rag_kb` | dicionário da classe completo; Comparison valida campo-a-campo | `semantic_rag_kb` + domain_knowledge (§5.2) |

### Estado por classe (referência inicial — refinar com o dono)

| Classe | Fase A (geometria) | Fase B/C (campos) | Próximo passo |
|--------|--------------------|--------------------|---------------|
| **LAJ** (laje) | ⏳ avançada (já iniciada) | pendente | fechar geometria → campos |
| **FV** (fundo de viga) | ⏳ avançada (já iniciada) | pendente | fechar geometria → campos |
| **LV** (lateral de viga) | ❌ a descrever | pendente | **dono descreve o vínculo geométrico → Athena formaliza** |
| **PIL** (pilar) | ❌ a descrever | pendente | **dono descreve o vínculo geométrico → Athena formaliza** |

> Cada classe que entra no loop ganha seu `engrev_{classe}_*` (replicando o pattern `engrev_laj_*`). LV e PIL precisam primeiro da **descrição do vínculo geométrico pelo dono** (que então é formalizada no plano), como hoje existe para LAJ/FV, antes de entrar no loop.

> **⚠️ Mismatch estrutural FV/LV (achado 2026-06-20):** no **N1 a viga é UM item** (`beams`, com fundo+laterais juntos), mas no **N2 são fichas separadas** (`reverse_eng_fichas`: FV=271, LV=229). Logo, na **Fase C de FV e LV** o loop precisa **decompor a viga N1** nos aspectos *fundo* (campos `viga_fundo_*`) e *laterais* (campos `viga_a_seg_*`/`viga_b_seg_*`) para comparar 1:1 com o N2. Pilares e Lajes não têm esse problema.

> **GATING (decisão do dono):** nenhuma classe inicia o loop sem ordem explícita do dono. Este masterplan é **planejamento**; a execução é disparada manualmente, classe a classe.

### Fundação (uma vez, antes das classes)
- **S0** — Fix `consolidar_obra_er` (F6); ligar `autovalidate_v3` ao botão Eng Reversa; confirmar gravação em `engrev_laj_*` + `calibrator_versions`.

### Cross-classe (depois das classes convergirem)
- **G1 — Generalização:** validar parâmetros de cada classe em ≥2 obras (G-Generalização) sem regressão.
- **G2 — Autonomia:** loop roda por LLM sem intervenção manual; meta = Análise Geral atinge nível N2 em obra nova (= "compreensão global": dicionário → autonomia).

---

## 7. Divisão por Squad (execução em modelo menor, por classe)

| Bloco | Squad responsável | Saída |
|-------|-------------------|-------|
| S0 fundação (motor reverso, autovalidate) | `Dados:STOGIntelligence-AIOS` + `Desenvolvimento:Dev-AIOS` | loop roda E2E |
| Fase A por classe (geometria) | `CAD:CadFase3Interpretacao-AIOS` | hit-rate geométrico 100% |
| Fase B/C por classe (campos + entrevista) | `Dados:RagForge-AIOS` + dono (entrevista) | dicionário N1↔N2 em `semantic_rag_kb` |
| G1 generalização cross-obra | `Dados:FeatureForge-AIOS` | params promovidos |
| G2 autonomia multi-obra | `Dados:CeoData-AIOS` + `CEOs:CEO-CAD-ANALYZER` | loop multi-obra |
| Quality gates / regressão | `Desenvolvimento:QA-AIOS` | suíte de não-regressão |

---

## 8. Riscos & Mitigações

| Risco | Mitigação |
|-------|-----------|
| Motor "decora" a obra-piloto (overfit) | G-Generalização exige ≥2 obras antes de promover |
| Gabarito N2 com comp/larg errado contamina aprendizado | Princípio #2: coordenada vence; diagnóstico (c) |
| Hardcode reintroduzido sob pressão | Lint/review: literais de tolerância proibidos; parâmetros vivem em `transformation_rules` + `*_calibrator_versions` (§5) |
| Regressão em obra já certificada | G-Regressão obrigatório antes de cada promoção |
| Acoplamento semântico atrasa o loop | S4 é paralelo, não bloqueia S1–S3 |

---

## 9. Referências
- `docs/MASTERPLAN-FICHAS-F1-F9-HARMONIZACAO.md` (taxonomia + semântica)
- `docs/MASTERPLAN-ENGENHARIA-REVERSA.md` (dual-flow)
- `docs/MASTERPLAN-ARETE-QUALITY-GATES.md` (gates G0–G6)
- Sessão Gemini: `…\6a039944-…\.system_generated\logs\transcript.jsonl` (passos 3411, 4402 = fluxo de treino)
