# Histórico — ANÁLISE LV (março/2026)

Documentos de conhecimento da engenharia reversa de **Laterais de Viga STOG**,
produzidos em março de 2026 e resgatados em 12/09/2026.

## Por que estão aqui

Viviam em `ANALISE_LV/` na branch `etapa1-fichas-botoes` e **não existiam nem em
`main` nem em `entrega/vps-20260810`** — nenhuma das duas branches que recebem
trabalho hoje.

Pior: `etapa1-fichas-botoes` **não pode ser publicada no GitHub**. O histórico
dela carrega quatro `decisoes.jsonl` de evidência QA acima do limite de 100 MB
(dois deles com 137,96 MB), e o `pre-receive` do GitHub recusa o push. Ou seja,
esse conhecimento existia num único disco, sem cópia remota possível.

Copiados **byte a byte** (md5 conferido), sem edição de conteúdo.

## O que cada um tem

| arquivo | o que é |
|---|---|
| `CONHECIMENTO_LV_STOG.md` | Anatomia da LV STOG extraída de **142 amostras, 5 obras, 13 DXFs** (10/03/2026): layout de título/Face A/Face B/seção transversal, tabela de frequência das layers nas 142 amostras, e a regra empírica `h_B = h_A − 10`. |
| `STOG-LV-PATCH-DESIGN.md` | Documento de projeto da reconstrução do DXF de LV (16/03/2026), com baseline de score 55/100 e alvo 85+/100. |
| `ANALYSIS_REPORT.md` | Investigação de fragmentos soltos na grade do DXF combinado: v35 (277 células, 9971 elementos isolados) → v37 (42 células, 456 elementos). |

## Como ler isto hoje

É **registro histórico**, não contrato vigente. O contrato atual do motor LV é
`docs/CONTRATO-RIGIDO-MOTOR-LV-N3-N4.md`, e a interpretação das fichas está em
`docs/LV-COMPREENDER-INTERPRETACAO-FICHAS-N2-N4.md`.

O valor destes três está na **evidência de corpus**: as frequências de layer e a
anatomia vêm de 142 amostras reais de 5 obras, uma base bem mais ampla que o
13_PAV onde o motor é calibrado hoje. Onde o motor atual contradisser algo aqui,
a pergunta certa é se o 13_PAV é exceção ou se o motor generalizou de menos —
não assumir que o documento antigo está errado.
