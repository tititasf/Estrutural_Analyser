# Relatório Arete — LAJ 13_PAV — âncoras de degrau e cotas de recorte

Data: 2026-07-06 23:55 BRT

## Escopo

- Itens focais: L318 e L319.
- Pedido: painéis devem usar 244/122/60, mas também tentar alinhar juntas com degraus/recortes para evitar painel em L; cotar alturas locais e recortes especiais.

## Alterações aplicadas

- `gerar_lj_dxf_stog.py`
  - Detecta degraus internos do contorno como âncora de paginação no eixo X.
  - Redistribui spans separados por âncora com módulos preferenciais.
  - Ignora micro-âncoras próximas da borda (`< 30 cm`) para não regredir lajes rasas.
  - Adiciona cotas verticais secundárias quando há spans de altura distintos.
  - Adiciona cotas `DIMENSION` para arestas de recorte/chanfro não cobertas por cotas principais.

- `motor_reverso_laj.py`
  - Espelha a regra segura de âncora no eixo X para roundtrip.
  - Mantém eixo Y desativado para essa canonicalização porque L319 depende de JSON Fase-4 oficial/intocável.

- Testes
  - Atualizados para exigir junta no degrau de L318.
  - Atualizados para exigir cotas verticais nos dois lados quando há duas alturas.
  - Cobrem veto de micro-âncoras/ruído.

## Validação executada

- `python -m pytest tests\test_laj_visual_reference_contract.py tests\test_motor_reverso_laj_dynamic_layers.py tests\test_smart_panner_general_rules.py -q --basetemp .pytest-tmp-laj-all4`
  - Resultado: `21 passed`.

- `python -m py_compile scripts\gerar_lj_dxf_stog.py scripts\motor_reverso_laj.py`
  - Resultado: OK.

- Arete focado:
  - L318: G1 PASS, G2 PASS.
  - L319: G1 PASS, G2 PASS.
  - L328-L331: revalidados após veto de micro-âncora; todos PASS.

- Regressão LAJ 13_PAV:
  - `31P / 0F / 0B`
  - Relatório: `scripts/arete/relatorios/20260706_235213/RELATORIO.md`

- G2-V CLI:
  - Run: `scripts/arete/relatorios/g2v/20260706_235311/relatorio.json`
  - L318: `SUSPEITO`
  - L319: `SUSPEITO`

## Decisão técnica

L318 recebeu a melhoria segura: a junta do eixo X pode coincidir com o degrau quando isso evita painel em L e não quebra G1/G2.

L319 não recebeu a canonicalização plena no eixo Y porque isso quebrava G1 contra a ficha N2/Fase-4 oficial. Como JSONs Fase-4 são intocáveis nesta etapa, a melhoria visual completa de L319 fica pendente de reextração/reselo autorizado.

## Triagem

Entrada adicionada em `scripts/arete/relatorios/triagem_erros/Obra_TREINO_1_13_PAV_lajes.jsonl`:

- `laj-L318-L319-g2v-ancora-degrau-cotas-recorte-20260706`

