---
task: review-n1
agent: aegis
inputs: [scope.json, evidence-index.json]
outputs: [decisoes.jsonl, achados.jsonl, perguntas.jsonl]
mutates: false
scripts:
  - scripts/arete/qa_n1_field_probe.py
  - scripts/arete/qa_profile_probe.py
  - scripts/arete/qa_evidence_auditor.py
  - scripts/arete/headless_sa_analise.py
---

# Revisar N1

1. Para hipótese localizada em snapshot já persistido, declarar os campos e
   checks em `qa_n1_field_probe.py`; pode cruzar classes sem copiar atributos.
2. Para hipótese modelada no perfil da classe, usar `qa_profile_probe.py` com
   `--project-id` (ou `--use-profile-sample` consciente).
3. Para cobertura ampla do snapshot, executar `qa_evidence_auditor.py review`.
4. Se extrator/vínculo mudou, materializar com `headless_sa_analise.py --secao ... --item ... --wait` antes de revisar.
5. Exigir adaptador de classe para confirmar geometria, faces, segmentos ou painéis.
6. Em **FV/LV** genérico, usar `TRILHA_N1_OBSERVADA` ou `PENDENTE`, nunca `CONFIRMAR` pleno.
7. Em **LAJ/PIL**, `CONFIRMAR` só via adaptador (`LajEvidenceAuditor` / `PilEvidenceAuditor`).
8. N1 não prova a si próprio; HTML e checkbox também não.
9. Consultar `data/authority_matrix.json` se houver dúvida de selo.

## Aceite positivo

- Cada decisão cita evidência independente ou permanece `PENDENTE`.
- Probe: apenas os checks declarados recebem PASS/FAIL/PENDENTE; cache frio e
  aquecido têm o mesmo resultado semântico.
- Escopo inequívoco (`project_id`).

## Aceite negativo (o que PASS **não** autoriza)

- PASS de probe/profile **não** aprova item, ficha, pavimento ou classe.
- Review genérico FV/LV **não** grava `apply` nem selo laranja.
- Cobertura PIL (`qa_pil_coverage`) **não** sozinha libera apply.
- Score de sessão / arquivo aberto / HTML **não** fecham interpretação.
