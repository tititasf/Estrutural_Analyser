# AGENTS.md — workspace CAD-ANALYZER (ponteiro fixo)

> 1. **Fonte única deste nível: `CLAUDE.md`** (este diretório) — layout do workspace,
>    missões ativas e regras de dados de produção. Leia antes de agir.
> 2. O código da app fica em `Agente-cad-PYSIDE-Restored-main/` — lá dentro leia o
>    `CLAUDE.md` do repo (fonte única do projeto) e o `AGENTS.md` (invariantes p/
>    agentes que não leem CLAUDE.md).
> 3. Em conflito: CLAUDE.md do repo > CLAUDE.md do workspace > este arquivo.


## Regras do Agente (Adicionadas Dinamicamente)
- **NUNCA USAR COMANDOS GIT (git checkout, git reset, git clean, etc) SEM PERMISSÃO EXPLÍCITA**. O repositório contém modificações locais geradas por outros agentes que não estão versionadas. Usar git destrutivo causará perda de trabalho irrecuperável.

## Imported Claude Cowork project instructions
