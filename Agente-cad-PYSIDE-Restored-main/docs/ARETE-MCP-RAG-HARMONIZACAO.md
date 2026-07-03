---
title: "Arete, MCP e RAG - Contrato de Harmonizacao"
date: 2026-07-02
status: proposed-canonical
owners: [cad-analyzer, data-rag, arete]
scope: architecture
activation: forbidden-until-explicit-owner-signal
---

# Arete, MCP e RAG - Contrato de Harmonizacao

## 1. Finalidade

Este documento define como o ciclo de qualidade Arete, o barramento MCP, o banco
SQLite e o segundo cerebro RAG devem se conectar sem duplicar autoridade nem
promover dados em desenvolvimento como verdade.

Ele e uma camada de alinhamento. Nao substitui os procedimentos e politicas
canonicos listados na secao 3.

Criar ou atualizar este documento NAO autoriza:

- ingerir fichas, logs, HTML ou SVG em indice produtivo;
- iniciar daemon de active learning;
- promover eventos T0 para T1/T2;
- registrar o servidor MCP em agentes;
- alterar extratores, geradores ou regras de producao.

Qualquer ativacao exige sinal explicito do dono e os gates da secao 12.

### 1.1 Modo de operacao atual: nao e multiagente

Hoje nao existe orquestracao multiagente. O que existe e human-in-the-CLI: o
dono abre e opera varias sessoes de IA em paralelo (Claude Code em uma ou mais
janelas, um agente dedicado a RAG, etc.), cada uma fazendo uma parte do
trabalho, e e o proprio dono quem le a saida de uma sessao e cola o contexto
relevante na outra. Nao ha coordenacao automatica entre sessoes, nao ha
protocolo de mensagem agente-a-agente, e nenhuma sessao age sem o dono
inspecionar e decidir o proximo passo entre uma e outra.

Isso importa para a leitura deste documento: qualquer trecho que mencione
"varios agentes" ou "sessoes concorrentes" (ex.: gatilho da Fase 3, secao 12)
descreve um cenario futuro, ainda nao desenhado, nao o estado atual. Trabalho
feito hoje por multiplas sessoes manuais nao conta como esse gatilho — o
gatilho e sobre agentes operando concorrentemente SEM relay manual do dono no
meio.

O desenho de um sistema multiagente real (papeis, protocolo de coordenacao,
graus de autonomia por agente) e trabalho posterior, deliberadamente adiado:
so faz sentido dividir funcoes e criar agentes dedicados depois que Arete, MCP
e RAG estiverem consolidados, funcionando e validados como estao descritos
neste documento. Decisao de arquitetura tomada hoje presumindo concorrencia
multiagente ja desenhada contamina o raciocinio com uma complexidade que ainda
nao existe e cujo desenho nem comecou — evitar.

## 2. Decisao central

Arete, MCP e RAG possuem responsabilidades diferentes:

| Componente | Responsabilidade | Nao deve fazer |
|---|---|---|
| Arete | Medir, diagnosticar, corrigir e reverificar N1/N2/N3/N4 | Declarar regra global sozinho |
| JSONL Arete | Registrar eventos/achados auditaveis do ciclo | Servir diretamente como verdade vetorial |
| SQLite | Persistir fichas, eventos, regras, aprovacoes e projecoes | Confundir edicao com validacao |
| MCP | Expor contratos seguros para agentes/UI e coordenar escritas | Ser nova fonte de verdade ou promover sozinho |
| RAG | Recuperar regras e exemplos com proveniencia e tier | Treinar motor ou decidir validade |
| Motores/robos | Interpretar, extrair e gerar artefatos CAD | Consumir vetor como valor final sem gate |

Regra resumida:

```text
Arete produz evidencia e mede qualidade.
MCP transporta e governa operacoes.
SQLite preserva estado e proveniencia.
RAG recupera conhecimento ja autorizado.
Motores mudam apenas por regra/configuracao/codigo testado.
```

## 3. Hierarquia documental

1. Definicao de qualidade e nomenclatura canonica G0-G6:
   `MASTERPLAN-ARETE-QUALITY-GATES.md`.
2. Procedimento operacional atual:
   `ARETE-LOOP-PROCEDIMENTO-GERAL.md`.
3. Captura e ciclo de achados:
   `ARETE-TRIAGEM-ERROS.md`.
4. Leitura HTML/SVG e QA:
   `ARETE-PLAYWRIGHT-QA-VISUAL.md`.
5. Infra de treino, principios e gates cross-obra:
   `MASTERPLAN-LOOP-TREINO-MOTOR.md`.
6. Confianca e tiers do RAG:
   `POLITICA-CONFIANCA-RAG.md`.
7. Desvalidacao e tombstones:
   `RAG-REVOGACAO-HUMANA-SPEC.md`.
8. Contrato MCP em preparacao:
   `D:/Agente-cad-PYSIDE/docs/MCP-ACTIVE-LEARNING-SPEC.md`.
9. Este documento:
   traduz os artefatos acima para uma unica arquitetura de integracao.

Em conflito:

- o Quality Gates define o que significa PASS e a nomenclatura G0-G6;
- o procedimento Arete define como gerar, diagnosticar, corrigir e reverificar;
- a Politica de Confianca vence sobre qualquer tentativa de indexacao;
- validacao ou revogacao humana vence sobre diagnostico automatico;
- N2 validado e professor de dados, mas N4 so e referencia visual apos seu gate.

## 4. Gates canonicos do Arete

Nao reduzir Arete a uma unica comparacao N2-N4. A ficha HTML apresenta quatro
evidencias, mas cada relacao mede uma responsabilidade diferente. Os nomes e a
ordem abaixo sao os definidos em `MASTERPLAN-ARETE-QUALITY-GATES.md`; este
documento nao cria uma taxonomia paralela.

### Trilho CROP - pre-condicao separada

```text
recorte automatico -> recorte humano aprovado
```

Treina detector, margem e perfil de recorte por classe. Aprovar o recorte nao
valida F5/N2 nem N4. CROP nao recebe numero G0-G6 porque possui ciclo e
governanca proprios.

### G0 - Sanidade do gabarito

Confirma que N2, recorte, classe, parte e identificadores sao coerentes antes de
qualquer comparacao. G0 falho bloqueia G1/G2.

### G1 - Round-trip da ficha

```text
N2 -> gerador N4 -> reextracao N2' -> diff N2 x N2'
```

Prova que os dados relevantes sobrevivem ao ciclo de geracao e reextracao.

### G2 - Paridade canonica N4 x recorte N2

```text
N2 validado -> gerador da classe -> N4 -> comparacao canonica por parte
```

Mede o desenho, nao apenas entidades DXF brutas. Antes de G1/G2 PASS, N4 e
candidato e pode conter erro de geometria, cotagem, texto, layer ou estilo.

### G3 - UI e persistencia

Gate transversal da app real: botoes, validacoes, persistencia apos restart e
protecao dos artefatos humanos.

### G4 - Convergencia de conversao N1 x N2

```text
Structural Analyzer puro -> N1/F7 -> conversao -> comparacao com N2/F5
```

Mede se o SA compreendeu o estrutural limpo. N2 nao pode ser copiado para N1.

### G5 - Paridade final N3 x N4

```text
N1 -> ficha de robo -> N3 <-> N4 ja validado
```

Mede se a rota produtiva reproduz o resultado esperado sem vazamento de N2/N4.
N3 nunca recebe campos do gabarito. G5 so possui valor depois de N4 passar
G1/G2 e a conversao N1 passar G4.

### G6 - Golden set e regressao

```text
fix candidato -> classe atual -> obras certificadas -> zero regressao
```

Um acerto em uma obra nao e default global. A promocao global exige pelo menos
duas obras e preservacao das obras ja certificadas.

## 5. N2 e N4: autoridade correta

- N2/F5 humano validado e o professor de dados da engenharia reversa.
- Coordenadas/geometria validada vencem campos derivados inconsistentes.
- N4 e a materializacao grafica produzida a partir de N2.
- N4 so pode julgar N3 depois de passar G1/G2.
- Um erro humano marcado em N4 e evidencia negativa, nao exemplo correto.
- Um N4 reverificado apos fix pode se tornar exemplo visual T1.

Consequencia: o RAG deve guardar separadamente `exemplo_correto`, `anti_padrao`,
`diagnostico` e `regra`. Similaridade vetorial nao pode misturar esses papeis.

## 6. Modelo de confianca

| Estado | Significado | Uso permitido |
|---|---|---|
| T0 | Rascunho, edicao, diagnostico, erro marcado, proposta | Investigacao e Curadoria |
| T1 | Evidencia ou conhecimento aprovado por humano em uma obra | Consulta RAG validada, com escopo |
| T2 | Padrao validado em duas ou mais obras sem regressao | Candidato a regra/default global |
| TX | Revogado ou substituido | Auditoria; excluido das consultas |

Fluxo Arete para conhecimento:

```text
ACHADO ABERTO/DIAGNOSTICO AUTO              -> T0
HUMANO MARCA "ERRADO"                       -> T0 negativo
FIX APLICADO + TESTES                        -> continua T0
FIX REVERIFICADO EXPLICITAMENTE PELO HUMANO  -> T1 versionado
MESMO PADRAO EM >=2 OBRAS + ZERO REGRESSAO   -> T2/global
DESVALIDACAO POSTERIOR                        -> TX + tombstone
```

Uma marcacao humana de erro valida que a saida esta errada. Ela nao valida
automaticamente a causa interpretada pelo agente nem o valor correto.

## 7. Registro Arete: modelo atual e evolucao futura

### 7.1 Decisao pragmatica atual

Com uma obra, uma pessoa revisando e baixo volume, nao implementar agora uma
infra completa de event sourcing. O JSONL atual funciona como registro
operacional versionado, nao como event log imutavel estrito.

Regras minimas obrigatorias:

- uma linha por `item + causa_raiz + marcado_por`, permitindo varias causas no
  mesmo item;
- `finding_id` estavel para atualizar o achado correto;
- `run_id` para identificar a geracao headless avaliada;
- atualizacao de `status`, `fix_aplicado`, `updated_at` e `verificado_em` por
  script, com reescrita atomica do arquivo;
- transicoes de status validadas;
- Git preserva a auditoria documental enquanto o volume for pequeno;
- reabrir um achado ja verificado cria novo `finding_id`, ligado pelo campo
  opcional `supersedes_finding_id`.

Esse modelo resolve a perda observada em L318 sem introduzir infraestrutura
prematura.

### 7.2 Modelo alvo futuro, ainda nao implementado

Quando volume, UI operacional ou automacao sem relay humano justificarem, migrar
para uma sequencia imutavel de eventos:

```text
ISSUE_DETECTED
DIAGNOSIS_PROPOSED
HUMAN_REVIEWED
FIX_APPLIED
VERIFICATION_PASSED | VERIFICATION_FAILED
ISSUE_REOPENED
KNOWLEDGE_APPROVED | KNOWLEDGE_REVOKED
```

Campos minimos do envelope:

| Campo | Funcao |
|---|---|
| `event_id` | ID imutavel do evento |
| `issue_id` | Agrupa o ciclo do mesmo achado |
| `parent_event_id` | Encadeia causalidade |
| `run_id` | Identifica a geracao headless |
| `obra`, `pavimento`, `classe`, `item` | Escopo estrutural |
| `levels_affected` | N1/N2/N3/N4/N5 afetados |
| `cause_code` | Taxonomia tecnica controlada |
| `marked_by` | humano/auto/sistema |
| `confidence` | Obrigatoria para diagnostico automatico |
| `evidence_refs` | Hashes e caminhos de HTML/SVG/DXF/JSON |
| `engine_version` | Commit/versao do motor avaliado |
| `created_at` | Timestamp UTC |

A projecao do conjunto de eventos calculara o estado atual do issue. Concordancia
entre diagnosticos passara a ser outro evento ligando `diagnosis_id` humano e
auto. Essa e direcao arquitetural, nao requisito da implementacao atual.

### 7.3 Multiplicidade

Uma nota pode descrever mais de uma causa. O parser deve produzir um achado por
causa por item. Exemplo real: uma nota pode indicar simultaneamente erro N1/N3 e
erro independente de cotagem N4. Nao reduzir ambos a uma unica `causa_raiz`.

## 8. Mapeamento dos stores existentes

| Store | Papel correto | Relacao com Arete |
|---|---|---|
| `reverse_eng_fichas` | F5/N2 versionada | Professor somente quando validada |
| `reverse_eng_recortes` | Evidencia de crop | Alimenta o trilho CROP, com status proprio |
| `training_events` | Feedback granular por campo | Sinal para regras, nao log completo Arete |
| `transformation_rules` | Regras versionadas/candidatas | Promocao segue gates cross-obra |
| `human_event_logs` | Edicoes antes/depois CAPTURED/T0 | Evidencia de edicao, nao aprovacao |
| `item_attention_notes` | Nota contextual do operador | Captura; pode originar achado |
| `n4_attention_feedback` | Feedback estreito de N4 | Projecao/compatibilidade, nao store Arete global |
| `crop_learning_events` | Eventos de recorte | Gate separado de F5/N4 |
| JSONL Arete | Registro operacional atual de achados | Fonte para futura migracao/eventos |

### Decisao sobre `n4_attention_feedback`

`n4_attention_feedback` nao e equivalente ao JSONL inteiro. A tabela so modela
um subconjunto de achados que afetam N4 e hoje nao possui classe, pavimento,
run, proveniencia, confianca, evidencia ou concordancia.

Quando houver integracao:

- preferir uma projecao dos eventos Arete filtrada por N4;
- manter a tabela antiga apenas como adaptador de compatibilidade;
- nao sincronizar todo JSONL diretamente com `save_n4_feedback` sem enriquecer
  identidade e proveniencia;
- evitar dois ciclos de resolucao independentes para o mesmo issue.

## 9. HTML/SVG como evidencia estruturada

As fichas HTML com SVG inline sao um pacote de auditoria multimodal derivado.
Elas nao substituem DXF, ficha estruturada ou validacao humana.

Uso recomendado:

- DOM/SVG `<text>` para rotulos e cotas exatas;
- atributos e coordenadas SVG para suporte a comparacao geometrica;
- screenshot/vision somente para hachura, contorno, cruzamentos e gestalt;
- vinculo aos DXFs e JSONs originais por hash;
- citacao da evidencia no resultado recuperado pelo RAG.

Nao recomendado:

- vetorizar HTML ou SVG bruto;
- usar OCR para texto que ja existe no DOM;
- tratar path SVG como semantica sem normalizacao;
- indexar uma ficha sem `run_id`, versao do motor e hashes das fontes.

Manifesto recomendado por ficha/run:

```json
{
  "run_id": "...",
  "obra": "...",
  "pavimento": "...",
  "classe": "LAJ",
  "item": "L318",
  "engine_commit": "...",
  "evidence": {
    "N1": {"artifact": "...", "sha256": "..."},
    "N2": {"artifact": "...", "sha256": "..."},
    "N3": {"artifact": "...", "sha256": "..."},
    "N4": {"artifact": "...", "sha256": "..."}
  }
}
```

## 10. MCP versus acesso direto

Adotar estrategia hibrida.

### ETL e indexacao interna

Usar leitura direta e read-only de SQLite/JSONL para:

- snapshots consistentes;
- processamento em lote;
- validacao de schema;
- reprodutibilidade e menor latencia.

### Agentes, UI e escritas

Usar MCP para:

- contratos estaveis entre agentes;
- autenticacao e autorizacao;
- idempotencia e concorrencia;
- aprovar/rejeitar/revogar;
- consultar proveniencia sem expor SQL;
- observabilidade operacional.

MCP e uma interface sobre o dominio. Nao deve possuir uma segunda logica de
tier, promocao ou resolucao diferente dos servicos usados pelo ETL direto.

## 11. Estado verificado em 2026-07-02

Leitura read-only do banco real `D:/Agente-cad-PYSIDE/project_data.vision`:

- `reverse_eng_fichas`: 906 (`769 draft`, `137 extracted`);
- `training_events`: 1436;
- `transformation_rules`: 23;
- `human_event_logs`: 160 (`159 CAPTURED/T0`, `1 TEST_QUARANTINED/T0`);
- `item_attention_notes`: 89;
- `n4_attention_feedback`: 0;
- `crop_learning_events`: 0.

Consequencias:

- o transporte MCP para agentes esta inativo;
- a captura T0 pela aplicacao ja esta ativa;
- promocao/indexacao MCP ainda nao foi exercitada ponta a ponta;
- nao ha base para promocao em massa;
- o estado confirma a decisao de nao ativar ingestao produtiva agora.

O JSONL Arete observado possui 17 achados LAJ, todos humanos e abertos. Ele
ainda usa o schema anterior: nenhum registro observado possui simultaneamente
`confidence`, `evidence` e `concordance`. A migracao para o modelo v2/eventos
continua pendente.

## 12. Fases de ativacao futura

### Fase 0 - Agora: preparacao

- mapear fontes e schemas;
- gerar manifestos e validadores read-only;
- nao gerar embeddings produtivos;
- nao promover eventos;
- manter Curadoria como observador.

### Fase 1 - Primeira obra fechada

Pre-condicao: G0/G1/G2 e G6 locais passam no escopo aplicavel, com
reverificacao humana. Conhecimento de N1/N3 exige tambem G4/G5.

- construir indice shadow/candidato isolado;
- executar retrieval offline;
- medir precision/recall e vazamento de T0;
- nao servir como professor global.

### Fase 2 - Duas ou mais obras

Pre-condicao: mesmo padrao validado em pelo menos duas obras e zero regressao.

- aprovar regras T2 elegiveis;
- habilitar consulta global T1/T2;
- manter exemplos negativos em namespace separado;
- ativar tombstones TX desde o primeiro dia.

### Fase 3 - MCP operacional

Ativar quando houver pelo menos um destes motivadores:

- varios agentes/sessoes concorrentes **operando sem relay manual do dono**
  (ver 1.1 — multiplas sessoes manuais coordenadas pelo dono NAO satisfazem
  este motivador; e sobre orquestracao autonoma, ainda nao desenhada);
- Curadoria/UI precisar operar o ciclo;
- obra nova sem N2 precisar consultar conhecimento aprovado.

Mesmo assim, ativacao exige teste ponta a ponta em copia do banco e indice
isolado antes de apontar para producao.

Varias CLIs manuais nao constituem sistema multiagente, mas ainda podem acessar
arquivos e SQLite ao mesmo tempo. Por isso permanecem necessarias idempotencia,
transacoes, escrita atomica e proveniencia. Isso e seguranca operacional basica,
nao desenho de orquestracao autonoma.

## 13. Gates antes de qualquer ingestao produtiva

- [ ] Schema pragmatico Arete (`finding_id`, `run_id`, uma causa por linha)
  definido e versionado.
- [ ] Um achado por causa, com IDs estaveis e proveniencia.
- [ ] Distincao entre evidencia negativa, diagnostico, regra e exemplo correto.
- [ ] N4 usado como juiz apenas quando G1/G2 passaram.
- [ ] Importador JSONL idempotente e testado em dry-run.
- [ ] Nenhum T0 aparece em query T1+.
- [ ] Revogacao TX/tombstones coberta por teste.
- [ ] Indice shadow avaliado antes do produtivo.
- [ ] G6 sem regressao e validacao em pelo menos duas obras para T2.
- [ ] Decisao explicita do dono registrada.

## 14. Invariantes

1. Edicao humana nao e validacao humana.
2. Marcacao de erro e evidencia negativa, nao resposta correta.
3. Diagnostico automatico e T0 ate decisao humana explicita.
4. N3 nunca recebe N2/N4 como entrada.
5. N4 nao e juiz antes de sua propria certificacao.
6. Historico nao e apagado; correcoes e revogacoes criam novas versoes/eventos.
7. RAG nao modifica motor diretamente.
8. MCP nao cria uma segunda fonte de verdade.
9. HTML/SVG e evidencia derivada e sempre aponta para a fonte original.
10. Regra global exige validacao cross-obra e zero regressao.
11. Hoje o modo de operacao e human-in-the-CLI (1.1) — nao ha orquestracao
    multiagente ativa nem desenhada; nenhuma decisao deste documento presume
    concorrencia autonoma entre agentes.
12. Varias CLIs manuais ainda exigem idempotencia, transacoes e escrita atomica;
    seguranca de concorrencia nao implica arquitetura multiagente.

## 15. Decisoes ainda pendentes

- Nome e local definitivo do store de eventos Arete no SQLite.
- Manter JSONL como log primario ou torna-lo export/projecao do SQLite.
- Gatilho objetivo para migrar do registro pragmatico ao event sourcing futuro.
- Taxonomia controlada de `cause_code` por classe.
- Schema do manifesto por run e estrategia de hashes.
- Metricas minimas do indice shadow.
- Processo de reconciliacao humano/automatico.
- Desativacao ou projecao de `n4_attention_feedback`.
- Renomear futuramente `validation_origin` de eventos T0 para evitar que origem
  humana da edicao seja confundida com aprovacao humana.

Essas decisoes podem ser projetadas agora, mas nao justificam ativar ingestao
antes dos gates definidos neste documento.
