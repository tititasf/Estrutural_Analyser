# Backlog Validation — App de Consulta Pública CAD-ANALYZER

> **Fase:** Product Owner / Validação de Backlog (gate pré-stories)
> **Autor:** Pax (AIOS Product Owner) — para CEO-Planejamento (Athena)
> **Fontes validadas:** `project-brief.md` (Atlas), `prd.md` (Morgan), `architecture.md` (Aria), `front-end-spec.md` (Uma)
> **Data:** 2026-07-11
> **Veredito:** **GO — score 8.5/10** (mínimo 7). Backlog aprovado para breakdown em stories pelo @sm, com 3 should-fix não-bloqueantes.

---

## 1. Sumário Executivo

Os quatro artefatos são **fortemente consistentes e convergentes**. Cada documento a jusante não apenas respeita o anterior — ele o **reforça** onde encontrou risco:

- A **arquitetura** endureceu o PRD: onde o PRD dizia "reusar FastAPI com endpoints separados", a arquitetura entregou **isolamento físico** (processo separado, DB próprio `mode=ro`, padrão Publisher/Reader) — segurança *by construction*, não hardening posterior.
- O **design** respeitou explicitamente a correção arquitetural mais crítica: **conteúdo client-side + `noindex` + zero SSR do dado privado** (front-end-spec §12, referenciando architecture §6.1). Nenhuma ficha de cliente entra em cache de CDN/edge nem é indexável. Esta é exatamente a armadilha que a tarefa de validação pediu para verificar — e está **coberta**.
- O **escopo MVP** é idêntico e testável nos quatro documentos: Busca por ID → Ficha N1/N3 (SVG zoom/pan) → Painéis LV → PWA offline/UX de campo → Segurança anti-enumeração. 3D, QR e materiais genéricos (PL/FV/LAJ) são unânime e explicitamente **Fase 2**.

Duas incertezas do brief foram **fechadas por verificação de código** na fase de arquitetura (não são mais riscos abertos):
1. **N3/N1 SVG já existe** pronto para render (`ficha_reader.py` → `foto_n1`/`foto_n3`).
2. **Contrato LV já está materializado em disco** (`JSON_Vigas_Laterais/*.json`) — elimina o acoplamento com o motor PySide que era o maior risco técnico do MVP.

O backlog está pronto para virar stories. Há **1 gap estrutural** que precisa ser explicitado no backlog (o **Publisher** — componente interno essencial não nomeado como epic/story no PRD) e **2 pontos de alinhamento documental** (should-fix), nenhum deles bloqueante.

---

## 2. Análise de Consistência (cruzamento dos 4 documentos)

### 2.1 Arquitetura respeita o PRD?

| Requisito PRD | Cobertura na Arquitetura | Veredito |
|---|---|---|
| NFR1 — IDs opacos, não-sequenciais | Token base62 CSPRNG 10-char, table-backed, revogável (§3) | ✅ Reforça (revogável + preparado p/ QR) |
| NFR2 — autorização server-side é defesa primária | Autorização *por construção*: só existe o que o Publisher projetou; sem "usuário" a furar (§5.1.2) | ✅ Reforça (elimina classe inteira de bug) |
| NFR3 — rate limiting + logging de enumeração | Cloudflare + app (`slowapi`), detecção de rajada de 404, `public_audit.db` (§5.2/§5.3) | ✅ Atende |
| NFR4 — projeção mínima, controllers fisicamente separados | Processo/porta/DB separados; blacklist de campos comerciais/pessoais verificável por teste (§3.2/§5.1.4) | ✅ Reforça (isolamento físico > lógico) |
| NFR5 — zero vazamento cross-cliente | Obra não-publicada é 404 *by construction*; fronteira A-vs-B estrutural (§2) | ✅ Atende (tolerância zero suportada) |
| NFR6/NFR7 — performance 3G/4G, SVG denso | SVG desacoplado do JSON, CDN imutável por content-hash, `svgo` no publish-time (§6.2) | ✅ Atende |
| NFR8 — PWA offline último item + status | app-shell SSG + service worker cache-first (§6.1) | ✅ Atende |
| FR1/FR5 — busca unificada obra/item | `/resolve/{code}` com `kind` (§3.1/§4) | ✅ Atende |
| FR2/FR3 — ficha N1/N3 SVG | Reuso de `ficha_reader`, endpoint `/svg/{nivel}` (§4.1) | ✅ Atende |
| FR4 — painéis LV | Lê JSON já persistido, zero import do motor (§1.2/§4.1) | ✅ Atende (e derruba risco de acoplamento) |
| FR6 — 404 indistinto anti-enumeração | 404 genérico **constante no tempo** (evita timing oracle) (§5.1.6) | ✅ Reforça |

**Conclusão:** a arquitetura não contradiz nenhum requisito do PRD; em 6 pontos ela **excede** a exigência, sempre na direção mais restritiva/segura — que é a direção correta para um produto cujo risco dominante é IDOR/BOLA.

### 2.2 Design respeita a arquitetura?

| Ponto de checagem crítico | Design (front-end-spec) | Veredito |
|---|---|---|
| **Sem SSR/SSG do dado privado** | §12 explícito: conteúdo client-side, `noindex,nofollow`, app-shell SSG só do chrome | ✅ Alinhado |
| Rótulos neutros (`obra_rotulo`, `pavimento_label`) — nunca `item_id`/`pavimento` crus | §3.2, §5.3, §5.5 usam só rótulos públicos da API | ✅ Alinhado |
| SVG por endpoint dedicado (não embutido no JSON) | §6.1 consome `/svg/{nivel}` lazy | ✅ Alinhado |
| 404 genérico único (anti-enumeração na própria UI) | §4.1, §5.2, Princípio 5 "silêncio seguro" | ✅ Alinhado |
| Estado 429/bloqueio (rate-limit da arquitetura) | §5.2 tela "Bloqueado" com contagem | ✅ Alinhado |
| Painéis LV do JSON persistido (`panels[].width...`) | §5.4 consome `/paineis-lv` com o schema exato | ✅ Alinhado |
| QR desabilitado, layout preparado p/ F2 | §5.1, afordância §7.5 (botão "em breve") | ✅ Alinhado |

**Conclusão:** o design é **arquitetura-consciente**. Não assume nenhuma capacidade que a arquitetura não entregue. O ponto mais delicado (não indexar/não SSR de dado privado) foi tratado como requisito de primeira classe.

### 2.3 Escopo MVP coerente nos 4?

| Feature | Brief | PRD | Arch | Design | Coerência |
|---|---|---|---|---|---|
| Busca por ID | MVP | MVP (Must) | Epic 1 | Tela 1 | ✅ |
| Ficha N1/N3 SVG zoom/pan | MVP | MVP (Must) | Epic 2 | Telas 3/6 | ✅ |
| Painéis LV | incerto (conf. baixa) | **MVP (Should)** — dado existe | Epic 3 | Tela 5.4 | ✅ resolvido |
| PWA offline + UX campo | MVP | MVP | Epic 4 | §7/§8 | ✅ |
| Segurança anti-enum | MVP (crítico) | MVP (Must, NN) | Epic 1 transversal | §5/§9 | ✅ |
| 3D real | F2 | F2 | F2 (A5) | fora | ✅ |
| QR-code | F2 | F2 | preparado F2 | botão "em breve" | ✅ |
| Materiais genéricos PL/FV/LAJ | F2 | F2 (Won't) | F2 (A5) | fora | ✅ |

**Conclusão:** convergência total. A única evolução de escopo entre brief→PRD (LV de "incerto" para "dentro do MVP") foi **justificada por evidência** (o dado existe) e confirmada pela arquitetura.

---

## 3. Gaps Identificados

> Classificação: 🔴 estrutural (precisa entrar no backlog) · 🟡 alinhamento documental (should-fix) · 🟢 fechado/não-bloqueante.

### 🔴 G1 — O "Publisher" não é nomeado no Epic List do PRD (gap estrutural)
A arquitetura introduz o **Publisher** (§2, §3.3): componente **interno autenticado** que, no ato de publicar uma obra, (a) minta os códigos opacos, (b) denormaliza a projeção mínima para `public_consulta.db`, (c) roda `svgo`, (d) controla revogação/republish. **Sem o Publisher, não existe um único código para consultar** — ele é pré-requisito absoluto de todo o MVP. Porém o Epic List do PRD (§11) só menciona "código de consulta opaco" dentro do Epic 1 sem nomear o Publisher como trabalho próprio, e ele vive na **zona interna** (toca `portal_data.db`, `DADOS-OBRAS`, exige auth) — contexto de segurança diferente da API pública.
**Ação:** tornar o Publisher um conjunto de stories **explícito e primeiro** dentro do Epic 1 (ver §4). É o item de maior risco de ser esquecido no breakdown.

### 🔴 G2 — Produção dos rótulos neutros (`obra_rotulo`/`pavimento_label`) sem dono definido
Design (§13.1 ação 3) explicitamente sinaliza: *"o design assume que já vêm seguros (sem nome de cliente)"*. Arquitetura (§3.2) define default anônimo mas exige o dono **optar ativamente** por um rótulo seguro. **Quem gera e valida esses rótulos?** É responsabilidade do Publisher + decisão do dono. Se ninguém produzir rótulos seguros, ou a UI mostra "Obra ·· A3F" (aceitável) ou alguém expõe o nome do cliente (viola R2/NFR4).
**Ação:** incluir "geração + validação de rótulos neutros pelo dono" como task do Publisher (Epic 1). Marcar como decisão de dono no gate.

### 🔴 G3 — `public_audit.db` / log de enumeração é NFR3 mas não tem story explícita
NFR3 exige "logging de padrões de enumeração" e o KPI "enumeração detectada/bloqueada = 100%". A arquitetura resolve com `public_audit.db` RW separado (§5.3) — a **única escrita permitida** na zona pública. É um artefato concreto com regra de segurança específica, mas não aparece como item no Epic List do PRD.
**Ação:** incluir como task de segurança do Epic 1 (a instrumentação da detecção de rajada + o alvo do KPI vivem aqui).

### 🔴 G4 — Configuração de borda (Cloudflare Tunnel + WAF + rate-limit + CORS) é infra/@devops
A arquitetura (§5.2, §7) depende de Cloudflare para TLS, CDN de SVG, rate-limit de borda, WAF e CORS travado no domínio Vercel. O design assume que o estado 429 existe. Isso é trabalho de **infra/@devops**, não de front nem de backend de aplicação, e não está nomeado no backlog.
**Ação:** task de infra no Epic 1 (Cloudflare Tunnel + regras) — dependência de deploy, delegável a @devops. A porta 21390 deve ser registrada no controle de portas do projeto.

### 🟡 G5 — Deriva documental: PRD §7 diz LV vem de `lv_generation_contract.py`; arquitetura corrigiu para ler JSON em disco
PRD Technical Assumptions §7 e §5.2 ("consumindo o `lv_generation_contract` já computado") sugerem importar/executar o módulo. A arquitetura (§1.2/§4.1) **verificou** que o contrato já está materializado em `JSON_Vigas_Laterais/*.json` e decidiu **ler o JSON sem importar o módulo** (zero acoplamento PySide). Não é contradição — é refinamento por evidência — mas o texto do PRD pode induzir o @sm/@dev ao caminho errado (mais custoso e acoplado).
**Should-fix:** anotar no PRD que a fonte canônica de LV é o JSON persistido (arquitetura é autoritativa neste ponto).

### 🟡 G6 — Deriva documental: PRD "reuso do FastAPI existente" vs arquitetura "NOVA API dedicada"
PRD §7 fala em "reaproveitar o FastAPI existente expondo endpoints read-only separados"; a arquitetura decide **novo processo/porta/DB dedicados** (§0/§2). São compatíveis (o PRD já pedia "separados"), mas um leitor apressado pode interpretar "reuso" como "mesma app" — exatamente o que a arquitetura rejeita por segurança (§1.5).
**Should-fix:** o breakdown deve seguir a arquitetura (processo isolado), não a leitura literal do PRD §7.

### 🟢 G7 — Extração de `ficha_reader.py` para módulo compartilhado toca o portal existente
Arquitetura §4.1/§8 propõe extrair `ficha_reader.py` para módulo compartilhado (alvo) com **escape hatch**: copiar com teste de paridade no MVP. Toca código do portal interno (backward-compat), então precisa de story própria com teste de paridade. Não é gap de cobertura (a arquitetura já resolveu com escape hatch), mas é uma **decisão de story** para o @sm.
**Ação:** story em Epic 2 com escolha explícita (extrair vs copiar-com-paridade); default MVP = copiar-com-paridade para não bloquear.

### 🟢 G8 — Dependências de dado (fechadas) e itens de negócio (paralelos)
- Disponibilidade de N3 SVG e LV JSON: **verificada na arquitetura** → risco fechado (era o Immediate Action #1 do brief).
- Taxonomia/unicidade do ID: **resolvida** (token table-backed) → fechada.
- **Validação jurídica/comercial** de "acesso livre por ID" (PRD §12.3, R2): decisão de dono já tomada; recomendação de validação **em paralelo, não-bloqueante**. Rastrear como risco de negócio, não como story de dev.
- **Teste de campo com ≥5 operadores em 3 obras** (NFR10): gate manual de saída do MVP, precisa de protótipo navegável antes (design §13.1 ação 4). Não é story de código — é atividade de aceite (ver DoD de saída).

---

## 4. Backlog Final do MVP — Epics, DoD e Prioridade

Mantenho os **4 epics** propostos por arquitetura/PRD, com **Epic 1 expandido** para tornar o Publisher, o audit e a infra de borda **explícitos** (fechando G1/G3/G4). Ordem de construção alinhada ao RICE do PRD §5.2.

> **Regra transversal:** Segurança **não** é epic final. A instrumentação de rate-limit/404-genérico/audit entra desde a **primeira** story do Epic 1. A **suíte de segurança verde (architecture §5.4) é o único gate inegociável de release.**

### EPIC 1 — Fundação, Publisher & Consulta Segura por ID  ·  **Must · P0**
Cobre PRD Epic 1 + NFR1–NFR5 + G1/G2/G3/G4. Entrega uma **consulta segura ponta-a-ponta** (mesmo que só de identificação) antes de qualquer render de ficha.

**Escopo de stories (sugestão para @sm — vertical slices):**
1. Publisher interno autenticado: minta token base62 CSPRNG, denormaliza projeção mínima, upsert preservando `code` no republish, revogação por `code`/`publish_batch` (G1).
2. Geração + validação de rótulos neutros (`obra_rotulo`/`pavimento_label`), default anônimo, opt-in do dono (G2).
3. Schema `public_consulta.db` com blacklist de campos comerciais/pessoais; passo `svgo` no publish-time.
4. Processo API pública isolado (`:21390`, bind 127.0.0.1, `mode=ro`), sem credencial do portal; endpoint `/resolve/{code}` (obra/item) + `/health`.
5. 404 genérico **constante-no-tempo**; anti-path-traversal (`is_relative_to` DADOS-OBRAS).
6. Rate-limit no app + detecção de rajada; `public_audit.db` (única escrita controlada) (G3).
7. Infra de borda: Cloudflare Tunnel + WAF + rate-limit + CORS travado no domínio Vercel; registrar porta 21390 (G4 — delegável a @devops).
8. Suíte de segurança (architecture §5.4) como gate.

**Definition of Done (Epic 1):**
- [ ] Publisher publica uma obra e minta códigos de obra + item; republish preserva `code`; revogação funciona.
- [ ] Rótulos neutros verificados pelo dono; nenhum nome de cliente atravessa a fronteira.
- [ ] API pública é **processo separado**, `mode=ro`, sem credencial do portal; **nenhum** verbo de escrita no router (POST/PUT/DELETE → 405).
- [ ] `/resolve` distingue `kind` obra/item; código inexistente/malformado/revogado/fora-de-escopo → **404 idêntico e tempo constante**.
- [ ] **Suíte de segurança verde:** enumeração de 1000 códigos → 100% 404 + rate-limit dispara + zero vazamento; obra A nunca resolve item de B; path traversal barrado; asserção de schema sem colunas da blacklist; prova de `mode=ro` (escrita → `OperationalError`).
- [ ] Rate-limit + audit de enumeração instrumentados (KPI "100% das rajadas barradas" mensurável).
- [ ] API pública **nunca** abre `portal_data.db` nem `project_data.vision` (teste/asserção).

### EPIC 2 — Ficha do Item (N1/N3)  ·  **Must · P1**
Cobre PRD Epic 2 + FR2/FR3 + G7. Depende do Epic 1 (resolução de código).

**Escopo:** reuso de `ficha_reader` (extrair OU copiar-com-paridade — G7); `/ficha/{code}` (projeção mínima, SVG por URL não embutido); `/svg/{nivel}` (`image/svg+xml`, `Cache-Control: immutable` + ETag content-hash); `/obra/{code}` (índice pav→item só com `code`+título+tipo); viewer SVG frontend (zoom/pan/double-tap, papel branco sempre).

**Definition of Done (Epic 2):**
- [ ] Ficha renderiza N1 e N3 em SVG com zoom/pan fluido em mobile; abas dinâmicas (só as com dado).
- [ ] JSON da ficha carrega **URLs** de SVG (payload leve), não SVG embutido; SVG servido por endpoint próprio, cacheável imutável por content-hash.
- [ ] Se caminho "copiar `ficha_reader`": **teste de paridade** vs portal verde. Portal interno intocado no fluxo existente.
- [ ] Navegação obra→pavimento→item funciona; resposta nunca contém `item_id`/`pavimento` crus.
- [ ] N3 ausente (`svg.n3=null`) tratado (aba não aparece; ficha não quebra).

### EPIC 3 — Lista de Painéis LV  ·  **Should · P2**
Cobre PRD Epic 3 + FR4. Depende do Epic 2 (ficha). **Primeira a deslizar sob pressão de prazo** (AUTO-DECISION do PRD §5.2) sem descaracterizar o MVP.

**Escopo:** `/ficha/{code}/paineis-lv` lê `JSON_Vigas_Laterais/{LV-PARA,LV-PASSA}/{beam}_{A,B}.json`, projeta campos públicos (`panels[].width/height1/height2/panel_type`, `total_width`, `h_section`), agrupa por lado; flag `tem_lv`; UI tabela/cartão com reflow.

**Definition of Done (Epic 3):**
- [ ] Painéis LV exibidos agrupados por lado; `tem_lv=false` oculta aba + nota neutra "Lista de painéis não disponível".
- [ ] **Zero import** de `lv_generation_contract.py`/PySide — lê só JSON persistido; se JSON ausente, nunca inventa.
- [ ] Sem scroll horizontal: reflui para cartão empilhado em < 380px; largura em destaque.

### EPIC 4 — UX de Campo & PWA Offline  ·  **Must (UX/a11y) + Should (offline) · P1–P2 (transversal)**
Cobre PRD Epic 4 + NFR8/NFR9/NFR10 + design §7–§12. **App-shell começa em paralelo ao Epic 1**; hardening de a11y/offline ao longo.

**Escopo:** app-shell SSG + service worker (cache-first SVG/shell, network-first ficha JSON, último item offline); badge de status; tokens alto-contraste (light/dark/sol-forte) WCAG AA; alvos ≥56px; histórico local + colar/clipboard; 5 telas + 6 estados; `noindex` + conteúdo client-side.

**Definition of Done (Epic 4):**
- [ ] PWA installable; último item consultado funciona offline com banner âmbar; badge de status ao vivo.
- [ ] **WCAG 2.1 AA verificado:** contraste (valores §8), alvo ≥56px, foco visível, teclado 100%, leitor de tela (VoiceOver/TalkBack); axe/Lighthouse a11y ≥ 95 no CI.
- [ ] 5 telas + 6 estados (loading/offline/404/429/svg-error/lv-absent) implementados.
- [ ] **Conteúdo client-side + `noindex` confirmado** — nenhuma ficha em cache de CDN/edge nem indexável (regra de segurança, não só SEO).

### Gate de Saída do MVP (DoD cross-cutting — antes de liberar)
- [ ] **Suíte de segurança verde** (Epic 1 §5.4) — **único gate inegociável**.
- [ ] Time-to-Ficha mediana < 3s (4G), funcional em 3G (< 8s).
- [ ] `noindex`/sem-SSR de dado privado confirmado em produção.
- [ ] **Teste de campo com ≥5 operadores reais em ≥3 obras**, N1/N3 + LV lidos na 1ª tentativa, **zero acesso cross-cliente** (NFR10 / MVP Success Criteria §4.3).
- [ ] Porta 21390 registrada no controle de portas; deploy da API isolado do portal.

**Ordem recomendada:** Epic 1 (fundação/segurança) → Epic 2 (núcleo de valor N1/N3) → Epic 3 (LV, primeira a deslizar). Epic 4 **transversal**, iniciando o app-shell em paralelo ao Epic 1. Convergente com RICE do PRD.

---

## 5. Gate de Validação (score 0–10)

| Dimensão | Peso | Nota | Racional |
|---|---|---|---|
| Consistência entre os 4 docs | alto | **9.5** | Convergência total; arquitetura reforça PRD; design respeita "sem SSR do dado privado" explicitamente |
| Completude de cobertura | alto | **8.5** | Forte; dependências de dado fechadas por verificação. Publisher/audit/infra de borda precisavam ser explicitados (feito aqui) |
| Acionabilidade para stories | alto | **9.0** | Arquitetura decisiva (schemas, endpoints, contratos); design com 12 componentes e estados. Pronto p/ vertical slices |
| Sequenciamento/dependências | médio | **9.0** | Clara: Epic 1 fundação → 2 → 3; Epic 4 transversal. Sem ciclos |
| Tratamento de risco | alto | **9.5** | Risco #1 (IDOR/BOLA) tratado como feature de 1ª classe; todos os riscos com mitigação e owner |
| Itens abertos remanescentes | médio | **7.5** | Rótulos neutros (dono), validação jurídica (paralela), protótipo+teste de campo (pendentes); nenhum bloqueia o breakdown |

**Score final (ponderado): 8.5 / 10** → **≥ 7 → GO / PROSSEGUIR.**

**Decisão:** **APROVADO para breakdown em stories pelo @sm (River).**
Condições (should-fix, não-bloqueantes):
1. Tornar o **Publisher** stories explícitas e primeiras no Epic 1 (G1) — já refletido no §4.
2. Reconciliar deriva documental do PRD §5.2/§7: fonte canônica de LV = **JSON persistido**; API pública = **processo dedicado** (G5/G6) — arquitetura é autoritativa.
3. Confirmar com o dono os **rótulos neutros** e a **validação jurídica em paralelo** (G2/G8) — sem bloquear.

---

## 6. Handoff

- **@sm (River):** breakdown dos 4 epics em stories (vertical slices), começando pelo Epic 1 com o Publisher explícito. Cada story herda o DoD do seu epic + o gate cross-cutting de segurança.
- **@devops (Gage):** infra de borda do Epic 1 (Cloudflare Tunnel/WAF/rate-limit/CORS), registro da porta 21390, deploy isolado.
- **@dono/@po:** validação dos rótulos neutros; validação jurídica de "acesso livre por ID" em paralelo.
- **@ux (Uma) + @po:** protótipo navegável das 5 telas → habilita o teste de campo com ≥5 operadores (gate de saída do MVP).

---

*Validação de backlog por Pax (AIOS Product Owner). Método: cruzamento de consistência dos 4 artefatos, mapeamento de gaps (4 estruturais fechados no backlog, 2 should-fix documentais, 2 fechados/paralelos), estruturação de 4 epics com DoD e prioridade, gate ponderado 0–10. Veredito: GO 8.5/10.*
