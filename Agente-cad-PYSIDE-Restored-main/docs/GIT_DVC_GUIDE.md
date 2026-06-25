# Git + DVC — Guia de Trabalho do Projeto

## Visão Geral do Repositório

O workspace tem duas camadas separadas:

```
D:/Agente-cad-PYSIDE/                  ← raiz do git
├── .git/                               ← controle de versão
├── .dvc/                               ← controle de dados (DVC)
├── DADOS-OBRAS/                        ← dados de obras (gerenciado pelo DVC)
├── project_data.vision                 ← banco SQLite principal (gerenciado pelo DVC)
├── DADOS-OBRAS.dvc                     ← ponteiro DVC para DADOS-OBRAS
├── project_data.vision.dvc             ← ponteiro DVC para o DB
└── Agente-cad-PYSIDE-Restored-main/   ← código da aplicação
    ├── src/
    ├── scripts/
    ├── docs/
    └── GOLDEN/
```

> **Regra fundamental:** código vai para o **git**, dados grandes vão para o **DVC/Drive**.
> Nunca fazer `git add DADOS-OBRAS/` ou `git add project_data.vision`.

---

## Branches

| Branch | Propósito |
|--------|-----------|
| `main` | Branch estável, espelho do que está no GitHub |
| `etapa1-fichas-botoes` | Branch de desenvolvimento ativa (sessão atual) |
| `fix/<nome>` | Correção pontual de bug |
| `feat/<nome>` | Feature nova |

### Regras de branch

- **Nunca commitar diretamente na `main`** durante desenvolvimento — use uma branch de sessão/feature
- Pull requests ou merge explícito para `main` após validação
- Push para `main` requer que todos os golden tests passem (124/124 no Arete)
- Force push na `main` somente quando o histórico contém blobs gigantes (situação excepcional — documentar o motivo no commit)

---

## Workflow Diário

### Início de sessão

```bash
cd D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main

# Ver estado atual
git status
git log --oneline -5

# Garantir que os dados estão atualizados (se mudaram no Drive)
cd ..
dvc pull
cd Agente-cad-PYSIDE-Restored-main
```

### Durante o desenvolvimento

```bash
# Trabalhar na branch de sessão
git checkout etapa1-fichas-botoes   # ou criar nova: git checkout -b feat/nome

# Commitar incrementalmente — pequenos commits temáticos
git add src/ui/canvas.py scripts/motor_reverso_fv.py
git commit -m "fix(canvas): clear_beams restaura snap_points para evitar crash"
```

### Fim de sessão

```bash
# Commitar tudo pendente no código
git add -u
git commit -m "feat(arete): ..."

# Se dados de obra foram modificados, atualizar DVC
cd D:/Agente-cad-PYSIDE
dvc add DADOS-OBRAS
dvc push
git add DADOS-OBRAS.dvc
git commit -m "dados: atualiza DADOS-OBRAS após rodada Arete"
git push origin <branch>
```

---

## Convenção de Commits

Formato: `tipo(escopo): descrição em português`

| Tipo | Quando usar |
|------|-------------|
| `feat` | Nova funcionalidade |
| `fix` | Correção de bug |
| `refactor` | Refatoração sem mudança de comportamento |
| `test` | Adição ou correção de testes |
| `docs` | Documentação |
| `dados` | Atualização de arquivos DVC (dados de obras) |
| `golden` | Re-selagem do golden set após fix validado |
| `arete` | Mudanças no harness de validação Arete |

### Exemplos reais do projeto

```
fix(canvas): clear_beams restaura snap_points/snap_segments para evitar crash
feat(ce): CE usa motor live para FV — elimina fallback para ficha estática do DB
fix(motor-fv): detecção NxMMM → _multiplier no segmento (cota multiplicadora)
golden(13_PAV): re-sela PIL/LV/FV/LAJ após fix tier inválido — 124/124 PASS
dados: remove DADOS-OBRAS do git + inicializa DVC com gdrive
```

### Rodapé obrigatório para commits gerados por IA

```
Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

---

## DVC — Gestão de Dados

### Configuração atual

| Item | Valor |
|------|-------|
| Remote | Google Drive (`thierry.tasf@gmail.com`) |
| Folder ID | `16M5RO5VgTlPAAV9ZUFQ12Dg3J-PdubqE` |
| Cache type | `hardlink` (não duplica espaço em disco) |
| Credenciais | Google Cloud project `dvc-estrutural` (375510219390) |

### Clonar o projeto do zero

```bash
# 1. Clonar o código
git clone https://github.com/tititasf/Estrutural_Analyser.git
cd Estrutural_Analyser

# 2. Instalar DVC
pip install "dvc[gdrive]"

# 3. Configurar credenciais OAuth (necessário uma vez por máquina)
dvc remote modify --local gdrive gdrive_client_id "<SEU_CLIENT_ID>"
dvc remote modify --local gdrive gdrive_client_secret "<SEU_CLIENT_SECRET>"

# 4. Baixar os dados (abrirá o browser para login Google)
dvc pull
```

> O `dvc pull` vai pedir autorização no browser na primeira vez. Faça login com `thierry.tasf@gmail.com`.

### Atualizar dados no Drive após mudanças

```bash
cd D:/Agente-cad-PYSIDE

# Se DADOS-OBRAS mudou
dvc add DADOS-OBRAS
dvc push
git add DADOS-OBRAS.dvc
git commit -m "dados: atualiza DADOS-OBRAS"
git push origin main

# Se project_data.vision mudou
dvc add project_data.vision
dvc push
git add project_data.vision.dvc
git commit -m "dados: atualiza project_data.vision"
git push origin main
```

### Arquivos ignorados pelo git (não commitar nunca)

```
project_data.vision          # DB principal (use DVC)
project_data.vision-wal      # WAL do SQLite
project_data.vision-shm      # SHM do SQLite
*.bak                        # Backups do DB
DADOS-OBRAS/                 # Dados de obras (use DVC)
engrev_*.vision.bak*         # Backups de aprendizado
```

---

## Merge para Main

Antes de fazer merge ou push para `main`:

1. **Todos os golden tests passando:** `python scripts/arete/rodar_arete.py` → 124/124 PASS
2. **Sem arquivos grandes:** verificar que nenhum `.bak`, `.dxf` grande ou `.vision` entrou no staging
3. **DVC atualizado:** se dados mudaram, `dvc push` antes do git push

```bash
# Checklist pré-push main
git diff --cached --name-only | grep -E "\.(bak|vision)$"  # deve retornar vazio
git diff --cached --name-only | grep "DADOS-OBRAS"          # deve retornar vazio
```

---

## Histórico e Problemas Conhecidos

### Blobs gigantes no histórico (resolvido em 2026-06-25)

Commit `c2b1264fa` havia adicionado 4 arquivos `.bak` de ~1.3GB cada, bloqueando o push para o GitHub. Resolvido com `git filter-branch --index-filter` + force push. Os blobs foram limpos com `git gc --aggressive --prune=now`.

**Prevenção:** o `.gitignore` na raiz do workspace bloqueia `*.bak` e `DADOS-OBRAS/`. Nunca usar `git add .` na raiz do workspace sem revisar o staging.

### Disco cheio durante dvc add (resolvido em 2026-06-25)

O `dvc add` por padrão copia arquivos para o cache local, dobrando o uso de disco. Resolvido configurando `cache.type = hardlink` — o cache usa hardlinks para os arquivos originais, sem duplicação.
