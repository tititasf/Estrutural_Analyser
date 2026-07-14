# QA LV — microciclo N1 / dual SVG / fast path

- Escopo: `Obra_TREINO_1` / `13_PAV` / projeto `dd238e47-1dc6-4f63-a760-4e7ce19a7386`.
- Itens selecionados pelos dados: `V301` (complexo), `V327` (referência), `V330` (Grade) e `V322` (aberturas).
- Alteração universal: cada segmento LV passa a exigir dois SVGs N1, local e contextual. O contexto é limitado ao mesmo lado e comportamento; não autoriza espelho A/B, nem cria eventos.
- Proveniência exposta no card: `source_key` e `source_slot` do contrato efetivamente usado.
- Fast path: a assinatura content-addressed inclui `src/core/lv_generation_contract.py`.
- Regressão: `24 passed` em `test_headless_partial_dependencies`, `test_headless_fv_diagnostic_integration`, `test_preficha_lateral_html` e `test_lv_generation_contract`.

## Estado da prova

O headless canônico de `V301` foi iniciado uma vez com `--wait --persist-db`, mas falhou antes do estágio LV por `NameError: _fv_global_boundary_link` em `main.py:12693`. Este arquivo não altera a dependência FV/PIL fora do escopo. Por isso não houve persistência parcial LV, smoke N3, ficha real atualizada ou veredito visual CLI nesta rodada.

## Próximo item técnico

Após a correção externa do helper compartilhado, retomar pelo mesmo comando de V301, executar a probe `four_contracts_and_support`, então `qa_n3_smoke.py` e `ficha_motor_item.py` para as seis variantes. Só depois avançar, item a item, para V327, V330 e V322.
