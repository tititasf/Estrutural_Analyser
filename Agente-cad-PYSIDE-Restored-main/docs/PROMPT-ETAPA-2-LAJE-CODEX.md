## MISSÃO
Implementar o **loop de treino da classe LAJE**: fazer o motor **"Análise Geral" (SlabTracer)** convergir para o **gabarito N2 (Eng. Reversa)** das lajes, na ordem **A) geometria → B) campos → C) entrevista**. A Análise Geral deve reproduzir o N2 **sem `teacher_coords` direto**, com **zero hardcode**. Escopo = **só LAJE**. **Pré-requisito:** Etapa 1 concluída.

## LEIA ANTES (em `...\docs\`)
1. `MASTERPLAN-LOOP-TREINO-MOTOR.md` ← principal (§2, §2.5, §5.1, §5.2, §6) · 2. `MASTERPLAN-FICHAS-F1-F9-HARMONIZACAO.md` (F5=N2/gabarito, F7=N1/candidato) · 3. `MASTERPLAN-ARETE-LAJE.md` + `MASTERPLAN-RECORTE-LAJE-APRENDIZAGEM.md` · 4. `SEMANTICA-LAJE-NOVA.md`

## REPO/BANCO/MOTOR
- Raiz: `D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main` · Banco REAL: `D:\Agente-cad-PYSIDE\project_data.vision`
- Motor laje: `src/core/slab_tracer.py` (ajustar — parâmetros dinâmicos) · Juiz: `learning_engine_code/autovalidate_v3.py`
- Análise Geral: `main.py·process_pillars_action()` · Eng Reversa: `main.py·_process_with_reverse_engineering()`
- Gabarito N2: `projects_repo/<project_id>/laje_data/obras.json`

## INFRA QUE JÁ EXISTE (REUSAR)
`reverse_eng_fichas` LAJ=177 (GABARITO/F5) · `fase3_fichas` laje=80 (CANDIDATO/F7) · `engrev_laj_n1_interpretacao_learning.vision` (bbox_n1 vs bbox_n2) · `engrev_laj_recorte_learning.vision` (deltas) · `*_calibrator_versions` (promoção) · `transformation_rules` Laje_* (dna_frequency_map) · `training_events` · Chroma (Laje_* offsets).
Campos N2: `numero,nome,comprimento,largura,coordenadas,area_cm2,linhas_verticais/horizontais,obstaculos,pontaletes,cotas_paineis`. Campos N1: `Laje_name,Laje_laje_dim,Laje_laje_outline_segs,Laje_laje_nivel,Laje_id_item,Laje_laje_islands`.

## PRINCÍPIOS
1. **Coordenadas N2 = verdade** (comp/larg podem estar errados — 5/98). 2. **Zero hardcode** — tolerâncias escalam com dims do teacher; parâmetros em `transformation_rules`+`calibrator_versions`. 3. Eng Reversa = consulta. 4. Promoção só após 100% em **≥2 obras** sem regressão. 5. Único "fixo por obra" = RAG da própria obra.

## FASE A — GEOMETRIA (primeiro)
SlabTracer reproduzir contornos/coords das lajes = N2, sem teacher_coords. A1: rodar `autovalidate_v3` (deltas → `engrev_laj_n1_interpretacao_learning.vision`). A2: ajustar parâmetros dinâmicos (search_radius, layers, tolerâncias; filtro camadas de cota; `_should_prefer_n2_axes_outline` bidirecional). A3: registrar em `calibrator_versions` (status=candidate). **Aceite: hit-rate geométrico = 100%.**

## FASE B — CAMPOS (depois)
nome, dimensões, nº lajes, nº segs de contorno, nível. B1: atualizar `dna_frequency_map` da role (nova version). B2: offset no Chroma. **Aceite: campos ≥95% vs N2.**

## FASE C — ENTREVISTA (uma a uma)
C1: consultar `domain_knowledge_ingestor.py --query`. C2: campo sem semântica → **perguntar ao dono UMA por vez**, gravar resposta no domain_knowledge. C3: mapa N1↔N2 em `semantic_rag_kb` (classe='LAJ'). **Aceite: Comparison campo-a-campo ≥90%.**

## GATES
G-Item=100% · G-Campo≥95% · G-Semântico≥90% · G-Generalização ≥2 obras · G-Regressão 0 (ref. Obra_TREINO_20=100%).

## RESTRIÇÕES
NÃO recriar `engrev_laj_*` · NÃO op destrutiva (backup `.vision`) · NÃO hardcode · só LAJE · branch separada, edições cirúrgicas.

## ENTREGÁVEL
A→B→C na obra-piloto **Obra_TREINO_1 pav 13** (`project_id 4869be2b-f17c-410b-a9c8-98a887ec1c95`), `calibrator_versions` populado, validar 2ª obra antes de promover. Relatório em `docs/ETAPA-2-LAJE-RELATORIO.md`. Comece medindo o baseline geométrico com `autovalidate_v3` antes de ajustar.
