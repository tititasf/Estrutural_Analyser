# Permitido vs proibido — ciclo treino × validação × juiz 🟠

SoT completa: `docs/QA-CICLO-EFICIENCIA-E-AUTORIDADE.md` + `docs/CONVENCAO-SELOS-VALIDACAO.md`.

## Juiz do agente = 🟠 laranja (`qa_agente`)

- [ ] Agente **é** o juiz de campo com prova (adaptador + evidência) → origem `qa_agente`
- [ ] 🟠 item só com **100%** campos obrigatórios `qa_agente` (isolado; não mistura azul/rosa)
- [ ] Visual G2-V lido e registrado → decide **ajuste de motor** ou PASS; não inventa 🔵/🌸
- [ ] LLM sem checklist/SVG/adaptador **não** grava 🟠

## Treino

| ✅ | ❌ |
|----|----|
| Item real como caso de treino | Hardcode `if item == …` |
| Fórmula geral + teste +/− | Score cosmético de classe |
| Teach reutilizável | RAG promote sem humano |

## Validação / visual

| ✅ | ❌ |
|----|----|
| CONFIRMAR com prova CAD/contrato | CONFIRMAR por “parece igual” |
| G2-V CLI + pack veredito | HTML genérico como prova |
| N2/N4 comparador | N2/N4 alimentando N1/N3 |

## Meta-eficiência

| ✅ | ❌ |
|----|----|
| `record-cycle` + `cycle_efficiency` no RESUME | Reescrever motor sem regressão |
| Otimizar rota/probes/tokens | Auto-selo Arete porque nota A de eficiência |

```text
python scripts/arete/qa_loop_executor.py record-cycle --run RUN --phase train|validate|visual|fix|regen --result PASS
```
