# Relatório Arete — Sessão 2026-06-12: Harness AR-0.1..AR-0.4 construído

**Rodada:** 20260612_harness_construido
**Executor:** Cowork (Sonnet 4.6) — modo autônomo
**Status:** HARNESS PRONTO — aguardando execução do smoke test no ambiente local

---

## O que foi construído

| Story | Arquivo | Status |
|-------|---------|--------|
| AR-0.1 | `scripts/arete/arete_config.py` | ✓ escrito |
| AR-0.1 | `scripts/arete/ficha_adapter.py` | ✓ escrito |
| AR-0.2 | `scripts/arete/gerar_n4_item.py` | ✓ escrito |
| AR-0.2 | `scripts/arete/roundtrip_ficha.py` | ✓ escrito |
| AR-0.3 | `scripts/arete/paridade_visual.py` | ✓ escrito |
| AR-0.4 | `scripts/arete/arete_runner.py` | ✓ escrito |

---

## Por que não rodou ainda

O workspace Linux do sandbox não subiu nesta sessão (HYPERVISOR_VIRT_DISABLED —
virtualização de hardware desabilitada no ambiente de execução do Cowork).
Os scripts precisam ser rodados no Python local do usuário (onde ezdxf e o projeto
já estão instalados).

---

## Como executar o smoke test (AR-0.1 validação)

```bash
cd D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/scripts/arete

# 1. Smoke test de 1 item de cada classe (AR-0.1)
python ficha_adapter.py all

# 2. Se tudo PASS: rodar G1 round-trip para P1 (AR-0.2)
python roundtrip_ficha.py PIL P1

# 3. G2 paridade visual para P1 (AR-0.3) — requer o N4 gerado em step 2
python paridade_visual.py \
  "D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-2_Triagem/recortes_reversos/ALIMONTI - PARAISO - 13° PAV.- PL - R00_motor/PIL_P1_motor_178105101634.dxf" \
  "D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/scripts/arete/tmp/PIL_P1/Fase-6_Execucao_CAD/PL_preview_P1.dxf" \
  --png relatorios/20260612_harness_construido/P1_comparacao.png

# 4. Runner completo PIL (AR-0.4)
python arete_runner.py --classe PIL
```

---

## Arquitetura do harness

```
scripts/arete/
├── arete_config.py       # paths, tolerâncias, campos obrigatórios, escopo
├── ficha_adapter.py      # DB → JSON layout Fase-4 + smoke test
├── gerar_n4_item.py      # N2 → DXF N4 (1 item ou batch)
├── roundtrip_ficha.py    # G1: N2→N4→re-extração→diff
├── paridade_visual.py    # G2: score por layer + render PNG
├── arete_runner.py       # orquestrador G0→G1→G2→G6 + relatórios
├── relatorios/           # outputs por rodada
└── tmp/                  # pastas adapter temporárias (limpar com adapter limpar_tmp())
```

## Fluxo do adapter (DA-A3)

```
DB.campos_json → strip _er_meta → tmp/PIL_P1/Fase-4_Sincronizacao/JSON_Pilares/P1.json
                                 → subprocess gerar_pl_dxf_stog.py --obra tmp/PIL_P1 --item P1
                                 → tmp/PIL_P1/Fase-6_Execucao_CAD/PL_preview_P1.dxf
```

Geradores não foram modificados. Zero toque em src/ui/.

---

## Próxima ação (AR-1)

Após smoke test PASS → `python arete_runner.py --classe PIL`

FAILs esperados na primeira rodada:
- G1: campos que o motor reverso não consegue re-extrair do DXF N4 gerado
  (ex: grade_1, distancias, par_*)
- G2: layers presentes no recorte que o gerador não emite (ou vice-versa)

Protocolo: diagnosticar 1 FAIL por vez via PNG, identificar causa, corrigir no
motor_reverso_pil.py ou gerar_pl_dxf_stog.py, regressão do golden, repetir.

---

_Arete Quality Gates — sessão 2026-06-12_
