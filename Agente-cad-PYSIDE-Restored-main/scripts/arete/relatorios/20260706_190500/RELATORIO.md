# Relatório Arete — LAJ 13_PAV — L318 distribuição/cotagem

Data: 2026-07-06 19:05 BRT

## Escopo

- Classe: LAJ
- Pavimento: 13_PAV
- Item focal: L318
- Pedido do dono: impedir PASS visual falso, remover divisão aleatória/hardcoded de painéis, preferir módulos 244/122/60 e posicionar cota vertical no trecho alto à direita.

## Alterações aplicadas

- `motor_reverso_laj.py`
  - Detecta malha longa ruidosa extraída do recorte.
  - Canonicaliza o eixo longo com regra geral de painéis, sem hardcode por item.
  - Usa `smart_panner` para preferir 244, depois 122, depois 60, com resíduo compensador.

- `gerar_lj_dxf_stog.py`
  - Rejeita linhas extraídas não canônicas no eixo longo antes de desenhar N4.
  - Mantém cotagem `DIMENSION` canônica.
  - Em polígonos em degrau, escolhe a guia vertical no trecho de maior altura, preferindo a direita quando aplicável.

- Testes
  - Cobrem veto de distribuição ruidosa como `58, 186, 76.5, 204.5`.
  - Cobrem saída esperada de L318: `12x244 + 211`.
  - Cobrem cota vertical deslocada para o trecho direito/alto.

## Validação executada

- `python -m pytest tests\test_laj_visual_reference_contract.py tests\test_motor_reverso_laj_dynamic_layers.py tests\test_smart_panner_general_rules.py -q`
  - Resultado: 21 passed.

- `python -m py_compile scripts\gerar_lj_dxf_stog.py scripts\motor_reverso_laj.py`
  - Resultado: OK.

- `python scripts\arete\arete_runner.py --classe LAJ --pav 13_PAV --item L318`
  - Resultado: G1 PASS, G2 PASS.

- `python scripts\arete\arete_runner.py --classe LAJ --pav 13_PAV`
  - Resultado: LAJ 13_PAV = 31 PASS, 0 FAIL, 0 BLOCKED.
  - Relatório-base: `scripts/arete/relatorios/20260706_185947/RELATORIO.md`.

- `python scripts\arete\g2v_harness.py --classe LAJ --pav 13_PAV --par n2xn4 --backend cli --item L318`
  - PNG: `scripts/arete/relatorios/g2v/20260706_190049/LAJ_L318_n2xn4.png`.
  - Veredito registrado: `SUSPEITO`, não `PASS`.

- `python scripts\arete\gerar_status.py`
  - Atualizou `docs/STATUS.md`.

## Decisão de qualidade

O número G1/G2 está limpo e a distribuição de painéis deixou de ser aleatória. Ainda assim, o G2-V foi mantido como `SUSPEITO` porque PASS visual em LAJ exige fechar todos os itens independentes: contorno/área interna, posição/legibilidade das cotas, painéis, HLAZ, hachuras e ausência de contaminação.

## Triagem

Entrada append-only adicionada em:

- `scripts/arete/relatorios/triagem_erros/Obra_TREINO_1_13_PAV_lajes.jsonl`

Finding:

- `laj-L318-g2v-distribuicao-paineis-canonica-20260706`

