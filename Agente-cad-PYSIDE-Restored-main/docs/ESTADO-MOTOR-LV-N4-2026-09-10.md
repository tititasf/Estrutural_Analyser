# Estado do motor LV N4 — 2026-09-10/11

Fecha a sessão de ajuste do motor LV (faces A/B + visão de corte) sobre a V301 do
13_PAV. Documenta o que virou regra, o que foi corrigido e o que ainda é frágil.

## 1. Regeneração de N4 — `--refresh-from-recorte` é o padrão

`scripts/arete/gerar_lv_n4_fichas.py` agora **liga o refresh por padrão**. Sem ele o
script lê o `fichas_lv_v2.json` / `campos_json` resumido (stale) e gera larguras de
painel erradas.

Incidente que motivou a mudança (2026-09-10): rodar `gerar_lv_n4_fichas.py V301` sem a
flag sobrescreveu N4 já validados pelo dono —

| arquivo | correto | gerado sem a flag |
|---|---|---|
| `LV_preview_V301_A.dxf` | 935 entidades | 314 |
| `LV_preview_V301_VIEW_A.dxf` | 234 | 96 |
| `LV_preview_V301_VIEW_B.dxf` | 503 | 88 |

Toda execução passou a declarar a fonte da ficha:

```
[FICHA] fonte = recorte N2 vivo (--refresh-from-recorte)
```

Opt-out explícito: `--no-refresh-from-recorte`. Com `--entry-json` o padrão continua
sendo respeitar o arquivo fornecido (ficha explícita é autoritativa).

**Procedimento obrigatório antes de publicar em `DADOS-OBRAS/*/Fase-6_Execucao_CAD/n4/`:**
gerar primeiro com `--out <scratch>` e comparar contagem de entidades contra o arquivo
de produção. Queda grande de entidades = ficha stale → abortar.

## 2. Visão de corte — N4 replica a geometria real do N2

Decisão do dono (2026-09-10): **o N4 reproduz o corte medido do N2; o N3 continua
proibido de ler N2.** Quem decide a proveniência é a própria seção (marca
`n1_contract_clean`), não a flag de CLI.

A cadeia do corte em `draw_viga_lateral_face_units` foi harmonizada com a rota legada
(`draw_viga_lateral`), que já fazia 3 níveis:

1. seção marcada como contrato N1 (N3 isolado) → `draw_section_n1_contract_clean`
   (anatomia limpa, nunca lê N2);
2. seção vinda da ficha N2 (N4) → `draw_section_visual_primitives` (replica o recorte);
3. sem primitivas → `draw_section_detail` (template procedural, último recurso).

Antes a rota de `face_units` era `if/else` e **nunca chegava nas primitivas** quando
`--strict-contract` estava ligado — por isso o corte saía como template genérico.

Efeito nas cotas (V301):

| | antes | agora | N2 real |
|---|---|---|---|
| Corte 1 | `55x19`, cotas 55/50 | 13/59/44/7/10/40/19 | idem ✓ |
| Corte 2 | `120x19` genérico | 124/109/105/120/19 | idem ✓ |

## 3. Escala 2× do corte e o empilhamento

As primitivas de corte do N2 vêm em **escala 2×** (existe a layer `Cota Seção (2x)`).
O `concrete_profiles` da ficha reconcilia com os campos escalares quando dividido por 2:

| medida no perfil ÷2 | valor | campo |
|---|---|---|
| largura da alma | 19 | `b` |
| altura total | 55 | `h_section` |
| laje esquerda | 27.8 × 13 | `extension_left_cm` / `laje_sup_A` |
| laje direita | 27.8 × 10 | `extension_right_cm` / `laje_sup_B` |
| desnível entre as lajes | 7 | (só existe na geometria, não há campo) |

O empilhamento antigo (`y_section -= max(h_sec + 90, 180)`) assumia 1× e fazia as seções
**se sobreporem** (no V301 o Corte 2 entrava 76 unidades no Corte 1). Como a extensão
também é assimétrica (o Corte 2 sobe 178.8 acima do centro e desce 61.2), nenhum
multiplicador fixo resolve. Agora `_section_rel_span()` **mede** a extensão real das
primitivas e cada seção é ancorada 90 abaixo do fundo real da anterior.

## 4. Template procedural — flange e hachuras

Mesmo sendo hoje o último recurso, o `draw_section_detail` foi corrigido:

- passa a aceitar `extension_left_cm` / `extension_right_cm` / `laje_sup_A` / `laje_sup_B`
  e desenhar o perfil em T real (antes: notch fixo só do lado direito, 24/b de largura);
  sem esses campos o comportamento antigo é preservado byte a byte;
- removidos dois HATCH que não existem no N2 (`HACHURACONCRETO` e `COTA`/ANSI31 sobre o
  concreto) — os contornos permanecem.

## 5. Página de revisão (`_build_segments_html_v301.py`)

- Cada ponto copiado agora carrega as coordenadas DXF reais
  (`@(x1,y1)->(x2,y2)`), para a referência sobreviver à troca de handles entre gerações.
- Nova classe de card: uma visão de corte por instância real da viga (N2 × N4).
- `find_n4_corte_instances` não depende mais do título sintético `"NOME (LxA)"` (que só o
  template emitia e sumiu): reproduz a cascata de empilhamento do gerador e mede a
  extensão de cada seção, cortando a faixa no meio do caminho até a seção vizinha.
- `FULL_N4_VIEW_A/B` recebeu clip explícito para não arrastar os blocos `PAR_*` soltos
  perto da origem local.

## 6. Frágil / em aberto

- O recorte do Corte 1 na página ainda deixa entrar um pedaço do topo do Corte 2 (as
  cotas em 2× de uma seção alcançam a vizinha).
- `_build_segments_html_v301.py` é específico da V301 — generalizar para o pavimento
  inteiro é o próximo passo.
- `SyntaxWarning: invalid escape sequence '\d'` na linha que injeta o JS (pré-existente,
  não bloqueia; `node --check` passa).
- Regressão usada nesta sessão: geração dos 32 itens LV do 13_PAV
  (`--item <V> --output-dir <scratch> --strict-contract`), 32/32 OK.
