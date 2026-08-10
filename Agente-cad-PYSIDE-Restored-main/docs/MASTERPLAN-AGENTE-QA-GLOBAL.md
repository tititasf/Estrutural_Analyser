# Masterplan — Agente QA Global de Evidências (Arete)

**Estado:** núcleo global ativo em modo conservador.
**Interface:** `scripts/arete/qa_evidence_auditor.py` (chat/CLI; a UI só apresenta).
**Escopo:** Obra → pavimento → classe → item → campo/vínculo, com consulta cruzada controlada.
**Loop/RAG:** `LOOPING-CANONICO.md`, `ARETE-LOOP-PROCEDIMENTO-GERAL.md` e
`CONTRATO-QA-RAG-LOOPINGS.md` formam o contrato operacional único.

**Orquestração reutilizável (13/07/2026):** a squad AIOS
`squads/qa-global-evidencias/` e a skill Codex `$qa-global-evidencias` empacotam este
contrato. Elas não criam outro motor: escolhem o menor microciclo canônico por
obra/pavimento/classe/item/nível/parte/variante, aplicam gates e produzem dossiê. O
comando AIOS é `/CAD:QAGlobalEvidencias-AIOS`.

## 1. Objetivo

Transformar a validação granular do Structural Analyzer em um processo auditável:

1. interpretar cada campo e vínculo a partir de prova rastreável;
2. confirmar somente o que é inequívoco;
3. abrir achado técnico quando há erro objetivo;
4. formular pergunta humana somente quando a regra geral realmente falta;
5. registrar sessão, evidência, decisão e score de confiança; e
6. produzir ground truth curado para o RAG, sem vazar N2/N4 para N1/N3.

O agente **não é um aprovador por similaridade**. Geometria é polígono, furos, recortes, contorno e coordenadas — nunca apenas comprimento × largura. Um número perto de um elemento não vira nível; uma proximidade não vira apoio; uma ficha não prova a si própria.

Ele também não é uma auditoria passiva isolada: é o executor assistido do Eixo B
dos loopings Arete. Cada sessão começa observando, transforma a evidência em
achado/hipótese, conduz o microciclo canônico e mede a correção. A validação de
campos só aparece após autoridade progressiva por família de campo; a promoção
de conhecimento segue o contrato QA↔RAG, não um score isolado.

## 2. Autoridade por classe

SoT versionada: `squads/qa-global-evidencias/data/authority_matrix.json`
(alinhada a `CLASS_REGISTRY` via `scripts/arete/qa_authority_matrix.py`).

| Classe | Fonte N1 observada | Adaptador | Estado atual | Pode selar? | Próximo gate |
|---|---|---|---|---|---|
| LAJ | `slabs.links_json` + `points_json` | `LajEvidenceAuditor` | `validation_ready` | Sim, somente `apply` explícito e snapshot íntegro | RAG T1/T2 + generalização em outra obra |
| PIL | `pillars.links_json` + `points_json`/`sides_data_json` | `PilEvidenceAuditor` + `qa_pil_coverage.py` | `validation_ready` (limites: retangular provado; L/U/circular pendente) | Sim, somente `apply` explícito via adaptador; cobertura ≠ apply | ampliar geometrias + QG7 institucional + set de campos de face |
| FV | `beams.data_json`, família `viga_fundo*` | `FvEvidenceAuditor` | `validation_ready` (segmentos com geometria re-derivada) | Sim, `apply` explícito só nos campos provados; 1 segmento ≠ viga inteira | golden multi-geometria + G2-V |
| LV | `beams.data_json`, famílias `viga_a_*`/`viga_b_*` + `lv_generation_contracts` | `LvEvidenceAuditor` | `validation_ready` (4 contratos A/B×PARA/PASSA) | Sim, `apply` explícito nos campos/contratos provados | golden para+passa + G2-V |

As quatro classes usam adaptadores dedicados. `CONFIRMAR` exige re-derivação
independente (geometria/contrato), não trilha genérica do payload. PASS de um
campo/segmento/contrato **não** aprova a ficha inteira. Golden visual e
pacote G2-V continuam o gate institucional antes de selagem em massa.

> **Precisão de vocabulário (atualizado 16/07/2026):** LAJ/PIL/FV/LV usam
> adaptadores. FV/LV cobrem famílias centrais (fundo por segmento; 4 contratos
> laterais). Aberturas/furos/geometrias especiais podem permanecer `PENDENTE`
> até extensão do adaptador.

## 3. Núcleo e adaptadores

```text
escopo explícito
  → snapshot persistido N1
  → adaptador da classe
  → fonte CAD / ficha / evidência web / contexto cross-classe / RAG
  → decisão por campo e vínculo
  → dossiê append-only + score
  → [somente adaptador validation_ready] apply transacional autorizado
```

O núcleo é comum: seleção de escopo, snapshots, hashes, sessões, perguntas explicadas, score, achados, rollback e recorrência de dúvidas. Cada adaptador define, sem herdar semântica de outra classe:

- campos obrigatórios e categorias de proveniência a/b/c/d;
- evidência mínima por campo;
- limites geométricos e relacionais;
- regras de visão de corte/cotas quando aplicável;
- fontes cross-classe permitidas;
- teste golden, gate visual e condição para `validation_ready`.

### Executor persistente de microciclos

`qa_loop_executor.py` implementa a retomada que antes existia apenas como comando
conceitual da squad. Cada run mantém `state.json`, ledger `events.jsonl`, orçamento de
ciclos e `RESUME.md`. Passos read-only seguros avançam automaticamente; um fix invalida
snapshot/cobertura e força nova prova. O executor nunca edita código sozinho, nunca
promove RAG e nunca habilita `apply` de classe `diagnostic_only`.

Estados humanos são explícitos: `WAITING_HUMAN_VISUAL`, `WAITING_HUMAN_QG7` e ensino
de regra estrutural. O ensino exige regra, exemplo, exceção/contraexemplo, escopo e
evidência; vira candidato T1 e tarefa de fórmula geral + testes, não treinamento de
pesos do LLM.

## 4. Consulta global e comandos

Sempre prefira `--project-id`: uma obra/pavimento pode ter reprocessamentos e o agente falha fechado se `--obra --pav` não for único.

```powershell
$py = 'D:\Agente-cad-PYSIDE\.venv\Scripts\python.exe'

# Mapa completo de campos e cobertura, sem alterar a base.
& $py -X utf8 scripts/arete/qa_evidence_auditor.py discover `
  --project-id <id> --classe ALL --include-sealed

# Diagnóstico de uma família ainda não habilitada para selar.
& $py -X utf8 scripts/arete/qa_evidence_auditor.py discover `
  --project-id <id> --classe FV --item V301

# Revisão por campo/vínculo das quatro classes. Produz decisões, achados,
# perguntas com cadeia de raciocínio e score; não altera a base fora de LAJ.
& $py -X utf8 scripts/arete/qa_evidence_auditor.py review `
  --project-id <id> --classe ALL --include-sealed

# Auditoria LAJ em profundidade (read-only).
& $py -X utf8 scripts/arete/qa_evidence_auditor.py audit `
  --project-id <id> --item L318 L319 --include-sealed
```

Cada `discover` grava `manifesto.json`, `inventario_classes.json`, `resumo_global.md` e uma entrada append-only em `scripts/arete/relatorios/qa_evidencias/registro_sessoes.jsonl`.

### 4.0 Quadro vivo de estado por classe/pavimento

O QA mantém quadro HTML/JSON/CSV/Markdown **read-only** por classe e pavimento para
orientar a execução item a item. O quadro é projeção de evidências persistidas,
nunca fonte para N1/N3 nem mecanismo de selo. Ele é regenerado após microciclo que
produza ou observe nova evidência persistida (review, decisão, materialização,
diagnóstico, smoke, gate visual ou regressão), e o agente entrega seu link no handoff.

O contrato de colunas, cores, estágios, especializações FV/LV/PIL/LAJ, nomes dos
motores e prompt operacional está em `docs/QA-QUADROS-ESTADO-POR-CLASSE.md`. FV já
possui `qa_fv_quadro_pavimento.py`; os demais quadros só existem após implementação
dedicada e não podem herdar campos ou semântica de outra classe.

### 4.1 Teste rápido de vínculo e limite de autoridade

Para uma dúvida localizada, preferir o probe declarativo antes do review amplo:

```powershell
& $py -X utf8 scripts/arete/qa_n1_field_probe.py `
  --request scripts/arete/qa_requests/examples/pil_p35_face_d_v328.json
```

Cada request escolhe somente campos/fontes/caminhos/checks necessários e pode
cruzar classes. `PASS` confirma apenas essas hipóteses, jamais a ficha ou o item.
O overlay permite testar uma saída candidata sem gravar no DB. A leitura mínima,
o snapshot por linha e o cache por conteúdo tornam o ciclo rápido e invalidável.

Hipóteses recorrentes devem virar perfis executáveis em
`squads/qa-global-evidencias/data/class_profiles`. O runner
`qa_profile_probe.py` exige escopo explícito e aplica fronteiras semânticas por
classe; especialmente, FV e LV não podem consultar famílias uma da outra no
`beams.data_json`. A premissa completa está em
`docs/QA-PERFIS-CLASSES-SA-N1-N3.md`.

`review --classe ... --item ...` é o teste rápido oficial para vínculos que já
estão no snapshot persistido. Ele não instancia Qt, não disputa a trava do
headless e não grava N1 em PIL/FV/LV:

```powershell
& $py -X utf8 scripts/arete/qa_evidence_auditor.py review `
  --project-id <id> --classe PIL --item P1 P3 P35 `
  --include-sealed --rag-evidence off
```

Use-o para detectar ausência de entidade de origem, slot sem proveniência,
conflito entre campos e cobertura do contrato. Ele avalia **o DB atual**; não
exercita uma alteração ainda não materializada no extrator. Se o código N1 foi
alterado, o microciclo headless continua obrigatório antes de repetir o review.

Rodadas read-only de uma única `--secao` usam fila e snapshot próprios da classe, com
ou sem `--item`; agentes QA de classes distintas podem materializar em paralelo.
Com `--persist-db --secao X --item ...`, o commit continua parcial (upsert, sem apagar
ausentes) e usa a fila de X. Ausência de `--secao`, múltiplas classes ou persistência
sem identidade de item promovem automaticamente a execução para o lock global + locks
PIL/LAJ/FV/LV. O QA nunca contorna essa política.

### 4.2 Gate anti-loop caro: aceite antes da materialização

Antes de editar um extrator/vínculo N1, o run deve declarar um predicado de aceite
executável por campo ou relação. O predicado diferencia explicitamente o objetivo
final de fatos intermediários. Exemplo: “V308 tem dimensão 19/55” não substitui
“P35 A/B vinculam V308 e o vão de V308 alcança P35”.

Roteiro obrigatório:

1. capturar o antes com `qa_n1_field_probe.py`;
2. provar a hipótese em teste puro/overlay;
3. executar um headless granular para materializar;
4. repetir imediatamente a mesma probe;
5. se o predicado final não mudar, interromper a repetição e investigar o elo
   anterior da cadeia fonte→vínculo.

Uma segunda execução headless para o mesmo item exige nova causa reproduzível e uma
probe/teste barato que demonstre por que o próximo resultado será diferente. Uma
dependência cross-classe não pode ser persistida em microciclo parcial se perder
segmentos ou cobertura geométrica em relação ao snapshot anterior. Pós-mortem de
referência: `docs/POSTMORTEM-PIL-P35-MICROCICLO-20260713.md`.

Mudança somente em geometria/estilo/cotas N3/N4 usa o gerador individual da
classe e `scripts/arete/ficha_motor_item.py`; o QA lê seu manifesto/hash como
evidência de iteração, sem tratá-lo como prova de interpretação N1.

Para os campos de saída, `qa_artifact_parity.py` compara declarativamente
contrato→payload→DXF→HTML e explicita metadado DXF ausente. A leitura visual
continua separada. O benchmark `qa_fastpath_benchmark.py` mede o caminho frio e
aquecido e exige checks semanticamente idênticos.

O caminho N3 padrão usa `qa_n3_smoke.py` antes da ficha individual. O smoke
confirma somente identidade, texto e camadas mínimas em todas as variantes
declaradas; a ficha/PNG continua responsável pela geometria e o gate visual.

## 5. Regras de evidência e anti-alucinação

1. **N1 é alvo, não prova de si próprio.** Campo persistido precisa de entidade/coord., fonte interpretativa ou cálculo reproduzível.
2. **N2/N4 são comparadores independentes.** Podem denunciar divergência; jamais alimentam N3 ou reescrevem N1.
3. **Visual obrigatório para gate visual.** Somente `g2v_harness.py --backend cli`;
   agente julga em **PNG**; SVG no HTML persist/portal (`QA-VISAO-EVIDENCIA-CANONICA.md`).
   API permanece desligada.
4. **Cross-classe é consultivo.** Uma laje pode consultar pilares/vigas limítrofes para testar contato; não copia atributos entre classes.
5. **Dúvida falha fechada.** `PENDENTE` ou `REVISAR_HUMANO`, acompanhada de observação, tentativas, hipóteses recusadas, impasse e impacto.
6. **Nenhum hardcode por obra/pavimento/item.** Regra nova exige causa geral e regressão.
7. **Dados protegidos.** JSONs Fase-4 e artefatos históricos são intocáveis; alterações de N1 só ocorrem por `apply` autorizado do adaptador apto.

## 6. Plano de consolidação por classe

### Fase A — LAJ: consolidar ground truth

- manter o auditor de visão de corte, pilares de apoio, níveis e vizinhança;
- curar exemplos aprovados e antipadrões no RAG por campo/subclasse;
- validar em outro pavimento e uma obra distinta sem mudar a regra;
- promover somente evidências humanas/visuais e decisões rastreáveis a T1/T2.

### Fase B — FV: primeiro adaptador reutilizado

- gerar `PROVENIENCIA-CAMPOS-FV.md` a partir do inventário e das fichas reais;
- definir segmentos de fundo, extremidades, altura/nível, recortes e vínculos com lajes/pilares;
- rodar diagnóstico N1×N2 e G2-V nos itens canônicos;
- habilitar `audit` FV somente depois de golden sem falso positivo crítico; `apply` apenas após revisão humana.

### Fase C — PIL: relações por face e entre pavimentos

- documentar faces A…F, geometria, dimensões, vigas/lajes adjacentes, continuidade e seção;
- validar que dimensão, face e elemento conectado apontam para a mesma entidade CAD;
- fazer consulta vertical de pavimentos como evidência, nunca como cópia de atributo;
- somente então liberar escrita controlada.

### Fase D — LV: segmentos e convenções de montagem

- documentar famílias de campos A/B, segmentos, passa/para, recortes e cotagem;
- verificar cadeia segmento → face → viga → laje/pilar;
- provar o adaptador em geometrias retas, degraus e recortes antes de habilitar selo.

## 7. RAG e ground truth

O RAG entra como memória consultiva, não como autoridade. Cada entrada deve carregar:

- classe, subclasse, campo e categoria de proveniência;
- obra/pavimento de origem e versão do motor;
- fonte primária (DXF/ficha/decisão humana/PNG do gate);
- decisão, confiança, exceção conhecida e citações;
- tier: **T1** humano confirmado, **T2** regra reproduzível aprovada, **T3** hipótese (não usada para selar).

Um campo só pode alimentar T1/T2 após validação humana e gate correspondente. Toda resposta do agente que usar RAG deve citar a entrada e nunca esconder conflito com a obra atual.

## 8. Quality gates do programa

| Gate | Critério de saída |
|---|---|
| QG0 Escopo | projeto/obra/pavimento resolvido sem ambiguidade |
| QG1 Schema | inventário real e tabela de proveniência da classe completos |
| QG2 Evidência | cada campo tem fonte mínima e regra de decisão |
| QG3 Visual | golden e veredito visual canônico aprovados quando aplicável |
| QG4 Segurança | N3 sem N2/N4, preservação de selos humanos, snapshot/rollback testados |
| QG5 Generalização | outro pavimento/obra passa sem regra por item |
| QG6 RAG | somente T1/T2 citável; recorrências e dúvidas monitoradas |
| QG7 Promoção | adaptador passa de `diagnostic_only` a `validation_ready` com revisão humana |

## 9. Próxima execução recomendada

1. Rodar `discover --classe ALL --include-sealed` no projeto de 13_PAV e arquivar o inventário-base.
2. Para FV, usar o inventário + diagnóstico canônico para escrever a proveniência antes de qualquer validação automática.
3. Repetir para PIL e LV, mantendo LAJ como corpus de referência para o núcleo, não como regra semântica reaproveitada.
4. Quando uma classe alcançar QG0–QG6, implementar seu adaptador de decisão e submetê-lo a revisão visual/humana antes de liberar `apply`.

## 10. Arquitetura da squad e decisão MCP/hooks

A squad segue task-first architecture: `ScopeResolver`, `EvidenceIndex`, adaptador de
classe, paridade contrato→payload→DXF→HTML, gate visual, triagem, regressão e candidato
RAG. O orquestrador apenas monta o DAG, aplica política e cache por conteúdo; não desenha,
não interpreta domínio e não escreve N1.

Fast paths disponíveis: probe N1 de campos/vínculos com leitura mínima e
cross-classe; paridade declarativa de artefatos; render DXF→PNG (agente) / SVG (web);
   consulta
RAG tipada que falha fechada quando o schema não suporta os filtros pedidos. O
contrato detalhado está em `QA-FASTPATHS-CAMPOS-ARTEFATOS.md`.

MCP e hooks automáticos ficam deliberadamente adiados. O QA já possui CLIs canônicos;
um hook sem contexto pode disparar headless caro ou escolher nível incorreto. MCP só
entra após adaptadores PIL/FV/LV, RAG tipado por classe/família/campo/tier/escopo,
separação read/write e testes de anti-leakage/rollback atingirem QG1–QG6.
