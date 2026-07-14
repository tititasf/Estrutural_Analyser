# V327 — endpoint LV e G5-V

## Resultado materializado

- Headless canônico persistido: `20260714_042512_245519_laterais_viga_12712`.
- `V327.A/B`: apoio inicial global `V328` removido; apoio final local `P27` preservado.
- Probe `four_contracts_and_support`: **PASS** com os quatro contratos, fontes
  PARA/PASSA disjuntas, `behavior_isolated=true`, sem fallback FV de dimensão e
  contato geométrico do apoio extremo.

## Visual G5-V — PASSA

Veredito CLI: **FAIL** (não selado).

- A correção de endpoint é visível: N3 não imprime mais `V328` no início e
  mantém `P27` no fim.
- Ainda falha a visão de corte N3, que é simplificada/antiga frente ao N4.
- Ainda faltam os sarrafos verticais internos de 7 cm nas extremidades das
  laterais A e B no N3.

Próxima causa: conversão N1→N3 de corte e de sarrafos de extremidade, sem usar
N2/N4 como input.
