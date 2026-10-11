# 11/10 — Gate CAD 13_PAV: VC, VF301/VF203, PIL especial, V330

## Correções (uma por causa)
| Causa | Arquivo | Commit | VPS (backup) |
|---|---|---|---|
| Miolo do encontro V302×V316 em planta lido como corte | `src/core/plan_corridor_cells.py` | 7da855654 (encaixe em `main.py` só na VPS: âncora é drift) | /root/bak_corredor_202610110230 |
| T genérico VF301/VF203: topo/fundo de mesma largura | `portal/app/lv_cut_map.py identified_frame` | sem commit (bloco é drift) | /root/bak_vf_frame_202610110300 |
| PIL em L: chegada da caixa D com canto impossível derrubava o SA de pilares | `src/core/pillar_special_faces.py` | 1cbacab5d | /root/bak_pil_l_boxd_202610110310 |
| V330 2-A: fusão de células sobre cruzamento invertido perdia as lajes da 2ª célula (L316) | `src/core/lv_inverted_crossings.py _inverted_segments` | sem commit (arquivo inteiro não versionado, de outra sessão) | /root/bak_lv_merge_slabs_202610110600 |

## Gate 13_PAV após as correções
- LAJ 31 confere · LV 70 confere / 2 incerto · VC 34 confere / 12 incerto
- Incertos legítimos: VF202 viga diagonal (gate LV só mede faces ortogonais); VC 6 degraus sem corte original + 6 vigas do núcleo vazado.
- PIL 9/10/27 e FV 17/10/9: código do gate em edição ativa por outra sessão (PIL 04:11; FV `qa_cad_gate.py` 05:28 VPS / 02:43 local, coerência length×extensão trocada em vigas verticais). Não tocado.

## Próximo FAIL
Coerência FV `length ≠ extensão do contorno` (V315/V317/V319/V321/V325/V332) — com a sessão dona do gate FV.
