# Training Pipelines Spec - ARETE, RAG e Humano no Loop

## Objetivo
Definir os ciclos de treino que evoluem uma classe estrutural ate ARETE sem contaminar o RAG e sem vazar gabarito.

Esta spec cobre:
- CROP: aprender a recortar melhor.
- A: N2 -> N4, engenharia reversa e robo reverso.
- B: N2 <-> N1, interpretacao do Structural Analyzer.
- C: N1 -> N3, producao final sem gabarito.
- Notas humanas: atencoes e decisoes auditaveis.

## Regra central
RAG nao e o treinador. RAG e memoria consultavel.

Os loopers produzem eventos, scores, exemplos e evidencias. O RAG guarda apenas o que passou pela barreira de confianca:
- T0: hipotese/quarentena.
- T1: validado por humano.
- T2: consolidado em mais de uma obra.
- TX: desvalidado/revogado.

## Trava anti-validacao sintetica
Nenhum fluxo CLI, script, looper, agente, batch, headless ou avaliador sintetico pode gravar
algo como validacao humana.

Permitido para CLI/looper:
- gerar candidato;
- medir score;
- comparar N3/N4;
- registrar `machine_candidate`;
- registrar evento em `quarantine`;
- sugerir correcao para o humano revisar.

Proibido para CLI/looper:
- marcar T1/T2;
- setar `status='aprovado'` como fonte de verdade;
- setar `is_validated=1`;
- chamar indexacao global;
- tombstonar/desvalidar como se fosse humano.

Promocao efetiva exige origem explicita de UI humana:

```text
validation_origin = "human_ui"
```

Qualquer origem como `cli`, `script`, `looper`, `agent`, `auto`, `batch`, `headless`,
`synthetic` ou origem ausente deve permanecer T0/quarentena, mesmo se o payload vier com
texto "aprovado".

## Ciclo CROP - aprender a recortar
Professor: recorte aprovado por humano.

Treina:
- detector de janela/bbox/poligono;
- margem por classe;
- layers/cores/textos/blocos uteis;
- falsos positivos frequentes por classe e pavimento.

Gate humano:
- o recorte contem o item inteiro;
- o recorte nao mistura itens vizinhos;
- a classe/contexto do recorte esta correto.

Nao valida:
- campos F5/N2;
- equivalencia N2/N4;
- desenho N4.

Persistencia:
- `crop_learning_events`
- exemplos visuais CROP-T1

## Ciclo A - N2 -> N4
Professor/juiz: F5/N2 validado + visual STOG humano.

Treina:
- `motor_reverso_{classe}.py`;
- extracao de campos;
- leitura de layers/historicos/cores;
- `gerar_{classe}_dxf_stog.py`;
- equivalencia visual N4 contra o desenho humano.

Gate humano:
- campos F5/N2 corretos;
- N4 visualmente equivalente ao STOG humano;
- score Comparison Engine acima do gate da classe.

Saida:
- N4 validado pode virar juiz externo para o Ciclo C.

## Ciclo B - N2 <-> N1
Professor externo: N2/F5 validado.

Treina:
- interpretacao N1/F7 do Structural Analyzer;
- mapeamento de vocabulario N1 <-> N2;
- conversao N1 -> ficha de robo;
- `transformation_rules` e calibradores.

Gate humano:
- campos do N1 convergem para campos do N2;
- divergencias recebem aceite, rejeicao, N/A ou nota humana;
- generalizacao so promove depois de mais de uma obra.

Proibido:
- sobrescrever dado humano;
- usar N2 como input do N3.

## Ciclo C - N1 -> N3
Juiz externo: N4 validado.

Treina:
- conversor N1 -> N3;
- populacao dos dados dos robos;
- geracao DXF N3 por classe;
- regressao visual N3 vs N4.

Gate humano:
- N3 se aproxima de N4 visual/semanticamente;
- nao ha vazamento de N2/N4 para o N3;
- discrepancias viram `training_events`.

Proibido:
- copiar campos de N2/N4 para gerar N3;
- considerar match valido se houve vazamento.

## Notas humanas
Notas humanas sao sinais de atencao, nao verdades globais automaticas.

Usos corretos:
- marcar duvida em item/campo/recorte;
- explicar divergencia;
- registrar regra candidata;
- orientar o proximo prompt CLI ou proxima iteracao do looper.

Promocao:
- nota -> pendencia;
- pendencia validada -> regra candidata;
- regra confirmada em T1/T2 -> `domain_knowledge` / `semantic_rag_kb`.

## Processo para classe nova
1. Registrar classe no `classe_registry`.
2. Definir partes/subpartes e campos canônicos.
3. Criar recorte CROP com exemplos T1.
4. Criar `motor_reverso_{classe}.py`.
5. Criar `gerar_{classe}_dxf_stog.py`.
6. Rodar Ciclo A ate N4 reproduzir N2/STOG validado.
7. Rodar Ciclo B ate N1/F7 convergir para N2/F5.
8. Rodar Ciclo C ate N3 se aproximar de N4 sem vazamento.
9. Promover regra apenas com evidencia em mais de uma obra.

## Processo via chat/CLI
O chat/CLI deve operar em iteracoes curtas:

1. Selecionar classe, obra, pavimento e item.
2. Rodar o looper correspondente em modo auditavel.
3. Mostrar diff/score/artefatos.
4. Mostrar decisao recomendada, mas nao aplicar como validacao humana.
5. Receber decisao humana real pela UI ou por comando que exija `validation_origin="human_ui"`.
6. Gravar evento com proveniencia completa.
7. Atualizar Curadoria e Comparison Engine.
8. Repetir ate bater gate da classe.

## Aba Curadoria - Pipelines de Treino
Esta aba deve ser read-only:
- mostra os ciclos;
- mostra docs/scripts encontrados;
- mostra contagens de eventos;
- mostra lacunas por classe.

Ela nao executa treino, nao indexa dados e nao promove regra.
