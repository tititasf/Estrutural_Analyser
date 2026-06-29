# CLAUDE.md — Estrutural Analyzer (CAD-ANALYZER)

## O que é este projeto

App PySide6 (10 abas) que automatiza formas de concreto estrutural:
DXF bruto → interpretação (Structural Analyzer) → geradores STOG (robôs PL/LV/FV/LJ)
→ fidelidade → engenharia reversa. Entry point: `main.py`.

**Pipeline dual-flow (nomenclatura N1–N4):**
- **N1** = itens estruturais do pipeline bruto (Fase-3/4, campos do Structural Analyzer)
- **N2** = ficha granular extraída do STOG humano pelo Motor Reverso
- **N3** = DXF gerado pelo robô a partir de N1 (via conversão Fase-4)
- **N4** = DXF gerado pelo robô a partir de N2

## MISSÃO ATUAL (2026-06) — Arete Quality Gates

> Leia SEMPRE antes de agir:
> 1. `docs/HANDOFF-ARETE-EXECUTOR.md` — missão, fatos verificados, protocolo de autonomia
> 2. `docs/MASTERPLAN-ARETE-QUALITY-GATES.md` — gates G0–G6, fases, definição de Arete (§6)

**Fase A em curso:** paridade 100% entre DXF N4 e recorte N2 nos 111 itens do
**13_PAV da Obra_TREINO_1** (PIL 35 → LV 32 → FV 26 → LAJ 18). Harness em `scripts/arete/`.
Estado/progresso: `scripts/arete/relatorios/` (relatório mais recente = onde paramos).

## Ambiente Python — OBRIGATÓRIO Python 3.12

> **NUNCA rodar com Python 3.13 ou 3.14.**
> Python 3.14 causa crash silencioso `STATUS_STACK_BUFFER_OVERRUN (0xC0000409)` no Windows
> quando QThread é destruído pelo GC — o processo é morto pelo SO antes de qualquer handler.
> ChromaDB (RAG) também é incompatível com Python 3.14 (Pydantic V1 quebra).

| Item | Valor |
|------|-------|
| Python obrigatório | **3.12** — `C:\Users\Thierry\AppData\Local\Programs\Python\Python312\python.exe` |
| Launcher | `iniciar_dashboard.bat` (já aponta para Python 3.12) |
| Build | `build_nuitka.bat` (já aponta para Python 3.12) |
| Pin de versão | `.python-version` na raiz do repo = `3.12` |
| Ambiente oficial | `D:\Agente-cad-PYSIDE\.venv\Scripts\python.exe` |

Configurar com `install_all.ps1` e iniciar sempre por `iniciar_dashboard.bat`.
Especificação completa: `../docs/PYTHON-3.12-RUNTIME.md`.

## Fatos do ambiente (verificados — não redescobrir)

| Item | Valor |
|------|-------|
| DB real (SQLite) | `D:/Agente-cad-PYSIDE/project_data.vision` (o da raiz do repo é stale) |
| Fichas N2 | tabela `reverse_eng_fichas` (campos_json = schema exato dos JSONs Fase-4; só `_er_meta` difere) |
| Recortes N2 | tabela `reverse_eng_recortes` + DXFs em `D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-2_Triagem/recortes_reversos/` |
| Geradores STOG | `scripts/gerar_{pl,lv,fv,lj}_dxf_stog.py` — certificados, usar via adapter |
| Motores reversos | `scripts/motor_reverso_{pil,lv,fv,laj,obra}.py` |
| Conversão N1→robô | `DADOS-OBRAS/{obra}/Fase-4_Sincronizacao/JSON_*/` |
| Render/scoring ref | `scripts/validar_granular_nim.py` (reusar lógica; NIM vision BANIDO como scorer) |

## Regras inegociáveis

1. **Schema N1 (Structural Analyzer) é IMUTÁVEL** — convergência com N2 acontece na
   camada de conversão, nunca alterando campos/vínculos do SA.
2. **NÃO editar `src/ui/modules/diagnostic_reverse_hub.py`** nem widgets de UI sem
   confirmar que nenhum outro agente trabalha neles em paralelo.
3. **NÃO modificar geradores STOG / motores reversos** sem causa comprovada por gate
   G1/G2 — e sempre rodar regressão do golden set (`GOLDEN/`) após qualquer fix.
4. **JSONs Fase-4 originais são intocáveis** — N2 é caminho paralelo independente.
5. **Um fix por causa, nunca hack por item.** Validação visual obrigatória: renderizar
   PNG e LER a imagem em todo FAIL.
6. **Escopo incremental rígido:** 13_PAV 100% → TREINO_1 completa → outras obras em
   steps. Nunca processar tudo de uma vez.
7. AutoCAD batch via `accoreconsole.exe` — NUNCA pipelines em paralelo.
8. Git: sem push para main; commits na branch de sessão.

## Modo de trabalho

Autônomo (autorizado pelo usuário): executar, validar, corrigir e instalar dependências
sem pedir permissão. Parar apenas para: decisão de produto ambígua (exceção legítima vs
bug), ação destrutiva fora de escopo, ou bloqueio externo real.
Toda rodada termina com `RELATORIO.md` em `scripts/arete/relatorios/{timestamp}/` +
golden selado + nota do próximo FAIL a atacar.
