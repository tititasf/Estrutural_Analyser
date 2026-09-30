# Correção — nível de laje com bug de unidade (13_PAV, 2026-09-26)

**Ordem do dono:** "se você sabe o que deveria ser, já ajusta o banco".
**Projeto:** `dd238e47-1dc6-4f63-a760-4e7ce19a7386` (TMC-EST-PE-6000-13P, Obra_TREINO_1 / 13_PAV).

## Causa

`main.py::_infer_slab_level_from_cut_deltas` somava o delta da visão de corte (em **cm**,
como diz a docstring de `_cut_view_level_delta`) ao nível da laje vizinha (em **m**).
+3 cm virou +3 m; +7 cm virou +7 m; −30 cm virou −30 m. O comentário no código já
registrava o sintoma ("deslocou laje em 7 m") sem a causa.

## Conserto no código

- `src/core/slab_level_inference.py`: `cut_delta_level` (cm → m) e `gate_cut_delta_level`
  — portões P2 magnitude (< 1 m), P3 pavimento (≤ 0,75 m do nível de referência),
  P4 planta (concorda com a cota escrita, ±2 cm). Falhou um → `needs_review`, o valor
  não é aplicado. Planta concorda → `confirmed`.
- `main.py`: usa as duas funções; registra `gates` em `level_inference`.
- Testes: `tests/test_slab_level_cut_delta.py` (casos reais L317/L318/L324).

## Dados corrigidos (3 passadas, dry-run revisado antes de cada uma)

| Laje | Antes | Depois | Evidência |
|---|---|---|---|
| L317 | 855.12 | **852.15** | L308 (humano, 852.12) + 3 cm; P2/P3 ok |
| L318 | 852.19 (validado) | **852.19** | inferência por delta dava 822.19 → 851.89; **conflito registrado**: vale o validado; −30 cm pode ser rebaixo real — revisar |
| L324 | 859.12 | **852.19** | L331 + 7 cm; **confirmado pela cota escrita na planta (852.19)** |
| L325 | 859.12 | **852.19** | herdava da L324 |

| Passada | Script | Alcance |
|---|---|---|
| 1 | `corrigir_nivel_laje.py` | 52 linhas / 113 trocas: lajes, rótulos de vizinhas, espelhos `slab_elements`/`fase3_fichas`, "Laje adjacente" nas vigas, faces dos pilares |
| 2 | `corrigir_cadeia.py` | 13 linhas / 132 trocas: pilares P9, P18, P23, P24, P26, P33, P49 — nível da laje nas faces, topo (`nivel_saida_abs`) e base (`nivel_chegada_abs`, mesmo deslocamento); espelhos da própria laje |
| 2b | ajuste manual | L318: espelhos seguem 852.19 validado + conflito anotado; fase3 P18/P32 alinhados à tabela de pilares |
| 3 | `corrigir_vigas.py` | 24 vigas / 169 trocas: nível do segmento recalculado pela regra "maior cota das lajes que tocam o trecho" (docs/NIVEL-SEGMENTO-FUNDO-VIGA.md); **16 estimados** (segmento sem lista de lajes: deslocamento do erro) marcados em `_correcoes` |

Varredura final: **0** ocorrências de 855.12 / 859.12 / 822.19 no projeto (fora dos
registros `valor_anterior`). 855.12 não é nível real deste prédio: o pé-direito do 13_PAV
é 3,21 m (`pd_pavimento_cm`), o pavimento de cima fica em 855.33.

## Não tocado

- `dxf_entidades`, `cache_dxf`: texto original do desenho.
- Projeto antigo `4869be2b…` (importação de junho): sem os valores do bug nas lajes afetadas.
- Backups (`backup_*.json`, fora do git): estado anterior de cada linha tocada.

## Pendente

- Revisar L318 (852.19 validado × −30 cm do corte) e os 16 segmentos estimados.
- Quem roda headless LV/PIL/FV no 13_PAV recebe agora os níveis corrigidos; a
  recomputação normal deve reproduzir os mesmos valores (mesma regra).
