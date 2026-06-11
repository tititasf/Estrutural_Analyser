---
id: CAD-10.3
title: "Upgrade 'Analise Geral' button"
epic: CAD-10
status: Draft
executor: "@dev"
quality_gate: "@qa"
quality_gate_tools: [integration_test, ui_test, code_review]
effort: 5
priority: HIGH
dependencies: [CAD-10.2]
---

# CAD-10.3: Upgrade "Analise Geral" button

## Description

Atualizar o botao "Analise Geral" na UI principal para oferecer duas opcoes: (1) rodar o pipeline completo (`pipeline_e2e.py`) seguido de import Fase-4, ou (2) importar dados Fase-4 existentes sem reprocessar. Adicionar progress bar com fases reais e opcao de cancelamento.

## Problem / Need

Atualmente, o botao "Analise Geral" chama apenas `engenharia_reversa_dxf.py` e importa dados superficiais. O usuario precisa rodar o pipeline completo manualmente via CLI e depois nao tem como trazer esses dados para a UI. Nao existe progress feedback durante o processamento.

## Scope

### IN Scope
- Detectar se Fase-4 ja existe para a obra/pavimento selecionado
- Dialog de opcao: "Usar interpretacao existente" vs "Re-processar tudo"
- Execucao do `pipeline_e2e.py` via QProcess (nao-bloqueante)
- Progress bar com fases reais: Fase-3 -> Fase-4 -> Import -> Done
- Chamada a `_import_fase4_to_db()` de CAD-10.2 apos pipeline
- Cancelamento do pipeline em andamento
- Toast/notification de conclusao com resumo

### OUT of Scope
- Modificacoes no `pipeline_e2e.py` (ler output via stdout/stderr)
- Comparison panel (CAD-10.4)
- Alteracoes no layout do DetailCard

## Acceptance Criteria

### AC1: Deteccao de Fase-4 existente
**Given** usuario seleciona obra "Obra_TREINO_21" e pavimento "12 PAV"
**And** `Fase-4_Sincronizacao/JSON_Pilares/` contem arquivos P*.json
**When** usuario clica "Analise Geral"
**Then** dialog aparece com opcoes:
- "Importar interpretacao existente (Fase-4 de {data})" — com timestamp do ultimo JSON
- "Re-processar pipeline completo"
- "Cancelar"

### AC2: Importacao rapida (Fase-4 existente)
**Given** usuario escolhe "Importar interpretacao existente"
**When** processo executa
**Then** `_import_fase4_to_db()` e chamado diretamente (sem rodar pipeline)
**And** progress bar mostra: "Importando Fase-4... (X/Y itens)"
**And** conclusao em < 5 segundos para obra tipica
**And** toast mostra: "Importacao completa: {N} pilares, {M} vigas, {K} lajes"

### AC3: Pipeline completo com progress
**Given** usuario escolhe "Re-processar pipeline completo"
**When** pipeline_e2e.py e executado via QProcess
**Then** progress bar mostra fases em tempo real:
- "Fase 2: Engenharia Reversa..." (baseado em parsing do stdout)
- "Fase 4: Motor Fase 4..."
- "Fase 5: Geracao DXF..."
- etc.
**And** stdout do pipeline e exibido em log compacto (scrollable)
**And** apos pipeline concluir, `_import_fase4_to_db()` e chamado automaticamente
**And** toast final mostra status e score

### AC4: Cancelamento do pipeline
**Given** pipeline esta rodando
**When** usuario clica "Cancelar"
**Then** QProcess e terminado (kill)
**And** progress bar reseta
**And** mensagem: "Pipeline cancelado. Dados parciais podem existir."
**And** DB nao e corrompido (import so acontece apos pipeline completo)

### AC5: Sem Fase-4 existente
**Given** usuario seleciona obra sem Fase-4 processada
**When** clica "Analise Geral"
**Then** dialog mostra apenas: "Processar pipeline completo" e "Cancelar"
**And** opcao "Importar existente" nao aparece

### AC6: Erro no pipeline
**Given** pipeline_e2e.py falha em alguma fase
**When** QProcess retorna codigo != 0
**Then** progress bar mostra vermelho
**And** mensagem de erro com a fase que falhou
**And** log completo acessivel para diagnostico
**And** import Fase-4 NAO e executado

### AC7: Refresh do DetailCard apos import
**Given** import completou com sucesso
**When** usuario abre DetailCard de qualquer item
**Then** campos auto-populados aparecem com valores do Fase-4
**And** campos aparecem com estilo visual distinto (ex: cor azul claro) indicando "auto-importado"
**And** campos previamente validados manualmente mantêm estilo verde

## Technical Notes

### QProcess Integration Pattern

```python
self._process = QProcess(self)
self._process.setProcessChannelMode(QProcess.MergedChannels)
self._process.readyReadStandardOutput.connect(self._on_pipeline_output)
self._process.finished.connect(self._on_pipeline_finished)

args = [str(SCRIPTS_DIR / "pipeline_e2e.py"),
        "--obra", str(obra_path),
        "--pavimento", pavimento]
self._process.start(sys.executable, args)
```

Este pattern ja existe em `comparison_engine.py` (Fase8Panel._on_validate_clicked). Reutilizar.

### Phase Detection from stdout

O `pipeline_e2e.py` ja imprime `[FASE N]` em cada fase. Parsear com regex:
```python
match = re.match(r'\[FASE (\d+)\] (.+)', line)
if match:
    fase_num, fase_desc = match.groups()
    self.progress_bar.setFormat(f"Fase {fase_num}: {fase_desc}")
```

## File List

| File | Action | Description |
|------|--------|-------------|
| `src/ui/modules/analise_geral.py` | MODIFY | Upgrade button logic |
| `src/ui/dialogs/pipeline_dialog.py` | CREATE | Dialog for option selection |
| `main.py` | MODIFY | Wire new dialog to button |

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-05-18 | @pm | Story created |
