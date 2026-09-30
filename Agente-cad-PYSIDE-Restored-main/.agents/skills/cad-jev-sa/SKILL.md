---
name: cad-jev-sa
description: Use Jev as an optional, evidence-based second reading for ambiguous SA/N1 interpretations of structural DXF/SVG in PIL, LV, FV or LAJ. Apply during CAD QA, source-candidate selection and cross-checks; not for N2/N3/N4 generation or automatic N1 writes.
---

# Jev como segunda leitura do SA

Use esta skill quando uma dúvida **localizada** de interpretação N1 possa se beneficiar de um julgamento semântico adicional. Leia primeiro `CLAUDE.md`, `docs/LOOPING-CANONICO.md` §1 (Eixo B), `docs/SA-ANALISE/JEV-SEGUNDA-LEITURA-OPCIONAL.md` e o manual em `docs/SA-ANALISE/CLASSES/{PIL,LV,FV,LAJ}.md` da classe envolvida. Esses documentos governam o fluxo; esta skill facilita sua aplicação. A skill oficial `typesafe-ai` orienta a API. Antes de mudar a integração, consulte apenas as páginas pertinentes do índice vivo `https://docs.typesafe.ai/llms.txt`, em especial state, primitive escolhida, confidence e Python SDK.

## Decidir se a consulta vale

- Comece pelo comportamento que a revisão precisa decidir: qual candidato da fonte pertence a este campo, face, célula, aresta ou segmento? Quando a medida ou um vínculo topológico exato já resolvem o caso, use código/CAD e pare.
- Mantenha DXF original, geometria e cálculo determinístico como fonte. O SA produz N1; Jev acrescenta opinião consultiva. N2/N4 só podem servir de comparação externa, nunca como evidência enviada para inferir N1.
- Considere `Choice` para selecionar entre candidatos reais, com `INSUFFICIENT`; `Noul` para uma condição local sim/não; `Score` para uma dimensão ordenada que tenha níveis definidos. A CLI atual implementa **apenas Choice**. Não simule Noul/Score por rótulos Choice sem motivo explícito; se outro primitivo for útil, adapte a ferramenta com validação própria.

## Preparar uma pergunta que possa ser auditada

1. Fixe projeto, pavimento, classe, item, campo e SHA-256 do **DXF fonte**; confirme que o snapshot N1 corresponde à mesma execução/fonte. Formule uma pergunta pequena antes de coletar dados.
2. Recupere do DXF um recorte estruturado com candidatos e a relação relevante: texto exato, handle, layer, coordenadas, contorno/interseção, transformações e vizinhança. Use SVG **da fonte** apenas como apoio experimental; para veredito visual, leia PNG full-layer. Não envie DXF inteiro nem JSON Fase-4. Se crescer demais, divida por unidade sem perder contexto de borda.
3. Descreva opções que se distingam por evidência, inclusive a possibilidade de evidência insuficiente. Verifique cobertura dos candidatos: Jev não pode selecionar um valor omitido. Mantenha `baseline_sa`, gabarito, parecer QA e resposta esperada fora do `evidence` enviado ao modelo. Não transforme a hipótese SA em conclusão dentro da pergunta.
4. No helper atual, monte pelo menos um controle com evidência relevante removida, sem resposta esperada no estado Jev. Valide o JSON localmente antes de chamar a API. Só execute a consulta se ela puder mudar a triagem ou revelar evidência faltante.

## Executar e interpretar

Na raiz do repo, com Python 3.12, adapte `scripts/arete/examples/jev_sa_second_read_l410.json` e rode:

```powershell
..\.venv\Scripts\python.exe scripts/arete/jev_sa_second_read.py --request <pacote.json>
..\.venv\Scripts\python.exe scripts/arete/jev_sa_second_read.py --request <pacote.json> --execute --output <novo-relatorio.json>
```

O primeiro comando só valida. O segundo usa `TYPESAFE_API_KEY` local e grava um sidecar novo; não sobrescreva rodadas. Verifique resposta completa, controle, identidade, hash, latência e tokens. `confidence` mede concentração da distribuição de opções; não prova correção física. Discordância, abstenção e falha de serviço vão para revisão, sem preencher N1 automaticamente. Separe falta de candidato/evidência, erro de modelo, erro de extração e falha de API. Confronte com geometria e PNG; uma convenção indecidível pelo desenho vira ficha visual de dúvida conforme `CLAUDE.md` regra 5d.

Para o QA canônico, `qa_evidence_auditor.py review` aceita
`--jev-request <pacote.json> --jev-source-dxf <DXF_Fase-1> [--jev-execute]`.
O pacote precisa de `use_context=QA_B1|QA_B2|QA_B3` e
`qa_snapshot_sha256` correspondente ao item no `manifesto.json` da rodada.
`SA_POST_EXTRACT` identifica a mesma consulta feita após o motor SA, via helper
standalone. `companion_questions` suporta até três perguntas independentes
`noul`/`score`; `presence_question_id` aponta para um Noul de presença. A
divergência entre presença e Choice é registrada como
`CONTRADICTORY_SIGNALS`. O Score Jev descreve só a dimensão declarada e não
altera o score QA canônico. Veja o ensaio L410 e limites no manual.

Por classe: PIL exige face/contato real; LV exige célula A/B × PARA/PASSA da própria ocorrência; FV exige prova **local por segmento**; LAJ exige região, espessura, marcador de nível e apoio por aresta. Os critérios completos permanecem nos manuais. Registre em relatório a hipótese SA, evidência CAD, julgamento Jev e controle, revisão PNG agentica independente e utilidade incremental. Para qualquer fix no SA, siga o microciclo e regressão do loop canônico. Respostas Jev não são rótulos de treino; corpus futuro usa consenso agentico fonte+PNG ou regra determinística, com proveniência. Caso indeterminado permanece indeterminado.
