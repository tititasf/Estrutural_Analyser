# QA — Quadros de Estado por Classe e Pavimento

## Finalidade e limite

Cada quadro é um produto **read-only** de acompanhamento por obra, pavimento, classe e item.
Ele orienta o próximo microciclo, mas nunca é fonte para N1/N3, gerador, comparador,
aprovador ou mecanismo de selo. O estado vem apenas do DB e de artefatos canônicos já persistidos.

O produto de cada classe é HTML, JSON, CSV e Markdown. A primeira coluna é
`Etapa atual / próximo passo`; as demais seguem a execução real. A cor de cada coluna
identifica a etapa; a primeira coluna recebe a cor da próxima evidência necessária ao item.

## Regra obrigatória de atualização

O QA regenera o quadro da classe/pavimento ao encerrar microciclo que produza ou leia nova evidência persistida:

1. `discover` ou `review`;
2. decisão humana ou agentic em N2, N3 ou N4;
3. materialização N1 pelo headless canônico, seguida de probe/review;
4. diagnóstico N1×N2, smoke N3, comparação de ficha ou veredito visual CLI;
5. correção de motor com teste/regressão que mude estado observável.

A regeneração é posterior à persistência e somente leitura: não executa headless, não cria DXF,
não roda gate e não grava selo. O handoff sempre aponta HTML atualizado, itens tocados,
próxima etapa por item e log append-only. Todos os selos laranja de uma classe/pavimento exigem
revisão humana antes de promoção para RAG.

## Cobertura e nomes de destino

| Classe QA | Motor/HTML | Estado | Particularidade |
|---|---|---|---|
| FV | `qa_fv_quadro_pavimento.py` → `QUADRO-FV-PAVIMENTO.html` | Implementado | segmentos, contorno, apoios, recortes, N1/SA e painéis N3 |
| LV | `qa_lv_quadro_pavimento.py` → `QUADRO-LV-PAVIMENTO.html` | A implementar | separar A/B e `Para`/`Passa`; FV nunca é fallback semântico |
| PIL | `qa_pil_quadro_pavimento.py` → `QUADRO-PIL-PAVIMENTO.html` | Implementado (2026-07-16) | geometria (polígono, travada) isolada de campos/vínculos (seção, nível, convenção, faces, vigas/lajes, corte, continuidade); ver `docs/SA-ANALISE/CLASSES/PIL.md` §7 |
| LAJ | `qa_laj_quadro_pavimento.py` → `QUADRO-LAJ-PAVIMENTO.html` | A implementar | geometria, corte, níveis, apoios e interferências próprios |

FV e PIL têm motor materializado hoje. Os outros nomes são contrato de implementação;
não se afirma que seus HTMLs existem antes de testes próprios.

## Ordem comum de colunas

Depois de `Etapa atual / próximo passo` e `Item`:

```text
N2 recorte/ficha validada
→ N4 gerado e decisão humana/QA
→ N1 / SA: estrutura interpretada
→ N1 / SA: topologia/geometria + campos com origem
→ N1-V (veredito visual SVG via CLI/modelo CLI)
→ ficha N1×N2 (comparação diagnóstica)
→ N3 gerado somente de N1: smoke + selos
→ ficha N3×N4 (comparação)
→ ficha N3×N2 (comparação diagnóstica)
→ R1 RAG multimodal: HTML pós-QA com hash e ingestão registrada
```

N2/N4 apenas comparam: nunca alimentam N1/N3. N4 mostra apenas 🔵 humano-app e 🟠 QA agentic.
A política N4 aprovada pode projetar azul/laranja em N2 para leitura, sem regravar a ficha N2.
N1 e N3 possuem quatro selos de item; campos N1 obedecem às origens permitidas pelo perfil.
G2 (paridade canônica) e G2-V (veredito visual CLI) pertencem ao N4, não viram cards separados.

**R1 não é gate Arete e não cria selo.** Após as validações do agente QA, o
HTML completo do item pode entrar no contexto RAG local como evidência T0. O
registro append-only é `scripts/arete/relatorios/qa_evidencias/rag_html_ingestoes.jsonl`,
no schema `arete.qa_rag_html_ingestion/v1`, com `project_id`, obra, pavimento,
classe, item, caminho do HTML, SHA-256, `qa_run_id`, data e estado
`INGESTED_T0|T1_PROMOTED`. O quadro só mostra ✓ quando caminho e hash estão
registrados. T0 é rastreável, mas não é memória confiável; T1 ainda exige a
aprovação humana de curadoria. A ingestão jamais pode alimentar N1/N3.

## Prompt-base para o agente

```text
Use $qa-global-evidencias.

Escopo exclusivo: obra {OBRA}, pavimento {PAV}, project_id {PROJECT_ID},
classe {CLASSE}, itens {ITENS ou próximo lote de 5}. Trabalhe item a item.
Leia CLAUDE.md, MASTERPLAN-AGENTE-QA-GLOBAL.md,
QA-QUADROS-ESTADO-POR-CLASSE.md e docs/SA-ANALISE/CLASSES/{CLASSE}.md.

1. Abra/regere em modo read-only o QUADRO-{CLASSE}-PAVIMENTO do escopo. Use-o só
   para escolher o próximo item/etapa pendente; nunca como fonte N1/N3.
2. Consulte DB, ficha N1, DXF/origem, SVGs, vínculos e apenas fontes cross-classe
   permitidas pelo perfil. N2/N4 são comparação, nunca entrada N1/N3.
3. Faça o menor microciclo canônico: probe/review; se houver fix geral, teste puro,
   headless da classe com --wait, nova probe e regressão. Sem hardcode.
4. Gates visuais usam SVG e g2v_harness --backend cli; API visual e PNG não são usados.
   Registre PASS/FAIL/SUSPEITO com proveniência, não por score numérico.
5. Após persistência, regenere HTML/JSON/CSV/MD, atualize o diário da classe
   (item, etapa, fontes, decisão, achado, confiança, comando, regressão e próximo passo)
   e entregue o link do HTML atualizado.
6. Pergunte somente por impasse real: observação, fontes, tentativas, hipóteses rejeitadas,
   impacto e pergunta objetiva.
```

## Especialização por classe

### FV — Fundos de viga

`PIL` pode ser lido apenas para provar apoios; `LV` nunca completa FV. Por segmento,
provar polígono/contorno local, início/fim, comprimento/largura, apoios, altura/seção,
furos, recortes e continuidade contextual. Comprimento é extensão geométrica, nunca soma de linhas.
N2 pode revelar multiplicadores/painéis apenas como comparação; não cria segmento N1.

O quadro FV divide explicitamente a validação N1 em duas colunas, ambas com
marcação por origem de campo: 🔵 humano-app, 🟠 QA agente e 🌸 humano-portal.
Essas três validações empilham no mesmo campo, mas uma origem nunca completa o
selo da outra.

1. **S3 — geometria por segmento.** Para cada `S<i>`, exige
   `viga_fundo_seg_<i>_area_segs` (contorno/links da área) e
   `viga_fundo_seg_<i>_dim` (dimensão C×L rastreável). A coluna só mostra
   `Validação S3 geometria: SIM` quando **todos** os segmentos têm os dois
   campos validados; uma ficha N1/N2 emitida recebe ✓ de disponibilidade, mas
   não sela geometria sozinha. Havendo N2, o 🟠 exige também diagnóstico N1×N2
   de quantidade e medidas dentro de 0,05 cm e N1-V `PASS`, lido pelo
   modelo/agente CLI nos SVGs N1 local e contextual. N2 compara; nunca cria
   segmento, contorno ou selo N1.
2. **S4 — item FV completo.** Fecha apenas o restante específico de fundo:
   identidade/quantidade (`name`, `viga_count_c`) e, para cada segmento,
   `local_ini` e `local_fim` (apoio/extremidade e continuidade). A coluna só
   mostra `Validação S4 item FV: SIM` quando a cobertura inteira existe. Ela
   não mistura ou substitui a aprovação geométrica de S3.

`✓` no relatório significa evidência daquela linha/etapa já persistida; `○`
significa pendente/ausente; `×` é FAIL/divergência realmente registrada. O
relatório não cria o 🟠: o QA grava `qa_agente` somente depois da cadeia N1
original → comparação permitida N2 → SVG local/contextual via CLI estar provada.

### LV — Laterais de viga

Tratar A Para, B Para, A Passa e B Passa como quatro partições do quadro LV.
Cada linha declara lado, convenção, continuidade/terminação, dimensões e recortes da face.
FV não é fallback semântico. PIL/LAJ são apenas consulta permitida pelo perfil LV.

### PIL — Pilares

Cada face e campo geométrico tem validação isolada: polígono, seção, dimensão, nível,
convenção nasce/passa, vigas/lajes adjacentes, corte e continuidade. Geometria aprovada
não é substituída em reanálise; só campos/vínculos ainda não validados podem ser reescritos.
O quadro separa face/geometria das famílias de campo.

### LAJ — Lajes

Geometria, níveis, espessura, corte, apoios e interferências têm validação própria.
Provar contorno, furos, recortes, nível e espessura antes de relações. Proximidade nunca
substitui a geometria isolada. O quadro separa corte e cada família de campos antes de N3.

## Critério de implementação de novo quadro

Antes de declarar uma classe pronta: motor dedicado, teste contra snapshot real,
HTML/JSON/CSV/MD, três topologias próprias e diário `docs/SA-ANALISE/CLASSES/<CLASSE>.md` atualizado.
Só infraestrutura de relatório (cores, etapas e serialização) pode ser reutilizada;
campos, tolerâncias e regras semânticas não atravessam classes.
