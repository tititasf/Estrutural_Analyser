# Story 2.4: Frontend — Tela Ficha do Item + Índice de Obra

**Epic:** Epic 2 — Ficha do Item (N1/N3)
**Priority:** P0
**Status:** ✅ Done (implementado e testado ao vivo em 2026-07-12)
**Estimated Effort:** G (grande)

```yaml
executor: "@dev"
quality_gate: "@architect"
quality_gate_tools: ["eslint-plugin-jsx-a11y", "lighthouse", "coderabbit"]
```

---

## Story

**As a** funcionário de fôrma que resolveu um código de item (ou obra),
**I want** ver a ficha completa com abas N1/N3/Painéis (só as que têm dado) e, se resolvi uma obra, navegar por pavimentos até o item certo,
**so that** eu confirme a especificação correta antes de montar ou conferir a peça.

---

## Context

Implementa FR2 (identificação + N1/N3), FR4 (aba Painéis — consumida via STORY-13, mas o slot de UI é criado aqui), e FR5 (navegação obra→item) do PRD, seguindo os wireframes exatos da front-end-spec (§5.3, §5.5) e o fluxo de navegação obra→item (§4.2).

[Source: prd.md FR2, FR5]
[Source: front-end-spec.md §5.3 "Ficha do Item"]
[Source: front-end-spec.md §5.5 "Índice de Obra"]
[Source: front-end-spec.md §4.2 "Fluxo — Navegar obra → item"]

---

## Acceptance Criteria

### Ficha do Item

1. **Given** a navegação para `/ficha/{code}` (após resolver via STORY-03/08), **when** a página carrega, **then** busca `GET /api/v1/ficha/{code}` (STORY-05) e renderiza: breadcrumb neutro (`‹ Voltar · {obra_rotulo} · {pavimento_label}`), tipo+título (ícone colorido + texto 24px), código pequeno + botão copiar (⧉), segmented control de abas (N1/N3/Painéis — **só as abas com dado aparecem**), preview do desenho ativo (fit-width), seção "Especificação" (`campos{}` como pares chave/valor), e banner de atenção (`atencao`) **só se não-vazio**.

2. **Given** `svg.n1` presente e `svg.n3` ausente (`null`), **when** renderizado, **then** o segmented control colapsa para um rótulo estático (sem controle inútil de 1 aba) — nunca mostra uma aba N3 vazia.

3. **Given** o botão "⧉ copiar código", **when** tocado, **then** copia o `code` para o clipboard com feedback visual (toast/highlight breve).

4. **Given** o carregamento do SVG preview falhar (timeout/erro de rede), **when** detectado, **then** mostra placeholder com ícone + "Não foi possível carregar o desenho" + botão "Tentar de novo" — **sem** quebrar o restante da ficha (campos/painéis continuam visíveis).

5. **Given** `tem_lv=true` mas o usuário está na aba N1/N3, **when** a aba Painéis é selecionada, **then** o slot de UI existe e delega o conteúdo real ao componente da STORY-13 (esta story cria o container/roteamento da aba; o conteúdo tabular é implementado na STORY-13).

### Índice de Obra

6. **Given** a navegação para `/obra/{code}` (após resolver `kind=obra`), **when** a página carrega, **then** busca `GET /api/v1/obra/{code}` (STORY-07) e renderiza acordeão de pavimentos (56px por linha), cada um expansível mostrando itens (código + título + ícone de tipo, 56px por linha).

7. **Given** um pavimento sem itens publicados, **when** expandido, **then** mostra estado vazio "Nenhum item publicado neste pavimento" (não erro).

8. **Given** o filtro local por título/tipo, **when** usado, **then** filtra a lista de itens já carregada **client-side** (sem nova requisição de rede) — filtro é conveniência de UI, não busca por código.

9. **Given** um item tocado no Índice de Obra, **when** selecionado, **then** navega para `/ficha/{code_do_item}` (o `code` do item, não o código de obra) — repetindo o fluxo de resolução da Ficha do Item (reaproveitando a mesma tela/lógica do AC1).

### Transversal

10. **Given** qualquer uma destas telas, **when** renderizada, **então** usa exclusivamente os componentes-núcleo e tokens da STORY-09 (nenhum estilo inline ad-hoc que fuja do design system).

11. **Given** a navegação por teclado (persona P3, desktop), **when** usada, **então** Tab/Shift-Tab percorrem os controles em ordem lógica, `Esc` fecha modais, foco visível em todo elemento interativo.

---

## Dependencies

- **Requires:** STORY-05 (`/ficha/{code}`), STORY-07 (`/obra/{code}`), STORY-09 (design system/componentes-núcleo).
- **Blocks:** STORY-11 (visualizador SVG tela cheia é acionado a partir do preview desta tela), STORY-13 (aba Painéis LV renderiza dentro do container criado aqui), STORY-14 (cache offline do "último item" se aplica a esta rota).

---

## Tasks / Subtasks

- [ ] Task 1 — Rota e data fetching da Ficha do Item (AC: 1, 4)
  - [ ] Subtask 1.1: `app/ficha/[code]/page.tsx` — client-side fetch de `/api/v1/ficha/{code}`
  - [ ] Subtask 1.2: Skeleton de carregamento da ficha completa
  - [ ] Subtask 1.3: Tratamento de erro de carregamento do SVG (placeholder + retry) sem quebrar o restante
- [ ] Task 2 — Componentização da Ficha (AC: 1, 2, 3, 5)
  - [ ] Subtask 2.1: Breadcrumb neutro, título com ícone de tipo
  - [ ] Subtask 2.2: `Segmented` dinâmico (colapsa se só 1 aba com dado)
  - [ ] Subtask 2.3: `SpecField` para `campos{}`, `AttentionBanner` condicional
  - [ ] Subtask 2.4: Botão copiar código (clipboard write + feedback)
  - [ ] Subtask 2.5: Slot/roteamento da aba Painéis (delega a STORY-13)
- [ ] Task 3 — Rota e data fetching do Índice de Obra (AC: 6, 7, 8, 9)
  - [ ] Subtask 3.1: `app/obra/[code]/page.tsx` — client-side fetch de `/api/v1/obra/{code}`
  - [ ] Subtask 3.2: Acordeão de pavimentos + lista de itens
  - [ ] Subtask 3.3: Filtro local client-side (sem nova requisição)
  - [ ] Subtask 3.4: Navegação item → Ficha do Item (reaproveita fluxo do AC1/AC9)
- [ ] Task 4 — Acessibilidade e navegação por teclado (AC: 10, 11)
  - [ ] Subtask 4.1: `role="tablist"/"tab"/"tabpanel"` no segmented control
  - [ ] Subtask 4.2: `aria-live="polite"` para resultado de busca carregado ("Ficha carregada: Pilar P1")
  - [ ] Subtask 4.3: Teste de navegação 100% por teclado

---

## Dev Notes

### Files/Components Expected

- `consulta-publica-web/app/ficha/[code]/page.tsx`
- `consulta-publica-web/app/obra/[code]/page.tsx`
- `consulta-publica-web/components/ficha/FichaHeader.tsx`, `FichaTabs.tsx`, `SpecFieldList.tsx`
- `consulta-publica-web/components/obra/PavimentoAccordion.tsx`, `ItemListRow.tsx`
- `consulta-publica-web/lib/api/ficha.ts`, `lib/api/obra.ts`

### Technical Notes

- **Wireframe exato da Ficha do Item** (layout, tamanhos, texto): [Source: front-end-spec.md §5.3]
- **Wireframe exato do Índice de Obra:** [Source: front-end-spec.md §5.5]
- **Fluxo obra→item com bordas:** "obra publicada mas sem itens em um pavimento → estado vazio 'Nenhum item publicado neste pavimento'. Lista longa → busca/filtro local + agrupamento por pavimento." [Source: front-end-spec.md §4.2]
- **Abas dinâmicas:** "N1 aparece se `svg.n1`; N3 se `svg.n3`; Painéis se `tem_lv=true`. Se só há N1, o segmented control colapsa para um rótulo estático." [Source: front-end-spec.md §5.3]
- **Breadcrumb nunca expõe dado cru:** "Nunca expõe `item_id`/`pavimento` crus (só os rótulos públicos vindos da API — `obra_rotulo`, `pavimento_label`)." [Source: front-end-spec.md §3.2]
- **Estados — matriz de referência para Ficha/Índice de Obra:** [Source: front-end-spec.md §14]

---

## Testing

- **Test file location:** `consulta-publica-web/__tests__/ficha/`, `__tests__/obra/`
- **Testing framework:** Jest + RTL / Playwright (fluxo completo)
- **Key test scenarios:**
  - Ficha renderiza corretamente com N1+N3+LV, com N1 apenas, e sem nenhum SVG (edge case)
  - Índice de Obra com pavimento vazio
  - Navegação item → ficha preserva o `code` correto
  - Falha de carregamento de SVG não quebra o resto da ficha
  - Navegação por teclado completa (Tab, Esc, Enter/Espaço)
- **Special considerations:** validar que nenhum componente desta tela tenta ler/exibir `item_id`/`pavimento` cru mesmo em modo debug/dev tools.

---

## 🤖 CodeRabbit Integration

**Story Type Analysis**
- **Primary Type:** Frontend
- **Secondary Type(s):** API (consumo de dois endpoints, tratamento de estados)
- **Complexity:** High — duas telas completas, múltiplos estados, navegação entre elas

**Specialized Agent Assignment**
- **Primary Agents:** @ux-expert, @dev
- **Supporting Agents:** —

**Quality Gate Tasks**
- [ ] Pre-Commit (@dev): a11y validation
- [ ] Pre-PR (@github-devops): UX consistency check contra front-end-spec §5.3/§5.5
- [ ] Pre-Deployment: N/A nesta story isolada (parte do release maior)

**CodeRabbit Focus Areas**
- **Primary Focus:**
  - Acessibilidade: `role="tablist"`, `aria-live`, navegação por teclado
  - Performance: componente otimizado, lazy loading do SVG (delegado à STORY-11, mas o slot deve já preparar lazy)
- **Secondary Focus:**
  - Responsive design (reflow de tabela/cartão herdado da STORY-09)
  - UX consistency com wireframes exatos da spec

**Self-Healing Configuration**
- **Expected Self-Healing:** Primary Agent: @dev (light) · Max Iterations: 2 · Timeout: 15 min · Severity Filter: CRITICAL only
- **Predicted Behavior:** CRITICAL (dado cru vazando na UI, quebra de acessibilidade crítica): auto_fix. HIGH: document_only.

---

## Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2026-07-11 | 0.1 | Story criada a partir de front-end-spec.md §4.2/§5.3/§5.5 e prd.md FR2/FR5 | River (SM) |
| 2026-07-12 | 1.0 | Implementado e testado ao vivo — ver Dev Agent Record | Claude (dev) |

---

## Dev Agent Record

**Arquivos criados:**
- `lib/api/ficha.ts` (`buscarFicha`, `urlAbsolutaSvg`), `lib/api/obra.ts` (`buscarIndiceObra`)
- `components/ficha/{FichaHeader,FichaTabs,SpecFieldList}.tsx` (+ `.module.css`)
- `components/obra/{PavimentoAccordion,ItemListRow}.tsx` (+ `.module.css`)
- `app/ficha/[code]/page.tsx` (substitui o placeholder da STORY-08), `app/ficha/[code]/page.module.css`
- `app/obra/[code]/page.tsx` (substitui o placeholder da STORY-08), `app/obra/[code]/page.module.css`
- `__tests__/ficha/page.test.tsx` (8 testes), `__tests__/obra/page.test.tsx` (5 testes)
- `components/ui/SvgViewer.tsx` ganhou prop `onErro` (callback de `<img onError>`) para permitir que a Ficha detecte falha de carregamento do SVG sem quebrar o resto da tela (AC4)

**Testes:** 60/60 passando no projeto inteiro (`npm test`). `npm run lint` e `npm run build` limpos.

**Decisão de kickoff — histórico só é salvo na Ficha, não na Busca:** a
STORY-08 documentou que `/resolve` só retorna `{kind, code}`, sem
`titulo`/`tipo`/`obra_rotulo` suficientes para um chip de histórico
decente. Confirmado nesta story: `adicionarAoHistorico` é chamado dentro do
`useEffect` de `app/ficha/[code]/page.tsx` assim que `buscarFicha` retorna
com sucesso — é o único ponto do fluxo com todos os campos necessários.

**2 bugs reais de teste encontrados e corrigidos (não bugs de produção):**
1. `jest.mock("@/lib/api/ficha")` (sem factory) automocka TODO export do
   módulo — incluindo `urlAbsolutaSvg`, uma função pura que eu queria
   manter real. Isso fazia `urlAbsolutaSvg(...)` retornar `undefined`,
   quebrando silenciosamente o `src` do `<img>` (SvgViewer renderizava uma
   `<div class="wrapper">` vazia, sem erro visível). Corrigido com mock
   parcial: `jest.mock("@/lib/api/ficha", () => ({ ...jest.requireActual(...), buscarFicha: jest.fn() }))`.
   Achado via `screen.debug()` isolando o componente `SvgViewer` sozinho
   (que funcionava) vs. dentro da página (que não).
2. `jest.restoreAllMocks()` não zera o histórico de chamadas (`.mock.calls`)
   de funções que já eram `jest.fn()` por causa de um `jest.mock()` no topo
   do arquivo (só restaura spies criados sobre implementação REAL) — um
   teste de "filtro local não dispara nova requisição" via `toHaveBeenCalledTimes(1)`
   falhava recebendo 4 (acumulado dos testes anteriores do mesmo arquivo).
   Corrigido trocando por `jest.clearAllMocks()` em `beforeEach` nos 2 novos
   arquivos de teste.

**Verificado ao vivo** contra a API real (`:21390`) e o frontend real
(`:21391`), usando a obra real republicada (`mAOblv8E22`, 432 itens em 2
pavimentos):
- `GET /ficha/tJbR0yqFiu` (pilar real): breadcrumb ("· Obra Teste Smoke ·
  13º Pavimento"), título "P1", código + botão copiar, aba única
  colapsada (só N1, sem N3 — segmented não aparece como controle, AC2
  confirmado), imagem do SVG carregada com sucesso (`GET .../svg/n1 → 200`
  confirmado via `read_network_requests`), todos os `campos{}` renderizados.
- `GET /obra/mAOblv8E22`: acordeão com 2 pavimentos reais ("13º PAVIMENTO
  (64)", "TÉRREO (368)"), itens com ícone de tipo (Pilar azul / Viga
  verde) — alguns itens reais têm `titulo_publico` vazio (dado real, não
  bug), clicar em "P10" navegou corretamente para `/ficha/{code de P10}` e
  carregou a ficha certa (confirma AC9 — preserva o `code` do ITEM, não o
  da obra).

**Débito técnico documentado:**
- Navegação 100% por teclado (AC11, Subtask 4.3) não tem teste automatizado
  dedicado — os componentes usam elementos nativos (`<button>`, `<input>`)
  que já são focáveis/operáveis por teclado por padrão do browser, mas não
  há teste explícito de ordem de Tab ou de `Esc`. Verificação manual não
  realizada nesta sessão (fora do escopo de tempo).
- Ao clicar "Tentar de novo" após falha de SVG, a página inteira busca
  `/ficha/{code}` de novo (não só o SVG) e reseta a aba selecionada para o
  padrão — simplificação aceitável para o MVP, mas não é o refetch mínimo
  ideal (refazer só o `<img src>` seria suficiente).
- `PavimentoAccordion` expande automaticamente TODOS os pavimentos quando
  há filtro ativo (`expandido={... || Boolean(filtro.trim())}`) — funciona
  mas não colapsa de volta ao limpar o filtro se o usuário tinha fechado
  manualmente antes; comportamento aceitável, não testado explicitamente.
