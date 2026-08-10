# Checklist operacional anti-super-selo (Arete / QA Global)

Usar em **toda** sessão que confirme campos ou prepare apply.

## Autoridade

- [ ] Consultei `data/authority_matrix.json` / `qa_authority_matrix.py`.
- [ ] Sei o que a classe **ainda não** cobre (PIL L/U/circular; FV 1 segmento ≠ viga; LV 1 contrato ≠ ficha).
- [ ] PASS de probe/profile/smoke **não** virou “item aprovado”.

## Prova

- [ ] Cada `CONFIRMAR` cita adaptador + evidência independente (geom/contrato), não HTML.
- [ ] HTML/checkbox tratados como apresentação (banner visível na ficha).
- [ ] G2 numérico sozinho **não** fechou gate visual.
- [ ] Se gate visual exigido: `g2v_harness --backend cli` + PNG/SVG **lidos** + veredito registrado.

## Escopo

- [ ] `--project-id` inequívoco (não adivinhar obra/pav).
- [ ] Itens/classe/nível/variante explícitos no dossiê.

## Apply / selo

- [ ] Apply só com comando explícito + snapshot íntegro.
- [ ] Não misturei `qa_agente` com “Arete ok / painel coerente”.
- [ ] FV/LV: não selei a viga inteira porque um segmento/contrato passou.

## Treino

- [ ] Achados classificados e, se recorrentes, ingeridos em `qa_error_memory`.
- [ ] RAG só materializado; promoção humana se T1/T2.
- [ ] Zero hardcode de item/obra/pav no motor.

## Handoff

- [ ] Paths absolutos do dossiê, `session_metrics`, RESUME e (se houver) quadro no stdout.
- [ ] Próxima ação concreta (não só “PENDENTE”).
