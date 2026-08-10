# PIL — manual granular de interpretação, validação e evolução

## 1. Modelo: volume, faces e relações de viga

PIL é volume geométrico com identidade, dimensão, nível, faces e relações locais.
Para retangulares, A/B são faces longas e C/D curtas; especiais ampliam a leitura
para E–H. `src/core/pillar_face_beams.py` enriquece as faces, e
`src/core/beam_interpreters/pilar_viga.py` mantém contratos exclusivos: **Pilar com
Viga Para** e **Pilar com Viga Passa**.

| Família | Campos/slots | Pergunta que decide | Confusão proibida |
|---|---|---|---|
| identidade/geometria | `name.label`, `points_json`, `pilar_segs`, dimensão | nome, bbox e dimensão descrevem o volume? | nome correto com polígono alheio |
| faces | `p_s{face}_l1_n`, lados e contatos | qual face/canto a relação toca? | assumir A/B em pilar especial |
| PASSA | `passa_esq`, `passa_dir`, interior | eixo continua além das duas faces? | registrar chegada como passa |
| PARA/chega | `viga_que_para`, `viga_que_chega`, aberturas | eixo termina no volume/face? | usar PASSA porque a viga está perto |
| níveis/vazios | topo, altura, níveis e neutralização | vazio/abertura é estrutural e na face certa? | preencher por outra face |
| montagem | CIMA, ABCD, GRADES, sarrafos, parafusos | variante está segregada? | GRADES contaminar CIMA/ABCD |

## 2. Ficha e evidência local/contextual

### 2.0 Visão canónica (obrigatória em N1-V / G2-V / G5-V)

Documento mestre: [`docs/QA-VISAO-EVIDENCIA-CANONICA.md`](../../QA-VISAO-EVIDENCIA-CANONICA.md).

Prova visual de PIL (CIMA, ABCD, GRADES): conteúdo full layers. **Agente = PNG**;
**persist/app/portal = SVG**. Headless sem persist = imagem só. Contagem/score
sem vision = **ruído**. `g2v_harness.py --backend cli` + inventário N2×N4.
`docs/QA-VISAO-EVIDENCIA-CANONICA.md`. Para/Passa ≠ PASS visual.

O pilar deve ser lido face por face. SVG local prova contorno, face, canto, viga e
contato; SVG contextual prova eixo, lajes e vizinhança, mas não cria uma relação. A
ficha granular expõe CIMA, ABCD PARA, ABCD PASSA, GRADES PARA e GRADES PASSA como
partes distintas. O guia `interpretacao_abcd.html` é manual protegido: ler, nunca
editar ou regenerar.

O campo validado é preservado isoladamente. Validar D/PASSA não aprova nem congela
A/B/C, PARA, vazios, aberturas ou GRADES. `pilar_segs` validado preserva geometria e
derivados; o restante sem validação pode ser reanalisado.

## 3. Probes, diagnóstico e score N1×N2

`qa_pil_coverage.py --run-probes` cobre `identity_geometry`, `faces`, `para`,
`passa` e `assembly`. Os probes de face/slot testam uma relação por vez: entidade,
dimensão, rastro e contato cross-classe. PASS local nunca promove o pilar inteiro.

`diagnostico_pil_n1_n2.py` não compara “faces preenchidas” como igualdade: N1/N2
usam semânticas diferentes nesse agregado. Ele alerta dimensão/identidade, mas não
fecha face, canto, chegada, abertura, vazio ou montagem. S5 exige matriz por parte:

1. CIMA: volume, dimensões, nível, topo e apoios.
2. ABCD PARA: face/canto, chegada, abertura e vazio.
3. ABCD PASSA: face, continuidade, lado esquerdo/direito e neutralização.
4. GRADES: quantidade/posição, nunca inferida de ABCD.
5. Score, match/mismatch/N/A e fonte por campo; 0,05 em medidas comparáveis.

```powershell
python scripts/arete/qa_evidence_auditor.py review --project-id <ID> --classe PIL --include-sealed
python scripts/arete/qa_pil_coverage.py --project-id <ID> --item P35 --run-probes
python scripts/arete/qa_profile_probe.py --classe PIL --probe face_beam_identity_dimension_contact `
  --item P35 --var face=D --project-id <ID>
python scripts/arete/headless_sa_analise.py --obra <OBRA> --pav <PAV> --secao pilares --item P35 --wait
python scripts/arete/g2v_harness.py --classe PIL --pav <PAV> --par n1xn2 --item P35 --backend cli
```

N1-V/G4-V (interpretação N1×N2) é lido pelo modelo/agente CLI a partir de SVGs e
manifesto; API visual é proibida. N2 só aponta divergência, não cria face/vínculo N1.

## 4. Casos de diagnóstico e dono do fix

| Sintoma | Evidência decisiva | Dono provável | Teste negativo |
|---|---|---|---|
| PASSA mas termina | eixo/contato e continuidade além das faces | `pilar_viga` | chegada em face curta |
| chegada na face errada | overlap/canto e SVG local | `pillar_face_beams` | outra face sem contato |
| dimensão no slot errado | trace e dimensão canônica da viga | materialização de face | nome em slot de dimensão |
| vazio/abertura duplicado | parte PARA/PASSA e face/canto | contrato PIL | vínculo em dois slots |
| GRADES em ABCD | variante e camadas N3 | gerador/contrato PIL | GRADES N/A isolado |
| falha multi-contrato desde eixo | captura de topologia comum | `BeamTracer` | regressão FV/LV/LAJ |

## 5. N3 e gates finais

N3 possui `CIMA`, `ABCD_PARA`, `ABCD_PASSA`, `GRADES_PARA` e `GRADES_PASSA`. Gerar
só a variante suspeita, rodar `qa_n3_smoke.py`, abrir `ficha_motor_item.py` e depois
G5 (paridade final N3×N4) / G5-V via SVG e CLI. Smoke confirma identidade/texto/camada;
não prova abertura, vazio, anticolisão, face ou grade. Igualdade por herança N2/N4 é
`vazamento_gabarito`.

Após mudança PIL: teste de face afetada, exclusão PARA/PASSA, cobertura das cinco
famílias, microciclo, diagnóstico PIL e N1-V. Mudou `BeamTracer`: regressão das quatro
classes. Diário: `docs/SA-ANALISE/HISTORICO/PIL.md`.

## 5.1 Leitura visual N3×N4 (G2-V/G5-V) — padrões do robô SCR (não confundir com bug)

Consolidado em 2026-07-16 após leitura visual real de P1/P2/P35 (G2-V/G5-V CLI)
gerar achados falsos por desconhecimento do desenho. Confirmado no código do
gerador (`scripts/gerar_pl_dxf_stog.py`, `scripts/pl_abcd_visual_nova.py`) e no
robô SCR legado (`_ROBOS_ABAS/Robo_Pilares/`):

- **Sarrafo C/D ≥ 30cm vira horizontal + texto de contagem.** Faces C/D com
  dimensão ≥30cm não desenham cada sarrafo individual — desenham só o do fundo
  e o do topo e escrevem a quantidade total em texto (`"9 sarr."` + `"2 sarr."`
  para o caso normal, `"6 sarr."` sozinho no caso curto). Código:
  `gerar_pl_dxf_stog.py:1527` (`is_horiz = fid in ('C','D') and concrete_dim >= 30`)
  e `:2001-2014` (os textos). **Ver isso numa face C/D não é falta de dado —
  é a otimização esperada.**
- **Hachura rosa de topo = vazio/abertura, não o painel.** O pattern `AR-CONC`
  (layer `COTA`, cor 241 rosada) hachura o **vazio/abertura** no topo do
  painel — `pl_abcd_visual_nova.py::draw_void_hatches`. **Correção
  (2026-07-16, ordem do dono): N3 E N4 devem ter essa hachura — não é
  exclusiva do N3.** Se o N4 não tiver, é um gap real do gerador a garantir
  daqui pra frente; mas **N4s já selados/validados não são regenerados
  retroativamente por causa disso** — o gap fica registrado como pendência
  de geração futura, não motivo pra reabrir selo já fechado. **Se o N4 tiver
  hachura BRANCA preenchendo o painel em si (não o vazio), aí sim é erro** —
  painel nunca deveria ter hatch próprio. Reaproveitamento de hachura de
  painel entre variantes é feature futura, **compreensão pendente** — não
  investigar/cobrar isso ainda em G2-V/G5-V.
- Consequência prática pro agente QA: ao ler SVG de G2-V/G5-V (N1-V não se
  aplica aqui — os cards N1 são geometria bruta do SA, sem ABCD/sarrafo/
  hachura; ver `docs/SA-ANALISE/HISTORICO/PIL.md`, entrada 2026-07-16), se o N4
  não tiver a hachura de vazio que o N3 tem, registrar como achado real
  (gap de geração), não descartar — mas também não bloquear/reabrir selo já
  fechado por causa disso; é pendência de melhoria de gerador, não motivo
  de FAIL retroativo. Sarrafo individual sumindo em C/D ≥30cm (virando
  contagem em texto) continua sendo comportamento esperado, não achado.

## 6. Autoevolução e candidato RAG PIL

Para cada BLUE/laranja, registrar subtipo do pilar, face/canto, PARA/PASSA, vazio,
abertura, nível e variante CIMA/ABCD/GRADES, incluindo contraexemplo de exclusão. O
HTML/SVG aprovado vira candidato RAG multimodal por **face e variante**, não por pilar
inteiro sem granularidade. Ao fechar os laranjas PIL do pavimento, consolidar cobertura
das cinco famílias e solicitar validação humana para futura curadoria RAG PIL.

## 7. Quadro de estado por pavimento (read-only)

`scripts/arete/qa_pil_quadro_pavimento.py` → `QUADRO-PIL-PAVIMENTO.{html,json,csv,md}`
(2026-07-16, primeira versão validada em 13_PAV/Obra_TREINO_1, 46 pilares reais).
Segue `docs/QA-QUADROS-ESTADO-POR-CLASSE.md`: read-only, nunca alimenta N1/N3, nunca
grava selo, regenerado ao fim de todo microciclo que produza/leia evidência nova.

### Fonte das decisões

O quadro **não reimplementa regra nenhuma**: instancia `PilEvidenceAuditor` (o mesmo
adaptador CAD independente de `qa_evidence_auditor.py`) em memória, com
`load_pillars`/`load_beams_for_project`/`load_slabs` do DB real, e lê as `Decision`
resultantes — a mesma leitura que `qa_evidence_auditor.py review` produziria. Não
executa headless, não gera DXF, não grava no banco. Isso é o que torna o quadro
"sem-headless" na rota de `docs/MASTERPLAN-AGENTE-QA-GLOBAL.md`.

### Colunas (ordem)

`Etapa atual/próximo passo` → `Item` → `N2 — ficha` → `N2 — campos (comparação)` →
`N4-PARA deste item` → `N4-PASSA deste item` → `N1 — geometria/polígono` →
`N1 — campos/vínculos` → `N1-V CLI — validação visual da interpretação N1` →
`Ficha N1×N2` → `N3-PARA — smoke` → `N3-PASSA — smoke` → `Ficha N3-PARA×N4` →
`Ficha N3-PASSA×N4` → `Ficha N3-PARA×N2` → `Ficha N3-PASSA×N2` →
`Selos N1 do item` → `Selos N3 do item` → `R1 — RAG multimodal` (2026-07-16).

`R1` segue o contrato já registrado em `docs/QA-QUADROS-ESTADO-POR-CLASSE.md`
(seção comum a todas as classes, mesmo schema/arquivo — não é invenção
isolada do PIL): depois de todas as validações do agente QA de um item, o
HTML completo pode entrar no contexto RAG local como evidência **T0**. O
registro é append-only em
`scripts/arete/relatorios/qa_evidencias/rag_html_ingestoes.jsonl`, schema
`arete.qa_rag_html_ingestion/v1` (`project_id`, `obra`, `pavimento`, `classe`,
`item`, `html_path`, `html_sha256`, `qa_run_id`, `status`
`INGESTED_T0|T1_PROMOTED`). O quadro só mostra `SIM` quando caminho e hash
estão de fato registrados — nunca infere ingestão por proximidade de item ou
run. **R1 não é gate Arete, não cria selo e jamais alimenta N1/N3.** T0 é
rastreável mas não é memória confiável; T1 ainda exige curadoria humana. O
mecanismo que efetivamente grava essa entrada (ingestão em si) é um passo
separado do quadro — read-only aqui, só lê o log.

**`N1-V CLI` não é comparação de fichas** (isso é a coluna seguinte, `Ficha
N1×N2`, diagnóstico automático de dimensão/faces). `N1-V CLI` é a validação
**visual** da própria interpretação N1: o agente CLI lê a ficha N1 junto das
imagens de contexto do SA (próxima e distante, como já aparece na ficha HTML) e
confirma, item a item, o checklist real do `g2v_harness` (9 itens:
`fonte_atual_confirmada`, `recorte_alvo_preciso`, `contorno_area_interna`,
`cotas_valores`, `cotas_posicao_legibilidade`, `linhas_paineis`, `hlaz`,
`hachuras_apoio`, `sem_contaminacao_vizinha`). Só o agente faz essa leitura —
por isso só existe selo **Laranja** aqui (nunca azul/rosa/verde); a célula
mostra `X/9` confirmados, não um veredito único.

`Selos N3 do item` fecha a tabela mostrando os 4 selos (azul/laranja/verde/
rosa) do N3, lidos de `artifact_validation_policies` `scope='N3'` — hoje
sempre zerado (`n3_policy_rows=0`), o mesmo tipo de estado honesto já visto
em N4.

**N4 e N3 têm PARA/PASSA por motivos opostos, por isso cada um virou 2 colunas:**
- **N4** nasce de UMA ficha N2 só; nenhum gerador (`ficha_adapter.py`,
  `gerar_n4_item.py`, `gerar_pl_dxf_stog.py`) tem ramo PARA/PASSA — produz 1 DXF.
  `N4-PARA` é **sempre** `➖ N/A` por construção (não calculado por item); só
  `N4-PASSA` carrega dado real (política N4, G2 do lote, G2-V n2×n4).
- **N3** nasce só do N1 (SA), e o pipeline (`PreValidationDialog.
  materialize_pl_n3_variants`) sempre gera as duas variantes pra comparar
  qual convenção de desenho bate com o real — por isso `N3-PARA`/`N3-PASSA`
  têm status **independentes**, cada um lido dos checks `abcd_para.*`/
  `abcd_passa.*` do `qa_n3_smoke_*.json` (o campo `overall` do relatório é
  combinado e não serve pra distinguir as duas).

`N4-PASSA` mostra os 2 selos que N4 admite (Azul=humano/app, Laranja=QA agente)
sempre separados — nunca um SIM/NÃO combinado, pra saber exatamente qual dos dois
o item tem (N4 nunca tem verde/rosa, que são de N1/N3).

`N1 — geometria/polígono` é a família **travada**: só cobre `pilar_segs`; uma vez
`CONFIRMAR` e presente em `validated_fields_json`, o quadro marca 🔒 "geometria
aprovada — não é substituída em reanálise" (nunca reescrita por um novo microciclo),
com os 3 selos possíveis (Azul/Laranja/Rosa — qualquer origem serve) para este
único campo, ex. `🔵 Azul 0/1 · 🟠 Laranja 1/1 · 🌸 Rosa 0/1`.

`N1 — campos/vínculos` virou (2026-07-16) um resumo **quantitativo** de cobertura
de selo, não mais descrição campo a campo: `Total de campos analisados: N` +
`Azul X/N`, `Laranja Y/N`, `Rosa Z/N`. Os campos contados são só os que o
adaptador realmente audita e pode selar — `dim`, `name`, `connections` e,
por face presente, `p_s{face}_l1_n`/`p_s{face}_v` (retangular típico = 11).
Nível (`extra.level`) e convenção NASCE/MORRE/SEGUE (`extra.classification`)
ficam **fora da contagem**: não têm `_audit_*` dedicado, exibição crua em nenhuma
coluna hoje. Visão/corte (smoke) e continuidade entre pavimentos também saíram
desta célula — smoke virou colunas próprias (`N3-PARA`/`N3-PASSA`, ver acima) e
continuidade segue fora de escopo. Qual campo específico ainda falta aparece em
`Etapa atual/próximo passo`, não mais aqui — a célula responde só "quanto já foi
selado", não "o quê".

Uma decisão `CONFIRMAR`/`N/A_CONFIRMADO` com `operations` ainda não vazio (isto é,
resolvida pelo adaptador mas não persistida por `apply`) não soma no selo — só
`apply` roda e grava origem em `validated_fields_json` conta pra `X/N`. Isso evitou
um falso "tudo pronto" no P35 antes de rodar `apply` (10/11 laranja; só
`p_sD_l1_n` ainda pendente de aplicar).

### Achado real capturado na primeira execução (2026-07-16)

Ao gerar o quadro, `p_sD_l1_n` de P35 apareceu `N/A_CONFIRMADO` (não mais
`PENDENTE`): investigação paralela do dono corrigiu o link stale `L325`
(dist=556cm > tol=15cm) para `"SEM LAJE"` no DB
(`source: qa_geometric_fix_2026-07-16`), documentando o valor anterior. P35 está a
um `apply` de selar 100% dos campos obrigatórios — o quadro mostra exatamente esse
estágio (`S5 — aplicar decisões já resolvidas: p_sD_l1_n`), sem inferir o selo antes
da persistência real.

Segundo achado (mesmo dia): a coluna `N2 — ficha` inicialmente lia só
`reverse_eng_fichas.status/aprovado_at` — e **as 906 fichas do banco inteiro**
(todas as classes, todas as obras) estão em `draft`/`extracted`; esse campo nunca
foi usado neste projeto. O aceite humano real acontece no RECORTE, via
`_on_aprovar`/`_on_aprovar_auto` de `src/ui/modules/diagnostic_reverse_hub.py`,
persistido em `reverse_eng_recortes.status` (`'aprovado'`/`'auto_aprovado'`), uma
tabela sem coluna de pavimento — o casamento correto é por `recorte_path` exato
(idêntico entre as duas tabelas), não por `projeto_id` (que em `reverse_eng_recortes`
está órfão/desalinhado da tabela `projects` real). Corrigido: `_n2_ficha_status`
agora cruza as duas fontes; 35/35 fichas PIL do 13_PAV aparecem com recorte
aprovado manualmente, e os 11 pilares sem ficha (`NASCE`) continuam honestamente
"sem ficha N2 persistida".

### Limitações declaradas (não escondidas)

- `artifact_validation_policies` não tem nenhuma linha `classe='PIL'` nesta obra/
  pavimento (`n4_policy_rows=0`): o card N4 aparece zerado honestamente — não há
  ainda workflow de decisão humana/QA via política N4 para PIL.
- G2-V/N1-V de PIL ainda usam captura PNG (`fonte_imagem == "html_ficha"`); nenhum
  relatório `fonte_imagem == "html_svg_vetorial"` existe para PIL até 2026-07-16 —
  o pipeline SVG-vetorial (o único com autoridade plena, per regra do dono) ainda
  não foi implementado para esta classe. O quadro expõe o veredito existente com a
  ressalva explícita em vez de tratá-lo como equivalente ao contrato SVG atual.
- `pillars` desta `project_id` tem 46 linhas; o golden Arete (`STATUS.md`) considera
  35 itens PIL no 13_PAV. A diferença (11 = itens `NASCE`) não foi explicada nem
  reconciliada por este quadro — reportada como está, sem inferir causa.
- Validado contra 3 topologias reais: P35 (SEGUE/INDETERMINADO — para+passa+interior+
  chegada nas 4 faces), P1 (MORRE, 3 faces `REVISAR_HUMANO` reais por viga sem
  evidência geométrica) e P41 (NASCE, 5 relações confirmadas, nada aplicado ainda).
