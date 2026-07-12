# Story 3.2: Frontend — Aba Painéis LV

**Epic:** Epic 3 — Lista de Painéis LV
**Priority:** P2 (Should — primeira a deslizar sob pressão de prazo, conforme PRD §5.1)
**Status:** ✅ Done (implementado e testado ao vivo em 2026-07-12)
**Estimated Effort:** P (pequeno)

```yaml
executor: "@dev"
quality_gate: "@architect"
quality_gate_tools: ["eslint-plugin-jsx-a11y", "coderabbit"]
```

---

## Story

**As a** funcionário de fôrma montando uma Viga Lateral,
**I want** ver a lista de painéis (largura, tipo, módulo STOG) num formato legível em mobile — tabela em telas largas, cartão empilhado em telas estreitas,
**so that** eu identifique rapidamente a largura de cada painel sem scroll horizontal confuso.

---

## Context

Implementa a aba "Painéis" dentro da Ficha do Item (slot criado na STORY-10), consumindo o endpoint `/paineis-lv` (STORY-12), seguindo o wireframe exato da front-end-spec (§5.4).

[Source: prd.md FR4]
[Source: front-end-spec.md §5.4 "Aba Painéis LV (dentro da Ficha)"]

---

## Acceptance Criteria

1. **Given** um item com `tem_lv=true`, **when** a aba "Painéis" é selecionada na Ficha do Item, **then** busca `GET /api/v1/ficha/{code}/paineis-lv` (STORY-12) e renderiza: largura total + altura (`total_width`/`h_section`) no topo, seguido de tabelas/cartões agrupados por lado (A/B), com colunas `#`, `Largura`, `Tipo`, `Módulo STOG`.

2. **Given** a largura da tela ≥ 380px, **when** renderizado, **then** usa `PanelTable` (tabela com cabeçalho sticky, linhas de 56px).

3. **Given** a largura da tela < 380px, **when** renderizado, **then** reflui automaticamente para `PanelCard` (cartão empilhado, largura em destaque grande, tipo e módulo abaixo) — **sem scroll horizontal**.

4. **Given** valores numéricos de largura/dimensão, **when** exibidos, **then** usam `font-variant-numeric: tabular-nums` (herdado dos tokens da STORY-09) para alinhamento visual consistente.

5. **Given** um item que deveria ter LV mas o backend retorna `404` em `/paineis-lv` (`tem_lv` desatualizado ou contrato ausente), **when** detectado, **then** mostra nota neutra dentro da ficha: "Lista de painéis não disponível para este item." — **não** quebra as demais abas (N1/N3 continuam acessíveis).

6. **Given** a aba Painéis, **when** ausente (`tem_lv=false` desde a resposta de `/ficha/{code}`), **then** a aba **não aparece** no segmented control (comportamento já coberto pela lógica dinâmica da STORY-10, aqui apenas garantido que o componente de painéis não é montado nesse caso).

---

## Dependencies

- **Requires:** STORY-12 (`/paineis-lv` endpoint), STORY-10 (container da Ficha do Item e segmented control dinâmico).
- **Blocks:** STORY-14 (cache offline do último item consultado deve incluir os dados de painéis, se aplicável).

---

## Tasks / Subtasks

- [ ] Task 1 — Data fetching da aba Painéis (AC: 1, 5)
  - [ ] Subtask 1.1: Fetch sob demanda de `/paineis-lv` (só quando a aba abre, mesmo padrão lazy do SVG)
  - [ ] Subtask 1.2: Tratamento de 404 → nota neutra, sem quebrar demais abas
- [ ] Task 2 — Componentes de exibição (AC: 2, 3, 4)
  - [ ] Subtask 2.1: `PanelTable` (herdado da STORY-09, populado com dados reais)
  - [ ] Subtask 2.2: `PanelCard` (reflow automático <380px)
  - [ ] Subtask 2.3: Agrupamento por lado A/B
- [ ] Task 3 — Testes (AC: todos)
  - [ ] Subtask 3.1: Teste de renderização tabela vs cartão por breakpoint
  - [ ] Subtask 3.2: Teste de estado 404/ausente

---

## Dev Notes

### Files/Components Expected

- `consulta-publica-web/components/ficha/PaineisLvTab.tsx`
- `consulta-publica-web/lib/api/paineis-lv.ts`
- (reuso) `consulta-publica-web/components/ui/PanelTable.tsx`, `PanelCard.tsx` (criados na STORY-09)

### Technical Notes

- **Wireframe exato:** [Source: front-end-spec.md §5.4]
- **Fonte de dados:** `panels[].width/height1/height2/panel_type`, `total_width`, `h_section` — architecture §4.1. [Source: front-end-spec.md §5.4 nota "Fonte de dados"]
- **Regra de reflow:** "Sem scroll horizontal: em telas estreitas, cada painel pode reflurir para cartão empilhado... em vez de tabela — o número da largura é o dado que o funcionário procura." [Source: front-end-spec.md §5.4]
- **Estado ausente:** "Estado LV ausente (`tem_lv=false`): a aba não existe. Se o usuário chegou esperando LV... mostrar dentro da ficha uma nota neutra: 'Lista de painéis não disponível para este item.'" [Source: front-end-spec.md §5.4]

---

## Testing

- **Test file location:** `consulta-publica-web/__tests__/paineis-lv/`
- **Testing framework:** Jest + RTL
- **Key test scenarios:**
  - Renderização tabela (≥380px) vs cartão (<380px) com o mesmo dado
  - Tratamento gracioso de 404 (nota neutra, demais abas intactas)
  - `tabular-nums` aplicado aos valores numéricos

---

## 🤖 CodeRabbit Integration

**Story Type Analysis**
- **Primary Type:** Frontend
- **Secondary Type(s):** API (consumo de endpoint sob demanda)
- **Complexity:** Low

**Specialized Agent Assignment**
- **Primary Agents:** @ux-expert, @dev
- **Supporting Agents:** —

**Quality Gate Tasks**
- [ ] Pre-Commit (@dev): a11y validation
- [ ] Pre-PR (@github-devops): UX consistency check
- [ ] Pre-Deployment: N/A

**CodeRabbit Focus Areas**
- **Primary Focus:**
  - Responsive design (reflow tabela↔cartão sem scroll horizontal)
  - Tratamento de estado ausente sem quebrar a ficha
- **Secondary Focus:**
  - Consistência com design system (tabular-nums, tokens)

**Self-Healing Configuration**
- **Expected Self-Healing:** Primary Agent: @dev (light) · Max Iterations: 2 · Timeout: 15 min · Severity Filter: CRITICAL only
- **Predicted Behavior:** CRITICAL (quebra da ficha inteira por erro de painéis): auto_fix. HIGH: document_only.

---

## Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2026-07-11 | 0.1 | Story criada a partir de front-end-spec.md §5.4 e prd.md FR4 | River (SM) |
| 2026-07-12 | 1.0 | Implementado e testado ao vivo — ver Dev Agent Record | Claude (dev) |

---

## Dev Agent Record

**Arquivos criados:**
- `lib/api/paineis-lv.ts` — `buscarPaineisLv`
- `components/ficha/PaineisLvTab.tsx` (+ `.module.css`) — fetch lazy, agrupamento por lado, nota neutra em 404/erro de rede
- `components/ui/PanelTable.tsx` — `moduloStog` tornado opcional (renderiza "—")
- `app/ficha/[code]/page.tsx` — substitui o placeholder "em construção (STORY-13)" pelo componente real
- `__tests__/paineis-lv/{paineis-lv-tab,panel-table-reflow}.test.(ts|tsx)` (8 testes)

**Testes:** 83/83 passando no projeto inteiro (`npm test`). `lint`/`build` limpos.

**Decisão de kickoff — `Módulo STOG` não é preenchido:** o endpoint da
STORY-12 (`/paineis-lv`) deliberadamente NÃO expõe um campo de módulo
STOG — esse valor vive só na lógica interna do motor desktop (fora do
contrato público, decisão já tomada e documentada na STORY-12). Em vez de
inventar um cálculo aqui (violaria Art. IV "No Invention" da Constitution),
tornei `PanelTable.moduloStog` opcional e ele renderiza "—" quando ausente.
Documentado como lacuna de produto conhecida — se o valor real for
necessário, o passo correto é STORY-12 expor um novo campo público (motor
já sabe computar isso internamente), não o frontend inventar uma heurística.

**Padrão lazy consistente com STORY-11:** `PaineisLvTab` só busca
`/paineis-lv` quando `ativo=true` (aba selecionada) — mesmo padrão do SVG
fullscreen. Um `dados !== null` guard evita refetch ao trocar de aba e
voltar (teste dedicado confirma 1 única chamada de rede).

**Verificado ao vivo** contra `:21390`/`:21391`: nenhum item real (pilar
nem viga_lateral) da obra de teste tem `tem_lv=true`, então o caminho
positivo (200 com painéis reais renderizados) só foi validado via os 8
testes Jest com fixture baseada no schema real (mesma fixture criada na
STORY-12). O caminho negativo FOI confirmado ao vivo: um segmento de viga
real (`GxngtSAOFq`, "VENTO 180%%d") sem SVG nenhum (nem N1 nem N3) caiu
automaticamente na aba "paineis" por padrão (lógica de `setAba` da
STORY-10) e, como `tem_lv=false`, renderizou corretamente
`EmptyState variante="lv-absent"` com o texto exato "Lista de painéis não
disponível para este item." — sem quebrar o restante da ficha
(Especificação continuou visível abaixo, AC5 confirmado).
