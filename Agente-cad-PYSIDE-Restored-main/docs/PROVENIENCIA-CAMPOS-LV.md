# Proveniência de campos LV — contrato inicial

**Classe:** laterais de viga (LV)
**Estado:** contrato inicial conservador; apto a orientar revisão read-only, não a selar automaticamente.

## Evidência primária

1. linha/polilinha do segmento lateral N1/DXF e o lado A/B explícito;
2. cotas e limites de início/fim ligados ao mesmo segmento;
3. entidades de apoio, laje, abertura ou pilar em contato com a lateral;
4. contrato N1 `lv_generation_contracts`, quando presente, como derivado rastreável; N2/N4 apenas comparação.

| Família observada | Campos/padrão | Categoria | Prova mínima |
|---|---|---|---|
| Existência/dimensão | `viga_[ab]_seg_*_exists`, `*_dim` | (a)/(b) | segmento no lado correto + cota/seção associada |
| Limites | `*_ini_name`, `*_end_name` | (a) relação | endpoint do segmento toca/termina no elemento nomeado |
| Comprimento | `*_comprimento_total`, `*_comp_total_*` | (b) derivado | endpoints e soma/relação reproduzível |
| Nível e lajes | `*_nivel_viga`, `*_lajes` | (a)/(b) | fonte semântica de nível + contato no lado correspondente |
| Aberturas/recortes | `*_abert_*` | (a) extração | recorte delimitado por contorno e medidas locais |
| Metadados | `lv_*`, `seg_a`, `seg_b`, `seg_c` | (c) convenção | contrato de geração/semântica documentado |

## Regras críticas

- A e B não são intercambiáveis; todo campo deve preservar lado, segmento e orientação.
- Texto composto de seção pode inverter ordem; usar conjunto/entidade de seção, não posição textual isolada.
- Abertura deve ter geometria própria; não pode nascer da invasão de pilar/viga vizinha.
- Medidas de recorte são locais: não substituí-las pela dimensão total da viga.

## Promoção

Para promoção: golden com `para` e `passa`, lados A/B, abertura, recorte e mudança de seção, mais G2-V e validação humana.
