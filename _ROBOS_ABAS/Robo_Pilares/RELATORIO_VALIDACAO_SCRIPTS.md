# Relatório de Validação de Scripts - Robo Pilares

**Data:** 2026-01-21  
**Status:** ⚠️ DIFERENÇAS DETECTADAS

## 📊 Resumo Executivo

### Resultados dos Testes

| Pavimento | CIMA | ABCD | GRADES | Status |
|-----------|------|------|--------|--------|
| **Subsolo** | ❌ 1 vs 28 (diferentes) | ❌ 0 vs 3 (faltando main) | ❌ 1 vs 4 (diferentes) | **FALHA** |
| **1 SS** | ❌ 0 vs 1 (faltando main) | ❌ 0 vs 0 | ❌ 0 vs 116 (faltando main) | **FALHA** |
| **Terreo** | ❌ 0 vs 6 (faltando main) | ❌ 0 vs 0 | ❌ 0 vs 0 | **FALHA** |
| **5pav** | ❌ 0 vs 15 (faltando main) | ❌ 0 vs 30 (faltando main) | ❌ 0 vs 60 (faltando main) | **FALHA** |

### Problemas Identificados

#### 1. **Scripts Faltando no main.py**
- A maioria dos pavimentos não tem scripts gerados via `main.py`
- Scripts existem apenas no standalone (interface legacy)
- **Causa provável:** Botões de geração no `main.py` não estão salvando em `SCRIPTS_ROBOS/`

#### 2. **Scripts Diferentes quando Existem**
- **CIMA (Subsolo):** 1 script no main.py vs 28 no standalone
  - Diferenças: Comandos `_ZOOM` diferentes, estrutura diferente
  - Diff: 1668-1773 linhas de diferença
  
- **GRADES (Subsolo):** 1 script no main.py vs 4 no standalone
  - Diferenças:
    - Nome do pilar: `1` vs `P16A.A`
    - Coordenadas de zoom: `4000.0` vs `4460.5`, `4921.0`
  - Diff: 793-888 linhas de diferença

#### 3. **ABCD Completamente Ausente**
- Nenhum script ABCD encontrado no `main.py` para nenhum pavimento
- Scripts existem no standalone mas não foram gerados via interface integrada

## 🔍 Análise Detalhada

### Diferenças Encontradas (Subsolo/CIMA)

```
--- main.py
+++ standalone
@@ -4,55 +4,37 @@
 ;
 _ZOOM
-C -40,70 10
-;
-_ZOOM
-C -41,80.0 10
```

**Interpretação:** O script do main.py tem comandos `_ZOOM` extras que não existem no standalone. Isso pode indicar:
- Dados de entrada diferentes
- Lógica de geração diferente
- Versões diferentes dos geradores

### Diferenças Encontradas (Subsolo/GRADES)

```
--- main.py
+++ standalone
@@ -24,7 +24,7 @@
 _TEXT
 3990.0,0.0
 90
-1
+P16A.A
```

**Interpretação:** O nome do pilar está diferente:
- main.py: `1` (número simples)
- standalone: `P16A.A` (nome completo com face)

Isso indica que o mapeamento `PilarModel` → `dict` pode não estar preservando o nome correto.

## 🎯 Causas Prováveis

### 1. Mapeamento de Dados Incorreto
- `AutomationOrchestratorService._pilar_model_to_legacy_dict()` pode não estar mapeando todos os campos corretamente
- Nome do pilar pode estar sendo extraído incorretamente

### 2. Diretórios de Saída Diferentes
- main.py: `SCRIPTS_ROBOS/{pavimento}_{TIPO}/`
- standalone: `output/scripts/{pavimento}_{TIPO}/`
- Pode haver confusão sobre onde salvar

### 3. Versões Diferentes dos Geradores
- Os geradores legacy (`CIMA_FUNCIONAL_EXCEL`, `Abcd_Excel`, `GRADE_EXCEL`) podem ter versões diferentes
- Ou podem estar sendo chamados com parâmetros diferentes

### 4. Dados de Entrada Diferentes
- Os pilares podem ter dados diferentes entre as duas interfaces
- Sincronização `sync_pillars_to_robo_pilares_action` pode não estar preservando todos os campos

## ✅ Ações Recomendadas

### Prioridade ALTA

1. **Verificar Mapeamento de Dados**
   - Revisar `_pilar_model_to_legacy_dict()` em `automation_service.py`
   - Garantir que `nome`, `numero`, e todos os campos de face estão sendo mapeados corretamente
   - Adicionar logs para comparar dict gerado vs esperado

2. **Unificar Diretórios de Saída**
   - Garantir que ambos salvam em `SCRIPTS_ROBOS/` na raiz do projeto
   - Verificar `AutomationOrchestratorService.scripts_dir`

3. **Gerar Scripts via main.py**
   - Testar botões de geração no `main.py`
   - Verificar se `generate_script_pillar_full()` e `generate_script_pavement_pillar()` estão funcionando
   - Confirmar que scripts estão sendo salvos no local correto

### Prioridade MÉDIA

4. **Validar Versões dos Geradores**
   - Verificar se os módulos `CIMA_FUNCIONAL_EXCEL`, `Abcd_Excel`, `GRADE_EXCEL` são os mesmos
   - Comparar assinaturas das funções `preencher_campos_diretamente_e_gerar_scripts()`

5. **Adicionar Testes Unitários**
   - Testar `_pilar_model_to_legacy_dict()` com dados conhecidos
   - Comparar dict gerado com dict esperado

### Prioridade BAIXA

6. **Melhorar Logging**
   - Adicionar logs detalhados na geração de scripts
   - Registrar dados de entrada e saída de cada gerador

## 📝 Próximos Passos

1. ✅ **Sistema de Testes Criado**
   - `test_script_comparison.py`: Compara scripts linha por linha
   - `test_autonomo_validacao.py`: Executa testes em lote
   - `gerar_relatorio_validacao.py`: Gera relatórios detalhados

2. 🔄 **Próximo:** Corrigir mapeamento de dados
   - Revisar `_pilar_model_to_legacy_dict()`
   - Garantir que nome do pilar está correto
   - Validar todos os campos de face

3. 🔄 **Depois:** Testar geração via main.py
   - Executar botões de geração
   - Verificar se scripts são salvos corretamente
   - Comparar com standalone

## 🛠️ Como Usar os Testes

```bash
# Teste individual
cd _ROBOS_ABAS/Robo_Pilares
python test_script_comparison.py --obra "Obra Testes" --pavimento "Subsolo" --verbose

# Teste autônomo (todos os pavimentos)
python test_autonomo_validacao.py

# Gerar relatório
python gerar_relatorio_validacao.py
```

## 📌 Notas Técnicas

- **Encoding:** Scripts devem estar em UTF-16 LE com BOM (`\xFF\xFE`)
- **Diretórios:**
  - main.py: `{project_root}/SCRIPTS_ROBOS/{pavimento}_{TIPO}/Combinados/`
  - standalone: `{project_root}/_ROBOS_ABAS/Robo_Pilares/pilares-atualizado-09-25/output/scripts/{pavimento}_{TIPO}/Combinados/`
- **Créditos:** Sistema de créditos está bypassado em modo desenvolvimento (`PILARES_DEV_MODE=1`)

---

**Status Final:** ⚠️ Sistema funcional mas scripts diferentes. Necessário corrigir mapeamento de dados e garantir geração via main.py.
