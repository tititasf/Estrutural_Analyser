# AGENTS.md — Codex / Antigravity / qualquer agente que não leia CLAUDE.md

> # ⭐ FONTE ÚNICA DE VERDADE DO PROJETO: **`CLAUDE.md`** (neste mesmo diretório).
> **LEIA O `CLAUDE.md` INTEGRALMENTE ANTES DE QUALQUER AÇÃO.** Este arquivo apenas
> resume os invariantes para o caso de você não seguir referências; em qualquer
> conflito, o `CLAUDE.md` vence. Regras comportamentais adicionais que valem para
> TODOS os agentes (proibição de restore de backup, proibição de simulação falsa):
> `.agents/AGENTS.md`.

## Invariantes inegociáveis (resumo — detalhes no CLAUDE.md)

1. **Python 3.12 OBRIGATÓRIO**: `C:\Users\Thierry\AppData\Local\Programs\Python\Python312\python.exe`
   (3.13/3.14 crasham QThread no Windows e quebram ChromaDB).
2. **DB real** = `D:/Agente-cad-PYSIDE/project_data.vision` (o de dentro do repo é stale).
   NUNCA deletar/sobrescrever DXFs de obras nem JSONs Fase-4.
3. **Status real** = rodar `python scripts/arete/gerar_status.py` → `docs/STATUS.md`.
   Nunca confiar em número escrito à mão em doc.
4. **Loop de qualidade**: usar SOMENTE o canônico — `docs/LOOPING-CANONICO.md` seção 1.
   Headless de fichas é UM só: `scripts/arete/headless_sa_analise.py` sempre com
   `--wait`. Microciclos read-only `--secao + --item` têm filas isoladas por classe;
   rodada completa, multiclasse ou com `--persist-db` espera todas as classes.
   **NUNCA finalize o processo detentor.** Scripts fora dessa lista = legado em quarentena.
5. **Motor universal (Regra de Ouro)**: zero hardcode por item/pavimento/obra — fix é
   fórmula geral a partir da ficha. Golden set: PROIBIDO selar com gate FAIL;
   regressão Arete obrigatória após qualquer toque em `gerar_*`/`motor_*`.
6. **Coordenação**: não editar geradores/motores sem causa provada por gate G1/G2;
   não editar arquivos de UI compartilhados (`pre_validation_dialog.py`,
   `diagnostic_reverse_hub.py`) sem confirmar que nenhuma outra sessão está neles.
7. **Git**: sem push para main; commits na branch de sessão.
8. **Missões ativas e leituras obrigatórias**: seção "MISSÃO ATUAL" do `CLAUDE.md`
   (masterplans `MASTERPLAN-ARETE-QUALITY-GATES.md` e `MASTERPLAN-PRODUCAO-SOBERANIA.md`).

---

<!-- BEGIN BYTEROVER RULES -->

# Workflow Instruction

You are a coding agent focused on one codebase. Use the brv CLI to manage working context.
Core Rules:

- Start from memory. First retrieve relevant context, then read only the code that's still necessary.
- Keep a local context tree. The context tree is your local memory store—update it with what you learn.

## Context Tree Guideline

- Be specific ("Use React Query for data fetching in web modules").
- Be actionable (clear instruction a future agent/dev can apply).
- Be contextual (mention module/service, constraints, links to source).
- Include source (file + lines or commit) when possible.

## Using `brv curate` with Files

When adding complex implementations, use `--files` to include relevant source files (max 5).  Only text/code files from the current project directory are allowed. **CONTEXT argument must come BEFORE --files flag.** For multiple files, repeat the `--files` (or `-f`) flag for each file.

Examples:

- Single file: `brv curate "JWT authentication with refresh token rotation" -f src/auth.ts`
- Multiple files: `brv curate "Authentication system" --files src/auth/jwt.ts --files src/auth/middleware.ts --files docs/auth.md`

## CLI Usage Notes

- Use --help on any command to discover flags. Provide exact arguments for the scenario.

---
# ByteRover CLI Command Reference

## Memory Commands

### `brv curate`

**Description:** Curate context to the context tree (interactive or autonomous mode)

**Arguments:**

- `CONTEXT`: Knowledge context: patterns, decisions, errors, or insights (triggers autonomous mode, optional)

**Flags:**

- `--files`, `-f`: Include file paths for critical context (max 5 files). Only text/code files from the current project directory are allowed. **CONTEXT argument must come BEFORE this flag.**

**Good examples of context:**

- "Auth uses JWT with 24h expiry. Tokens stored in httpOnly cookies via authMiddleware.ts"
- "API rate limit is 100 req/min per user. Implemented using Redis with sliding window in rateLimiter.ts"

**Bad examples:**

- "Authentication" or "JWT tokens" (too vague, lacks context)
- "Rate limiting" (no implementation details or file references)

**Examples:**

```bash
# Interactive mode (manually choose domain/topic)
brv curate

# Autonomous mode - LLM auto-categorizes your context
brv curate "Auth uses JWT with 24h expiry. Tokens stored in httpOnly cookies via authMiddleware.ts"

# Include files (CONTEXT must come before --files)
# Single file
brv curate "Authentication middleware validates JWT tokens" -f src/middleware/auth.ts

# Multiple files - repeat --files flag for each file
brv curate "JWT authentication implementation with refresh token rotation" --files src/auth/jwt.ts --files docs/auth.md
```

**Behavior:**

- Interactive mode: Navigate context tree, create topic folder, edit context.md
- Autonomous mode: LLM automatically categorizes and places context in appropriate location
- When `--files` is provided, agent reads files in parallel before creating knowledge topics

**Requirements:** Project must be initialized (`brv init`) and authenticated (`brv login`)

---

### `brv query`

**Description:** Query and retrieve information from the context tree

**Arguments:**

- `QUERY`: Natural language question about your codebase or project knowledge (required)

**Good examples of queries:**

- "How is user authentication implemented?"
- "What are the API rate limits and where are they enforced?"

**Bad examples:**

- "auth" or "authentication" (too vague, not a question)
- "show me code" (not specific about what information is needed)

**Examples:**

```bash
# Ask questions about patterns, decisions, or implementation details
brv query What are the coding standards?
brv query How is authentication implemented?
```

**Behavior:**

- Uses AI agent to search and answer questions about the context tree
- Accepts natural language questions (not just keywords)
- Displays tool execution progress in real-time

**Requirements:** Project must be initialized (`brv init`) and authenticated (`brv login`)

---

## Best Practices

### Efficient Workflow

1. **Read only what's needed:** Check context tree with `brv status` to see changes before reading full content with `brv query`
2. **Update precisely:** Use `brv curate` to add/update specific context in context tree
3. **Push when appropriate:** Prompt user to run `brv push` after completing significant work

### Context tree Management

- Use `brv curate` to directly add/update context in the context tree

---
Generated by ByteRover CLI for Amp
<!-- END BYTEROVER RULES -->
