# Contextualização: Aba Laterais de Viga (main.py) ↔ Robo_Laterais_de_Vigas

## 1. Aba do Robo Laterais de Viga no `Agente-cad-PYSIDE/main.py`

### 1.1 Carregamento e path

- **Path do módulo:** `_ROBOS_ABAS/Robo_Laterais_de_Vigas` é adicionado ao `sys.path` (linhas ~15–17).
- **Entry point:** `from robo_laterais_viga_pyside import VigaMainWindow`. Se falhar, `VigaMainWindow = None` e o Robo Laterais fica indisponível.
- O Robo Laterais é o **primeiro** robô cujo path é configurado no `main.py` (antes de Lajes, Fundos e Pilares).

### 1.2 Posição na UI

- **`module_tabs`:** Aba **"Robo Laterais de Viga"** é o **índice 4** (após Diagnostic Hub, Structural Analyzer, Comparison Engine, Robo Pilares).
- **`module_stack`:** O widget do Robo Laterais é o 5º widget do stack; ao clicar na aba, `module_stack.setCurrentIndex(4)` exibe o Robo.

### 1.3 Instanciação (init)

```text
self.robo_viga = VigaMainWindow()
self.robo_viga.licensing_service = self.licensing_proxy
self.robo_viga.setWindowFlags(Qt.Widget)  # embed mode
self.module_stack.addWidget(self.robo_viga)
```

- O **`LicensingProxy`** do main é atribuído a `robo_viga.licensing_service`. O Robo Laterais usa esse proxy para `user_data`, `consume_credits`, etc., quando integrado ao dashboard.

### 1.4 Integrações principais

| Integração | Onde | Descrição |
|------------|------|-----------|
| **Sincronização de contexto (Obra/Pavimento)** | `sync_robots_with_master_context` (~388–425) | Ao mudar obra/pavimento nos combos da top bar (ou ao criar projeto), chama `robo_viga.add_global_obra(work_name)` ou `robo_viga.add_global_pavimento(work_name, pavement_name)`. |
| **Sincronizar vigas → Robo Laterais** | `sync_beams_to_laterais_action` (~1433–1482) | Botão **"🤖 Sincronizar Laterais de Vigas"** na aba **Análise → Vigas**. Exige Obra e Pavimento; chama `add_global_pavimento`, monta `viga_list` a partir de `beams_found` (nome, `id_item`/número, `parent_name`), ordena naturalmente e chama `robo_viga.add_viga_bulk(viga_list)`. |
| **Geração de script conjunto** | `generate_script_beam_set` (~4909–4936) | Usa `robo_viga.generate_conjunto_scripts()` (por classe/conjunto) e `_create_laz_command_files`. Requer obra selecionada. |
| **Geração de script pavimento** | `generate_script_pavement_beam` (~4938–4972) | Usa `robo_viga.add_global_pavimento` + `robo_viga.generate_pavimento_scripts()`. Requer obra e pavimento. |

**Observação:** Não há sincronização reversa (Robo Laterais → DB principal) como no Robo Pilares. O `_sync_legacy_works` atua apenas sobre `robo_pilares`.

### 1.5 Quando o contexto é propagado ao Robo Laterais

- `switch_to_tab` → `sync_robots_with_master_context(self.current_work_name)` (só obra).
- `on_global_project_created` → `sync_robots_with_master_context(work_name, project_name, project_id)`.
- `_on_work_changed` (combo Obra) → `sync_robots_with_master_context(work_name)`.
- `_on_pavement_changed` (combo Pavimento) → `sync_robots_with_master_context(work_name, project_name)`.
- Criação de projeto via gerenciador → `sync_robots_with_master_context(work_name, pavement_name)`.

### 1.6 API esperada do `robo_viga` (VigaMainWindow)

- `add_global_obra(obra_name)`
- `add_global_pavimento(obra_name, pav_name)`
- `add_viga_bulk(viga_list)` → `{'added': int, 'skipped': int}` ou legado `int`
- `generate_conjunto_scripts()` — gera por classe/conjunto (ex.: "Lista Geral").
- `generate_pavimento_scripts()` — gera para todas as vigas do pavimento atual.
- `licensing_service` — atribuído pelo main (`LicensingProxy`).

---

## 2. Robo_Laterais_de_Vigas (`robo_laterais_viga_pyside`)

### 2.1 Estrutura principal

- **Classe:** `VigaMainWindow` (PySide6).
- **Modelo:** `VigaState` (dataclass), `PanelData`, `HoleData`, `PillarDetail`.
- **Dados:** `project_data[obra][pavimento]` → `{ 'vigas': { nome: VigaState }, 'metadata': {...} }`.
- **Persistência:** `dados_vigas_ultima_sessao.json` (estrutura compatível com `project_data`).

### 2.2 `add_global_obra` / `add_global_pavimento`

- **`add_global_obra(obra_name)`:** Cria obra em `project_data` se não existir, atualiza `cmb_obra`, `current_obra`, `update_pavimento_combo`, `save_session_data`.
- **`add_global_pavimento(obra_name, pav_name)`:** Garante obra (via `add_global_obra` se preciso), cria pavimento com `vigas: {}` e `metadata`, seleciona obra e pavimento nos combos, chama `on_pav_changed`, `save_session_data`.

### 2.3 `add_viga_bulk(viga_list)`

- Cada item: `{ 'name', 'number' (opcional), 'parent_name' (classe, ex. "Lista Geral") }`.
- Se `name` não existe em `vigas` do pavimento atual, cria `VigaState` com `number`, `name`, `floor`, `segment_class = parent_name`.
- Retorna `{'added': count, 'skipped': skipped}`.
- Atualiza lista de vigas e persiste sessão.

### 2.4 Geração de scripts

- **`generate_pavimento_scripts`:** Gera scripts para todas as vigas do pavimento atual (`_generate_bulk_scripts`).
- **`generate_conjunto_scripts`:** Filtra vigas pela classe/conjunto (`cmb_classes.currentText()`), gera em pasta `{pav}_{current_class}`.
- Saída em `SCRIPTS_ROBOS` na raiz do projeto. Usa `GeradorScriptViga` (`gerador_script_viga`) e `gerador_script_combinados` para combinados.
- Verificação de licença via `licensing_service` (área m² do lote); em modo offline ou falha de débito, pergunta se deseja gerar gratuitamente.

### 2.5 Config e templates

- **Config:** `config.json` em `Robo_Laterais_de_Vigas/config.json`. Contém `layers`, `comandos`, `opcoes`, `numeracao_blocos`. **Não** contém templates.
- **Templates:** Fonte única **`_ROBOS_ABAS/config/templates_laterais_vigas.json`**. Exibidos na aba **Templates** (Configurações → toolbar). Carregar: `_carregar_templates()`; salvar: `_salvar_templates()` ao adicionar/excluir template. O arquivo pode ter também `layers`/`comandos`/`opcoes` no topo; ao salvar, só a chave `templates` é atualizada.
- **EXE:** Em frozen, `templates_file` = `{exe_dir}/config/templates_laterais_vigas.json`. Coloque aí uma cópia se rodar standalone.

### 2.6 Outros pontos

- **Layers:** Ex.: `textos_laterais` (configurável). Usado em `gerador_script_viga` / `gerador_script_combinados`.
- **Integração AutoCAD:** `win32com` / `pythoncom` (opcional). Seleção de entidades, etc.
- **Build:** `build_secure.py`, `compile_with_pyinstaller.py`; módulo pode rodar **standalone** ou **embarcado** no Agente-cad.

---

## 3. Resumo do fluxo Vigas (Análise) → Laterais de Viga

1. Usuário seleciona **Obra** e **Pavimento** na top bar → `sync_robots_with_master_context` atualiza o Robo Laterais.
2. Structural Analyzer encontra vigas → `beams_found` (com `name`, `id_item`, `parent_name`, etc.).
3. Usuário vai em **Análise → Vigas** e clica **"🤖 Sincronizar Laterais de Vigas"**.
4. `sync_beams_to_laterais_action` chama `add_global_pavimento` (reforça contexto), monta `viga_list` a partir de `beams_found`, chama `add_viga_bulk`.
5. Robo Laterais cria/atualiza vigas no pavimento, persiste em `dados_vigas_ultima_sessao.json`.
6. Usuário pode ir na aba **Robo Laterais de Viga**, editar vigas, e usar **Gerar Pavimento** / **Gerar Conjunto** (ou os atalhos do main que delegam a `generate_pavimento_scripts` / `generate_conjunto_scripts`).

---

## 4. Referências rápidas

- **main.py:** linhas 15–25 (import), 400–408 (sync), 1100–1103 (botão), 1433–1482 (sync action), 1709 / 1754–1765 (tab + stack), 4909–4972 (scripts).
- **robo_laterais_viga_pyside.py:** `VigaMainWindow`, `VigaState`, `add_global_obra` (~7766), `add_global_pavimento` (~7780), `add_viga_bulk` (~7811), `generate_pavimento_scripts` (~5005), `generate_conjunto_scripts` (~5019), `_generate_bulk_scripts` (~5054).
