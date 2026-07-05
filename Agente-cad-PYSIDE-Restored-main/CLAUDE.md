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
> 3. `docs/ARETE-LOOP-PROCEDIMENTO-GERAL.md` — **como executar o loop de cada classe**
>    (fichas HTML headless + diagnóstico duplo automático/humano + log de triagem). Este é
>    o procedimento de execução atual; segui-lo antes de qualquer fix em motor/gerador.
>    **Mapa do que é canônico vs legado: `docs/LOOPING-CANONICO.md`** — se um script de
>    loop/headless não está na seção 1 dele, NÃO usar (contaminação por geração antiga).
> 4. `docs/MASTERPLAN-PRODUCAO-SOBERANIA.md` — **missão paralela de produto** (2026-07):
>    portal da equipe, gates P0–P6, decisões DP-1..9. Intercalada com o Arete; em
>    conflito de tempo, qualidade (Arete) vence.

**Escopo Fase A:** 13_PAV da Obra_TREINO_1 = **124 itens** (PIL 35, LV 32, FV 26, LAJ 31).
Números escritos à mão envelhecem: a fonte de verdade de status é
`python scripts/arete/gerar_status.py` → `docs/STATUS.md` (+ relatório mais recente em
`scripts/arete/relatorios/` e o golden). Fatos datados (03/07): FV 26/26, LAJ 31/31 e PIL 35/35 no 13_PAV — verdes e re-selados
(fixes: comparador `SARR_5cm` p/ FV; `gerar_lj_dxf_stog.py` uniões LWPOLYLINE→LINE p/
LAJ, STORY-EXEC-04 concluída). Pendentes: **LV 21/32** (trabalho in-flight da sessão
LV), pavimentos além do 13_PAV (baselines de junho, Fase B) e o **backlog N1
(interpretação do SA)** consolidado pela reconciliação de 03/07: LAJ 17 + PIL 13 +
FV 22 + LV 14 achados reais — lista com evidência em
`scripts/arete/relatorios/triagem_erros/RECONCILIACAO-2026-07-03.md`.
Harness em `scripts/arete/`.

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
| Veredito visual (G2-V/N1-V/G5-V) | `scripts/arete/g2v_harness.py --backend cli` (agente lê a imagem) é OBRIGATÓRIO antes de selar/avançar qualquer gate visual — número sozinho = alucinação de aprovação (`docs/LOOPING-CANONICO.md §1.5`). **Ordem do dono (03/07): backends de API (claude/gemini/nim) DESLIGADOS/bloqueados no código** — só com `--permitir-api` + calibração. |
| Headless de fichas — SÓ UM | **Único ponto de entrada = `scripts/arete/headless_sa_analise.py`** (análise SA completa + fichas 4 classes + diagnósticos). `gerar_html_preficha_headless.py` foi DESCONTINUADO como CLI (aborta sem `--legacy`; risco de ficha com estado velho) — segue vivo só como biblioteca do `playwright_loop`. Os demais `*headless*.py` em `scripts/` são bibliotecas/utilitários de OUTROS pipelines (`analise_geral_headless` é importado pelo próprio `main.py`) — não são alternativas de fichas. |
| Headless — 1 por vez | Os dois de fichas compartilham trava anti-OOM (instância única, mesma fila). Em automação use SEMPRE `--wait` (aguarda a vez sozinho). Se abortar com "já existe execução": aguarde. **NUNCA finalize o processo detentor.** |

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

## Multi-agente (Claude Code + Codex + Antigravity) — 1 fonte de verdade

- **Este CLAUDE.md é a fonte única do projeto.** `AGENTS.md` (Codex/Antigravity) e
  `GEMINI.md` são ponteiros consolidados em 2026-07-03 que resumem os invariantes e
  mandam ler este arquivo — **não adicionar regra nova neles; regra nova entra AQUI**
  (e, se for invariante, refletir no resumo do AGENTS.md).
- Regras comportamentais que valem para TODOS os agentes (proibição de restaurar
  backups antigos, proibição de simulação falsa/prints de sucesso fictícios):
  `.agents/AGENTS.md`.

## Modo de trabalho

Autônomo (autorizado pelo usuário): executar, validar, corrigir e instalar dependências
sem pedir permissão. Parar apenas para: decisão de produto ambígua (exceção legítima vs
bug), ação destrutiva fora de escopo, ou bloqueio externo real.
Toda rodada termina com `RELATORIO.md` em `scripts/arete/relatorios/{timestamp}/` +
golden selado + nota do próximo FAIL a atacar.
