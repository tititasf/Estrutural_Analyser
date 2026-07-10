# Relatorio rapido — LAJ 13_PAV — L319 cotas especiais + UI sidebar

Data: 2026-07-07 11:37 -03:00

## Resultado

- L319: o gerador agora adiciona cotas de projecao em recortes especiais, em vez de depender apenas da cota horizontal/alinhada da aresta. Isso cobre:
  - distancias do degrau ate linhas de painel/parede;
  - alturas locais do recorte em L;
  - intersecoes do chanfro com linhas verticais de painel.
- A regra so ativa em poligonos complexos. Retangulos simples continuam com cotagem minima canonica.
- UI Comparison Engine: o painel esquerdo agora compacta os combos e mostra nome curto da obra quando o banco retorna caminho absoluto. O caminho completo fica em `userData`/tooltip.

## Validacao executada

- `python -m py_compile src/ui/modules/comparison_engine.py scripts/gerar_lj_dxf_stog.py`
  - Resultado: OK
- `python -m pytest tests/test_smart_panner_general_rules.py tests/test_laj_visual_reference_contract.py tests/test_motor_reverso_laj_dynamic_layers.py -q --basetemp .pytest-tmp-laj-ui-cotas2`
  - Resultado: `23 passed`
- `python scripts/arete/arete_runner.py --classe LAJ --pav 13_PAV --item L319`
  - Resultado: `1P / 0F / 0B`, L319 com `COTA=18`, `PAINEIS=7`
- `python scripts/arete/arete_runner.py --classe LAJ --pav 13_PAV`
  - Resultado: `31P / 0F / 0B`, Arete `100.0%`
  - Relatorio: `scripts/arete/relatorios/20260707_113543/RELATORIO.md`
- `python scripts/arete/g2v_harness.py --classe LAJ --pav 13_PAV --par n2xn4 --backend cli --item L319`
  - Imagem: `scripts/arete/relatorios/g2v/20260707_113519/LAJ_L319_n2xn4.png`
  - Veredito registrado: `SUSPEITO`
- `python scripts/arete/gerar_status.py`
  - Resultado: `docs/STATUS.md` atualizado

## Observacao de qualidade

Nao foi selado PASS visual para L319. A cotagem N4 evoluiu, mas o G2-V ainda nao confirma equivalencia visual integral N2/N4; portanto permanece `SUSPEITO` ate validacao visual humana ou ajuste do render/verificacao.
