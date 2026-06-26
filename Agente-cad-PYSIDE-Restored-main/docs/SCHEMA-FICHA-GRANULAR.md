# SCHEMA-FICHA-GRANULAR

Versao: `granular-v1.0`  
Fonte: `project_data.vision`, tabela `reverse_eng_fichas.campos_json` real.

## Regra comum

F5 e F7 usam o mesmo envelope de metadados, sem alterar os campos de robo ja existentes:

- `_ficha.id`: ID canonico F1-F9, deterministico.
- `_ficha.tipo`: `F5` ou `F7`.
- `_ficha.obra`, `_ficha.pavimento`, `_ficha.classe`, `_ficha.item`.
- `_schema.name`: `SCHEMA-FICHA-GRANULAR`.
- `_schema.version`: `granular-v1.0`.
- `_semantic_refs`: mapa campo -> `pending_domain_knowledge_link`.

IDs:

- F5: `F5-{OBRA}-{PAV}-{CLASSE}-{ITEM}`.
- F7: `F7-{OBRA}-{PAV}-{CLASSE}-{ITEM}`.

## PIL

Campos reais: `numero`, `nome`, `comprimento`, `largura`, `altura`, `pavimento`, `nivel_chegada`, `nivel_saida`, `modo_distribuicao`, faces `A..H` com `h1_X..h5_X`, `larg1_X..larg3_X`, `laje_X`, `posicao_laje_X`, alem de campos de grade/parafusos quando presentes.

Semantica base: `docs/SEMANTICA-PILAR-NOVA.md`.

## LV

Campos reais: `number`, `name`, `floor`, `side`, `total_width`, `total_height`, `panels`, `holes`, `pillar_left`, `pillar_right`, `sarrafo_left_id`, `sarrafo_right_id`, `h_A`, `h_B`, `b_geom`, `h_section`, `h_section_all`, `laje_sup_A`, `laje_inf_A`, `laje_sup_B`, `laje_inf_B`, `tipo_viga`, `section_views`, `continuation`, `text_left`, `text_right`, `panels_A`, `panels_B`, `_er_meta`.

Semantica base: `docs/SEMANTICA-VIGA-NOVA.md`.

## FV

Campos reais: `number`, `name`, `floor`, `total_width`, `total_height`, `panels`, `segments_rich`, `holes`, `pillar_left`, `pillar_right`, `label_left`, `label_right`, `sarrafo_left_id`, `sarrafo_right_id`, `_n_linhas_folha`, `_er_meta`, `_fase4_ref`.

Semantica base: `docs/SEMANTICA-VIGA-NOVA.md`.

## LAJ

Campos reais: `numero`, `nome`, `comprimento`, `largura`, `pavimento`, `coordenadas`, `area_cm2`, `linhas_verticais`, `linhas_horizontais`, `obstaculos`, `modo_selecionado`, `unioes_nos_bordes`, `observacoes`, `pontaletes`, `_sa_meta`, `cotas_paineis`, `_stog_pose`, `_forma_canonica`, `_er_meta`.

Semantica base: `docs/SEMANTICA-LAJE-NOVA.md`.

## Aplicacao nesta etapa

- F5: `DiagnosticReverseHub._salvar_ficha()` preserva o JSON real e adiciona o envelope canonico.
- F7: `DatabaseManager.save_fase3_fichas()` materializa N1 em `fase3_fichas` com o mesmo envelope.
- Campos validados/NA continuam preservados por `validated_fields_json` e `na_fields_json` nos elementos estruturais e por merge no JSON de F5.

