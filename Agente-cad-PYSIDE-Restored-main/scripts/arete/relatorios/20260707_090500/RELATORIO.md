# Relatorio rapido — LAJ 13_PAV — L309 + UI Comparison Engine

Data: 2026-07-07 09:05 -03:00

## Resultado

- Bug visual do painel esquerdo corrigido: o `Comparison Engine` usava `setFixedWidth(16777215)` no `LevelColumn`, inflando o `minimumSizeHint` e criando scroll horizontal gigante. Agora a coluna tem `minimumWidth(0)` e `QSizePolicy.Expanding`.
- Paginacao de L309 corrigida na regra geral: vao de 311 cm nao gera mais recorte sub-60. A distribuicao antiga `122 + 47 + 20(uniao) + 122` virou `122 + 20(uniao) + 169`.
- A regra nao e hardcoded por item: esta em `smart_panner.py` e e espelhada no gerador/motor para malhas retangulares simples.
- Guard rail mantido: quando existe HLAZ explicita, a canonicalizacao nao sobrescreve a ficha. Isso preservou L312/L315.

## Validacao executada

- `python -m pytest tests/test_smart_panner_general_rules.py tests/test_laj_visual_reference_contract.py tests/test_motor_reverso_laj_dynamic_layers.py -q --basetemp .pytest-tmp-laj-l309-panner8`
  - Resultado: `23 passed`
- `python -m py_compile src/ui/modules/comparison_engine.py scripts/smart_panner.py scripts/gerar_lj_dxf_stog.py scripts/motor_reverso_laj.py`
  - Resultado: OK
- `python scripts/arete/arete_runner.py --classe LAJ --pav 13_PAV`
  - Resultado: `31P / 0F / 0B`, Arete `100.0%`
  - Relatorio: `scripts/arete/relatorios/20260707_090203/RELATORIO.md`
- `python scripts/arete/gerar_status.py`
  - Resultado: `docs/STATUS.md` atualizado

## Veredito visual

L309 nao foi selada como PASS visual.

O G2-V `scripts/arete/relatorios/g2v/20260707_085412/LAJ_L309_n2xn4.png` ficou como `SUSPEITO`: o N4 melhorou a distribuicao dos paineis, mas a referencia visual N2 ainda mostra malha/hachuras antigas. Assim, o resultado numerico 31/31 nao e usado como verdade visual para L309.

## Pendencia

Reabrir/recarregar a app para validar a correcao do layout do Comparison Engine e regenerar/visualizar L309 contra a referencia N2 atualizada antes de qualquer fechamento visual.
