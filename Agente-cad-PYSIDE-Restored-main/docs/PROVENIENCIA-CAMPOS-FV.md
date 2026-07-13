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

## Sessão QA read-only — 2026-07-12

**Projeto:** `dd238e47-1dc6-4f63-a760-4e7ce19a7386` (`Obra_TREINO_1`, `13_PAV`)  
**Inventário:** `fv_qa_evidence_20260712_2015`  
**Revisão por campo:** `fv_qa_review_20260712_2016`  
**Diagnóstico N1×N2:** `scripts/arete/relatorios/qa_evidencias/fv_qa_diagnostico_20260712_2017/Obra_TREINO_1/13_PAV/20260712_185155/diagnostico_fv_n1_n2.json`

### Evidência observada

- O escopo contém 36 entidades FV N1 e 26 fichas N2 comparáveis. N2 foi usado apenas para detectar divergência; não é fonte de nenhum campo N1/N3.
- Em 24 comparáveis, 17 coincidem na quantidade física de segmentos; somente 12 coincidem nas medidas na tolerância de `0,05 cm`.
- Os campos `*_area_segs`, `*_dim`, `*_local_ini` e `*_local_fim` possuem vínculo N1 em parte dos itens, mas `viga_fundo_seg_*_exists`, `fv_is_h` e `seg_bottom` ainda não preservam a entidade CAD de origem de modo independente.
- Um contorno FV automático só é aceitável quando o polígono fechado contém a extensão axial do segmento e suas duas faces físicas DXF; comprimento/bbox isolados não provam posição.
- Uma geometria de área marcada `validated` por humano permanece autoritativa. Geometria automática deslocada, sem selo humano, deve ser reavaliada contra as faces DXF antes de ser reaproveitada.

### Geometrias representativas para regressão

1. painel retilíneo simples: V305;
2. repetição física e chanfro: V306;
3. pilar `NASCE` que não é obstáculo sólido: V312;
4. fundo diagonal/em L: V307;
5. associação espacial entre vigas próximas: V327/V328.

**Sem promoção:** esta sessão é diagnóstica. Nenhum campo foi promovido para selo, golden, G2-V ou validação humana.
