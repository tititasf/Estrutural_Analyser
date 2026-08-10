# Validação Visual (G2-V) — Caminhos explorados e veredito

**Data:** 2026-07-03 | **Status:** CANÔNICO — decisão de arquitetura do dono.
Complementa a hierarquia de validação de `docs/LOOPING-CANONICO.md §1.5` (G2-V =
Nível 2). Este doc responde: **qual é a forma confiável de dar o veredito visual que
o G2 numérico não consegue** — e fecha os becos sem saída para nenhuma sessão futura
reabri-los gastando tokens.

---

## 1. VEREDITO (leia isto primeiro)

> **A ÚNICA fonte de interpretação visual com qualidade GARANTIDA hoje é a visão do
> próprio agente de chat CLI — Claude Code, Codex ou Grok — lendo PNG (raster) no loop.**
> Quase todos os LLMs multimodais veem pixels, não SVG nativo no CLI: por isso o agente
> julga em **PNG** full-render; **SVG** fica para HTML/app/portal (zoom humano).
> Dual-mode canónico: `docs/QA-VISAO-EVIDENCIA-CANONICA.md`.
> APIs de visão são plugáveis no harness para batch autônomo FUTURO, mas nenhuma foi
> validada com qualidade suficiente ainda (NIM reprovado; Claude/Gemini API bloqueados
> por billing na data). Nenhum modelo de "grounding"/"computer-use" serve — eles agem,
> não julgam. Ver §2 e §3.

> **🔒 ORDEM DO DONO (03/07) — NADA DE API POR ENQUANTO.** O veredito visual é dado
> EXCLUSIVAMENTE pela visão do agente CLI (`--backend cli`). Os backends de API
> (claude/gemini/nim) estão **desligados por padrão e bloqueados no código** do
> `g2v_harness.py` — só rodam com `--permitir-api`, que exige ordem explícita do dono E
> o protocolo de calibração (§4). Nenhuma sessão deve habilitar API por conta própria.
> Motivo: sem calibração, modelo de API não validado = alucinação de aprovação (o NIM
> falhou 4/4, chegou a inverter achado). Enquanto não houver ordem + calibração, API não
> entra no fluxo.

Regra operacional: **selar golden exige veredito visual (§1.5). Enquanto não houver API
de visão calibrada e aprovada, esse veredito é dado pelo agente CLI lendo PNG**
(render full do DXF ou screenshot da ficha) — não por um script rodando sozinho e
não “lendo” só o path de um SVG sem raster. Headless **sem** `--persist-db` pode
gerar só imagem (dinâmico); **com** persist / portal web → HTML **com SVG**.
"G2 numérico 100%" continua sendo candidato.

---

## 2. Caminhos explorados e por que cada um foi aceito/rejeitado (03/07/2026)

| Caminho | Resultado | Veredito |
|---|---|---|
| **Agente CLI (Claude Code) lendo o PNG direto** | Pegou TODOS os defeitos reais: contaminação V13, marcas ausentes L301, hachura sumida L329 | ✅ **PADRÃO** — qualidade comprovada |
| **NIM (Llama 3.2 90B Vision) via API** | 4 testes, 0 acertos; na L329 **inverteu** o achado ("hachura no N4, falta no recorte" — era o oposto). Falso positivo direcional é pior que silêncio | ❌ **REPROVADO** (confirma HANDOFF) |
| **Gemini 2.5 Pro / 3.1 Pro via API** | Bloqueado: cota 0 (billing não habilitado no projeto Google) — não pôde ser avaliado | ⏸️ Candidato futuro, só com billing + calibração |
| **Claude API (backend `claude`)** | Bloqueado: sem crédito na conta Anthropic — não pôde ser avaliado | ⏸️ Candidato futuro (prior forte, mesmo modelo do agente) |
| **Edge + Copilot via Playwright** | Impossível estruturalmente: Copilot é chrome nativo do navegador, Playwright automatiza só o DOM da aba | ❌ **BECO SEM SAÍDA** — não reabrir |
| **Stealth/anti-bot (Patchright, Camoufox, nodriver)** | Irrelevante: são para raspar sites hostis (Cloudflare/DataDome). Aqui são arquivos `file://` locais, sem adversário | ❌ **FORA DE ESCOPO** |
| **UI-TARS / OmniParser / Computer Use / Operator** | Ferramentas para AGIR numa tela (clicar/navegar) ou parsear UI em elementos clicáveis. Não julgam "esse desenho está certo" | ❌ **FERRAMENTA ERRADA** — resolvem outro problema |
| **Z.AI Vision MCP (GLM-4.6V)** | Único da pesquisa que é "entender imagem" e não "agir". Não testado | ⏸️ Candidato a backend futuro, só via protocolo de calibração (§4) |

**Não existe "biblioteca mágica de visão".** A qualidade É o modelo. O melhor modelo
acessível é o próprio Claude/Codex do agente CLI. Parar de procurar infra; o gargalo
nunca foi capturar a imagem (isso o `playwright_loop.py` já faz perfeito) — é a força
do modelo que julga.

---

## 3. Captura da imagem — problema JÁ RESOLVIDO

A captura NÃO é o gargalo. Duas fontes, ambas prontas:

1. **Screenshot da ficha HTML granular** (preferida) — `playwright_loop.py` /
   `g2v_harness.screenshot_evidence_grid` tira o `.evidence-grid` (N1/N2/N3/N4 com
   contexto). Mais legível e **sem o bug da sentinela** (§5).
2. **Render DXF cru** (`paridade_visual.render_comparacao`) — fallback; hoje tem o bug
   da sentinela (§5), usar só quando não há ficha HTML.

Ferramenta de automação: **Playwright** (accessibility-tree + screenshot), já validado
no repo. Não trocar por Puppeteer/Selenium/stealth — nada disso agrega ao caso.

---

## 4. O harness `g2v_harness.py` — estado e pendências

**Auditado 03/07:** é **multiclasse** (CLASSES vem de `GERADORES.keys()`; todas as
funções de resolução recebem `classe`; roda PIL/LV/FV/LAJ com o mesmo código) e **sem
hardcode de item** (nenhum ID/medida/pavimento chumbado; `--pav` sobreescreve o
default). Fonte de imagem plugável (html/dxf), backend plugável (claude/nim/gemini),
prompt canônico único versionado, saída JSON. Arquitetura correta — manter.

**Estado (03/07 — implementado):** o harness cobre agora **os 3 pares visuais** com um
único código, via `--par`:
- `n2xn4` (G2-V) · `n1xn2` (N1-V — interpretação do SA) · `n3xn4` (G5-V — vazamento/conversão).
A ficha HTML mostra os 4 cards, então a mesma imagem serve qualquer par; muda só o foco
do prompt (`PAR_FOCUS` + `build_prompt`).

Melhorias aplicadas (03/07):
1. ✅ **Modo `--backend cli` (emit-only, agora DEFAULT):** gera a imagem + stub de
   veredito VAZIO + prompt, para o agente Claude Code/Codex ler e preencher. É a via de
   qualidade comprovada e é a padrão. `--backend claude|gemini` (API) fica para batch
   autônomo futuro; `nim` mantido só para comparação (reprovado).
2. ✅ **Schema de `achados` enriquecido** para rotear o fix ao motor certo:
   `parte` (CIMA/ABCD/face/segmento/laje/geral), `direcao`
   (`n4_a_mais`=gerador criou lixo | `n4_a_menos`=motor perdeu dado | `divergente`),
   `motor_suspeito` (`gerador|extrator_n2|interpretacao_n1|conversao_n1|indefinido`) +
   categorias novas `segmentacao` e `vazamento_gabarito`.
3. ✅ Docstring/CLI atualizados (cli/gemini/pares, gate label G2-V/N1-V/G5-V no console).
4. ✅ **Foco POR CLASSE** (`CLASSE_FOCUS`, injetado no prompt) — cada classe manda a
   visão caçar seus defeitos típicos (Modelo de Partes, masterplan §4-A):
   - **PIL:** VISÃO CIMA + ABCD (A/B longas, C/D curtas; subtipo ret/L/U/T→EFGH).
     **GRADES é parte separada com par próprio** (`--par grades`, só PIL): onde HÁ
     recorte de grades (pavimentos 1º/2º/14º/TÉRREO/TIPO da TREINO_1) vale veredito
     visual automático; onde NÃO há (ex. 13_PAV) o dono valida o N4 grades (Nível 3).
     O recorte de grades é por SHEET do pavimento (não por pilar) — o comparador
     numérico per-sheet é a story AR-1'.E, pendente; o `--par grades` já entrega a
     leitura visual do N4 grades. Na comparação n2xn4 (CIMA+ABCD), grade que aparece
     no N4 = bug de segregação de partes (`grades_no_n4_comparado`), não `n4_a_mais`.
   - **LV:** VC + Face A + Face B — conferir AMBAS as faces; alturas h_A/h_B (bug de
     round-trip conhecido); segmentos Para/Passa.
   - **FV:** parte única, mas SEGMENTAÇÃO é o ponto (viga contínua = N segmentos, ref
     V301 ~16; subdetecção = `segmentacao`/`n4_a_menos`/`interpretacao_n1`).
   - **LAJ:** parte única, HACHURA DE APOIO (N4 costuma faltar = `hachura_ausente`/
     `n4_a_menos`); HLAZ; distinguir hachura de apoio da laje de hachura de vizinho
     (contaminação). Verificado: as 4 classes injetam o foco e resolvem item + imagem.

**Pendência (ainda aberta):**
- **Protocolo de calibração de backend de API** antes de confiar em Gemini/Z.AI/Claude
  API: rodar contra casos de veredito JÁ conhecido (L329 = FAIL real de hachura ausente;
  ≥1 PASS real) e só promover se acertar. Nunca adotar às cegas — foi o erro do NIM.

**Distinção crítica que o harness deixa clara:** `--backend claude` (API Anthropic, com
billing/chave) NÃO é o mesmo que "Claude Code CLI lendo a imagem" (agente no loop, sem
billing, qualidade comprovada). São caminhos diferentes para o mesmo modelo-base — o
modo `cli` é o segundo, e é o padrão.

---

## 5. Bug prioritário descoberto no caminho (maior que a escolha de visão)

`paridade_visual._collect_dxf_segments` NÃO filtra a **linha-sentinela em x=-9000** que
os geradores inserem por-layer (para materializar a layer no DXF), nem os layers
`CARIMBO`/`Folhas`. Efeito: o bbox de render vira `x=[-9000, 2830]`, espremendo o
desenho real num canto e distorcendo a proporção. **Consequência séria:** os
`comparacao.png` dos goldens selados hoje (FV/LAJ/PIL) podem estar deformados — quem
"validou visualmente" olhando essas imagens olhou imagem torta.

Isso é a **prova viva da doutrina §1.5**: o G2 numérico selou, mas a camada visual
estava comprometida → esses goldens são **candidatos, não Arete**. O script antigo
`validar_granular_nim.py` já tinha a exclusão correta (`_ADMIN_LAYERS` + `x < -5000`);
nunca foi portada para o comparador oficial. **Corrigir `paridade_visual.py` (excluir
sentinela `x<-5000` + CARIMBO/Folhas) é prioridade** — contamina a base visual de tudo.
(A fonte HTML do harness não tem esse bug, por não passar pelo `_collect_dxf_segments`.)

---

## 6. Anti-escopo (não reabrir, não construir)

- ❌ NÃO montar squad/skill de visão (vision-forge, BrowserForge, OmniParser +
  Computer Use). É infra de agente-que-age para um problema de agente-que-julga —
  scope creep que contamina o sistema recém-descontaminado.
- ❌ NÃO reabrir Edge+Copilot, stealth/anti-bot, UI-TARS/grounding — §2 fechou.
- ❌ NÃO adotar backend de API sem o protocolo de calibração (§4.3).
- ⏸️ Habilitar billing de Claude API OU Gemini é o único passo que destrava a
  comparação de batch autônomo — decisão de custo do dono, não urgente enquanto a
  validação por agente-no-loop cobre a fase de calibração (volume pequeno, incremental).
```

