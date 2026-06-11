# Análise de Gaps de Testes — Vision-Estrutural AI

**Data:** 2026-05-17  
**Baseline:** 28 PASS | 0 FAIL (test_humano_autonomo.py)  
**Escopo:** Validação E2E via pywinauto (UIA) + análise funcional

---

## Estado Atual — 28 Checks Cobertos

```
[01] app_start           — Aplicação inicia sem crash
[02] login               — Login com credenciais válidas
[03] project_open        — Projeto "TREINO" abre
[04] tab1_canvas         — Canvas exibe entidades DXF (lines>0)
[05] tab1_canvas_count   — lines=1911, polys=173 (contagem real)
[06] tab1_sidebar        — Sidebar lista pavimentos
[07] tab1_pav_select     — Pavimento selecionável via UIA
[08] tab2_open           — Tab "Comparison Engine" abre
[09] tab2_checkboxes     — ['PL','LV','FV','LJ'] presentes
[10] tab2_validar        — Botão "▶ Validar" existe e está habilitado
[11] tab2_validar_run    — Validação executa em ~9s sem crash
[12] tab2_certificar     — Botão "✅ Certificar Obra" existe
[13] tab2_certificar_run — Certificação gera CERTIFICADO.json
[14] robo_PL_dxf         — Robô Pilares: score_label='OK'
[15] robo_LV_dxf         — Robô Laterais de Viga: score_label='OK'
[16] robo_FV_dxf         — Robô Fundo de Vigas: score_label='OK'
[17] robo_LJ_dxf         — Robô Laje: score_label='OK'
[18-28]                  — Checks estruturais de navegação e persistência
```

---

## Gaps Identificados (Prioridade Alta → Baixa)

### GAP-01 — Geração Real de DXF pelos Robôs (P0)

**Problema:** Os robôs reportam `score_label='OK'` mas nenhum novo DXF é gerado  
durante o teste. O `cmb_obra` (combo de seleção de obra) não é acessível via UIA  
no contexto dos robôs — o teste usa o DXF existente de runs anteriores.

**Impacto:** O teste valida o estado dos robôs, mas não a geração de saída real.  
Uma regressão no pipeline de geração passaria despercebida.

**Fix sugerido:**
1. Adicionar seleção de obra via teclado (`win.type_keys('{DOWN}')`) como fallback ao UIA combobox
2. Verificar timestamp dos DXF gerados: `assert os.path.getmtime(dxf_path) > test_start_time`
3. Validar que o DXF tem > 0 entidades após geração: `python -c "from ezdxf import readfile; ..."`

---

### GAP-02 — Fase-3 (Interpretação DXF) Não Testada (P0)

**Problema:** O botão "▶ Interpretar DXF" (Fase-3) existe mas não é clicado nos testes.  
Não há cobertura de:
- Execução do `engenharia_reversa_dxf.py`
- Criação dos arquivos `Fase-3_Interpretacao_Extracao/`
- Dados JSON de saída da interpretação

**Fix sugerido:**
```python
# Após selecionar pavimento:
btn_interpretar = win.child_window(title_re='.*Interpretar DXF.*', control_type='Button')
btn_interpretar.click()
time.sleep(15)  # Fase-3 é pesada
fase3_dir = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS/TREINO/Fase-3_Interpretacao_Extracao")
assert fase3_dir.exists(), "Fase-3 não gerou output"
```

---

### GAP-03 — Pipeline E2E Não Testado (P1)

**Problema:** O botão "▶▶ Pipeline Completo (F1→F8)" não é exercitado.  
O pipeline orquestra: Fase-1 → Fase-3 → Fase-4 → Fase-8 em sequência.  
Uma falha silenciosa no encadeamento passaria sem detecção.

**Fix sugerido:** Teste de smoke do pipeline com timeout de 120s e validação dos  
outputs em cada fase.

---

### GAP-04 — Validação de Canvas Após Mudança de Pavimento (P1)

**Problema:** O teste seleciona um pavimento mas não verifica se o canvas **atualiza**  
com as entidades do novo pavimento. O `[CANVAS]` log é impresso só na primeira carga.

**Fix sugerido:**
```python
# Monitorar stdout para novo log de canvas após troca de pavimento
# Verificar que as contagens mudam (diferente pavimento = diferente geometria)
```

---

### GAP-05 — Modo de Renderização (RenderMode) Não Testado (P1)

**Problema:** O diálogo "Modo de Renderização" (V1-V20) não é exercitado.  
O cache pickle usa `mode.name` como sufixo — uma mudança de modo deve invalidar  
o cache, mas isso não é validado.

**Fix sugerido:** Teste que troca para `STRUCTURAL_ONLY` e verifica que o canvas  
carrega entidades diferentes (menos linhas, só estruturais).

---

### GAP-06 — Pickle Cache Auto-Invalidação (P1)

**Problema:** Após o fix `_LOADER_MTIME` em `dxf_worker.py`, não há teste  
automatizado que valide a invalidação do cache quando `dxf_loader.py` é modificado.

**Fix sugerido:**
```python
# 1. Criar .pkl artificialmente com mtime antigo
# 2. Tocar dxf_loader.py (atualizar mtime)
# 3. Carregar DXF e verificar que bypassa cache (log: "carregado sem cache")
```

---

### GAP-07 — Verificação do CERTIFICADO.json (P2)

**Problema:** O teste só verifica que `CERTIFICADO.json` **existe**, não seu conteúdo.  
Um certificado com score 0 ou campos ausentes não seria detectado.

**Fix sugerido:**
```python
cert = json.loads(Path("D:/Agente-cad-PYSIDE/.../CERTIFICADO.json").read_text())
assert cert.get("obra") != ""
assert 0 <= cert.get("media_score", -1) <= 100
assert cert.get("status") in ("APROVADO", "CONDICIONAL", "REPROVADO")
```

---

### GAP-08 — Score Labels Reais (P2)

**Problema:** Os robôs retornam `score_label='OK'` mas isso é um fallback visual.  
O score numérico real (ex: 84.2%) não é extraído pelo teste.

**Fix sugerido:** Após `btn_validate`, procurar label com regex `r'\d+\.\d+%'`  
e assertar `float(score_text[:-1]) >= 60.0`.

---

### GAP-09 — Combo de Obra Inacessível via UIA (P2)

**Problema:** Comentado no código como `"obra combo inacessivel via UIA"`.  
O `QComboBox` dos robôs não aparece na árvore de acessibilidade do Windows UIA.

**Diagnóstico necessário:**
- Verificar se `setAccessibleName()` está sendo chamado no combo
- Tentar `win.child_window(best_match='ComboBox', found_index=0)`  
- Tentar `win.type_keys('{ALT}{DOWN}')` para abrir dropdown

---

### GAP-10 — Testes Unitários de dxf_loader.py (P2)

**Problema:** Não há testes unitários automatizados do `DXFLoader.load_dxf()`.  
Todos os 10 fixes aplicados só são validados via teste E2E (lento, frágil).

**Fix sugerido:**
```python
# tests/unit/test_dxf_loader.py
def test_load_stog_r12():
    data = DXFLoader.load_dxf("tests/fixtures/TREINO_1.dxf")
    assert len(data['lines']) > 1000
    assert len(data['texts']) > 100
    assert data.get('error') is None
```

---

## Rastreamento de Estado da Interface

### Tab 0 — Diagnostic Hub
| Componente | Estado | Testado |
|------------|--------|---------|
| Canvas DXF | ✅ linhas=1911 após purga do pkl | ✅ tab1_canvas_count |
| Sidebar pavimentos | ✅ lista obras | ✅ tab1_sidebar |
| Botão "Interpretar DXF" | ✅ existe | ❌ execução não testada |
| Botão "Pipeline E2E" | ✅ existe | ❌ execução não testada |
| Modo de renderização | ✅ diálogo disponível | ❌ não testado |
| Log de eventos | ✅ mostra stdout | ❌ não validado no teste |

### Tab 2 — Comparison Engine
| Componente | Estado | Testado |
|------------|--------|---------|
| CheckBoxes PL/LV/FV/LJ | ✅ presentes | ✅ tab2_checkboxes |
| Botão "▶ Validar" | ✅ habilitado | ✅ tab2_validar_run |
| Scores por tipo | ✅ exibidos | ❌ valor numérico não assertado |
| Histórico (tabela) | ✅ existe | ❌ não testado |
| Tendência (sparkline) | ✅ existe | ❌ não testado |
| Botão Certificar | ✅ habilitado | ✅ tab2_certificar_run |
| Conteúdo CERTIFICADO.json | ✅ gerado | ❌ conteúdo não validado |

### Tabs 3-6 — Robôs (Pilares / LV / FV / Laje)
| Componente | Estado | Testado |
|------------|--------|---------|
| Score label visível | ✅ 'OK' em todos | ✅ robo_*_dxf |
| Seleção de obra via combo | ❌ inacessível UIA | ❌ GAP-09 |
| Geração de DXF novo | ❌ não verificado | ❌ GAP-01 |
| Conteúdo do DXF gerado | ❌ não verificado | ❌ GAP-01 |

---

## Infraestrutura de Cache DXF

### Estado Pós-Fix

| Mecanismo | Antes | Depois |
|-----------|-------|--------|
| Invalidação por DXF mtime | ✅ já existia | ✅ mantido |
| Invalidação por loader mtime | ❌ ausente | ✅ `_LOADER_MTIME` em `dxf_worker.py` |
| Teste automatizado da invalidação | ❌ ausente | ❌ GAP-06 pendente |

### Causa Raiz do Bug `lines=0` (Resolvido)

1. `dxf_loader.py` foi corrigido (10 fixes)
2. `dxf_worker.py` verificava apenas `pkl_mtime > dxf_mtime`
3. Como o arquivo `.dxf` não foi modificado → pkl stale era sempre usado
4. **Fix aplicado:** `pkl_mtime > dxf_mtime AND pkl_mtime > _LOADER_MTIME`
5. **Solução imediata:** `find . -name "*.pkl" -delete` (purga manual)

---

## Próximas Histórias Recomendadas

| ID | Título | Prioridade |
|----|--------|-----------|
| CAD-TEST-01 | Testes unitários DXFLoader (10 fixes) | P0 |
| CAD-TEST-02 | Validação geração real de DXF pelos robôs | P0 |
| CAD-TEST-03 | Cobertura Fase-3 (Interpretar DXF) | P1 |
| CAD-TEST-04 | Fix UIA ComboBox robôs (acessibilidade) | P1 |
| CAD-TEST-05 | Validação conteúdo CERTIFICADO.json | P2 |
| CAD-TEST-06 | Teste invalidação cache pkl por loader mtime | P2 |
| CAD-DS-01 | Migração theme.py em detail_card.py (P1 file) | P1 |
| CAD-DS-02 | Migração theme.py em login_widget.py | P2 |
| CAD-DS-03 | Migração theme.py em organisms.py | P2 |
