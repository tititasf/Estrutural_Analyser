# GRADES PIL — configuração visual INI/NOVA

Data: 05/07/2026  
Escopo: sarrafos horizontais das GRADES de pilares, usados pelos geradores N3/N4.

## Regra confirmada pelo dono

- As distâncias dos horizontais são configuráveis, não hardcode geométrico.
- INI e NOVA mantêm perfis independentes.
- A interface apresenta `Base → H1`, `H1 → H2`, ..., `H8 → H9`.
- O gerador converte esses intervalos em posições acumuladas a partir da borda inferior da grade.
- Só são desenhados horizontais cuja espessura completa cabe na altura disponível.

## Valores iniciais importados da referência ROBO_GRADES/SCR

- INI — posições: `60, 170, 280, 390, 500, 610, 720, 830, 940 cm`.
- NOVA — posições: `30, 120, 210, 300, 390, 480, 720, 830, 940 cm`.

Fonte: `_ROBOS_ABAS/Robo_Pilares/pilares-atualizado-09-25/src/robots/ROBO_GRADES.py`
e `config/templates_grades.json` do robô legado.

## Implementação

- `config/pl_grade_visual_profiles.json`: fonte persistente dos dois perfis.
- `scripts/pl_grade_visual_config.py`: validação, conversão intervalo↔posição e escrita atômica.
- `scripts/gerar_pl_dxf_stog.py`: N3/N4 aplicam o perfil correspondente a `--visual-mode`.
- `src/ui/modules/comparison_engine.py`: aba `GRADES INI/NOVA` na configuração visual de PIL.
- `interpretacao_abcd.html`: regra registrada sem alterar as regras anteriores.
- Log schema v2: `pil13-grades-horizontal-config-20260705`, marcado por humano.

## Verificação

- `py_compile`: PASS.
- Testes específicos/autocad: 6 PASS.
- Testes de modo visual e layout executados até o teste LV preexistente: 30 PASS; a falha posterior é de layout LV e não toca PIL/GRADES.
- Inspeção visual local, sem API: `scripts/arete/tmp/grades_ini_nova_config_visual.png`.
  Para uma grade de 280 cm, INI desenhou 60/170 e NOVA desenhou 30/120/210.

## Regressão PIL — sete pavimentos

| Pavimento | Resultado atual | Relatório |
|---|---:|---|
| 13_PAV | 35P / 0F | `20260705_194537` |
| 12_PAV | 34P / 2F | `20260705_194952` |
| 14_PAV | 27P / 1F | `20260705_195356` |
| 1_PAV | 15P / 23F | `20260705_195714` |
| 2_PAV | 34P / 2F | `20260705_200130` |
| TERREO | 18P / 5F | `20260705_200538` |
| COBERTURA | 6P / 23F | `20260705_200812` |

Os FAILs adicionais observados em 1_PAV, TERREO e COBERTURA ocorrem em G1 no campo
`paineis_intervals_D`; G2/GRADES não é a causa. Contraprova com o espaçamento antigo
reproduziu exatamente os mesmos FAILs em 1_PAV/P11, TERREO/P16 e COBERTURA/P11,
mantendo G2 PASS. Portanto, esse estado concorrente de ABCD/round-trip não foi criado
pela configuração de horizontais.

Nenhum golden foi selado ou atualizado.

## Pendente do dono

A aprovação Nível 3 das fichas GRADES dos 35 pilares do 13_PAV permanece separada;
este pavimento não possui recorte N2 de GRADES para comparação automática.
