# PRD — App de Consulta Pública CAD-ANALYZER (Consulta de Fôrmas por ID)

> **Fase:** Strategy / PRD
> **Autor:** Morgan (AIOS PM) — para CEO-Planejamento (Athena)
> **Fonte:** `project-brief.md` (Atlas / AIOS Analyst, 2026-07-11)
> **Data:** 2026-07-11
> **Status:** Draft para revisão do Product Owner (@po Pax)
> **Modo de elaboração:** YOLO — decisões autônomas documentadas inline como `[AUTO-DECISION]`

---

## 1. Goals and Background Context

### 1.1 Goals

- Transformar um **ID de elemento de fôrma** numa consulta instantânea, read-only, utilizável no chão de fábrica e no canteiro — fonte única e sempre atualizada da especificação.
- Entregar a ficha N1 (leitura humana/SA) e N3 (desenho robô/CAD) em **SVG de alta fidelidade**, renderizável direto no navegador, com zoom/pan mobile fluido.
- Expor a **lista de painéis de Vigas Laterais (LV)** — dado que já existe no pipeline (`lv_generation_contract.py`) — como valor imediato para o funcionário de fôrma.
- Garantir **acesso livre pela internet, sem cadastro** (decisão de produto já tomada pelo dono), com segurança anti-enumeração **não-negociável**: IDs opacos, rate limiting e zero vazamento cross-cliente.
- Entregar uma **PWA mobile-first de campo** (alto contraste para sol forte, alvos de toque grandes para luvas, cache offline do último item, indicador de status de conexão).
- Ativar um canal de consumo público para dados que já existem e já são validados, sem custo marginal de geração de conteúdo.

### 1.2 Background Context

Hoje a especificação técnica de fôrmas (fichas N1/N3, desenhos SVG) vive num portal interno autenticado (FastAPI + Jinja2) desenhado para triagem/validação, acessível apenas à equipe. Cliente, funcionário de fôrma e construtor de campo não têm acesso rápido à "verdade" do item que estão produzindo ou montando — dependem de PDFs desatualizados, prints de WhatsApp e ligações. O retrabalho de fôrma por especificação errada/desatualizada é a categoria de perda mais cara (material + mão de obra + atraso).

O pipeline CAD-ANALYZER **já produz** fichas validadas e desenhos N3 gerados por robô, e **já expõe** endpoints que retornam JSON com `foto_n1` e `foto_n3` como SVG embutido, prontos para renderizar no navegador (ex.: `/obras/{id}/n1/{classe}/{item_id}?pavimento=X`). O `obra_id` já é um UUID real e não-sequencial. O custo marginal de transformar esse dado existente num produto de campo é baixo; o valor é alto. Esta PRD define um MVP deliberadamente estreito — **read-only 2D com segurança forte** — deixando viewer 3D e QR-code para fases posteriores.

### 1.3 Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2026-07-11 | 0.1 | PRD inicial a partir do project-brief do Analyst; Open Questions de dado/acesso/ID resolvidas contra código real | Morgan (PM) |

---

## 2. Personas (reuso do Analyst)

### P1 — Funcionário de Fôrma (fábrica/oficina) — **Primária**
Operador de produção que monta a fôrma física a partir da especificação. Baixa tolerância a UI complexa; mãos enluvadas; poeira e luz variável. Trabalha hoje de desenho impresso/PDF em revisão possivelmente antiga. **Precisa:** ver rápido e sem erro o N3, a lista de painéis e as cotas do item; certeza de que é a versão correta. **UX derivada:** alto contraste, fonte grande, alvos ≥48px, N3 com zoom fluido, tolerante a conexão instável.

### P2 — Construtor no Canteiro — **Secundária**
Encarregado/mestre de obra que recebe e posiciona os elementos. Ambiente externo (sol forte), conectividade ruim, movimento constante. Hoje confere peça contra papel/memória e liga para a fábrica. **Precisa:** confirmar no local que a peça corresponde à especificação (posição, dimensões, materiais), consultando por ID escrito na peça/etiqueta. **UX derivada:** offline-first robusto, busca por ID como fluxo primário.

### P3 — Cliente — **Terciária**
Contratante/engenheiro do cliente consultando o que foi especificado; provavelmente desktop ou mobile em ambiente controlado. **Precisa:** autonomia para consultar especificação sem depender de suporte. **Tensão crítica:** cliente A **não pode** ver dados da obra do cliente B — condiciona toda a estratégia de segurança de acesso.

---

## 3. Requirements

> Convenção: `FR` = requisito funcional, `NFR` = requisito não-funcional. Requisitos marcados **[MVP]** entram no escopo mínimo; **[F2]/[F3]** são fase posterior; **[NN]** = não-negociável.

### 3.1 Functional Requirements

- **FR1 [MVP]:** O sistema deve prover um **campo de busca único** que aceite um ID/código de consulta e resolva para a visão correta: ID de obra → lista de pavimentos/itens; ID/código de item → ficha do item.
- **FR2 [MVP]:** Ao resolver um ID de item, o sistema deve renderizar a **ficha read-only** com: identificação (tipo de elemento — pilar/laje/viga lateral/viga de fundo — obra, pavimento, posição), **N1** (interpretação humana/SA) e **N3** (desenho robô/CAD).
- **FR3 [MVP]:** O sistema deve renderizar o **SVG de `foto_n1` e `foto_n3`** direto no navegador (consumindo o JSON já exposto pelo portal), com **zoom e pan** fluidos em mobile. Nenhuma conversão de formato de desenho é necessária.
- **FR4 [MVP]:** Para itens de **Viga Lateral (LV)**, o sistema deve exibir a **lista de painéis estruturada** (largura de cada painel e distribuição em módulos STOG 244/122cm), consumindo o `lv_generation_contract` já computado pelo motor SA.
- **FR5 [MVP]:** Quando um ID resolver para uma **obra**, o sistema deve listar os pavimentos e, dentro deles, os itens consultáveis, permitindo navegação até a ficha.
- **FR6 [MVP]:** O sistema deve tratar **IDs inválidos, inexistentes ou fora de escopo** de forma indistinta (mesma resposta genérica "não encontrado"), sem revelar se um ID existe — mitigação de enumeração.
- **FR7 [MVP]:** A busca deve tolerar variações triviais de digitação do código (trim de espaços, case-insensitive) sem por isso permitir adivinhação estrutural do ID.
- **FR8 [F2]:** O sistema deve exibir uma **lista de materiais genérica** para todas as classes (PL/FV/LAJ além de LV). *Fora do MVP: o dado estruturado ainda não existe para FV/PL; exige computação nova a montante.*
- **FR9 [F2]:** O sistema deve permitir abrir a ficha via **leitura de QR-code** impresso na peça física.
- **FR10 [F2]:** O sistema deve exibir um **mini viewer 3D** interativo (glTF/GLB) do elemento.
- **FR11 [F3]:** O sistema deve exibir **status de produção ao vivo** do elemento (fabricação → transporte → instalação).
- **FR12 [F3]:** O sistema deve permitir **captura as-built** em campo (foto/nota/checklist), sincronizada ao portal interno.

### 3.2 Non-Functional Requirements

**Segurança (crítico — a coluna vertebral desta PRD)**

- **NFR1 [MVP][NN]:** Todo identificador exposto publicamente deve ser **opaco e não-sequencial** (UUID ou slug com token). **É proibido** expor IDs adivinháveis do tipo `obra_id=1,2,3…`. O `obra_id` UUID atual satisfaz isto; o **pavimento** (hoje string tipo "TERREO"/"13_PAV", não único globalmente) e o **item** (string tipo "P1"/"L101") **não** podem ser expostos crus — deve haver um **código de consulta opaco por item** (decisão de detalhe da fase de Architecture, requerida por esta PRD).
- **NFR2 [MVP][NN]:** A **autorização de escopo server-side** é a defesa primária, não a ofuscação. Mesmo com ID opaco, o backend deve validar que a resposta contém apenas o item solicitado, jamais permitir varredura de itens vizinhos por incremento.
- **NFR3 [MVP][NN]:** Todo endpoint de consulta por ID deve ter **rate limiting** por IP/sessão e **logging de padrões de enumeração** (rajadas de "não encontrado", varredura sequencial). Detecção de enumeração deve poder disparar bloqueio temporário.
- **NFR4 [MVP][NN]:** A resposta pública deve ser uma **projeção mínima**: nunca expor dado comercial, pessoal ou contratual do cliente. Os endpoints públicos devem ser **fisicamente separados** dos controllers internos autenticados — nunca reusar o mesmo controller sem checagem de autorização.
- **NFR5 [MVP][NN]:** **Zero incidentes de vazamento cross-cliente.** Um cliente jamais deve, por qualquer manipulação de ID/URL, acessar dados de obra de outro cliente. Métrica de tolerância zero.

**Performance & Disponibilidade**

- **NFR6 [MVP]:** **Time-to-Ficha** (do "digitei o ID" ao "vejo a ficha renderizada") deve ter mediana **< 3s em 4G** e ser **funcional em 3G** (alvo < 8s em 3G).
- **NFR7 [MVP]:** SVGs N3 densos devem ser servidos otimizados (via CDN, lazy-load, cache), evitando travamento de render em aparelhos Android de baixo custo.
- **NFR8 [MVP]:** A app deve ser **PWA installable** e funcionar **offline para o último item consultado** (service worker + cache), com **indicador claro de status de conexão/sync**.

**Usabilidade de Campo (Acessibilidade)**

- **NFR9 [MVP]:** UI de **alto contraste** legível sob luz solar direta; tipografia grande; **alvos de toque ≥ 48px** (operáveis com luvas). Meta de conformidade: **WCAG 2.1 AA** para contraste e tamanho de alvo.
- **NFR10 [MVP]:** Fluxo utilizável **sem treinamento formal** — um funcionário de fôrma e um construtor devem completar a consulta na primeira tentativa (validado em teste com ≥5 usuários reais).

**Plataforma & Manutenção**

- **NFR11 [MVP]:** Suporte a **Chrome/Android e Safari/iOS recentes**; mobile-first degradando graciosamente para desktop (persona cliente). WebGL 2.0 **não** é requisito do MVP (só entra com o 3D da F2, sempre com fallback 2D).
- **NFR12 [MVP]:** A app deve consumir **dados vivos** do pipeline (via projeção pública), não cópias — garantindo que o campo nunca trabalhe de revisão antiga.

---

## 4. MVP Scope (explícito e testável)

### 4.1 Dentro do MVP
1. Busca unificada por ID (obra/pavimento/item) → roteamento correto (FR1, FR5).
2. Ficha read-only N1 + N3 em SVG com zoom/pan (FR2, FR3).
3. Lista de painéis **LV** estruturada (FR4) — dado já existe.
4. PWA installable + cache offline do último item + indicador de status (NFR8).
5. UX de campo: alto contraste, fonte grande, alvos ≥48px (NFR9).
6. Segurança anti-enumeração completa: IDs opacos, autorização server-side, rate limiting, projeção mínima (NFR1–NFR5).

### 4.2 Fora do MVP (explícito)
- **Viewer 3D real** → Fase 2 (confirmado). No MVP, no máximo placeholder/imagem estática; **sem** three.js/glTF.
- **Lista de materiais genérica** para PL/FV/LAJ → Fase 2 (dado estruturado não existe hoje; exige trabalho a montante). **A lista de painéis LV NÃO está fora — ela entra no MVP** porque o dado já existe.
- Leitura de **QR-code** → Fase 2 (desenhar o código de consulta já pensando nisso).
- Captura de dados em campo (fotos, checklists ITP/ITC, markup as-built) → Fase 3.
- Edição de qualquer dado (app é **100% read-only** no MVP).
- Login social / contas de cliente / permissionamento granular por usuário → não previsto (acesso é livre por ID opaco, por decisão do dono).
- App nativo iOS/Android em loja (PWA cobre "download via link").
- Notificações, versionamento visível, histórico de revisões.

### 4.3 MVP Success Criteria (critério de aceite do MVP)
O MVP é bem-sucedido se um **funcionário de fôrma e um construtor**, sem treinamento, conseguirem digitar um código de consulta e visualizar corretamente **N1/N3 + lista de painéis (para itens LV)** em **< 5s em 4G**, **sem nenhum caso de acesso a dados de obra de outro cliente**, validado em teste de campo com **≥5 usuários reais** em **≥3 obras distintas**.

---

## 5. Priorização das Features do MVP

### 5.1 MoSCoW

| Prioridade | Feature | Racional |
|---|---|---|
| **Must** | Busca por ID unificada (FR1/FR5) | É a "porta de entrada"; sem ela não há produto |
| **Must** | Ficha N1/N3 em SVG com zoom/pan (FR2/FR3) | Resolve a dor central; dado pronto (SVG embutido) |
| **Must** | Segurança anti-enumeração (NFR1–NFR5) | Não-negociável; sem ela o produto é um vazamento cross-cliente |
| **Must** | UX de campo alto-contraste/toque (NFR9) | Sem isto vira protótipo ignorado no canteiro |
| **Should** | Lista de painéis **LV** (FR4) | Alto valor para P1; dado já existe (`lv_generation_contract`) |
| **Should** | PWA offline + indicador de status (NFR8) | Conectividade de canteiro é instável; valor real mas não bloqueia consulta online |
| **Won't (MVP)** | Lista de materiais genérica (FR8) | Dado inexistente para PL/FV/LAJ; alto esforço a montante |
| **Won't (MVP)** | Viewer 3D (FR10), QR-code (FR9) | Fase 2 confirmada |

### 5.2 RICE (validação quantitativa da ordem de construção)

Escala: Reach 1–5 (fração de sessões que tocam a feature), Impact {0.25, 0.5, 1, 2, 3}, Confidence 0–100%, Effort em pessoa-semana. **Score = (Reach × Impact × Confidence) / Effort.**

| Feature | Reach | Impact | Conf. | Effort | RICE | Ordem |
|---|---|---|---|---|---|---|
| Busca por ID unificada | 5 | 3 | 100% | 2 | **7.5** | 1 |
| Segurança anti-enumeração | 5 | 3 | 100% | 3 | **5.0** | 2 (paralela à busca — fundação) |
| Ficha N1/N3 (SVG zoom/pan) | 5 | 3 | 90% | 3 | **4.5** | 3 |
| UX de campo (contraste/toque) | 5 | 2 | 90% | 2 | **4.5** | 3 (transversal) |
| PWA offline + status | 4 | 2 | 85% | 3 | **2.3** | 4 |
| Lista de painéis LV | 3 | 2 | 80% | 2 | **2.4** | 4 |
| Lista de materiais genérica | 4 | 2 | 30% | 8 | **0.3** | Fora — F2 |

**Leitura:** RICE e MoSCoW convergem. Busca + Segurança são a fundação inseparável; N1/N3 e UX de campo vêm logo depois; painéis LV e PWA offline fecham o MVP. Materiais genérica tem RICE ~0.3 (baixa confiança de dado + alto esforço) → confirmadamente F2.

> `[AUTO-DECISION]` LV entra como **Should** e não **Must**: o dado existe e o valor é alto, mas a consulta N1/N3 já entrega o núcleo da proposta mesmo sem a lista de painéis. Se o cronograma apertar, LV é a primeira a deslizar sem descaracterizar o MVP. (razão: preservar um MVP entregável e testável mesmo sob pressão de prazo.)

---

## 6. User Interface Design Goals

### 6.1 Overall UX Vision
Uma única tela de entrada — campo de busca dominante "Insira o código de consulta" — que resolve para um **cartão de especificação** de leitura instantânea em campo. Estética funcional de alto contraste, não decorativa: prioridade absoluta é legibilidade sob sol e operação com luvas.

### 6.2 Key Interaction Paradigms
- **Busca-primeiro:** o app abre no campo de busca; nenhum menu complexo antes da consulta.
- **Zoom/pan direto no desenho** (pinch + arrasto) para inspeção de cotas no N3.
- **Offline transparente:** último item disponível sem rede; badge de status de conexão sempre visível.
- **Toque generoso:** navegação por alvos grandes, mínimo de digitação além do código.

### 6.3 Core Screens and Views
- **Tela de Busca** (entrada única).
- **Resultado de Obra** (lista de pavimentos → itens).
- **Ficha do Item** (identificação + abas N1 / N3 / Painéis LV).
- **Visualizador de Desenho** (SVG em tela cheia com zoom/pan).
- **Estado "Não encontrado"** (genérico, sem revelar existência de ID).

### 6.4 Accessibility: **WCAG 2.1 AA**
Foco em contraste (luz solar), tamanho de alvo (≥48px, luvas) e tipografia grande. `[AUTO-DECISION]` AA e não AAA — AA cobre as necessidades de campo (contraste/alvo) sem o custo de conformidade AAA, desproporcional para um app read-only de consulta. (razão: relação custo/valor; foco é usabilidade de campo, não conformidade regulatória.)

### 6.5 Branding
Sem guia de marca fornecido. `[AUTO-DECISION]` Adotar tema utilitário de alto contraste (fundo claro / traço escuro para desenhos; paleta neutra) como default, deixando tokens de marca para ajuste posterior. (razão: nenhum ativo de marca disponível; legibilidade de campo é o driver.)

### 6.6 Target Device and Platforms: **Web Responsive (mobile-first, Android-primeiro)**
PWA instalável; degrada para desktop (persona cliente).

---

## 7. Technical Assumptions

> Decisões técnicas definitivas são da fase de Architecture (@architect Aria). Abaixo, balizas e restrições derivadas do brief e do código verificado.

- **Repository Structure:** `[AUTO-DECISION]` reuso do repositório/infra existente do CAD-ANALYZER; frontend PWA como novo app dentro da estrutura atual. (razão: budget enxuto; brief manda preferir reuso.)
- **Service Architecture:** endpoints **read-only públicos separados** dos controllers internos autenticados, sobre o FastAPI existente. Backend expõe apenas **projeção pública** (view sem campos sensíveis). Frontend PWA (Next.js/React, compatível com deploy Vercel citado pelo dono) + service worker para offline.
- **Data source:** mesmo store do pipeline; o SVG já sai embutido nos endpoints (`foto_n1`/`foto_n3`) — **zero conversão de formato** no MVP. A lista de painéis LV vem de `src/core/lv_generation_contract.py`.
- **Código de consulta opaco:** requisito de Architecture — mapear (obra_id UUID, pavimento string, item string) para um **identificador opaco único por item**, sem expor a estrutura de pastas/nomenclatura interna. Deve ser desenhado já pensando em QR-code (F2).
- **Testing Requirements:** `[AUTO-DECISION]` **Unit + Integration**, com ênfase em testes de **autorização/isolamento cross-cliente** (tentativas de enumeração, manipulação de ID, varredura) como suíte de segurança obrigatória do gate de release. Teste de usabilidade de campo (≥5 usuários) é gate manual do MVP. (razão: o risco #1 é IDOR/vazamento; a suíte de segurança é inegociável.)
- **Hosting:** frontend em Vercel/CDN; assets SVG via CDN (Cloudflare/CloudFront) para latência de campo e alívio do backend.
- **Ports/Deploy:** seguir política de portas do projeto para qualquer serviço local; deploy público do backend read-only isolado do portal interno.

---

## 8. Success Metrics

### 8.1 Business Objectives
- Reduzir o volume de solicitações de suporte "qual a especificação do item Y?" em **≥30%** em 90 dias pós-lançamento (baseline a coletar no pré-lançamento). `[AUTO-DECISION]` alvo 30% na ausência de meta do dono — patamar conservador e mensurável. (razão: sem baseline histórico, 30% é uma redução perceptível e defensável.)
- Reduzir incidência de **retrabalho de fôrma** por especificação errada/desatualizada (meta a quantificar com dado de chão de fábrica).
- Ativar canal de consumo público de dado já produzido, **custo marginal ~zero** de conteúdo.

### 8.2 KPIs (o que significa "funcionar bem")
| KPI | Definição | Alvo |
|---|---|---|
| **Time-to-Ficha** | Mediana: resolução do ID → render da ficha | < 3s (4G); < 8s (3G) |
| **Taxa de sucesso de busca** | % de IDs digitados que resolvem para ficha válida | > 90% |
| **Retenção de campo** | % de usuários que retornam ≥3×/semana | Tendência crescente (ferramenta, não protótipo) |
| **Vazamento cross-cliente** | Incidentes de acesso a obra de outro cliente | **0 (tolerância zero)** |
| **Sucesso sem treinamento** | Usuários que completam consulta na 1ª tentativa | ≥ 4 de 5 no teste de campo |
| **Enumeração detectada/bloqueada** | Rajadas de varredura detectadas e barradas | 100% das rajadas de teste barradas |

### 8.3 User Success Metrics
- Do "digitei o ID" ao "vejo a ficha correta" **< 5s em 4G**.
- Localizar N3 + lista de painéis sem treinamento (teste com 5 operadores).
- Consulta funciona offline após primeiro acesso, com indicador claro.

---

## 9. Roadmap (MVP → Fase 2 → Fase 3)

### Fase 1 — MVP (read-only 2D, segurança forte)
Busca por ID · Ficha N1/N3 SVG (zoom/pan) · Lista de painéis LV · PWA offline + status · UX de campo AA · Segurança anti-enumeração completa. **Gate de saída:** MVP Success Criteria (§4.3) + suíte de segurança verde.

### Fase 2 — Fechar o loop físico↔digital e ampliar dado
- **QR-code na peça** (etiqueta jobsite-grade → scan abre ficha); código de consulta do MVP já preparado para isto.
- **Lista de materiais genérica** para PL/FV/LAJ (após estruturação do dado a montante).
- **Mini viewer 3D**: pipeline CAD→glTF/GLB comprimido (< 10MB, Draco/meshopt, LOD), via three.js ou `model-viewer` com fallback WebGL 2D obrigatório. Só após validar demanda e existir conversor.

### Fase 3 — Plataforma de campo viva
- **Status de produção ao vivo** (fabricação → transporte → instalação).
- **Captura as-built** (foto/nota/checklist ITP/ITC) sincronizada ao portal interno.
- Expansões: portal do cliente autenticado, integração ERP/produção, exportação de listas para compras, AR overlay.

---

## 10. Riscos & Mitigações (herdados do brief + avaliação estratégica PM)

| # | Risco | Sev. | Mitigação | Owner |
|---|---|---|---|---|
| R1 | **Vazamento cross-cliente via ID (IDOR/BOLA)** | CRÍTICO | IDs opacos + autorização server-side + rate limiting + monitoramento de enumeração + projeção mínima (NFR1–5). Suíte de segurança é gate de release | @architect + @security + @dev |
| R2 | **Confidencialidade comercial do dado exposto publicamente** | CRÍTICO | Decisão do dono é "acesso livre por ID"; **não reabrir**. Mitigar via ID opaco não-adivinhável + projeção mínima (sem dado comercial). Recomendar validação jurídica em paralelo, sem bloquear o MVP | @po / dono |
| R3 | **Materiais/painéis genéricos inexistentes** | ALTO | Já mitigado no escopo: só **LV** entra no MVP (dado existe); genérica é F2 | PM (escopo) |
| R4 | **Viewer 3D — custo/complexidade** | ALTO | Cortado do MVP (§4.2); validar demanda antes da F2 | PM (escopo) |
| R5 | **SVG N3 denso lento em mobile/3G** | MÉDIO | CDN, otimização/rasterização progressiva, lazy-load, cache PWA (NFR7) | @architect |
| R6 | **UX de campo mal calibrada = abandono** | MÉDIO | Teste com 5 operadores reais é critério de sucesso do MVP (NFR10) | @ux |
| R7 | **Formato/unicidade do código de consulta** | MÉDIO | Código opaco único por item, desenhado na Architecture; busca com desambiguação | @architect |

> **Avaliação estratégica:** o risco dominante desta iniciativa **não é de produto, é de segurança**. Toda a arquitetura de acesso (NFR1–NFR5) deve ser tratada como funcionalidade de primeira classe, não como "hardening" posterior. A recomendação de go/no-go do MVP fica condicionada à suíte de segurança verde (zero vazamento cross-cliente demonstrado) — este é o único gate inegociável.

---

## 11. Epic List (proposta para breakdown por @sm)

- **Epic 1 — Fundação & Consulta Segura por ID:** infra PWA + endpoint público read-only isolado + código de consulta opaco + busca unificada + rate limiting/anti-enumeração (entrega uma consulta segura ponta-a-ponta, mesmo que só de identificação).
- **Epic 2 — Ficha do Item (N1/N3):** render de SVG `foto_n1`/`foto_n3` com zoom/pan mobile e navegação obra→pavimento→item.
- **Epic 3 — Lista de Painéis LV:** consumo do `lv_generation_contract` e exibição estruturada mobile.
- **Epic 4 — UX de Campo & PWA Offline:** alto contraste WCAG AA, alvos ≥48px, service worker/cache offline, indicador de status.

> Segurança (Epic 1) é fundação transversal — **não** é uma story final. Logging/rate-limiting entram desde a primeira story do Epic 1.

---

## 12. Next Steps

### 12.1 UX Expert Prompt (@ux Uma)
Desenhar a UX de campo mobile-first para a App de Consulta Pública CAD-ANALYZER a partir deste PRD: tela de busca única, ficha N1/N3 com zoom/pan, lista de painéis LV, estados offline e "não encontrado". Prioridade: WCAG 2.1 AA (contraste sob sol, alvos ≥48px para luvas). Entregar wireframes das 5 telas do §6.3.

### 12.2 Architect Prompt (@architect Aria)
Projetar a arquitetura a partir deste PRD, resolvendo dois pontos críticos: (1) **código de consulta opaco único por item** que mapeie (obra_id UUID, pavimento string, item string) sem expor nomenclatura interna e já preparado para QR-code (F2); (2) **camada de acesso público read-only** isolada do portal interno, com autorização server-side, rate limiting e monitoramento de enumeração satisfazendo NFR1–NFR5 (tolerância zero a vazamento cross-cliente). Reusar FastAPI + SVG embutido existente e `lv_generation_contract.py`. Frontend PWA (Next.js/Vercel) com service worker offline.

### 12.3 Handoff
- **@po (Pax):** validar escopo MVP e priorização antes do breakdown.
- **@sm (River):** breakdown dos 4 epics em stories (vertical slices).
- **Validação jurídica/comercial** de "acesso livre por ID" recomendada em paralelo, sem bloquear o MVP (decisão de acesso já tomada pelo dono).

---
*PRD gerado por Morgan (AIOS PM) em modo YOLO — decisões autônomas marcadas `[AUTO-DECISION]`. Fonte de dados verificada contra código real do pipeline nesta sessão.*
