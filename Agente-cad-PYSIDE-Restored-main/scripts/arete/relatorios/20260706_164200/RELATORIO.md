# Relatório Arete — LAJ L318 — G2‑V estrito

Data: 2026-07-06 16:42 -03:00

## Veredito

- O PASS visual anterior de `20260706_000331` foi invalidado.
- G1/G2 numérico LAJ 13_PAV: **31/31 PASS** em `20260706_163229`.
- G2‑V atual de L318: **SUSPEITO**, aguardando confirmação do dono sobre posição/legibilidade das cotas.
- G6 de L318: **BLOCKED**, como esperado, porque não existe PASS G2‑V estrito para os bytes atuais.

## Causas corrigidas

- O bbox 3139×201 preenchia um vazio fora da laje. O N2 real é um polígono em degrau:
  `[[2413,0],[2413,49],[0,49],[0,201],[3139,201],[3139,0],[2413,0]]`.
- A HLAZ 726×20 era expandida pela largura inteira; agora permanece em
  `x=2413, y=89.5`.
- O gerador ignorava as 24 posições de `cotas_paineis` e criava uma cadeia própria
  no centro; agora materializa valores e posições extraídos do N2.
- O Comparison Engine usa o polígono N2 como destaque e limita o viewer à área alvo.
- O G2‑V LAJ usa render direto com ROI, alta resolução, hashes N2/N4 e checklist.
- G6 exige PASS visual com checklist completo e hashes atuais.

## Evidências

- G2‑V L318/L319/L326: `scripts/arete/relatorios/g2v/20260706_163327/`
- Regressão completa 31/31: `scripts/arete/relatorios/20260706_163229/`
- Prova de bloqueio G6: `scripts/arete/relatorios/20260706_163829/`
- Triagem append-only: 125 linhas JSON válidas.

## Testes

- `py_compile` dos motores, harness, comparador, runner e Comparison Engine: PASS.
- Testes focados de contorno, HLAZ, cotas e veto G6: **6 PASS**.
- A suíte visual ampla mantém um FAIL preexistente de contrato de tipo
  `LINE`×`LWPOLYLINE` em L302; não foi causado por esta alteração e o gate canônico
  completo ficou 31/31.

## Pendência humana

Reabrir a aplicação para carregar o código Python atualizado, selecionar L318 e
confirmar no Comparison Engine se as posições das cotas correspondem ao N2. Até essa
confirmação, não converter o SUSPEITO em PASS e não selar golden.
