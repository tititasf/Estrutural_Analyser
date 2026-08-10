---
task: regression-gate
agent: aegis
inputs: [changed_component, class_scope, golden_baseline]
outputs: [regression-report.json]
mutates: false
scripts:
  - pytest (tests/test_qa_*.py e focados da classe)
---

# Executar regressão

Rodar primeiro testes unitários/contratos focados, depois regressão da classe e dos
pavimentos exigidos. Comparar baseline histórico sem exigir corrigir FAIL antigo, mas
bloquear qualquer novo FAIL. Fix em gerador/motor/comparador exige o gate definido no repo.

Incluir quando tocar autoridade/contrato:

- `python scripts/arete/qa_authority_matrix.py`
- `pytest tests/test_qa_authority_matrix.py tests/test_qa_*.py -q` (escopo mínimo)

## Aceite positivo

- Nenhum FAIL novo no escopo declarado.

## Aceite negativo

- Regressão verde **não** declara Arete ok sem gate visual exigido.
