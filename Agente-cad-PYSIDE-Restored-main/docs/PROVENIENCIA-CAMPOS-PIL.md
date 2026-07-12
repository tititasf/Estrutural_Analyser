# Proveniência de campos PIL — contrato inicial

**Classe:** pilares (PIL)
**Estado:** contrato inicial conservador; apto a orientar revisão read-only, não a selar automaticamente.

## Evidência primária

1. polígono do pilar no DXF/N1 e suas faces ordenadas;
2. rótulo/cota com posição e camada, associado à mesma geometria;
3. contato geométrico com laje/viga, com face identificável;
4. ficheiro/HTML N1 apenas como apresentação; N2/N4 apenas comparação independente.

| Família observada | Campos/padrão | Categoria | Prova mínima | Tratamento especial |
|---|---|---|---|---|
| Geometria | `pilar_segs` | (a) extração | polígono fechado e não degenerado | não reduzir L/U/circular a bbox retangular |
| Identidade | `name` | (a) extração | texto canônico `P...` associado ao polígono | texto distante não é rótulo do pilar |
| Dimensão | `dim` | (a)/(b) | cota ou duas paredes identificadas | `VF...` não é dimensão de seção |
| Relação de face com laje | `p_s[A-H]_l*_n` | (a) relação | face do pilar + laje nomeada + contato/adjacência | nome de laje sem face/contato |
| Relação de face com viga | `p_s[A-H]_v_*_[nd]` | (a) relação | face + viga + dimensão/posição correspondente | copiar relação da face vizinha |
| Conexões resumidas | `connections` | (b) derivado | relações de face já comprovadas | lista livre que contradiz as faces |

## Regras críticas

- Pilar não retangular requer prova por faces/partes; comparação simples de largura × comprimento é inválida.
- Face, nome da viga/laje e geometria devem concordar. Qualquer um sem os outros permanece pendente.
- Relações entre pavimentos são contexto consultivo, jamais cópia de atributos do pavimento vizinho.

## Promoção

Para promoção: golden com retangular/L/U ou especial, revisão visual, prova de face e regressão cross-classe PIL↔LAJ/FV/LV.
