# Fontes de conhecimento — status

> Gerado por `scripts/kb/kb_inventario.py` em 2026-09-29. Não editar à mão: a curadoria vai em `fontes_override.yaml` e o arquivo é regenerado.

| Status | Qtde | Significado |
|---|---:|---|
| entrada | 5 | lido por todo agente antes de agir |
| canonico | 72 | citado por uma entrada ou marcado canónico — é a verdade vigente |
| ativo | 142 | em uso (tocado desde 2026-07-01 ou citado) |
| historico | 56 | registro do passado; consultar só para entender decisões |
| legado | 40 | marcado descontinuado/obsoleto — não seguir |
| candidato_obsoleto | 0 | sem uso aparente — revisar para arquivar/remover |

## Stores de conhecimento fora do texto

| Store | Onde | Status | Estado medido |
|---|---|---|---|
| kb_global | `KB-GLOBAL` | vivo | índice desta base (kb_build.py); derivado, reconstruível |
| semantic_rag_kb | `project_data.vision` | vivo | tabela de regras tieradas (T0/T1/TX); consumida por qa_rag_evidence/qa_rag_curation; 117 regras, 8 T1 |
| rag_artifact_validations | `project_data.vision` | vivo | validações de artefato N3/N4 + políticas de lock; até 2026-07-22 |
| qa_session_index | `Agente-cad-PYSIDE-Restored-main/scripts/arete/qa_session_index.py` | latente | mini-RAG de sessão por pavimento (SQLite); D0–D3 concluídos em julho, sem uso desde |
| obra_rag_db | `DADOS-OBRAS` | latente | LanceDB por obra (obra_docs/obra_dxf_inventory); ligado à app PySide (project_manager, obra_rag_pipeline) |
| bytereover_context_tree | `Agente-cad-PYSIDE-Restored-main/.brv/context-tree` | legado | 83 notas ByteRover; última escrita 2026-08-01; conteúdo coberto pelos docs canônicos |
| lancedb_stog_rag_db | `DADOS-OBRAS/stog_rag_db` | legado | domain_knowledge + stog_kbs; embedder NIM; última escrita 2026-06-04; substituído pela KB global |
| faiss_vectors | `data/vectors/faiss` | legado | 213 vetores de 2026-05-28, todos T0 (nunca validados); tombstones até 2026-07-21 |

## entrada (5)

| Fonte | Título | Data | Citado por | Motivo |
|---|---|---|---:|---|
| `Agente-cad-PYSIDE-Restored-main/AGENTS.md` | AGENTS.md — Codex / Antigravity / qualquer agente que não leia CLAUDE.md | 2026-09-25 | 0 | ponto de entrada dos agentes |
| `Agente-cad-PYSIDE-Restored-main/CLAUDE.md` | CLAUDE.md — Estrutural Analyzer (CAD-ANALYZER) | 2026-09-26 | 3 | ponto de entrada dos agentes |
| `Agente-cad-PYSIDE-Restored-main/docs/CONHECIMENTO/MAPA-DO-CONHECIMENTO.md` | Mapa do Conhecimento — base global da empresa | 2026-09-28 | 9 | ponto de entrada dos agentes |
| `Agente-cad-PYSIDE-Restored-main/docs/LOOPING-CANONICO.md` | LOOPING CANÔNICO — o único loop válido (e a quarentena dos obsoletos) | 2026-09-25 | 28 | ponto de entrada dos agentes |
| `CLAUDE.md` | CLAUDE.md — Workspace CAD-ANALYZER (raiz de dados + app) | 2026-09-25 | 33 | ponto de entrada dos agentes |

## canonico (72)

| Fonte | Título | Data | Citado por | Motivo |
|---|---|---|---:|---|
| `AGENTS.md` | AGENTS.md — workspace CAD-ANALYZER (ponteiro fixo) | 2026-07-11 | 8 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/.agents/AGENTS.md` | AGENTS | 2026-07-01 | 3 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/.agents/skills/cad-jev-sa/SKILL.md` | Jev como segunda leitura do SA | 2026-09-29 | 2 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/GEMINI.md` | GEMINI.md — ponteiro fixo (não editar; manter 1 fonte só) | 2026-07-05 | 2 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/ARETE-LOOP-PROCEDIMENTO-GERAL.md` | ARETE — Procedimento Geral de Looping por Classe (Fichas HTML + Diagnóstico Duplo) | 2026-08-10 | 22 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/ARETE-TRIAGEM-ERROS.md` | Arete — Triagem de Erros (ciclo marcar → logar → corrigir → reverificar) | 2026-07-02 | 7 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/ARQUITETURA-DB-COMPLETA.md` | ARQUITETURA DB — CAD-ANALYZER | 2026-06-25 | 3 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/ARQUITETURA-INTERPRETADORES-VIGA-N1-ISOLADOS.md` | Arquitetura N1 — Interpretadores de viga isolados | 2026-07-09 | 9 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/CALCULOS_ALGORITMOS.md` | Algoritmos de Cálculo — Sistema NOVA CAD | 2026-06-25 | 4 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/CONHECIMENTO/CONTRATO-KB-MULTIOBRA.md` | Contrato — KB global e KB por obra | 2026-09-25 | 3 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/CONHECIMENTO/DECISOES-DO-DONO.md` | Registro de decisões do dono | 2026-09-29 | 6 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/CONHECIMENTO/GLOSSARIO.md` | Glossário — base global da empresa | 2026-09-29 | 2 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/CONHECIMENTO/MAPA-CODIGO.md` | Mapa de código | 2026-09-26 | 2 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/CONHECIMENTO/PLANO-HARMONIZACAO.md` | Plano de harmonização do conhecimento | 2026-09-26 | 9 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/CONTRATO-QA-RAG-LOOPINGS.md` | Contrato QA ↔ RAG ↔ Loopings Arete | 2026-08-10 | 10 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/CONTRATO-RIGIDO-MOTOR-LV-N3-N4.md` | Contrato Rigido do Motor LV N3/N4 | 2026-09-27 | 10 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/CONVENCAO-SELOS-VALIDACAO.md` | Convenção de Selos de Validação | 2026-08-10 | 15 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/GIT_DVC_GUIDE.md` | Git + DVC — Guia de Trabalho do Projeto | 2026-06-25 | 2 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/HANDOFF-ARETE-EXECUTOR.md` | HANDOFF — Executor Arete Quality Gates (Cowork) | 2026-08-10 | 6 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/HANDOFF-DEVOPS-VPS-HETZNER.md` | HANDOFF-DEVOPS — VPS Hetzner (servidor principal, substitui o modelo workstation+Tailscale) | 2026-09-12 | 4 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/INDICE-DOCS-QA.md` | Índice de Documentação QA — Roteamento para Agente e Humano | 2026-08-10 | 0 | marcado Status: canónico |
| `Agente-cad-PYSIDE-Restored-main/docs/INTERPRETACAO-PILARES-ABCD.md` | Interpretação de Lajes e Vigas que Passam para Pilares ABCD | 2026-08-10 | 9 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/INTERPRETACAO-VIGA-CHEGA-VAO-E-FACE.md` | Interpretação — quando a viga "chega" na face do pilar | 2026-08-23 | 4 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/LV-COMPREENDER-INTERPRETACAO-FICHAS-N2-N4.md` | LV - Compreensao De Interpretacao N2/N4 | 2026-09-13 | 10 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/MASTERPLAN-ARETE-QUALITY-GATES.md` | MASTERPLAN — Arete Quality Gates: Paridade N2→N4 e Convergência N1→N3 | 2026-08-10 | 24 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/MASTERPLAN-CONSOLIDACAO-ENTREGA.md` | MASTERPLAN — Consolidação e Entrega | 2026-08-10 | 4 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/MASTERPLAN-ENGENHARIA-REVERSA.md` | MASTERPLAN — Engenharia Reversa & Dual-Flow Comparison Engine | 2026-06-25 | 7 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/MASTERPLAN-JEV-SA-EXPLORACAO.md` | Masterplan — Jev para interpretar a planta estrutural no SA/N1 | 2026-09-29 | 2 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/MASTERPLAN-LOOP-LV-N2-VISION-N4.md` | MASTERPLAN - Loop LV N2 Vision -> N4 DXF | 2026-06-25 | 4 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/MASTERPLAN-OBRAS-DRIVE.md` | Masterplan — OBRAS DRIVE (integração app desktop ↔ portal web) | 2026-07-13 | 3 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/MASTERPLAN-PRODUCAO-SOBERANIA.md` | MASTERPLAN — Produção & Soberania: do laboratório ao uso real da equipe | 2026-08-10 | 14 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/MATERIAIS-E-CONSTRUCAO.md` | Materiais e Construção — quantitativo de painéis e sarrafos | 2026-09-29 | 3 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/NIVEL-SEGMENTO-FUNDO-VIGA.md` | Nível por segmento de fundo de viga | 2026-09-12 | 1 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/PADRAO-SVG-WEB-PANZOOM-VIEWBOX.md` | Padrão canônico — SVG web com pan/zoom (viewBox) | 2026-08-10 | 8 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/PADRAO-TAGS-DESTAQUE-AGENTICO-PIL.md` | Padrão canônico — tags do destaque PIL (SA + camadas QA) | 2026-09-12 | 5 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/PERSISTENCIA-HEADLESS-SA.md` | Persistência transacional do headless SA | 2026-08-10 | 9 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/PIPELINE-VISAO-N2-N3-N4-ANTIALUCINACAO.md` | Pipeline de visão anti-alucinação — N2 · N3 · N4 (desenho) vs N1 (interpretação) | 2026-08-10 | 4 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/PLANO-PREPROCESSAMENTO-PAVIMENTO-TORRES.md` | Pré-processamento por pavimento e torre — plano de execução | 2026-09-22 | 2 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/POLITICA-CONFIANCA-RAG.md` | Politica de Confianca RAG | 2026-06-26 | 7 | curadoria: tiers T0/T1/T2/TX valem para a KB global e para semantic_rag_kb |
| `Agente-cad-PYSIDE-Restored-main/docs/PROCEDIMENTO-QA-FV-N1-CONTEXTUAL.md` | Procedimento QA — Fundos de Viga (N1 Contextual Unificado) | 2026-08-10 | 8 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/PROCEDIMENTO-QA-LAJ-N1-CONTEXTUAL.md` | Procedimento QA — Lajes (N1 Contextual) | 2026-08-10 | 3 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/PROCEDIMENTO-QA-LV-N1-CONTEXTUAL.md` | Procedimento QA — Laterais de Viga (N1 Contextual) | 2026-08-10 | 2 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/PROCEDIMENTO-QA-PIL-N1-CONTEXTUAL.md` | Procedimento QA — PIL N1 contextual + looping de destaque agêntico | 2026-08-10 | 4 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/PROVENIENCIA-CAMPOS-FV.md` | Proveniência de campos FV — contrato inicial | 2026-08-10 | 7 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/PROVENIENCIA-CAMPOS-LAJ.md` | Proveniência de Campos — LAJ | 2026-07-09 | 8 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/PROVENIENCIA-CAMPOS-LV.md` | Proveniência de campos LV — contrato completo | 2026-08-10 | 5 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/PROVENIENCIA-CAMPOS-PIL.md` | Proveniência de campos PIL — contrato inicial | 2026-08-10 | 4 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/QA-FASTPATHS-CAMPOS-ARTEFATOS.md` | QA fast paths — campos N1 e artefatos N3/N4 | 2026-07-14 | 4 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/QA-INVENTARIO-MINIMO-VALIDACAO-VISUAL.md` | QA — Inventário mínimo para validação visual válida | 2026-09-25 | 12 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/QA-N2-N4-COMPARACAO-FIDELIDADE.md` | QA — Comparação N2·N3·N4 com fidelidade real (não “parece igual”) | 2026-08-10 | 2 | marcado Status: canónico |
| `Agente-cad-PYSIDE-Restored-main/docs/QA-PERFIS-CLASSES-SA-N1-N3.md` | QA por classe — compreensão SA N1 e validação N3 | 2026-08-10 | 12 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/QA-VISAO-EVIDENCIA-CANONICA.md` | QA — Visão canónica de evidência (nível de qualidade obrigatório) | 2026-09-25 | 30 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/RAG-GROUNDTRUTH-LAJ-13PAV.md` | Fase 2 LAJ — ground truth curado, 13_PAV | 2026-07-12 | 1 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/RAG-REVOGACAO-HUMANA-SPEC.md` | RAG Revogacao Humana Spec | 2026-06-26 | 4 | curadoria: revogação/tombstone vale para decisões e regras da KB global |
| `Agente-cad-PYSIDE-Restored-main/docs/REGRA-ENTREGA-E2E-QUALIDADE-MAXIMA.md` | REGRA — Entrega ponta a ponta com qualidade máxima | 2026-08-10 | 4 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/ROBOS_GUIDE.md` | Guia dos Robos Especializados | 2026-06-25 | 3 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/ROBO_SCR_PATTERNS.md` | Padrões de Desenho dos Robos SCR — Sistema NOVA | 2026-06-25 | 4 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/SA-ANALISE-PROGRESSO-POR-ITEM.md` | Structural Analyzer — progresso por item e trilha de evidências | 2026-09-25 | 6 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/SA-ANALISE/CLASSES/FV.md` | FV — manual granular de interpretação, validação e evolução | 2026-09-29 | 9 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/SA-ANALISE/CLASSES/LAJ.md` | LAJ — manual granular de interpretação, validação e evolução | 2026-08-10 | 8 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/SA-ANALISE/CLASSES/LV.md` | LV — manual granular de interpretação, validação e evolução | 2026-09-26 | 11 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/SA-ANALISE/CLASSES/PIL.md` | PIL — manual granular de interpretação, validação e evolução | 2026-09-25 | 9 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/SA-ANALISE/CLASSES/README.md` | Manuais granulares por classe — Structural Analyzer | 2026-09-25 | 3 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/SA-ANALISE/JEV-SEGUNDA-LEITURA-OPCIONAL.md` | Jev como segunda leitura opcional do SA/N1 | 2026-09-29 | 10 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/SEMANTICA-LAJE-NOVA.md` | Semântica dos Campos — Laje NOVA (Sistema Fôrma) | 2026-06-25 | 8 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/SEMANTICA-PILAR-NOVA.md` | Semântica dos Campos — Pilar NOVA (Sistema Fôrma) | 2026-07-11 | 11 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/SEMANTICA-VIGA-NOVA.md` | Semântica dos Campos — Viga NOVA (Sistema Fôrma) | 2026-06-25 | 8 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/SPEC-VIGA-SPLIT-FV-LV.md` | SPEC — Separação da Viga em FV (Fundo) + LV (Lateral) em TODOS os níveis | 2026-06-25 | 4 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/STATUS.md` | STATUS — gerado automaticamente, NÃO editar à mão | 2026-09-12 | 16 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/docs/VISION-VALIDACAO-CAMINHOS.md` | Validação Visual (G2-V) — Caminhos explorados e veredito | 2026-08-10 | 7 | citado por ponto de entrada |
| `Agente-cad-PYSIDE-Restored-main/squads/qa-global-evidencias/data/authority_matrix.json` | authority_matrix | 2026-08-10 | 15 | citado por ponto de entrada |
| `docs/PYTHON-3.12-RUNTIME.md` | Runtime Python do CAD-ANALYZER | 2026-06-29 | 4 | citado por ponto de entrada |

## ativo (142)

| Fonte | Título | Data | Citado por | Motivo |
|---|---|---|---:|---|
| `Agente-cad-PYSIDE-Restored-main/.claude/commands/CAD/QAGlobalEvidencias-AIOS.md` | QA Global de Evidências — Arete | 2026-08-10 | 0 | tocado em 2026-08-10 / citado por 0 |
| `Agente-cad-PYSIDE-Restored-main/DEPLOYMENT.md` | Manual de Deploy e Distribuição - Estrutural Analyzer | 2026-06-25 | 2 | tocado em 2026-06-25 / citado por 2 |
| `Agente-cad-PYSIDE-Restored-main/MEMORY_SYSTEM_README.md` | 🧠 Sistema de Memória Multi-Nível AgenteCAD | 2026-06-25 | 1 | tocado em 2026-06-25 / citado por 1 |
| `Agente-cad-PYSIDE-Restored-main/docs/ARCHITECTURE.md` | Arquitetura do Sistema AgenteCAD / Estrutural Analyzer | 2026-06-25 | 5 | tocado em 2026-06-25 / citado por 5 |
| `Agente-cad-PYSIDE-Restored-main/docs/ARETE-ARQUITETURA-VALIDACAO.md` | Arete — Arquitetura de Validação: Problema Atual e Alvo | 2026-06-25 | 1 | tocado em 2026-06-25 / citado por 1 |
| `Agente-cad-PYSIDE-Restored-main/docs/ARETE-MCP-RAG-HARMONIZACAO.md` | Arete, MCP e RAG - Contrato de Harmonizacao | 2026-07-02 | 7 | tocado em 2026-07-02 / citado por 7 |
| `Agente-cad-PYSIDE-Restored-main/docs/ARETE-PLAYWRIGHT-QA-VISUAL.md` | Arete — QA visual das fichas granulares N1/N2/N3/N4 | 2026-09-25 | 7 | tocado em 2026-09-25 / citado por 7 |
| `Agente-cad-PYSIDE-Restored-main/docs/ARTIFACT_GOVERNANCE_N3_N4.md` | Governança dos artefatos N3/N4 | 2026-06-29 | 1 | tocado em 2026-06-29 / citado por 1 |
| `Agente-cad-PYSIDE-Restored-main/docs/CONTEXTUALIZACAO_VIGAS_SEGMENTOS_FUNDOS.md` | 📋 Contextualização: Lista de Vigas, Campo SEGMENTOS e Abas A/B de FUNDOS | 2026-06-25 | 2 | tocado em 2026-06-25 / citado por 2 |
| `Agente-cad-PYSIDE-Restored-main/docs/DATA_FLOW.md` | Fluxo de Dados Completo - AgenteCAD | 2026-06-25 | 3 | tocado em 2026-06-25 / citado por 3 |
| `Agente-cad-PYSIDE-Restored-main/docs/DATA_POPULATION_CHECKLIST.md` | Checklist de Populacao de Dados | 2026-06-25 | 1 | tocado em 2026-06-25 / citado por 1 |
| `Agente-cad-PYSIDE-Restored-main/docs/DESIGN-SYSTEM-PYSIDE.md` | Design System -- TSF PROJETOS (PySide6) | 2026-06-25 | 2 | tocado em 2026-06-25 / citado por 2 |
| `Agente-cad-PYSIDE-Restored-main/docs/DEVELOPER_ONBOARDING.md` | Guia de Onboarding para Desenvolvedores | 2026-06-25 | 3 | tocado em 2026-06-25 / citado por 3 |
| `Agente-cad-PYSIDE-Restored-main/docs/ENCICLOPEDIA-SCHEMA.md` | Enciclopedia de Classes - Contrato das 8 Dimensoes | 2026-06-26 | 2 | curadoria: 8 dimensões por classe viram o eixo 'classe' da KB global |
| `Agente-cad-PYSIDE-Restored-main/docs/ESTADO-MOTOR-LV-N4-2026-09-10.md` | Estado do motor LV N4 — 2026-09-10/11 | 2026-09-12 | 0 | tocado em 2026-09-12 / citado por 0 |
| `Agente-cad-PYSIDE-Restored-main/docs/ETAPA-1-RELATORIO.md` | ETAPA 1 - Fichas & Botoes | 2026-06-25 | 1 | tocado em 2026-06-25 / citado por 1 |
| `Agente-cad-PYSIDE-Restored-main/docs/GEOMETRY-INDEX-N2-N3-N4.md` | GeometryIndex — camada estruturada N2 · N3 · N4 | 2026-08-10 | 2 | tocado em 2026-08-10 / citado por 2 |
| `Agente-cad-PYSIDE-Restored-main/docs/HANDOFF-ARCHITECT-PORTAL.md` | HANDOFF ARCHITECT — Backend do Portal Soberano (Gates P1–P3) | 2026-07-05 | 2 | tocado em 2026-07-05 / citado por 2 |
| `Agente-cad-PYSIDE-Restored-main/docs/HANDOFF-DATAENGINEER-PORTAL.md` | HANDOFF — Data Engineer: Schema de Dados do Portal | 2026-07-05 | 1 | tocado em 2026-07-05 / citado por 1 |
| `Agente-cad-PYSIDE-Restored-main/docs/HANDOFF-DEVOPS-PORTAL.md` | HANDOFF-DEVOPS — Deploy & Operação do Portal na Workstation | 2026-07-05 | 2 | tocado em 2026-07-05 / citado por 2 |
| `Agente-cad-PYSIDE-Restored-main/docs/HANDOFF-PIL-LV-CROSSCLASS-20260711.md` | HANDOFF PIL ↔ LV — cross-class (2026-07-11) | 2026-07-13 | 0 | tocado em 2026-07-13 / citado por 0 |
| `Agente-cad-PYSIDE-Restored-main/docs/HANDOFF-PRODUCAO-EXECUTOR.md` | HANDOFF — Executor de Stories (Produção & Qualidade) | 2026-07-05 | 9 | tocado em 2026-07-05 / citado por 9 |
| `Agente-cad-PYSIDE-Restored-main/docs/HANDOFF-QA-PORTAL.md` | HANDOFF-QA — Estratégia de Testes do Portal Soberano | 2026-08-10 | 1 | tocado em 2026-08-10 / citado por 1 |
| `Agente-cad-PYSIDE-Restored-main/docs/HANDOFF-UX-PORTAL.md` | HANDOFF-UX — Portal Web da Equipe (fluxo enxuto de 6 etapas) | 2026-07-05 | 1 | tocado em 2026-07-05 / citado por 1 |
| `Agente-cad-PYSIDE-Restored-main/docs/INSIGHTS-QA-PIL-ABCD-13PAV-ATENCAO-HUMANA.md` | Insights QA — Pilares ABCD 13_PAV (atenções humanas → L1) | 2026-08-18 | 0 | tocado em 2026-08-18 / citado por 0 |
| `Agente-cad-PYSIDE-Restored-main/docs/INSIGHTS-QA-PIL-ABCD-PACK10-VALIDADO.md` | Insights QA — Pilares ABCD (pack P1–P10 · Obra_TREINO_1 / 13_PAV) | 2026-08-10 | 0 | tocado em 2026-08-10 / citado por 0 |
| `Agente-cad-PYSIDE-Restored-main/docs/LOOPING-AGENTICO-INTERPRETACAO-PILARES-ABCD.md` | Looping agêntico — interpretação de pilares ABCD | 2026-08-18 | 2 | tocado em 2026-08-18 / citado por 2 |
| `Agente-cad-PYSIDE-Restored-main/docs/LV-ISOLAMENTO-MODULAR.md` | LV — isolamento modular e limites de edição | 2026-07-14 | 0 | tocado em 2026-07-14 / citado por 0 |
| `Agente-cad-PYSIDE-Restored-main/docs/MASTERPLAN-AGENTE-QA-EVIDENCIAS.md` | Anexo técnico LAJ — Agente QA Global de Evidências (Areté) | 2026-07-13 | 1 | tocado em 2026-07-13 / citado por 1 |
| `Agente-cad-PYSIDE-Restored-main/docs/MASTERPLAN-AGENTE-QA-GLOBAL.md` | Masterplan — Agente QA Global de Evidências (Arete) | 2026-08-10 | 11 | tocado em 2026-08-10 / citado por 11 |
| `Agente-cad-PYSIDE-Restored-main/docs/MASTERPLAN-ARETE-FUNDO-VIGA.md` | MASTERPLAN — Arete FUNDO DE VIGA (FV): N2→N4 → N2↔N1 → N1→N3 | 2026-07-09 | 3 | tocado em 2026-07-09 / citado por 3 |
| `Agente-cad-PYSIDE-Restored-main/docs/MASTERPLAN-ARETE-LAJE.md` | MASTERPLAN — Arete LAJE: N2→N4 → N2↔N1 → N1→N3 | 2026-07-09 | 3 | tocado em 2026-07-09 / citado por 3 |
| `Agente-cad-PYSIDE-Restored-main/docs/MASTERPLAN-ARETE-LATERAL-VIGA.md` | MASTERPLAN — Arete LATERAL DE VIGA (LV): N2→N4 → N2↔N1 → N1→N3 | 2026-07-09 | 4 | tocado em 2026-07-09 / citado por 4 |
| `Agente-cad-PYSIDE-Restored-main/docs/MASTERPLAN-ARETE-PILAR.md` | MASTERPLAN ARETE - PILAR | 2026-07-09 | 2 | tocado em 2026-07-09 / citado por 2 |
| `Agente-cad-PYSIDE-Restored-main/docs/MASTERPLAN-CAD-ANALYZER.md` | MASTERPLAN CAD-ANALYZER v1.0 | 2026-06-25 | 6 | tocado em 2026-06-25 / citado por 6 |
| `Agente-cad-PYSIDE-Restored-main/docs/MASTERPLAN-CAD-UI.md` | MASTERPLAN-CAD-UI — Vision-Estrutural AI | 2026-06-25 | 2 | tocado em 2026-06-25 / citado por 2 |
| `Agente-cad-PYSIDE-Restored-main/docs/MASTERPLAN-FICHAS-F1-F9-HARMONIZACAO.md` | MASTERPLAN — Arquitetura de Fichas F1–F9, Harmonização & Acoplamento Semântico | 2026-06-25 | 8 | tocado em 2026-06-25 / citado por 8 |
| `Agente-cad-PYSIDE-Restored-main/docs/MASTERPLAN-INTERPRETACAO-VALIDACAO.md` | MASTERPLAN — Validação Campo a Campo da Interpretação DXF | 2026-06-25 | 2 | tocado em 2026-06-25 / citado por 2 |
| `Agente-cad-PYSIDE-Restored-main/docs/MASTERPLAN-MINIRAG-QA-N1.md` | Masterplan — Mini-RAG de sessão + índice CAD para o QA Global N1 | 2026-08-10 | 3 | tocado em 2026-08-10 / citado por 3 |
| `Agente-cad-PYSIDE-Restored-main/docs/MASTERPLAN-PORTAL-FUNDOS-VIGA-HIFI.md` | MASTERPLAN — Fundos de Viga HI-FI no Portal Web | 2026-09-12 | 0 | tocado em 2026-09-12 / citado por 0 |
| `Agente-cad-PYSIDE-Restored-main/docs/MASTERPLAN-RECORTE-LAJE-APRENDIZAGEM.md` | MASTERPLAN - Recorte LAJ: Aprendizagem por Aprovacoes Humanas | 2026-06-25 | 1 | tocado em 2026-06-25 / citado por 1 |
| `Agente-cad-PYSIDE-Restored-main/docs/PADRAO-SVG-ELEMENTO-CLICAVEL-DEPURACAO.md` | Padrão — SVG por elemento clicável para depuração N2×N4 | 2026-09-12 | 0 | tocado em 2026-09-12 / citado por 0 |
| `Agente-cad-PYSIDE-Restored-main/docs/PADRAO-VALIDACAO-HTML-PIL-N4.md` | Padrão de validação humana — PIL N4 | 2026-08-10 | 0 | tocado em 2026-08-10 / citado por 0 |
| `Agente-cad-PYSIDE-Restored-main/docs/POSTMORTEM-PIL-P35-MICROCICLO-20260713.md` | Pós-mortem — PIL P35 / vínculo V308 em A-B — 2026-07-13 | 2026-07-14 | 2 | tocado em 2026-07-14 / citado por 2 |
| `Agente-cad-PYSIDE-Restored-main/docs/PROMPT-LOOPING-DESTAQUE-AGENTICO-FV-PARA-PIL.md` | Prompt — Looping de interpretação + anotação + desenho agêntico | 2026-08-10 | 1 | tocado em 2026-08-10 / citado por 1 |
| `Agente-cad-PYSIDE-Restored-main/docs/PROMPTS-QA-CLASSES-DUAL-ZOOM-FASTPATH.md` | Prompts QA por classe — N1 em dois SVGs e microciclo rápido | 2026-07-14 | 0 | tocado em 2026-07-14 / citado por 0 |
| `Agente-cad-PYSIDE-Restored-main/docs/PROPOSTA-MINIRAG-SESSAO-N1.md` | Proposta — Mini-RAG dinâmico de sessão para validação N1 SA | 2026-08-10 | 1 | tocado em 2026-08-10 / citado por 1 |
| `Agente-cad-PYSIDE-Restored-main/docs/PROPOSTA-NIVEL-LAJE-POR-EVIDENCIAS.md` | Proposta — nível de laje por soma de evidências | 2026-09-26 | 2 | tocado em 2026-09-26 / citado por 2 |
| `Agente-cad-PYSIDE-Restored-main/docs/PROVENIENCIA-CAMPOS.md` | Proveniência de Campos — Arete | 2026-07-05 | 3 | tocado em 2026-07-05 / citado por 3 |
| `Agente-cad-PYSIDE-Restored-main/docs/QA-CAPACIDADE-POR-CLASSE.md` | Capacidade do agente por classe (paridade PIL / LAJ / FV / LV) | 2026-08-10 | 3 | tocado em 2026-08-10 / citado por 3 |
| `Agente-cad-PYSIDE-Restored-main/docs/QA-CICLO-EFICIENCIA-E-AUTORIDADE.md` | QA Global — Ciclo treino×validação, eficiência e autoridade (permitido vs proibido) | 2026-08-10 | 3 | tocado em 2026-08-10 / citado por 3 |
| `Agente-cad-PYSIDE-Restored-main/docs/QA-CLI-DATASET-LOGGING.md` | Logs e dataset candidato do QA por CLIs | 2026-08-18 | 0 | tocado em 2026-08-18 / citado por 0 |
| `Agente-cad-PYSIDE-Restored-main/docs/QA-EVIDENCIAS-LAJ-13PAV-20260711.md` | QA de Evidências — LAJ 13_PAV — 2026-07-11 | 2026-07-11 | 1 | tocado em 2026-07-11 / citado por 1 |
| `Agente-cad-PYSIDE-Restored-main/docs/QA-QUADROS-ESTADO-POR-CLASSE.md` | QA — Quadros de Estado por Classe e Pavimento | 2026-08-10 | 4 | tocado em 2026-08-10 / citado por 4 |
| `Agente-cad-PYSIDE-Restored-main/docs/QUALITY-GATE-MASTERPLANS-FICHAS-LOOP.md` | QUALITY GATE — Masterplans Fichas F1-F9 & Loop de Treino | 2026-06-25 | 3 | tocado em 2026-06-25 / citado por 3 |
| `Agente-cad-PYSIDE-Restored-main/docs/QUESTIONARIO-LV-SA-2026-09-25.md` | Questionario ao dono — interpretacao SA das Laterais de Viga (2026-09-25) | 2026-09-25 | 3 | tocado em 2026-09-25 / citado por 3 |
| `Agente-cad-PYSIDE-Restored-main/docs/README.md` | Documentação — CAD-ANALYZER / Estrutural Analyzer | 2026-09-25 | 2 | curadoria: índice de 2026-07-03; a entrada vigente é docs/CONHECIMENTO/MAPA-DO-CONHECIMENTO.md |
| `Agente-cad-PYSIDE-Restored-main/docs/REVERSE_ENGINEERING.md` | Sistema de Engenharia Reversa - AgenteCAD | 2026-06-25 | 2 | tocado em 2026-06-25 / citado por 2 |
| `Agente-cad-PYSIDE-Restored-main/docs/RODADA-LV-13PAV-REVISAO-GRANULAR.md` | Rodada de revisão granular — LV 13_PAV | 2026-09-12 | 0 | tocado em 2026-09-12 / citado por 0 |
| `Agente-cad-PYSIDE-Restored-main/docs/SCHEMA-FICHA-GRANULAR.md` | SCHEMA-FICHA-GRANULAR | 2026-06-25 | 9 | tocado em 2026-06-25 / citado por 9 |
| `Agente-cad-PYSIDE-Restored-main/docs/SPEC-GERADORES-DXF.md` | Especificação Completa dos Geradores DXF — STOG Quality | 2026-06-25 | 2 | tocado em 2026-06-25 / citado por 2 |
| `Agente-cad-PYSIDE-Restored-main/docs/VECTOR_SCHEMA.md` | Schema JSON dos Vetores Semanticos | 2026-06-25 | 7 | tocado em 2026-06-25 / citado por 7 |
| `Agente-cad-PYSIDE-Restored-main/docs/design-system-gaps.md` | Design System Gaps — Vision-Estrutural AI | 2026-06-25 | 2 | tocado em 2026-06-25 / citado por 2 |
| `Agente-cad-PYSIDE-Restored-main/docs/interviews/LAJES.md` | Entrevista: Sistema de Lajes | 2026-06-25 | 1 | tocado em 2026-06-25 / citado por 1 |
| `Agente-cad-PYSIDE-Restored-main/docs/interviews/PILARES.md` | Entrevista: Sistema de Pilares | 2026-06-25 | 1 | tocado em 2026-06-25 / citado por 1 |
| `Agente-cad-PYSIDE-Restored-main/docs/interviews/VIGAS.md` | Entrevista: Sistema de Vigas | 2026-06-25 | 1 | tocado em 2026-06-25 / citado por 1 |
| `Agente-cad-PYSIDE-Restored-main/docs/planning/app-consulta-publica/architecture.md` | Architecture — App de Consulta Pública CAD-ANALYZER (Consulta de Fôrmas por ID) | 2026-07-12 | 16 | tocado em 2026-07-12 / citado por 16 |
| `Agente-cad-PYSIDE-Restored-main/docs/planning/app-consulta-publica/backlog-validation.md` | Backlog Validation — App de Consulta Pública CAD-ANALYZER | 2026-07-12 | 1 | tocado em 2026-07-12 / citado por 1 |
| `Agente-cad-PYSIDE-Restored-main/docs/planning/app-consulta-publica/front-end-spec.md` | Front-End Spec — App de Consulta Pública CAD-ANALYZER (Consulta de Fôrmas por Código) | 2026-07-12 | 9 | tocado em 2026-07-12 / citado por 9 |
| `Agente-cad-PYSIDE-Restored-main/docs/planning/app-consulta-publica/masterplan.md` | Masterplan — App de Consulta Pública CAD-ANALYZER | 2026-07-12 | 0 | tocado em 2026-07-12 / citado por 0 |
| `Agente-cad-PYSIDE-Restored-main/docs/planning/app-consulta-publica/prd.md` | PRD — App de Consulta Pública CAD-ANALYZER (Consulta de Fôrmas por ID) | 2026-07-12 | 20 | tocado em 2026-07-12 / citado por 20 |
| `Agente-cad-PYSIDE-Restored-main/docs/planning/app-consulta-publica/project-brief.md` | Project Brief: App de Consulta Pública CAD-ANALYZER (Consulta de Fôrmas por ID) | 2026-07-12 | 6 | tocado em 2026-07-12 / citado por 6 |
| `Agente-cad-PYSIDE-Restored-main/docs/preprocessamento/BASELINE.md` | Baseline do pré-processamento | 2026-09-22 | 2 | tocado em 2026-09-22 / citado por 2 |
| `Agente-cad-PYSIDE-Restored-main/docs/preprocessamento/CONTRATO-CONSUMO-SA.md` | Contrato de consumo assistido pelo SA | 2026-09-23 | 2 | tocado em 2026-09-23 / citado por 2 |
| `Agente-cad-PYSIDE-Restored-main/docs/preprocessamento/STATUS-IMPLEMENTACAO-2026-09-22.md` | Estado da implementação — pré-processamento por pavimento/torre | 2026-09-22 | 1 | tocado em 2026-09-22 / citado por 1 |
| `Agente-cad-PYSIDE-Restored-main/docs/preprocessamento/STATUS-IMPLEMENTACAO-2026-09-23.md` | Pré-processamento — checkpoint de 2026-09-23 | 2026-09-24 | 0 | tocado em 2026-09-24 / citado por 0 |
| `Agente-cad-PYSIDE-Restored-main/docs/qa/app-consulta-publica-security-gate-report.md` | Relatório de Gate de Segurança — App de Consulta Pública | 2026-07-12 | 2 | tocado em 2026-07-12 / citado por 2 |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/STORY-DOC-ARETE-G0-G6-RECONCILIACAO.md` | STORY-DOC - Reconciliacao Arete G0-G6, MCP e RAG | 2026-07-02 | 0 | tocado em 2026-07-02 / citado por 0 |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/STORY-DOC-ARETE-MCP-RAG-HARMONIZACAO.md` | STORY-DOC - Harmonizacao Arete, MCP e RAG | 2026-07-02 | 0 | tocado em 2026-07-02 / citado por 0 |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/STORY-EXEC-01-FV-SARR5CM.md` | STORY-EXEC-01 — FV 13_PAV: corrigir causa `SARR_5CM` (6 itens FAIL) | 2026-07-03 | 2 | tocado em 2026-07-03 / citado por 2 |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/STORY-EXEC-02-FLAG-SECAO.md` | STORY-EXEC-02 — Flag `--secao` no headless (gerar só uma classe) | 2026-07-03 | 1 | tocado em 2026-07-03 / citado por 1 |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/STORY-EXEC-03-DIAG-LAJ-HEADLESS.md` | STORY-EXEC-03 — Integrar diagnósticos automáticos LAJ/LV/PIL ao headless (como FV já está) | 2026-07-03 | 1 | tocado em 2026-07-03 / citado por 1 |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/STORY-EXEC-04-LAJ-LINHAS-HORIZONTAIS.md` | STORY-EXEC-04 — LAJ 13_PAV: round-trip de `linhas_horizontais` quebrado (23 itens FAIL) | 2026-07-03 | 2 | tocado em 2026-07-03 / citado por 2 |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/STORY-EXEC-05-RECONCILIACAO-CONCORDANCIA.md` | STORY-EXEC-05 — Reconciliar diagnósticos auto de PIL/FV/LV + rollup de concordância | 2026-07-03 | 2 | tocado em 2026-07-03 / citado por 2 |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/STORY-PRE-1.0-PREPROCESSAMENTO-PAVIMENTO-TORRES.md` | STORY PRE-1.0 — Pré-processamento por pavimento e torre | 2026-09-22 | 0 | tocado em 2026-09-22 / citado por 0 |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/STORY-QAEV-1.0-LAJ-AUDITOR-EVIDENCIAS.md` | STORY QAEV-1.0 — Auditor de Evidências para LAJ | 2026-07-12 | 0 | tocado em 2026-07-12 / citado por 0 |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/active/EPIC-CAD-10.md` | EPIC-CAD-10: Ficha Integrada de Interpretacao | 2026-06-25 | 1 | tocado em 2026-06-25 / citado por 1 |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/active/app-consulta-publica/README.md` | Roadmap de Stories — App de Consulta Pública CAD-ANALYZER | 2026-07-12 | 1 | tocado em 2026-07-12 / citado por 1 |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/active/app-consulta-publica/STORY-01-schema-publisher.md` | Story 1.1: Schema `public_consulta.db` + Publisher (mint/upsert/revoke de códigos opacos) | 2026-07-12 | 1 | tocado em 2026-07-12 / citado por 1 |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/active/app-consulta-publica/STORY-02-api-skeleton.md` | Story 1.2: API pública FastAPI — skeleton, porta 21390, conexão read-only | 2026-07-12 | 1 | tocado em 2026-07-12 / citado por 1 |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/active/app-consulta-publica/STORY-03-resolve-endpoint.md` | Story 1.3: Endpoint `GET /api/v1/resolve/{code}` | 2026-07-12 | 1 | tocado em 2026-07-12 / citado por 1 |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/active/app-consulta-publica/STORY-04-security-hardening.md` | Story 1.4: Rate Limiting + CORS + Detecção de Enumeração | 2026-07-12 | 1 | tocado em 2026-07-12 / citado por 1 |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/active/app-consulta-publica/STORY-05-ficha-reader-endpoint.md` | Story 2.1: `ficha_reader` compartilhado + Endpoint `GET /api/v1/ficha/{code}` | 2026-07-12 | 1 | tocado em 2026-07-12 / citado por 1 |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/active/app-consulta-publica/STORY-06-svg-endpoint.md` | Story 2.2: Endpoint `GET /api/v1/ficha/{code}/svg/{nivel}` | 2026-07-12 | 1 | tocado em 2026-07-12 / citado por 1 |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/active/app-consulta-publica/STORY-07-obra-index-endpoint.md` | Story 2.3: Endpoint `GET /api/v1/obra/{code}` | 2026-07-12 | 1 | tocado em 2026-07-12 / citado por 1 |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/active/app-consulta-publica/STORY-08-frontend-pwa-scaffold-busca.md` | Story 1.5 / 2.4: Frontend — Scaffold PWA (Next.js 14) + Tela de Busca | 2026-07-12 | 1 | tocado em 2026-07-12 / citado por 1 |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/active/app-consulta-publica/STORY-09-design-tokens.md` | Story 4.1: Frontend — Design System / Tokens (Tailwind, Light/Dark/Sol-Forte, WCAG AA) | 2026-07-12 | 1 | tocado em 2026-07-12 / citado por 1 |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/active/app-consulta-publica/STORY-10-frontend-ficha-obra-index.md` | Story 2.4: Frontend — Tela Ficha do Item + Índice de Obra | 2026-07-12 | 1 | tocado em 2026-07-12 / citado por 1 |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/active/app-consulta-publica/STORY-11-svg-viewer-fullscreen.md` | Story 2.5: Frontend — Visualizador SVG Tela Cheia (Zoom/Pan) | 2026-07-12 | 1 | tocado em 2026-07-12 / citado por 1 |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/active/app-consulta-publica/STORY-12-paineis-lv-endpoint.md` | Story 3.1: Endpoint `GET /api/v1/ficha/{code}/paineis-lv` | 2026-07-12 | 1 | tocado em 2026-07-12 / citado por 1 |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/active/app-consulta-publica/STORY-13-frontend-paineis-lv.md` | Story 3.2: Frontend — Aba Painéis LV | 2026-07-12 | 1 | tocado em 2026-07-12 / citado por 1 |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/active/app-consulta-publica/STORY-14-pwa-offline-service-worker.md` | Story 4.2: Frontend — PWA Installability + Service Worker + Cache Offline + Status | 2026-07-12 | 1 | tocado em 2026-07-12 / citado por 1 |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/active/app-consulta-publica/STORY-15-security-test-suite-gate.md` | Story (Gate): Suíte de Testes de Segurança — Gate Obrigatório de Release | 2026-07-12 | 1 | tocado em 2026-07-12 / citado por 1 |
| `Agente-cad-PYSIDE-Restored-main/resumo_perda_codigo.md` | Resumo da Perda de Código - 09/07/2026 | 2026-07-09 | 0 | tocado em 2026-07-09 / citado por 0 |
| `Agente-cad-PYSIDE-Restored-main/squads/qa-global-evidencias/CHANGELOG.md` | Changelog | 2026-08-10 | 0 | tocado em 2026-08-10 / citado por 0 |
| `Agente-cad-PYSIDE-Restored-main/squads/qa-global-evidencias/README.md` | QA Global de Evidências | 2026-08-10 | 0 | tocado em 2026-08-10 / citado por 0 |
| `Agente-cad-PYSIDE-Restored-main/squads/qa-global-evidencias/agents/aegis.md` | Aegis — Orquestrador QA de Evidências | 2026-08-10 | 4 | tocado em 2026-08-10 / citado por 4 |
| `Agente-cad-PYSIDE-Restored-main/squads/qa-global-evidencias/checklists/evidence-gate-checklist.md` | Checklist do gate de evidência | 2026-08-10 | 0 | tocado em 2026-08-10 / citado por 0 |
| `Agente-cad-PYSIDE-Restored-main/squads/qa-global-evidencias/checklists/operational-anti-superselo-checklist.md` | Checklist operacional anti-super-selo (Arete / QA Global) | 2026-08-10 | 2 | tocado em 2026-08-10 / citado por 2 |
| `Agente-cad-PYSIDE-Restored-main/squads/qa-global-evidencias/checklists/permitido-vs-proibido-ciclo.md` | Permitido vs proibido — ciclo treino × validação × juiz 🟠 | 2026-08-10 | 1 | tocado em 2026-08-10 / citado por 1 |
| `Agente-cad-PYSIDE-Restored-main/squads/qa-global-evidencias/contracts/qa-rag-looping.md` | Contrato QA ↔ Arete ↔ RAG | 2026-07-13 | 0 | tocado em 2026-07-13 / citado por 0 |
| `Agente-cad-PYSIDE-Restored-main/squads/qa-global-evidencias/data/audit-score.json` | audit-score | 2026-08-10 | 0 | tocado em 2026-08-10 / citado por 0 |
| `Agente-cad-PYSIDE-Restored-main/squads/qa-global-evidencias/data/class_capability_matrix.json` | class_capability_matrix | 2026-08-10 | 3 | tocado em 2026-08-10 / citado por 3 |
| `Agente-cad-PYSIDE-Restored-main/squads/qa-global-evidencias/data/fv_lv_adapter_backlog.md` | Backlog de adaptadores FV / LV | 2026-08-10 | 0 | tocado em 2026-08-10 / citado por 0 |
| `Agente-cad-PYSIDE-Restored-main/squads/qa-global-evidencias/data/team-manifest.md` | Team manifest | 2026-07-13 | 0 | tocado em 2026-07-13 / citado por 0 |
| `Agente-cad-PYSIDE-Restored-main/squads/qa-global-evidencias/docs/INTEGRACAO-APP-AGENTE.md` | Integração app ↔ agente QA Global | 2026-08-10 | 2 | tocado em 2026-08-10 / citado por 2 |
| `Agente-cad-PYSIDE-Restored-main/squads/qa-global-evidencias/tasks/curate-rag.md` | Preparar candidato RAG | 2026-08-10 | 0 | tocado em 2026-08-10 / citado por 0 |
| `Agente-cad-PYSIDE-Restored-main/squads/qa-global-evidencias/tasks/index-evidence.md` | Indexar evidências | 2026-08-10 | 0 | tocado em 2026-08-10 / citado por 0 |
| `Agente-cad-PYSIDE-Restored-main/squads/qa-global-evidencias/tasks/parity-contract.md` | Paridade e smoke de artefatos | 2026-08-10 | 0 | tocado em 2026-08-10 / citado por 0 |
| `Agente-cad-PYSIDE-Restored-main/squads/qa-global-evidencias/tasks/plan-remediation.md` | Planejar remediação | 2026-08-10 | 0 | tocado em 2026-08-10 / citado por 0 |
| `Agente-cad-PYSIDE-Restored-main/squads/qa-global-evidencias/tasks/regression-gate.md` | Executar regressão | 2026-08-10 | 0 | tocado em 2026-08-10 / citado por 0 |
| `Agente-cad-PYSIDE-Restored-main/squads/qa-global-evidencias/tasks/resolve-scope.md` | Resolver escopo | 2026-08-10 | 0 | tocado em 2026-08-10 / citado por 0 |
| `Agente-cad-PYSIDE-Restored-main/squads/qa-global-evidencias/tasks/review-artifact.md` | Revisar artefato N3/N4 | 2026-08-10 | 0 | tocado em 2026-08-10 / citado por 0 |
| `Agente-cad-PYSIDE-Restored-main/squads/qa-global-evidencias/tasks/review-n1.md` | Revisar N1 | 2026-08-10 | 0 | tocado em 2026-08-10 / citado por 0 |
| `Agente-cad-PYSIDE-Restored-main/squads/qa-global-evidencias/tasks/structure-question.md` | Estruturar dúvida humana | 2026-08-10 | 0 | tocado em 2026-08-10 / citado por 0 |
| `Agente-cad-PYSIDE-Restored-main/squads/qa-global-evidencias/tasks/visual-gate.md` | Executar gate visual | 2026-08-10 | 0 | tocado em 2026-08-10 / citado por 0 |
| `Agente-cad-PYSIDE-Restored-main/squads/qa-global-evidencias/templates/dossie-template.md` | Dossiê QA — {run_id} | 2026-08-10 | 0 | tocado em 2026-08-10 / citado por 0 |
| `Agente-cad-PYSIDE-Restored-main/squads/qa-global-evidencias/templates/structured-question-template.md` | Dúvida estruturada | 2026-07-13 | 2 | tocado em 2026-07-13 / citado por 2 |
| `C:/Users/Thierry/.claude/skills/opus-5-5-converter/SKILL.md` | Opus 5.5 Converter | 2026-09-25 | 0 | tocado em 2026-09-25 / citado por 0 |
| `C:/Users/Thierry/.claude/skills/opus-5-5-converter/references/canonical-blocks.md` | Canonical blocks | 2026-09-25 | 1 | tocado em 2026-09-25 / citado por 1 |
| `C:/Users/Thierry/.claude/skills/qa-global-evidencias/SKILL.md` | QA Global de Evidências | 2026-07-16 | 0 | tocado em 2026-07-16 / citado por 0 |
| `C:/Users/Thierry/.claude/skills/qa-global-evidencias/references/authority-and-provenance.md` | Autoridade e proveniência | 2026-07-16 | 1 | tocado em 2026-07-16 / citado por 1 |
| `C:/Users/Thierry/.claude/skills/qa-global-evidencias/references/rag-governance.md` | Governança RAG | 2026-07-13 | 2 | tocado em 2026-07-13 / citado por 2 |
| `C:/Users/Thierry/.claude/skills/qa-global-evidencias/references/routing.md` | Roteamento canônico | 2026-07-13 | 1 | tocado em 2026-07-13 / citado por 1 |
| `C:/Users/Thierry/.claude/skills/qa-global-evidencias/references/structured-questions.md` | Pergunta humana estruturada | 2026-07-13 | 1 | tocado em 2026-07-13 / citado por 1 |
| `MASTERPLAN-GERENCIAR-PROJETOS-v5.0.md` | MASTERPLAN — CAD Analyzer v5.0 | 2026-06-11 | 1 | tocado em 2026-06-11 / citado por 1 |
| `MASTERPLAN-SEMANTICO-v1.0.md` | MASTERPLAN SEMÂNTICO — Vision-Estrutural AI | 2026-06-11 | 1 | tocado em 2026-06-11 / citado por 1 |
| `PROMPT-HANDOFF-2026-07-20-detailcard.md` | Handoff — performance da ficha de detalhe (SA/Pilares) + vínculo de texto quebrado | 2026-08-10 | 0 | tocado em 2026-08-10 / citado por 0 |
| `docs/CLI_REFERENCE.md` | CLI Reference - CAD-ANALYZER v3.0 | 2026-03-08 | 3 | tocado em 2026-03-08 / citado por 3 |
| `docs/GETTING_STARTED.md` | Getting Started - CAD-ANALYZER v3.0 | 2026-06-29 | 3 | tocado em 2026-06-29 / citado por 3 |
| `docs/HANDOFF-B-KNOWLEDGE-EXTRACTION.md` | HANDOFF-B: Conhecimento Extraído dos PDFs | 2026-03-18 | 2 | curadoria: conhecimento de negócio (PI/NSC |
| `docs/MCP-ACTIVE-LEARNING-SPEC.md` | MCP Active Learning - Contrato Seguro | 2026-07-02 | 5 | tocado em 2026-07-02 / citado por 5 |

## historico (56)

| Fonte | Título | Data | Citado por | Motivo |
|---|---|---|---:|---|
| `ANALISE-ESTRATEGICA-E2E-NOVA-OBRA.md` | Analise Estrategica E2E — Pipeline STOG CAD para Nova Obra | 2026-06-11 | 0 | curadoria: análise E2E de nova obra (jun/26); útil quando a Fase B/C chegar |
| `Agente-cad-PYSIDE-Restored-main/PROMPTPESSOAL.MD` | PROMPTPESSOAL | 2026-06-25 | 0 | curadoria: brief original do produto (origem |
| `Agente-cad-PYSIDE-Restored-main/REFACTORACAO_PYSYDE.MD` | Plano de Refatoração: Migração Tkinter para PySide6 (Robô Pilares) | 2026-06-25 | 0 | curadoria: migração Tkinter→PySide concluída |
| `Agente-cad-PYSIDE-Restored-main/docs/ANALISE-BASELINE-LV-VISAO-CORTE-10-VIGAS.md` | Baseline LV - Visao Corte N2 x N4 | 2026-06-25 | 0 | curadoria: baseline de jun/26 |
| `Agente-cad-PYSIDE-Restored-main/docs/CAD-10-VALIDATION-REPORT.md` | CAD-10 Validation Report -- 2026-05-19 | 2026-06-25 | 1 | curadoria: relatório de maio |
| `Agente-cad-PYSIDE-Restored-main/docs/HISTORICO-ANALISE-LV/ANALYSIS_REPORT.md` | Fragment Analysis Report: combined DXF v35 -> v37 | 2026-09-12 | 1 | pasta de histórico / story concluída |
| `Agente-cad-PYSIDE-Restored-main/docs/HISTORICO-ANALISE-LV/CONHECIMENTO_LV_STOG.md` | Conhecimento Extraído: Laterais de Vigas STOG | 2026-09-12 | 1 | pasta de histórico / story concluída |
| `Agente-cad-PYSIDE-Restored-main/docs/HISTORICO-ANALISE-LV/README.md` | Histórico — ANÁLISE LV (março/2026) | 2026-09-12 | 0 | pasta de histórico / story concluída |
| `Agente-cad-PYSIDE-Restored-main/docs/HISTORICO-ANALISE-LV/STOG-LV-PATCH-DESIGN.md` | STOG LV DXF Reconstruction - Patch Design Document | 2026-09-12 | 1 | pasta de histórico / story concluída |
| `Agente-cad-PYSIDE-Restored-main/docs/LOOPING-EVOLUCAO-N2-VISAO-FICHA.md` | LOOPING-EVOLUCAO-N2 — Visão × Ficha Motor × Iteração Humana | 2026-08-10 | 4 | curadoria: superseded pelo ARETE-LOOP-PROCEDIMENTO-GERAL (docs/README.md) |
| `Agente-cad-PYSIDE-Restored-main/docs/MASTERPLAN-LOOP-TREINO-MOTOR.md` | MASTERPLAN — Loop de Treino do Motor (Análise Geral → Gabarito Eng. Reversa) | 2026-07-02 | 12 | curadoria: superseded na execução pelo ARETE-LOOP-PROCEDIMENTO-GERAL; infra de dados citada continua válida |
| `Agente-cad-PYSIDE-Restored-main/docs/MASTER_PLAN.md` | MASTER PLAN - AgenteCAD Sistema Operacional Cognitivo | 2026-06-25 | 4 | curadoria: visão ampla anterior (Antigravity); diverge do enquadramento atual |
| `Agente-cad-PYSIDE-Restored-main/docs/MASTER_PLAN_V2.md` | MASTER PLAN V2 - Sistema Operacional Cognitivo AgenteCAD | 2026-06-25 | 2 | curadoria: idem MASTER_PLAN |
| `Agente-cad-PYSIDE-Restored-main/docs/OCR_DXF_ECOSYSTEM_ANALYSIS.md` | Análise do Ecossistema OCR/DXF vs. Nosso Pipeline | 2026-06-25 | 0 | curadoria: pesquisa de ferramentas de mai/26 |
| `Agente-cad-PYSIDE-Restored-main/docs/PROMPT-ETAPA-1-CODEX.md` | PROMPT — ETAPA 1 (Fichas & Botões) para Codex executar | 2026-06-25 | 0 | curadoria: prompt executado em jun/26 |
| `Agente-cad-PYSIDE-Restored-main/docs/PROMPT-ETAPA-2-LAJE-CODEX.md` | PROMPT-ETAPA-2-LAJE-CODEX | 2026-06-25 | 0 | curadoria: prompt executado em jun/26 |
| `Agente-cad-PYSIDE-Restored-main/docs/PROMPT-VIGA-SPLIT-FV-LV-CODEX.md` | PROMPT — Refactor "Viga Split FV/LV em todos os níveis" para Codex | 2026-06-25 | 0 | curadoria: prompt executado em jun/26 |
| `Agente-cad-PYSIDE-Restored-main/docs/SA-ANALISE/HISTORICO/FV.md` | Diário SA — FV | 2026-08-10 | 2 | pasta de histórico / story concluída |
| `Agente-cad-PYSIDE-Restored-main/docs/SA-ANALISE/HISTORICO/LAJ.md` | Diário SA — LAJ (Histórico de Progresso e Evolução) | 2026-08-10 | 1 | pasta de histórico / story concluída |
| `Agente-cad-PYSIDE-Restored-main/docs/SA-ANALISE/HISTORICO/LV.md` | Diário SA — LV | 2026-08-10 | 1 | pasta de histórico / story concluída |
| `Agente-cad-PYSIDE-Restored-main/docs/SA-ANALISE/HISTORICO/PIL.md` | Diário SA — PIL | 2026-08-10 | 2 | pasta de histórico / story concluída |
| `Agente-cad-PYSIDE-Restored-main/docs/STATUS-ATUAL-JUNHO-2026.md` | CAD-ANALYZER — Status Atual & Próximos Passos | 2026-06-25 | 2 | curadoria: snapshot de junho |
| `Agente-cad-PYSIDE-Restored-main/docs/TEST_GAP_ANALYSIS.md` | Análise de Gaps de Testes — Vision-Estrutural AI | 2026-06-25 | 1 | curadoria: snapshot de junho |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/STORY-SA-1.1-RENDER-LINKS-HETEROGENEOS.md` | STORY SA-1.1 - Renderizacao segura de vinculos heterogeneos | 2026-06-29 | 0 | curadoria: story de jun/26 parada em Ready for Review |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/STORY-UX-SA-1.2-SALVAR-MCP-E-INTERACAO-PROJETOS.md` | STORY-UX-SA-1.2 - Salvar item SA, evidencia MCP e interacao do Gerenciar Projetos | 2026-06-29 | 0 | curadoria: story de jun/26 parada em Ready for Review |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/completed/CAD-10.1.story.md` | CAD-10.1: Mapper Fase-4 -> DetailCard | 2026-06-25 | 1 | pasta de histórico / story concluída |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/completed/CAD-10.2.story.md` | CAD-10.2: Upgrade _import_fase4_to_db() | 2026-06-25 | 1 | pasta de histórico / story concluída |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/completed/CAD-10.3.story.md` | CAD-10.3: Upgrade "Analise Geral" button | 2026-06-25 | 1 | pasta de histórico / story concluída |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/completed/CAD-10.4.story.md` | CAD-10.4: Comparison Panel na Ficha | 2026-06-25 | 1 | pasta de histórico / story concluída |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/completed/CAD-10.5.story.md` | CAD-10.5: Comparison Engine Renovado | 2026-06-25 | 1 | pasta de histórico / story concluída |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/completed/CAD-10.6.story.md` | CAD-10.6: Realimentacao do Interpretador | 2026-06-25 | 1 | pasta de histórico / story concluída |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/completed/CAD-5.1.story.md` | Story CAD-5.1 — Extrator B/H de Pilares (DIMENSION Proximity) | 2026-06-25 | 0 | pasta de histórico / story concluída |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/completed/CAD-5.2.story.md` | Story CAD-5.2 — Extrator Comprimento/Altura de Vigas (LV DXF) | 2026-06-25 | 0 | pasta de histórico / story concluída |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/completed/CAD-5.4.story.md` | Story CAD-5.4 — Extrator Garfos/EVG | 2026-06-25 | 0 | pasta de histórico / story concluída |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/completed/CAD-5.5.story.md` | Story CAD-5.5 — Auto-fill Fichas Completas por Robô | 2026-06-25 | 0 | pasta de histórico / story concluída |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/completed/CAD-6.1.story.md` | Story CAD-6.1 — Audit Completo DXF + Field Mapping para Robôs | 2026-06-25 | 0 | pasta de histórico / story concluída |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/completed/CAD-6.2.story.md` | Story CAD-6.2 — Extração total_width (B da Viga) do FV DXF | 2026-06-25 | 0 | pasta de histórico / story concluída |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/completed/CAD-6.3.story.md` | Story CAD-6.3 — Extração `coordenadas` das Lajes (LJ DXF) | 2026-06-25 | 0 | pasta de histórico / story concluída |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/completed/CAD-6.4.story.md` | Story CAD-6.4 — Integração Completa: vigas.json e lajes.json com todos os elementos | 2026-06-25 | 0 | pasta de histórico / story concluída |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/completed/CAD-6.5.story.md` | Story CAD-6.5 — Gerador DXF Headless para Pilares (ezdxf) | 2026-06-25 | 0 | pasta de histórico / story concluída |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/completed/CAD-6.6.story.md` | Story CAD-6.6 — Gerador DXF Headless para Vigas (ezdxf) | 2026-06-25 | 0 | pasta de histórico / story concluída |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/completed/CAD-6.7.story.md` | Story CAD-6.7 — Gerador DXF Headless para Lajes (ezdxf) | 2026-06-25 | 0 | pasta de histórico / story concluída |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/completed/CAD-6.8.story.md` | Story CAD-6.8 — Comparador DXF Gerado vs. Ground Truth | 2026-06-25 | 0 | pasta de histórico / story concluída |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/completed/CAD-6.8b.story.md` | Story CAD-6.8b — Validação Real Não-Circular vs. STOG | 2026-06-25 | 0 | pasta de histórico / story concluída |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/completed/CAD-6.9.story.md` | Story CAD-6.9 — Validação Não-Circular Completa (Pilares + Vigas + Lajes) | 2026-06-25 | 0 | pasta de histórico / story concluída |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/completed/CAD-7.1.story.md` | CAD-7.1 — Extração Assembly Data do DXF PL (CHAPA, GRADE, SP, Perfil Metálico) | 2026-06-25 | 0 | pasta de histórico / story concluída |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/completed/CAD-7.2.story.md` | CAD-7.2 — Extração MEIO_PONT por Laje (Pontaletes e Meio Pontaletes) | 2026-06-25 | 0 | pasta de histórico / story concluída |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/completed/CAD-8.1.story.md` | CAD-8.1 — Discovery de DXFs por Obra/Pavimento | 2026-06-25 | 0 | pasta de histórico / story concluída |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/completed/CAD-8.2.story.md` | CAD-8.2 — motor_fase4.py Multi-Pavimento | 2026-06-25 | 0 | pasta de histórico / story concluída |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/completed/CAD-8.4.story.md` | CAD-8.4 — Pipeline Orquestrador E2E (Single Command) | 2026-06-25 | 0 | pasta de histórico / story concluída |
| `Agente-cad-PYSIDE-Restored-main/docs/stories/completed/CAD-9.1.story.md` | CAD-9.1 — Extração de Coordenadas Absolutas (Âncoras STOG) | 2026-06-25 | 0 | pasta de histórico / story concluída |
| `MASTERPLAN-CEREBRO-RAG-MULTIMODAL-v1.0.md` | MASTERPLAN — Cérebro RAG Multimodal + Curadoria Redesign | 2026-06-29 | 8 | curadoria: antecessor da KB global (jun/26); princípios herdados em PLANO-HARMONIZACAO §2 |
| `RELEASE_NOTES_v3.0.md` | Release Notes - CAD-ANALYZER v3.0 | 2026-03-08 | 1 | curadoria: notas de release de mar/26 |
| `compreensao_global_app.md` | Compreensao Global e Auditoria de Implementacao | 2026-06-29 | 0 | curadoria: auditoria de implementação de jun/26 |
| `conversa_historico_truncado.md` | Histórico Recuperável da Conversa (Contexto Truncado) | 2026-07-09 | 0 | título marca histórico |
| `docs/HANDOFF-A-SQUAD-ESTADO-ATUAL.md` | HANDOFF-A: Estado Atual do Sistema CAD-ANALYZER | 2026-03-18 | 0 | curadoria: estado do sistema em mar/26 |

## legado (40)

| Fonte | Título | Data | Citado por | Motivo |
|---|---|---|---:|---|
| `Agente-cad-PYSIDE-Restored-main/README.md` | AgenteCAD / Estrutural Analyzer | 2026-09-26 | 0 | curadoria: descreve pipeline ML→SCR de jun/26 (SCR saiu |
| `Agente-cad-PYSIDE-Restored-main/STATUS.md` | STATUS.md — Vision-Estrutural AI v4.4 | 2026-09-26 | 0 | curadoria: STATUS v4.4 de jun/26, sistema desconectado; status real = docs/STATUS.md gerado |
| `Agente-cad-PYSIDE-Restored-main/_arquivo/README.md` | Arquivo — conhecimento legado | 2026-09-26 | 0 | arquivado em _arquivo/ (harmonização 2026-09-26) |
| `Agente-cad-PYSIDE-Restored-main/_arquivo/skills/agents-byterover/SKILL.md` | ByteRover Knowledge Management | 2026-09-26 | 0 | arquivado em _arquivo/ (harmonização 2026-09-26) |
| `Agente-cad-PYSIDE-Restored-main/_arquivo/skills/claude-byterover/SKILL.md` | ByteRover Knowledge Management | 2026-09-26 | 0 | arquivado em _arquivo/ (harmonização 2026-09-26) |
| `Agente-cad-PYSIDE-Restored-main/docs/_arquivo/README.md` | Arquivo — conhecimento legado | 2026-09-26 | 0 | arquivado em _arquivo/ (harmonização 2026-09-26) |
| `Agente-cad-PYSIDE-Restored-main/docs/_arquivo/rag-junho-2026/TRAINING-PIPELINES-SPEC.md` | Training Pipelines Spec - ARETE, RAG e Humano no Loop | 2026-09-26 | 1 | arquivado em _arquivo/ (harmonização 2026-09-26) |
| `Agente-cad-PYSIDE-Restored-main/docs/_arquivo/rag-junho-2026/stories/STORY-MCP-1.0-ACTIVE-LEARNING-SEGURO.md` | STORY MCP-1.0 - Active Learning seguro | 2026-09-26 | 0 | arquivado em _arquivo/ (harmonização 2026-09-26) |
| `Agente-cad-PYSIDE-Restored-main/docs/_arquivo/rag-junho-2026/stories/STORY-RAG-0.5-ANTI-SYNTHETIC-VALIDATION.md` | STORY RAG-0.5 - Anti Synthetic Validation Guard | 2026-09-26 | 0 | arquivado em _arquivo/ (harmonização 2026-09-26) |
| `Agente-cad-PYSIDE-Restored-main/docs/_arquivo/rag-junho-2026/stories/STORY-RAG-1.1-SEMANTIC-RAG-KB-POPULADA.md` | STORY RAG-1.1 - semantic_rag_kb Populada | 2026-09-26 | 0 | arquivado em _arquivo/ (harmonização 2026-09-26) |
| `Agente-cad-PYSIDE-Restored-main/docs/_arquivo/rag-junho-2026/stories/STORY-RAG-1.2-INDEXACAO-T1-AUDITADA.md` | STORY RAG-1.2 - Indexacao T1 Auditada | 2026-09-26 | 0 | arquivado em _arquivo/ (harmonização 2026-09-26) |
| `Agente-cad-PYSIDE-Restored-main/docs/_arquivo/rag-junho-2026/stories/STORY-RAG-2.0-CURADORIA-OBSERVADOR-VALIDADA.md` | STORY RAG-2.0 - Curadoria Observador Validada | 2026-09-26 | 0 | arquivado em _arquivo/ (harmonização 2026-09-26) |
| `Agente-cad-PYSIDE-Restored-main/docs/_arquivo/rag-junho-2026/stories/STORY-RAG-2.7-CURADORIA-PIPELINES-TREINO.md` | STORY RAG-2.7 - Curadoria: Pipelines de Treino | 2026-09-26 | 0 | arquivado em _arquivo/ (harmonização 2026-09-26) |
| `Agente-cad-PYSIDE-Restored-main/docs/_arquivo/rag-junho-2026/stories/STORY-RAG-3.0-AUDITORIA-HOOKS-HUMANOS.md` | STORY RAG-3.0 - Auditoria dos Hooks Humanos | 2026-09-26 | 0 | arquivado em _arquivo/ (harmonização 2026-09-26) |
| `Agente-cad-PYSIDE-Restored-main/docs/_arquivo/rag-junho-2026/stories/STORY-RAG-3.1-CROP-LEARNING-DIAGNOSTIC-REVERSE.md` | STORY RAG-3.1 - Crop Learning no Diagnostic Reverse Hub | 2026-09-26 | 0 | arquivado em _arquivo/ (harmonização 2026-09-26) |
| `Agente-cad-PYSIDE-Restored-main/docs/_arquivo/rag-junho-2026/stories/STORY-RAG-3.1B-VALIDACAO-F5-N2.md` | STORY RAG-3.1b - Validacao Humana da F5/N2 | 2026-09-26 | 0 | arquivado em _arquivo/ (harmonização 2026-09-26) |
| `Agente-cad-PYSIDE-Restored-main/docs/_arquivo/rag-junho-2026/stories/STORY-RAG-3.2-MEMORIA-ARTEFATOS-N3-N4.md` | STORY RAG-3.2 - Memoria de Artefatos N3/N4 | 2026-09-26 | 0 | arquivado em _arquivo/ (harmonização 2026-09-26) |
| `Agente-cad-PYSIDE-Restored-main/docs/_arquivo/rag-junho-2026/stories/STORY-RAG-3.2A-GALERIA-ARTEFATOS.md` | STORY RAG-3.2A — Galeria de artefatos N3/N4 | 2026-09-26 | 0 | arquivado em _arquivo/ (harmonização 2026-09-26) |
| `Agente-cad-PYSIDE-Restored-main/docs/_arquivo/rag-junho-2026/stories/STORY-RAG-4.0-RAG-POR-OBRA-AUDITADO.md` | STORY RAG-4.0 - RAG por Obra Auditado | 2026-09-26 | 0 | arquivado em _arquivo/ (harmonização 2026-09-26) |
| `Agente-cad-PYSIDE-Restored-main/docs/_arquivo/rag-junho-2026/stories/STORY-RAG-4.1-CONTEXTO-READ-ONLY-SA.md` | STORY RAG-4.1 - Contexto RAG Read-only no Structural Analyzer | 2026-09-26 | 0 | arquivado em _arquivo/ (harmonização 2026-09-26) |
| `Agente-cad-PYSIDE-Restored-main/docs/_arquivo/rag-junho-2026/stories/STORY-RAG-4.2A-RETRIEVAL-LOCAL-SEGURO.md` | STORY RAG-4.2A — Retrieval local seguro por obra | 2026-09-26 | 0 | arquivado em _arquivo/ (harmonização 2026-09-26) |
| `Agente-cad-PYSIDE-Restored-main/docs/_arquivo/rag-junho-2026/stories/STORY-RAG-6.0-OPERACAO-E-PLUGINS.md` | STORY RAG-6.0 — Operação segura e plugins de classe | 2026-09-26 | 0 | arquivado em _arquivo/ (harmonização 2026-09-26) |
| `Agente-cad-PYSIDE-Restored-main/docs/_arquivo/rag-junho-2026/stories/active/RAG-0.story.md` | RAG-0: Fundacao de confianca anti-contaminacao do RAG | 2026-09-26 | 0 | arquivado em _arquivo/ (harmonização 2026-09-26) |
| `Agente-cad-PYSIDE-Restored-main/docs/_arquivo/rag-junho-2026/stories/active/RAG-1.story.md` | RAG-1: Regras semanticas seguras no semantic_rag_kb | 2026-09-26 | 0 | arquivado em _arquivo/ (harmonização 2026-09-26) |
| `Agente-cad-PYSIDE-Restored-main/docs/_arquivo/rag-junho-2026/stories/active/RAG-2.story.md` | RAG-2 - Curadoria Observadora Read-Only | 2026-09-26 | 0 | arquivado em _arquivo/ (harmonização 2026-09-26) |
| `Agente-cad-PYSIDE-Restored-main/docs/_arquivo/rag-junho-2026/stories/active/RAG-3.story.md` | RAG-3 - Validacao Humana Event-Driven | 2026-09-26 | 0 | arquivado em _arquivo/ (harmonização 2026-09-26) |
| `Agente-cad-PYSIDE-Restored-main/docs/_arquivo/rag-junho-2026/stories/active/RAG-4.story.md` | RAG-4 - Consulta RAG Read-Only no Comparison Engine | 2026-09-26 | 0 | arquivado em _arquivo/ (harmonização 2026-09-26) |
| `Agente-cad-PYSIDE-Restored-main/docs/_arquivo/rag-junho-2026/stories/active/RAG-5.story.md` | RAG-5 - Snapshot RAG Local por Obra | 2026-09-26 | 0 | arquivado em _arquivo/ (harmonização 2026-09-26) |
| `Agente-cad-PYSIDE-Restored-main/docs/_arquivo/rag-junho-2026/stories/active/RAG-6.story.md` | RAG-6 - Registro Declarativo de Classes | 2026-09-26 | 0 | arquivado em _arquivo/ (harmonização 2026-09-26) |
| `Agente-cad-PYSIDE-Restored-main/docs/_arquivo/rascunhos/task_verification.md` | Verification of Canvas Updates | 2026-09-26 | 0 | arquivado em _arquivo/ (harmonização 2026-09-26) |
| `README.md` | CAD-ANALYZER v3.0 | 2026-09-26 | 9 | curadoria: README de mar/26 da raiz; entrada vigente é CLAUDE.md |
| `_arquivo/README.md` | Arquivo — conhecimento legado | 2026-09-26 | 0 | arquivado em _arquivo/ (harmonização 2026-09-26) |
| `_arquivo/docs/HANDOFF-C-ROADMAP-PRODUCAO.md` | HANDOFF-C: Roadmap para Produção | 2026-09-26 | 0 | arquivado em _arquivo/ (harmonização 2026-09-26) |
| `_arquivo/docs/MASTERPLAN-RAG-INTEGRACAO-COMPLETA.md` | MASTERPLAN — RAG: Integração Completa por Todas as Frentes | 2026-09-26 | 2 | arquivado em _arquivo/ (harmonização 2026-09-26) |
| `_arquivo/docs/MASTERPLAN-RAG-VECTORIZACAO.md` | MASTERPLAN | 2026-09-26 | 3 | arquivado em _arquivo/ (harmonização 2026-09-26) |
| `_arquivo/masterplans-antigos/MASTERPLAN-CAD-ANALYZER-SQUADS.md` | MASTERPLAN — CAD-ANALYZER: Team Completo + Pipeline End-to-End | 2026-09-26 | 1 | arquivado em _arquivo/ (harmonização 2026-09-26) |
| `_arquivo/masterplans-antigos/MASTERPLAN-CAD-ANALYZER-v2.md` | MASTERPLAN CAD-ANALYZER v2.0 — Estado Real + Gap Analysis para ARETE | 2026-09-26 | 0 | arquivado em _arquivo/ (harmonização 2026-09-26) |
| `_arquivo/masterplans-antigos/MASTERPLAN-CAD-ANALYZER-v3.md` | MASTERPLAN CAD-ANALYZER v3.0 — Geração DXF por Robô + Comparação vs. Engenharia Reversa | 2026-09-26 | 0 | arquivado em _arquivo/ (harmonização 2026-09-26) |
| `_arquivo/masterplans-antigos/MASTERPLAN-CAD-ANALYZER-v4.0.md` | MASTERPLAN CAD-ANALYZER v4.0 | 2026-09-26 | 1 | arquivado em _arquivo/ (harmonização 2026-09-26) |
| `_arquivo/masterplans-antigos/MASTERPLAN-SS-v5.0.md` | MASTERPLAN SS — Vision-Estrutural AI v4.7 → v5.0 SS | 2026-09-26 | 0 | arquivado em _arquivo/ (harmonização 2026-09-26) |
