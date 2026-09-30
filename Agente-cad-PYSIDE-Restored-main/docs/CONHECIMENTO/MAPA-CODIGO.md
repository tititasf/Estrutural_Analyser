# Mapa de código

> Gerado por `scripts/kb/kb_mapa_codigo.py` em 2026-09-26 a partir das docstrings. Não editar à mão.
> ★ canônico (citado pelo CLAUDE.md / LOOPING-CANONICO §1) · ✗ descontinuado · · sem docstring

**648 módulos**, 136 sem docstring.

## App — núcleo (src/core) (100)

| Módulo | Papel |
|---|---|
| `src/core/agent_identity.py` | AgenteCAD - Sistema Operacional Cognitivo Antigravity |
| `src/core/analysis_helpers.py` | Funções puras extraídas do Structural Analyzer (main.py Fase 3). |
| `src/core/artifact_governance.py` | · |
| `src/core/auth/models.py` | · |
| `src/core/beam_corridor_recovery.py` | Recupera o corredor físico de uma viga a partir do par de paredes do DXF. |
| `src/core/beam_identity.py` | Canonical identity and safe consolidation for structural beams. |
| `src/core/beam_interpreters/channel_confidence_scorer.py` | ChannelConfidenceScorer: Mapeamento de sinais de confiança e coincidência espacial entre vínculos de fundo e canais físicos DXF. |
| `src/core/beam_interpreters/contracts.py` | Contratos dos interpretadores estruturais derivados da topologia de vigas. |
| `src/core/beam_interpreters/fundo_viga.py` | Interpretacao exclusiva dos segmentos de fundo de viga (FV). |
| `src/core/beam_interpreters/global_channel_extractor.py` | GlobalBeamChannelExtractor — Extrator Global de Canais de Fôrma de Vigas. |
| `src/core/beam_interpreters/lateral_viga.py` | Contratos isolados dos quatro fluxos de lateral de viga. |
| `src/core/beam_interpreters/lateral_viga_cells.py` | Segmentacao SA (N1) das Laterais de Viga — as QUATRO celulas isoladas. |
| `src/core/beam_interpreters/pilar_viga.py` | Contratos isolados para relacoes pilar-viga. |
| `src/core/beam_interpreters/registry.py` | Registro fechado dos sete interpretadores estruturais. |
| `src/core/beam_segment_validation.py` | Segmentos de viga (FV/LV) — chaves e checagem de completude. |
| `src/core/beam_support_links.py` | Normalização neutra dos apoios globais de vigas. |
| `src/core/beam_tracer.py` | · |
| `src/core/beam_walker.py` | · |
| `src/core/cad_utils.py` | · |
| `src/core/cima_l_contract.py` | Contrato editável do CIMA L — grades, quadradinhos, parafusos, desvio. |
| `src/core/context_engine.py` | · |
| `src/core/crop_learning_store.py` | Generic crop learning storage for reverse-engineering crops. |
| `src/core/database.py` | · |
| `src/core/drive_client.py` | Cliente HTTP da app desktop pro portal web (Masterplan OBRAS DRIVE, Fase 1). |
| `src/core/drive_download_hook.py` | Hook único de download sob demanda (Masterplan OBRAS DRIVE). |
| `src/core/drive_mirror.py` | Cria o "espelho local" de 1 item de obra Drive (Masterplan OBRAS DRIVE, Fase 1). |
| `src/core/dxf_loader.py` | · |
| `src/core/dxf_loader_instrumented.py` | [NEW v7/v8] Sanitizador Global de Geometria. Remove 'fans' e artefatos de todo o Modelspace. |
| `src/core/engrev_fv_n1_interpretacao_learning_store.py` | Auditable learning store for N1 FV (Fundo de Viga) interpretation. |
| `src/core/engrev_laj_n1_interpretacao_learning_store.py` | Auditable learning store for N1 LAJ interpretation. |
| `src/core/engrev_laj_recorte_learning_store.py` | Storage auditavel para aprendizagem de recortes LAJ da engenharia reversa. |
| `src/core/ficha_utils.py` | Canonical ficha helpers for F1-F9. |
| `src/core/field_mapping.py` | CAD-10.1 |
| `src/core/fundo_segment_levels.py` | Derivação auditável do nível de cada segmento de fundo de viga. |
| `src/core/fv_generation_contract.py` | Canonical input contract shared by the FV N3/N4 generator. |
| `src/core/geometry_engine.py` | · |
| `src/core/infra/supabase_client.py` | · |
| `src/core/item_attention_store.py` | · |
| `src/core/item_manual.py` | Identidade e criação de item desenhado na WEB (P3 do caminho de entrega). |
| `src/core/laj_n3_learning.py` | Shared N3/Robo Laje line learning from validated human LAJ fichas. |
| `src/core/laj_n3_stog_runner.py` | N3 LAJ generation bridge using the same STOG DXF generator as N4. |
| `src/core/laje_n1_to_robot_ficha.py` | Convert N1 LAJ interpretation data into the robot LJ ficha contract. |
| `src/core/learning/baseline_runner.py` | Baseline Runner - roda um pavimento sem learning e registra o hit rate base. |
| `src/core/learning/bottom_beam_learning_store.py` | · |
| `src/core/learning/context_signature.py` | Assinatura geometrica (Context Key) para o Learning Store. |
| `src/core/learning/feedback_models.py` | Dataclasses para o Learning Store. |
| `src/core/learning/learning_store_base.py` | Classe base do Learning Store. |
| `src/core/learning/learning_store_cache.py` | Cache singleton thread-safe para o Learning Store. |
| `src/core/learning/learning_store_factory.py` | Factory para instanciar o Learning Store correto por classe estrutural. |
| `src/core/learning/slab_learning_store.py` | SlabLearningStore - Learning Store especifico para lajes. |
| `src/core/lv_beam_scene.py` | Cena medida de uma viga para as Laterais de Viga (LV) — topologia BRUTA. |
| `src/core/lv_draw_contract.py` | Contrato rigido entre fichas LV e o motor de desenho N3/N4. |
| `src/core/lv_generation_contract.py` | Contrato de geracao N3 para laterais, derivado dos vinculos canonicos SA. |
| `src/core/lv_support_contact.py` | Geometric guard for LV endpoint supports. |
| `src/core/memory.py` | · |
| `src/core/memory_system.py` | Sistema de Memória Multi-Nível AgenteCAD |
| `src/core/n2_anchor.py` | Âncora N2 canônica — recorte validado no Diagnostic Reverse Hub. |
| ★ `src/core/n2_marco_highlight.py` | Contorno do marco vermelho N2 (LAJ) — CE + audit visual (fonte única). |
| `src/core/n2_pilar_views.py` | N2 original views for PIL: pick the human recorte and crop CIMA / ABCDEF. |
| `src/core/n5_assembler.py` | · |
| `src/core/niveis_extractor.py` | Motor de extração de cotas da Elevação Típica. |
| `src/core/obra_identity.py` | Identidade canônica de obra/pavimento — ponto único de normalização. |
| `src/core/perspective_mapper.py` | · |
| ★ `src/core/pil_qa_notes_chrome.py` | Chrome de QA dinâmico PIL — espelho do looping FV (validadores + anotações + layers). |
| `src/core/pillar_abcd_tables.py` | Tabelas de interpretação ABCD por face (laje / passa / chega / interior). |
| `src/core/pillar_analyzer.py` | · |
| `src/core/pillar_db_hydration.py` | Compatibilidade de payload PIL entre snapshots desktop e headless. |
| `src/core/pillar_face_beams.py` | Enriquecimento de faces de pilar com vigas (passa por esquina + chegadas). |
| `src/core/pillar_geometry_fix.py` | Correção dinâmica de contorno de pilar (geometria vinculada errada). |
| `src/core/pillar_geometry_recovery.py` | Recuperacao conservadora de contornos de pilares truncados no DXF. |
| `src/core/pillar_n3_ficha.py` | Contrato editavel N1 -> N3 para pilares no portal. |
| `src/core/pillar_special_faces.py` | Interpretação geométrica de pilares ortogonais especiais (A–F). |
| `src/core/pillar_table_evidence.py` | Pós-processamento conservador de tabelas a partir da topologia N1. |
| `src/core/preficha_segments.py` | Contrato puro entre os segmentos produzidos pelo SA e a pre-ficha. |
| `src/core/qa_presentation_notice.py` | Aviso canônico: apresentação HTML/checkbox ≠ prova QA Arete. |
| `src/core/recorte_motor.py` | Recorte Motor — Extrator automático de recortes de engenharia reversa. |
| `src/core/sa_db_persistence.py` | Persistência transacional da reanálise do Structural Analyzer. |
| `src/core/sa_project_source.py` | Fonte canônica de entrada do Structural Analyzer. |
| `src/core/security/data_protection.py` | · |
| `src/core/services/audit_exporter.py` | CAD-10.5 |
| `src/core/services/auth_service.py` | · |
| `src/core/services/cloud_intelligence_service.py` | · |
| `src/core/services/comparison_service.py` | CAD-10.4 |
| `src/core/services/completude_cache.py` | CAD-15 |
| `src/core/services/correction_service.py` | CAD-10.6 |
| `src/core/services/data_coordinator.py` | · |
| `src/core/services/delivery_service.py` | CAD-12 |
| `src/core/services/dxf_generator.py` | CAD-11 |
| `src/core/services/email_service.py` | · |
| `src/core/services/fase4_importer.py` | CAD-10.2 |
| `src/core/services/ml_feedback_service.py` | CAD-13 |
| `src/core/services/multi_pav_importer.py` | CAD-14 |
| `src/core/services/storage_service.py` | · |
| `src/core/services/sync_service.py` | · |
| `src/core/slab_level_inference.py` | Seleção conservadora de níveis de laje derivados de cortes e da planta. |
| `src/core/slab_tracer.py` | · |
| `src/core/spatial_index.py` | · |
| `src/core/storage/project_storage.py` | · |
| `src/core/text_associator.py` | · |
| `src/core/validation_model.py` | Modelo de validação de campo/item [2026-07-13] — 3 origens de campo |

## App — UI PySide (src/ui) (54)

| Módulo | Papel |
|---|---|
| `src/ui/canvas.py` | · |
| `src/ui/components/atoms.py` | · |
| `src/ui/components/molecules_comparison.py` | · |
| `src/ui/components/molecules_control.py` | · |
| `src/ui/components/molecules_diagnostic.py` | · |
| `src/ui/components/organisms.py` | · |
| `src/ui/components/project_cards.py` | · |
| `src/ui/confidence_indicator.py` | ConfidenceIndicator - Widget reutilizavel para exibir confidence de campos. |
| `src/ui/dialogs/convert_doc_dialog.py` | · |
| `src/ui/dialogs/correction_dialog.py` | CAD-10.6 |
| `src/ui/dialogs/create_client_dialog.py` | · |
| `src/ui/dialogs/delivery_dialog.py` | CAD-12 |
| `src/ui/dialogs/detail_dialog.py` | · |
| `src/ui/dialogs/document_upload_dialog.py` | · |
| `src/ui/dialogs/email_detail_dialog.py` | · |
| `src/ui/dialogs/generate_dxf_dialog.py` | CAD-11 |
| `src/ui/dialogs/project_details_dialog.py` | · |
| `src/ui/dialogs/robot_ficha_dialog.py` | · |
| `src/ui/drive_obras_combo.py` | Padrão único de UI/UX pra QComboBox de obras (Masterplan OBRAS DRIVE). |
| `src/ui/modules/comparison_engine.py` | · |
| `src/ui/modules/diagnostic_hub.py` | · |
| ★ `src/ui/modules/diagnostic_reverse_hub.py` | Diagnostic Reverse Hub — Tab 2 |
| `src/ui/modules/dxf_loader_worker.py` | subprocess helper para extrair ops vetoriais de DXF. |
| `src/ui/modules/dxf_scan_worker.py` | subprocess helper para escanear labels do DXF estrutural. |
| `src/ui/modules/ficha_pdf_generator.py` | Gerador de fichas PDF por classe (PIL/LV/FV/LAJ) usando reportlab 4.x. |
| `src/ui/organisms/admin_panel.py` | · |
| `src/ui/organisms/login_widget.py` | · |
| `src/ui/organisms/user_profile_dialog.py` | · |
| `src/ui/overlays.py` | · |
| `src/ui/overlays_beams.py` | · |
| `src/ui/theme.py` | Design System v1.0 · CAD Analyzer – Vision Estrutural AI |
| `src/ui/widgets/admin_dashboard.py` | · |
| `src/ui/widgets/central_controle.py` | · |
| `src/ui/widgets/comparison_tab.py` | CAD-10.4 |
| `src/ui/widgets/dashboard_components.py` | · |
| `src/ui/widgets/data_pipeline.py` | · |
| `src/ui/widgets/detail_card.py` | · |
| ★ `src/ui/widgets/fv_hifi_n1_render.py` | HI-FI N1 render for Fundos de Viga (FV). |
| `src/ui/widgets/fv_hifi_n1_render.py.__fix__.py` | HI-FI N1 render for Fundos de Viga (FV). |
| `src/ui/widgets/fv_qa_proposal_draw.py` | Capacidade de desenho do QA no N1 contextual FV. |
| `src/ui/widgets/interpretation_dialog.py` | · |
| `src/ui/widgets/link_manager.py` | · |
| `src/ui/widgets/pre_validation_dialog.py` | PreValidationDialog — janela de confirmação pós-análise de lajes. |
| `src/ui/widgets/preficha_fundo_html.py` | Gerador granular das páginas HTML de fundos de viga. |
| `src/ui/widgets/preficha_laje_html.py` | Gerador granular das páginas HTML de lajes (LJ). |
| `src/ui/widgets/preficha_lateral_html.py` | Gerador granular das páginas HTML de laterais de viga (LV). |
| `src/ui/widgets/project_manager.py` | · |
| `src/ui/widgets/qa_global_dossier_panel.py` | Painel mínimo: abrir dossiê QA (prova) sem reimplementar o motor. |
| `src/ui/widgets/svg_embed_utils.py` | Helpers para embutir SVG inline nas fichas granulares N1-N4. |
| `src/ui/widgets/training_log.py` | · |
| `src/ui/widgets/training_log_dialog.py` | · |
| `src/ui/workers/canvas_worker.py` | · |
| `src/ui/workers/code_publico_worker.py` | Worker de background pra buscar o código público (App de Consulta) de |
| `src/ui/workers/dxf_worker.py` | · |

## App — outros (src/*) (13)

| Módulo | Papel |
|---|---|
| `src/agents/base_agent.py` | Base Agent - Classe Base para Todos os Agentes |
| `src/agents/generator_agent.py` | Generator Agent - Agente de Geração |
| `src/agents/interpreter_agent.py` | Interpreter Agent - Agente de Interpretação |
| `src/agents/perception_agent.py` | Perception Agent - Agente de Percepção |
| `src/agents/swarm_orchestrator.py` | Swarm Orchestrator - Coordenador de Agentes |
| `src/agents/validator_agent.py` | Validator Agent - Agente de Validação |
| `src/ai/memory_store.py` | · |
| `src/ai/multimodal_processor.py` | Processador Multimodal para RAG Avançado - AgenteCAD |
| `src/ai/vision_client.py` | · |
| `src/cognitive/causal_engine.py` | Causal Vector Engine - Motor de Raciocinio Causal |
| `src/cognitive/rag_dialectic.py` | RAG Dialectic - Retrieval Augmented Generation com Dialética |
| `src/cognitive/vector_trajectory.py` | Vector Trajectory - Blockchain de Pensamentos |
| `src/utils/auto_indexer.py` | · |

## Portal web (portal/app) (60)

| Módulo | Papel |
|---|---|
| `portal/app/access.py` | Regras de visibilidade entre membro comum e dono (papel='dono') — 2026-07-06. |
| `portal/app/auth.py` | Login por membro + sessao via cookie assinado (HANDOFF §4). |
| `portal/app/auto_publish_poller.py` | Auto-publicação de obras para a App de Consulta Pública. |
| `portal/app/certification.py` | Rotulo de certificacao por classe (certificado/beta) — R9 / DP-13. |
| `portal/app/classificador.py` | Sugestão de classe/pavimento por nome de arquivo (2026-07-06 — triagem em lote). |
| `portal/app/config.py` | Configuracao do portal — paths, credenciais Drive, intervalos, segredo de sessao. |
| `portal/app/dbdep.py` | Dependencia FastAPI: conexao SQLite por request. |
| `portal/app/drawing_modes.py` | Contrato compartilhado dos estilos visuais expostos pelo portal. |
| `portal/app/drive_poller.py` | Poller do Google Drive (DP-10/DP-11/R8) por injecao de dependencia. |
| `portal/app/dxf_preview.py` | Renderização DXF→PNG (2026-07-06) — para telas que só têm DXF, sem preview |
| `portal/app/ficha_reader.py` | Leitor nativo de fichas N1/N3 do portal (2026-07-06). |
| `portal/app/fv_ficha.py` | Compositor da ficha nativa HI-FI de fundos de viga do portal. |
| `portal/app/fv_operations.py` | Operacoes persistentes e atomicas do SA de fundos de viga. |
| `portal/app/jobs.py` | Fila de jobs: worker de thread unica + exclusao mutua real via single_instance (HANDOFF §3). |
| `portal/app/laje_ficha.py` | Contrato enxuto da ficha web de lajes, com camadas carregadas sob demanda. |
| `portal/app/laje_operations.py` | Edições humanas persistentes da ficha web de lajes. |
| `portal/app/lv_ficha.py` | Compositor da ficha web de laterais de viga (Lado A/B, Para/Passa). |
| `portal/app/lv_n3_operations.py` | Contratos N3 editáveis de LV sem modificar a rodada SA original. |
| `portal/app/lv_operations.py` | Overrides web persistentes para detalhes manuais das laterais de viga. |
| ★ `portal/app/main.py` | App factory FastAPI do portal (HANDOFF §1.1). NUNCA importa PySide6. |
| `portal/app/n5_release.py` | Liberacao self-service do N5 (DP-13/R9): assemble_n5 real + registro auditavel. |
| `portal/app/pillar_abcd_review.py` | Correções humanas da tabela ABCD, isoladas do snapshot imutável do SA. |
| `portal/app/pillar_level_view.py` | Cotas consultivas das faces PIL no portal, sem modificar o snapshot N1. |
| `portal/app/pillar_tag_view.py` | Atualiza a vista com tags a partir da tabela ABCD consultiva do portal. |
| `portal/app/pipeline_runner.py` | Acionamento do pipeline: subprocess do headless + import do assemble_n5 (HANDOFF §1.2). |
| `portal/app/preprocessamento/adapters/cuts.py` | Chamadas explícitas de corte; seção e planta nunca são sobrepostas por nome. |
| `portal/app/preprocessamento/adapters/inventory.py` | Inventário consultivo de rótulos de lajes/vigas por recorte de torre. |
| `portal/app/preprocessamento/adapters/level_convention.py` | Leitura conservadora da convenção de níveis, sem alterar o extrator SA. |
| `portal/app/preprocessamento/adapters/level_crossing.py` | Levantamento pré-SA de cotas por torre, sem criar resultados estruturais. |
| `portal/app/preprocessamento/adapters/levels.py` | Campos de nível explícitos: sem datum não há preenchimento assistido. |
| `portal/app/preprocessamento/adapters/pillar_convention.py` | Extração conservadora da legenda geométrica de pilares em DXF. |
| `portal/app/preprocessamento/adapters/pillars.py` | Inventário de pilares por recorte de torre, sem persistência SA. |
| `portal/app/preprocessamento/context_resolver.py` | Contexto SA opcional, fixado por projeto, torre e revisão antes do processo. |
| `portal/app/preprocessamento/contracts.py` | Contrato v1 dos pacotes internos de pré-processamento. |
| `portal/app/preprocessamento/crosscheck.py` | Conflitos consultivos e ciclos de proveniência; não promove consenso. |
| `portal/app/preprocessamento/freshness.py` | Revisões de dependências, sem invalidar ou escrever resultados estruturais. |
| `portal/app/preprocessamento/preprocess_runner.py` | Execução isolada do pré-processamento pelo worker do portal. |
| ★ `portal/app/preprocessamento/runner.py` | Runner isolado da fundação do pré-processamento. |
| `portal/app/preprocessamento/sa_comparison.py` | Comparação consultiva com snapshot SA de origem exata. |
| `portal/app/preprocessamento/service.py` | Lote isolado: pacotes imutáveis e índice SQLite transacional próprio. |
| `portal/app/preprocessamento/sources.py` | Resolução de fontes por obra/pavimento/bruto/recorte. |
| `portal/app/preprocessamento/store.py` | Publicação atômica e leitura dos pacotes de pré-processamento. |
| `portal/app/public_codes_lookup.py` | Consulta (SÓ LEITURA) de `public_consulta.db` a partir do portal |
| `portal/app/qa_jobs.py` | Execucao persistente de uma rodada QA multi-item no worker serial do portal. |
| `portal/app/recortes_reader.py` | Leitor dos recortes reais gerados por `RecorteMotor` (2026-07-06). |
| `portal/app/routers/admin_publish_routes.py` | Publicação de obras para a App de Consulta Pública (STORY-01). |
| `portal/app/routers/auth_routes.py` | Rotas de autenticacao: POST /login, POST /logout, GET /me (HANDOFF §1.1/§4). |
| `portal/app/routers/comentarios_routes.py` | Rotas de comentarios T0 (equipe:*) — server-side, substituem localStorage (HANDOFF §1.1/§4). |
| `portal/app/routers/fichas_routes.py` | Rotas de fichas HTML: serve os HTML N1-N4 ja gerados pelo pipeline (HANDOFF §1.1). |
| `portal/app/routers/jobs_routes.py` | Rotas das etapas 2-6 do fluxo enxuto (DP-14) + GET /jobs/{id} (HANDOFF §1.2). |
| `portal/app/routers/n1_routes.py` | Rotas do viewer nativo N1 (SA) — 2026-07-06 (ver plano witty-hopping-sunbeam). |
| `portal/app/routers/obras_routes.py` | Rotas de obras: GET /obras, GET /obras/{id} (HANDOFF §1.1/§1.2 etapa 1). |
| `portal/app/routers/paginas_routes.py` | Páginas server-rendered do portal (Jinja2) — front-end mínimo (HANDOFF-UX §1-6). |
| `portal/app/routers/preprocessamento_routes.py` | Fila do inventário pré-SA por pavimento; sem acionar motores estruturais. |
| `portal/app/routers/qa_routes.py` | Endpoints autenticados da fila QA agêntica multi-item. |
| `portal/app/routers/recortes_routes.py` | Rotas do viewer de Recortes (bruto×limpo) — 2026-07-06. |
| `portal/app/routers/viewer_routes.py` | Viewer do ESTRUTURAL LIMPO por pavimento (P2 do MASTERPLAN-CONSOLIDACAO-ENTREGA). |
| `portal/app/seed.py` | CLI de admin do dono: cadastra membros no portal_data.db (HANDOFF §4). |
| `portal/app/torre_crop.py` | Recorte por torre/detalhes (2026-07-07) — motor REAL de review visual. |
| `portal/app/viewer_pavimentos.py` | Quais pavimentos da obra têm estrutural limpo para abrir no viewer. |

## Scripts — geradores, motores, obra (scripts/) (195)

| Módulo | Papel |
|---|---|
| `scripts/_patch_cima_v2.py` | Patch draw_cima v2 — 6 correções baseadas no robô SCR. |
| `scripts/_test_abcd_counts.py` | Testa contagem de entities ABCD ezdxf vs SCR. |
| `scripts/_test_lv_counts.py` | Testa contagem de entities LV draw_lv_face vs SCR (face 1). |
| `scripts/analisar_dxf_detalhado.py` | Análise profunda entity-by-entity de um DXF |
| `scripts/analise_geral_headless.py` | Análise Geral Headless — equivalente a process_pillars_action sem GUI/PySide6. |
| `scripts/analise_massiva_lv_stog.py` | Análise massiva de vigas laterais STOG |
| `scripts/apply_correction.py` | CAD-10.6 |
| `scripts/arete_lj_batch_13pav.py` | Batch ARETE LAJ para Obra_TREINO_1 / 13_PAV. |
| `scripts/arete_lj_canonico.py` | Comparador canonico LAJ para a frente Arete Laje. |
| `scripts/arete_lj_visual_audit.py` | Gera auditoria visual autonoma ARETE LAJ. |
| `scripts/atualizar_bh_com_stog.py` | Atualiza pilares_bh.json com dados STOG (ground truth). |
| `scripts/audit_db.py` | · |
| `scripts/audit_dxf_robot_fields.py` | Auditoria completa dos DXFs STOG vs. campos dos robôs. |
| `scripts/audit_laj_n1_n3_13pav.py` | Audit N1/N3 LAJ outputs against N2/N4 references for Obra_TREINO_1 13_PAV. |
| `scripts/audit_theme_compliance.py` | Detecta cores hardcoded fora do theme.py |
| `scripts/auditar_interpretacao.py` | Auditoria de campos suspeitos em JSONs Fase-3/Fase-4. |
| `scripts/batch_stog_validate.py` | Roda os 4 geradores STOG + validação em todas as obras. |
| `scripts/build_bootstrapper_pyinstaller.py` | · |
| `scripts/build_fast_updater.py` | · |
| `scripts/build_installer.py` | · |
| `scripts/build_nuitka.py` | · |
| `scripts/build_only_updater.py` | · |
| `scripts/build_release.py` | · |
| `scripts/cad_pipeline_cli.py` | CLI unificado do CAD-ANALYZER (CAD-12.1 / 12.2 / 12.3) |
| `scripts/certificar_obra.py` | Certificação formal do pipeline CAD-ANALYZER (CAD-11.1) |
| `scripts/check_supabase_files.py` | · |
| `scripts/check_url.py` | · |
| `scripts/check_versions.py` | BUILD-02: Verifica versões e injeta em installer.iss |
| `scripts/ciclo_refinamento.py` | Ciclo completo de refinamento ezdxf vs AutoCAD ground truth |
| `scripts/comparar_assembly_pl.py` | Validação não-circular dos dados de assembly (CAD-7.x) |
| `scripts/comparar_bh_stog_vs_gerado.py` | Comparacao NAO-CIRCULAR. |
| `scripts/comparar_dxf.py` | Comparador de DXFs gerados vs. dados Fase 3 (ground truth). |
| `scripts/comparar_lajes_stog_vs_gerado.py` | Comparacao NAO-CIRCULAR para lajes. |
| `scripts/comparar_stog_fidelidade.py` | Compara DXF STOG real vs DXF gerado por layer |
| `scripts/comparar_vigas_stog_vs_gerado.py` | Comparacao NAO-CIRCULAR para vigas. |
| `scripts/compare_parts.py` | · |
| `scripts/completion_batch.py` | · |
| `scripts/consolidar_dxf_lajes.py` | Consolida DXFs individuais de lajes em LJ_gerado.dxf. |
| `scripts/consolidar_dxf_pilares.py` | Consolida DXFs individuais de pilares em um |
| `scripts/consolidar_dxf_vigas.py` | Consolida DXFs individuais de vigas em |
| `scripts/convert_icon.py` | · |
| `scripts/converter_dwg_dxf_accore.py` | Converte DWG → DXF no Windows ou Linux. |
| `scripts/converter_dwg_dxf_autocad.py` | converter_dwg_dxf_autocad.py |
| `scripts/debug_tufup_error.py` | · |
| `scripts/debug_updater_client.py` | · |
| `scripts/demo_channel_scoring_telemetry.py` | · |
| `scripts/deploy_update.py` | · |
| `scripts/descobrir_obras.py` | Discovery automático de DXFs por obra/pavimento. |
| `scripts/diag_cut_views_pav13.py` | Diagnóstico de visões de corte — PAV 13. |
| `scripts/discover_cad.py` | · |
| `scripts/domain_knowledge_ingestor.py` | RAG Forge / CAD Domain Knowledge |
| `scripts/dxf_cleanup.py` | Pós-processamento de DXFs gerados pelos Robôs. |
| `scripts/engenharia_reversa_dxf.py` | Extração de ground truth a partir de DXFs de entrega STOG. |
| `scripts/engrev_laj_recorte_loop.py` | Loop headless de validacao dos recortes LAJ da engenharia reversa. |
| `scripts/export_training_data.py` | CAD-13 |
| `scripts/extract_n2_gabarito.py` | · |
| `scripts/extract_n2_report.py` | · |
| `scripts/extrair_ancoras_dxf.py` | Extrai coordenadas absolutas (ancoras) de cada |
| `scripts/extrair_assembly_pl.py` | Extrai dados de montagem do DXF PL (CAD-7.x) |
| `scripts/extrair_bh_pilares.py` | Extrai dimensoes B e H de pilares a partir dos |
| `scripts/extrair_garfos_evg.py` | Extrai dados de garfos/EVG do EVG DXF. |
| `scripts/extrair_grades_pl.py` | Extrai dados de grades dos DXFs STOG PL (Pilares) |
| `scripts/extrair_lajes_lj.py` | Extrai dados de lajes a partir dos DXFs ESTRUTURAIS |
| `scripts/extrair_largura_vigas_fv.py` | Extrai largura (B = min(b,h)) das vigas a partir |
| `scripts/extrair_meioPont_pl.py` | CAD-7.2: Extração de PONTALETE e MEIO_PONTALETE por Laje |
| `scripts/extrair_nivel_lajes.py` | Extrai mapa granular de nível por laje. |
| `scripts/extrair_parametros_viga.py` | Extração profunda de parâmetros de vigas STOG |
| `scripts/extrair_parametros_viga_v3.py` | Extração STOG v3: Painéis + Seção separados |
| `scripts/extrair_poligono_lajes.py` | Extrai coordenadas (poligono) das lajes a partir |
| `scripts/extrair_secoes_stog_pl.py` | Extrai B/H REAL de cada pilar do DXF STOG PL. |
| `scripts/extrair_vigas_lv.py` | Extrai altura_lateral (h) e comprimento de vigas a partir |
| `scripts/fase4_to_detail_mapper.py` | CAD-10.1 (AC-5) |
| `scripts/fidelidade_kb_scorer.py` | EPIC-STOG-5 |
| `scripts/fidelidade_lajes.py` | Fidelidade geométrica: LJ_gerado.dxf vs STOG LJ original (CAD-10.4) |
| `scripts/fidelidade_pilares.py` | Fidelidade geométrica: PL_gerado.dxf vs STOG PL original (CAD-10.2) |
| `scripts/fidelidade_vigas.py` | Fidelidade geométrica: LV_gerado + FV_gerado vs STOG originais (CAD-10.3) |
| `scripts/finish_packaging.py` | · |
| `scripts/fix_css_fstrings.py` | Fix broken f-string CSS braces: Colors.TOKEN}}; rest }  -> Colors.TOKEN}; rest }} |
| `scripts/full_robot_json_patch.py` | · |
| `scripts/fv_arete_pipeline.py` | FV ARETE Pipeline — Extrai N2 de cada recorte, gera N4, compara. |
| `scripts/fv_l_panel_geometry.py` | Geometric recognition helpers for folded FV panels. |
| `scripts/fv_loop_runner.py` | FV Loop Runner — executa comparação N1×N2 para Fundo de Vigas sem GUI. |
| `scripts/fv_render_compare.py` | Renderiza recorte N2 e N4 gerado lado a lado para comparação visual. |
| `scripts/fv_render_loop.py` | Render headless do pavimento para o loop de qualidade FV. |
| `scripts/generate_icon.py` | · |
| `scripts/gerar_50_cenarios.py` | Gera 50+ cenários SCR de cada robô para base de dados sólida |
| `scripts/gerar_50_cenarios_fv.py` | Generate 50 FV scenarios via real robot (decompiled gerar_script). |
| `scripts/gerar_50_cenarios_lajes.py` | Generate 50 laje scenarios via SmartPanner + save as JSON. |
| `scripts/gerar_50_cenarios_lv.py` | Generate 50 LV scenarios via real robot. |
| `scripts/gerar_dxf_lajes.py` | Gerador DXF headless para lajes (ezdxf). |
| `scripts/gerar_dxf_pilares.py` | Gerador DXF headless para pilares (ezdxf). |
| `scripts/gerar_dxf_vigas.py` | Gerador DXF headless para vigas (ezdxf). |
| `scripts/gerar_fv_dxf_stog.py` | Gerador STOG-quality FV DXF (Vigas Fundo, sem AutoCAD) |
| `scripts/gerar_ground_truth_batch.py` | Executa todos os 50 SCR de cada tipo no AutoCAD via COM |
| ★ `scripts/gerar_lj_dxf_stog.py` | Gerador STOG-quality LJ DXF (Lajes, sem AutoCAD) |
| `scripts/gerar_lv_dxf_stog.py` | Gerador STOG-quality LV DXF (Vigas Laterais, sem AutoCAD) |
| `scripts/gerar_obra_completa.py` | Gera SCR + DXF para obra inteira via robôs reais |
| `scripts/gerar_obras_salvas.py` | Gerador de obras_salvas.json no formato do Robo_Pilares |
| `scripts/gerar_pl_dxf_stog.py` | Gerador STOG-quality PL DXF (sem AutoCAD) |
| `scripts/gerar_scr_pilares.py` | Gera SCR AutoCAD para pilares a partir de JSON Fase-4 |
| `scripts/gerar_scr_via_robo.py` | Gera SCR usando os robôs PySide REAIS |
| `scripts/gerar_vc_headless.py` | Gera 50 cenários Visão de Corte (VC) headless |
| `scripts/import_obras_to_db.py` | Importa obras de D:/Agente-cad-PYSIDE/DADOS-OBRAS para o banco local. |
| `scripts/inspect_bundle.py` | · |
| `scripts/inspect_db_schema.py` | · |
| `scripts/inspect_dbs.py` | · |
| `scripts/integrar_fichas_completas.py` | Integra todos os dados extraídos em fichas completas |
| `scripts/integrar_fichas_fase3.py` | Integra todas as fontes Fase 3 em vigas.json e lajes.json completos. |
| `scripts/integrar_fichas_pilares.py` | Integra todas as fontes Fase 3 em pilares.json completo. |
| `scripts/laje_analise_geral_headless.py` | Analise Geral Headless para LAJ - equivalente ao loop FV, sem GUI/PySide6. |
| `scripts/laje_human_quality_gate.py` | Quality gate for LAJ Structural Analyzer against human validated outlines. |
| `scripts/laje_loop_runner.py` | LAJ Loop Runner - compara N1 x N2 para Lajes sem GUI. |
| `scripts/list_n2_13pav.py` | · |
| `scripts/lj_refinamento_loop_vision.py` | · |
| `scripts/lj_vision_loop.py` | · |
| `scripts/lv_ab_prod_pav_loop_runner.py` | Baseline visual N2 x N4 para laterais A/B de vigas LV. |
| `scripts/lv_n2_vision_loop_runner.py` | lv_n2_vision_loop_runner.py |
| `scripts/lv_n4_unit_loop_runner.py` | lv_n4_unit_loop_runner.py |
| `scripts/lv_section_prod_pav_loop_runner.py` | Loop de producao N2 x N4 para visoes-corte LV de um pavimento. |
| `scripts/lv_section_visual_loop_runner.py` | Baseline visual N2 x N4 para visoes de corte de laterais de viga. |
| `scripts/migrate_storage.py` | · |
| `scripts/migrate_versions.py` | · |
| `scripts/mostrar_stog_elementos.py` | · |
| `scripts/mostrar_stog_zoom.py` | · |
| `scripts/mostrar_stog_zoom2.py` | · |
| `scripts/motor_fase4.py` | Fase 4 Sincronizacao Headless |
| `scripts/motor_reverso_fv.py` | Motor Reverso FV — Extrai ficha N2 de recorte DXF STOG fundo de viga. |
| `scripts/motor_reverso_laj.py` | Motor Reverso LAJ — Extrai ficha N2 de recorte DXF STOG laje. |
| `scripts/motor_reverso_lv.py` | Motor Reverso LV — Extrai ficha N2 de recorte DXF STOG lateral viga. |
| `scripts/motor_reverso_obra.py` | Motor Reverso Obra v2 — Análise inteligente da obra a partir das fichas N2. |
| `scripts/motor_reverso_pil.py` | Motor Reverso PIL — Extrai ficha granular N2 de recorte DXF STOG pilar. |
| `scripts/motor_reverso_pil_zones.py` | Extrai 3+1 fichas N2 separadas por zona PIL. |
| `scripts/motor_version_report.py` | · |
| `scripts/nim_prerender_worker.py` | Daemon de pré-renderização de DXFs para PNG. |
| `scripts/nuitka_inspector.py` | · |
| `scripts/obra_crop_engine.py` | Motor de recorte automático de DXFs brutos. |
| `scripts/obra_dxf_classifier.py` | Classifica DXFs da Fase-1 de uma obra. |
| `scripts/obra_global_scanner.py` | Sprint 2: Scanner global de DXFs limpos aprovados. |
| `scripts/obra_pdf_ingestor.py` | Indexa PDFs/MDs da Fase-1 de uma obra no RAG por-obra. |
| `scripts/obra_rag_pipeline.py` | Orquestrador do pipeline RAG semântico da Fase 1. |
| `scripts/obra_rag_utils.py` | Utilitários compartilhados para o RAG por-obra. |
| `scripts/obra_triagem_populator.py` | Popula SQLite obra_triagem com sugestões do RAG. |
| `scripts/onboarding_obra.py` | Integração de nova obra ao pipeline CAD-ANALYZER (CAD-12.4) |
| `scripts/pipeline_batch.py` | Processa TODAS as obras/pavimentos completos em batch. |
| `scripts/pipeline_e2e.py` | Orquestrador E2E do pipeline CAD-ANALYZER. |
| `scripts/pl_abcd_visual_nova.py` | Visual ABCD modo NOVA — regras gerais (qualquer pilar/obra). |
| `scripts/pl_cima_especial.py` | CIMA DXF de pilar especial (L) — conversão do motor SCR. |
| `scripts/pl_grade_visual_config.py` | Perfis visuais das travessas horizontais das grades de pilares. |
| `scripts/pos_batch_certify.py` | Certificação pós-batch e atualização STATUS_GLOBAL. |
| `scripts/pre_build_obfuscate.py` | Script de pré-processamento para ofuscar código antes do build PyInstaller |
| `scripts/preprocessamento_pavimento.py` | CLI seguro para construir a camada interna de pré-processamento. |
| `scripts/regenerar_batch.py` | · |
| `scripts/regenerar_e_validar.py` | Regenera os 4 DXFs de uma obra e valida os elementos. |
| `scripts/relatorio_fidelidade.py` | Relatório consolidado de fidelidade do pipeline (CAD-10.5) |
| `scripts/render_3_cases_overlay.py` | Script para gerar a renderização dos 3 casos de validação visual: |
| `scripts/render_massivo_lv.py` | Renderização massiva de vigas STOG individuais |
| `scripts/reproduzir_lv_comparacao.py` | Reprodução + Comparação de vigas STOG v3 |
| `scripts/restore_metadata.py` | · |
| `scripts/run_all_scr_autocad.py` | Executa SCR scripts no AutoCAD via COM automation |
| `scripts/run_cut_view_analysis_headless.py` | Roda _auto_link_slab_cut_views headless para PAV 13 e salva de volta no DB. |
| `scripts/run_pil_batch.py` | Run PIL fidelidade scorer for all obras. |
| `scripts/run_scr_autocad.py` | Executa SCR no AutoCAD via COM automation |
| `scripts/sanitize_files.py` | · |
| `scripts/setup_supabase_env.py` | · |
| `scripts/smart_panner.py` | Motor de Distribuição de Painéis para Lajes (Completo) |
| `scripts/stog_adaptive_sentinel.py` | stog_adaptive_sentinel.py |
| `scripts/stog_intelligence_extractor.py` | EPIC-STOG-2 |
| `scripts/stog_rag_ingestor.py` | EPIC-STOG-3 |
| `scripts/test_native_download.py` | · |
| `scripts/test_part14.py` | · |
| `scripts/test_part15.py` | · |
| `scripts/test_prancha.py` | Test prancha detection on TREINO_18 LV and TREINO_3 FV. |
| `scripts/test_preprocess_worker.py` | Testa PreProcessAllWorker._process() fora do Qt. |
| `scripts/test_range_support.py` | · |
| `scripts/test_ssl_download.py` | · |
| `scripts/test_ssl_old.py` | · |
| `scripts/test_tiny_range.py` | · |
| `scripts/test_urllib_download.py` | · |
| `scripts/testar_laje_nim.py` | · |
| `scripts/teste_reproducibilidade.py` | Teste de determinismo do pipeline CAD-ANALYZER (CAD-11.2) |
| `scripts/train_bottom_beams_auto.py` | · |
| `scripts/train_real_bottom_beams.py` | · |
| `scripts/update_dxf_paths.py` | Atualiza dxf_path de todos os projetos no banco para o DXF estrutural correto. |
| `scripts/upload_intelligence.py` | · |
| `scripts/validar_dxf_coletivo.py` | Valida DXFs coletivos gerados vs. IDs do ground truth. |
| `scripts/validar_elementos_dxf.py` | Validador por elemento segundo SPEC-GERADORES-DXF.md |
| `scripts/validar_geometria_visual.py` | · |
| ★ `scripts/validar_granular_nim.py` | Validação visual granular por elemento (viga individual). |
| `scripts/validar_lv_stog.py` | Automated LV DXF Validation: Generated vs STOG Reference |
| `scripts/validar_pipeline_sa.py` | Validação do Pipeline SA → Robôs |
| `scripts/validar_score_pipeline.py` | Compara fichas extraídas pelo pipeline com ground truth. |
| `scripts/validar_visual_dxf.py` | · |
| `scripts/verify_final_setup.py` | BUILD-01: Smoke test do executável Nuitka compilado. |
| `scripts/verify_python_runtime.py` | Validate the only supported CAD-ANALYZER Python runtime. |
| `scripts/visual_modes.py` | Perfis visuais dos geradores DXF de Pilares e Vigas. |

## Scripts — Arete / QA (scripts/arete) (220)

| Módulo | Papel |
|---|---|
| `scripts/arete/_audit_abcd_pack.py` | Audita tabelas ABCD de um pack de pilares (sem N1, rápido). |
| ★ `scripts/arete/_build_segments_html_v301.py` | HTML E2E multi-segmento V301 com RENDER DXF real (ezdxf), não wireframe. |
| `scripts/arete/_bump_abcd_fonts.py` | Aumenta fontes nas fichas ABCD já exportadas (sem re-render N1). |
| `scripts/arete/_diag_dims_b.py` | · |
| `scripts/arete/_diag_ficha_v301.py` | Dump da ficha live V301 (recorte N2 -> entry N4) — inspeciona face_units. |
| `scripts/arete/_diag_ficha_v301b.py` | Dump COMPACTO da ficha live V301 — so o essencial por face_unit. |
| `scripts/arete/_diag_marco_n2n4.py` | Marco zone exact V/H/HATCH for V301.A N2 vs N4. |
| `scripts/arete/_diag_metrics.py` | · |
| `scripts/arete/_diag_n2_cota_lines.py` | · |
| `scripts/arete/_diag_n2_dim_anchor.py` | · |
| `scripts/arete/_diag_n4_b_geom.py` | · |
| `scripts/arete/_diag_n4_band.py` | Dump de TODAS as linhas do N4 VIEW_B.dxf na banda de uma unidade. |
| `scripts/arete/_diag_right_dim_v301.py` | Dim verticals after extreme-right wall — N2 vs N4 V301.A/B. |
| `scripts/arete/_diag_right_wall_v301.py` | Dump V/H na zona direita (body_end - 5 .. full) N2 vs N4 V301.A/B. |
| `scripts/arete/_diag_unitb8.py` | Diff linhas must_reproduce N2 x N4 — UNIT.B#8 (11B) e UNIT.B#11 (6B). |
| `scripts/arete/_diag_units_v301.py` | Dump face_units UNIT* panels/h/marco for V301. |
| `scripts/arete/_diag_v301_ab.py` | Diagnóstico rápido V301 A/B — face_units, N4 bands, cotas inventadas. |
| `scripts/arete/_fix_pil_sa_fields_p123.py` | Preenche campos SA de P1–P3 (13_PAV) a partir dos contratos N3 derivados. |
| `scripts/arete/_force_viewbox_pz.py` | · |
| `scripts/arete/_html_animal_v301.py` | HTML ANIMAL V301 — N4 full + N2 + clips de visão. |
| `scripts/arete/_inject_pil_qa_chrome.py` | Injeta chrome QA PIL (validadores + layers) em pack já exportado com N1 SVG. |
| `scripts/arete/_open_zoom_right_v301.py` | Gera zoom N2×N4 da parede extrema direita + cotas e abre no browser. |
| `scripts/arete/_overfit_gerar_pl_BACKUP.py` | Gerador STOG-quality PL DXF (sem AutoCAD) |
| `scripts/arete/_patch_abcd_atencao_ui.py` | Patch em fichas ABCD existentes: remove checklist + injeta campo Atenção. |
| `scripts/arete/_patch_abcd_next_invalid_btn.py` | Patch nas fichas ABCD existentes: injeta botão "Próximo pendente" na nav-bar. |
| `scripts/arete/_patch_abcd_struct_atencao.py` | Injeta APONTAMENTOS ESTRUTURADOS dentro de cada caixa agêntica (L1/L2/L3). |
| `scripts/arete/_patch_arete100.py` | Patches for Arete 100% G+R on V301.A/B. |
| `scripts/arete/_patch_ce_compare_n1_n2.py` | Patch Comparar N1 (contexto + destaque real) e Comparar N2 (resolve recorte). |
| `scripts/arete/_patch_ce_pil_n3.py` | Patch one-shot: CE PIL N3 load + restore_single_view + logging + n3_ok variants. |
| `scripts/arete/_patch_degrau_hatch.py` | · |
| `scripts/arete/_patch_frame_g80.py` | Patch _draw_panel_frame_n2 + small_x para G>=80% (A/B). |
| `scripts/arete/_patch_g100_honest.py` | G=100% honesto: so geometria presente no N2, zero phantom. |
| `scripts/arete/_patch_hatch2.py` | · |
| `scripts/arete/_patch_motor_bodyend.py` | · |
| `scripts/arete/_patch_n1_tabs.py` | Converte N1 empilhado → abas (próximo / distante) sem re-render SVG. |
| `scripts/arete/_patch_no_phantom.py` | Remove phantom V65@244 + paredes marco inventadas; gate FAIL se overdraw. |
| `scripts/arete/_patch_pil_panzoom_tags.py` | Injeta pan/zoom no N1 das fichas PIL e atualiza CSS/JS do chrome. |
| `scripts/arete/_probe_n1_svg.py` | · |
| `scripts/arete/_probe_prop_svg.py` | · |
| `scripts/arete/_summarize_v301_gate.py` | Resumo honesto gate V301 — foco alucinação (extra / inventada / pixel). |
| `scripts/arete/_tmp_cima_n2_geom.py` | Geometric read of N2 CIMA window: L contour, texts, small squares, dims. |
| `scripts/arete/_tmp_cima_svg_visual.py` | Render N2 CIMA (recorte) and N3 CIMA L as SVG+PNG for visual/geometric compare. |
| `scripts/arete/_tmp_cycle_b2.py` | · |
| `scripts/arete/_tmp_cycle_b3.py` | · |
| `scripts/arete/_tmp_inject_abcd_ef.py` | Inject N3 ABCD/GRADES 6-face SVGs into P26/P27 HTML (img-n3 only). |
| `scripts/arete/_tmp_map_segs.py` | · |
| `scripts/arete/_tmp_n2_cima_legacy.py` | N2 CIMA P27: perfil/madeira/parafuso vs concreto, in cm (drawing is 2x). |
| `scripts/arete/_tmp_patch_test_cima.py` | · |
| `scripts/arete/_tmp_probe_b.py` | · |
| `scripts/arete/_tmp_probe_b3.py` | Probe Face B verts around 244 and leftover V7 through laje. |
| `scripts/arete/_tmp_probe_laje_v.py` | Find ANY vertical edge (LINE or LWPOLYLINE) through the laje at 244. |
| `scripts/arete/_tmp_probe_n4dxf.py` | Inspect actual generated N4 combined DXF for Face B Painéis verts. |
| `scripts/arete/_tmp_probe_verts.py` | · |
| `scripts/arete/_tmp_regen_cima_l.py` | Regen CIMA L DXF/SVG/PNG and patch HTML N3 CIMA panel. |
| `scripts/arete/_tmp_rerender_abcd.py` | Re-render ABCD/GRADES with a tight crop so A-F fill the viewer. |
| `scripts/arete/_tmp_sarr_spans.py` | · |
| `scripts/arete/_zoom_marco_strict.py` | Zoom estrito marco N2×N4 — sem aspect expandir o crop. |
| `scripts/arete/aplicar_revisao_humana_pil_n2.py` | Registra na ficha N2 as correções geométricas validadas no painel humano. |
| `scripts/arete/apply_pil_aten_l1_n3_pack.py` | Aplica atenções humanas no pack ABCD → L1 corrigido + abas N3 (cima/ABCD/grades). |
| `scripts/arete/arete_config.py` | Configuracoes centrais do harness Arete Quality Gates. |
| ★ `scripts/arete/arete_runner.py` | Orquestrador G0→G1→G2→G6 (batch por classe). |
| `scripts/arete/arquivar_orfaos_identidade.py` | Arquiva linhas órfãs de pillars/beams/slabs — decisão do dono em 2026-07-30. |
| `scripts/arete/audit_n2_marco_attention.py` | Audit visual + loop do marco vermelho N2 (itens com atenção LAJ). |
| `scripts/arete/build_lv_debug_viewer.py` | Viewer unico de depuracao das laterais: SA x N3 x N4, por viga e segmento. |
| `scripts/arete/build_unvalidated_fv_n1_n3_html.py` | · |
| `scripts/arete/comparar_ficha_lv_vision.py` | Extrai ficha N2 de um recorte LV e valida com vision. |
| `scripts/arete/comparar_ficha_lv_vision_opus55.py` | variante Opus 5.5 de comparar_ficha_lv_vision.py. |
| `scripts/arete/comparar_lv_n3_n4.py` | Regua N3 x N4 das laterais de viga. |
| `scripts/arete/conversao_n1_diff.py` | Gate G4 para LAJ: converte o N1 bruto do SA e compara com o N2. |
| ★ `scripts/arete/diagnostico_common.py` | Helpers compartilhados pelos diagnósticos numéricos headless N1×N2 por classe. |
| `scripts/arete/diagnostico_fv_n1_n2.py` | Diagnóstico numérico headless entre os fundos de viga N1 e N2. |
| `scripts/arete/diagnostico_laj_n1_n2.py` | Diagnóstico numérico headless entre as lajes N1 e N2. |
| `scripts/arete/diagnostico_lv_n1_n2.py` | Diagnóstico numérico headless entre as laterais de viga (LV) N1 e N2. |
| `scripts/arete/diagnostico_pil_n1_n2.py` | Diagnóstico numérico headless entre os pilares N1 e N2. |
| ★ `scripts/arete/dxf_to_svg_casos.py` | Converte os DXFs gerados por gen_casos_n4_standalone.py em SVG (pra |
| `scripts/arete/enhance_revisao_svg_panzoom.py` | Publica uma variante do painel humano com svg-pan-zoom, sem tocar no DB. |
| `scripts/arete/exception_registry.py` | API de consulta sobre G2_EXCECOES (arete_config.py) |
| `scripts/arete/export_pilares_abcd_fichas.py` | Exporta fichas HTML de pilares com tabelas ABCD a partir do DB (sem Qt). |
| `scripts/arete/ficha_adapter.py` | Adapter N2→Fase-4 layout (DA-A3 do masterplan). |
| ★ `scripts/arete/ficha_motor_item.py` | Ficha visual individual para iterar motores N3/N4 sem abrir o SA. |
| `scripts/arete/fix_pil_l1n_no_slab_contact.py` | Corrige p_s{face}_l1_n/l2_n persistidos sem contato geometrico real com a laje. |
| `scripts/arete/forma_canonica_pil.py` | Extrator e diff de FORMA CANONICA por parte — G2 v1.2 (Paridade Canonica). |
| `scripts/arete/g2v_batch_mosaic.py` | Monta mosaico PNG por item (N1 local + N1 contextual + N2) a partir de relatorio g2v. |
| `scripts/arete/g2v_gate0_geometry.py` | Portão 0 geométrico (FAIL-closed) para G2-V. |
| ★ `scripts/arete/g2v_harness.py` | Harness ÚNICO de veredito VISUAL para todos os gates do Arete |
| `scripts/arete/gate_n2_n4_fidelidade.py` | Gate de fidelidade N2×N4 — camadas G (geometria) e R (rótulos). |
| `scripts/arete/gen_casos_n4_standalone.py` | Gera DXFs N4 (zonas ABCD/CIMA/GRADES) para os 12 casos didaticos da ficha |
| `scripts/arete/geometry_index.py` | GeometryIndex — retrieval estruturado N2/N3/N4 (sem RAG, sem pixels). |
| `scripts/arete/geometry_lv_units.py` | Âncora multi-unidade LV: face_units N2 ↔ bandas VIEW_A/B N4. |
| ★ `scripts/arete/gerar_duvida_html.py` | Gera a ficha HTML de uma dúvida de interpretação, para decisão do dono. |
| `scripts/arete/gerar_ficha_decisoes_medicao.py` | Gera a ficha de re-selo: células que a medição do desenho contradiz. |
| ★ `scripts/arete/gerar_html_preficha_headless.py` | Gerador headless de fichas HTML de pré-análise de pilares/vigas/lajes. |
| `scripts/arete/gerar_lv_n4_fichas.py` | Gera DXF N4 LV direto de fichas_lv_v2.json (bypass DB). |
| `scripts/arete/gerar_n4_item.py` | Gera DXF N4 a partir de ficha N2 (DB) para 1 ou N itens. |
| ★ `scripts/arete/gerar_status.py` | gera docs/STATUS.md a partir das fontes reais. |
| `scripts/arete/gold_lv.py` | Gold N2 de uma viga LV — medido do recorte cru, para o dono arbitrar. |
| ★ `scripts/arete/headless_sa_analise.py` | Executa o SA usando o mesmo projeto, DXF e motor da interface humana. |
| `scripts/arete/inject_n4_caso.py` | Injeta o bloco 'Geracao N4 dos diagramas' (carousel com SVGs ABCD/CIMA/ |
| `scripts/arete/inventario_geometria_fidelidade.py` | Inventário geométrico de fidelidade — coordenadas de CADA linha e cota. |
| `scripts/arete/jev_beam_section_pilot.py` | Read-only raw-DXF beam-label/section association probe for FV/LV evidence. |
| `scripts/arete/jev_beam_snapshot_probe.py` | Read-only, compact FV/LV N1 contract profile for one SA project. |
| `scripts/arete/jev_beam_tracer_ab_probe.py` | Compare current local vs copied VPS BeamTracer on the same frozen DXF, in memory. |
| `scripts/arete/jev_duplicate_slab_label_pilot.py` | Resolve two raw L409 labels against one N1 slab polygon, without trusting N1 text position. |
| `scripts/arete/jev_fv_scope_audit.py` | Audit whether FV opening summaries carry beam-wide context into each segment. |
| `scripts/arete/jev_fv_scope_jev_probe.py` | Jev QA gate for per-segment FV opening claims lacking local provenance. |
| `scripts/arete/jev_fv_segment_readonly_export.py` | Small read-only production FV evidence export for two ambiguous beams. |
| `scripts/arete/jev_hybrid_visual_pack.py` | Make full-layer source DXF SVG/PNG pairs for hybrid interpretation review. |
| `scripts/arete/jev_l410_physical_audit.py` | Reproduce the small raw-DXF physical evidence around L410. |
| `scripts/arete/jev_laj_ambiguous_height_probe.py` | Targeted Jev counterfactual for an ambiguous slab-level association. |
| `scripts/arete/jev_laj_height_pilot.py` | Read-only comparison of slab height labels from raw DXF text. |
| `scripts/arete/jev_laj_level_hybrid_pilot.py` | Read-only LAJ level association from DXF TEXT + N1 polygon + Jev. |
| `scripts/arete/jev_laj_level_stability_pilot.py` | Small Jev ablation on ambiguous 14_PAV slab elevation candidates. |
| `scripts/arete/jev_lv_cell_geometry_audit.py` | Audit N1 LV cells against their own FV geometry, without modifying N1. |
| `scripts/arete/jev_lv_cell_targeted_probe.py` | Targeted Jev cross-check on LV cell attribution, with a no-geometry control. |
| `scripts/arete/jev_lv_cell_visualize.py` | Plot one N1 LV attribution audit in plan coordinates (diagnostic, not source DXF). |
| `scripts/arete/jev_lv_contract_readonly_export.py` | Small read-only beam contract export; safe to pipe to VPS python3 stdin. |
| `scripts/arete/jev_lv_orientation_audit.py` | Read-only audit of LV orientation against raw DXF beam-label rotation. |
| `scripts/arete/jev_lv_orientation_jev_probe.py` | Jev second-opinion on LV orientation disagreements, using raw DXF only. |
| `scripts/arete/jev_n1_snapshot_fingerprint.py` | Read-only N1 table fingerprint for comparing local and VPS SA snapshots. |
| `scripts/arete/jev_pil_dim_pilot.py` | Read-only pilot: N1 pillar dimension text versus deterministic and Jev choices. |
| `scripts/arete/jev_pil_readonly_export.py` | Export only the pillar columns needed for a read-only Jev/SA comparison. |
| `scripts/arete/jev_prod_laj_level_crosscheck.py` | Compare production SA slab state against direct DXF elevation evidence. |
| `scripts/arete/jev_qa_probes_pilot.py` | Compare Jev evidence triage with existing field-scoped QA probes for four classes. |
| `scripts/arete/jev_sa_dynamic_router.py` | Read-only dynamic Jev/SA/CAD/vision routing from frozen VPS pilot evidence. |
| `scripts/arete/jev_sa_vision_fusion_pilot.py` | Read-only evidence fusion for the 14_PAV Jev/SA/visual research pilot. |
| `scripts/arete/jev_special_detail_link_pilot.py` | Cross-document Jev pilot: map special pillar labels to a raw CAD detail title. |
| `scripts/arete/jev_special_geometry_pilot.py` | Pilot for a shared detail resolving ambiguous special-pillar N1 rows. |
| `scripts/arete/limpar_html_fv.py` | Remove elementos indesejados das fichas HTML de fundos de viga já geradas. |
| `scripts/arete/lv_n4_face_unit_details.py` | Detalhes N4 de LV que usam campos explicitos por face_unit da ficha. |
| `scripts/arete/lv_n4_face_unit_selection.py` | Selecao canonica N4 sem colapsar ocorrencias com detalhe superior proprio. |
| `scripts/arete/migrate_semantic_rag_tier_columns.py` | Migra semantic_rag_kb para colunas nativas de tier/field/familia/pavimento. |
| `scripts/arete/paridade_n3_n4_laj.py` | Gate G5 LAJ: gera N3 de N1 bruto e compara canonicamente com N4. |
| `scripts/arete/paridade_visual.py` | Gate G2: paridade visual DXF N4 vs recorte N2. |
| `scripts/arete/partes_pil.py` | Segmentacao por partes (Modelo de Partes v1.1) para PIL. |
| `scripts/arete/patch_pil_geometry_reanalysis_status.py` | Marca visualmente fichas PIL cuja geometria-base foi reprovada. |
| `scripts/arete/persist_pil_face_beams_corridor_fix.py` | Reaplica `face_beams` nos pilares já persistidos, com a recuperação de |
| ★ `scripts/arete/pil_agentic_highlight_draw.py` | Desenha destaque PIL sobre N1 SVG (HI-FI DXF + faces coloridas + tags). |
| `scripts/arete/pil_arrival_tip_qa.py` | Audita e corrige somente o ponto visual das vigas que chegam. |
| `scripts/arete/pil_blind_l1_calibration.py` | Calibração cega do agente QA (Camada 1): roda checagens 100% derivadas de |
| `scripts/arete/pil_cruzamento_classes.py` | Cruzamento entre classes — corrobora a interpretação ABCD do pilar com o que |
| `scripts/arete/pil_geom_contato.py` | Predicado de relação viga↔face do pilar — por ALINHAMENTO, como manda o doc. |
| `scripts/arete/pil_l2_apply_calibrated_fixes.py` | Camada 2 (Ag.L2) — aplica correções SOBRE a Camada 1, com travas de integridade. |
| `scripts/arete/pil_l2_apply_evidence_fixes.py` | Aplica a Camada 2 (Ag.L2) a partir do relatório de evidência dura |
| `scripts/arete/pil_l2_evidence_check.py` | Diagnóstico de evidência dura p/ Camada 2 (looping agêntico PIL ABCD). |
| `scripts/arete/pil_l3_qa_microcycle.py` | Materializa a Camada 3 do microciclo QA de pilares. |
| `scripts/arete/pil_layer_from_struct.py` | Desenha uma camada (L2/L3) a partir dos APONTAMENTOS ESTRUTURADOS da camada |
| `scripts/arete/pil_layer_selfcheck.py` | Auto-avaliação de uma camada desenhada: o agente confere o PRÓPRIO desenho |
| `scripts/arete/pil_qa_memoria.py` | Memória de QA dos pilares — consolida atenções ESTRUTURADAS em: |
| ★ `scripts/arete/playwright_loop.py` | Visualização headless e interpretacao das fichas HTML de pré-análise. |
| `scripts/arete/probe_jev_lv_sa_n4.py` | Primeiro teste Jev (TypeSafe System One) no caminho LV SA x N3 x N4. |
| `scripts/arete/promote_arrival_tip_to_l3.py` | Promove o microciclo interno de ponto de chegada para a Camada 3 pública. |
| `scripts/arete/propagar_subtipo_pil.py` | Injeta `subtipo_pil` nos JSONs da Fase-4. |
| `scripts/arete/qa_agent_web_poc.py` | PoC local: web (localhost) -> subprocess `claude -p` (OAuth do plano |
| ★ `scripts/arete/qa_artifact_parity.py` | Paridade declarativa contrato → payload → DXF → HTML por campo/variante. |
| `scripts/arete/qa_authority_matrix.py` | Authority matrix canônica do QA Global — anti-drift skill/squad/código. |
| `scripts/arete/qa_class_capability.py` | Valida o mapa de capacidade do agente por classe (paridade PIL/LAJ/FV/LV). |
| `scripts/arete/qa_class_golden_regression.py` | Golden/regressão N1 multi-item unificado — PIL, LAJ, FV, LV. |
| `scripts/arete/qa_cli_fallback.py` | Roteador serial de QA entre CLIs autenticadas por assinatura/OAuth. |
| `scripts/arete/qa_cli_resilient.py` | Adaptação resiliente do provedor Antigravity para o QA do portal. |
| `scripts/arete/qa_content_cache.py` | Cache por conteúdo para fast paths QA. |
| `scripts/arete/qa_cycle_efficiency.py` | Rubrica de eficiência do ciclo treino × validação (QA Global). |
| `scripts/arete/qa_enqueue.py` | Enfileira uma rodada QA persistente sem depender da interface web. |
| `scripts/arete/qa_error_memory.py` | Memória de erro tipada por família (cross-sessão, sem hardcode de item). |
| ★ `scripts/arete/qa_error_review.py` | Janela de navegador persistente para triagem de erros |
| ★ `scripts/arete/qa_evidence_auditor.py` | Auditor CLI de evidências do Structural Analyzer. |
| `scripts/arete/qa_export_training.py` | Exporta o corpus QA; por padrão somente amostras promovidas por curadoria. |
| `scripts/arete/qa_fastpath_benchmark.py` | Benchmark reproduzível dos probes N1 ultragranulares. |
| `scripts/arete/qa_fv_lv_adapters.py` | Adaptadores CAD independentes para FV e LV (QA Global). |
| `scripts/arete/qa_fv_lv_golden_regression.py` | Compat: redireciona para o golden unificado das 4 classes (só FV/LV por default). |
| `scripts/arete/qa_fv_quadro_pavimento.py` | Quadro read-only de progresso FV por pavimento. |
| `scripts/arete/qa_g2v_record_verdict.py` | Registra veredito visual padronizado no relatorio.json do g2v_harness. |
| `scripts/arete/qa_g2v_visual_gate.py` | Gate visual de prontidão — PIL, LAJ, FV, LV via g2v_harness (backend CLI). |
| `scripts/arete/qa_handoff_assets.py` | Resolve assets de handoff multi-classe: quadro pavimento + KPIs treino/validação. |
| `scripts/arete/qa_identity_integrity.py` | Integridade de identidade obra/pavimento/item — diagnóstico READ-ONLY. |
| `scripts/arete/qa_laj_quadro_pavimento.py` | Quadro QA read-only de estado LAJ por pavimento. |
| ★ `scripts/arete/qa_loop_executor.py` | Executor persistente dos microciclos do QA Global de Evidências. |
| `scripts/arete/qa_lv_quadro_pavimento.py` | Quadro QA read-only de estado por pavimento para Laterais de Viga. |
| ★ `scripts/arete/qa_n1_field_probe.py` | Provas ultragranares de campos/vínculos N1, sem executar o SA completo. |
| `scripts/arete/qa_n1_sources.py` | Adaptadores mínimos de leitura N1 por classe para provas ultragranares. |
| ★ `scripts/arete/qa_n3_smoke.py` | Smoke semântico N3 por classe, variante, contrato e DXF. |
| `scripts/arete/qa_open_latest_dossier.py` | Localiza e opcionalmente abre o dossiê QA / run de loop mais recente. |
| `scripts/arete/qa_pil_approved_corpus.py` | Congela e compara o corpus PIL aprovado no looping HTML. |
| ★ `scripts/arete/qa_pil_coverage.py` | Cobertura estrutural do adaptador QA de pilares. |
| `scripts/arete/qa_pil_l1_visual.py` | QA agêntico PIL — **somente Camada 1** (vs SA motor com tags). |
| `scripts/arete/qa_pil_multimodal_rag.py` | Materializa um pacote RAG multimodal PIL sem promover memória ativa. |
| `scripts/arete/qa_pil_n1_contextual_pipeline.py` | CLI looping agêntico PIL (espelho FV propose-draw / write-agent). |
| `scripts/arete/qa_pil_quadro_pavimento.py` | Quadro read-only de progresso PIL por pavimento. |
| ★ `scripts/arete/qa_profile_probe.py` | Executa probes N1 declarados nos perfis semânticos de cada classe. |
| `scripts/arete/qa_rag_curation.py` | Materializa candidatos RAG a partir de uma sessão QA, sem promover memória. |
| `scripts/arete/qa_rag_evidence.py` | Consulta RAG particionada e retrocompatível para o QA Global. |
| `scripts/arete/qa_run_pack.py` | Executa uma rodada QA sincrona sobre um pack Arete (diagnostico/validacao). |
| `scripts/arete/qa_session_index.py` | Índice de sessão do QA Global N1 — camadas B2 (snapshot) e B3 (fonte CAD). |
| `scripts/arete/reconciliar_dimensoes_pil_n2.py` | Reconcilia dimensoes canonicas N2 PIL a partir das faces medidas no recorte. |
| `scripts/arete/reenrich_pillar_face_beams_db.py` | Reaplica face_beams (passa/para/dim limpa) em pillars.sides_data_json. |
| `scripts/arete/refresh_pil_qa_runtime.py` | Atualiza somente o runtime QA PIL de fichas já geradas. |
| `scripts/arete/regen_n3_variants_nova.py` | Re-enriquece e regenera todos os n3_variants com o motor NOVA universal. |
| `scripts/arete/regen_pl_n3_para_visual.py` | Regenera N3 (ABCD/GRADES) com visual NOVA via o motor geral. |
| ★ `scripts/arete/revisao_laj_n2_n4_html.py` | Painel humano local para revisar recortes N2 de LAJ contra N4 existente, |
| ★ `scripts/arete/revisao_pil_n2_n4_html.py` | Painel humano local para revisar recortes N2 de PIL contra N4 existente. |
| `scripts/arete/revisao_pil_n2_n4_vistas_html.py` | · |
| ★ `scripts/arete/rodada_lv_13pav.py` | Rodada de revisao granular LV — uma pagina por viga + indice. |
| `scripts/arete/roundtrip_ficha.py` | Gate G1: round-trip N2 -> N4 -> N2prime -> diff. |
| ★ `scripts/arete/run_geometry_gate_lv.py` | Geometry gate LV — N2×N4 multi-unidade via GeometryIndex. |
| `scripts/arete/run_lv_generator_n4.py` | Adaptador N4 LV: preserva ocorrencias repetidas com detalhe proprio de ficha. |
| `scripts/arete/serve_abcd_fichas.py` | Serve fichas ABCD + API de notas (looping agêntico PIL). |
| ★ `scripts/arete/servidor_revisao_pil.py` | Servidor local do painel PIL, com persistência explícita das revisões humanas. |
| ★ `scripts/arete/single_instance.py` | trava de instância única via lock exclusivo de arquivo. |
| `scripts/arete/sync_abcd_dxf_geometry_revision.py` | Cria uma revisao ABCD sem sobrescrever o checkpoint historico. |
| `scripts/arete/test_ce_pav_routing.py` | Valida que _get_recorte_dxf_for_er retorna o recorte |
| `scripts/arete/test_n2_n4_abcd.py` | Validacao N2 vs N4 para zona ABCD de pilares PIL. |
| `scripts/arete/test_visual_n2_n4.py` | Validacao visual N2 vs N4 ABCD PIL (3 camadas) |
| `scripts/arete/teste_subprocess_linux.py` | Reproduz no Linux o teste que TRAVAVA no Windows. |
| ★ `scripts/arete/triagem_concordancia.py` | Rollup de concordância entre diagnóstico automático e triagem humana. |
| `scripts/arete/validar_13pav_intervals.py` | Extrai paineis_intervals de cada PIL 13_PAV |
| `scripts/arete/validar_abertura_pilar_lv.py` | Valida `classificar_aberturas_pilar` contra o N2, por POSICAO DE PAREDE. |
| `scripts/arete/validar_aberturas.py` | Testa extração de aberturas nos itens de exemplo. |
| `scripts/arete/validate_pl_abcd_linewise.py` | Validação visual RIGOROSA linha-a-linha: DXF manual × gerado (ABCD PIL). |
| `scripts/arete/validate_sa_pillar_fields.py` | Valida população SA de pilares: face_beams, passa_esq/dir, chegadas, lajes, HTML N1. |
| `scripts/arete/validate_sa_pillar_run.py` | Valida pack HTML N1 de pilares + re-enrich com motor atual. |
| `scripts/arete/vision_anti_hallucination.py` | Camada de VISÃO anti-alucinação N2×N4. |

## Scripts — base de conhecimento (scripts/kb) (6)

| Módulo | Papel |
|---|---|
| ★ `scripts/kb/kb_build.py` | constrói o índice da base de conhecimento (global ou de uma obra). |
| `scripts/kb/kb_comum.py` | esquema, fatiamento e embedder da base de conhecimento (global e por obra). |
| `scripts/kb/kb_eval.py` | mede a qualidade da busca da KB contra perguntas com resposta conhecida. |
| `scripts/kb/kb_inventario.py` | inventário das fontes de conhecimento do workspace. |
| `scripts/kb/kb_mapa_codigo.py` | gera docs/CONHECIMENTO/MAPA-CODIGO.md a partir das docstrings. |
| ★ `scripts/kb/kb_query.py` | busca na base de conhecimento (global + obra), híbrida texto + significado. |
