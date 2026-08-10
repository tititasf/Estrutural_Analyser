# Structural Analyzer — progresso por item e trilha de evidências

Este documento é o mapa operacional para uma obra/pavimento em treino. Ele
complementa `LOOPING-CANONICO.md`: não substitui os gates Arete nem autoriza
usar N2/N4 como fonte de N1/N3.

> **Notação obrigatória:** G1 (round-trip N2→N4→N2′), G2 (paridade canônica
> N2×N4), G3 (UI/persistência), G4 (convergência/interpretação N1), G5 (paridade
> final N3×N4) e G6 (golden/regressão). A validação visual de G2-V, N1-V/G4-V e
> G5-V ocorre exclusivamente via `g2v_harness.py --backend cli`: o
> **modelo/agente CLI** lê os SVGs-fonte e o manifesto vetorial. API visual é proibida.

## Onde o histórico mora

Cada classe tem um diário append-only em `docs/SA-ANALISE/HISTORICO/`:

| Classe | Diário |
|---|---|
| PIL | `PIL.md` |
| LAJ | `LAJ.md` |
| FV | `FV.md` |
| LV | `LV.md` |

## Manuais operacionais específicos

O fluxo S0–S8 abaixo é geral. Antes de investigar um item, abrir o manual da classe
em `docs/SA-ANALISE/CLASSES/`: [PIL](SA-ANALISE/CLASSES/PIL.md),
[LAJ](SA-ANALISE/CLASSES/LAJ.md), [FV](SA-ANALISE/CLASSES/FV.md) ou
[LV](SA-ANALISE/CLASSES/LV.md). Eles definem campos, SVGs, exceções, motor dono,
probes, diagnóstico, smoke e regressão próprios; não autorizam usar um caminho de
uma classe como fallback semântico de outra.

## Agente autoevolutivo, guardião e alimentador RAG

O agente QA é pioneiro: não se limita a listar FAIL. A cada evidência ele deve
**observar → localizar fonte → formular regra geral → provar no menor escopo →
ajustar/programar o motor autorizado → testar → registrar → atualizar este processo
e o manual granular da classe**. A evolução é acumulativa: exemplos, contraexemplos,
campos difíceis, causas descartadas, comandos rápidos e regressões passam a integrar a
documentação para reduzir trabalho repetido no próximo item/pavimento/obra.

Isso não autoriza autoaprovação: N2/N4 nunca alimentam N1/N3, o schema N1 permanece
imutável e toda alteração de motor exige a prova/regressão proporcional. O agente é
também guardião RAG por classe: organiza evidência e prepara candidatos multimodais,
mas **não promove RAG sozinho**. A alimentação/harmonização efetiva continua dependente
da revisão humana posterior.

### Contexto obrigatório ao iniciar/retomar uma sessão

O agente deve carregar e registrar: obra, `project_id`, pavimento, classe, quantidade
total/processada/selos, itens BLUE/laranja/pendentes, último run/headless, diagnóstico,
achados abertos, manual da classe e diário append-only. A fonte viva é
`gerar_status.py`, DB read-only, `qa_evidence_auditor discover/review`, relatório mais
recente e `HISTORICO/<CLASSE>.md`; número antigo de texto não substitui essa leitura.

### Gatilhos de aprendizagem e RAG

| Gatilho | Dever do agente | Saída, sem promoção automática |
|---|---|---|
| item marcado **BLUE** na UI/humano | capturar HTML/SVG, fontes CAD/DB, decisão e contraexemplo; ajustar/testar se houver causa geral | entrada no diário, triagem v2 e candidato RAG do item/campo |
| solicitação humana | investigar a dúvida, implementar regra universal quando provada e documentar o caminho | manual da classe atualizado + evidência rastreável |
| todos os selos laranja da classe em um pavimento | consolidar cobertura, exceções, regressões, HTMLs/SVGs e candidatos da classe | pedir ao humano validação do pavimento/classe para futura curadoria RAG |
| obra concluída | sintetizar o que as classes ensinaram sobre a obra: convenções, níveis, relações, exceções e limites | pedir validação humana da compreensão global da obra antes de qualquer RAG geral |

O HTML validado de um item é produto multimodal candidato: ficha N1/N2/N3/N4, SVGs,
manifestos, vínculos, coordenadas, score e decisão humana formam uma unidade heurística
reutilizável. Sem proveniência, versões/hashes, escopo e aprovação humana, ele continua
somente evidência local — nunca “memória” global.

## Tabelas padrão — relatório do agente no chat CLI

Toda atualização operacional começa por um resumo e pelo quadro do pavimento
quando o escopo for uma classe completa. Eles separam estado vivo, evidência
realmente lida e próxima ação. Não usar número de G2 como sinônimo de selo N1/N3
ou Arete.

### 1. Resumo de selos por nível

O topo do `QUADRO-FV-PAVIMENTO.html` tem **exatamente quatro cards**, um para
cada nível: N1, N2, N3 e N4. Não criar cards paralelos para `is_validated`,
Arete, topologia, G2 ou diagnóstico: são evidências/etapas dentro do nível e
nunca substitutos do selo correspondente.

Os quatro cards aparecem em **dois blocos**: primeiro o consolidado de todos
os tempos (somente registros FV com identidade reconhecível) e depois o
**pavimento atual em treino/análise**. A lista abaixo dos cards é sempre e
somente a lista de itens do pavimento atual, identificada com obra, pavimento e
classe no título. Assim o consolidado mostra progresso histórico e a tabela não
mistura itens de outros pavimentos.

No consolidado há ainda um card de **cobertura de execução QA FV**: total de
obras e de pavimentos em que o `qa_evidence_auditor` realmente rodou para FV,
lidos de `registro_sessoes.jsonl` append-only. Inventário no DB sem sessão QA
registrada não entra nesse contador.

| Card | Total | Selos mostrados | Fonte e regra |
|---|---:|---|---|
| N1 / SA — Fundos FV | itens N1 persistidos no Structural Analyzer (SA) | azul, laranja, verde, rosa | somente estado de selo já persistido no SA; N2/N4 nunca completam N1 |
| N2 — Fichas FV | fichas N2 do pavimento | azul, laranja, verde, rosa | azul/laranja são projeção **read-only** da política N4 pareada; azul N4 humano valida N2 azul, laranja N4 QA valida N2 laranja; nenhum dado da ficha é regravado |
| N3 — Fundos FV | itens N3 com smoke ou política persistida | azul, laranja, verde, rosa | somente evidência N3 persistida; N2/N4 nunca alimentam N3 |
| N4 — Fundos FV | fichas N2 com referência N4 | azul, laranja | N4 humano-app é azul; N4 do QA é laranja; verde/rosa não se aplicam ao N4 |

**G2 (paridade canônica N2×N4)** é exibido dentro do card N4 como evidência do
lote. Não é card independente, não é veredito visual e não cria selo. G2-V,
N1-V e G5-V continuam vereditos visuais via `g2v_harness.py --backend cli`,
lidos pelo modelo/agente CLI nos SVGs.

Arete, topologia humana, diagnóstico e `is_validated` permanecem no JSON de
proveniência e nas linhas detalhadas; não inflacionam a contagem dos cards.

### 2. Quadro detalhado de um pavimento

Cada linha é exatamente uma viga/item FV do projeto selecionado. O artefato
canônico tem Markdown para leitura, CSV para filtro e JSON de proveniência. No
chat, mostrar a tabela completa se ela couber; caso contrário, mostrar o resumo,
as linhas em trabalho e o link clicável para o quadro completo.

Para FV, o motor read-only é
`scripts/arete/qa_fv_quadro_pavimento.py`. Ele recebe somente
`--project-id`, `--obra`, `--pav` e `--output-dir`, lê automaticamente o G2 de
`docs/STATUS.md` e gera `QUADRO-FV-PAVIMENTO.html`, Markdown, CSV e JSON.
`--g2-lote` é uma sobrescrita exclusiva para auditoria histórica. O HTML é a
leitura padrão: contém todas as linhas, cards de resumo, proveniência e o comando
de atualização; o chat só aponta o arquivo, evitando repetir uma tabela larga a
cada sessão.

O QA regenera o quadro FV ao final de todo microciclo que tenha produzido ou lido
evidência persistida: review, decisão N2/N3/N4, materialização headless,
diagnóstico, smoke, veredito visual CLI ou regressão. O quadro não é fonte N1/N3
nem mecanismo de selo. O contrato comum FV/LV/PIL/LAJ e os prompts operacionais
estão em [QA-QUADROS-ESTADO-POR-CLASSE.md](QA-QUADROS-ESTADO-POR-CLASSE.md).

| Etapa atual / próximo passo | Item | N2 — validação / estado técnico | S1 — ficha N2 emitida + segmentos/painéis (C×L cm) | N4 deste item — validação / G2-V CLI | S3 — N1 / SA: geometria por segmento (contorno + C×L) | S4 — N1 / SA: item completo (quantidade, continuidade, apoios) | N1-V CLI | Ficha N1×N2 (comparada / QA) | N3 — smoke + selos do item | Ficha N3×N4 (comparada / QA) | Ficha N3×N2 (comparada / QA) | R1 — RAG multimodal: HTML pós-QA (hash/ingestão) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `S0…S8` e a próxima evidência/comando objetivo; a cor da célula segue a coluna-alvo da etapa | `Vxxx` | `Validação N2: SIM/NÃO` herdada somente do aceite N4 azul/laranja correspondente; `draft`/`extracted` é mostrado apenas como estado técnico histórico da ficha e nunca nega esse aceite | `✓ Ficha N2: emitida` confirma somente disponibilidade; abaixo `S1 C×L; S2 C×L`, incluindo multiplicador/painéis. Não é selo humano por si só | `Validação N4 deste item: SIM/NÃO` + origem azul/laranja; `G2-V CLI deste item: SIM (PASS/FAIL/SUSPEITO)` somente quando o relatório canônico SVG+manifesto tiver veredito CLI completo, senão `NÃO registrado`; **G2** aparece apenas no card N4 do lote | Cada `S<i>` mostra `area_segs` (contorno) + `dim` (C×L), com 🔵/🟠/🌸. `SIM` só quando todos os segmentos têm ambos. Com N2: número+medidas em 0,05 e N1-V CLI SVG local/contextual são obrigatórios para o 🟠 QA | Cada `S<i>` mostra `local_ini` + `local_fim`; também exige `name` e `viga_count_c`. `SIM` só quando fecha o item inteiro, sem substituir S3 | `N1-V CLI deste item: PASS/FAIL/SUSPEITO` quando houver relatório canônico SVG+manifesto completo; senão `SVG emitido; QA pendente` ou `não emitido / QA pendente`; nunca API/PNG | N2 é apenas comparação, tolerância 0,05 | smoke separado dos 4 selos N3; smoke não acende selo | comparação visual e decisão QA separadas; G5/G5-V | comparação de ficha diagnóstica, nunca fonte de N3 | `✓ RAG HTML: SIM` só quando o log append-only registra HTML + SHA-256 + `qa_run_id`. `T0 contextual` não é T1 nem Arete; T1 depende de curadoria humana. RAG nunca alimenta N1/N3 |

Regras da célula:

1. `SIM` significa que a prova de **validação** foi persistida e identificada;
   “há arquivo”, “há campo” e “teste numérico passou” são estados distintos.
2. `C×L` é sempre **comprimento × largura em cm**. Em fundo não retangular,
   registrar também `chanfro`, `furo` ou `recorte` e conservar os pontos do
   contorno; não reduzir a geometria a uma linha.
3. Se N1 não tiver pontos/evidence_segments persistidos, registrar
   `não persistido` para o comprimento. Não copiar a medida N2 para preencher a
   tabela N1.
4. Multiplicadores de cota/painel precisam aparecer como `5× <painel>` ou
   equivalente quando a ficha os declarar. Se o dado só está visível no SVG e
   não estruturado, escrever `multiplicador visual pendente` em vez de calcular
   por suposição.
5. Toda comparação contém dois estados: **comparada** (diagnóstico/artefato
   existe) e **QA** (alguém decidiu com evidência). Um `PASS` automático não é
   `QA=SIM`.

### 3. Linha compacta de atualização

| Escopo | Estágio/gate (o que faz) | Evidência consultada | Estado provado | Próxima ação | Humano necessário |
|---|---|---|---|---|---|
| `<obra>/<pav>/<classe>/<itens>` | `Sx`, Gx (função) e variante | DB, diagnóstico, HTML/SVG, contrato/DXF ou relatório com caminho | PASS/FAIL/PENDENTE/N/A; contagem e limite da prova | menor comando/hipótese que move o item | não / validar SVG / decidir regra / curar RAG |

Após a tabela, no máximo quatro linhas: **achado principal**, **motor dono**,
**não-regressão** e **limite**. Gate visual sempre escreve “via
`g2v_harness.py --backend cli`, lido pelo modelo/agente CLI nos SVGs”; nunca “visão
automática” ou API. A tabela é relatório de chat, não substitui diário, triagem v2 ou
manifesto.

Uma entrada é obrigatória quando um item é analisado, recebe achado, muda de
etapa, é aprovado/reprovado visualmente ou tem uma hipótese descartada. O
diário não é um selo: o estado efetivo continua no DB, nas fichas, no diagnóstico
e nos relatórios gerados.

## Ordem obrigatória para obra de treino

```text
N2 recorte humano validado
        ↓
N4 gerado do N2 e validado visualmente
        ↓
N1 interpreta o DXF original (independente de N2/N4)
        ↓
N1: geometria + segmento/campo + evidência visual validados
        ↓
N1×N2: fichas comparadas campo a campo, score de concordância e achados
        ↓
N1 semelhante ao N2 como referência diagnóstica, sem N2 alimentar N1
        ↓
N3 gerado somente de N1
        ↓
N3: smoke + comparação visual com N4 e N2
        ↓
Gates Arete, golden, regressão e revisão humana final
```

N2/N4 são professores de comparação e aceitação da geração reversa. Eles nunca
preenchem, corrigem ou pontuam N1/N3 como entrada.

## Estágios de um item

| Etapa | Objetivo e saída | Ferramenta canônica | Critério para avançar |
|---|---|---|---|
| S0 — Inventário | identidade, classe, item, parte/variante, fonte DXF e estado de validação | `gerar_status.py`, DB read-only, `qa_evidence_auditor discover` | escopo e histórico existentes |
| S1 — N2 aceito | ficha/recorte humano revisado por parte/campo | Reverse Hub + ficha N2/recorte DXF | humano valida ou registra FAIL/BLOCKED |
| S2 — N4 aceito | N4 vem exclusivamente da ficha N2 e representa o recorte | gerador individual da classe, `ficha_motor_item.py`, `g2v_harness.py --backend cli` | G2 (paridade canônica) numérico + G2-V (veredito visual N2×N4 via modelo/agente CLI); golden só após revisão |
| S3 — geometria N1 por segmento | SA extrai do DXF original o contorno local e a dimensão C×L de cada segmento | `headless_sa_analise.py --secao fundos_viga --item ... --wait`, `qa_evidence_auditor review`, ficha HTML/SVG e diagnóstico N1×N2 | para cada segmento, `area_segs` + `dim` persistidos e validados; com N2, quantidade/medidas em 0,05 e N1-V `PASS` via `g2v_harness.py --backend cli` nos SVGs local/contextual antes de 🟠 QA; N2 nunca preenche N1 |
| S4 — item FV completo | fecha os campos não geométricos de fundo: identidade/quantidade, continuidade e apoios por extremidade | `qa_evidence_auditor review`, `qa_profile_probe.py`, `qa_n1_field_probe.py`, ficha HTML/SVG; PIL apenas para provar apoio | `name`, `viga_count_c`, `local_ini` e `local_fim` de todos os segmentos têm cadeia rastreável e validação; cada origem 🔵/🟠/🌸 permanece isolada |
| S5 — selo QA N1 | QA audita a interpretação N1 campo a campo contra o DXF e compara ficha N1×N2 para localizar divergência antes de N3 | `qa_evidence_auditor review`, matriz/score de ficha N1×N2, probes N1, ficha HTML/SVG, `g2v_harness.py --par n1xn2 --backend cli` + diário/triagem v2 | score de concordância N1×N2 e achados registrados; campos N1 extraíveis/algorítmicos passam na tolerância 0,05 ou têm FAIL/N/A justificado; N2 compara, nunca preenche N1 |
| S6 — N3 independente | contrato N3 materializado de N1, DXF individual e ficha de motor | contrato da classe, gerador individual, `qa_n3_smoke.py`, `ficha_motor_item.py` | identidade, segmentos, ordem, dimensões, apoios e exceções chegam ao DXF |
| S7 — selo QA N3 | N3 visualmente confrontado com N4 e N2, sem herança de gabarito; FAIL é classificado entre geração N3 e interpretação N1 | `g2v_harness.py --par n3xn4 --backend cli`, comparação N3×N2 aplicável, smoke/ficha de motor | G5 (paridade final N3×N4) + G5-V (veredito visual via modelo/agente CLI), smoke e revisão humana; se N1 está provado, corrige gerador; se a prova N1 é insuficiente, retorna a S5 |
| S8 — entrega Arete ao humano | HTML completo do item/partes é entregue ao dono para verificação final da cadeia N1/N2/N3/N4 | pack HTML canônico, SVGs-fonte CLI, manifesto e relatório consolidado | humano confirma tudo correto; então golden/regressão e critérios de `MASTERPLAN-ARETE-QUALITY-GATES.md §6` fecham Arete |

### Significado dos selos laranja QA

- **Laranja N1:** S3+S4+S5 concluídos para aquele item/parte. Prova que a
  interpretação N1 foi auditada; não declara Arete e não autoriza gerar N3 de
  dado N2/N4.
- **Laranja N3:** laranja N1 + S6+S7 concluídos. Prova que N3 nasceu de N1 e
  foi auditado contra as referências. Também não substitui o selo Arete.
- **Arete:** somente S8. Exige os dois selos QA quando aplicáveis, os gates
  visuais e o golden/regressão; número verde isolado nunca fecha etapa.

## Como o agente trabalha em cada estágio

### S0 — inventário

1. Ler DB e `gerar_status.py`; abrir/continuar o diário da classe.
2. Registrar item, parte, variante, fonte DXF, estado de campos/segmentos e
   histórico de FAILs. Não rodar headless para essa consulta.

### S1 e S2 — referência N2/N4

1. Abrir o recorte e ficha N2; a validação do recorte é humana.
2. Gerar N4 por item/parte e abrir a ficha de motor. A evidência visual é sempre
   SVG: texto, cotas, geometria e metadados permanecem vetoriais e rastreáveis.
3. Rodar G2 (paridade canônica) e o G2-V (veredito visual via modelo/agente CLI)
   com `g2v_harness --backend cli`; registrar o resultado e o caminho
   dos SVGs e do manifesto SVG. O agente não altera N1 nesta etapa.

### S3 e S4 — interpretação N1

1. Se a pergunta é sobre campo já persistido, usar primeiro probe read-only
   (`qa_n1_field_probe`/`qa_profile_probe`) e ficha HTML existente.
2. Se o motor precisa ser executado, usar somente
   `headless_sa_analise.py --secao <classe> --item <item> --wait`. Microciclo
   é suficiente para uma investigação; mudança em motor compartilhado exige
   regressão completa conforme `LOOPING-CANONICO.md`.
3. **S3 FV** fecha somente a geometria de cada segmento: para cada
   `viga_fundo_seg_<i>`, validar `area_segs` (contorno/links) e `dim`
   (comprimento × largura). A coluna S3 só fica `SIM` quando todos os segmentos
   estão completos. Havendo ficha N2, comparar contagem e C×L na tolerância 0,05
   e executar obrigatoriamente N1-V pelo `g2v_harness.py --backend cli`: o
   modelo/agente CLI lê os SVGs N1 local e contextual. **Selo 🟠 FV:** além de
   C×L, o checklist `contorno_posicao_sobre_estrutural` deve ser true — cada
   contorno N1 alinhado e posicionado sobre as faces/linhas do DXF estrutural;
   tamanho certo com área flutuando = FAIL e **proíbe** `qa_agente` em
   exists/area_segs/dim. Só então o agente pode persistir 🟠 nos campos
   geométricos confirmados; N2 continua somente referência, nunca escrita em N1.
4. **S4 FV** não revalida nem substitui o contorno S3. Fecha o item completo
   com `name`, `viga_count_c`, `local_ini` e `local_fim` de cada segmento. Os
   dois últimos provam continuidade e apoio em cada extremidade. A coluna só
   fica `SIM` quando todos esses campos existem e foram validados. 🔵 humano-app,
   🟠 QA-agente e 🌸 humano-portal são coberturas independentes: um selo não é
   obtido misturando origens.
5. Converter o achado em triagem schema v2 e diário: fato, fonte, hipótese,
   tentativa e próximo teste. Não promove campo por proximidade de bbox.

### S5 — auditoria QA N1 campo a campo

1. O agente QA chama `qa_evidence_auditor review` e monta a matriz de campos:
   identidade, geometria, segmento, ordem, dimensão, apoio, corte/abertura e
   contexto. Cada célula fica PASS, FAIL, PENDENTE ou N/A justificado.
2. Comparar ficha N1×N2 campo a campo e registrar score de concordância por
   item/parte, além de cada match, mismatch e N/A. Sem essa comparação e seu
   score/achados, S5 não avança para S6/N3. Campos N1 extraíveis/algorítmicos
   precisam concordar dentro de 0,05; somente N/A de campo só-no-N2/teto
   estrutural, com fonte e justificativa, pode não contar como mismatch. Esta
   referência diagnóstica separa erro de interpretação N1 de erro posterior de
   contrato/geração N3.
3. Conservar a cadeia de origem N1: DXF original → BeamTracer/interpretador →
   link/campo N1. N2 e o recorte visual detectam divergência, mas nunca
   preenchem, corrigem ou elevam o score de N1 por herança.
4. Rodar N1-V em SVG pelo backend CLI e ler todos os vetores do par. O selo laranja N1 só
   existe se o QA explicar por que cada segmento/campo é correto **e**, em FV,
   confirmar visualmente alinhamento/posição de cada contorno sobre o estrutural
   (`contorno_posicao_sobre_estrutural`), ou se o humano registrar a decisão
   quando a evidência não for suficiente.
5. Se FAIL, formular correção universal, testar um caso representativo e
   retornar a S3/S4; nunca marcar laranja por score numérico.

### S6 — N3 independente

1. Materializar contrato exclusivamente do N1 persistido, gerar DXF individual
   sem headless e produzir SVG/HTML da ficha de motor.
2. Rodar `qa_n3_smoke.py`: nome, identidade, painel/segmento, ordem,
   dimensões, apoios e exceções declaradas devem chegar ao DXF.

### S7 — auditoria QA N3 e retorno controlado

1. Ler N3×N4 e N3×N2 visualmente pelo CLI, com N2/N4 apenas como referências.
2. Se N3 diverge mas S5 provou N1 e o contrato está correto, o achado é do
   gerador/conversão N3: corrigir o motor geral e repetir S6.
3. Se a divergência aponta segmento, apoio, dimensão ou exceção que S5 não
   provou, reabrir S5 — e só então, se necessário, S3/S4. Nunca “ajustar” o
   N3 para imitar N2/N4 sem descobrir a causa.
4. Se houver sinal de dado N2/N4 alimentando N3, registrar
   `vazamento_gabarito` e reprovar a etapa.

### S8 — entrega e validação humana

1. Gerar o pack HTML completo do item, incluindo fichas N1/N2/N3/N4, SVGs-fonte
   do veredito, manifesto e links de triagem.
2. Entregar ao humano a pergunta objetiva “a cadeia inteira está correta?”;
   registrar APROVAR, FAIL ou observação no diário e na triagem.
3. Só depois da confirmação humana, golden e regressão da classe é que o item
   pode ser considerado Arete. O HTML é evidência de entrega, não automação de
   aprovação.

## Caminho rápido, seguro e eficaz

1. Faça primeiro o **probe read-only** do campo já persistido; não rode
   headless para responder pergunta que o DB já responde.
2. Para mudar interpretação, execute uma única rodada canônica limitada por
   `--secao` e `--item`, sempre com `--wait`. O cache content-addressed pode
   reusar o contexto N1, mas não dispensa o motor canônico.
3. Escolha um caso representativo por família geométrica e corrija a causa
   universal; não ataque todos os itens antes da primeira leitura visual.
4. Gere N3 por item e rode smoke/ficha de motor sem headless. Só depois faça o
   confronto visual e uma regeneração canônica quando o N1 mudou.
5. Registre cada tentativa, inclusive hipótese rejeitada. Isso evita repetir
   uma correção já provada insuficiente.

## Modelo mínimo de entrada no diário

```md
## AAAA-MM-DD HH:MM — <obra>/<pavimento> — <item>/<parte>
- Etapa: S4 — N1 evidenciado
- Estado: PASS | FAIL | BLOCKED | PENDENTE
- Fontes: <DXF/DB/ficha/SVG/manifesto/relatório com caminhos>
- Evidência observada: <fato verificável>
- Tentativa/caminho: <motor, regra geral ou probe; nunca hardcode>
- Hipóteses rejeitadas: <por quê>
- Decisão: <o que foi ou não foi promovido>
- Próximo passo: <comando/gate e responsável>
- Não-regressão: <teste, golden, diagnóstico ou N/A justificado>
```

Triagem automática/humana continua em
`scripts/arete/relatorios/triagem_erros/*.jsonl` schema v2. O diário aponta
para o `finding_id`; não duplica nem reescreve esse registro.
