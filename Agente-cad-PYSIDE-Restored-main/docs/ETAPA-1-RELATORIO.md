# ETAPA 1 - Fichas & Botoes

Data: 2026-06-20  
Escopo: fundacao F1-F9, botoes, IDs, schema granular, persistencia segura e F6.

## Mudancas

- Criado `src/core/ficha_utils.py` para IDs canonicos F1-F9, normalizacao de pavimento/classe, envelope `_ficha/_schema/_semantic_refs` e backup lazy do `.vision`.
- Criado `docs/SCHEMA-FICHA-GRANULAR.md` a partir dos campos reais de `reverse_eng_fichas.campos_json`.
- Reconciliado `docs/VECTOR_SCHEMA.md` apontando F5/F7 para o schema granular, sem migracao.
- `Iniciar Analise Geral` agora materializa F7/N1 em `fase3_fichas` via `DatabaseManager.save_fase3_fichas()`.
- `Analisar com Eng Reversa (F5/N2)` agora consulta F5/N2, mostra relatorio e carrega cache de consulta; nao chama `process_pillars_action()` e nao gera DXF.
- `Analise com Contexto (futuro)` ficou como placeholder documentado; nao altera dados.
- Reverse Hub carimba F5 e F4 com metadados canonicos e preserva `validated_fields` e `na_fields` ao regerar.
- F6 ganhou export `consolidar_obra_er()` e o resumo salvo recebe ID canonico F6.
- Migração destrutiva legada de `reverse_eng_fichas` foi neutralizada no import do Reverse Hub.
- Combo Structural tenta listar pavimentos pela `obra_triagem` aprovada e cai para `projects` quando necessario.
- Hub Pre ganhou fallback generico para pavimentos numericos, reduzindo exibicao como `Outros`.

## Piloto

Obra: `Obra_TREINO_1`  
Project ID: `4869be2b-f17c-410b-a9c8-98a887ec1c95`  
Pavimento normalizado: `13_PAV`

Consulta somente leitura no banco real:

- F5: FV 26, LAJ 27, LV 32, PIL 35.
- Recortes validados: FV 26, LAJ 27, LV 32, PIL 35.

## Verificacao

- `python -m py_compile main.py src/core/database.py src/core/ficha_utils.py src/ui/modules/diagnostic_reverse_hub.py src/ui/modules/diagnostic_hub.py scripts/motor_reverso_obra.py`
- Query read-only em `D:/Agente-cad-PYSIDE/project_data.vision` confirmou F5/recortes para `Obra_TREINO_1` / `13_PAV`.

## Fora do escopo

- Nenhum loop de treino foi implementado.
- Nenhuma regra em `transformation_rules` foi alterada.
- `src/core/slab_tracer.py` nao foi alterado.
- Acoplamento real de `_semantic_refs` com `domain_knowledge` fica para a etapa semantica/RAG.

