# Proveniência de campos FV — contrato inicial

**Classe:** fundo de viga (FV)
**Estado:** contrato inicial conservador; apto a orientar revisão read-only, não a selar automaticamente.

## Evidência primária

1. entidades do recorte N1/DXF: polilinha do fundo, linhas de limite e cotas;
2. `beams.data_json.links` do mesmo item, com texto, posição, pontos e papel da entidade;
3. ficha N1/HTML como apresentação rastreável;
4. N2/N4 somente para diagnóstico, nunca como fonte para N1/N3.

| Família observada | Campos/padrão | Categoria | Prova mínima | Nunca aceitar como prova |
|---|---|---|---|---|
| Existência | `viga_fundo_seg_*_exists` | (a) extração | polilinha/segmento de fundo identificável | booleano isolado no payload |
| Geometria/área | `*_area_segs` | (a) extração | polígono fechado, coordenadas e área reproduzível | bbox ou área N2 isolada |
| Dimensão | `*_dim` | (b) derivado | duas cotas/coord. ligadas ao mesmo segmento | texto `19/55` sem segmento/ordem |
| Limites locais | `*_local_ini`, `*_local_fim` | (a) extração | ponto inicial/final no contorno do fundo | posição aproximada de outro elemento |
| Metadados | `fv_is_h`, `seg_bottom` | (c) convenção | regra de orientação documentada + geometria correspondente | similaridade com outra viga |

## Regras críticas

- Comprimentos repetidos exigem multiplicador físico rastreável; não contar uma única ocorrência como várias.
- A ordem de `largura/altura` em textos compostos não é uma prova sem a entidade de seção.
- Uma interseção com pilar/viga deve ser registrada como recorte/interferência, não incorporada ao fundo.
- Divergência N1×N2 é achado para diagnóstico; não autoriza copiar N2 para N1.

## Promoção

Para promoção a `validation_ready`: golden FV, G2-V, três geometrias representativas, zero falso positivo crítico e evidência de cada família acima.
