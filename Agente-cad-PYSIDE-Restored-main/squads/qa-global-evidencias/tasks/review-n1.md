---
task: review-n1
agent: aegis
inputs: [scope.json, evidence-index.json]
outputs: [decisoes.jsonl, achados.jsonl, perguntas.jsonl]
mutates: false
---

# Revisar N1

1. Para hipótese localizada em snapshot já persistido, declarar os campos e
   checks em `qa_n1_field_probe.py`; pode cruzar classes sem copiar atributos.
2. Para cobertura ampla do snapshot, executar `qa_evidence_auditor.py review`.
3. Se extrator/vínculo mudou, materializar com `headless_sa_analise.py --secao ... --item ... --wait` antes de revisar.
4. Exigir adaptador de classe para confirmar geometria, faces, segmentos ou painéis.
5. Em PIL/FV/LV genérico, usar `TRILHA_N1_OBSERVADA`, não `CONFIRMAR` pleno.
6. N1 não prova a si próprio; HTML e checkbox também não.

Aceite do probe: apenas os checks declarados recebem PASS/FAIL/PENDENTE; cache
frio e aquecido têm o mesmo resultado semântico.

Aceite: cada decisão cita evidência independente ou permanece `PENDENTE`.
