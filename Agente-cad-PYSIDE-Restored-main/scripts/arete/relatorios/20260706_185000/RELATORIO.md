# Relatório Arete — LAJ 13_PAV — correção de regressão visual N4

Data: 2026-07-06 18:50 -03:00

## Escopo

- Classe: LAJ
- Pavimento: 13_PAV
- Itens focais: L316 e L318
- Motivo: tela do dono mostrou regressão visual no N4: formatação de cotas diferente do padrão, retângulo/HLAZ fantasma e hachuras externas contaminando a área da laje.

## Diagnóstico

- Não foi encontrado hardcode por item (`L316`, `L318`) nem medidas fixas específicas nos motores/geradores.
- O extrator atual reconhece L318 como contorno em degrau `3139 x 201`, com HLAZ local `726 x 20`.
- A regressão visual vinha do gerador:
  - `cotas_paineis` eram desenhadas como `TEXT` na layer `PAINEIS`, quebrando a formatação canônica do robô.
  - HLAZ local era desenhada como `LWPOLYLINE` na layer `Hachura`, aparecendo como retângulo fantasma.
  - `apoios_hachurados` crus do recorte eram copiados para o N4 isolado, trazendo hachuras externas/de contexto para dentro da comparação.

## Correções

- `scripts/gerar_lj_dxf_stog.py`
  - N4 isolado voltou a usar cotagem canônica por `DIMENSION`.
  - HLAZ local agora é `HATCH` sólido, não contorno `LWPOLYLINE`.
  - `apoios_hachurados` só são desenhados quando `include_context=True`; no N4 isolado ficam fora para não contaminar a área da laje.
- `scripts/arete/roundtrip_ficha.py`
  - `apoios_hachurados` foi marcado como campo de contexto externo, fora do round-trip G1 de N4 isolado.
- `tests/test_laj_visual_reference_contract.py`
  - Contrato visual atualizado para exigir cotas canônicas e HLAZ sólida.

## Validação executada

- `py_compile`:
  - `scripts/gerar_lj_dxf_stog.py`
  - `scripts/motor_reverso_laj.py`
  - `scripts/arete/g2v_harness.py`
  - `scripts/arete/arete_runner.py`
  - `src/ui/modules/comparison_engine.py`
- Testes focados:
  - `tests/test_laj_visual_reference_contract.py`
  - `tests/test_motor_reverso_laj_dynamic_layers.py`
  - `tests/test_arete_g6_visual_gate.py`
  - `tests/test_g2v_harness_lv_paths.py`
  - Resultado: `19 passed`
- Arete LAJ 13_PAV:
  - `python scripts/arete/arete_runner.py --classe LAJ --pav 13_PAV`
  - Resultado: `31P / 0F / 0B`
  - Relatório: `scripts/arete/relatorios/20260706_184405/RELATORIO.md`
- G2-V CLI:
  - `python scripts/arete/g2v_harness.py --classe LAJ --pav 13_PAV --par n2xn4 --backend cli --item L316 L318`
  - Relatório: `scripts/arete/relatorios/g2v/20260706_184504/relatorio.json`
  - PNGs:
    - `scripts/arete/relatorios/g2v/20260706_184504/LAJ_L316_n2xn4.png`
    - `scripts/arete/relatorios/g2v/20260706_184504/LAJ_L318_n2xn4.png`

## Veredito visual

- L316: `SUSPEITO`
- L318: `SUSPEITO`

Motivo: não há novo PASS visual. A geometria e a formatação principal foram corrigidas, mas o G2-V ainda precisa de validação humana para:

- confirmar a política de hachuras de apoio/contexto no N4 isolado;
- confirmar posição/legibilidade de cada cota no Comparison Engine.

G6 permanece bloqueado corretamente até existir PASS G2-V estrito com checklist completo.

## Triagem

Log append-only atualizado:

- `scripts/arete/relatorios/triagem_erros/Obra_TREINO_1_13_PAV_lajes.jsonl`
- Nova entrada: `laj-L316-L318-g2v-formato-cotas-hachura-contexto-20260706`

`scripts/arete/gerar_status.py` executado e `docs/STATUS.md` regenerado.
