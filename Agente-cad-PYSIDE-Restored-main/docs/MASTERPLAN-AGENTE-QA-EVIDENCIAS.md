# Masterplan — Agente QA de Evidências (Areté)

**Status:** núcleo LAJ implementado; piloto em revisão com escrita transacional opt-in

**Nome canônico:** `arete-qa-evidencias`

**Interface primária:** chat/CLI; a UI apenas exibe os resultados
**Escopo inicial:** N1 do Structural Analyzer, por obra → pavimento → classe → item → campo/vínculo

## 0. Missão unificada do programa

Este agente não é uma iniciativa isolada. Ele integra a missão maior de consolidar cada classe estrutural como interpretação confiável, transformar as validações humanas em ground truth auditável, alimentar o RAG sem contaminação e usar esse conhecimento para evoluir os motores de forma geral.

A meta completa, por classe, é:

1. consolidar N1, N2, N3 e N4 com proveniência e veredito visual quando aplicável;
2. auditar N1 campo por campo e vínculo por vínculo;
3. corrigir causas gerais no motor, sem hardcode por item/obra/pavimento;
4. formar ground truth somente com decisões humanas/evidências confirmadas;
5. curar regras, exemplos corretos e antipadrões para o RAG;
6. integrar o RAG ao agente como memória consultiva T1/T2;
7. permitir validação controlada pelo agente, com perguntas para ambiguidades;
8. provar generalização em outros pavimentos e depois em outras obras;
9. repetir o mesmo ciclo na classe seguinte sem importar regras semânticas incompatíveis.

### 0.1 Ordem oficial das classes

| Ordem | Classe | Papel no programa |
|---|---|---|
| 1 | **LAJ — Lajes** | classe pioneira; cria o núcleo do agente, contrato de evidências e primeira base RAG curada |
| 2 | **FV — Fundos de Viga** | primeira prova de reutilização do núcleo em outra geometria e outra ficha |
| 3 | **PIL — Pilares** | expande o agente para elementos verticais, seções, continuidade e relações entre pavimentos |
| 4 | **LV — Laterais de Viga** | última classe; maior diversidade de segmentos, lados, recortes e convenções de montagem |

Essa ordem é fixa para o programa atual: **LAJ → FV → PIL → LV**. Uma classe só inicia a fase de aplicação automática depois que a anterior atingir seus gates de saída. Diagnósticos read-only da classe seguinte podem ser preparados antes, mas não podem promover ground truth nem alimentar o RAG ativo.

### 0.2 Arquitetura de reutilização

Não serão criados quatro agentes independentes. Haverá:

- um núcleo `arete-qa-evidencias`, responsável por snapshot, decisões, perguntas, auditoria, persistência append-only e integração RAG;
- um adaptador por classe, responsável por schema de campos, proveniência, evidências mínimas, relações geométricas e gates visuais;
- um RAG comum, obrigatoriamente particionado por classe, subclasse, campo, obra, pavimento, tier e proveniência;
- suites golden por classe, usadas para impedir que a evolução de uma interpretação degrade as anteriores.

O núcleo aprende **como auditar**. Os adaptadores e o RAG ensinam **o que cada campo significa**. Regras de LAJ não podem ser aplicadas a FV/PIL/LV por similaridade textual.

### 0.3 Ciclo obrigatório de uma classe

```text
baseline e tabela de proveniência
  → consolidação N1/N2/N3/N4
  → agente QA read-only
  → correção do motor + regressão
  → ground truth humano auditado
  → curadoria RAG T1/T2
  → agente QA enriquecido pelo RAG
  → aplicação controlada
  → expansão de pavimento/obra
  → gate de classe concluída
```

### 0.4 Gate de saída antes da próxima classe

Uma classe está pronta para liberar a seguinte quando:

- a tabela de proveniência de todos os campos está completa;
- o núcleo read-only audita item, campo e vínculo sem depender da UI;
- falsos positivos críticos de validação são zero no golden da classe;
- pendências e ambiguidades produzem perguntas, não preenchimentos inventados;
- o ground truth é rastreável até evidência e decisão humana;
- o RAG contém apenas T1/T2 curado e toda resposta apresenta citação;
- nenhuma informação N2/N4 vazou para N1/N3;
- o modo `apply` preserva selos humanos e rejeita snapshot desatualizado;
- a regressão da classe e das classes anteriores permanece verde;
- ao menos um pavimento adicional demonstra que a regra não é hardcoded no pioneiro.

### 0.5 Estado de partida de LAJ

LAJ 13_PAV é o primeiro corpus do programa. N2, N3 e N4 foram aprovados visualmente pelo dono, e os itens N1 foram aprovados como conjunto; a validação granular de todos os campos/vínculos ainda precisa ser consolidada. Portanto, o próximo marco não é ampliar cegamente para outra classe: é construir Q1 read-only, reproduzir a auditoria granular de LAJ, corrigir as causas encontradas e só então curar o primeiro conjunto RAG da classe.

## 1. Problema que este agente resolve

Uma ficha pode parecer boa como item e ainda conter um vínculo falso, uma cota classificada como nível, um apoio contaminado por uma viga, um contorno que invadiu um pilar ou um valor inferido sem fonte. Validar manualmente campo a campo é necessário para construir ground truth, mas não escala.

O Agente QA de Evidências será o revisor técnico conservador dessa ficha. Ele lê cada campo e cada vínculo, reúne evidências verificáveis, decide o que é seguro confirmar e **não completa por palpite**. Para todo restante, produz uma instrução de correção ou uma pergunta curta para o dono.

Ele não é um gerador, um comparador numérico simplista nem um substituto do veredito visual humano. É a camada que torna a validação de N1 auditável e repetível.

## 2. Resultado esperado

Para cada campo de cada item, o agente produz exatamente uma decisão:

| Decisão | Efeito permitido | Quando usar |
|---|---|---|
| `CONFIRMAR` | pode validar o campo/vínculo | evidência direta, coerente e sem conflito |
| `N/A_CONFIRMADO` | pode marcar não aplicável com motivo | a semântica do campo não se aplica ao item |
| `PENDENTE` | não grava validação | evidência insuficiente, inferência plausível mas não provada |
| `CORRIGIR` | abre achado; não apaga dado | divergência objetiva entre campo e fonte |
| `REVISAR_HUMANO` | gera pergunta ao dono | duas interpretações legítimas ou conflito de fontes |

`CONFIRMAR` e `N/A_CONFIRMADO` só podem ser aplicados em lote depois de o relatório ser revisado e de o operador fornecer `--apply` para aquele `run_id`. `CORRIGIR`, `PENDENTE` e `REVISAR_HUMANO` jamais são convertidos em selo por automação.

## 3. Princípios inegociáveis

1. **Evidência antes de confiança.** Um score nunca substitui geometria, texto-fonte ou veredito visual.
2. **A menor autoridade vence.** O agente pode sugerir e confirmar evidência inequívoca; não pode alterar regra de motor, N2, DXF ou selo humano.
3. **Sem validação circular.** Um campo extraído não prova a si mesmo; fonte e conclusão precisam ser independentes.
4. **Sem vazamento entre fluxos.** N2/N4 podem ser evidência comparativa, mas N3 nunca recebe dados de N2/N4. Coincidência por herança é `vazamento_gabarito`, não sucesso.
5. **RAG é consulta, não autoridade.** Somente conhecimento T1/T2, com citação, pode apoiar uma hipótese; nunca substitui o DXF/ficha da obra.
6. **Preservação humana.** Não sobrescrever, apagar ou rebaixar `is_validated`, selo azul, selo verde, campos já validados ou JSONs Fase-4. Uma possível revogação vira pergunta/achado, não mutação.
7. **Proveniência explícita.** Toda decisão referencia arquivo, tabela, item, campo, coordenada/entidade e regra usada.
8. **Falhar fechado.** Dúvida significa `PENDENTE` ou `REVISAR_HUMANO`, jamais `CONFIRMAR`.
9. **CLI primeiro.** O fluxo inteiro funciona sem dashboard; a UI somente apresenta o dossiê e aplica uma decisão previamente autorizada.

## 4. Limites de autoridade

### Pode fazer

- Ler a base real `D:/Agente-cad-PYSIDE/project_data.vision`, DXF, fichas N1/N2, recortes, HTML e relatórios Arete.
- Montar grafo item → campo → vínculo → entidade CAD → evidência visual → regra/RAG.
- Marcar `validated_fields_json`, `na_fields_json` e classes de vínculo **somente** para decisões aprovadas no relatório e no mesmo projeto/pavimento solicitado.
- Criar entradas append-only de auditoria, achados e perguntas.
- Sugerir correção de extrator, tracer, normalizador ou regra de proveniência.

### Não pode fazer

- Gerar selo azul/verde por conta própria; o selo continua consequência do contrato do Structural Analyzer.
- Editar dados N2/Fase-4, golden, notas históricas ou uma decisão humana existente.
- Usar N2/N4 como entrada de N3, nem transformar uma semelhança visual em dado de N1.
- Rodar API de visão. Para gates visuais usa somente `g2v_harness.py --backend cli` e leitura humana/agent do PNG.
- Resolver ambiguidade geométrica inventando tolerância, coordenada, nível ou vizinho.

## 5. Fontes, ordem de consulta e confiança

| Ordem | Fonte | Papel | Limite |
|---|---|---|---|
| 1 | N1 persistido: `slabs`/`beams`/`pillars`, `*_elements`, `links_json` | alvo da auditoria e estado de validação | não é prova de si próprio |
| 2 | DXF bruto + entidades/coord. | prova espacial primária | exigir entidade/coord. rastreável |
| 3 | Ficha interpretativa N1 e imagem do recorte | explica a interpretação | não vence o DXF se divergir |
| 4 | Render visual N1×N2 ou N3×N4 | detecta contorno, posição, cotagem e contaminação | não aprova sozinho |
| 5 | Ficha N2/F5 e DXF STOG | comparação independente e diagnóstico | jamais alimenta N3 |
| 6 | RAG T1/T2 com `semantic_ref` | regra de classe/estilo e exemplos aprovados | consulta somente, sempre citada |
| 7 | Notas/triagem humana | contexto e exceções | não converte nota em fato sem evidência |

Quando fontes discordarem, o agente registra a discordância. Não faz média entre coordenadas, áreas ou níveis.

### 5.1 Anel consultivo cross-classe

O adaptador audita o campo na sua classe de origem, mas consulta elementos
estruturais próximos das outras classes para confrontar a interpretação. Essa
consulta é somente leitura, traz entidade, coordenada/distância, validação e
proveniência para o dossiê; nunca copia campos de PIL/FV/LV para LAJ nem altera
o elemento consultado.

| Campo-alvo | Consulta permitida | Quando pode elevar confiança |
|---|---|---|
| nível LAJ | pilares em contato direto; vigas FV/LV próximas como contexto | ao menos dois pilares em contato convergem no mesmo nível e confirmam uma fonte LAJ já existente |
| apoio LAJ | PIL e vigas próximas | nome, face e contato geométrico convergem; proximidade isolada não basta |
| corte/contorno LAJ | FV/LV próximos | somente para excluir contaminação por viga; nunca para inventar recorte |
| vizinhança LAJ | LAJ-fonte e elementos limítrofes | a identidade/direção é confirmada sem circularidade |

O consenso externo não cria um valor novo. Ele apenas confirma ou reprova um
valor que já exista em evidência própria da classe-alvo. Se houver discordância
entre classes ou ausência de contato geométrico, a confiança diminui e o agente
formula uma pergunta com: observação, tentativas, hipóteses rejeitadas, impasse,
impacto nos vínculos dependentes e a regra geral que precisa ser ensinada.

## 6. Modelo de auditoria por campo

O agente primeiro carrega a tabela de proveniência da classe (para LAJ: `docs/PROVENIENCIA-CAMPOS-LAJ.md`). Cada campo é classificado antes de ser julgado:

| Categoria de proveniência | Tratamento QA |
|---|---|
| (a) extração geométrica direta | confirmar somente com entidade/contorno/coordenadas verificáveis |
| (b) derivado determinístico | confirmar se insumos e fórmula/relação forem reproduzíveis |
| (c) convenção humana/estilo | não abrir falso bug; consultar RAG/regra de estilo ou perguntar ao dono |
| (d) excluído/N/A | exigir motivo e fonte que prove a inaplicabilidade |

### 6.1 Tipos de evidência mínimos

| Tipo de campo | Evidência para `CONFIRMAR` |
|---|---|
| nome/classe | texto CAD ou ficha de origem identificado no recorte |
| dimensão | duas coordenadas ou entidade de cota ligadas à mesma parede/segmento |
| contorno/área | polígono e segmentos; área total **e** coincidência de geometria/coord. |
| nível | rótulo semanticamente nível, camada/contexto confiável ou regra derivada citada; números de painel nunca bastam |
| vizinhança | laje-fonte, direção ortogonal, distância/contato e valor semanticamente associado à fonte |
| apoio/pilar/viga | entidade nomeada, face/contato geométrico e ausência de invasão/contaminação |
| visão de corte | geometria real de corte; caso ausente, `N/A_CONFIRMADO` apenas com evidência |
| cotagem/recorte complexo | imagem/DXF legível que permita fabricar/cortar; cotas diagonais só se a regra de classe permitir |

### 6.2 Regras especiais de integridade

- Um valor numérico perto de uma laje não pode ser nível apenas por parecer decimal. Deve ter proveniência semântica.
- Para área, `comprimento × largura` é apenas checagem auxiliar. O comparador deve avaliar polígono, furos, degraus, recortes, coordenadas e orientação.
- Um vínculo de vizinhança deve referenciar a entidade-fonte e a direção; valor sem fonte é pendente.
- Um suporte que invade uma viga, está distante da face ou tem nome vazio é `CORRIGIR`/`PENDENTE`, nunca confirmado.
- Antes de confirmar qualquer campo derivado, o agente verifica que seus insumos não são provenientes de N2/N4 quando o alvo é N1/N3.

## 7. Fluxo CLI por execução

```text
seleção explícita de obra/pav/classe/itens
  → snapshot somente leitura do N1 e do DXF
  → carrega proveniência e regras da classe
  → coleta evidências (DXF, links, fichas, PNG, RAG T1/T2)
  → avalia campo/vínculo individualmente
  → detecta contradições e dependências
  → emite decisões + achados + perguntas
  → revisão humana do relatório
  → aplicação opcional e restrita das decisões aprovadas
  → reabertura/verificação de persistência
```

Comandos-alvo (a implementar em fases):

```powershell
# Não altera a base; produz dossiê e perguntas.
python scripts/arete/qa_evidence_auditor.py audit `
  --obra Obra_TREINO_1 --pav 13_PAV --classe LAJ --item L312 L319

# Reexecuta somente pendências após uma correção do motor.
python scripts/arete/qa_evidence_auditor.py audit --run <run_id> --only pending

# Mostra perguntas que realmente exigem decisão humana.
python scripts/arete/qa_evidence_auditor.py questions --run <run_id>

# Só após revisão explícita: aplica CONFIRMAR/N/A aprovados deste run.
python scripts/arete/qa_evidence_auditor.py apply --run <run_id> --decision-file aprovadas.json
```

O comando `apply` deve exigir `--project-id`, verificar que ele coincide com o snapshot e rejeitar qualquer item que tenha sido alterado após a auditoria.

## 8. Dossiê e contratos de dados

Cada execução escreve, sem editar uma anterior:

```text
scripts/arete/relatorios/qa_evidencias/<run_id>/
  manifesto.json                 # filtros, hashes, versões, fontes
  decisoes.jsonl                 # uma linha por campo/vínculo
  achados.jsonl                  # bugs/regras a corrigir
  perguntas.jsonl                # perguntas humanas não ambíguas
  resumo.md                      # leitura humana e próximos passos
  evidencias/                    # PNGs, SVGs, recortes e referências
```

Schema mínimo de `decisoes.jsonl`:

```json
{
  "decision_id": "qaev-...",
  "run_id": "...",
  "project_id": "...",
  "obra": "...",
  "pavimento": "...",
  "classe": "LAJ",
  "item": "L318",
  "field_id": "laje_vizinhas_niveis",
  "slot_id": "neighbor_south",
  "provenance_category": "a",
  "decision": "CORRIGIR",
  "confidence": "high",
  "reason": "402.5 é cota de painel, não nível da laje-fonte",
  "evidence": [{"kind": "dxf_text", "source": "...", "entity_id": "...", "coord": [0,0]}],
  "rag_citations": [],
  "requires_human": false,
  "snapshot_hash": "..."
}
```

Uma pergunta contém contexto suficiente para resposta curta: fato observado, alternativas permitidas, evidências e consequência da resposta. Exemplo: “L318: o rótulo 852.19 corresponde ao nível da laje ou ao corte? O campo atual é 822.19; não validei nenhum dos dois.”

## 9. Hierarquia de decisões e selo

O agente não grava `is_validated` diretamente.

1. Ele decide campo/vínculo e gera relatório.
2. O operador aprova o subconjunto inequívoco.
3. A aplicação marca só os campos/classes de vínculo correspondentes.
4. O Structural Analyzer calcula 100% e, pelo contrato existente, aciona conjuntamente selo azul + verde.
5. Um item com qualquer `PENDENTE`, `CORRIGIR` ou `REVISAR_HUMANO` não recebe selo por esse agente.

Assim, o selo continua significando “campos necessários confirmados”, não “o agente encontrou uma maioria de indícios”.

## 10. Integração com RAG futuro

O RAG entra após o leitor local, em modo somente consulta:

- Filtro obrigatório por classe, subclasse, obra/pavimento e tier permitido.
- Toda sugestão traz `semantic_ref`, tier, regra e exemplo de origem.
- T0 é contexto de investigação; não pode justificar `CONFIRMAR`.
- T1/T2 podem explicar categoria (c), exceção de obra e padrão de cotagem, mas não anulam geometria local.
- Achado confirmado por humano pode virar candidato de curadoria. A promoção ao RAG global é outro fluxo, com revogação humana e sem propagação automática.

Integrações previstas: `semantic_rag_kb`, `domain_knowledge`, `POLITICA-CONFIANCA-RAG.md`, `RAG-REVOGACAO-HUMANA-SPEC.md` e `ARETE-MCP-RAG-HARMONIZACAO.md`.

## 11. Fases de implantação

| Fase | Entrega | Escrita na base | Critério de saída |
|---|---|---|---|
| Q0 — contrato | este masterplan, schema, taxonomia de decisões e casos de teste | não | regras aprovadas |
| Q1 — leitor N1 | CLI read-only; dossiê campo/vínculo com DXF e fichas | não | LAJ 13_PAV reproduz auditoria manual sem falso selo |
| Q2 — evidência visual | integra recorte/PNG e g2v CLI quando exigido | não | achados geométricos explicáveis com imagem |
| Q3 — perguntas e achados | fila de dúvidas, triagem e instrução de correção | não | uma dúvida por decisão, sem perguntas redundantes |
| Q4 — aplicação controlada | `apply` com snapshot, allowlist e append-only | só decisões aprovadas | reabrir SA preserva e sela corretamente |
| Q5 — RAG consultivo | retrieval T1/T2 citado e isolado por obra | não | RAG melhora cobertura sem aumentar falso positivo |
| Q6 — expansão | LAJ/FV/PIL/LV e outros pavimentos/obras | conforme Q4 | regressão e proveniência por classe aprovadas |

Q6 respeita a ordem oficial: primeiro expansão LAJ, depois adaptação FV, depois PIL e por último LV. Cada adaptação reutiliza o núcleo e adiciona somente o plugin semântico/geométrico específico da classe.

## 11.1 Roadmap macro do programa

| Etapa | Classe | Entrega dominante | Resultado |
|---|---|---|---|
| P1 | LAJ | consolidar ground truth + Q1/Q2 do agente | auditor read-only confiável para lajes |
| P2 | LAJ | RAG T1/T2 + aplicação controlada | agente de LAJ assistido por memória curada |
| P3 | LAJ | outros pavimentos/obra | prova de generalização e golden pioneiro |
| P4 | FV | adaptador FV + consolidação + RAG FV | segunda classe prova a reutilização do núcleo |
| P5 | PIL | adaptador PIL + consolidação + RAG PIL | relações verticais e seções auditáveis |
| P6 | LV | adaptador LV + consolidação + RAG LV | cobertura das quatro classes estruturais |
| P7 | Todas | auditoria cruzada e operação contínua | agente/RAG multiclasses sem contaminação semântica |

## 12. Piloto: LAJ, 13_PAV

O piloto deve começar com os casos que mostraram por que o agente é necessário:

- números de painel tratados indevidamente como níveis de vizinhos;
- contornos que invadem pilar/viga ou não reproduzem pequenos degraus;
- apoio distante/sem nome versus apoio de face verificável;
- nível inferido que conflita com texto/ficha;
- cotagem de recortes complexos cuja fabricação não é rastreável.

Para cada caso, o resultado correto pode ser `CORRIGIR` ou `REVISAR_HUMANO`; o objetivo não é maximizar campos azuis, e sim maximizar decisões justificadas.

## 13. Critérios de aceite e testes

- Dado um número de painel sem marcador semântico, o agente não o confirma como nível.
- Dado um contorno com mesma largura/altura mas degrau diferente, o agente não o confirma por área/bounding box.
- Dado vínculo de pilar que invade viga, o agente abre achado e não valida suporte.
- Dado campo (d) sem entidade aplicável, o agente exige razão N/A rastreável.
- Dado RAG T0, o agente não confirma campo com ele.
- Dado snapshot alterado entre `audit` e `apply`, a aplicação falha fechada.
- Dado selo humano existente, nenhuma rotina o reescreve ou remove.
- Cada decisão possui ao menos uma evidência navegável; decisões geométricas possuem coordenada/entidade ou artefato visual.

## 14. Riscos e barreiras

| Risco | Barreira |
|---|---|
| alucinação do agente | fontes citadas, estados fechados e revisão antes de apply |
| contaminar N1 com N2/N4 | separação de fluxo e detector de proveniência/vazamento |
| confirmar campo de convenção humana | tabela a/b/c/d e RAG somente consultivo |
| desfazer selo humano | read-only por padrão; apply allowlist e snapshot |
| excesso de perguntas | agrupar por causa-raiz e perguntar só quando altera a decisão |
| regressão entre obras | regras sem hardcode; piloto + testes de propriedades + amostras multiobra |

## 15. Próxima ação concreta

Implementar Q1 como CLI **read-only** para LAJ 13_PAV, com seleção de um ou mais itens. Ele deve reproduzir o relatório da auditoria atual, incluindo a detecção de níveis-vizinhos contaminados, mas ainda sem gravar validação. Só depois de uma rodada humana de comparação do dossiê com o Structural Analyzer começa Q2/Q4.
