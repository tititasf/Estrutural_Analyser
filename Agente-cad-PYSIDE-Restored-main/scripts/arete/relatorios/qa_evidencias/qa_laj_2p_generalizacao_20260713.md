# LAJ — tentativa de generalização em 2_PAV

Data: 2026-07-13  
Projeto: `94cf7136-7640-44b1-9757-0b81971c6ccd` (`TMC-EST-EX-4000-2PV-R00_R2018_ASCII_ODA`)  
Amostra: `L51` (simples), `L58` (degraus), `L75` (contorno complexo).

## Execução canônica

- Headless único, offscreen, com persistência: `qa_laj_2p_generalizacao_headless_v3_20260713`.
- Artefatos e diagnóstico saíram sob `2_PAV`; o ajuste de proveniência impediu o default legado `13_PAV` de contaminar a rota.
- O gate FV deixou de bloquear microciclos LAJ quando FV não é seção solicitada. Nenhuma viga foi alterada.

## Veredito: SUSPEITO — não promover ao T2

As três imagens N1 mostram contornos compatíveis com a área interna desenhada no recorte. Porém, as fichas N2 ainda estão `draft` e declaram áreas/bboxes que abrangem elementos vizinhos:

| Item | Área N1 | Área N2 declarada | IoU | Decisão |
| --- | ---: | ---: | ---: | --- |
| L51 | 28.781 | 138.086 | 0,208 | fonte N2 inconsistente |
| L58 | 26.788 | 135.592 | 0,198 | fonte N2 inconsistente |
| L75 | 13.570 | 70.769 | 0,192 | fonte N2 inconsistente |

O harness visual foi preenchido como `SUSPEITO`, nunca `PASS`: `scripts/arete/relatorios/g2v/20260713_020647/relatorio.json`.

## Próximo passo correto

Antes de usar `2_PAV` como prova de generalização, é necessário obter ou validar um N2 de LAJ com geometria de área interna e proveniência humana confirmada. O motor N1 não será ajustado contra essas fichas porque isso transformaria contaminação N2 em falso alvo.
