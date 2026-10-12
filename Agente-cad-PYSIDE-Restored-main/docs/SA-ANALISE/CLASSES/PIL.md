# PIL — manual granular de interpretação, validação e evolução

## 1. Modelo: volume, faces e relações de viga

PIL é volume geométrico com identidade, dimensão, nível, faces e relações locais.
Para retangulares, A/B são faces longas e C/D curtas; especiais ampliam a leitura
para E–H. `src/core/pillar_face_beams.py` enriquece as faces, e
`src/core/beam_interpreters/pilar_viga.py` mantém contratos exclusivos: **Pilar com
Viga Para** e **Pilar com Viga Passa**.

Na medição independente do QA, respeitar a orientação das tabelas: pilar
vertical usa A oeste, B leste, C norte, D sul; horizontal usa A sul, B norte,
C oeste, D leste. As distâncias esquerda e direita seguem o sentido local da
face (`pillar_abcd_tables._face_axis_span`); comparar ambas individualmente,
sem ordenar os valores e ocultar uma inversão. Contatos `interior` também
exigem medição; `passa` exige prova própria de corredor/canto e não pode receber
a aprovação de um contato `chega`. Nome da viga e seção devem ter associação
comprovada ao mesmo trecho original. Uma linha de cota ou corte atravessando a
faixa não é, por si só, apoio estrutural ou fim de vão. Ausência dessa prova
mantém o caso incerto, sem apagar o vínculo nem declarar divergência por uma
seção de outra viga.

Uma seção numérica dentro da faixa também pode pertencer a um pilar. Confirmar
o papel do texto e seu alinhamento ao eixo da viga antes de atribuí-lo: no caso
auditado, `19/50` horizontal de um pilar aparecia na faixa de uma viga vertical
cuja seção própria `19/55` também estava no desenho. Contorno próximo, largura
compatível e nome de viga na faixa não tornam esse número uma seção da viga.

**Jev opcional:** em dúvida de face/vínculo após topologia CAD, consultar por
candidato e face com handle e contato local; dimensão retangular simples segue
pela geometria. Ver [segunda leitura do SA](../JEV-SEGUNDA-LEITURA-OPCIONAL.md).

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
- Consequência prática pro agente QA: ao ler a evidência (PNG/SVG) de G2-V/G5-V (N1-V não se
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


### Consolidação de níveis — 2026-10-01

Regra integrada: `docs/INTERPRETACAO-NIVEIS-POR-REGIAO-E-SEGMENTO.md` (canônico). Topo final = maior nível válido de região de laje ou viga em contato real com a face. Exibir face(s) do contato mais alto e nível final; base em coluna separada. Região interna não certifica a face que toca a principal. Fonte estimada de viga não vira medida no pilar; nascimento no pavimento seguinte conserva Não se aplica.

**PIL-MULTILAJES-POR-FACE-20261009 (dono):** uma face admite vários contatos de laje, inclusive principal e região de outra espessura/nível ou contatos separados por viga que chega. Cada trecho conserva nome, região, início/fim em cm desde o canto da face, distâncias aos dois cantos, largura de contato, espessura e nível próprios com proveniência. Medir pelo contorno real, nunca unir contatos desconexos pela caixa envolvente. Não exigir uma ou duas linhas por face; conferir intervalos e contatos reais. Ausência de nível não é zero; espessura diferente não prova altitude diferente. O N3 deve reproduzir cada contato e conservar sua identidade ao salvar/regenerar, sem atribuir o primeiro nome/nível da face aos demais. O suporte de dados e a certificação do desenho N3 são verificações distintas.


### Desenho N3 Nova dos pilares especiais — 2026-10-03

Padrões visuais aprovados do CIMA em L e das prévias U_v10/T_v11: [PADRAO-NOVA-PILARES-ESPECIAIS-CIMA.md](../../PADRAO-NOVA-PILARES-ESPECIAIS-CIMA.md). A geometria deve derivar do contorno SA e conservar a identidade das faces; dimensões do exemplo não são constantes. A aprovação visual das prévias U/T pelo dono em 2026-10-03 não certifica sua integração ao N3: continuam obrigatórios os gates de integração, regressão e conferência visual. Este vínculo documenta o contrato, sem afirmar integração dos protótipos ao gerador de produção.


### Referência padrão e treino de exceções — NIV-PADRAO-EXCECAO-20261003

Aplicar o contrato global em `docs/INTERPRETACAO-NIVEIS-POR-REGIAO-E-SEGMENTO.md`, seção Referência padrão e exceções explícitas. O padrão confirmado é topo da viga no nível principal da laje ou base de saída do pavimento quando não há laje, salvo indicação explícita diferente. Ausência de corte não torna esse padrão uma estimativa por si só. Preservar regiões de laje, datum da viga, contato por face do pilar e fontes independentes. QA distingue convenção de medida e verifica qualidade/cobertura da leitura antes de confirmar; não elevar score apenas renomeando status. Interpretação de vigas em níveis diferentes por hatch/corte está pendente de treino com exemplos reais futuros; não foi certificada neste caso.


## Apresentação N3/N5 por modo — 07/10/2026

INI, NOVA e Formascia têm padrões de desenho distintos sobre o mesmo contrato estrutural. Consultar a [matriz canônica de desenho](../../PADROES-DESENHO-N3-N5.md) e o [padrão INI aprovado](../../PADRAO-INI-APROVADO.md). A aprovação visual não altera os dados SA nem certifica automaticamente todos os itens. LAJ INI compartilha o N3/perfil NOVA; os compositores N5 continuam separados.


## Segunda passada por convenção independente — 2026-10-08

Depois da busca inicial, comparar candidatos do CAD fonte com dimensões junto ao nome, camada semântica e convenção recorrente entre candidatos dimensionados. Recorrência é preferência, nunca veto a uma forma minoritária. Excluir peças comprovadas de corte ou viga; não usar a associação SA anterior como prova de classe. Garantir posse única da geometria; empates continuam sem decisão. Preservar contornos aprovados por humano. Duas etiquetas próximas podem corresponder a duas geometrias distintas: não duplicar uma fonte.

Contorno especial preserva concavidade e vazio. O U observado em P12/TIPO_TESTE não é um retângulo envolvente nem um T. A segunda passada recuperou nove associações de contorno nessa obra; nomes e coordenadas são exemplos de validação, não constantes do reconhecedor. Módulo: `src/core/pillar_geometry_association.py`. Evidência: `scripts/arete/relatorios/20261008_pilares_associacao/`.

Circular permanece listado no SA com centro, raio, diâmetro, perímetro e área derivados do círculo. Registrar contatos com vigas e ângulo no plano CAD (0° no eixo +X, sentido anti-horário), identificando fonte e possível sobreposição. Contato derivado de fundo publicado precisa ser revisto se esse fundo mudar. P21 tem diâmetro 60 e nenhum contato na validação atual. Métodos N3/CIMA/ABCD e N5 circulares ainda não implementados: excluir somente sua geração, sem bloquear os demais pilares ou criar ficha retangular fictícia. Geometria reconhecida não confirma automaticamente níveis ou toda a ficha SA.

## ESTILO-INTEGRADO-20261008 — harmonização entre classes

Síntese vigente, convenções recorrentes, contraprovas e pendências: [Estilos estruturais — interpretação integrada](../../CONHECIMENTO/ESTILOS-ESTRUTURAIS-INTERPRETACAO-INTEGRADA.md). Consultar a evidência local antes de aplicar a regra a outra obra; cooperação entre classes não constitui prova circular nem aprovação automática.

### PIL-DETALHE-AMPLIADO-CONTEXTO-20261010 — moldura e informação interna

Esclarecimento do dono: a moldura da prancha pode conter a planta estrutural e
detalhes ampliados. Classificar seu contorno como moldura não autoriza excluir
o conteúdo interno. O detalhe do pilar é uma região de evidência útil para a
pré-interpretação e o SA, vinculada ao pilar da planta; não é outro pilar físico.
Preservar região, revisão da fonte, entidades originais, legenda, cotas e
transformação entre desenho e dimensão física. Cada recorte precisa ter consumo
comprovado; existir no detector ou em um JSON não comprova esse comportamento.

Caso confirmado no 14_PAV: contornos 3AD/3AE envolvem planta e detalhe; 3AF é o
detalhe ampliado P26=P27, legenda C78 e escala impressa C77. Geometria DXF
330/436/38 e cotas 165/218/19 são grandezas diferentes; não converter apenas
pela inscrição 1:25. O vínculo deve conservar os dois pilares canônicos e
confrontar suas dimensões, sem duplicar o inventário nem inventar níveis.
Essa confirmação é específica da fonte SHA256
`76144cb3c77586684c8db76311fe1ef3cadeef6389e003b948ac7c57c41e2e27`;
os handles não são uma regra geral para outras revisões.

Verificação inicial de 10/10: o detector atual separa essa região de detalhe no replay
do estrutural limpo. Porém o contexto fresco consumido contém 3AF como candidato
ambíguo P47 dentro da torre; o `detalhes.dxf` consumido não contém P26=P27 e não
há corte vinculado ao detalhe. Portanto o consumo desse caso está pendente.
Prova: `scripts/arete/relatorios/20261010_encontros_niveis_14pav/desenvolvimento_rapido/integracao_v408_identidade/detail_crop_behavior_receipt.json`.

Implementação posterior: regiões derivadas do
mesmo DXF preservam os arquivos de produção. O adapter só autoriza um detalhe
quando há legenda explícita e única, contorno canônico correspondente e cadeias
originais de cotas completas. Cada cadeia exige traço da dimensão, marcas nas
pontas, extensões até os vértices e texto numérico alinhado; razões desenho/cota
precisam concordar nos dois eixos. Números próximos ou a escala impressa não
bastam. Ausência ou conflito mantém o candidato sem autorização.

O consumidor confere essas medidas contra os contornos efetivamente produzidos
pelo SA, com revisão e handles originais no recibo. Dono ausente/ambíguo, revisão
diferente ou divergência geométrica bloqueiam o ciclo rápido. A comparação não
reescreve a geometria N1 nem cria níveis. O contorno ampliado só perde o papel
de candidato da planta com prova de contorno e identidade originais; pilares
canônicos têm prioridade. O replay não substitui pré + SA + pós-QA frescos nem
o controle de regressão. Evidência local:
`proved_detail_consumption_replay.json`, na mesma pasta do recibo anterior.

Nova rodada completa `cycle14-detail-ready-20261010`: após instalar a
dependência ausente do detector no runtime SA da VPS, o recibo de consumo
registrou `checked` para P26 e P27, com cotas e entidades originais. O contorno
3AF deixou de exigir base/topo como falso P47: quatro ocorrências removidas,
nenhuma ocorrência adicionada frente à rodada anterior. Nenhum DXF original
foi alterado e não houve renderização ou publicação. A missão continua com
354 ocorrências; este resultado comprova o consumo do detalhe, não a aprovação
integral do pavimento. Erro de detecção agora bloqueia o ciclo em vez de ser
interpretado como inventário vazio.
Recibo: `detail_ready14_cycle_report.json`, na mesma pasta dos anteriores.
Controle fresco 13_PAV: `detail_ready13_cycle_report.json`, 347 ocorrências
pendentes e zero regressões contra a referência original, isolamento aprovado
e sem renderização/publicação. Essa fonte não forneceu detalhe com prova
suficiente; a integração não impôs vínculos a candidatos não comprovados.

### PIL-CORREDORES-LOCAIS-E-FACES-FISICAS-20261010

Rastreio das duas chamadas reais de enriquecimento na mesma rodada comprovou
que retângulos finais 19/55 produzidos pelo reparador de largura eram excluídos
pela ausência de uma marca própria do produtor LV. A seleção agora aceita toda
proposta retangular tipada de fundo, mas somente a confirmação das duas paredes
no DXF original disponibiliza o corredor. No ciclo completo `width-qa-20261010`,
P34 voltou a ter os seis vínculos locais 19/55, sem alterar a fonte ou publicar.
A seleção de candidatos não aprova identidade nominal nem os encontros restantes.

Contatos interiores retangulares devem medir folgas nos trechos locais com
paredes confirmadas, não no bbox acolchoado do traçado. Replay real P34 mede
0/0 nas faces curtas; testes negativos preservam ausência de prova quando não
há corredor verificado. A mudança ainda requer rodada completa após integração.

Pilares ortogonais em L com seis faces usam planos derivados do contorno fechado
original, após correspondência única de vértices. As distâncias novas seguem
o sentido p0→p1 da face física, incluindo reflexões e rotações. Intervalos novos
explicitam essa origem; dados antigos sem marcador preservam sua convenção.
O QA revelou a inversão no P26A e o replay corrigido mede 0/199 tanto no SA como
no original. Passa em contorno especial continua exigindo prova própria do canto,
sem certificação por bbox. Receipts `width_qa14_validation_receipt.json` e
`special_face_direction_receipt.json` conservam os limites de cada prova.

### PIL-IDENTIDADE-POR-CAMINHO-ORIGINAL-20261011 — aprendizado e limites

Identidade nominal, seção numérica local e distância na face são provas
distintas. Um caminho nominal pode atravessar vãos sem repetição de seção,
desde que ambas as paredes originais sejam contínuas no mesmo eixo e largura,
e cada lacuna seja um único apoio fechado com nome e dimensões comprovados.
O vão medido conserva sua própria seção numérica; o caminho não transporta
altura, nível ou folga de outro vão. Seção explícita contraditória, parede
ausente, deslocamento de eixo, concorrência nominal e apoio não comprovado
continuam vetos. Moldura comprovada perde apenas o papel de apoio; seu conteúdo
permanece evidência. Posse do apoio pode usar a extensão real do texto original,
com dimensões, orientação e unicidade, em vez de só o ponto de inserção.

Replay local dos snapshots físicos: 14_PAV passou de 58 para 106 contatos
medidos e 13_PAV de 65 para 103, sem alterar fonte ou estado. Isso não aprova
o pavimento: divergências numéricas e pendências continuam independentes.
157 testes passaram; recibo `pil_nominal_bbox_path_finish_receipt.json` em
`scripts/arete/relatorios/20261010_encontros_niveis_14pav/desenvolvimento_rapido/integracao_v408_identidade/`.

O agregado `paths14_cycle_report.json` distingue 174 ocorrências PIL no
assessment (119 diretas e 55 resumos/cobertura dependentes) de 131 mensagens
incertas no QA bruto (incluindo repetidas). As 119 diretas distribuem-se em
63 Passa dependentes da prova da face adjacente, 55 identidades/seções locais
sem prova e um candidato a vínculo sem parede original. Esses números não
equivalem a 174 causas distintas; resolver identidade exige recalcular os
dependentes, sem aprovar cotas espelhadas ou repetir valores SA como evidência.

Quatro contraprovas reais preservam os limites: P17D/V402 encontra interrupção
por cruzamento e não alcança nome original; P33C/V408 alcança VF403 na faixa
14/55, enquanto V408 está no trecho 19/55; P49D/V425 alcança V426. Os dois
últimos exigem reconciliar associação nominal e mudança de seção no motor,
não liberar o QA por proximidade. P41C/V410 encontra V410 antes de V409, mas
o veto atual varre a componente inteira e inclui esse segundo nome após outro
apoio. A proposta experimental encerra cada ramo na primeira etiqueta
original: nomes concorrentes nas primeiras fronteiras continuam ambíguos,
e nunca se salta uma etiqueta adversa para alcançar o nome solicitado.

O experimento confirmou apenas P41C e conservou os outros três negativos;
34 testes de contraprova passaram, incluindo rotação, ausência de parede,
offset, mudança de largura, seção conflitante e nomes concorrentes nas duas
direções. A proposta foi integrada depois no helper local, sem instalação
remota nesta etapa: 161 testes passaram, incluindo concorrência dentro do mesmo
primeiro vão e nome diferente além do primeiro vão solicitado. Isso não
constitui certificação QA nem aprovação do pavimento. Evidências:
`first_named_frontier_receipt.json`, `test_first_named_frontier.py` e
`paths14_pil_cause_inventory.json`, na pasta acima. A busca nominal experimental
não altera a regra de alturas: chamada numérica corretamente vinculada vence
altura inferida da representação em corte; falta de vínculo permanece dúvida.

Replay integrado completo usa o mesmo leitor original em ambas as passadas e
troca somente a busca nominal: no estado fresco `paths14_analysis_state.json`,
106→109 contatos medidos (P41A/B/C); no controle `physical13_analysis_state.json`,
103→109 (P1A/B/D e P41A/B/C). Nenhuma medição anterior regrediu; fontes e estados
mantiveram os hashes. Os três negativos acima permaneceram incertos. O recibo
`frontier_integrated14_13_receipt.json` conserva prova por contato, comparação
com o comportamento instalado e ausência de publicação. A integração local
preservou uma mudança concorrente do leitor POLYLINE; o delta compara a mesma
cena nas duas buscas, não atribui essa mudança concorrente ao ajuste nominal.

## Chegadas: seção local e reconciliação de identidade — 2026-10-11

Uma caixa de viga pode estar deslocada ou ter largura diferente da seção
numérica original. Ao medir distâncias de chegada, o corredor precisa ter
espessura compatível com a seção **do contato** (tolerância de 0,6 cm), não
necessariamente com a seção global da viga. Rejeitar esse corredor preserva
o fallback geométrico existente; não inventar outra distância. Contraprovas
incluem seção local verificada diferente da seção global e caixa de 24 cm
que não pode decidir a ocupação de uma seção 14/55. A rodada fresca confirmou
a correção dos cinco afastamentos de VF403/P28–P30 anteriormente errados em
2 cm; a fórmula não contém esses nomes.

Reconciliação nominal automática exige uma única primeira fronteira original
e seção local comprovada. Reavaliar o candidato no mesmo contato: mesmas
paredes, mesma face, distâncias corretas, handles de nome e seção. Nenhuma
posição é deslocada. Campos/slots validados por humano são preservados;
nomes concorrentes ou alteração de parede/distância vetam a troca. Duplicatas
automáticas idênticas podem ser consolidadas, mantendo duplicatas humanas.
O SA aplica essa leitura antes de materializar os slots PIL, tanto no app
quanto no ciclo headless. O pós-QA continua lendo o DXF original.

Evidência local: `scripts/arete/relatorios/20261011_pil_continuacao/`.
`cycle14_06_frozen/cycle_report.json` registra PRE→SA→QA sem desenho/publicação,
isolamento aprovado e nenhuma regressão contra a rodada imediatamente anterior.
Foram reconciliados nove contatos distintos V408→VF403; aplicações repetidas
entre PRE/SA/merge não representam nove causas novas por etapa. O recibo
`identity_applied_receipt.json` conserva os handles e hash da fonte. PIL ficou
14 confere / 21 incerto / 0 diverge; **não é aprovação do pavimento**.
Fixture reduzido omite históricos/outros projetos/dados globais. Runtime
isolado tem recibo de hashes e cerca de 36 MB; imports opcionais de robôs
legados ausentes impedem tratá-lo como prova de todos os modos N3/produção.
O replay 13_PAV é controle de leitor, não substitui a rodada fresca do 13º.

### PIL-PAREDES-E-SECAO-LOCAL-20261011 — duplicatas e mudança de seção

Uma aresta de contorno fechado não cria um segundo corredor quando uma
parede aberta original cobre integralmente a mesma aresta, no mesmo eixo e
posição. O leitor conserva os handles da parede aberta. Cobertura parcial,
lacuna e traços de outra orientação não autorizam descartar o contorno ou
prolongar a parede. Esta deduplicação atua só nos candidatos de medição;
não remove entidades do desenho nem decide a identidade estrutural.

Uma única etiqueta longitudinal original diferente da identidade solicitada
fica explícita como proposta de revisão, com seção e paredes comprovadas.
O QA não aprova o alias. A reconciliação exige nova medição do candidato,
com as mesmas paredes/face e ausência de erros; campos humanos continuam veto.

Mudança de altura com largura constante pode ter um traço transversal
original ligando exatamente as duas paredes da viga. Para limitar a chamada
numérica ao trecho junto ao pilar, exigir uma seção numérica única em cada
célula imediatamente adjacente ao traço, com mesma largura medida,
orientação longitudinal e alturas diferentes. Traço de cota já identificado,
aresta fechada, linha parcial/prolongada, célula sem chamada ou com chamadas
conflitantes não decide essa mudança. O vínculo nominal e as distâncias
continuam provas separadas; o separador não transporta altura ao outro trecho.

Quando o contato já está medido e o único erro é a seção, a reconciliação PIL
pode corrigir apenas a dimensão do slot automático. Reprovar o candidato no
leitor original, com os mesmos handles de parede, nome e seção, sem mover
posições. Um slot `para` normalizado como `interior` pode ser localizado pelo
mesmo nome e canto físico único. Não modificar a seção global FV/LV nem
substituir um slot humano. Contatos derivados são recalculados pela tabela;
não corrigir cada repetição manualmente.

Evidência: `scripts/arete/relatorios/20261011_pil_continuacao/`.
`cycle14_07_openwalls` e `cycle13_02_directnames` completaram PRE→SA→QA com
isolamento aprovado, sem desenho/publicação e sem diferenças de geometria,
medidas ou contatos contra seus baselines imediatos. As 115 diferenças mais
antigas do primeiro ciclo fresco 13 continuam pendentes de revisão original;
trocar o baseline não constitui aprovação dessas diferenças.

`section_boundary_effect.json` compara os mesmos estados, alternando somente
o vínculo de separador: nenhuma prova anterior perdida; no 13º, P41 ganhou
duas provas e P49 passou a expor a seção incorreta. O original usa o separador
40F na V301 e a seção 19/120 E96 na V330. O teste isolado em uma cópia de P49
corrigiu 19/71→19/120, preservando posições e eliminando os erros derivados;
isso ainda exige ciclo completo. `section_reader_tests_03.log`: 96 testes
passaram, incluindo contraprovas de separadores e veto humano.

### PIL-U-N3-INTEGRACAO-20261011 — cobertura e limites da prova

N3 U vincula A–H às oito arestas físicas após normalização do anel; C/D são
as pontas. CIMA e ABCD exigem as oito faces. GRADES inclui C/D somente quando
a largura física excede 40 cm, independentemente de uma largura de painel
editada. Falta de face obrigatória interrompe a entrega dos arquivos.
`u_ini_threshold_tests.log`: 85 testes passaram, com geração real NOVA/INI
nos limites 30/40/41 cm e contraprova removendo uma face do desenho.

`golden_u_conversion_regression.json` regenerou todos os 314 inputs PIL
salvos sob GOLDEN, incluindo conjuntos arquivados/invalidados, em INI/NOVA
e CIMA/ABCD/GRADES. As 1.884 comparações antes/depois desta conversão foram
iguais, sem erros de auditoria DXF. Esta prova não sela os conjuntos nem
certifica mudanças históricas de outros motores. Chapas, sarrafos, perfis
e madeira são geometricamente iguais à prévia U_v10; pontas dos parafusos
e textura diferem e seguem sem aprovação visual. Cobertura A–H não equivale
à certificação física/visual G2/G2-V.

### PIL-MEDICAO-PARCIAL-NAO-PROVA-AUSENCIA-20261011

Uma coleção de trechos FV com ambas as paredes verificadas prova presença
nesses trechos. Não prova que a coleção cobre todos os braços da viga.
Na poda de contato distante, conservar também candidatos não degenerados
do traçado quando a coleção verificada é parcial. A medição transversal
continua vetando candidatos em outro corredor. Essa conservação serve apenas
para impedir uma exclusão indevida; não fornece distâncias, seção ou aprovação.
O QA deve reprovar novamente o candidato contra o original. As distâncias
de interiores continuam usando somente paredes verificadas.

Causa reproduzida nos argumentos reais do SA: V322 no P16 do 13º possuía
braços ao sul e ao norte. O contexto posterior conservava somente trechos
FV verificados ao norte, e `prune_beams_far_from_face` apagava D.interior.
O leitor original mede o contato sul sem erros (20A/20B, FA0, 1007, 19/120).
`p16_actual_table_replay.json` reproduz a exclusão; a versão corrigida mantém
o candidato em todos os três contextos reais capturados. Testes próprios e
regressões PIL: 110 passaram. Novos ciclos completos permanecem necessários;
nenhuma aprovação visual ou de produção decorre deste replay.

### PIL-IDENTIDADE-CELULAS-NUMERICAS-20261011

Uma mudança de altura com largura constante não interrompe necessariamente
a identidade da viga. O leitor de caminhos originais pode conservar esse
vínculo quando uma linha aberta transversal termina nas duas paredes e cada
célula possui seção numérica longitudinal única, de mesma largura, diferente
da célula adjacente. Linhas de cota, contornos fechados, traços incompletos,
células sem número e seções conflitantes continuam vetados. A identidade
exige o mesmo caminho original com apoios comprovados; a linha de mudança
não fornece identidade nem transporta altura. O resultado registra as células
separadamente e deixa a seção agregada nula.

75 testes passaram. Comparação dos leitores 07/08 nos mesmos snapshots e DXFs:
oito contatos do 13º (P42/P43) passaram de incertos a medidos, nenhuma prova
foi perdida; no 14º não houve alteração. Ciclos completos 13_05/14_11 em
validação. Este ganho do leitor não aprova o pavimento nem as diferenças
históricas. Evidências: `numeric_cells_reader_status_delta.json` e
`runtime_numeric_cells_receipt.json` no relatório `20261011_pil_continuacao`.

### PIL-U-TEXTURA-INSERT-20261011

A textura do U aprovado utiliza a orientação do INSERT de madeira incorporada
antes de dimensionar o bloco. O asset bruto tem os eixos trocados, afetando
principalmente o meio pontalete. O payload U agora declara rotação -90 graus
do template antes da escala; payloads anteriores mantêm seu comportamento.
Comparação DXF serializada, sem render: 336 entidades de Madeira_textura
iguais à referência U_v10, assim como chapa, sarrafo, perfil e madeira.
Pontas dos parafusos conservam a orientação interna atual e continuam sendo
uma diferença independente a revisar. Igualdade numérica da textura não
substitui aprovação visual ou selo G2/G2-V.

### PIL-IDENTIDADE-ABERTURA-T-20261011

A parede interrompida por uma chegada em T não é, por si, uma interrupção
da viga longitudinal. O leitor independente pode conectar os dois intervalos
somente quando a parede oposta cobre o intervalo inteiro, os extremos da
parede interrompida coincidem com as duas paredes perpendiculares originais,
ambas terminam nessa borda vindo do mesmo lado, e um nome perpendicular
único identifica a chegada. Contorno fechado sobreposto, dois lados abertos,
parede faltante e nomes concorrentes vetam a conexão. O nome longitudinal
continua vindo de sua própria chamada original; nenhuma altura é transportada.

Original V402/V420 inspecionado em `original_v402_v420_t_joint.png`.
85 testes passaram. Comparação dos leitores 08/09: oito contatos V402 em
P17/P18 do 14º ganharam prova, sem erros numéricos; nenhuma prova perdida;
13º sem alteração. Conservar testemunhos das paredes contínua/perpendiculares
e do texto, sem inventar handle de pilar para uma chegada em T. Ciclos completos
e revisão formal ainda são necessários. Nenhuma alteração FV/LV decorre
desse leitor PIL.
### PIL-NOME-EXTENSAO-ORIGINAL-20261011 — texto que cruza a face

O ponto de inserção não representa toda a etiqueta original. Uma etiqueta
nominal inteira pode começar ligeiramente dentro do apoio e ter a maior parte
impressa no vão. No leitor independente de continuidade, o fallback exige
orientação longitudinal, posição transversal compatível e pelo menos 80% da
extensão longitudinal real do texto no mesmo vão. A extensão vem da entidade
original; um token dentro de MTEXT maior não recebe a caixa do texto completo.
Nomes concorrentes continuam veto. O fallback não vincula números de seção,
não transporta altura e não amplia a geometria do contato.

Contraprova original: V318/F9C começa em 2757,540889, enquanto a parede do vão
começa em 2759,038. A etiqueta impressa ocupa esse vão, acima do P14.
Comparação sobre estados imutáveis: seis contatos P5/P45 do 13º ganharam prova,
sem perda no 13º ou alteração no 14º. Evidência e PNG original em
`scripts/arete/relatorios/20261011_pil_continuacao/`; a rodada completa conserva
o gate pós-SA e a restrição de publicação.

### PIL-PASSA-SECAO-POR-CANTO-20261011

Dois cantos da mesma face podem pertencer a trechos da mesma viga com alturas
diferentes. Corrigir uma passagem automática somente quando o leitor original
já comprova o canto físico e a face perpendicular de origem, e o único erro é
a seção. Reprovar a alteração se mudar parede, canto, face de origem, identidade
ou qualquer outra medida. Preservar slots/campos humanos. Não escolher uma
altura global por nome nem copiar a seção de um canto para o outro.

Contraprova original TIPO_TESTE/P6: V526 chega com 19/120 pela face A e 19/50
pela B. A passagem DA conserva 19/120 e DB recebe 19/50, pelas respectivas
paredes e chamadas numéricas originais. Ciclo completo
`cycle_tipo_03_corner_sections`: zero divergência PIL, seis confere e quinze
incertos; sem alteração espacial/de níveis, sem desenho/publicação e isolamento
aprovado. A ausência de divergência não aprova os contatos ainda incertos.


## PIL-CORTE-INTERROMPIDO-ORIGINAL-20261011

Uma seção com símbolo de interrupção continua sendo evidência numérica quando
os traços originais vinculam inequivocamente a cota ao perfil. O leitor pode
reconstituir um contorno auxiliar a partir de um único corte diagonal, dois
fustes LINE originais e a tampa original completa. A linha de cota interrompida
exige duas partes originais colineares ligadas a um único marcador zigzag
centrado, ticks nos extremos, testemunhas e um número único alinhado. Paredes
originais em polilinha podem servir de testemunhas se forem contínuas entre a
cota e o limite do perfil; uma parede desconectada não basta.

A largura numérica deve coincidir com as duas paredes; a altura numérica
corretamente vinculada prevalece sobre a altura gráfica abreviada. A prova
permanece dentro do vão próprio, sem transportar altura ao atravessar pilares.
Não se altera o DXF, não se aproxima contorno por bbox e não se aprova quando
falta tampa, fuste, marcador, tick, testemunha ou quando há cotas conflitantes.

Evidência: scripts/arete/relatorios/20261011_pil_continuacao/
broken_section_glyphs_13.json contém seis cortes originais recuperados;
original_v318_broken_section.png foi lido pelo agente. Comparação do mesmo
estado: 18 contatos do 13º ganham prova, sem perda de prova no 14º. 122 testes
passaram, incluindo rotações, espelhamento e contraprovas incompletas. A rodada
completa PRE/SA/QA é registrada separadamente e continua necessária.


### Caminho de identidade com corte original dimensionado

O caminho nominal pode usar a seção dimensionada como prova local quando não
há texto completo B/H nesse vão. Exigir as mesmas paredes e o perfil inteiro
contido no próprio intervalo. Preservar todos os handles do perfil, traços,
cotas e textos na evidência. Não substituir B/H conflitantes; não transportar
a altura para outro intervalo. As contraprovas de tampa/tick ausentes e cota
ambígua mantêm status incerto. O leitor independente passou a provar três
contatos V318 do P45; a nova rodada completa registra o efeito final.

### Rótulo contido em outro retângulo não muda o dono do pilar

Um rótulo P pode cair também em um retângulo de outra entidade ou anotação.
O vínculo ao pilar exige o contrato original rótulo + B/H + contorno compatível,
e não apenas inclusão espacial. Se o mesmo handle do rótulo está vinculado por
esse contrato a um único contorno diferente, o retângulo concorrente não pode
virar apoio desse pilar. Nome sem vínculo, números ausentes ou vínculos
concorrentes conservam a barreira: não presumir ausência de um pilar.

Diagnóstico original: P14/E5B + E5C/19/98 pertence ao contorno 27D, enquanto
BD3/DFD (205 x 125 cm) também incluem o texto. P20/E48 + E49/19/86 pertence a
266, enquanto BD7/DF8 também incluem o texto. O diagnóstico isolado e os hashes
estão em named_contour_frontier_diagnostic.json. A integração candidata do QA
está apenas em runtime_frozen_14, com patch separado; o arquivo compartilhado
portal/app/qa_cad_gate.py não foi alterado. Comparação original da candidata:
13 contatos ganham prova no 13º e 13 no 14º, sem perda. 118 testes passaram.
Isso não é aprovação global nem dispensa rodadas completas e integração.

### Contato interior sem canto explícito e canto canônico repetido

O serializador ABCD pode atribuir CC/DD ao contato interior cuja origem não
guarda `corner`. Esse canto canônico não impede vincular o único slot interior
com o mesmo nome e sem canto explícito. Antes de alterar o nome ou a seção,
remeça a proposta no original: mesmas paredes, nome único, seção numérica,
distâncias sem erro e nenhuma validação humana. Canto explícito diferente,
slots repetidos e qualquer erro conservam o registro. Não mover geometria,
distâncias ou canto para fazer a proposta passar.

Replay inicial de P33 C/interior vincula a proposta VF403 14/55 às paredes
2A1/2A2/372/374/376/651, nome D74 e seção DBF. Porém a rodada completa
`cycle14_14_uncornered_identity` mostrou que a reconstrução ABCD transforma
esse interior em A/Passa sem prova. Portanto a proposta é vetada: exigir
também nova medição da tabela canônica reconstruída, conservando face, papel,
paredes e ausência de erros. Uma linha de tabela corrigida isoladamente não
aprova o slot persistido. O replay atualizado preserva P33 e P28; P28 também
tem veto por distâncias. Evidência em
`20261011_pil_continuacao/p33_uncornered_identity_replay.json`. Os testes
incluem a contraprova de reclassificação para Passa, além de distância,
paredes diferentes, validação humana e ambiguidade.

### Mudança numérica com outros traços completos no mesmo vão

Um traço transversal completo só define mudança de seção quando as duas
células originais imediatamente adjacentes têm números B/H únicos, distintos
e da largura medida. Traços completos adicionais sem essa prova não devem
apagar uma fronteira numérica comprovada. Após selecionar as fronteiras,
exigir seção única em cada intervalo resultante completo; número conflitante
em qualquer parte do intervalo mantém incerteza. Não unir paredes com lacuna,
ignorar pilares/barreiras nomeadas ou transportar altura para outro vão.

O leitor local de seção também precisa excluir o handle B/H já vinculado por
contrato numérico original a um único pilar, como o leitor de identidade já
faz. Sem vínculo numérico único, conservar o texto para revisão. A exclusão
candidata permanece no snapshot de QA isolado; arquivo compartilhado intacto.

Prova original do 13º: P43/E08 + E09/19/50 é seção do pilar; a viga tem
101B/19/55 à esquerda de 411 e E80/19/120 à direita. 301/306 são outros traços
completos que, sozinhos, não provam mudança numérica. PNG original inspecionado
`20261011_pil_continuacao/original_v301_change.png`, com handles e hash no JSON
vizinho. A candidata runtime_frozen_17 recupera 15 contatos no leitor do 13º,
sem perda; 14º e TIPO sem alteração. 170 testes passaram no runtime exato.
Essas são provas de leitor e contraprovas, não aprovação de rodadas completas
ou publicação; conferir o dossiê para o resultado posterior do ciclo.

### A identidade corrigida precisa conservar o papel físico da chegada

A prova de uma linha editada da tabela não basta: reconstruir ABCD com os
mesmos dados e exigir que o contato continue medido no original, com as mesmas
paredes, nome, seção e distâncias. Quando a seção comprovada é mais estreita
que a face curta retangular, aplicar R2 já decidida: chegada, não interior.
Migrar somente o slot automático único, mantendo sua posição e qualquer
validação humana. A mudança de papel exige nova prova após a reconstrução;
um contato que desaparece ou vira passagem sem prova conserva a pendência.

O corredor diretamente medido do original também pode preservar uma chegada
cujo nome, seção e paredes já foram vinculados pela prova original individual,
quando o traçado interpretado omitiu esse braço. Não usá-lo para restaurar
aliases automáticos sem esse vínculo: a candidata 19 trouxe contatos V408
adicionais sem prova no ciclo completo do 14º (156 ocorrências contra 149).
A candidata 20 restringe a retenção à origem `original_contact_identity` ou
`original_contact_section`, exigindo novamente o QA após reconstrução.
Os ciclos completos 20 e 21 ainda reproduziram os seis deltas da candidata 19.
A candidata 21 restringiu também a medição à origem comprovada (142 testes),
mas essa restrição não resolveu a regressão. O diagnóstico diferencial
`bound_alias_table_differential.json` comprova que as versões 18 e 21 geram
os mesmos aliases a partir do mesmo snapshot. A causa estava na reconciliação:
renomear o alias criava duas linhas do mesmo contato físico e o guard de
unicidade vetava a correção. Não atribuir essa regressão à tabela sem comparar
as duas versões com os mesmos dados.
Conservar esse candidato na poda de distância não o aprova. Para medir
chegada, tratar os corredores separados;
largura incompatível ou distâncias locais concorrentes permanecem sem
medição única. A via `verified_only` conserva o contrato de fundo verificado.

P33 C no original do 14º: parede 2056,025/2070,025, seção DBF/14/55,
nome D74/VF403 por caminho original de apoios; face curta de 19 cm,
distâncias 0/5 cm. A proposta antiga de trocar só o nome foi reprovada no
ciclo completo. A candidata 19 corrige também o papel pela R2 e o replay
canônico comprova C/chega, sem criar a passagem espúria. P28 conserva o veto.
Recibos `p33_short_face_role_probe.json` e `short_face_replay_19.json` no
dossiê 20261011_pil_continuacao; 176 testes da candidata e 104 de regressão
passaram. A candidata 19 permanece como contraprova do efeito colateral; a
20 mantém a chegada do P33 no replay e passa 177 testes, incluindo veto ao
alias sem vínculo. Replay não substitui PRE/SA/pós-QA completo nem autoriza publicação.

### Duplicação de paredes no exterior da face

Ao medir apenas o exterior da face, uma borda fechada que continua atrás do
pilar só pode ser descartada como duplicata se a parede aberta original
cobrir integralmente sua parte exterior. Cobertura parcial conserva a
ambiguidade; não estender paredes ou unir lacunas. A candidata 18 passa o
caso positivo e a contraprova de cobertura parcial, mas não muda os contatos
comprovados dos snapshots reais comparados. A proposta de integração contém
somente a função PIL `measure`; preservar todas as outras funções do QA
compartilhado. Não copiar o arquivo inteiro do runtime congelado sobre o atual.

### Hipótese de identidade indireta na viga que entra no T

No diagnóstico de P24/V419, a seção e as paredes locais podem ser lidas,
mas a identidade continua interrompida no encontro com V407. Um protótipo
buscou provar o nome da viga transversal por apoios originais, sem permitir
recursão por outros T e exigindo seção local. Passou 16 casos sintéticos,
mas não ganhou nem perdeu prova nos três desenhos reais comparados; foi
removido. `indirect_t_identity_probe.json` e `p24_incoming_path_probe.json`
preservam o diagnóstico. Não aceitar um T pelo nome distante quando o próprio
caminho até esse nome permanece sem prova. Resultado de busca não é associação.

### Duplicata física e conservação da evidência após nova interpretação

Duas linhas propostas só equivalem a um contato quando coincidem face, papel,
nome, seção, largura, distâncias medidas, canto, pilar e todos os handles de
paredes, nome e seção. Exigir distâncias presentes e ausência de erros. Uma
parede ou distância diferente conserva o veto. A candidata 22 distingue essa
duplicata física de chegadas concorrentes; o replay original corrige os aliases
de P28/P29/P30 sem transportar seção para outro vão.

A nova interpretação pode reconstruir `face_beams` e apagar a origem de um
contato já provado. Guardar temporariamente apenas sua evidência; restaurar
metadados somente no único slot recém-interpretado com a mesma face, família,
nome, seção e canto, o mesmo hash do DXF e os mesmos pontos do pilar. Não criar
contatos antigos, mudar geometria ou sobrepor validação humana. Exigir handles
originais completos e retirar o registro temporário após a reconciliação.
Fonte alterada, geometria diferente, slot ambíguo ou papel diferente vetam a
restauração. Prova antiga sem os pontos do pilar também não é reutilizada.

A candidata 23 implementa esse contrato nos módulos PIL próprios; 154 testes
passaram no runtime congelado exato, incluindo contraprovas de fonte, pontos,
seção, canto, papel, validação humana, duplicatas e handles incompletos.
Recibos: `runtime_provenance_23_receipt.json` e
`provenance_23_tests_receipt.json`, no dossiê 20261011_pil_continuacao.
Isso não certifica produção: consultar `provenance_cycles.json`, os recibos
de revisão e a classificação das pendências após PRE/SA/pós-QA completos.
O QA compartilhado continua fora desta alteração. A observação atual
`current_integration_observation.json` confirma que o método PIL do `main.py`
local já corresponde ao candidato; isso não comprova deploy na VPS.

A rodada completa 23 do 14º remove os aliases e permite revisar três deltas
originais (149 ocorrências brutas, 146 após revisão exata), porém a reconstrução
independente continua reprovada: `_serialize_analysis_state` elimina `source`
e `original_identity_evidence` dos slots leves. Usar `interpretacao_abcd` para
essa contraprova; atribuir uma chave `abcd_tables` não substitui a tabela que
o QA lê e pode produzir uma falsa conclusão de conservação.

A candidata 24 encaminha o serializador isolado à função própria
`serialize_original_contact_slot`, conservando somente hash, pontos do pilar,
handles de paredes/nome/seção e declaração de posições preservadas para fontes
originais completas. Não serializa segmentos de desenho ou caminhos pesados.
156 testes passaram no runtime exato, com teste de serializar → reinterpretar
→ recuperar autoridade e contraprova de handles incompletos. O arquivo de UI
compartilhado permanece intacto; `proposta_pil_serializer.patch` contém apenas
o encaminhamento necessário. A candidata precisa de ciclos completos e de
reconstrução real aprovada; testes focados não liberam publicação.

As três rodadas completas 24 terminaram com isolamento aprovado e código
congelado inalterado: 14º 149 ocorrências brutas, 13º 196 e TIPO 1153.
A revisão original exata aprova somente os três deltas de contatos do 14º,
resultando em 146 ocorrências; não altera as outras pendências do gate.
`serializer_24_actual_rebuild.json` comprova reconstrução real a partir dos
slots serializados em 10 pilares do 14º, 9 do 13º e 1 do TIPO. P33 conserva
C/chega VF403 14/55 medido no original. Nenhuma dessas provas aprova o
pavimento inteiro ou autoriza publicação. A integração do serializador leve
e dos três ajustes do leitor PIL no QA compartilhado continua proposta.

### Fronteira confirmada pelo dono: consumo localizado em ambos os leitores

A decisão `PIL-V301-13P-LIMITE-100-20261012` confirma no original do 13º
a divisória `414`: seção `E83` 19/120 antes, `102A` 19/55 depois, até P47.
Não usar o nome da viga, camada do traço ou número da cota como regra geral.
Uma revisão humana só pode ser consumida com hash do DXF idêntico, handle da
divisória aberta cobrindo as duas paredes, handles dos números dos dois lados,
seções longitudinais compatíveis com a largura e nenhum número concorrente.
Revisão ausente, malformada, duplicada ou incompatível não concede autoridade.

O leitor de seção local e o grafo de identidade precisam consumir a mesma
fronteira: resolver apenas o primeiro deixa o segundo descartando um vão
numericamente conflitante. A revisão separa a propriedade dos números;
não cria paredes, não atravessa lacunas e não inventa nomes. O grafo ainda
exige continuidade original e primeiras fronteiras nominais concordantes.
Fonte: `DECISOES-DO-DONO.md`, recibo humano e candidata isolada 26 no dossiê
`20261011_pil_continuacao`. Consultar os ciclos completos e o diferencial
antes de considerar regressão aprovada; a revisão não libera publicação.

A candidata 26 concluiu os três ciclos completos sem regressões registradas:
13º 183 ocorrências restantes (antes 196), 14º 146 e TIPO 1153. No 13º,
PIL passou de 25 para 26 itens confere; P46/P47/P48 ainda têm outros encontros
incertos, P49 passou a confere. No diferencial dos mesmos snapshots foram
12 contatos adicionais medidos, incluindo Passa derivados, e zero perdas nos
três pavimentos. 197 testes passaram no runtime exato; as entradas originais
e a revisão ficaram inalteradas durante cada ciclo. QA/UI compartilhados
intactos. Evidências: `reviewed_boundary_26_completed.json`,
`reviewed_boundary_reader_differential.json` e
`VALIDACAO_V301_CANDIDATA_26.md`. Estes resultados não encerram a missão.

### PIL-T-FECHADO-PELA-PAREDE-CONTINUA-20261012

Uma lateral em T não interrompe o vão da principal quando suas duas paredes
originais terminam na mesma face externa e ambas as paredes da principal
cobrem todo o intervalo desse encontro. A própria parede aberta contínua da
principal pode fechar a lateral: não exigir um traço redundante separado com
exatamente a largura do ramo. O ramo ainda precisa de nome e seção numérica
originais únicos e da largura medida, comprovados pelo leitor chamador.

Cruzamento através da principal, encontro parcial, extremidades distintas,
parede principal interrompida, contorno fechado ou fechamento incompleto
continuam sendo barreiras. Não importar a altura do ramo: a principal exige
sua própria seção numérica no vão, identidade nominal independente e
distâncias medidas na face. Nenhuma regra depende de nome, obra ou camada.

Implementação própria: `pil_qa_t_junctions.capped_exterior_t`. Integração no
QA compartilhado somente proposta em `proposta_pil_qa_completa_27.patch`, no
dossiê `20261011_pil_continuacao`; arquivo vivo preservado. 213 testes passaram
no runtime exato. Diferencial dos mesmos estados: 10 contatos adicionais no
14º, 4 no TIPO, zero perdas; 13º inalterado. Esse diferencial inclui contatos
Passa derivados e não certifica PRE/SA novo ou publicação. Consultar os ciclos
completos e `VALIDACAO_T_CONTINUO_CANDIDATA_27.md` para o resultado final.

#### Rodadas completas da candidata 27

Três ciclos completos concluídos sem regressão registrada, com fontes/revisão, isolamento e runtime conservados: 13_PAV: 183 ocorrências globais, 14_PAV: 132 ocorrências globais, TIPO_TESTE: 1147 ocorrências globais. Fixtures diagnósticas; nenhuma aprovação global ou publicação. Recibos em `continuous_t_27_completed.json` e `VALIDACAO_T_CONTINUO_CANDIDATA_27.md`.

### PIL-CHEGADA-CURTA-GEOMETRIA-SEPARADA-20261012

O comprimento mínimo utilizado para procurar nome e B/H não é uma prova de
ausência da viga. Duas paredes estruturais originais abertas, únicas, que
alcançam a face e possuem extensão exterior positiva podem comprovar largura
e distâncias mesmo num trecho menor que esse mínimo. Registrar apenas
`geometry_only`: nome e altura continuam sem aprovação. Parede única, folga
sem traço, contorno fechado, projeção atrás da face e pares concorrentes
exigem abstenção. Não prolongar paredes nem importar seção da perpendicular.

Evidência: P28/C nos originais do 13º e 14º apresenta dois traços de 5 cm,
largura 19 cm e distâncias de 2,5 cm em ambos os lados. Handles 1D8/1D9 no
13º e 24C/24D no 14º. A anotação longitudinal além do cruzamento não está no
trecho curto: ainda falta provar a continuidade nominal e da seção através
da abertura, independentemente do SA. Não confundir com a lateral em T
fechada pela parede contínua da principal.

Leitor próprio `pil_qa_short_arrivals.short_original_arrival`, 13 testes
positivos/negativos aprovados. Prova nas duas fontes imutáveis em
`20261011_pil_continuacao/p28_short_original_geometry_receipt.json`.
Uso atual é diagnóstico, sem integração no QA, redução de pendências ou
publicação. Inventário refinado conserva os mesmos 58 contatos incertos.


### PIL-BORDA-REGIONAL-APROVADA-20261012

Uma mudança de seção pode coincidir com uma borda regional que ultrapassa a largura
inteira da viga. Isso exige decisão humana explícita; não é regra automática para
usar cotas, hachuras ou qualquer traço extenso como divisória. O contrato
`cad.original_beam_section_review/v1` aceita `boundary_kind=reviewed_region_edge`
somente com SHA256 do DXF original, handle único da borda original aberta que cobre
as duas paredes, números originais próprios em ambos os intervalos, mesma largura
medida e rotação longitudinal. Hash divergente, borda parcial, fechada, tipo desconhecido,
valores concorrentes ou revisão duplicada deixam a leitura incerta.

A decisão V514-TIPO-BORDA-FAIXA-H10-20261012 identifica a borda 6714, o número
7D37 (19/48) antes e 7D36 (19/50) depois. Na candidata 28, os 217 testes passam e
na comparação sobre os mesmos estados há dois contatos adicionais medidos no TIPO,
nenhuma perda e nenhuma alteração nos contatos do 13º/14º. Isso é evidência do leitor;
não certifica publicação nem corrige automaticamente o estado SA. Rodadas completas
e seus gates continuam obrigatórios. Evidência em
`20261011_pil_continuacao/region_edge_28_differential.json` e
`region_edge_28_tests_receipt.json`.


### PIL-ANCORA-DENTRO-DE-APOIO-ORIGINAL-20261012

Se a face avaliada estiver dentro de outro apoio original, o leitor pode localizar
o início do caminho na saída desse apoio, exigindo um único contorno contendo a
âncora estritamente no interior, vínculo original do nome P e seção numérica,
par de paredes solicitado e continuidade original de ambas até a saída. Apoio
anônimo, número ausente, duas saídas concorrentes, sobreposição de apoios ou lacuna
em qualquer parede mantêm incerteza. Não fundir pilares nem transportar a seção.

No P13/13º, as faces A e B estão dentro do P50 original (37B, FEC, E8A).
A prova leva aos vãos externos com seções próprias 1037/1036 e ao nome V302/107A.
A comparação candidata 29 sobre os mesmos estados ganha dois contatos no 13º,
sem perdas e sem mudança no 14º/TIPO. 235 testes da candidata passaram.
A integração e a rodada completa foram incorporadas à candidata 30 baseada no
código atual. Fonte: supported_anchor_p13_probe_29.json e
supported_anchor_29_differential.json. Esta regra não aprova a missão inteira.

### PIL-VALIDACAO-CORRENTE-20261012

A candidata 30 foi atualizada sobre os módulos correntes, preservando as mudanças
externas a PIL. Três ciclos completos terminaram: 13_PAV com 180 ocorrências,
14_PAV com 132 e TIPO com 1141. Não houve regressões nem alterações espaciais
contra os controles anteriores; isolamento, código e inputs ficaram estáveis.
Essas contagens são diagnósticos de fixtures reduzidas, não certificação de produção.
A função local `measure` recebeu somente os seis trechos PIL revisados; todas as
outras funções QA foram preservadas. 235 testes PIL e 111 testes isolados N3/N5
passaram. A UI compartilhada não foi alterada; sua integração continua pendente.
Recibo vigente: `20261011_pil_continuacao/current_30_completed_receipt.json`.

A inspeção do caminho P26/P27 no 13º encontrou os contornos originais em L 280/283,
com nomes E5D/E61 e chamadas VER DET. E5F/E60. Esses apoios não têm o contrato
numérico retangular usado pelo leitor de continuidade. Um retângulo envolvente
preencheria o vazio do L e não constitui prova. O inventário de B/H alinhado a
nome P e dimensões externas de contornos não retangulares não encontrou vínculo
nos três desenhos examinados. Não ampliar a regra de propriedade por proximidade
nem tratar a ausência como uma nova aprovação humana. É uma classe técnica de
ligação entre contorno original e detalhe/cotas, ainda sem prova suficiente.
Inventários: `l_support_original_30.json` e `nonrect_numeric_ownership_30.json`.
