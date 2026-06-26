# Plano de Refatoração: Migração Tkinter para PySide6 (Robô Pilares)

Este documento detalha o mapeamento da interface legado (Tkinter) e o plano de migração para **PySide6**, focando em uma arquitetura modular, estética premium e performance otimizada.

## 1. Visão Geral da Estrutura Legada
O código atual reside principalmente em `src/utils/funcoes_auxiliares_2.py`, dentro da classe `PilarAnalyzer`. A interface é construída em um único método massivo e as lógicas de cálculo estão misturadas com a criação de widgets.

### Localização das Abas Principais:
- **Dados Gerais**: Linha 7704 - Gerencia o pilar principal, grades e régua visual.
- **Abas Individuais (A-H)**: Linha 10933 (`criar_aba_painel`) - Gerencia dimensões de laje, alturas h1-h5 (com hachura) e aberturas.
- **Pilares Especiais**: Linha 32216 - Gerencia cálculos avançados para pilares em L, T e U.

---

## 2. Mapeamento de Componentes e Estilos

### Temas e Estilos (Migration target: QSS)
| Elemento Tkinter | Estilo Legado | Proposta PySide6 (Premium) |
| :--- | :--- | :--- |
| `ttk.LabelFrame` | Padrão cinza | `QGroupBox` com bordas arredondadas e gradientes sutis |
| `ttk.Button` | Padrão OS | `QPushButton` com hover effects, ícones SVG e sombras |
| `tk.Canvas` (Régua) | `RulerWidget` | `RulerWidget(QWidget)` usando `QPainter` para renderização vetorial |
| `tk.Entry` | Branco simples | `QLineEdit` com foco animado e validação em tempo real |

---

## 3. Detalhamento das Abas

### Aba: Dados Gerais
**Campos e Funcionalidades:**
- **Identificação**: Número (Pilar), Nome, Pavimento (Combobox), Pav. Anterior.
- **Geometria**: Comprimento, Largura, Nível Chegada/Saída, Nível Diferencial, Altura.
- **Controles**: Botões "Novo", "Selecionar no CAD", "Próximo Número".
- **Lógica de Grades**: 3 Grades (Conjunto 1) com resolução de conflitos via botões `⚡G1`, `⚡G2`, `⚡G3`.
- **Régua Visual**: `RulerWidget` integrada com detecção de colisão entre detalhes (Azul) e parafusos (Vermelho).

### Aba: Painéis (A-H)
**Campos por Painel:**
- **Laje**: Campo de valor e posição da laje.
- **Dimensões**: Larguras (1-3) e Alturas (h1-h5).
- **Hachura**: Seleção de hachura (0, 1, 2) para h2-h5 via RadioButtons.
- **Aberturas**: Matriz de aberturas (Esquerda/Direita) com Distância, Boca, Profundidade e Rebaixo.
- **Locks**: `[SEGURANCA]` checkboxes para travar campos.

### Aba: Pilares Especiais
- **Modos**: NOVA (PLINE) e INI.
- **Tipos**: L, T, U.
- **Cálculo Automático**: Sincronização em tempo real via FocusOut nos campos de dimensão.

---

## 4. Plano de Implementação PySide6

### Fase 1: Base e Estilização (`src/view/styles.qss`)
- Criar um sistema de cores dinâmico (Dark Mode por padrão ou suporte a temas).
- Implementar `CustomWidgets` (RoundButtons, StyledInputs).

### Fase 2: Componente `RulerWidget`
- Reescrever o Canvas do Tkinter usando `QPainter`.
- Adicionar antialiasing e interatividade suave para arrastar ponteiros.

### Fase 3: Estrutura de Abas (`src/view/main_window.py`)
- Modularizar cada aba em uma classe separada (`GeneralDataTab`, `PanelTab`, `SpecialPillarsTab`).
- Utilizar `QStackedWidget` ou `QTabWidget` customizado.

### Fase 4: Engine de Cálculo e Sincronização
- Separar a lógica de cálculo (Business Logic) da UI (View).
- Usar `Signals/Slots` para comunicação entre componentes (ex: ao mudar modo na aba Especial, atualizar Dados Gerais).

---

## 5. Recomendações Críticas de Melhoria
1. **Performance**: O arquivo atual tem 46k linhas. A refatoração DEVE dividir isso em pelo menos 10 sub-arquivos.
2. **Validação**: Implementar `QValidator` nos campos numéricos para evitar erros de cast (`float`).
3. **UX**: Adicionar previews 2D reais dos pilares especiais (L, T, U) conforme o usuário digita.
4. **Auto-Save**: Manter e otimizar a lógica de salvamento automático que já existe no legado.
