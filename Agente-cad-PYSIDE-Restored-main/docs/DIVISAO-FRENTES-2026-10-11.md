# Divisão da missão em 2 frentes — 2026-10-11

Objetivo comum: QA do SA zerado (ou só incertos justificados) no 14_PAV, 13_PAV e TIPO_TESTE →
ciclo rápido completo aprovado → publicação na VPS → conferência visual final. Erro visual volta ao ciclo rápido.

Os números (14_PAV 223, 13_PAV 347, TIPO_TESTE 1.167) somam ocorrências sobrepostas e resumos derivados:
atacar **família/causa**, nunca item. Duas réguas existem e as duas precisam fechar:
QA pós-SA do ciclo de desenvolvimento e gate CAD da VPS (`.portal_overrides/qa_cad_gate/<pav>.json`).

## Frente 1 — Codex: PILARES + pré-processamento
Dono exclusivo de: `src/core/pil*`, `pillar_*`, `pil_qa_*`, `qa_original_polyline.py`, pré-processamento/triagem/recortes, N3/N5 de pilares.

1. **Encontros de pilares 14_PAV (142):** paredes, identidade, seção e continuidade dos contatos.
2. **PIL 13_PAV no gate CAD:** 10 diverge / 27 incerto (P1, P10, P18, P24–P27, P33–P35); separar corpus × geometria (V308×VF203, V310) de erro de motor.
3. **V517/P16** e **alertas de identidade de contatos** no TIPO_TESTE.
4. **N3 dos pilares especiais:** reprodução completa das 8 faces do U (circulares seguem adiados).
5. **Pré-processamento/triagem:** convenções de níveis, pilares, cortes e regiões; recortes manuais/OSNAP.
6. **Performance N3 de pilares** (N5 NOVA 19 itens/96,88 s como linha de base).

## Frente 2 — Claude: VIGAS (FV/LV), LAJES, NÍVEIS, CORTES + integração final
Dono exclusivo de: `fundo_viga*`, `lateral_viga*`, `lv_*`, `fv_*`, `qa_fv_*`, `slab_*`, `niveis_*`, `qa_cad_gate*.py`, `qa_cad_gate_cortes.py`, retenção de disco.

1. **Fundos 14_PAV:** eixos (3) — parcela × nome × eixo original; limites (78) — corredores, extremos, oblíquos.
2. **Regressão do gate FV 13_PAV** (36 → 17 confere): coerência `length ≠ extensão do contorno` com comprimento/largura trocados em vigas verticais (V315/V317/V319/V321/V325/V332) + VF301 seg 8 sem nível.
3. **Níveis:** nível regional da L406 pelo corte local; nível do degrau da L17.
4. **V408:** variações de seção.
5. **Laterais/VC:** manter LV 70/0 e VC 34/0 no 13_PAV; estender ao 14_PAV e TIPO_TESTE.
6. **Performance N3 completo** (meta 8 min; medido 11min22s) e medição das fichas.
7. **Armazenamento:** retenção dos snapshots de desenvolvimento (`/tmp/sa-dev-validation`) e os 5 links históricos quebrados.
8. **Integração final (depois da Frente 1 entregar):** fluxo triagem → pré-processamento → SA → N3 → N5, seleção de pavimento, execução granular, combinações de modos; publicação e conferência visual.

## Regras de convivência
- Arquivo fora da sua lista = pedir à outra frente; `main.py` e `headless_sa_analise.py` são compartilhados: só trechos próprios, avisar no commit.
- Git: índice compartilhado — `hash-object`/`update-index` só dos próprios caminhos; nada de `git add -A`.
- VPS: checar `portal_jobs` ativos antes de reiniciar; backup em `/root/bak_*`; publicar só linhas próprias.
- Fix de uma frente que muda contrato da outra (ex.: viga que chega no pilar) vira nota em `DECISOES-DO-DONO.md`/doc da classe antes do deploy.
- Cada rodada: `scripts/arete/relatorios/<timestamp>/RELATORIO.md` + próximo FAIL.
