# Medição independente do QA SA

O avaliador `scripts/arete/qa_sa_benchmark.py` mede decisões por critério, separando PIL, LAJ, FV, LV Para e LV Passa. Confiança autodeclarada do modelo não entra como acurácia ou probabilidade calibrada. Não altera SA e não homologa classes.

O corpus deve ser reservado antes da avaliação. Casos usados para ajustar o prompt, incluindo os ensaios P1/L301/V301 desta sessão, pertencem ao desenvolvimento; não podem servir como prova de generalização. Guardar a interpretação-base e as provas originais com hashes. Cada rótulo pertence a uma versão específica de um item/unidade/critério. Prova repetida não adjudica automaticamente outro segmento.

Formato de entrada do corpus:

```json
{
  "schema": "cad.qa.sa.reference/v1",
  "split": "held_out",
  "cases": [{
    "case_id": "identidade-estavel",
    "classe": "FV",
    "behavior": "para",
    "unit_id": "S1",
    "criterion": "geometry",
    "source_sha256": "HASH_SHA256_DA_INTERPRETACAO_BASE",
    "reference_correct": false,
    "reference_origin": "human_adjudication",
    "human_label_verified": true,
    "reviewer": "responsavel-pela-adjudicacao",
    "reviewed_at": "instante-da-adjudicacao",
    "method": "metodo-e-regra-utilizados",
    "proofs": [{"path": "referencias/cad-original.dxf", "sha256": "HASH_SHA256_DA_PROVA"}]
  }]
}
```

O exemplo é apenas schema; não representa rótulo real. `independent_cad_measurement` também é origem aceita para critérios objetivamente medidos, com responsável, método, data e provas originais. Não rotular um critério semântico incerto como verdadeiro por proximidade ou por opinião do modelo. Enquanto faltar adjudicação binária, o caso não constitui referência para este avaliador.

Previsões têm schema `cad.qa.sa.predictions/v1` e uma lista `rows`. Cada linha repete `case_id`, `classe`, `behavior`, `unit_id`, `criterion`, `source_sha256`, e acrescenta `round_id` e `assessment` (`pass`, `fail`, `inconclusive`, `technical_failure`). Os hashes e identidades precisam coincidir exatamente. Duplicatas e previsões sem referência são recusadas; uma previsão ausente conta como falha técnica, sem reduzir o denominador.

Executar pelo Python 3.12 do projeto:

```text
python -m scripts.arete.qa_sa_benchmark --corpus referencias/corpus.json --predictions resultados/previsoes.json --output resultados/medicao-nova.json
```

A saída registra matrizes de confusão, falsas aprovações, cobertura de decisão, acurácia incluindo incertezas/falhas técnicas e acurácia seletiva explicitamente nomeada. Informa classes ausentes, número de positivos/negativos e intervalos Wilson. Critérios do mesmo item são correlacionados: esses intervalos não substituem amostragem por item/obra nem permitem generalizar.

Hashes verificam integridade, não independência ou verdade dos rótulos. A auditoria do corpus deve conferir seleção anterior ao teste, origem no CAD original, revisão responsável, balanceamento e cobertura de famílias. Não usar referências obtidas do próprio overlay SA ou do candidato como verdade independente. Até existir esse corpus, probabilidades calibradas e homologação permanecem indisponíveis.
