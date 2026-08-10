# Diário SA — LV

Use o modelo de `docs/SA-ANALISE-PROGRESSO-POR-ITEM.md` e o manual
`docs/SA-ANALISE/CLASSES/LV.md`. Entradas são append-only e
registram lado A/B, PARA/PASSA, apoios, laje/visão-corte e N3 por variante.

## 2026-07-17 18:55 — Obra_TREINO_1/13_PAV — V301/face A
- Etapa: S6/S7 — N3 independente / auditoria QA N3, veredito visual N2×N4 (G2-V)
- Estado: PENDENTE (gap real pequeno e localizado, não Arete ainda)
- Fontes: `scripts/arete/relatorios/g2v/v301_n2_inventory/` (inventário linha-a-linha,
  regenerado), `scripts/arete/relatorios/g2v/v301_arete_review/vision/*.png` (SVG→PNG
  lido via Read), DB `reverse_eng_fichas` classe=LV elemento_id=V301, reextração ao
  vivo de `scripts/motor_reverso_lv.py::extrair_ficha_lateral_viga`.
- Evidência observada:
  1. O inventário original (antes desta sessão) reportava 44 linhas + 14 cotas +
     2 textos "MISSING_N4" para face A. Corrigido bug de classificação em
     `scripts/arete/tmp/_v301_n2_inventory.py` (faltava excluir geometria/cota/texto
     fora da largura do próprio item, x<0 ou x>total_w — pertence aos vizinhos
     V309A/V312 desenhados no mesmo clip de contexto). Após o fix: **30 linhas + 5
     cotas + 2 textos reclassificados como `N2_CONTEXTO_VIZINHO_nao_copiar`** (não é
     gap). Gap real: **14 linhas + 5 cotas**, 0 textos.
  2. As 14 linhas + 5 cotas reais concentram-se todas na mesma feição: a "abertura"
     50.5×65 no canto do painel largo (161.5 = 28.7+21.8+111 já visualmente presente
     como grupo, mas o vazio y=0-65 sob a abertura e o "ombro" y=65 não estão
     completos no N4) e a extensão "marco" (h_total 124 vs h_body 109, últimos ~40cm
     de largura).
  3. Causa-raiz confirmada na FONTE (motor), não no gerador: reextração ao vivo de
     `motor_reverso_lv.extrair_ficha_lateral_viga` contra o DXF N2 real reproduz
     `h_total=161.5` (valor de LARGURA, não altura — bug) em vez de 124; os painéis
     de 28.7/21.8 (abertura) saem com `height1=44` copiado do painel 1 em vez de
     reconhecer painel cheio (109) + recorte de canto; os painéis 19/21.2 (zona
     marco) saem como `laje_sup_local=7.0` em vez da extensão mais alta.
  4. **A ficha N2 persistida em `reverse_eng_fichas` (classe=LV, elemento_id=V301)
     está STALE**: h_body=125, h_total=132, os 4 painéis de panels_A/face_units têm
     `height1=125.0` uniforme (sem nenhum degrau capturado) e `laje_sup_local=7.0`
     em todos — versão anterior ao fix que já corrigiu height1=44 do painel 1. O N4
     atual (109/124/44 corretos) não vem dessa linha do DB; vem de uma reextração
     mais nova ainda não persistida. Ferramentas que leem o DB direto (`qa_evidence_
     auditor.py`, `qa_profile_probe.py`) verão dados desatualizados até essa ficha
     ser regravada.
- Tentativa/caminho: inspeção read-only (DB, motor ao vivo, PNGs); fix aplicado
  somente no script de auditoria (`_v301_n2_inventory.py`, reclassificação de
  contexto), formula geral (bounds check pela largura do item), não hardcode de
  V301. Doc canônico `docs/QA-INVENTARIO-MINIMO-VALIDACAO-VISUAL.md` §6 atualizado
  com os números corrigidos para não contaminar sessões futuras com o "44
  MISSING" antigo.
- Hipóteses rejeitadas: "N4 tem 44 linhas de geometria realmente faltando" —
  descartada; 30/44 eram geometria do vizinho no mesmo clip, não do item.
- Decisão: nenhum campo confirmado/selado. Achado aberto, causa geral, ainda sem
  fix no motor.
- Próximo passo: (a) persistir a ficha V301 no DB a partir da extração corrente do
  motor (upsert `reverse_eng_fichas`) para destravar QA/tools que leem o DB; (b)
  corrigir `motor_reverso_lv.py` para reconhecer abertura de canto (width×height,
  não copiar height1 do painel anterior para sub-larguras geradas por V-lines de
  abertura) e h_total real (não confundir com largura agrupada) — regra geral, não
  só V301; (c) rodar regressão nas outras 31 vigas LV do 13_PAV antes de selar;
  (d) regenerar inventário + G2-V após o fix.
- Não-regressão: pendente — fix do motor ainda não aplicado nesta sessão.

## 2026-07-20 — mini-RAG (B1) estendido a LV: usar `--session-index` no `review`

MR-3 (`scripts/arete/relatorios/20260718_minirag_d0d1/MR3-RELATORIO.md`) mediu
que `qa_evidence_auditor.py review --classe LV --session-index <índice>` traz
**+4 entradas reais de `human_event_logs`** (status `CAPTURED`) que o `review`
sem `--session-index` não alcança. Regressão zero: 394/394 decisões idênticas
com/sem o índice no 13_PAV. Ganho menor que FV/LAJ em volume absoluto (só 4
linhas `CAPTURED` existem hoje para LV na base inteira), mas real. **Recomendação
para próximas sessões LV:** passar `--session-index
scripts/arete/relatorios/qa_session_index/<obra>_<pav>` nas revisões reais, mesmo
protocolo de FV/LAJ.
