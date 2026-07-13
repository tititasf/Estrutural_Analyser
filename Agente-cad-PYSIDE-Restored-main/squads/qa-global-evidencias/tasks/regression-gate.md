---
task: regression-gate
agent: aegis
inputs: [changed_component, class_scope, golden_baseline]
outputs: [regression-report.json]
mutates: false
---

# Executar regressão

Rodar primeiro testes unitários/contratos focados, depois regressão da classe e dos
pavimentos exigidos. Comparar baseline histórico sem exigir corrigir FAIL antigo, mas
bloquear qualquer novo FAIL. Fix em gerador/motor/comparador exige o gate definido no repo.
