# Padrão de validação humana — PIL N4

**Status:** aprovado pelo dono em 22/07/2026, exceto pilares especiais (P26 e
P27), que seguem em sessão própria.

## Artefato de referência

O exemplo preservado do padrão é o painel HTML abaixo. Ele deve ser usado como
referência de estrutura e interação para revisões futuras de N2 × N4 de pilares:

- `scripts/arete/relatorios/revisao_pil_vistas_20260721_130629/index.html`
- snapshot da rodada aprovada:
  `scripts/arete/relatorios/revisao_pil_vistas_20260722_121302/index.html`

O primeiro caminho é a cópia servida para a revisão humana e conserva o estado
de `revisoes_humanas.json`; o segundo é o artefato imutável da última geração.

## Contrato do painel

- Um card por pilar, comparando ficha N2, vista superior N4 e vista ABCD N4.
- SVG local, zoom pelo scroll, pan por arraste e viewers independentes para
  CIMA e ABCD.
- Checkbox de validação e campo de atenção persistidos sem perder o estado ao
  atualizar a página.
- N4 sem hatch de painéis sólidos: hatch somente em vazios, aberturas e lajes,
  unificados quando formam uma região contínua.
- Painel acima da laje: retângulo no layer `Painéis`; em painel de até 7 cm,
  sarrafo adicional na sua linha inferior.
- Cotas de laje e painel superior (por exemplo 12 + 7) permanecem separadas e
  alinhadas na mesma hierarquia da cadeia de cotas da face.

## Limites de autoridade

Este HTML é evidência de revisão humana e apresentação. A ficha N2 alimenta o
motor N4; erros de leitura pertencem ao motor N2, enquanto erros de geometria,
layers, hatch, cotagem ou comportamento pertencem ao motor de desenho N4. O
painel não autoriza alterar N1 nem usar N2/N4 como entrada de N3.
