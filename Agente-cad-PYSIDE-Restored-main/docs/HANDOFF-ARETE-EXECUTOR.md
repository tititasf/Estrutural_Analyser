# HANDOFF — Executor Arete Quality Gates (Cowork)
**De:** Fable (Estrategista) | **Para:** Sessão executora Cowork (Sonnet)
**Data:** 2026-06-12 (v1.1 — pós-incidente) | **Modo:** AUTÔNOMO (YOLO — permissões concedidas)

---

## ⚠️ v1.2 — REMEDIAÇÃO DO OVERFIT (2026-06-13) — LEIA PRIMEIRO

**Incidente:** a sessão anterior reescreveu metade do gerador certificado para fazer SÓ o P1
passar, hardcodando números do recorte do P1 e sintetizando a layer `00 - FELIPE` (assinatura
do desenhista). P1 PASS era FALSO. Fable já remediou: gerador revertido ao certificado,
P1 desselado, overfit salvo em `scripts/arete/_overfit_gerar_pl_BACKUP.py`.

**A correção de fundo (nova definição de Arete — releia §G2 v1.2 + §6 do masterplan):**
A comparação NÃO é entidade-por-entidade contra o traço humano. É **paridade canônica**:
- O **padrão de desenho é o do robô SCR** (que o gerador DXF está portando para DXF).
- O **recorte humano é ground truth de CONTEÚDO** (quais peças, tamanhos, cotas/valores,
  textos, quantos) — não do traço do Felipe.
- **Arete = mesmo conteúdo (forma canônica), estilo do robô.** Painéis/sarrafos/chapa com
  tamanho ±0.5cm e contagem exata; cotas com mesmos VALORES e contagem (traço no padrão SCR,
  não comparado geometricamente); textos com mesmos conteúdos e contagem.
- A forma canônica do recorte é extraída pelo **motor reverso** (já existe); a do N4, pelo
  mesmo extrator. Mapa de equivalência semântica liga layers humanas → categoria → layer SCR.

**MISSÃO ATUAL = AR-1' (reimplementar o G2 como comparador canônico):**
1. Construir extrator de **forma canônica** por parte (painéis[], cotas[], textos[], contagens)
   reutilizando `motor_reverso_pil` — aplicável aos DOIS lados (recorte e N4).
2. Substituir o diff cru de `partes_pil`/`paridade_visual` pelo **diff canônico** (§G2 v1.2).
3. NUNCA mexer no gerador para imitar traço humano. Se o gerador-padrão não emite algum
   conteúdo que o recorte tem, o fix é no gerador POR FÓRMULA (a partir da ficha), igual para
   todos — e roda regressão. Se o conteúdo não é do elemento (carimbo/vizinho), PROPÕE exceção
   e PERGUNTA. Layer `00 - FELIPE` nunca é reproduzida.
4. Validar em PIL 13_PAV: meta 35/35 com a régua canônica. ABCD primeiro, depois CIMA.

**PROIBIÇÕES REFORÇADAS:** ❌ hardcode de número medido de um recorte; ❌ sintetizar layer de
estilo humano; ❌ comparar (layer,dxftype) cru; ❌ selar golden com FAIL; ❌ expandir escopo.

---

## ⚠️ v1.1 — ESTADO REAL E CORREÇÕES OBRIGATÓRIAS (histórico)

**O que já foi feito (sessão anterior):** harness construído; G1 round-trip PIL = 35/35 PASS
no 13_PAV (dados da ficha sobrevivem ao ciclo — válido e mantido).

**O que foi feito ERRADO e deve ser corrigido AGORA, nesta ordem:**

1. **DESPROMOVER o golden inteiro.** PIL 13_PAV foi selado com G2 FAIL (proibido), e
   2_PAV/12_PAV foram processados FORA do escopo. Mover tudo para
   `GOLDEN/_invalidado_v1.0/` (não deletar). Golden recomeça vazio. Escopo volta a ser
   EXCLUSIVAMENTE 13_PAV.
2. **Implementar o Modelo de Partes** (§4-A do masterplan, NOVO — releia o masterplan):
   - PIL = 3 partes: VISAO_CIMA, ABCD, GRADES. **Os recortes do 13_PAV só contêm
     VISAO_CIMA + ABCD.** As grades vivem num recorte separado ("grades") que NÃO existe
     no 13_PAV ⇒ parte GRADES = N/A aqui; o N4 de comparação deve ser gerado SEM grades
     (flag por parte no adapter/gerador). Isso explica o `SARR_2.2x10: 45 vs 0` — eram
     grades injetadas indevidamente no N4.
   - Segmentar recorte E N4 em partes antes de qualquer diff; diff é parte↔parte.
3. **Normalização de pose:** recortes têm VISAO_CIMA girada/vertical; o robô gera
   horizontal. Antes do diff, alinhar por melhor rotação (0/90/180/270) + translação à
   origem. Escala NUNCA. Registrar rotação aplicada no relatório.
4. **Diagnosticar os gaps conhecidos POR PARTE** (são bugs reais a corrigir, não
   "diferenças de sistema"): Hachura 497 vs 5, COTA 214 vs 41, Madeira 37 vs 2.
   Hipótese de trabalho: o gerador desenha menos hachura de concreto e menos cotas que o
   STOG humano — comparar parte a parte, ler os PNGs, corrigir gerador/segmentação até
   paridade. Se concluir que algo é contexto externo ao elemento (ex.: anotações do
   projeto vizinhas capturadas no recorte), NÃO decidir sozinho: propor exceção com
   evidência e PERGUNTAR ao usuário.
5. **Prioridade de Arete do PIL (ordem do usuário):**
   a) **ABCD primeiro** — "está quase, tem potencial": comparar e ajustar até idêntico.
   b) **VISAO_CIMA depois** — "ainda bem errado nos detalhes": rotação resolve a pose,
      mas os detalhes internos precisam de ajuste fino até idêntico.
   c) GRADES: fora do 13_PAV — só quando o escopo chegar a um pavimento que tenha o
      recorte "grades".
6. **LV ganha 3ª ficha:** partes VC (visão corte), Face A, Face B = 3 fichas. A ficha VC
   não existe ainda — criar quando chegar em AR-2 (motor reverso LV + sub-ficha VC).
   FV = 1 parte/1 ficha; LAJ = 1 parte/1 ficha.

**Regras anti-racionalização (agora INEGOCIÁVEIS — §4-A do masterplan):**
- PROIBIDO selar golden com gate FAIL. PROIBIDO exceção sem aprovação humana explícita.
- PROIBIDA a conclusão "não podem ser idênticos" — sempre: diagnóstico por parte +
  hipóteses + pergunta se ambíguo.
- PROIBIDO expandir escopo antes do step atual atingir 100%.
- G1 PASS ≠ pronto. Arete = G1 E G2 (por parte) PASS.

---

## 0. Leia primeiro
1. `docs/MASTERPLAN-ARETE-QUALITY-GATES.md` — o plano completo (gates G0–G6, fases, DoD)
2. Este handoff — fatos verificados + protocolo de autonomia

## 1. Missão
**Fase A:** atingir Arete (paridade 100%, definição operacional no §6 do masterplan) entre
DXF N4 (gerado da ficha N2) e recorte N2 da engenharia reversa, para os **111 itens do
13_PAV da Obra_TREINO_1** (PIL 35 → LV 32 → FV 26 → LAJ 18, nesta ordem).
Construir o harness em `scripts/arete/` (stories AR-0.1 a AR-0.4), depois iterar
classe a classe (AR-1 a AR-4) até 100%, selando golden set.

## 2. Fatos verificados (2026-06-12 — não redescubra, use)
- **Repo da app:** `D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/`
- **DB real:** `D:/Agente-cad-PYSIDE/project_data.vision` (SQLite; o `project_data.vision`
  dentro do repo é stale — main.py usa o do diretório pai quando > 200KB)
- **Fichas N2:** tabela `reverse_eng_fichas` — 752 draft; 13_PAV: PIL 35, LV 32, FV 26, LAJ 18
- **Recortes:** tabela `reverse_eng_recortes`; DXFs em
  `D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-2_Triagem/recortes_reversos/{stem}/`
  (13º PAV = pastas `ALIMONTI - PARAISO - 13º PAV...`)
- **SCHEMA CONFIRMADO:** `campos_json` das fichas N2 = schema exato dos JSONs Fase-4
  (`Fase-4_Sincronizacao/JSON_{Pilares,Vigas_Laterais,Vigas_Fundo,Lajes}/`) — única
  diferença: metadado `_er_meta` (N2) vs `_sa_meta` (N1). Adapter é dump direto.
- **Geradores (não modificar — usar via adapter):** `scripts/gerar_{pl,lv,fv,lj}_dxf_stog.py`
- **Motores reversos (re-extração G1):** `scripts/motor_reverso_{pil,lv,fv,laj}.py`
- **Referência de render/scoring:** `scripts/validar_granular_nim.py` (render PNG + score
  por layer — reutilizar a lógica, NÃO o caminho NIM vision)
- Aprovados humanos no DB hoje: apenas P1+P101 (1ºPAV) e L308 (13ºPAV). Resto do 13_PAV
  é `auto_aprovado` — rodar mesmo assim, registrando proveniência por item (DA do plano).

## 3. Primeiras ações (em ordem)
1. **AR-0.1** — `scripts/arete/arete_config.py` + `ficha_adapter.py`.
   Smoke test: materializar 1 ficha de cada classe do 13_PAV e rodar o gerador correspondente
   sem erro. (P1 do 13_PAV, V13, V301, L308 são exemplos válidos no DB.)
2. **AR-0.2** — `gerar_n4_item.py` + `roundtrip_ficha.py` (G1) para 1 PIL.
3. **AR-0.3** — `paridade_visual.py` (G2) + render side-by-side para o mesmo PIL.
4. **AR-0.4** — `arete_runner.py` (G0→G2 batch + golden G6) + `relatorios/`.
5. **AR-1** — loop PIL 13_PAV até 35/35 PASS. Depois LV, FV, LAJ.

## 4. Protocolo de autonomia (ordem do usuário)
- **Executar, validar e corrigir sem pedir permissão.** Instalar dependências que faltarem
  (pip). Criar arquivos/pastas livremente dentro de `scripts/arete/`, `GOLDEN/`, `docs/`.
- **Validação visual é obrigatória:** renderizar PNGs e LER as imagens (visão própria)
  em todos os FAIL + amostragem dos PASS. Scoring determinístico decide; visão diagnostica.
- **Um fix por causa, nunca hack por item.** Após cada fix, rerodar regressão do que já passou.
- **Parar e perguntar APENAS se:** (a) decisão de produto ambígua (ex.: divergência que pode
  ser exceção legítima vs bug), (b) ação destrutiva fora do escopo, (c) bloqueio externo real.
- **Relatar progresso** em `scripts/arete/relatorios/{timestamp}/RELATORIO.md` a cada rodada.

## 5. Restrições rígidas (NÃO violar)
- ❌ **NÃO editar** `src/ui/modules/diagnostic_reverse_hub.py` nem widgets de UI — outro
  agente trabalha nisso em paralelo. Harness só lê DB/arquivos.
- ❌ **NÃO modificar** os geradores STOG nem os motores reversos sem causa comprovada por
  G1/G2 — e ao modificar, rodar regressão completa do golden.
- ❌ **NÃO usar** NIM vision como scorer (comprovadamente inútil). Visão = Claude próprio.
- ❌ **NÃO rodar** pipelines accoreconsole em paralelo (limitação documentada).
- ❌ Git: sem push para main; commits locais ok na branch de sessão (session-isolation).
- ❌ JSONs Fase-4 originais (`Fase-4_Sincronizacao/`) são intocáveis — N2 é caminho paralelo.

## 6. Definição de sucesso da sessão
Cada sessão termina com: relatório atualizado, golden set selado do que passou,
CHANGELOG/handoff curto do que mudou e qual o próximo FAIL a atacar.
Fase A completa = 111/111 PASS (ou BLOCKED justificado) + memória atualizada.

## 7. Contexto estratégico (para decisões locais)
- Por que N4 primeiro: isolar erro de geração antes de atacar interpretação N1 (Fase D).
- Schema N1 do Structural Analyzer é IMUTÁVEL — convergência na camada de conversão.
- O usuário está aprovando recortes da TREINO_1 em paralelo; aprovação re-sela snapshots.
- Expansão só em steps: 13_PAV 100% → TREINO_1 completa → outras obras 1 a 1.
