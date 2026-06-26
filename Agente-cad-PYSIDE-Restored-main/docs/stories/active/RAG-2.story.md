# RAG-2 - Curadoria Observadora Read-Only

## Objetivo

Transformar a aba Curadoria em um painel visual do estado real do Cerebro RAG, sem escrever no banco, sem indexar fichas e sem validar/desvalidar itens.

## Escopo

- Mostrar a barreira de confianca: T0 quarentena, T1 validado, T2 consolidado, TX revogado.
- Mostrar metricas reais de `project_data.vision`.
- Mostrar cobertura dos stores vetoriais FAISS e da ponte `semantic_rag_kb`.
- Mostrar que `semantic_rag_kb` foi populada por regras semanticas, nao por fichas em desenvolvimento.
- Enciclopedia por classe mostra evidencias das 8 dimensoes sem inferir compreensao inexistente.
- Aprendizado mostra eventos humanos, roles e accuracy das regras em modo somente leitura.
- Pendencias transforma lacunas observadas em uma fila priorizada de validacao e harmonizacao.
- Preservar o painel administrativo legado como sub-aba.

## Fora de Escopo

- Nao indexar T0.
- Nao validar/desvalidar fichas pela Curadoria.
- Nao regravar F5/F7.
- Nao acoplar N3 a N2/N4.

## Gate

- A aba Curadoria abre sem erro.
- As sub-abas exibem contagens reais.
- Existe contagem explicita de TX/tombstones.
- Enciclopedia separa F5/N2, F7/N1, regras e tiers por classe.
- Aprendizado separa validacoes, rejeicoes e N/A sem disparar retraining.
- Pendencias alerta taxonomias nao canonicas, classes sem T1/T2 e memoria legada T0.
- Nao ha botao de escrita ou indexacao ampla.

## Validacao

- `python -m py_compile src/ui/widgets/project_manager.py`
- Testes RAG focados continuam passando.
