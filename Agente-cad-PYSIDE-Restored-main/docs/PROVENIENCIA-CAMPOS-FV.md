# Proveniência de campos FV — contrato inicial

**Classe:** fundo de viga (FV)
**Estado (2026-07-16):** `validation_ready` via `FvEvidenceAuditor`
(`scripts/arete/qa_fv_lv_adapters.py`) para segmentos com geometria re-derivada
(exists/area_segs/dim/local_ini-fim). Um segmento confirmado **não** aprova a
viga inteira; golden multi-geometria + G2-V seguem recomendados antes de selagem
em massa.

## Evidência primária

1. entidades do recorte N1/DXF: polilinha do fundo, linhas de limite e cotas;
2. `beams.data_json.links` do mesmo item, com texto, posição, pontos e papel da entidade;
3. ficha N1/HTML como apresentação rastreável;
4. N2/N4 somente para diagnóstico, nunca como fonte para N1/N3.

| Família observada | Campos/padrão | Categoria | Prova mínima | Nunca aceitar como prova |
|---|---|---|---|---|
| Existência | `viga_fundo_seg_*_exists` | (a) extração | polilinha/segmento de fundo identificável | booleano isolado no payload |
| Geometria/área | `*_area_segs` | (a) extração | polígono fechado **e** borda sobre face DXF classificada (posição no estrutural); checklist N1-V `contorno_posicao_sobre_estrutural` | bbox/área isolada, contorno flutuante com C×L certo, área N2 isolada |
| Dimensão | `*_dim` | (b) derivado | duas cotas/coord. ligadas ao mesmo segmento | texto `19/55` sem segmento/ordem |
| Limites locais | `*_local_ini`, `*_local_fim` | (a) extração | ponto inicial/final no contorno do fundo | posição aproximada de outro elemento |
| Metadados | `fv_is_h`, `seg_bottom` | (c) convenção | regra de orientação documentada + geometria correspondente | similaridade com outra viga |

> **Fronteira de payload:** o escalar raiz `fv_is_h` e o escalar raiz
> `seg_bottom` são estado transitório do interpretador, não campos de ficha
> nem slots de validação. A evidência auditável de segmentos continua em
> `links.viga_segs.seg_bottom` e em `viga_fundo_seg_N_area_segs`. A contagem
> bruta pode divergir da quantidade física consolidada (por exemplo após
> agrupar painéis); o QA nunca abre achado apenas por essa divergência.

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

## Sessão QA read-only — 2026-07-16

**Escopo:** V309, V320, V325, V327 e V332 (`Obra_TREINO_1/13_PAV/FV`).

- O auditor passou a resolver `viga_fundo_seg_N_exists` pela área local do
  **mesmo** índice somente quando o slot `area_segs.contour` é polígono
  fechado de área positiva. A decisão resultante é exclusivamente
  `TRILHA_N1_OBSERVADA`; não confirma a geometria, não escreve no DB e não
  promove selo.
- Foram removidos do inventário auditável os escalares internos raiz
  `fv_is_h` e `seg_bottom`. A demonstração mostrou `V320=6/2`, `V325=4/1` e
  `V327=3/1` entre a contagem bruta e os painéis consolidados: tratá-los como
  campo de ficha produziria pergunta humana falsa e incentivaria uma correção
  destrutiva do estado N1.
- Reexecução read-only: `20260716_132435_review_17372bf4`, 30 decisões,
  0 pergunta; nenhuma modificação de N1/N2/N3/N4, DXF, JSON Fase-4 ou selo.

## Sessão QA de evidências — 2026-07-14

**Escopo:** `Obra_TREINO_1` / `13_PAV` / `FV` / projeto
`dd238e47-1dc6-4f63-a760-4e7ce19a7386`.  Consulta de PIL é permitida apenas
para provar o apoio físico; LV não é fonte nem fallback semântico de FV.

### Contrato observado e materializado

| Campo/vínculo FV | Fonte permitida | Persistência exigida | Limite de uso |
|---|---|---|---|
| `viga_fundo_seg_N_area_segs.contour` | `seg_bottom` e faces DXF da própria FV | `points`, `evidence_segments[N]`, `source_slot=seg_bottom`, ficha de medida | prova local; não é o eixo inteiro da viga |
| `viga_fundo_seg_N_local_ini/fim` | texto/entidade em contato com a extremidade daquele segmento; PIL pode confirmar | `scope=segment_local`, `evidence_role=fv_segment_local_support`, pontos quando a entidade os possui | não pode ser inferido apenas pelo zoom distante |
| `links.apoios.inicio/fim` | extremos da continuidade global já encontrada no N1 | `scope=beam_global`, `evidence_role=fv_beam_global_boundary` | não substitui o apoio de cada painel FV |
| furo/recorte | entidade DXF que toca/interrompe o contorno local | vínculo em `cortes`/`aberturas` e pontos da entidade | ausência no DB é `N/A`, nunca geometria inventada |

### Duas evidências N1, sem terceiro zoom

- **Local:** recorte SVG do DXF que destaca somente o segmento escolhido, suas
  extremidades, dimensão, apoios locais e as exceções em contato.
- **Contextual:** outro recorte SVG da mesma origem DXF, usando exclusivamente
  os contornos FV já persistidos da mesma viga. Ele explica nome, eixo,
  continuidade, pilares/apoios globais e transições, mas não cria segmento nem
  apoio.
- Ambos mantêm textos DXF como elementos `<text>` SVG. A ficha expõe o
  `source_key`, `source_slot`, `evidence_segments`, apoios locais e limites
  globais para tornar a diferença auditável.

### Cache e preservação

O atalho headless não instancia `MainWindow`: reutiliza o contexto canônico que
foi calculado por `BeamTracer` e `FundoVigaInterpreter`. Seu cache é
content-addressed pelo conteúdo do DXF, `BeamTracer`, interpretador FV,
contrato FV e dependências N1 comuns. Ele é apenas desempenho: não sela campo,
não altera N1/N3 e não dispensa a execução canônica com `--wait` quando houver
mudança real de interpretação.

Na persistência parcial, a topologia/contorno humano validado continua soberano;
o enriquecimento automático só atualiza a sua própria proveniência em links não
validados. Um `evidence_segments.source_segment=0` é inválido e é migrado para o
índice FV real durante reparo automático, nunca em geometria validada.

### Amostra e estado de exceções

- Casos escolhidos para prova: V305 (simples), V301 e V306 (multi-segmento e
  apoios distintos), V307 (diagonal/especial). A seleção é N1/DB/DXF; N2/N4
  seguem exclusivamente comparação posterior.
- A inventariação read-only atual não encontrou item FV deste pavimento com
  `holes` ou `cuts` persistidos. Portanto o requisito de furo/recorte fica
  explicitamente **N/A pendente de caso real**, sem fabricar um terceiro zoom ou
  exceção sintética.
- Nenhuma promoção para golden, G2-V, selo ou validação humana ocorreu nesta
  sessão; ainda dependem de geração canônica, diagnóstico e veredito visual CLI.
