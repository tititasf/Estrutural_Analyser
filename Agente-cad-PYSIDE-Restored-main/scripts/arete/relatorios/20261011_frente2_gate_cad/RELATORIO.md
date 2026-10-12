# Frente 2 — gate CAD pós-SA (FV/LV/LAJ/VC) — 11/10/2026

Escopo: `docs/DIVISAO-FRENTES-2026-10-11.md`, Frente 2. Tudo publicado na VPS e
rodado lá (`qa_cad_gate_run.run_pavimento`), backups em `/root/bak_*`.

## Commits (só hunks próprios)

| Commit | O que muda | Backup VPS |
|---|---|---|
| 7ce256b9a | VC: desempate topo/fundo pelo topo **desenhado** (V408 14_PAV, símbolo 60×14 com SA h=55) | `bak_vc_frame_measured_h_202610111800` |
| 0b8ffea49 | QA-FV: eixo local por rótulo colinear; fatia de tampa abaixo de EPS fica para as guardas de ponta (V412/V418, V303 seg 6) | `bak_fv_eixo_colinear_202610111830` |
| ec8fd3e3e | LAJ: região sem `h=` próprio ganha altura/nível pelo corte que tem degrau escrito (L406/96B 14_PAV → h=12, 855,22); VC aceita o número | `bak_slab_degrau_escrito_202610111930`, `bak_vc_degrau_escrito_202610111945` |
| d40253068 | VC: laje desenhada numa peça só entre dois símbolos entra recortada; lado com laje declarada e sem braço no desenho vira incerto (TIPO_TESTE) | `bak_vc_laje_compartilhada_202610112030` |
| f1ee24525 | QA-FV: extremo aberto (as duas arestas terminam sem traço de fecho) vira incerto, não "corte por rótulo" (V513/V522 TIPO_TESTE) | `bak_fv_extremo_aberto_202610112130` |

Infra, sem versionamento: `cad-limpeza.timer` agora roda a cada 3 h (backup
`bak_limpeza_timer_202610111850`). A limpeza com `--apply` liberou 23,67 GB
(disco de 98% para 76%). Os 5 vínculos históricos quebrados estão fechados: o
R9 removeu os symlinks e os arquivos apagados não têm volta.

## Resultado no portal (sidecars da VPS, depois dos fixes)

Contagens em confere / incerto / diverge. O PIL é da Frente 1 (Codex) e não
entra aqui.

| Pavimento | LAJ | FV | LV | VC |
|---|---|---|---|---|
| 13_PAV (TREINO_1) | 31/0/0 | 24/12/0 | 70/2/0 | 34/12/0 |
| 14_PAV (TREINO_1) | 22/0/0 | 22/11/0 | 66/0/0 | 29/14/0 |
| TIPO_TESTE (Teste_Stephanie, SA novo fe113b57) | 21/0/0 | 23/6/1 | 55/0/5 | 19/19/0 |

Antes dos fixes, o TIPO_TESTE estava assim:

- FV: 4 diverge;
- VC: 7 diverge;
- LV: 5 diverge.

13_PAV e 14_PAV ficaram inalterados depois dos dois últimos fixes.

### O que sobra no TIPO_TESTE (todos medidos e renderizados: são achados reais do SA, não do gate)

- **FV V521 seg 2:** o fundo começa 1 cm depois do traço (seg 1 termina em 2277,8 e seg 2 começa em 2278,8). A lacuna é do SA.
- **LV V517 A Para/Passa seg 1×2:** sobreposição de 19 cm sobre o P16. O P16 fica entre dois trechos da mesma viga, e a lateral corre pela face curta C/D, então os dois trechos englobam o pilar (G10/D-64). A regra de dono único por parede (linha 912 de DECISOES) preserva explicitamente a exceção C/D. **Pergunta ao dono**, abaixo.
- **LV V512 B Passa seg 2:** o Passa estende 201 cm ao longo do poço do ELEVADOR, sem traço colinear (o fundo da caixa não está desenhado).
- **LV V522 B seg 7:** pedaço de 1,5 cm entre a borda de laje e o P14, que o SA já marca "fora da linha". Um teste não commitado de outra sessão (`test_void_boundaries_keep_pillar_whole_and_short_free_strip`) exige manter a faixa de 1,5 cm. **Não mexi**; o `lateral_viga_cells.py` tem trabalho em curso de outra sessão.
- **LV V522 B Passa seg 16:** face entre V502 e V501 sem traço; só a hachura termina ali.
- **VC incertos novos:** V504 L7, V522 L17/L19, V526 L13 e VF3. Nesses cortes o SA declara laje do outro lado (pela planta, com `neigh_slab_height=0`), mas o símbolo desenha só a laje do rótulo. É lacuna da ficha do SA (N1).

## Perguntas ao dono

1. **VF301 seg 8 (13_PAV):** nível da união sob a invertida, 852,12 (L308) ou 852,19 (L317)?
   - **Resolvida 12/10 (dono: "compare os cortes").** Cortes da VF301: 7 + 48 sobre a laje de 852,12, topo 852,19, fundo 851,64. Corte da V332 19/55 rente à L317 (852,19): fundo 851,64. Fundo único, sem degrau, igual ao seg 7. Decisão FV-UNIAO-NIVEL-PELO-CORTE-20261012.
   - Achados medidos no estado publicado: (a) L317 está com 852,22 no SA, contra 852,19 da D-64 (regressão); (b) ~~o contrato vertical da VF301 é "nível estimado"~~ — corrigido 12/10: os contratos apresentados (`entries`) já usam `original_cut_datum` com topo 852,19; só as colisões físicas (`physical_entries`) ficam em 852,12. O pendente do gate vem da união do seg 8 (`level=''`, `unresolved_local_slab_references`), não do contrato.
     - L317, causa real (12/10): na VPS o `main.py` chamava `paired_cut_level_source` sem as lajes (o guarda de região não tinha o que olhar), e o grafo de cortes (`cut_view_rooted_graph`) lia o corte V330 pelo lado da L316, cujo degrau h=10 o guarda só procurava na vizinha. Fix: o guarda olha os degraus das duas lajes; a VPS recebeu só a linha da chamada (o resto do `main.py` local tem trabalho de outras sessões não publicado). Na coleta, a L317 passou de 852,22 a "sem nível", e o resolvedor por região fica livre para a D-64.
     - Conferido no portal (cadeia 69ea6c49, 12/10 18:12): pacote L317 = 852,19 (`scoped_cut_wing_relative_delta_cm`, degrau L316 852,16 + 3); estado publicado L316/L317 = 852,19, nenhum 852,22 restante. Gate 13_PAV: LAJ 31/0/0, FV 25/11/0 (era 24/12), LV 70/2/0, VC 34/12/0. A VF301 segue incerta (852,12 × 852,19): é a correção 2.
     - Correção 2 (12/10): `merge_opposite_arrivals` recebe também os contratos apresentados; quando os dois lados da união têm `original_cut_datum` com o mesmo topo/base (L308: 7 + 48, L317: 0 + 55 → topo 852,19, base 851,64), a união não fica pendente e mantém a regra da linha (`highest_touching_slab`), com `level_proof`. Conferido no portal (cadeia 54e69bc0): VF301 seg 8 = 852,19 (L317), prova base 851,64; gate VF301 **confere**; 13_PAV FV 26/10/0 (era 25/11), demais classes iguais.
2. **V517 × P16 (TIPO_TESTE):** pilar entre dois trechos da mesma viga, com a lateral pela face curta C/D. Qual trecho engloba o pilar? Os dois englobando dá painel sobreposto.
   - **Resolvida 12/10 (dono):** a lateral passa só pela face C do P16; em Para e em Passa é um segmento único. Defeito do SA: parte em dois e sobrepõe 19 cm. Decisão LV-FACE-CURTA-SEGMENTO-UNICO-20261012.

## Próximo FAIL a atacar

- LV V512: Passa estendido ao longo de vazio sem traço (SA `measured_passa`).
- Lacuna de 1 cm entre fundos do SA (V521).
- Desempenho do N3: meta 8 min, medido 11 min 22 s.
- Integração E2E final depois da Frente 1.
