# Contextualização: Aba Robo Pilares (main.py) vs Legacy pilares-atualizado-09-25

## 1. Aba do Robo Pilares no `Agente-cad-PYSIDE/main.py`

### 1.1 Carregamento e path

- **Path do módulo:** `_ROBOS_ABAS/Robo_Pilares/pilares-atualizado-09-25` é adicionado ao `sys.path` (linhas ~102–105).
- **Entry point:** `bootstrap.create_pilares_widget(db_manager=self.db)` (linhas ~107–111). Se falhar, `create_pilares_widget = None` e o Robo Pilares fica indisponível.

### 1.2 Posição na UI

- **`module_tabs`:** Aba **"Robo Pilares"** é o **índice 3** (após Diagnostic Hub, Structural Analyzer, Comparison Engine).
- **`module_stack`:** O widget do Robo Pilares é o 4º widget do stack; ao clicar na aba, `module_stack.setCurrentIndex(3)` exibe o Robo.

### 1.3 Instanciação (init)

```text
self.robo_pilares = create_pilares_widget(db_manager=self.db)
self.robo_pilares.setWindowFlags(Qt.Widget)  # embed mode
self.module_stack.addWidget(self.robo_pilares)
```

- O **`DatabaseManager`** (`self.db`) é repassado para sincronizar obras/projetos com o banco principal.

### 1.4 Integrações principais

| Integração | Onde | Descrição |
|------------|------|-----------|
| **Sincronização de contexto (Obra/Pavimento)** | `_sync_nav_to_robos` (~412–420) | Ao mudar obra/pavimento nos combos da top bar, chama `robo_pilares.add_global_obra(work_name)` ou `robo_pilares.add_global_pavimento(work_name, pavement_name)`. |
| **Sincronizar pilares → Robo** | `sync_pillars_to_robo_pilares_action` (~1536–1669) | Botão "🤖 Sincronizar Robo Pilares" na aba **Análise → Pilares**. Converte `pillars_found` em `PilarModel`, aplica `PilarService.distribute_face_heights` / `sync_pilar_heights`, chama `vm.sync_global_context`, substitui `current_pavimento.pilares` e muda para a aba do Robo (index 3). |
| **Sync obras legadas → DB** | `_sync_legacy_works` (~625–684) | Lê `robo_pilares.vm.obras_collection` (lista de `ObraModel`), cria obras/pavimentos no DB principal se não existirem. |
| **Geração de scripts** | `generate_script_pillar_full`, `generate_script_pavement_pillar` (~4800–4905) | Usam `robo_pilares.vm.automation_service` para `generate_full_paviment_orchestration` ou script do pavimento atual. |

### 1.5 API esperada do `robo_pilares`

- `add_global_obra(obra_name)`  
- `add_global_pavimento(obra_name, pav_name)`  
- `vm`: ViewModel com `sync_global_context`, `obras_collection`, `current_pavimento`, `selected_pilar`, `automation_service`, `notify_property_changed`.

---

## 2. Legacy: `pilares-atualizado-09-25`

### 2.1 `run.py` – script de inicialização

- **Função:** Ponto de entrada quando o Robo Pilares roda **standalone** (ex.: executável empacotado).
- **Path:** `_ROBOS_ABAS/Robo_Pilares/pilares-atualizado-09-25/run.py`

**Resumo do fluxo:**

1. **Silenciar saída (opcional):**  
   - Substitui `builtins.print` e `logging.Logger._log` por funções vazias, exceto se `PILARES_ENABLE_CONSOLE_DEBUG=1`.

2. **Frozen init:**  
   - Importa `src.utils.__frozen_init__.ensure_frozen_paths` (ou `utils.__frozen_init__` como fallback).  
   - Garante `sys.path` correto para Nuitka/PyInstaller (`.exe`, pastas `.dist` / `dist_nuitka`).

3. **`main()`:**  
   - Detecta ambiente frozen (`.exe`, diretórios `.dist` / `dist_nuitka`).  
   - Ajusta `script_dir` / `src_dir` e `sys.path`.  
   - Importa `src.main.main` (ou `main.main`) como `pilar_main` e executa.  
   - Se `pilar_main()` retornar `False`, chama `sys.exit(1)`.

**Importante:** No **Agente-cad**, o Robo Pilares **não** é iniciado via `run.py`. O main adiciona o path do `pilares-atualizado-09-25` e importa **apenas** `bootstrap.create_pilares_widget`. O `run.py` é usado só no executável standalone do PilarAnalyzer.

### 2.2 `bootstrap.py`

- **Path:** `pilares-atualizado-09-25/bootstrap.py`  
- Adiciona `src` ao `sys.path` e importa UI/serviços.

**`create_pilares_widget(db_manager=None)`:**

1. Instancia serviços: `CadIntegrationService`, `ExcelDataService`, `AutomationOrchestratorService(project_root)`, `LegacyDataService(legacy_path)` com `legacy_path = src/core`.
2. Cria `MainViewModel(..., db_manager=db_manager)`.
3. Cria `MainWindow(main_vm)` e retorna.

Ou seja, o widget embarcado no main é a **MainWindow** do Robo Pilares, que já usa o ViewModel e os serviços (incl. legacy e automação).

### 2.3 `src/main.py` (legacy)

- **Função:** Entrada **standalone** do PilarAnalyzer (invocada por `run.py`).
- Configura `__frozen_init__`, paths, encoding, etc., e em seguida dispara a aplicação (UI) do PilarAnalyzer.  
- No fluxo **Agente-cad**, o `main.py` do Agente-cad **não** chama `src.main` do Pilares; apenas usa o widget criado pelo `bootstrap`.

### 2.4 UI e ViewModel

- **`MainWindow`** (`ui/main_window.py`):  
  - Recebe `MainViewModel`, monta layout com `PilarListPanel` e `PilarDetailsForm`.  
  - Expõe `add_global_obra` e `add_global_pavimento`, que delegam para `vm.sync_global_context`.

- **`MainViewModel`** (`ui/viewmodels/main_viewmodel.py`):  
  - Mantém `obras_collection` (lista de `ObraModel`), `current_obra`, `current_pavimento`, `selected_pilar`.  
  - `load_legacy_data()` preenche `obras_collection` via `LegacyDataService`.  
  - `sync_global_context(obra_name, pav_name?)` busca/cria obra e pavimento, opcionalmente sincroniza estrutura com `db_manager.get_projects()`, e atualiza estado + notificações.

### 2.5 `src/utils` (legacy)

| Arquivo | Função resumida |
|---------|------------------|
| **`__frozen_init__.py`** | `ensure_frozen_paths()`: detecta frozen (Nuitka/PyInstaller), configura `sys.path` (exe, `src`, parent). Usado por `run.py` e `src.main`. |
| **`funcoes_auxiliares.py`** | Cálculo de aberturas em pares de linhas (`calcular_aberturas_em_pares`), filtros de linhas, classificação esquerda/direita, etc. |
| **`funcoes_auxiliares_2..6`** | Extensões/variantes de funções auxiliares (incl. estruturas tipo `obras` em alguns). |
| **`autocad_wrapper.py`** | `AutoCADWrapper`: COM (`win32com`), conexão com AutoCAD, seleção, processamento de retângulos/linhas/textos, cálculos geométricos. |
| **`grade_calculator.py`** | `GradeCalculator`: cálculo de parafusos e grades (ex.: `calcular_parafusos`, `calcular_grades`), alinhado com lógica legada (ex. `funcoes_auxiliares_5`). |
| **`calculadora_grades_especiais.py`** | Cálculos específicos de grades. |
| **`excel_mapping.py`** | Mapeamento para Excel. |
| **`autocad_ui_utils.py`** | Utilitários de UI para AutoCAD. |
| **`debug_logger.py`** | Logging de debug. |
| **`robust_path_resolver.py`** | Resolução de paths em ambientes frozen/dev. |

Os **robots** (`src/robots/`) e **services** (`geometry_service`, `legacy_service`, `pilar_service`, etc.) usam ou complementam esses utils.

---

## 3. Resumo de relações

```
main.py (Agente-cad)
├── sys.path += pilares-atualizado-09-25
├── from bootstrap import create_pilares_widget
├── robo_pilares = create_pilares_widget(db_manager=self.db)
├── module_tabs[3] = "Robo Pilares", module_stack[3] = robo_pilares
├── _sync_nav_to_robos → add_global_obra / add_global_pavimento
├── sync_pillars_to_robo_pilares_action → vm.sync_global_context + pavimento.pilares
├── _sync_legacy_works → vm.obras_collection → DB
└── generate_script_* → vm.automation_service

pilares-atualizado-09-25/
├── run.py          → standalone only; frozen init; chama src.main
├── bootstrap.py    → create_pilares_widget (MainWindow + MainViewModel + services)
├── src/
│   ├── main.py     → standalone app entry (não usado pelo Agente-cad)
│   ├── ui/         → MainWindow, MainViewModel, panels, forms
│   ├── services/   → cad, excel, automation, legacy, pilar
│   ├── models/     → ObraModel, PavimentoModel, PilarModel
│   ├── robots/     → robôs ABCD, CIMA, GRADES, etc.
│   └── utils/      → __frozen_init__, funcoes_auxiliares*, autocad_wrapper,
│                     grade_calculator, excel_mapping, ...
```

---

## 4. Geração de Scripts: Comparação Detalhada entre Interfaces

### 4.1 Fluxo de Geração no `main.py` (Agente-cad)

**Entry Points:**
- `generate_script_pillar_full()` (linha ~4800): Gera scripts para **todos os pavimentos** de uma obra
- `generate_script_pavement_pillar()` (linha ~4853): Gera scripts para o **pavimento atual**

**Fluxo de Execução:**
```
main.py → robo_pilares.vm.automation_service → AutomationOrchestratorService
  ↓
generate_full_paviment_orchestration(pavimento, obra)
  ↓
├── generate_scripts_cima() → CIMA_FUNCIONAL_EXCEL.preencher_campos_diretamente_e_gerar_scripts()
├── generate_abcd_script() → Abcd_Excel.preencher_campos_diretamente_e_gerar_scripts()
└── generate_grades_script() → GRADE_EXCEL.preencher_campos_diretamente_e_gerar_scripts()
  ↓
Cada gerador:
  1. Converte PilarModel → dict (via _pilar_model_to_legacy_dict)
  2. Chama função legacy preencher_campos_diretamente_e_gerar_scripts(dados_pilar)
  3. Salva scripts individuais em SCRIPTS_ROBOS/{pavimento}_{TIPO}/
  4. Executa combinador (Combinador_de_SCR_*.py)
  5. Script final em SCRIPTS_ROBOS/{pavimento}_{TIPO}/Combinados/*.scr
```

**Diretório de Saída:**
- Base: `{project_root}/SCRIPTS_ROBOS/`
- Estrutura: `{pavimento_safe_name}_{TIPO}/Combinados/{arquivo}.scr`
- Exemplo: `SCRIPTS_ROBOS/Pavimento_1_CIMA/Combinados/Pavimento_1_CIMA.scr`

### 4.2 Fluxo de Geração na Interface Standalone (PilarAnalyzer)

**Entry Points:**
- `Painel_de_Controle.pipeline_automatizado(tipo)` (linha ~1370)
- `funcoes_auxiliares_6.executar_todos_*_excel()` (CIMA, ABCD, GRADES)

**Fluxo de Execução:**
```
PilarAnalyzer (standalone)
  ↓
Painel_de_Controle.pipeline_automatizado('CIMA'|'ABCD'|'GRADES')
  ↓
executar_todos_{tipo}_excel()
  ↓
Para cada pilar:
  Conector_Interface_PainelControle → Excel temporário
  ↓
CIMA_FUNCIONAL_EXCEL.preencher_campos_e_gerar_scripts() OU
Abcd_Excel.preencher_campos_e_gerar_scripts() OU
GRADE_EXCEL.preencher_campos_diretamente_e_gerar_scripts()
  ↓
Salva em output/{pavimento}_{TIPO}/
  ↓
Combinador_de_SCR_*.processar_arquivos()
  ↓
Script final em output/{pavimento}_{TIPO}/Combinados/*.scr
```

**Diretório de Saída:**
- Base: `{project_root}/output/`
- Estrutura: `{pavimento}_{TIPO}/Combinados/{arquivo}.scr`
- Exemplo: `output/Pavimento_1_CIMA/Combinados/Pavimento_1_CIMA.scr`

### 4.3 Diferenças Críticas entre Interfaces

| Aspecto | main.py (Agente-cad) | Standalone (PilarAnalyzer) |
|--------|----------------------|---------------------------|
| **Diretório Base** | `SCRIPTS_ROBOS/` | `output/` |
| **Conversão de Dados** | `AutomationOrchestratorService._pilar_model_to_legacy_dict()` | `Conector_Interface_PainelControle` → Excel temporário |
| **Geradores CIMA/ABCD** | `preencher_campos_diretamente_e_gerar_scripts(dict)` | `preencher_campos_e_gerar_scripts(excel_path)` OU `preencher_campos_diretamente_e_gerar_scripts(dict)` |
| **Gerador GRADES** | `preencher_campos_diretamente_e_gerar_scripts(dict)` | `preencher_campos_diretamente_e_gerar_scripts(dict)` |
| **Encoding de Saída** | UTF-16 LE (BOM) via geradores legacy | UTF-16 LE (BOM) via geradores legacy |
| **Combinadores** | Mesmos módulos (`Combinador_de_SCR_*.py`) | Mesmos módulos (`Combinador_de_SCR_*.py`) |
| **Validação de Créditos** | **BYPASSADO** (modo desenvolvimento) | Ativo (pode bloquear) |

### 4.4 Mapeamento de Dados: PilarModel → Legacy Dict

O `AutomationOrchestratorService._pilar_model_to_legacy_dict()` (linha ~224) mapeia:

**Campos Básicos:**
- `nome`, `comprimento`, `largura`, `altura`
- `nivel_chegada`, `nivel_saida`, `nivel_diferencial`
- `pavimento`, `pavimento_anterior`

**Parafusos (par_1_2 até par_8_9):**
```python
'parafuso_p1_p2': int(pilar.par_1_2 or 0),
'parafuso_p2_p3': int(pilar.par_2_3 or 0),
# ... até par_8_9
```

**Faces A-H:**
- Lajes: `laje_{face}`, `posicao_laje_{face}`
- Dimensões: `larg1_{face}`, `larg2_{face}`, `larg3_{face}`
- Alturas: `h1_{face}` até `h5_{face}`
- Hachuras: `hachura_l{l}_h{i}_{face}` (L1-L3, H2-H5)
- Aberturas (A, B): `distancia_{side}_{k}_{face}`, `largura_{side}_{k}_{face}`, etc.

**Pilares Especiais:**
- `pilar_especial_ativo`, `tipo_pilar_especial`
- `comp_1`, `comp_2`, `comp_3`, `larg_1`, `larg_2`, `larg_3`
- `distancia_pilar_especial`

**Grades:**
- Grupo 1: `grade_1`, `distancia_1`, `grade_2`, `distancia_2`, `grade_3`
- Grupo 2: `grade_1_grupo2`, `distancia_1_grupo2`, etc.
- Grades especiais por face (A, B, E, F, G, H): `grade_{face}_{i}`, `dist_{face}_{i}`
- Detalhes: `detalhe_{face}_{g}_{d}`, `altura_detalhe_{face}_{g}_{h}`

### 4.5 Pontos de Falha Potenciais

#### 4.5.1 Diferenças de Caminho
- **main.py**: Usa `SCRIPTS_ROBOS/` (definido em `AutomationOrchestratorService.__init__`)
- **Standalone**: Usa `output/` (definido em `robust_path_resolver.get_project_root()`)
- **Risco**: Scripts podem ser salvos em locais diferentes, causando confusão

#### 4.5.2 Diferenças de Conversão de Dados
- **main.py**: Conversão direta `PilarModel` → `dict` via `_pilar_model_to_legacy_dict()`
- **Standalone**: Pode usar Excel intermediário (`Conector_Interface_PainelControle`)
- **Risco**: Campos podem ser mapeados incorretamente ou perdidos na conversão

#### 4.5.3 Encoding e Formatação
- Ambos devem usar UTF-16 LE com BOM (`\xFF\xFE`)
- **Risco**: Se encoding for diferente, scripts podem estar corrompidos no AutoCAD

#### 4.5.4 Combinadores
- Ambos usam os mesmos módulos, mas podem ter versões diferentes
- **Risco**: Ordem de combinação ou formatação final pode diferir

### 4.6 Validação e Testes

**Script de Teste Comparativo:** `_ROBOS_ABAS/Robo_Pilares/test_script_comparison.py`

**Validações Implementadas:**
1. **Comparação de Estrutura**: Verifica se ambos geram os mesmos arquivos
2. **Comparação de Conteúdo**: Diff linha por linha dos scripts finais
3. **Validação de Encoding**: Verifica UTF-16 LE com BOM
4. **Validação de Comandos AutoCAD**: Verifica sintaxe básica dos comandos
5. **Comparação de Tamanho**: Detecta scripts incompletos

**Como Executar:**
```bash
cd _ROBOS_ABAS/Robo_Pilares
python test_script_comparison.py --obra "NomeObra" --pavimento "NomePavimento"
```

### 4.7 Sistema de Créditos

**Modo Desenvolvimento (BYPASS):**
- No `bootstrap.py`, o sistema pode ser inicializado em modo offline/desenvolvimento
- Créditos são **bypassados** quando `modo_offline = True` ou variável de ambiente `PILARES_DEV_MODE=1`
- Ver `credit_system.py` linha ~534: `self.modo_offline = (user_id == "offline" and api_key == "offline_mode")`

**Para Desabilitar Bloqueios:**
1. Definir variável de ambiente: `PILARES_DEV_MODE=1`
2. Ou modificar `bootstrap.py` para criar `CreditManager("offline", "offline_mode")`
3. Ou modificar `funcoes_auxiliares_6._verificar_modo_offline()` para sempre retornar `False` (não bloqueia)

---

## 5. Checklist para alterações

- Ao mudar a **aba** ou o **stack** no main: os índices do Robo Pilares são **3** em `module_tabs` e `module_stack`.  
- Ao trocar **API** do Robo (`add_global_*`, `vm`): manter compatibilidade com `_sync_nav_to_robos`, `sync_pillars_to_robo_pilares_action`, `_sync_legacy_works` e `generate_script_*`.  
- **`run.py`** é só para standalone; o Agente-cad não o executa.  
- **`src/utils`**: são dependências do legacy (robots, services, UI); mudanças ali afetam o Robo Pilares tanto standalone quanto embarcado.
- **Geração de Scripts**: Sempre validar que ambos os caminhos (main.py e standalone) geram scripts idênticos usando `test_script_comparison.py`
- **Diretórios**: Verificar se `SCRIPTS_ROBOS/` (main.py) e `output/` (standalone) estão sincronizados
