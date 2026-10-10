# Gate CAD pós-SA — funcionamento, classes, funções e descobertas

**Status:** canônico · **Criado:** 2026-10-09 · **Reescrito:** 2026-10-10 (estado publicado na VPS)
**Escopo:** global (todas as obras e pavimentos), classes PIL, LAJ, FV e LV
**Autoridade:** complementa o [Mapa do Conhecimento](MAPA-DO-CONHECIMENTO.md), as [Decisões do Dono](DECISOES-DO-DONO.md) e os manuais de classe em `docs/SA-ANALISE/CLASSES/`. Em conflito sobre **o que o gate mede e como roda**, este doc vence; sobre **a regra de interpretação** de cada classe, vence o manual da classe.
**Deploy:** `docs/HANDOFF-DEVOPS-VPS-HETZNER.md` §10.10–10.11.

---

## 1. O que é

O **gate CAD pós-SA** mede no **DXF original** o que o Structural Analyzer (SA) declarou e diz, por item, se **confere**, **diverge** ou está **incerto**. É determinístico: lê linhas, polilinhas, textos e hachuras do desenho, sem modelo de IA, sem nome de layer e sem tocar no estado do SA.

Ele **substituiu as camadas QA por CLI** (L1/L2/L3), que eram lentas (15–40 min por item, fila parada em 04/10, ver `project_qa_fila_clis`). O gate leva segundos por pavimento:

| Classe | Tempo típico por pavimento (13_PAV) |
|---|---|
| PIL | ~0,6 s |
| LAJ | ~0,3 s |
| FV | ~9–16 s |
| LV | ~1 s |

### 1.1 Quando roda (automático)

1. O job SA do portal termina (`portal/app/pipeline_runner.py`, bloco "Gate CAD pós-SA"). O gancho existe nos **dois** ramos: SA+N3 e SA sem N3 (`--sa-only`, o botão SA do portal). Até 10/10 o ramo `--sa-only` não chamava o gate, e o selo ficava velho depois de rodar só o SA.
2. `qa_cad_gate_run.best_effort(obra_dir, pav, secao, item_names)` roda o gate da seção e dos itens do job. Ele **nunca derruba o job**: em erro, só registra no log.
3. O resultado vai para o **sidecar** `<obra>/.portal_overrides/qa_cad_gate/<pav>.json` (schema, pavimento, source, source_sha256, `classes.{PIL,LAJ,FV,LV,VC}`, `tempos_s`, `gerado_em`).
4. O portal lê o sidecar:
   - **selo CAD** na lista lateral de cada classe: ✓ confere, ✕ diverge, ? incerto (`drill_grade.js` → `renderGateCadBadge`);
   - **caixa do gate** dentro das fichas PIL, LAJ, FV e LV (`obra_detalhe.html` → `window.gateCadHtml`; `fv_ficha.js`, `lv_ficha.js`);
   - API: `n1_routes.py` → `classe_status` (lista) e `item_status` / `_gate_cad_ficha` (ficha).
5. **Desatualizado:** cada item guarda o `snapshot_sha256` do que foi medido. Se o SA mudou depois, `item_status` marca `desatualizado=true`: o selo fica velho até rodar de novo.

Não há botão manual: rodar o SA já roda o gate.

### 1.2 Status por item (`qa_cad_gate_run.resumo`)

| Status | Quando |
|---|---|
| `confere` | todos os contatos medidos sem erro |
| `diverge` | algum contato **medido** com erro (o desenho diz outra coisa) |
| `incerto` | nada diverge, mas algum contato não pôde ser medido **e bloqueia promoção** |
| `indisponivel` | sem DXF original ou erro de leitura |

Contato `uncertain` com `blocks_promotion=False` (usado em FV e LV para o que é informativo) **não** derruba o item para incerto.

---

## 2. Princípios (inegociáveis)

1. **A medida é dona do número.** Valor medido no CAD vence estimativa, IA ou visão.
2. **Zero aprovação falsa.** Na dúvida, `uncertain`; nunca aprovar por proximidade.
3. **Sem nome de layer.** Classificação por geometria e texto (`feedback_motor_layer_independence`).
4. **Só leitura.** O gate não altera o estado do SA, `project_data.vision` nem os DXFs.
5. **Não inventar campo.** O gate só confere o que o SA **declara**. A v1 do LV media uma "altura útil" que o SA não declara e gerou 274 divergências falsas; foi removida.
6. **Divergência precisa de prova.** Antes de declarar um achado como real, renderizar o DXF e ler o PNG (`feedback_ler_png_antes_de_perguntar`).

---

## 3. Arquitetura e funções

| Arquivo | Função | Papel |
|---|---|---|
| `portal/app/qa_cad_gate.py` | `measure` | PIL: paredes, rótulos e contornos de pilar |
| | `measure_slabs` / `_measure_slabs` | LAJ: rótulo, `h=` e cota escritos dentro do contorno |
| | `measure_beams` | FV: arestas, seção, apoios, inventário, níveis (`_beam_levels`) |
| | `measure_fv_tags` | FV: âncora das tags no SVG da ficha (só na evidência) |
| | `measure_lateral_beams` | LV: arestas, seção, laje da face, extremos, sobreposição, coerência |
| | `for_snapshot` | despacho por classe (PIL/LAJ/FV/LV) com o DXF de produção |
| | `for_evidence` | medição para o pacote de revisão (FV inclui tags) |
| | `errors` | lista de erros de um relatório |
| `portal/app/qa_cad_gate_run.py` | `run_pavimento` / `best_effort` | roda o pavimento e grava o sidecar |
| | `measure_state` | mede por seção (`SECOES`) e itens |
| | `resumo`, `classe_status`, `item_status`, `item_name` | leitura para lista e ficha |
| `portal/app/qa_cad_gate_cortes.py` | `measure_obra` / `measure_pavimento` | VC: cortes originais, interpretados, cobertura e degraus (seção 5) |
| `portal/app/pipeline_runner.py` | bloco pós-SA | chamada automática |
| `portal/app/routers/n1_routes.py` | `_gate_cad_ficha`, uso de `classe_status` | API das fichas e da lista |
| `portal/app/qa_versions.py`, `qa_review_contract.py` | uso na adoção/QA | trava CAD na rodada de QA |

**Seções e itens** (`SECOES`, `CLASSE_PORTAL`):
- PIL: `pilares`, `pilares_especiais`; item = nome do pilar.
- LAJ: `lajes`; item = nome da laje.
- FV: `fundo`; item = nome da viga.
- LV: `laterais_viga`; item = `VIGA|para` ou `VIGA|passa`, com as faces A e B juntas e as quatro coleções `lateral_{a,b}_{para,passa}`.

**Testes:** `portal/tests/test_qa_cad_gate*.py` (gate, run, lv, fv, fv_nivel, pil, laj).

---

## 4. Por classe

### 4.1 Pilar (PIL) — `measure`

- **Mede:** contorno do pilar (polilinha fechada, mesmo com `Closed=false` e ponto repetido); paredes de viga que **chegam ou atravessam** cada face; rótulo da viga na parede; distâncias da viga à quina.
- **Guardas:** identidade do contorno, vínculo face↔viga, distâncias.
- **Descobertas:**
  - **"Link fantasma" era alucinação** do dossiê de outra IA: no 13_PAV, 11 dos 13 eram vigas reais atravessando o pilar com a mesma largura (P42/P46/P48/P51). Face sem parede fica `uncertain` + `ghost_suspect`; **nada é removido**.
  - Parede que atravessa a face conta; para achar o rótulo vale só o trecho externo. Com dois rótulos na parede contínua, vale o do **primeiro vão**.
  - `dist_esq`/`dist_dir` são gravados, mas comparados **sem orientação** (`sorted`): a convenção esq/dir por face ainda não foi conferida contra o SA.
  - VF301 "19/66" no SA de 10/08 era a seção do pilar P8 (texto vizinho), não a da viga.

### 4.2 Laje (LAJ) — `measure_slabs`

- **Mede:** rótulo, espessura `h=` e cota de nível escritos **dentro** do contorno da própria laje (E1). Regiões rebaixadas (`slab_steps`) têm espessura própria.
- **Guardas:** `identidade_contorno`, `dimensoes_espessura`, `niveis`.
- **Limite:** sem texto dentro do contorno, fica incerto (E1 ausente); não procura texto por proximidade.

### 4.3 Fundo de viga (FV) — `measure_beams`

- **Mede:** arestas longas sobre paredes originais; seção bw/h escrita na faixa; apoios e limites (pilar, viga, laje); inventário de segmentos (sem lacuna ou sobreposição); **níveis** por segmento (`_beam_levels`: laje que toca, cota escrita, datum do pavimento, exceções hachuradas do original).
- **Guardas:** `identidade_contorno`, `dimensoes`, `apoios_limites`, `inventario_segmentos`, `niveis`.
- **Visão de corte no fundo:** peça local com vão ≤ 100 cm e saída ≤ 50 cm, agrupada por ≤ 4 cm e preenchimento residual ≤ 1 cm², é **visão de corte**, não abertura; não segmenta o fundo (`_visao_corte_t`, `_section_view_unions`).
- **T de mesma altura (D-90):** a viga que chega atravessa a outra; a trava de chegada lateral está em `measure_beams`.
- **Evidência:** `measure_fv_tags` exige a âncora da tag no SVG a ≤ 0,5 cm (só na revisão).

### 4.4 Lateral de viga (LV) — `measure_lateral_beams` (v2, `cad.qa_original_laterais/v2`)

Por segmento das quatro coleções (A/B × Para/Passa):

| Aspecto | Guarda | O que confere |
|---|---|---|
| arestas | `identidade_contorno` | a face está sobre uma parede colinear do original; o lado do corpo é dado pela parede oposta a bw |
| seção | `dimensoes` | bw/h escritos na faixa = `lv_cell.sections`/`dim`; descarta seção logo abaixo de rótulo `P\d+` (texto de pilar) |
| laje da face | `laje_face` | lajes na faixa de 0,5–6 cm fora da face (trecho ≥ 5 cm, a mesma regra do `lv_beam_scene`) = `lv_cell.slabs`, inclusive a espessura das regiões rebaixadas |
| extremo início/fim | `apoios_limites` | traço perpendicular tocando a face; se não houver, fica incerto |
| sobreposição | `inventario_segmentos` | segmentos da mesma face sem sobreposição |
| coerência | `consistencia_alertas` | length, nível em segmento valid, level × `lv_cell.level`, `level_slabs` ⊆ `lv_cell.slabs`, width × `lv_cell.dim` |

- **Não mede a altura do painel:** o SA não a declara; quem calcula é o gerador N3.
- **SA antigo sem `lv_cell`:** as lajes declaradas vêm de `level_slabs`, sem espessura, e a coerência fica `uncertain` com o aviso "rodar o SA de novo". Na obra thierry 14_PAV, o resultado foi de 64/64 diverge para 60/4.
- **Resultados (10/10):** 13_PAV TREINO 63 confere / 9 diverge; 14_PAV TREINO 62/4; thierry 14_PAV 60/4.
- **Achados reais, conferidos em PNG:**
  - regiões rebaixadas não declaradas pelo SA: L313 h=10 (V302, V318), L410 h=11 (V406, V409, V411);
  - face 0,5 cm fora da parede: V324 B, V422 B;
  - L316 a mais no V330 2-A;
  - Passa sobre pilar sem laje (V309A B seg 1 → L319; V330 A seg 4-A → L318). O dono decidiu (**D-91**) que o Passa sobre pilar também tem laje, e o SA foi corrigido em 10/10 (`lv_beam_scene.passa_slabs`).

---

## 5. Visão Corte (VC) — `qa_cad_gate_cortes.py` (D-92, implementado 10/10)

O dono pediu (10/10) que o gate revise também as **Visões Corte**, originais e interpretadas: divergência ali aponta **erro de nível**, que é grave. Funciona como o gate de **níveis e dimensões das lajes e de cada segmento de viga**.

**Quando roda:** no mesmo pós-SA, sempre que a seção do job for `lajes`, `fundos_viga`, `laterais_viga` ou o pavimento inteiro (`qa_cad_gate_run.VC_SECOES`). A seção `pilares` não refaz os cortes. Classe `VC` no sidecar; item = viga (`V302`) ou laje com degrau (`L319`). Custo: ~6,5 s no 13_PAV, porque inclui `structural_cut_overlay.collect_sections`.

**Onde aparece:** caixa própria, "Gate Visão Corte (níveis e degraus)", logo abaixo da caixa do gate nas fichas FV, LV e LAJ (`item_status` devolve `visao_corte`; `gateCadHtml` desenha). O selo "desatualizado" usa `inputs_fingerprint`, a impressão digital do que o SA declarou para o item.

| Parte | Função | O que confere | Guarda |
|---|---|---|---|
| Corte original | `measure_original` | O polígono do corte lido pelo SA vira a união das peças fechadas do DXF contidas nele. O perfil T/L é medido nas 4 orientações (`profile`): bw, h e braços de laje por lado (desnível do topo, espessura). Fica a orientação com menos erros contra a ficha do SA (`beam_w/h`, `side_*_laje_name`, `beam_lajes_side_*`, `own/neighbor_dist_top`, `*_slab_height`, `direction`). | `dimensoes`, `niveis` |
| Corte interpretado | `measure_calculated` | Para cada corte calculado (`section_contract`): desnível = (topo − cota escrita na laje)×100 e espessura contra o `h=` escrito dentro do contorno (E1, `slab_values` reaproveita `measure_slabs`). No corte relativo, confere o degrau entre os lados. | `niveis`, `dimensoes` |
| Cobertura | — | Segmento de fundo sem corte (`soffit_coverage` pending) e corte que o SA não montou (`blocked`) ficam **incertos bloqueantes**. | `inventario_segmentos` |
| Degrau de laje | `measure_slab_step` | Corte original do degrau: duas espessuras e os dois offsets (topo/fundo) contra `slab_steps` (Δnível e Δfundo). Degrau sem corte no DXF é aviso não bloqueante. | `degraus` |

**Regras aprendidas na calibração (13_PAV):**
- **Alma por peso de comprimento:** a alma é o intervalo transversal que ocupa mais comprimento ao longo da altura. Pela interseção, a quebra inclinada estreitava a alma, e o corte 19/120 era lido deitado (bw 12, braço 19–30).
- **Espora ≤ 3 cm não é braço** (`ARM_MIN_CM`).
- **Alma quebrada** (símbolo de quebra): h não é medível, aviso não bloqueante. Braço na metade de baixo do desenho (viga invertida) é medido **a partir do fundo da viga**. Assim o V330 19/120 (lajes no fundo, desnível 107/110) confere.
- **Espessura esquemática:** se o símbolo desenha uma espessura diferente da declarada, mas a declarada é o `h=` da planta, vira **nota** ("vale a planta"), não divergência. Vale para o corte original e para o degrau (ex.: L319 BD5 com símbolo 10/13 e planta 11/14).
- **Ficha vazia** (o SA não leu direção nem lajes): incerto bloqueante, não divergência.

**Resultado 10/10 no portal** (job 766f8b05, 13_PAV): 46 itens, **39 confere / 4 diverge / 3 incerto**.
- V302 e V303 (interpretado): o corte usa laje de 10 cm com desnível de 3 cm, mas a planta diz `h=13` com a cota no topo (L309, L312, L316, L321–L324). Possível erro de nível no SA; a investigar.
- V314 e V320 (original 19/55): o desenho tem laje dos dois lados; o SA declara um lado "nulo". Conferido em PNG.
- Incertos: V316 (ficha do corte não lida, beam_w ausente); VF203 e VF301 ("topo + laje + fundo não fecha a altura da viga").

**Não faz ainda:** coerência `top_level_m` do corte × nível do segmento FV; degraus de viga sem corte desenhado (mudança de fundo entre segmentos), que hoje só aparecem quando há corte.

## 6. Camada Jev / IA (fora do gate automático)

O gate automático **não usa IA**. A consulta delimitada a Jev (pergunta de lista fechada, alternativas ancoradas em handles, opção `INSUFFICIENT`, controle negativo de remoção) é trilha separada, documentada em `docs/MASTERPLAN-QA-JEV.md`. Haiku é proibido no QA (`feedback_qa_sem_haiku`).

---

## 7. Governança

- **Deploy:** sempre na VPS, pelo §10.6 do handoff: backup, `portal_jobs` sem job ativo, restart e smoke. **Nunca** usar overlay `/tmp/ovl`: o pacote regular de `/opt` vence e o systemd não lê `PYTHONPATH`.
- **Arquivos copiados do Windows** chegam com CRLF: normalizar para LF antes de commitar no ledger.
- **Fix de gate** termina com a rodada no portal e a leitura dos achados, não só com testes verdes (`feedback_qa_loop_to_seal`).
- Toda divergência mostra o valor do SA, o valor medido e onde (face, segmento, coordenada).

## 8. Histórico

| Data | Marco | Commits (local / ledger VPS) |
|---|---|---|
| 2026-10-10 | gate PIL/LAJ/FV publicado; "link fantasma" vira `uncertain` | 13a391ce1 / e11ef77 |
| 2026-10-10 | gate roda sozinho após o SA; FV 2x mais rápido | 59954cf7c / 9fb348e |
| 2026-10-10 | selo CAD na lista e caixa na ficha de pilar | f3e8342d6 / 9df13d5 |
| 2026-10-10 | LV v2 religado; caixa nas fichas FV/LV; SA antigo sem `lv_cell` | 5f6497993 / 5f3d183 |
| 2026-10-10 | D-91: Passa sobre pilar declara a laje da face (SA corrigido) | ver git log / arquivo vivo (backup `/root/bak_lv_d91_202610101650`) |
| 2026-10-10 | gate também no ramo `--sa-only` (botão SA) | árvore (ramo sa-only ainda sem commit) / arquivo vivo (backup `/root/bak_saonly_gate_202610101718`) |
| 2026-10-10 | D-92 implementada: gate Visão Corte (classe VC), caixa nas fichas FV/LV/LAJ | ver git log / arquivo vivo (backup `/root/bak_vc_gate_202610101609`) |
