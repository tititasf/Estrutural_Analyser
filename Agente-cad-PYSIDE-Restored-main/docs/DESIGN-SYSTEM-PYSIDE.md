# Design System -- TSF PROJETOS (PySide6)

**Version:** 2.0.0
**Date:** 2026-06-04
**Application:** TSF PROJETOS -- CAD Estrutural Desktop
**Framework:** PySide6 (Python Qt6)
**Theme:** Dark Professional
**Token Source:** `src/ui/theme.py` (Colors, Fonts, Spacing, Radius, StyleSheets)

> Fonte canonica de tokens visuais, componentes e padroes de layout.
> Todos os modulos DEVEM importar de `src/ui/theme.py` -- nunca usar hex inline.
> Referencia visual: Comparison Engine (niveis N1/N2/N3) e Structural Analyzer (sidebar + canvas).

---

## 1. Principios Visuais

### P1 -- Dark Professional
Background escuro industrial (`#121212` base) com contraste alto para leitura prolongada em estacao de trabalho. Zero cores vibrantes em superficies grandes. Vibrancia reservada exclusivamente para dados e estados. Zero branco puro (`#fff`) como background -- apenas como cor de texto de enfase maxima.

### P2 -- Dados em Primeiro Lugar
O conteudo tecnico (valores numericos, scores, tabelas de ficha, DXF viewers) ocupa o espaco visual dominante. Chrome da UI (bordas, titulos de secao, navegacao) e visualmente recuado -- menor, mais escuro, menos peso tipografico. O usuario olha para DADOS, nao para a moldura.

### P3 -- Hierarquia por Cor
Cor indica FUNCAO, nunca decoracao:
- **Ciano** (`#00d4ff`) = interativo, selecionado, link
- **Azul** (`#0078d4`) = acao primaria (botoes de comando)
- **Semanticas** (verde/amarelo/vermelho) = estado de validacao
- **Nivel** (N1 azul / N2 verde / N3 laranja / N4 roxo) = profundidade de analise
- **Gold** (`#FFD700`) = excelencia (score ARETE)

### P4 -- Feedback de Estado
Todo processo exibe estado visual: pending, running, ok, error. Nenhuma operacao roda "silenciosa". Pipeline steps, progress bars slim, e status badges comunicam o estado em tempo real. Areas vazias usam `EmptyStateWidget` -- nunca um espaco em branco sem mensagem.

### P5 -- Densidade Informacional
Interface otimizada para monitores 1920x1080+. Rows de tabela de 20px, items de lista de 24px, fontes de 9-13px. Espacamento compacto mas legivel. Chrome vertical minimo: top bar 40px, fase bar 22px, tab bar 32px = 94px de overhead total. O profissional de engenharia precisa ver MUITOS dados simultaneamente.

---

## 2. Paleta Completa

### 2.1 Backgrounds

| Token | Hex | Uso |
|-------|-----|-----|
| `Colors.BG_DEEP` | `#121212` | Fundo principal da aplicacao, dialogs, viewers DXF |
| `Colors.BG_PRIMARY` | `#1a1a2e` | Fundo geral da app (legado -- preferir BG_DEEP para novos modulos) |
| `Colors.BG_SECONDARY` | `#16213e` | Headers, paineis secundarios, tab pane selected |
| `Colors.BG_PANEL` | `#1e1e1e` | Paineis internos, sidebars, frames |
| `Colors.BG_CARD` | `#252525` | Cards, items de lista, inputs, botoes secundarios |
| `Colors.BG_SURFACE` | `#252528` | Headers de tabela, list backgrounds |
| `Colors.BG_HOVER` | `#2a2a3e` | Estado hover de items interativos |
| `Colors.BG_DANGER_DARK` | `#332222` | Fundo de botoes danger (hover delete) |

### 2.2 Textos

| Token | Hex | Uso |
|-------|-----|-----|
| `Colors.TEXT_BRIGHT` | `#ffffff` | Enfase maxima: titulos ativos, valores criticos, texto sobre accent |
| `Colors.TEXT_PRIMARY` | `#e0e0e0` | Texto principal corpo |
| `Colors.TEXT_SECONDARY` | `#888888` | Labels, subtitulos, metadata, tabs inativas |
| `Colors.TEXT_DIM` | `#666666` | Texto sutil, timestamps, mensagens auxiliares |
| `Colors.TEXT_MUTED` | `#555555` | Desabilitado, placeholders, footers |
| `Colors.TEXT_LINK` | `#00d4ff` | Links clicaveis (alias de ACCENT_PRIMARY) |

### 2.3 Bordas

| Token | Hex | Uso |
|-------|-----|-----|
| `Colors.BORDER_DEFAULT` | `#333333` | Borda padrao de paineis, cards, tabs |
| `Colors.BORDER_INPUT` | `#444444` | Borda de inputs, botoes secundarios |
| `Colors.BORDER_SUBTLE` | `#2a2a2a` | Separadores suaves entre items de lista |
| `Colors.BORDER_PANEL` | `#2d2d30` | Borda de paineis tipo metric card |
| `Colors.BORDER_ACCENT` | `#00d4ff` | Borda de destaque (focus, selected, active) |
| `Colors.BORDER_TEAL_DARK` | `#2a4654` | Borda card principal (teal escuro) |

### 2.4 Accents -- Acao e Brand

| Token | Hex | Uso |
|-------|-----|-----|
| `Colors.ACCENT_PRIMARY` | `#00d4ff` | Ciano principal: links, selected, highlights, borda focus |
| `Colors.ACCENT_BRAND` | `#00E5FF` | Ciano brand: logo, branding (ligeiramente mais claro) |
| `Colors.ACCENT_BLUE` | `#0078d4` | Azul acao: botoes primarios, tab selected |
| `Colors.ACCENT_BLUE_HOVER` | `#0099ff` | Hover do azul acao |
| `Colors.ACCENT_TEAL` | `#00bcd4` | Teal: sections, links no manager |
| `Colors.ACCENT_MINT` | `#00ffcc` | Mint: botoes de adicionar, grupos especiais |
| `Colors.ACCENT_SLATE` | `#6c7293` | Cinza-azulado: botoes secundarios neutros |

### 2.5 Accents -- Semanticos (Estado)

| Token | Hex | Uso |
|-------|-----|-----|
| `Colors.ACCENT_SUCCESS` | `#4caf50` | Verde sucesso |
| `Colors.ACCENT_SUCCESS_ALT` | `#00cc66` | Verde validacao (mais vivo, para botoes LISP/criar) |
| `Colors.ACCENT_WARNING` | `#ff9800` | Laranja aviso |
| `Colors.ACCENT_WARNING_ALT` | `#ffb300` | Laranja headers |
| `Colors.ACCENT_DANGER` | `#f44336` | Vermelho erro |
| `Colors.ACCENT_DANGER_ALT` | `#f85149` | Vermelho GitHub style |
| `Colors.ACCENT_INFO` | `#e3b341` | Amarelo informativo / nota |
| `Colors.ACCENT_GOLD` | `#FFD700` | Ouro: badge admin, score ARETE |

### 2.6 Accents -- Especiais

| Token | Hex | Uso |
|-------|-----|-----|
| `Colors.ACCENT_PURPLE` | `#a070ff` | Roxo: overlay ativo, canvas active state |
| `Colors.ACCENT_LINK_PURPLE` | `#d500f9` | Roxo vibrante: indicador vinculos, progress bars |
| `Colors.ACCENT_MAGENTA` | `#d63384` | Magenta: sync buttons, training log |
| `Colors.ACCENT_FOREST` | `rgba(26,74,26,1)` | Verde escuro: pipeline buttons SA |
| `Colors.ACCENT_FOREST_BORDER` | `rgba(46,125,50,1)` | Borda do verde escuro |

### 2.7 Transparencias (Glass)

| Token | Valor | Uso |
|-------|-------|-----|
| `Colors.GLASS_WHITE_3` | `rgba(255,255,255,0.03)` | Frosted glass sutil (stats frames, metric cards) |
| `Colors.GLASS_WHITE_5` | `rgba(255,255,255,0.05)` | Frosted glass medio (hover leve, nav button) |
| `Colors.GLASS_WHITE_10` | `rgba(255,255,255,0.10)` | Frosted glass forte (active state, pressed) |

### 2.8 Paleta de Niveis de Analise (Comparison Engine)

Usada no Comparison Engine para identificar profundidade de analise.
Cada nivel tem uma cor accent e um background escuro proprio.

| Nivel | ID | Accent | Background | Descricao |
|-------|----|--------|------------|-----------|
| Nivel 1 | `N1` | `#4a9eff` (azul) | `#1b3a6b` | Estrutura Real -- DXF estrutural original |
| Nivel 2 | `N2` | `#4acf7a` (verde) | `#1a4a2a` | STOG Real -- Engenharia reversa |
| Nivel 3 | `N3` | `#cf8a4a` (laranja) | `#4a2a1a` | Robot Gerado -- DXF gerado pelo robo |
| Nivel 4 | `N4` | `#a855f7` (roxo) | `#2d1a4a` | Validacao Visual (reservado para futuro) |

**Regras da paleta de nivel:**
- O accent do nivel e usado para: badge pill, titulo, borda de header, chunk de progress bar, titulo de pipeline, titulo de ficha, cor de texto do header colorido.
- O background do nivel e usado apenas no header card do nivel (72px de altura).
- A borda do container usa o accent com 13% de opacidade: `{accent}22`.
- Texto descritivo dentro do header usa `rgba(255,255,255,0.65)`.

### 2.9 Score Colors (faixas automaticas)

| Faixa | Label | Token | Hex |
|-------|-------|-------|-----|
| >= 85% | ARETE | `Colors.ACCENT_GOLD` | `#FFD700` |
| >= 75% | OK | `Colors.ACCENT_SUCCESS` | `#4caf50` |
| >= 60% | MELHORAR | `Colors.ACCENT_WARNING` | `#ff9800` |
| < 60% | INVESTIGAR | `Colors.ACCENT_DANGER` | `#f44336` |

Implementacao em `comparison_engine.py :: ScoreLabel` e `_score_category()`.

---

## 3. Tipografia

### 3.1 Font Families

| Token | Valor | Uso |
|-------|-------|-----|
| `Fonts.FAMILY` | `'Segoe UI', Tahoma, Geneva, Verdana, sans-serif` | Toda a interface |
| `Fonts.FAMILY_MONO` | `'Consolas', monospace` | Codigo, paths, terminal de eventos, valores tecnicos |

### 3.2 Escala de Tamanhos

| Token | Valor | Uso Principal |
|-------|-------|---------------|
| `Fonts.SIZE_XS` | `9px` | Pipeline step labels, tooltips, timestamps, fase bar |
| `Fonts.SIZE_SM` | `10px` | Badges, metadata, item lists compactos, field buttons |
| `Fonts.SIZE_MD` | `11px` | **PADRAO** -- Labels, botoes, corpo de tabela, tabs |
| `Fonts.SIZE_LG` | `12px` | Sidebar items, metricas, tree nodes, valores de campo |
| `Fonts.SIZE_XL` | `13px` | Titulos de secao, inputs, badge de nivel, subtitulos |
| `Fonts.SIZE_XXL` | `14px` | Subtitulos de painel, valores de metric card |
| `Fonts.SIZE_TITLE` | `16px` | Titulos de modulo, logo label |
| `Fonts.SIZE_HERO` | `20px` | Score principal hero, valor de destaque maximo |

### 3.3 Pesos por Contexto

| Contexto | Font Size | Font Weight | Color Token |
|----------|-----------|-------------|-------------|
| Label de campo | `SIZE_MD` (11px) | normal | `TEXT_SECONDARY` |
| Valor de campo | `SIZE_MD` (11px) | normal | `TEXT_PRIMARY` |
| Valor destacado | `SIZE_LG` (12px) | bold | `ACCENT_BRAND` |
| Titulo de secao | `SIZE_XL` (13px) | bold | `ACCENT_PRIMARY` |
| Titulo de secao (letter-spacing) | `SIZE_MD` (11px) | bold | `ACCENT_PRIMARY` + `letter-spacing: 1.5px` |
| Badge de status | `SIZE_SM` (10px) ou `SIZE_MD` (11px) | bold | (cor semantica) |
| Badge de nivel | `SIZE_XL` (13px) | bold | (accent do nivel) bg / `#000` text |
| Codigo / path / terminal | `SIZE_SM` (10px) | normal | `TEXT_PRIMARY` + `FAMILY_MONO` |
| Score hero | `SIZE_HERO` (20px) | bold | (cor por faixa) |
| Pipeline step label | `SIZE_XS` (9px) | normal (pending) / bold (active) | `TEXT_SECONDARY` / accent |
| Pipeline step message | 8px (inline) | normal | `TEXT_DIM` / `ACCENT_DANGER` |

---

## 4. Espacamento e Layout

### 4.1 Spacing Scale

| Token | Valor | Uso |
|-------|-------|-----|
| `Spacing.XS` | 2px | Micro gaps (entre icon e texto inline) |
| `Spacing.DENSE` | 4px | Grupos de botoes, linhas de detalhe compactas, pipeline steps |
| `Spacing.BASE` | 8px | Espacamento padrao entre items |
| `Spacing.LOOSE` | 12px | Separadores de secao |
| `Spacing.LARGE` | 16px | Secoes maiores, padding de paineis internos |
| `Spacing.OUTER` | 20px | Margens de container externo |

### 4.2 Margins (tuplas para setContentsMargins)

| Token | Valor | Uso |
|-------|-------|-----|
| `Spacing.MARGINS_ZERO` | `(0, 0, 0, 0)` | Encaixe flush, layouts inline |
| `Spacing.MARGINS_TIGHT` | `(8, 8, 8, 8)` | Cards compactos, LevelColumn content |
| `Spacing.MARGINS_INNER` | `(16, 16, 16, 16)` | Paineis internos |
| `Spacing.MARGINS_OUTER` | `(20, 20, 20, 20)` | Containers principais, estados vazios |

### 4.3 Border Radius

| Token | Valor | Uso |
|-------|-------|-----|
| `Radius.SM` | `3px` | Inputs, badges pequenos, pipeline frame |
| `Radius.MD` | `4px` | Botoes secundarios, cards de lista, tabelas |
| `Radius.LG` | `6px` | Botoes primarios, paineis |
| `Radius.XL` | `8px` | GroupBox, dialogs, metric cards |
| `Radius.PILL` | `12px` | Badge pill, toggle buttons |
| `Radius.CIRCLE` | `50%` | Avatares |

### 4.4 Component Heights (fixos)

| Componente | Altura | Largura | Notas |
|------------|--------|---------|-------|
| TopBar | 40px | 100% | Logo + combos + status |
| FaseLabel bar | 22px | 100% | Texto 10px + padding 6px |
| ModuleTabBar | 32px | 100% | 8 tabs com padding 6px 16px |
| Sidebar | flex | 280px fixed | Tree widget + botoes |
| Item de lista | 24px min-height | flex | padding 4px top/bottom |
| Row de tabela | 20px | flex | Densidade maxima para fichas |
| Botao field (compacto) | 22px | auto | Vincular, Zoom, N/A |
| Botao primario | 32px | auto (min 80px) | Acao principal com texto |
| Botao grande CTA | 40px | 100% ou auto | Salvar, AI Fix |
| Nav button sidebar | 36px | 100% | Item de navegacao |
| Progress bar slim | 4px | 100% | Indicacao sutil |
| Progress bar normal | 8px | 100% | Visibilidade media |
| Progress bar labeled | 14px | 100% | Com texto (%) dentro |
| Level column header | 72px | 540px | Badge + titulo + descricao |
| Level column | flex | 540px fixed | Coluna completa N1/N2/N3 |
| DXF viewer | min 260px | flex | Canvas central |
| Ficha table | 240px fixed | flex | Tabela de dados da ficha |
| Terminal de eventos | max 150px | flex | QTextEdit mono |

---

## 5. Componentes

### 5.1 TopBar

Barra superior fixa com gradiente linear, logo a esquerda, combos de obra/pavimento no centro, status a direita.

```python
# Construcao:
top_bar = QFrame()
top_bar.setObjectName("TopBar")
top_bar.setFixedHeight(40)
top_layout = QHBoxLayout(top_bar)
top_layout.setContentsMargins(10, 0, 20, 0)
top_layout.setSpacing(10)
```

**QSS:**

```css
QFrame#TopBar {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #121212, stop:1 #1e1e1e);
    border-bottom: 1px solid #333333;
}

QFrame#TopBar QLabel#LogoLabel {
    color: #00E5FF;
    font-weight: bold;
    font-size: 16px;
    background: transparent;
}

QFrame#TopBar QComboBox {
    background: #252525;
    color: #e0e0e0;
    border: 1px solid #333333;
    border-radius: 3px;
    padding: 2px 6px;
    font-size: 11px;
    min-width: 140px;
}

QFrame#TopBar QComboBox:hover {
    border-color: #00d4ff;
}

QFrame#TopBar QLabel {
    color: #888888;
    font-size: 10px;
    background: transparent;
}
```

### 5.2 FaseLabel Bar

Faixa estreita abaixo do TopBar indicando a etapa ativa do pipeline. Texto align-left com letter-spacing.

```python
# Construcao:
fase_bar = QFrame()
fase_bar.setObjectName("FaseLabel")
fase_bar.setFixedHeight(22)
```

**QSS:**

```css
QFrame#FaseLabel {
    background: #060e1a;
    border-bottom: 1px solid #0f2040;
    min-height: 22px;
    max-height: 22px;
}

QFrame#FaseLabel QLabel {
    color: #3a7fd4;
    font-size: 9px;
    font-weight: bold;
    letter-spacing: 1px;
    background: transparent;
    padding-left: 12px;
}
```

### 5.3 ModuleTabBar (8 tabs)

Tab bar horizontal com 8 modulos (Gerenciar Projetos, Diagnostic Hub, Structural Analyzer, Comparison Engine, 4x Robos). Tab ativa tem underline cyan 2px. Sem bordas laterais entre tabs.

```python
# Construcao:
module_tabs = QTabWidget()
module_tabs.setObjectName("ModuleTabs")
module_tabs.tabBar().setObjectName("ModuleNav")
```

**QSS:**

```css
QTabWidget#ModuleTabs::pane {
    background: #121212;
    border: none;
}

QTabBar#ModuleNav::tab {
    background: #121212;
    color: #888888;
    padding: 6px 16px;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: 11px;
    font-weight: bold;
    min-width: 100px;
    height: 32px;
}

QTabBar#ModuleNav::tab:selected {
    color: #00d4ff;
    background: #16213e;
    border-bottom: 2px solid #00d4ff;
}

QTabBar#ModuleNav::tab:hover:!selected {
    color: #e0e0e0;
    background: #2a2a3e;
}
```

### 5.4 SidebarPanel

Painel lateral esquerdo com background escuro, borda direita, tree widget interno. Largura fixa de 280px.

```python
# Construcao:
sidebar = QWidget()
sidebar.setObjectName("SidePanel")
sidebar.setFixedWidth(280)
```

**QSS:**

```css
#SidePanel {
    background: #1e1e1e;
    border-right: 1px solid #333333;
    min-width: 280px;
    max-width: 280px;
}

#SidePanel QTreeWidget {
    background: transparent;
    color: #e0e0e0;
    border: none;
    font-size: 12px;
    outline: none;
}

#SidePanel QTreeWidget::item {
    padding: 6px 8px;
    border-bottom: 1px solid #2a2a2a;
}

#SidePanel QTreeWidget::item:hover {
    background: #2a2a3e;
}

#SidePanel QTreeWidget::item:selected {
    background: rgba(0, 120, 212, 0.1);
    color: #00d4ff;
    border-left: 3px solid #0078d4;
}
```

### 5.5 ListView / TreeView (generico)

Listas scrollaveis com items de 24px, borda arredondada, fundo surface.

**QSS:**

```css
QListWidget, QTreeWidget {
    background: #252528;
    color: #e0e0e0;
    border: 1px solid #444444;
    border-radius: 4px;
    font-size: 10px;
    outline: none;
}

QListWidget::item, QTreeWidget::item {
    padding: 4px 8px;
    min-height: 24px;
    border-bottom: 1px solid #2a2a2a;
}

QListWidget::item:hover, QTreeWidget::item:hover {
    background: #2a2a3e;
}

QListWidget::item:selected, QTreeWidget::item:selected {
    background: #16213e;
    color: #00d4ff;
}
```

### 5.6 StatusBadge (PASS/FAIL/WARN/INFO/PENDING)

Badge visual com cor semantica. Implementado como `QLabel` com padding, borda e background semi-transparente. Referencia: `src/ui/components/atoms.py :: StatusBadge`.

**Variantes QSS:**

**PASS / VALID / OK:**
```css
StatusBadge {
    background-color: rgba(40, 167, 69, 0.2);
    color: #4caf50;
    border: 1px solid #4caf50;
    border-radius: 4px;
    padding: 4px 8px;
    font-weight: bold;
    font-size: 11px;
}
```

**WARN / REVISAO:**
```css
StatusBadge {
    background-color: rgba(255, 193, 7, 0.2);
    color: #ff9800;
    border: 1px solid #ff9800;
    border-radius: 4px;
    padding: 4px 8px;
    font-weight: bold;
    font-size: 11px;
}
```

**FAIL / ERROR / CRITICAL:**
```css
StatusBadge {
    background-color: rgba(220, 53, 69, 0.2);
    color: #f44336;
    border: 1px solid #f44336;
    border-radius: 4px;
    padding: 4px 8px;
    font-weight: bold;
    font-size: 11px;
}
```

**INFO:**
```css
StatusBadge {
    background-color: rgba(0, 212, 255, 0.15);
    color: #00d4ff;
    border: 1px solid #00d4ff;
    border-radius: 4px;
    padding: 4px 8px;
    font-weight: bold;
    font-size: 11px;
}
```

**PENDING:**
```css
StatusBadge {
    background-color: rgba(136, 136, 136, 0.15);
    color: #888888;
    border: 1px solid #555555;
    border-radius: 4px;
    padding: 4px 8px;
    font-weight: bold;
    font-size: 11px;
}
```

**Compact variant:** Substituir `padding: 4px 8px` por `padding: 2px 6px` e `font-size: 11px` por `font-size: 10px`.

### 5.7 DataTable (Ficha de Dados)

Tabela QTableWidget com alternating row colors, header com peso visual, rows de 20px. Usado para fichas de pilares, vigas, lajes.

**QSS generico:**

```css
QTableWidget {
    background: #1e1e1e;
    color: #e0e0e0;
    border: 1px solid #333333;
    border-radius: 4px;
    gridline-color: #2a2a2a;
    font-size: 10px;
    outline: none;
    alternate-background-color: #1a1a1e;
}

QTableWidget::item {
    padding: 2px 6px;
}

QTableWidget::item:selected {
    background: rgba(0, 120, 212, 0.2);
    color: #00d4ff;
}

QHeaderView::section {
    background: #252528;
    color: #888888;
    border: none;
    border-bottom: 1px solid #333333;
    border-right: 1px solid #2a2a2a;
    padding: 4px 6px;
    font-size: 10px;
    font-weight: bold;
}
```

**DataTable com header colorido por nivel** (Comparison Engine):

Dentro de um LevelColumn, o header da tabela usa o accent do nivel para cor de texto e um background com opacidade reduzida.

```python
def ficha_table_qss(accent: str) -> str:
    """QSS para tabela de ficha dentro de LevelColumn."""
    return f"""
    QTableWidget {{
        background: {Colors.BG_PANEL};
        color: {Colors.TEXT_PRIMARY};
        border: 1px solid {Colors.BORDER_DEFAULT};
        gridline-color: {Colors.BORDER_SUBTLE};
        font-size: {Fonts.SIZE_SM};
        alternate-background-color: #1a1a1e;
    }}
    QTableWidget::item {{
        padding: 2px 6px;
    }}
    QHeaderView::section {{
        background: {accent}22;
        color: {accent};
        border: none;
        border-bottom: 1px solid {Colors.BORDER_DEFAULT};
        padding: 4px 6px;
        font-size: {Fonts.SIZE_SM};
        font-weight: bold;
    }}
    """
```

Configuracao obrigatoria:
```python
table.setAlternatingRowColors(True)
table.verticalHeader().setVisible(False)
table.setEditTriggers(QTableWidget.NoEditTriggers)
table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
```

### 5.8 PipelineStepWidget

Mini-painel com N steps de processamento por nivel. Cada step tem icon (16px) + label (flex) + message (right-aligned). Referencia: `comparison_engine.py :: PipelineStepsWidget`.

**Status icons e cores:**

| Status | Icon | Cor |
|--------|------|-----|
| `pending` | `(hourglass)` | `Colors.TEXT_SECONDARY` (#888888) |
| `running` | `(spinner)` | `Colors.ACCENT_WARNING` (#ff9800) |
| `ok` | `(check)` | `Colors.ACCENT_SUCCESS_ALT` (#00cc66) |
| `error` | `(cross)` | `Colors.ACCENT_DANGER` (#f44336) |

**QSS do frame container (parametrizado por nivel):**

```python
def pipeline_frame_qss(bg_color: str, accent: str) -> str:
    return f"""
    QFrame {{
        background: {bg_color};
        border-radius: 4px;
        border: 1px solid {accent}22;
    }}
    """
```

**QSS dos elementos internos:**

```python
# Title label do pipeline:
f"color: {accent}; font-size: 9px; font-weight: bold; background: transparent;"

# Step label (pending):
f"color: {Colors.TEXT_SECONDARY}; font-size: 9px; background: transparent;"

# Step label (active -- ok/error/running):
f"color: {color}; font-size: 9px; font-weight: bold; background: transparent;"

# Step message (normal):
f"color: {Colors.TEXT_DIM}; font-size: 8px; background: transparent;"

# Step message (error):
f"color: {Colors.ACCENT_DANGER}; font-size: 8px; background: transparent;"

# Icon label:
"background: transparent; font-size: 10px;"
```

Layout: `setContentsMargins(6, 4, 6, 4)`, `setSpacing(2)`.

### 5.9 ActionButton (primary / secondary / ghost / danger)

Quatro variantes de botao. Usar `StyleSheets.button_primary()` etc. do theme.py ou aplicar QSS abaixo.

**Primary** -- Acao principal. Azul solido. `setFixedHeight(32)`.

```css
QPushButton[class="primary"],
QPushButton#PrimaryButton {
    background: #0078d4;
    color: #ffffff;
    border: none;
    padding: 8px 16px;
    font-size: 11px;
    font-weight: bold;
    border-radius: 6px;
}

QPushButton[class="primary"]:hover,
QPushButton#PrimaryButton:hover {
    background: #0099ff;
}

QPushButton[class="primary"]:pressed,
QPushButton#PrimaryButton:pressed {
    background: #005a9e;
}

QPushButton[class="primary"]:disabled,
QPushButton#PrimaryButton:disabled {
    color: #555555;
    background: #252525;
}
```

**Secondary** -- Acao auxiliar. Background card com borda.

```css
QPushButton[class="secondary"] {
    background: #252525;
    color: #e0e0e0;
    border: 1px solid #444444;
    padding: 5px 10px;
    font-size: 11px;
    border-radius: 4px;
}

QPushButton[class="secondary"]:hover {
    background: #333333;
    border-color: #555555;
}

QPushButton[class="secondary"]:pressed {
    background: #1a1a1a;
}
```

**Ghost** -- Botao transparente com accent outline. Referencia: `StyleSheets.button_accent()`.

```css
QPushButton[class="ghost"] {
    background: transparent;
    color: #00d4ff;
    border: 1px solid #00d4ff;
    padding: 4px 8px;
    font-size: 11px;
    border-radius: 3px;
}

QPushButton[class="ghost"]:hover {
    background: #00d4ff;
    color: #121212;
}

QPushButton[class="ghost"]:disabled {
    color: #555555;
    border-color: #333333;
}
```

**Danger** -- Acao destrutiva. Vermelho ao hover.

```css
QPushButton[class="danger"] {
    background: #252525;
    color: #f44336;
    border: 1px solid #444444;
    padding: 5px 10px;
    font-size: 11px;
    border-radius: 4px;
}

QPushButton[class="danger"]:hover {
    background: #332222;
    border-color: #f44336;
}

QPushButton[class="danger"]:pressed {
    background: #2a1111;
}
```

**Field Button** -- Compacto (22px). Usado para Vincular, Zoom, Validar, N/A.

```css
QPushButton[class="field-btn"] {
    font-size: 10px;
    font-weight: bold;
    border: 1px solid #333333;
    border-radius: 3px;
    background: #252525;
    padding: 2px 6px;
    max-height: 22px;
}

QPushButton[class="field-btn"]:hover {
    background: #333333;
    border-color: #555555;
}
```

### 5.10 ProgressBar

**Slim (4px)** -- Indicacao sutil, sem texto. Usado em LevelColumn.

```python
bar.setFixedHeight(4)
bar.setStyleSheet(f"""
    QProgressBar {{
        background: {Colors.BG_DEEP};
        border: none;
        border-radius: 2px;
    }}
    QProgressBar::chunk {{
        background: {Colors.ACCENT_PRIMARY};
        border-radius: 2px;
    }}
""")
```

**ProgressBar slim com accent de nivel:**

```python
def progress_bar_nivel_qss(accent: str) -> str:
    return f"""
    QProgressBar {{
        border: none;
        background: {Colors.BG_DEEP};
    }}
    QProgressBar::chunk {{
        background: {accent};
    }}
    """
```

**Normal (8px)** -- Visibilidade media.

```css
QProgressBar[class="normal"] {
    background: #252525;
    border: 1px solid #333333;
    border-radius: 3px;
    max-height: 8px;
    min-height: 8px;
    text-align: center;
    color: transparent;
}

QProgressBar[class="normal"]::chunk {
    background: #00d4ff;
    border-radius: 2px;
}
```

**Labeled (14px)** -- Com texto percentual dentro. Usado pelo StyleSheets.progress_bar().

```css
QProgressBar {
    background: #252525;
    border: 1px solid #333333;
    border-radius: 3px;
    text-align: center;
    color: #e0e0e0;
    font-size: 10px;
    max-height: 14px;
    min-height: 14px;
}

QProgressBar::chunk {
    background: #00d4ff;
    border-radius: 2px;
}
```

**Indeterminado:** `bar.setRange(0, 0)` com altura 4px (loading states).

### 5.11 DXFCanvas Frame

Container do viewer DXF com background extra-escuro e borda fina.

```python
canvas.setObjectName("DXFCanvas")
canvas.setMinimumHeight(260)
canvas.setStyleSheet(f"""
    background: {Colors.BG_DEEP};
    border: 1px solid {Colors.BORDER_DEFAULT};
    border-radius: 2px;
""")
# Para viewers com fundo preto absoluto:
# background: #0a0a0a;
```

Regra: Viewers DXF NUNCA exibem scrollbars. Pan/zoom e feito via mouse.

```python
canvas.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
canvas.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
```

### 5.12 ScoreLabel

Label de score com cor automatica por faixa. Tamanho hero (20px), bold. A cor e setada programaticamente, nao via QSS estatico.

```python
class ScoreLabel(QLabel):
    """Label de score com cor automatica por faixa."""

    SCORE_COLORS = {
        "arete":   (Colors.ACCENT_GOLD,    "ARETE"),
        "ok":      (Colors.ACCENT_SUCCESS,  "OK"),
        "improve": (Colors.ACCENT_WARNING,  "MELHORAR"),
        "bad":     (Colors.ACCENT_DANGER,   "INVESTIGAR"),
    }

    def set_score(self, score: float | None):
        if score is None:
            self.setText("--")
            self.setStyleSheet(
                f"color: {Colors.TEXT_DIM}; font-size: 20px; font-weight: bold;"
            )
            return
        cat = self._categorize(score)
        color = self.SCORE_COLORS[cat][0]
        self.setText(f"{score:.1f}%")
        self.setStyleSheet(f"color: {color}; font-size: 20px; font-weight: bold;")

    @staticmethod
    def _categorize(score: float) -> str:
        if score >= 85: return "arete"
        if score >= 75: return "ok"
        if score >= 60: return "improve"
        return "bad"
```

### 5.13 NivelBadge (N1/N2/N3/N4)

Badge pill com cor accent solida do nivel, texto preto bold. Largura fixa 28-36px.

```python
NIVEL_ACCENTS = {
    "N1": "#4a9eff",
    "N2": "#4acf7a",
    "N3": "#cf8a4a",
    "N4": "#a855f7",
}

def nivel_badge_qss(nivel_id: str) -> str:
    accent = NIVEL_ACCENTS.get(nivel_id, Colors.TEXT_SECONDARY)
    return f"""
    QLabel {{
        background: {accent};
        color: #000000;
        font-weight: bold;
        font-size: 13px;
        padding: 1px 6px;
        border-radius: 3px;
        min-width: 28px;
        max-width: 36px;
    }}
    """
```

**NivelBadge titulo** (texto ao lado do badge, sem background):

```python
def nivel_title_qss(accent: str) -> str:
    return f"""
    QLabel {{
        color: {accent};
        font-weight: bold;
        font-size: 13px;
        background: transparent;
    }}
    """
```

### 5.14 ComboBox

```python
# Usar: StyleSheets.combo_box()
```

**QSS:**

```css
QComboBox {
    background: #252525;
    color: #e0e0e0;
    border: 1px solid #333333;
    padding: 4px 6px;
    font-size: 11px;
    border-radius: 3px;
}

QComboBox:hover,
QComboBox:focus {
    border-color: #00d4ff;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox QAbstractItemView {
    background: #252525;
    color: #e0e0e0;
    selection-background-color: #2a2a3e;
    selection-color: #00d4ff;
    border: 1px solid #333333;
    outline: none;
}
```

### 5.15 InputField

```python
# Usar: StyleSheets.input_field()
```

**QSS:**

```css
QLineEdit, QTextEdit {
    background: #252525;
    border: 1px solid #333333;
    border-radius: 3px;
    padding: 4px 6px;
    color: #e0e0e0;
    font-size: 13px;
    selection-background-color: rgba(0, 212, 255, 0.3);
}

QLineEdit:focus, QTextEdit:focus {
    border: 1px solid #00d4ff;
}

QLineEdit:disabled, QTextEdit:disabled {
    background: #1e1e1e;
    color: #555555;
}
```

### 5.16 GroupBox

```python
# Usar: StyleSheets.group_box()
```

**QSS:**

```css
QGroupBox {
    font-size: 11px;
    font-weight: bold;
    color: #00d4ff;
    border: 1px solid #333333;
    border-radius: 8px;
    margin-top: 8px;
    padding-top: 12px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    background: #121212;
}
```

### 5.17 ScrollArea

```python
# Usar: StyleSheets.scroll_area()
```

**QSS:**

```css
QScrollArea {
    border: none;
    background: transparent;
}

QScrollBar:vertical {
    border: none;
    background: #1e1e1e;
    width: 8px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #444444;
    min-height: 20px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #555555;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    border: none;
    background: #1e1e1e;
    height: 8px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background: #444444;
    min-width: 20px;
    border-radius: 4px;
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0;
}
```

### 5.18 Section Header

Cabecalho de secao padronizado. Titulo em maiusculas com letter-spacing e linha separadora. Referencia: `atoms.py :: make_section_header()`.

```python
from src.ui.components.atoms import make_section_header

header = make_section_header("PILARES", "42 registros", accent_color=Colors.ACCENT_PRIMARY)
layout.addWidget(header)
```

**QSS do titulo:**
```python
f"color: {color}; font-size: {Fonts.SIZE_MD}; font-weight: bold; letter-spacing: 1.5px; background: transparent;"
```

**QSS da linha separadora:**
```python
f"background-color: {Colors.BORDER_SUBTLE}; border: none;"
# QFrame.HLine, height=1px
```

### 5.19 MetricCard

Card de metrica com fundo glass, borda panel, border-radius XL.

```python
card.setStyleSheet(f"""
    QFrame {{
        background: {Colors.GLASS_WHITE_3};
        border: 1px solid {Colors.BORDER_PANEL};
        border-radius: {Radius.XL};
        padding: 8px;
    }}
    QFrame:hover {{
        border-color: {Colors.ACCENT_BLUE};
        background: #222225;
    }}
""")
# Titulo: TEXT_SECONDARY, SIZE_SM
# Valor:  TEXT_BRIGHT, SIZE_XXL, bold
# Delta:  ACCENT_SUCCESS ou ACCENT_DANGER, SIZE_XS
```

### 5.20 EmptyStateWidget / LoadingStateWidget

Widgets de estado padronizados. Importar do theme.py.

```python
from src.ui.theme import EmptyStateWidget, LoadingStateWidget

# Estado vazio:
empty = EmptyStateWidget(
    message="Nenhum projeto carregado",
    icon="O",
    detail="Selecione uma obra para comecar."
)
# icon: 32px, TEXT_MUTED | message: SIZE_XL, TEXT_SECONDARY, bold | detail: SIZE_MD, TEXT_MUTED

# Estado loading:
loading = LoadingStateWidget(message="Processando DXF...")
# barra indeterminada h=4px, ACCENT_PRIMARY
```

### 5.21 Terminal de Eventos

```python
terminal = QTextEdit()
terminal.setReadOnly(True)
terminal.setMaximumHeight(150)
terminal.setStyleSheet(f"""
    QTextEdit {{
        background: {Colors.BG_DEEP};
        color: {Colors.ACCENT_SUCCESS_ALT};
        font-family: {Fonts.FAMILY_MONO};
        font-size: {Fonts.SIZE_SM};
        border: 1px solid {Colors.BORDER_DEFAULT};
        border-radius: {Radius.SM};
        padding: 4px;
    }}
""")
```

---

## 6. Padroes de Layout

### 6.1 SidebarLeft + ContentArea

Layout primario. Usado por: Structural Analyzer, Comparison Engine (painel fase-8), Gerenciar Projetos.

```
+------+-----------------------------+
|      |                             |
| SIDE |       Content Area          |
| BAR  |    (viewer / tabela /       |
|      |     dual canvas / ficha)    |
| 280  |                             |
|  px  |                             |
|      |                             |
| fixed|        flex (stretch)       |
+------+-----------------------------+
```

**Implementacao:**

```python
splitter = QSplitter(Qt.Horizontal)

sidebar = QWidget()
sidebar.setObjectName("SidePanel")
sidebar.setFixedWidth(280)
sidebar.setStyleSheet(f"""
    background: {Colors.BG_PANEL};
    border-right: 1px solid {Colors.BORDER_DEFAULT};
""")

content = QWidget()
content.setStyleSheet(f"background: {Colors.BG_DEEP};")

splitter.addWidget(sidebar)
splitter.addWidget(content)
splitter.setStretchFactor(0, 0)  # sidebar fixa
splitter.setStretchFactor(1, 1)  # content flex
```

### 6.2 FullCanvas

Canvas DXF ocupa toda a area. Controles em toolbar acima ou overlay.
Usado por: Diagnostic Hub (modo visualizacao), viewers DXF standalone.

```
+-------------------------------------+
| [Toolbar / Controls]           28px |
+-------------------------------------+
|                                     |
|           DXF Canvas                |
|           (#0a0a0a bg)              |
|                                     |
|           (pan/zoom via mouse)      |
|                                     |
+-------------------------------------+
```

### 6.3 TriColumn (Comparison Engine)

Tres colunas de largura fixa (540px cada) lado a lado dentro de QScrollArea horizontal. Cada coluna e um LevelColumn com header colorido, viewer, pipeline steps e ficha.

```
+------------+------------+------------+
|  N1 Column |  N2 Column |  N3 Column |
|   540px    |   540px    |   540px    |
|            |            |            |
| [header    | [header    | [header    |
|  72px      |  72px      |  72px      |
|  #1b3a6b]  |  #1a4a2a]  |  #4a2a1a]  |
|            |            |            |
| [DXF view  | [DXF view  | [DXF view  |
|  260px+]   |  260px+]   |  260px+]   |
|            |            |            |
| [progress  | [progress  | [progress  |
|  4px]      |  4px]      |  4px]      |
|            |            |            |
| [pipeline  | [pipeline  | [pipeline  |
|  steps]    |  steps]    |  steps]    |
|            |            |            |
| [ficha     | [ficha     | [ficha     |
|  240px]    |  240px]    |  240px]    |
+------------+------------+------------+
        dentro de QScrollArea horizontal
```

**Implementacao do LevelColumn:**

```python
col = QFrame()
col.setFixedWidth(540)
col.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
col.setStyleSheet(f"""
    QFrame {{
        background: {Colors.BG_SECONDARY};
        border-right: 1px solid {Colors.BORDER_DEFAULT};
    }}
""")
# Layout interno: QVBoxLayout margins(8,8,8,8) spacing(6)
```

---

## 7. Regras Anti-Padrao

### 7.1 PROIBIDO: Cores hex inline

```python
# ERRADO
label.setStyleSheet("color: #00d4ff;")
frame.setStyleSheet("background: #1e1e1e;")

# CORRETO
label.setStyleSheet(f"color: {Colors.ACCENT_PRIMARY};")
frame.setStyleSheet(f"background: {Colors.BG_PANEL};")
```

**Excecao UNICA:** Cores de serie de grafico (sparklines, charts) que nao tem correspondente semantico nos tokens. Marcar com comentario `# hardcoded-ok: cor de serie de grafico, sem token equivalente`.

### 7.2 PROIBIDO: setFixedWidth em colunas que devem ser flex

```python
# ERRADO -- trava a coluna independente da janela
table.setColumnWidth(1, 200)
table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)

# CORRETO -- coluna estica com o container
table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
```

### 7.3 PROIBIDO: QScrollBar:horizontal visivel em DXF viewers

```python
# ERRADO -- scrollbar aparece no viewer
canvas.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

# CORRETO -- viewers usam pan/zoom via mouse
canvas.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
canvas.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
```

### 7.4 PROIBIDO: Hex abreviados ou genericos hardcoded

```python
# ERRADO -- hex sem semantica
"background: #333;"
"color: #444;"
"border: 1px solid #222;"

# CORRETO -- referencia ao token
f"background: {Colors.BORDER_DEFAULT};"
f"color: {Colors.BORDER_INPUT};"
f"border: 1px solid {Colors.BORDER_SUBTLE};"
```

### 7.5 PROIBIDO: font-size sem token

```python
# ERRADO
"font-size: 12px;"
"font-size: 14px;"

# CORRETO
f"font-size: {Fonts.SIZE_LG};"
f"font-size: {Fonts.SIZE_XXL};"
```

### 7.6 PROIBIDO: Spacing magico

```python
# ERRADO -- valores arbitrarios
layout.setContentsMargins(15, 15, 15, 15)
layout.setSpacing(7)

# CORRETO -- tokens de spacing
layout.setContentsMargins(*Spacing.MARGINS_INNER)
layout.setSpacing(Spacing.BASE)
```

### 7.7 PROIBIDO: f-string placeholders nao interpolados

```python
# ERRADO -- bug comum! String SEM f-prefix, tokens viram texto literal
self.setStyleSheet("""
    NavButton:checked {
        color: {Colors.ACCENT_BLUE};
    }
""")
# Resultado: color: {Colors.ACCENT_BLUE}  (literal, nao resolve)

# CORRETO -- com f-prefix e {{ }} para chaves CSS
self.setStyleSheet(f"""
    NavButton:checked {{
        color: {Colors.ACCENT_BLUE};
    }}
""")
# Resultado: color: #0078d4
```

**Nota:** Este bug existe atualmente em `atoms.py` nos widgets NavButton, SyncToggleButton, AttachmentChip e AISuggestionBox.

### 7.8 PROIBIDO: QMainWindow dentro de tab sem flag

```python
# ERRADO -- abre janela flutuante
manager = ProjectManager()
tab.addWidget(manager)

# CORRETO -- embutir como widget
manager = ProjectManager()
manager.setWindowFlags(Qt.Widget)
tab.addWidget(manager)
```

### 7.9 PROIBIDO: Espaco vazio sem mensagem

```python
# ERRADO -- area em branco confusa
if not data:
    pass  # nada aparece

# CORRETO -- estado vazio informativo
if not data:
    empty = EmptyStateWidget(message="Sem dados", icon="O", detail="Carregue uma obra.")
    layout.addWidget(empty)
```

---

## 8. QSS Master Sheet

Aplicar no `QApplication` para garantir base consistente global. Componentes especificos podem fazer override via `setStyleSheet()` com maior especificidade.

```css
/* =================================================================
   TSF PROJETOS -- Master QSS v2.0
   Aplicar via: app.setStyleSheet(open("master.qss").read())
   Tokens source: src/ui/theme.py
   ================================================================= */

/* -- Base -------------------------------------------------------- */

QMainWindow {
    background-color: #121212;
    color: #e0e0e0;
}

QWidget {
    background-color: #121212;
    color: #e0e0e0;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    font-size: 11px;
}

/* -- ScrollBars -------------------------------------------------- */

QScrollBar:vertical {
    border: none;
    background: #1e1e1e;
    width: 8px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #444444;
    min-height: 20px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #555555;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    border: none;
    background: #1e1e1e;
    height: 8px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background: #444444;
    min-width: 20px;
    border-radius: 4px;
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0;
}

/* -- Tabs -------------------------------------------------------- */

QTabWidget::pane {
    background: #121212;
    border: none;
}

QTabBar::tab {
    background: #1e1e1e;
    color: #888888;
    padding: 6px 16px;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: 11px;
}

QTabBar::tab:selected {
    color: #ffffff;
    border-bottom: 2px solid #00d4ff;
}

QTabBar::tab:hover:!selected {
    color: #e0e0e0;
    background: #2a2a3e;
}

/* -- Buttons (base) ---------------------------------------------- */

QPushButton {
    background: #252525;
    border: 1px solid #444444;
    border-radius: 4px;
    padding: 5px 10px;
    color: #e0e0e0;
    font-size: 11px;
}

QPushButton:hover {
    background: #333333;
    border-color: #555555;
}

QPushButton:pressed {
    background: #1a1a1a;
}

QPushButton:disabled {
    color: #555555;
    background: #1e1e1e;
}

/* -- Button: Primary --------------------------------------------- */

QPushButton#PrimaryButton {
    background: #0078d4;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: bold;
}

QPushButton#PrimaryButton:hover {
    background: #0099ff;
}

QPushButton#PrimaryButton:pressed {
    background: #005a9e;
}

QPushButton#PrimaryButton:disabled {
    color: #555555;
    background: #252525;
}

/* -- Button: Small Primary --------------------------------------- */

QPushButton#PrimarySmall {
    background: #0078d4;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 5px 12px;
    font-size: 11px;
    font-weight: bold;
}

/* -- Button: Field (compact 22px) -------------------------------- */

QPushButton[class="field-btn"] {
    font-size: 10px;
    font-weight: bold;
    border: 1px solid #333333;
    border-radius: 3px;
    background: #252525;
    padding: 2px 6px;
    max-height: 22px;
}

QPushButton[class="field-btn"]:hover {
    background: #333333;
    border-color: #555555;
}

/* -- Inputs ------------------------------------------------------ */

QLineEdit, QTextEdit {
    background: #252525;
    border: 1px solid #333333;
    border-radius: 3px;
    padding: 4px 6px;
    color: #e0e0e0;
    font-size: 13px;
    selection-background-color: rgba(0, 212, 255, 0.3);
}

QLineEdit:focus, QTextEdit:focus {
    border: 1px solid #00d4ff;
}

QLineEdit:disabled, QTextEdit:disabled {
    background: #1e1e1e;
    color: #555555;
}

/* -- ComboBox ---------------------------------------------------- */

QComboBox {
    background: #252525;
    color: #e0e0e0;
    border: 1px solid #333333;
    padding: 4px 6px;
    font-size: 11px;
    border-radius: 3px;
}

QComboBox:hover, QComboBox:focus {
    border-color: #00d4ff;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox QAbstractItemView {
    background: #252525;
    color: #e0e0e0;
    selection-background-color: #2a2a3e;
    selection-color: #00d4ff;
    border: 1px solid #333333;
    outline: none;
}

/* -- Lists & Trees ----------------------------------------------- */

QListWidget, QTreeWidget {
    background: #252528;
    color: #e0e0e0;
    border: 1px solid #444444;
    border-radius: 4px;
    font-size: 10px;
    outline: none;
}

QListWidget::item, QTreeWidget::item {
    padding: 4px 8px;
    min-height: 24px;
    border-bottom: 1px solid #2a2a2a;
}

QListWidget::item:hover, QTreeWidget::item:hover {
    background: #2a2a3e;
}

QListWidget::item:selected, QTreeWidget::item:selected {
    background: #16213e;
    color: #00d4ff;
}

/* -- Tables ------------------------------------------------------ */

QTableWidget {
    background: #1e1e1e;
    color: #e0e0e0;
    border: 1px solid #333333;
    border-radius: 4px;
    gridline-color: #2a2a2a;
    font-size: 10px;
    outline: none;
    alternate-background-color: #1a1a1e;
}

QTableWidget::item {
    padding: 2px 6px;
}

QTableWidget::item:selected {
    background: rgba(0, 120, 212, 0.2);
    color: #00d4ff;
}

QHeaderView::section {
    background: #252528;
    color: #888888;
    border: none;
    border-bottom: 1px solid #333333;
    border-right: 1px solid #2a2a2a;
    padding: 4px 6px;
    font-size: 10px;
    font-weight: bold;
}

/* -- GroupBox ----------------------------------------------------- */

QGroupBox {
    font-size: 11px;
    font-weight: bold;
    color: #00d4ff;
    border: 1px solid #333333;
    border-radius: 8px;
    margin-top: 8px;
    padding-top: 12px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    background: #121212;
}

/* -- ProgressBar (default labeled 14px) -------------------------- */

QProgressBar {
    background: #252525;
    border: 1px solid #333333;
    border-radius: 3px;
    text-align: center;
    color: #e0e0e0;
    font-size: 10px;
    max-height: 14px;
    min-height: 14px;
}

QProgressBar::chunk {
    background: #00d4ff;
    border-radius: 2px;
}

/* -- ScrollArea -------------------------------------------------- */

QScrollArea {
    border: none;
    background: transparent;
}

/* -- Splitter ---------------------------------------------------- */

QSplitter::handle {
    background: #333333;
    width: 1px;
    height: 1px;
}

/* -- TopBar ------------------------------------------------------ */

QFrame#TopBar {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #121212, stop:1 #1e1e1e);
    border-bottom: 1px solid #333333;
}

QLabel#LogoLabel {
    color: #00E5FF;
    font-weight: bold;
    font-size: 16px;
    background: transparent;
}

/* -- Side Panel -------------------------------------------------- */

#SidePanel {
    background: #1e1e1e;
    border-right: 1px solid #333333;
}

/* -- Status Labels ----------------------------------------------- */

QLabel#StatusOk      { color: #4caf50; }
QLabel#StatusWarning { color: #ff9800; }
QLabel#StatusError   { color: #f44336; }

/* -- Metric Cards ------------------------------------------------ */

QFrame[class="MetricCard"] {
    background: #1e1e1e;
    border: 1px solid #2d2d30;
    border-radius: 8px;
}

QFrame[class="MetricCard"]:hover {
    border-color: #0078d4;
    background: #222225;
}

/* -- Tooltip ----------------------------------------------------- */

QToolTip {
    background: #252525;
    color: #e0e0e0;
    border: 1px solid #00d4ff;
    padding: 4px 8px;
    font-size: 11px;
}
```

---

## 9. Bugs Conhecidos no Codigo Atual

| Arquivo | Widget | Bug | Impacto |
|---------|--------|-----|---------|
| `components/atoms.py` | `NavButton._get_style()` | String sem f-prefix: `{Colors.xxx}` nao interpola | Estilo incorreto |
| `components/atoms.py` | `SyncToggleButton._update_style()` | Idem -- QSS literal | Toggle sem cor correta |
| `components/atoms.py` | `AttachmentChip.__init__()` | Idem | Chip sem estilo |
| `components/atoms.py` | `AISuggestionBox.btn_action` | Idem | Botao sem hover |

Correcao: Adicionar `f` prefix a todas as strings QSS e duplicar `{` `}` para CSS braces.

---

## 10. Migracao e Adocao

### 10.1 Prioridade de Migracao

| Prioridade | Arquivo | Inline Styles | Status |
|------------|---------|---------------|--------|
| DONE | `modules/comparison_engine.py` | ~30 | Migrado para tokens |
| DONE | `modules/diagnostic_hub.py` | ~20 | Migrado para tokens |
| DONE | `main.py` | ~10 | Migrado para tokens |
| P1 | `widgets/detail_card.py` | ~60 | PENDENTE |
| P1 | `organisms/login_widget.py` | ~20 | PENDENTE |
| P1 | `organisms/user_profile_dialog.py` | ~25 | PENDENTE |
| P2 | `components/organisms.py` | ~15 | PENDENTE |
| P2 | `widgets/dashboard_components.py` | ~20 | PENDENTE |
| P2 | `widgets/central_controle.py` | ~15 | PENDENTE |
| P3 | `dialogs/robot_ficha_dialog.py` | ~10 | PENDENTE |
| P3 | `widgets/link_manager.py` | ~8 | PENDENTE |
| P3 | `widgets/training_log_dialog.py` | ~6 | PENDENTE |

Referencia completa de gaps: `docs/design-system-gaps.md`

### 10.2 Regras de Migracao

1. Ler `src/ui/theme.py` antes de tocar em qualquer arquivo UI
2. Substituir hex inline pelo token equivalente (consultar tabela em `design-system-gaps.md`)
3. Usar `StyleSheets.xxx()` para padroes repetidos (sidebar, button_primary, etc.)
4. Testar visualmente cada aba apos migracao -- nenhuma regressao visual permitida
5. Nao alterar comportamento -- apenas substituicao de estilo
6. Ao encontrar f-string bugs (falta de f-prefix), corrigir junto com a migracao

---

## 11. Referencia Rapida de Tokens

### Cores por Contexto de Uso

| Contexto | Token |
|----------|-------|
| Fundo da app | `BG_DEEP` |
| Fundo de painel / sidebar | `BG_PANEL` |
| Fundo de card / input | `BG_CARD` |
| Fundo de viewer DXF | `BG_DEEP` |
| Fundo de header de tabela | `BG_SURFACE` |
| Hover de item | `BG_HOVER` |
| Texto corpo | `TEXT_PRIMARY` |
| Label / metadata | `TEXT_SECONDARY` |
| Desabilitado | `TEXT_MUTED` |
| Texto sutil | `TEXT_DIM` |
| Texto maximo | `TEXT_BRIGHT` |
| Link / selecionado | `ACCENT_PRIMARY` |
| Logo / brand | `ACCENT_BRAND` |
| Botao acao | `ACCENT_BLUE` |
| Sucesso | `ACCENT_SUCCESS` |
| Aviso | `ACCENT_WARNING` |
| Erro | `ACCENT_DANGER` |
| Borda padrao | `BORDER_DEFAULT` |
| Borda focus / active | `BORDER_ACCENT` |
| Borda sutil / separator | `BORDER_SUBTLE` |
| Borda de input | `BORDER_INPUT` |

### Fontes por Contexto

| Contexto | Size Token | Weight |
|----------|------------|--------|
| Body / label | `SIZE_MD` | normal |
| Item de lista | `SIZE_SM` | normal |
| Sidebar tree | `SIZE_LG` | normal |
| Botao | `SIZE_MD` | bold |
| Titulo de secao | `SIZE_XL` | bold |
| Logo | `SIZE_TITLE` | bold |
| Score hero | `SIZE_HERO` | bold |
| Pipeline step | `SIZE_XS` | normal |
| Badge | `SIZE_SM` | bold |
| Input | `SIZE_XL` | normal |
| Terminal / codigo | `SIZE_SM` | normal + `FAMILY_MONO` |

### Referencias Visuais Validadas

| Modulo | O que exemplifica |
|--------|-------------------|
| **Comparison Engine** | Tabs coloridas N1/N2/N3, DXF viewer, TriColumn layout, PipelineSteps, ScoreLabel, NivelBadge |
| **Structural Analyzer** | Sidebar + canvas, botoes de acao, toolbar tools, terminal de eventos |
| **ProjectManager** | Cards de projeto, lista hierarquica, formularios, field buttons |

Ao criar novo modulo, olhar primeiro esses 3 como referencia antes de inventar padrao novo.

---

*TSF PROJETOS Design System v2.0 -- 2026-06-04*
*Fonte canonica para toda decisao visual. Desvios devem ser justificados e documentados.*
