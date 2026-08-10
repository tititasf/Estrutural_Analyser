# Diário SA — PIL

Use o modelo de `docs/SA-ANALISE-PROGRESSO-POR-ITEM.md` e o manual
`docs/SA-ANALISE/CLASSES/PIL.md`. Entradas são append-only e
identificam face/variante PARA/PASSA quando aplicável.

## 2026-07-16 — Apply em lote + reprocessamento de 16 itens (S5)

- **Contexto**: `qa_pil_quadro_pavimento.py` revelou 421 decisões `CONFIRMAR`/
  `N/A_CONFIRMADO` já resolvidas pelo `PilEvidenceAuditor` mas nunca
  persistidas (`operations` ainda não aplicados).
- **Ação 1**: `qa_evidence_auditor.py review --classe PIL --project-id
  dd238e47-1dc6-4f63-a760-4e7ce19a7386` (46 itens) + `apply --seal-complete`
  → **30/46 pilares selados** (`is_validated=1`) de imediato, sem nenhum fix
  de motor — só persistência do que já estava correto.
- **Achado**: 37 itens tinham `REVISAR_HUMANO` em `p_s{face}_v` (motor espera
  viga X, persistido vazio/divergente) — 117 campos no total. Amostra
  confirmou padrão: pilares nunca reprocessados com o motor
  `pillar_face_beams.py` corrigido hoje (fixes 1/11/12/15 da sessão
  anterior), não um bug novo.
- **Ação 2**: reprocessamento real via
  `headless_sa_analise.py --secao pilares --item <16 itens> --persist-db
  --wait` (Python 3.12 do `.venv` — o `python` do PATH é 3.14 e o headless
  aborta corretamente; usar sempre `.venv/Scripts/python.exe` para qualquer
  script que toque o SA). Resultado: REVISAR_HUMANO em `p_s{face}_v` caiu de
  117 para 3 campos (só `P24`, rejeitado por guarda de regressão de
  topologia do próprio SA: `V322: old (4,410cm) vs new (3,380cm)` — o SA
  preferiu manter o valor antigo, correto por design).
- **Achado aberto (não resolvido sozinho — pendente revisão humana):** os 16
  itens reprocessados continuam bloqueados no selo completo por
  `connections` `REVISAR_HUMANO`. Causa: `connections.lajes_conectadas.
  details` (persistido por um caminho de cálculo em `main.py`, distinto do
  `pillar_face_beams.py`) inclui entradas `source: beam_wall_alignment` em
  faces C/D que o motor `pillar_face_beams.py` (já corrigido hoje, chamado
  fresh pelo `PilEvidenceAuditor`) não confirma. Exemplo: P11 face D, viga
  `V302` — a geometria de V302 (`seg_bottom`) só tem segmentos horizontais em
  y≈2661/2680 (o eixo A/B do pilar), nenhum segmento no x fixo da face D que
  indicaria contato perpendicular real. Suspeita (não confirmada
  unilateralmente): falso positivo no cálculo de `connections` de `main.py`,
  não uma lacuna do motor de faces. **Decisão de produto necessária**: qual
  dos dois cálculos é autoritativo para vínculos por alinhamento de parede
  nas faces curtas? Até essa decisão, `_audit_connections` continua correto
  em recusar `CONFIRMAR` — a divergência é real e exige olho humano, não um
  ajuste de tolerância no adaptador.
- **Ação 3**: `qa_n3_smoke.py` rodado para os 46 pilares (ambas variantes
  ABCD_PARA/ABCD_PASSA, usando os packs N3 frescos dos dois reprocessamentos
  de hoje) — **46/46 PASS**. S6 fechado por completo para o pavimento.
- **Bloqueio estrutural real para S7 (G5-V, N3×N4)**: `g2v_harness.py --par
  n3xn4 --backend cli` retornou `BLOCKED` para os 46 itens: "Ficha não
  contém SVGs vetoriais para o par solicitado". Investigado a fundo: a
  ficha HTML granular de PIL (`headless_sa_analise.py`) define a classe CSS
  `.evidence-card` mas **nunca a aplica** a nenhum elemento real — não existe
  o card multi-estágio N1/N2/N3/N4 com SVG embutido que
  `export_evidence_svgs()` precisa (procura `.evidence-card .evidence-title
  b` com texto N1–N4). Os relatórios antigos que "funcionavam" (`fonte_imagem:
  "html_ficha"`, ex. `g2v/20260714_022907`) usavam um caminho de rasterização
  PNG hoje removido — a regra do dono (`--fonte-imagem html` é a ÚNICA opção;
  harness é SVG-only) tornou esse caminho antigo definitivamente inválido, não
  apenas "legado a substituir eventualmente". **Isto não é um bug para caçar
  item a item nem algo que se resolve rodando de novo**: é uma peça do
  gerador de fichas PIL que nunca foi construída (embutir os 4 cards com SVG
  vetorial). Confirmado que o mesmo bloqueio vale para **N1-V (`--par
  n1xn2`)**, testado isoladamente em P35: mesmo erro, mesma causa raiz — não
  é específico do par N3×N4, é a ficha PIL inteira que nunca gerou o
  markup. Implementar isso é um trabalho de gerador (`headless_sa_analise.py`
  / template de ficha PIL), fora do escopo de "rodar o adaptador de novo" e
  sujeito à regra "não modificar gerador sem causa comprovada + regressão
  proporcional" — não resolvido nesta sessão, registrado para decisão/priorização.
  **Todos os selos que dependem de veredito visual CLI (N1-V e G5-V) ficam
  honestamente pendentes até essa peça existir; nada foi forçado ou simulado.**

## 2026-07-16 (cont.) — Causa raiz do achado `connections` resolvida (fix, não hack)

Investigação de código (não suposição): `main.py:6407` chama
`enrich_pillar_report_with_beams` (o MESMO motor de `pillar_face_beams.py`,
não há dois motores) — não há duplicação/divergência real entre `main.py` e
o adaptador. O bug era do próprio `PilEvidenceAuditor._audit_connections`:
o motor produz **duas visões** do mesmo resultado — `face_beams` (passa/
para/interior, cobre A/B) e a lista `lajes` (que `main.py` persiste como
`connections.lajes_conectadas.details`); vínculos por alinhamento de parede
em C/D (`source: beam_wall_alignment`) só existem em `lajes`, **nunca** em
`face_beams`. Comparar só contra `face_beams` (como o código fazia) gerava
`REVISAR_HUMANO` falso para todo vínculo desse tipo.

**Fix aplicado** (`scripts/arete/qa_evidence_auditor.py`):
`_face_beams_for` virou `_enriched_report_for` (cacheia as duas saídas do
motor); `_audit_connections` agora compara contra a união de
`face_beams` + as entradas `source=beam_wall_alignment` de `lajes`. Testado
(tentei só `lajes` primeiro — regrediu 6 itens que já estavam corretos via
`face_beams`; a união foi a correção certa). 2 testes de regressão novos em
`tests/test_qa_evidence_auditor_pil.py` (geometria real de P11/V302),
suíte completa (36 testes) verde.

**Resultado real**: `review`+`apply --seal-complete` para os 46 pilares →
**37/46 selados** (de 30). REVISAR_HUMANO caiu de 19 para 12 campos, restrito
a 9 itens (P24, P25, P26, P27, P29, P30, P31, P32, P48) — todos com
divergência **genuína** (ex. P29 face C: `connections` grava viga `V306`
mas `p_sC_v_passa_esq_n` já persistido/validado é `VF202` — dois candidatos
de viga próximos, o motor escolheu um pra `p_s{face}_v` e outro pra
`connections` na mesma rodada; provável bug de desambiguação em
`pillar_face_beams.py`, não investigado a fundo ainda — registrado como
próximo achado, não forçado).

## 2026-07-16 (cont.) — Card SVG provado com leitura real + achado + fix: recorte N2 do pavimento errado

Após o card de evidência ficar pronto, rodei `g2v_harness.py --par n3xn4` e
`--par n1xn2` de verdade para P35 e **li os SVGs no navegador** (Browser pane
via Playwright — a ferramenta de screenshot ficou instável no meio da
investigação, voltou a funcionar depois). Achados reais, não simulados:

- **n3xn4 (P35): SUSPEITO.** Estrutura, cotas, níveis e nomenclatura batem
  entre N3 (PARA/PASSA) e N4. Único ponto: densidade da hachura de topo em
  A/B parece menor no N4 — não deu pra confirmar com zoom (crop de região
  não é suportado no Browser pane) se é diferença real ou só efeito de
  escala das colunas largas vs estreitas. Registrado como achado severidade
  média, não como PASS cego.
- **n1xn2 (P35): achado real confirmado, depois corrigido.** A Foto N2 da
  ficha mostrava cabeçalho "COBERTURA - PD: 3.60" em vez de "13 PAVIMENTO -
  PD: 3.21". Confirmei lendo os DOIS DXFs fonte diretamente com `ezdxf`: o
  arquivo de 13_PAV realmente diz "13° PAVIMENTO - PD: 3.21"; existe TAMBÉM
  um `PIL_P35_motor_*.dxf` em
  `NOVA - ALIMONTI - PARAISO - COBERTURA E DECK - PL - R00/` com cabeçalho
  "COBERTURA - PD: 3.60" idêntico ao que apareceu na ficha. **Causa raiz
  encontrada e corrigida**: `_render_n2_recorte_b64`
  (`src/ui/widgets/pre_validation_dialog.py`) fazia
  `glob.glob(recortes_base + '/**/PIL_{item}_motor_*.dxf', recursive=True)`
  **sem filtrar por pavimento** — varre a árvore `recortes_reversos/`
  inteira (todos os andares) e pega `matches[0]` de uma lista ordenada por
  path completo (`reverse=True`), que por acidente alfabético favorece
  pastas "NOVA - ..." sobre "ALIMONTI - ...". Como nomes de item (ex. "P35")
  repetem entre pavimentos, isso troca silenciosamente o recorte exibido.
  Fix: filtrar `matches` pelo token do pavimento atual (`- {numero}`, mesmo
  padrão já usado em `_find_pil_recorte_fallback`) antes de escolher o
  primeiro. **Testado e confirmado visualmente**: regenerei a ficha de P35
  e o cabeçalho agora mostra "13 PAVIMENTO - PD: 3.21" corretamente.
- **Achado sistêmico, não resolvido ainda**: esse bug pode afetar qualquer
  item cujo nome se repita em mais de um pavimento (praticamente todo item
  numérico simples, já que a numeração se repete por andar/tipo). Vale
  rodar uma varredura ampla depois pra ver quantos itens (de qualquer
  classe, não só PIL) tinham a Foto N2 errada antes deste fix.
- **Bloqueio de infraestrutura à parte (contexto, não achado de QA)**:
  durante a investigação o disco `D:` ficou 100% cheio (`html_fichas/`
  sozinho tinha 37GB acumulados desde 11/07, sem política de retenção) e
  travou a regeneração da ficha (`OSError: No space left on device`). O
  dono identificou e removeu uma worktree órfã
  (`.claude/worktrees/happy-colden-fd91b6`, mesmo commit da main, sem
  mudança não commitada) que sozinha liberou 113GB.

**Correção de leitura (mesmo dia, lote de 46 itens):** ao continuar a leitura
visual em P1/P2, marquei "hachura de topo ausente no N4" como achado
(SUSPEITO) em P1 e P35. **O dono corrigiu**: isso é comportamento esperado,
não bug — consolidado em `docs/SA-ANALISE/CLASSES/PIL.md` §5.1 (sarrafo C/D
≥30cm vira horizontal+contagem em texto; hachura rosa de topo é do
vazio/abertura via `AR-CONC`, N3 tem e N4 não precisa ter). Vereditos de
P1 e P35 corrigidos de SUSPEITO para PASS nos relatórios G2-V. Lição:
antes de marcar achado de "elemento ausente" em G2-V/G5-V, checar se o
padrão já está documentado como comportamento esperado do robô SCR.

## 2026-07-16 (cont.) — G5-V (n3xn4) lido para os 35/35 itens com N2; achado real 2ª causa raiz do bug de pavimento

Concluída a leitura visual G5-V (`--par n3xn4`) dos 35 itens PIL com N2 no
13_PAV (P1-P35), em lote via Browser pane (técnica documentada em
`docs/ARETE-PLAYWRIGHT-QA-VISUAL.md` §"Leitura em lote via Browser pane" —
página HTML local agrupando ~7 itens por vez, viewport estreito 700px,
scroll+screenshot, ~1 chamada de ferramenta por item em vez de 4-6).
**35/35 PASS**, todos com o mesmo achado padrão não-bloqueante já
documentado (N4 sem hachura de vazio/abertura, severidade baixa).

**Achado real, 2ª causa raiz do bug de recorte-pavimento-errado (não a mesma
do achado de P35 acima):** ao tentar ler o par `n1xn2` para o mesmo lote,
o cabeçalho do card N2 de P1 mostrou "3° AO 12° PAVIMENTO - PD: 2.80" (nem
13° PAV nem COBERTURA — um terceiro pavimento errado, o "TIPO" recorrente).
Investigado com debug print real (não suposição): em rodadas de **classe
completa** (`headless_sa_analise.py --secao pilares`, sem `--item`),
`self._pavimento` chega em `_render_n2_recorte_b64` como o **nome bruto do
projeto** (`"TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA"`), não o rótulo
canônico `"13_PAV"` — só rodadas com `--item` (microciclo granular) passavam
pelo `canonical_pavimento()` antes. O fix de 16/07 anterior (filtrar
`matches` por `f'- {pav_num.group(1)}'`) assumia formato já canônico; no
nome bruto, o primeiro grupo de dígitos é "6000" (de "PE-6000"), o filtro não
casava com nada e o código caía de volta no bug antigo (escolhe
alfabeticamente "TIPO - 3° AO 12°..." em vez de "13° PAV...").

**Fix aplicado** (`src/ui/widgets/pre_validation_dialog.py::_render_n2_recorte_b64`):
chama `canonical_pavimento(self._pavimento)` (mesma função de
`src/core/ficha_utils.py` já usada pelo resto do pipeline) antes do regex de
dígito, em vez de assumir que quem chamou já normalizou. Testado: rodada de
classe completa (46 pilares) regenerada do zero, `P1` confirmado com
cabeçalho "13° PAVIMENTO - PD: 3.21" correto. **Acao futura sugerida (não
feita agora — fora do escopo desta rodada):** `_query_detail_recorte` (linha
~1353, mesmo arquivo) tem o mesmo padrão `re.search(r'(\d+)', self._pavimento
...)` sem `canonical_pavimento()`; vale auditar se sofre do mesmo problema em
algum caminho de rodada de classe completa.

**Correção de processo (mesmo dia):** o par `n1xn2` **não é** um gate visual
válido para PIL neste formato — os cards "N1" são geometria bruta do
Structural Analyzer (contexto próximo/distante), não uma ficha comparável a
N2. Isso já estava registrado em
`docs/ARETE-LOOP-PROCEDIMENTO-GERAL.md:224-226`: "`g2v_harness.py --par
n1xn2 --backend cli` só é admissível se seus dois cards forem as fichas
comparáveis; geometria bruta do SA contra recorte N2 é inconclusiva, não é
PASS nem FAIL." Sete vereditos PASS registrados por engano
(`20260716_pil_n1xn2_full/relatorio.json`, P1-P7) foram **revertidos** para
`veredito: null` com nota de invalidação — não usar essa rodada como selo
N1-V. `docs/LOOPING-CANONICO.md:268` continua listando `n1xn2` como o
comando de N1-V na tabela; há uma tensão entre essa linha e o comentário já
existente em `qa_pil_quadro_pavimento.py::_n1v_checklist_cell` ("não é
comparação de ficha N1×N2") e a regra do procedimento geral — registrado
aqui como pendência de doc, não resolvido unilateralmente.

**Fix da pendência auditada:** `_query_detail_recorte`
(`src/ui/widgets/pre_validation_dialog.py:1353`, usada pelo viewer "Gabarito"
da aba Convenção de Pilares) tinha o mesmo padrão de bug do
`_render_n2_recorte_b64` (regex de dígito direto em `self._pavimento` sem
`canonical_pavimento()`). Confirmado com teste isolado: `re.search(r'(\d+)',
"TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA")` (nome bruto do projeto, valor
real de `self._pavimento` em rodadas de classe completa) casava "6000" (de
"PE-6000"), gerando `pav_filter = '%- 6000%'` — não bate com nada no DB, o
filtro de pavimento é silenciosamente ignorado (aqui é *miss*, cai para o
fallback "3ª — qualquer PIL aprovado da obra", não *wrong-pick* como no
`_render_n2_recorte_b64`, porque a query é exact/LIKE em vez de glob
ordenado, mas ainda é o mesmo defeito de raiz). Fix aplicado: mesma chamada
`canonical_pavimento(self._pavimento or '')` antes do regex. Confirmado:
`canonical_pavimento("TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA")` →
`"13_PAV"` → `pav_num.group(1)` → `"13"` → filtro correto.

**Outros usos de `self._pavimento` auditados, não alterados (menor
severidade, fora do padrão do bug):** linha 1335 (`obra_recortes.pavimento_name
= self._pavimento`, comparação exata contra coluna do DB — se vier nome bruto
do projeto, é *miss* que cai pro próximo tier, não escolha errada) e linhas
4713-4714 (`sa_entry['nome'] == self._pavimento`, usado só para destacar a
linha "atual" numa lista de pavimentos na UI — cosmético). Nenhum dos dois
tem risco de selecionar arquivo/dado errado como os dois já corrigidos;
registrado aqui para não redescobrir, não corrigido agora (fora do escopo do
achado reportado).

**Padrão semelhante encontrado em outros 2 arquivos, não corrigido (risco
menor, fora do escopo):** `scripts/fidelidade_pilares.py:95` e
`scripts/fidelidade_vigas.py:87` têm o mesmo `re.search(r'\d+', pavimento)`
sem `canonical_pavimento()`, mas `pavimento` ali vem de `args.pavimento`
(flag CLI explícito de scripts standalone de fidelidade), não de um valor
auto-derivado internamente — erro de digitação do operador seria óbvio
(resultado vazio), não um bug silencioso de arquivo trocado. Registrado para
auditoria futura, não mexido agora.

## 2026-07-16 (cont.) — Quadro de estado: coluna N3×N4 conectada ao G5-V real

A coluna `n3_n4_ficha_passa` do `qa_pil_quadro_pavimento.py` estava
**hardcoded** como "⏳ não comparada / QA pendente" para todo item, nunca
lida de nenhum relatório real — mesmo depois do G5-V (n3xn4) ter sido
realmente lido para os 35/35 itens (entrada acima). Causa: a função
`_g2v_by_item` (linha 264) já suporta qualquer par/gate do harness, mas só
era chamada para `n1xn2`/N1-V e `n2xn4`/G2-V; nunca para `n3xn4`/G5-V.

**Fix**: adicionada a chamada `g2v_n3xn4 = _g2v_by_item(repo_root, pavimento,
"n3xn4", "G5-V")` e duas funções novas — `_n3_n4_ficha_para()` (célula
estática N/A, mesma razão estrutural de `_n4_g2_g2v_para`: N4 nunca tem
variante PARA) e `_n3_n4_ficha_passa(g2v_n3xn4.get(item))` (mostra o
veredito real, já que o card N3 do harness `n3xn4` já traz as duas variantes
PARA/PASSA lado a lado contra o único N4 — não há veredito separado por
variante, por isso cai inteiro na coluna PASSA, mesma convenção da coluna N4
acima). Testado com rodada real (`qa_pil_quadro_pavimento.py` completo):
P1/P4/P9 (amostra) mostram `"G5-V CLI (n3×n4) deste item: ✅ PASS (confiança
0.85) (SVG-vetorial)"` na coluna PASSA e o N/A estático na coluna PARA.
Também corrigido o texto do bullet de "limits" do quadro (linha ~783), que
ainda dizia "pipeline SVG-vetorial de PIL ainda não implementado" — agora
distingue G2-V (ainda PNG/legado, não mexido), G5-V (SVG-vetorial real,
35/35) e N1-V (descontinuado como gate, não é problema de formato de
imagem). `n3_n2_ficha_para/passa` continuam pendentes de verdade — não
existe par `n3xn2` no `g2v_harness.py` (`--par` só aceita `n2xn4`, `n1xn2`,
`n3xn4`, `grades`); construir esse par, se decidido necessário, é trabalho
novo de harness, não wiring de dado já existente.

## 2026-07-16 (cont.) — Par n3xn2 concluído: S7 fechado de verdade para os 35/35

O dono apontou o raciocínio certo: já que N4 foi aprovado contra N2 (G2-V) e
N3×N4 (G5-V) já bateu 35/35, o mesmo motor de comparação visual bastava para
N3×N2 — só faltava usar. Investigação mostrou que o par `n3xn2` **já estava
quase todo preparado** em `g2v_harness.py` (`PAR_FOCUS["n3xn2"]`,
`wanted_stages["n3xn2"]`, `choices`, help text, gate `"S7-N3N2"` — provavelmente
trabalho desta mesma sessão antes da compactação). Faltava só um detalhe: o
bloco que resolve o path do DXF N3 em disco (`if par == "n3xn4" and n3_dir is
not None:`) não incluía `n3xn2`, então o rastro de evidência (`evidencia_fontes`)
e a checagem de existência do N3 seriam pulados para esse par (a extração de
SVG em si não dependia disso, já que vem direto do HTML). Fix: `if par in
("n3xn4", "n3xn2") and n3_dir is not None:`.

Rodado `g2v_harness.py --par n3xn2 --backend cli` para os 35 itens (mesma
ficha corrigida de 15:47:49) e lido em lote via Browser pane (mesma técnica
de `docs/ARETE-PLAYWRIGHT-QA-VISUAL.md`, adaptada para 3 cards por item: N2,
N3-mode1/PARA, N3-mode2/PASSA). **35/35 PASS** — geometria, proporções,
segmentação e cabeçalho de pavimento batendo entre as duas variantes de N3 e
o gabarito N2, sem contaminação de item vizinho. Achados de estilo (não
bloqueantes, mesma classe dos já documentados): P18 tem "CAMBOTA"/"CORTE A-A"
extra no N2 (contexto do recorte humano, N3 não precisa replicar); P26 mostra
texto de contagem de sarrafo em todas as faces no N2 (anotação humana rica)
enquanto N3 só marca C/D≥30cm (convenção SCR minimalista) — nenhum dos dois é
divergência de conteúdo/geometria.

Conectado no quadro (`qa_pil_quadro_pavimento.py`): `g2v_n3xn2 =
_g2v_by_item(repo_root, pavimento, "n3xn2", "S7-N3N2")` + função
`_n3_n2_ficha()` nova. Diferente do par n3xn4 (onde a coluna PARA é N/A
estático porque N4-PARA não existe), aqui **as duas variantes de N3 existem
de verdade** e o harness já as lê juntas contra o mesmo N2 num veredito só —
por isso o mesmo texto aparece em `n3_n2_ficha_para` e `n3_n2_ficha_passa`,
não é célula estática. Testado com rodada real do quadro: P1/P9/P35 mostram
`"S7-N3N2 CLI (n3×n2, ambas variantes) deste item: ✅ PASS (confiança 0.85)
(SVG-vetorial)"` nas duas colunas.

**S7 agora fechado de verdade para os 35/46 pilares com N2** (os outros 11
não têm recorte N2 — fora de escopo estrutural destes gates, não pendência).
`n3_n4_ficha_passa` e `n3_n2_ficha_para/passa`: 35/35 PASS, com evidência SVG
vetorial real, lida item a item pelo agente, não número sozinho.

## 2026-07-17 — Hardening do PilEvidenceAuditor: zero tolerância a vínculo desconexo

O dono reportou (sessão anterior) um bug real visto no app: o campo
`dim` de alguns pilares foi confirmado pelo agente mesmo com o vínculo
apontando para o rótulo de uma viga vizinha em vez da cota do próprio
pilar. Investigação confirmou: `_audit_dim` já **detectava** isso
(`PIL-DIM-LINK-MISLABELED`, achado real documentado desde o caso de P35),
mas só registrava o achado como log — a decisão seguia confirmando via
bbox × ficha "Dimensão (b x h)", tratando o vínculo contaminado como um
problema à parte, não bloqueante.

**Fix** (`scripts/arete/qa_evidence_auditor.py::PilEvidenceAuditor._audit_dim`):
vínculo mislabeled agora força `REVISAR_HUMANO` sempre, mesmo quando o
texto solto da ficha bate com o bbox por coincidência — o próprio dado que
a UI destaca pro campo está errado, não é confiável independente do
resultado da comparação numérica.

**Segundo bug do mesmo padrão, achado ao auditar `_audit_name`**: quando
não havia NENHUM rótulo vinculado (`labels` vazio), o código confirmava
mesmo assim (`if pillar.name.upper() in texts or not labels`). Ausência de
evidência estava sendo tratada como confirmação. Fix: sem rótulo vinculado
vira `PENDENTE`, nunca `CONFIRMAR`. Mesmo bug replicado em
`LajEvidenceAuditor._audit_name` (mesma estrutura, mesmo autor) — corrigido
junto, mesma regra.

Suíte completa rodada após os dois fixes: 37/39 passam (2 falhas
pré-existentes e não-relacionadas — `test_global_discovery_keeps_beam_
families_separate_and_is_read_only` e `test_rag_consultation_marks_
unavailable_partition_as_degraded`, confirmadas via `git stash` como já
quebradas antes deste fix, de outra sessão mexendo em FV/RAG). Teste de
`dim` mislabeled atualizado para exigir `REVISAR_HUMANO` em vez do
`CONFIRMAR` antigo (`test_dim_flags_mislabeled_link_and_never_confirms`).

**Impacto real medido** (`qa_evidence_auditor.py review --classe PIL
--include-sealed`, 46 itens, read-only): **10/46 pilares** tinham o
vínculo `dim` genuinamente contaminado — P1, P10, P11, P17, P18, P24, P25,
P35, P41, P51. Não era um caso isolado do P35 já conhecido. Destes, **7 já
estavam selados** (`is_validated=1`): P10, P11, P17, P18, P35, P41, P51.

**Correção retroativa autorizada explicitamente pelo dono** (2026-07-17):
script `scripts/arete/tmp/retract_dim_qa_agente_2026-07-17.py` (transação
BEGIN IMMEDIATE/commit, isolado à tabela `pillars`, só o campo `dim`)
removeu a origem `qa_agente` de `dim` nos 10 itens e recalculou
`is_validated` pela cobertura real de campos obrigatórios. Resultado
confirmado: os 10 itens com `dim_origins=[]` (nenhuma validação falsa
remanescente) e `is_validated=0` para todos (os 7 que estavam selados
foram reabertos corretamente). Nenhum outro campo tocado — conferido campo
a campo em P35 (connections/name/faces/pilar_segs mantiveram suas origens
`qa_agente` intactas).

**Próximo passo natural (não feito ainda, fora do escopo deste fix):**
esses 10 itens agora têm `dim` REVISAR_HUMANO real — precisam de revisão
humana da cota declarada (ou reprocessamento do link no app) antes de
poderem ser reselados. O quadro (`qa_pil_quadro_pavimento.py`) já vai
refletir isso automaticamente na próxima rodada (lê `validated_fields_json`
fresco do banco).

## 2026-07-17 (cont.) — N/A laranja (agente) + campo pendente roxo, implementado

Depois da correção do backend (entrada acima), o dono pediu para completar
os dois pedidos visuais que tinham ficado pendentes por causa de outra
sessão ativa em `detail_card.py` — dono confirmou explicitamente que
poderia prosseguir mesmo assim ("já implemente").

**Design final** (documentado em `docs/CONVENCAO-SELOS-VALIDACAO.md`):

1. **N/A do agente fica laranja.** Sem coluna nova no banco: o agente
   (`qa_evidence_auditor.py`, op `mark_na`) prefixa `na_reasons[field_id]`
   com o marcador `ORIGEM_NA_AGENTE_MARCADOR = "[origem:qa_agente] "`
   (`src/core/validation_model.py`). A UI (`detail_card.py`) detecta o
   marcador (`_na_agente_e_tooltip`) e troca `STYLE_NA` (azul-info, N/A
   humano) por `STYLE_NA_AGENTE` (laranja) — tanto no campo quanto no botão
   N/A (`_na_button_qss`, chamado na criação do botão e de novo em
   `refresh_validation_styles`). `na_motivo_exibicao()` remove o marcador
   antes de mostrar pro usuário.

2. **Campo pendente do agente fica roxo.** Novo estado, ortogonal ao N/A e
   aos 3 selos: quando o agente conclui PENDENTE/REVISAR_HUMANO num campo
   obrigatório (ex. nível de viga que passa/chega que não deu pra
   determinar), isso precisa ficar visualmente diferente de "ninguém olhou
   ainda". Guardado em `extra_data_json['agent_pending'] = {field_id:
   motivo}` — chave nova, ZERO migração de schema, porque
   `database.py::load_pillars`/`load_slabs` já mescla `extra_data_json`
   direto em cima do item_data (`p.update(extra)`) — descoberto ao
   investigar por que `pillars.data_json` (achado inicialmente em
   `main.py:7143`) não existe mais na tabela real: é código morto de um
   schema anterior, protegido por try/except, nunca executa de fato; o
   caminho real é `load_pillars` lendo as colunas granulares
   (`links_json`/`validated_fields_json`/`na_fields_json`/`extra_data_json`
   etc.), as MESMAS que `qa_evidence_auditor.py` já escreve.

   Escrito por um subcomando novo, isolado de `apply`:
   `qa_evidence_auditor.py flag-pending --project-id ... --run <review-run>`
   — nunca confirma nada, nunca exige decisão "high", sempre seguro de
   rodar de novo (substitui o `agent_pending` anterior pelo mais recente do
   review; item que passou a confirmar tudo fica com `agent_pending={}`,
   limpando o roxo automaticamente). UI: `STYLE_PENDENTE_AGENTE` (borda
   roxa, `Colors.ACCENT_PURPLE`) só quando o campo não está validado nem
   N/A — nunca sobrepõe os outros dois estados.

**Rodado contra os 46 pilares reais**: `flag-pending` confirmou os 10 itens
do achado `dim` (entrada acima) com `agent_pending: {"dim": "..."}` e P29
com `agent_pending: {"connections": "1 face(s) de connections divergem..."}`
— hoje nenhum item tem `p_s{face}_v` pendente (já resolvido pelas sessões
anteriores), mas o mecanismo está pronto pra quando aparecer de novo.

**Testado**: 14 testes novos em `tests/test_validation_model.py` (marcador
de origem N/A, remoção do marcador pra exibição, leitura de
`agent_pending`) + smoke test real de instanciação do `DetailCard` (Qt
offscreen) confirmando que os estilos aplicam corretamente sem exceção
(`dim` com `agent_pending` → borda roxa `#a070ff`; campo N/A do agente →
borda laranja `#ff9800`). Suíte completa: 67/69 (os 2 restantes são as
mesmas falhas pré-existentes de outra sessão, já documentadas, não
relacionadas).

**Risco de colisão com sessão paralela**: `detail_card.py` tinha ~139
linhas não commitadas de outra sessão ativa (migração para
`_field_has_human_validation`/normalização de links). Editado de forma
cirúrgica — só os blocos de estilo N/A e o loop de `refresh_validation_
styles`, nenhuma linha da outra sessão tocada ou revertida. Se a outra
sessão commitar antes desta mudança, rodar a suíte de novo pra confirmar
que não houve conflito silencioso.

## 2026-07-19 — Root-cause real do bug `dim` (10 itens): motor corrigido, não patch de dado

- **Contexto**: os 10 pilares com `dim` `REVISAR_HUMANO` (P1, P10, P11, P17,
  P18, P24, P25, P35, P41, P51 — achado de 2026-07-17) tinham `links['dim']`
  apontando pro rótulo de uma viga vizinha (`V301`, `V302`, `V312`, `V325`,
  `V330`, `V304`, `V309`, `V328`, `V301`, `V320`) em vez da cota real do
  pilar. Instrução do dono: nada de correção humana manual nem write direto
  no banco — achar a causa no motor, corrigir, rerodar, confirmar que liga
  sozinho.
- **Causa raiz encontrada** (`src/core/pillar_analyzer.py:180-188`,
  `PillarAnalyzer.analyze()`): o bloco "FORÇAR VÍNCULOS REAIS DA PRÉ-FICHA"
  (`main.py:6904-6941`) calcula `links['dim']` corretamente a partir do bbox
  geométrico do polígono (`min(pw,pl)xmax(pw,pl)`), procurando o texto exato
  no DXF ou usando o valor calculado como fallback. Mas **depois** desse
  bloco, `PillarAnalyzer.analyze(p_data)` roda de novo e reexecuta uma busca
  textual ingênua por `dim` com regex `\d+([xX]\d+)?` (sem âncoras) num raio
  de 400 — essa regex casa com o número de QUALQUER rótulo vizinho (ex.:
  "V301" tem dígito "301"), então sobrescreve o vínculo correto com o nome
  de uma viga sempre que ela estiver mais perto que o texto da cota real (ou
  quando não há texto de cota desenhado — caso destes 10 itens, que usavam
  só o fallback calculado). Achado por instrumentação (`print` temporário em
  3 pontos: antes/depois do bloco FORÇAR, depois do `PillarAnalyzer`),
  confirmando `links['dim']` correto logo após o bloco FORÇAR e já
  contaminado logo depois do `PillarAnalyzer` — sem nenhuma outra escrita de
  `links['dim']` em `main.py` no meio do caminho.
- **Fix**: mesmo padrão já usado pro campo `name` (`identity_locked`). O
  bloco FORÇAR agora seta `p_data['dim_locked'] = True` depois de calcular o
  vínculo real; `PillarAnalyzer.analyze()` só roda a busca textual de `dim`
  se `not p_data.get('dim_locked')`. `dim_regex` continua definida fora do
  guard (usada também no laço de faces, `p_s{face}_v_*_d`).
- **Bug intermediário durante o fix**: primeira versão do guard deixou
  `dim_regex = ...` dentro do `if not p_data.get('dim_locked')`, causando
  `UnboundLocalError` silencioso (capturado pelo `except Exception` do loop,
  que só loga via `self.log` — invisível em headless) pra **todo** pilar com
  `dim_locked=True` (ou seja, todo pilar com pré-ficha, quase todos).
  Descoberto adicionando `print`+`traceback.print_exc()` temporário no
  `except` do loop de pilares. Corrigido movendo `dim_regex` pra fora do
  guard.
- **Validação real (DB)**: `headless_sa_analise.py --secao pilares --wait`
  (sem persist, só leitura) confirmou os 10 `dim_link_pos_analyzer` corretos
  após o fix. Rodada completa `--persist-db --wait` (sem `--secao`, ~25 min,
  gera+persiste as 4 classes) confirmou os 10 valores no banco real:
  P1=19x66, P10=19x60, P11=19x80, P17=19x120, P18=19x79, P24=19x80,
  P25=19x60, P35=19x60, P41=19x50, P51=19x50 — todos batendo com o bbox do
  `points_json`. `qa_evidence_auditor.py review --classe PIL --item <10>` →
  `CONFIRMAR` nos 10 (evidência `dim_geometry`, bbox coerente com
  polígono). `apply --seal-complete` → todos `is_validated=1`, origem
  `qa_agente`, `agent_pending` vazio (sem marcação roxa residual).
- **Nota operacional**: `--persist-db` sem `--secao` roda as 4 classes e
  **reexporta o pack HTML inteiro duas vezes** (uma export inicial +
  uma reexport pós-N3 quando `fundos_viga`/`laterais_viga`/`lajes` estão no
  escopo) — ~25 min cada vez neste pavimento. O DB COMMIT acontece bem antes
  do fim do processo (log `[SA-HUMAN] DB COMMIT transacional`); dá pra
  verificar/auditar/selar assim que essa linha aparece, sem esperar o resto
  do reexport terminar — só não se pode finalizar o processo (regra do
  projeto: nunca matar o dono do lock).

## 2026-07-19 (cont.) — Gate visual G5-V (n3xn4) pós-fix: 8/8 lidos, PASS

Depois do fix + persist + selo geométrico (entrada acima), 8 dos 10 itens
(P1, P10, P11, P17, P18, P24, P25, P35 — P41/P51 fora do escopo do gate,
mesma exclusão de sempre) já tinham veredito `PASS` no G5-V de 2026-07-16,
só que **anterior ao fix**: como `--persist-db` regenerou o N3 (`N3 PL
PARA+PASSA: 92 gerado(s)` no log), aquele veredito antigo ficou tecnicamente
obsoleto. Rerodei `g2v_harness.py --par n3xn4 --item <8>` e li os SVGs de
verdade (Browser pane, técnica de galeria local, uma página por SVG desta
vez — página única com os 24 SVGs empilhados travou a ferramenta de
screenshot, provavelmente por peso; por item funcionou sem problema).

**Resultado: 8/8 PASS** (confiança 0.88). Estrutura ABCD (4 faces,
proporções, cotas por face) coerente em N3 para todos, batendo com a
geometria do `dim` corrigido hoje. Achado registrado (severidade baixa, não
bloqueante): **P1** mostra N4 com PD genérico (2.80) divergente do PD real
do pavimento (3.21, usado em N3) e sem hachura/chapisco — mesmo padrão de
gap do gerador N4 já documentado em P8 (2026-07-16), não relacionado ao fix
de `dim_locked` (dim alimenta N1→N3, nunca N2→N4). P35 foi o melhor caso
(N4 com PD igual e hachura completa), confirmando que o gap é uma
característica pré-existente do gerador N4 para certos itens, não uma
regressão desta sessão. Vereditos gravados em
`scripts/arete/relatorios/g2v/20260719_pil_dimfix_n3xn4/relatorio.json`.

## 2026-07-20 — mini-RAG (B1) testado em PIL: disponível, sem ganho ainda

MR-3 (`scripts/arete/relatorios/20260718_minirag_d0d1/MR3-RELATORIO.md`)
testou `qa_evidence_auditor.py review --classe PIL --session-index <índice>`
no 13_PAV: regressão zero (560/560 decisões idênticas com/sem o índice), mas
**cobertura B1 = cobertura baseline (10 = 10)** — nenhuma entrada extra de
`human_event_logs`, porque essa tabela **não tem nenhuma linha `classe=PIL`
hoje** (checado direto no DB). Não é bug do índice nem do adaptador PIL — é
ausência de dado-fonte (nenhuma aprovação em lote/ensino humano registrado
com motivo para PIL ainda). **Não adicionar `--session-index` como prática
obrigatória em revisões PIL agora** — não atrapalha, mas também não ajuda.
Reavaliar quando `human_event_logs` acumular linhas PIL (ex.: após uma rodada
de aprovação em lote como a que já existe para LAJ).
