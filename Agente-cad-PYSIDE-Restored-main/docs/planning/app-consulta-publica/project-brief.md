# Project Brief: App de Consulta Pública CAD-ANALYZER (Consulta de Fôrmas por ID)

> **Fase:** Discovery / Greenfield
> **Autor:** Atlas (AIOS Analyst) — para CEO-Planejamento (Athena)
> **Data:** 2026-07-11
> **Status:** Draft para revisão do Product Owner
> **Confiança geral:** Média-Alta (pesquisa de campo sólida; suposições de negócio ainda não validadas com usuários reais)

---

## Executive Summary

Proposta de uma **aplicação web pública (PWA, deploy tipo Vercel)** que serve como "porta de entrada única" para consultar a especificação técnica de qualquer elemento de fôrma para concreto armado do ecossistema CAD-ANALYZER. O usuário digita um **ID (obra, pavimento ou item)** e visualiza a ficha completa: interpretações N1 (leitura humana do desenho original) e N3 (desenho gerado por robô/CAD), lista de materiais, lista de painéis e um mini viewer 3D.

- **Problema central:** hoje a especificação de fôrmas vive num portal interno autenticado (FastAPI + Jinja2) acessível só à equipe de triagem. Cliente, funcionário de fôrma e construtor de campo não têm acesso rápido à "verdade" do item que estão produzindo ou montando — dependem de PDFs desatualizados, prints de WhatsApp e ligações.
- **Público-alvo:** três personas de campo/consulta — (1) cliente consultando especificação, (2) funcionário que constrói a fôrma na fábrica/canteiro, (3) construtor na obra.
- **Proposta de valor:** transformar o ID de um elemento numa consulta instantânea, mobile-first, utilizável no chão de fábrica e no canteiro (luz forte, luvas, 3G/4G instável), servindo como fonte única e sempre atualizada da especificação.

**Recomendação de escopo:** MVP focado em **visualização read-only da ficha (N1/N3 + materiais + painéis)** com forte disciplina de segurança de acesso. **Viewer 3D real fica para a Fase 2** — no MVP, entregar 2D de alta fidelidade (SVG/imagem N3) e, no máximo, um placeholder 3D. Ver seção MVP Scope.

---

## Problem Statement

### Estado atual e dores
- A especificação técnica de fôrmas (fichas N1/N3, desenhos SVG/DXF) está trancada no **portal interno autenticado**, desenhado para triagem/validação, não para consulta de campo.
- **Cliente:** não consegue verificar de forma autônoma "o que foi especificado para o item X" sem pedir à equipe — gera fricção comercial e retrabalho de suporte.
- **Funcionário de fôrma (fábrica/oficina):** monta a fôrma a partir de desenhos impressos ou PDFs que podem estar numa revisão antiga. Erro de leitura de uma cota ou painel = fôrma refeita = desperdício de material e horas.
- **Construtor no canteiro:** precisa conferir, no local do elemento, se a peça que chegou corresponde à especificação (posição, dimensões, materiais). Sem acesso móvel, confia em memória ou papel amassado no bolso.

### Impacto (qualitativo — quantificar é área de pesquisa aberta)
- Retrabalho de fôrma por especificação errada/desatualizada é a categoria de perda mais cara (material + mão de obra + atraso de cronograma). A literatura de campo confirma que a dor #1 do rastreamento de pré-fabricados era "planilhas Excel atualizadas à mão, cheias de ineficiência e erro" — exatamente o gap que ID+consulta única resolve.
- Suporte da equipe interna consumido respondendo "qual a especificação do item X?".

### Por que soluções existentes não bastam
- **Portal interno:** autenticado, desenhado para triagem, não otimizado para mobile/campo, não expõe materiais/painéis estruturados nem 3D.
- **PDFs/impressos:** sem versionamento vivo — o campo trabalha de revisão velha (problema clássico "as-built" documentado na indústria).
- **Softwares BIM/precast de mercado (Visibuild, IMPACT/StruSoft, Idencia, Fieldwire):** robustos, mas são plataformas caras, genéricas e não falam a linguagem/dados específicos do pipeline CAD-ANALYZER (fichas N1/N3, geradores STOG). Não há integração com os dados já validados internamente.

### Urgência
O pipeline CAD-ANALYZER já produz fichas validadas e desenhos N3 gerados por robô. O dado existe e está sendo desperdiçado por falta de um canal de consumo público. É baixo custo marginal transformar dado existente em produto de campo.

---

## Proposed Solution

### Conceito central
Um **PWA público** com uma única porta de entrada: campo de busca "Insira o ID da obra, pavimento ou item". A resolução do ID abre uma **ficha responsiva** com abas/seções:
1. **Identificação** — tipo de elemento (pilar / laje / viga lateral / viga de fundo), obra, pavimento, posição.
2. **N1 (leitura humana / SA)** — interpretação do desenho original.
3. **N3 (desenho robô/CAD)** — SVG/imagem de alta fidelidade, com zoom/pan.
4. **Lista de materiais** — estruturada (feature nova).
5. **Lista de painéis** — estruturada (feature nova).
6. **Mini viewer 3D** — Fase 2 (ver riscos).

### Diferenciais
- **Zero fricção de acesso** para o caso de uso legítimo: consulta por ID, sem cadastro pesado — porém com controles anti-abuso (ver Segurança).
- **Fonte única e viva:** lê os dados já validados no pipeline, não uma cópia desatualizada. Elimina o problema "campo trabalha de revisão antiga".
- **Mobile-first de campo real:** alto contraste (luz solar), alvos de toque grandes (luvas), funciona offline após primeiro carregamento (PWA cache), indicador claro de status de sync — todos padrões confirmados pela pesquisa de UX de canteiro.
- **Falar a língua do domínio:** N1/N3, painéis, materiais de fôrma — não um BIM genérico.

### Por que vai funcionar onde outros falharam
Não competimos com plataformas BIM completas. Fazemos **uma coisa excepcionalmente bem**: transformar um ID num cartão de especificação consultável em campo, alimentado por dados que já existem e já são validados internamente. Baixo escopo, alto valor, baixa curva de aprendizado (princípio confirmado: "interfaces mobile fáceis, com pouco treinamento, mesmo nos dias mais corridos").

---

## Target Users

### Primary User Segment: Funcionário de Fôrma (fábrica/oficina)
- **Perfil:** operador de produção que monta a fôrma física a partir da especificação. Baixa tolerância a UI complexa. Mãos ocupadas/enluvadas, ambiente com poeira e luz variável.
- **Comportamento atual:** trabalha de desenho impresso ou PDF no celular pessoal; confere cotas e painéis manualmente.
- **Necessidades:** ver **rápido e sem erro** o desenho N3, a lista de painéis e as cotas do item que está montando; certeza de que é a versão correta.
- **Objetivo:** montar a fôrma certa de primeira, sem retrabalho.
- **Requisitos de UX derivados:** alto contraste, fonte grande, alvos de toque generosos, N3 com zoom fluido, funciona com conexão instável.

### Secondary User Segment: Construtor no Canteiro
- **Perfil:** encarregado/mestre de obra que recebe e posiciona os elementos. Ambiente externo (sol forte), conectividade ruim, movimento constante.
- **Comportamento atual:** confere peça contra papel/memória; liga para a fábrica em caso de dúvida.
- **Necessidades:** confirmar no local que a peça corresponde à especificação (posição, dimensões, materiais); consultar por ID escrito na peça/etiqueta.
- **Objetivo:** montagem correta no canteiro, zero peça errada instalada.
- **Requisitos de UX derivados:** offline-first robusto, busca por ID como fluxo primário, futura leitura de QR-code na peça (Fase 2 — padrão dominante na indústria de precast).

### Tertiary User Segment: Cliente
- **Perfil:** contratante/engenheiro do cliente consultando o que foi especificado. Provavelmente desktop ou mobile em ambiente controlado.
- **Comportamento atual:** solicita informação à equipe interna; espera resposta.
- **Necessidades:** autonomia para consultar especificação de itens em produção; transparência.
- **Objetivo:** acompanhar/auditar a especificação sem depender de suporte.
- **Tensão crítica:** cliente A **não pode** ver dados da obra do cliente B. Isso condiciona toda a estratégia de acesso (ver Riscos/Segurança).

---

## Goals & Success Metrics

### Business Objectives
- Reduzir em X% o volume de solicitações de suporte do tipo "qual a especificação do item Y?" em 90 dias pós-lançamento (baseline a coletar).
- Reduzir incidência de retrabalho de fôrma por especificação errada/desatualizada (meta a quantificar com dado de chão de fábrica).
- Ativar um canal de consumo público para dados já produzidos pelo pipeline, sem custo marginal de geração de conteúdo.

### User Success Metrics
- Tempo do "digitei o ID" até "estou vendo a ficha correta" < 5 segundos em 4G.
- Funcionário de fôrma consegue localizar N3 + lista de painéis de um item sem treinamento formal (teste de usabilidade com 5 operadores).
- Consulta funciona offline após primeiro acesso (PWA), com indicador de status claro.

### KPIs
- **Time-to-Ficha:** mediana do tempo de resolução de ID → render da ficha. Alvo: < 3s (4G), < 8s (3G).
- **Taxa de sucesso de busca:** % de IDs digitados que resolvem para ficha válida (mede clareza do formato de ID). Alvo: > 90%.
- **Retenção de campo:** % de usuários que retornam ≥3x/semana (indica que virou ferramenta de trabalho, não protótipo).
- **Zero incidentes de vazamento cross-cliente:** métrica de segurança inegociável (0 tolerância).

---

## MVP Scope

### Core Features (Must Have)
- **Busca por ID unificada:** um campo que aceita ID de obra, pavimento ou item; resolve e roteia para a visão correta (obra → lista de pavimentos/itens; item → ficha). Rationale: é a "porta de entrada" descrita pelo dono do produto.
- **Ficha do item read-only (N1 + N3):** render das interpretações N1 e do desenho N3 em **SVG/imagem de alta fidelidade**, com zoom/pan mobile fluido. Rationale: é o dado que já existe e resolve a dor central; 2D é viável hoje.
- **Lista de materiais estruturada:** tabela legível em mobile. Rationale: feature nova mas de valor direto para funcionário/construtor. **Depende de o dado existir/ser estruturável a partir do pipeline** (ver Open Questions).
- **Lista de painéis estruturada:** idem. Rationale: crítica para o funcionário de fôrma.
- **UX de campo:** alto contraste, tipografia grande, alvos de toque ≥ 48px, PWA com cache offline do último item consultado, indicador de status de conexão/sync. Rationale: confirmado como fator de sucesso/fracasso na literatura de canteiro.
- **Controle de acesso anti-enumeração:** IDs **não-sequenciais/não-adivinháveis** (UUID ou slug ofuscado) OU gate leve (código de obra + PIN), rate limiting e logging de padrões de enumeração. Rationale: sem isso, um ID público = IDOR/BOLA, vazamento cross-cliente (ver Riscos — risco #1).

### Out of Scope for MVP
- **Viewer 3D real** (three.js/glTF interativo). Vai para Fase 2 — alto custo/risco, requer pipeline CAD→glTF que ainda não existe. No MVP, no máximo um placeholder ou imagem isométrica estática.
- Leitura de **QR-code** na peça física (Fase 2 — porém é o padrão da indústria de precast; desenhar o ID pensando nisso).
- Captura de dados em campo (fotos, assinaturas, checklists ITP/ITC, markup as-built).
- Edição de qualquer dado (app é 100% read-only no MVP).
- Login social / gestão de contas de cliente / permissionamento granular por usuário.
- App nativo iOS/Android em loja (PWA cobre o "download via link" no MVP).
- Notificações, versionamento visível ao usuário, histórico de revisões.

### MVP Success Criteria
O MVP é bem-sucedido se um **funcionário de fôrma e um construtor**, sem treinamento, conseguirem digitar um ID e visualizar corretamente N1/N3 + materiais + painéis do item em < 5s em 4G, **sem nenhum caso de acesso a dados de obra de outro cliente**, validado em teste de campo com pelo menos 5 usuários reais e 3 obras distintas.

---

## Post-MVP Vision

### Phase 2 Features
- **Mini viewer 3D real:** pipeline CAD (DXF/dados validados) → **glTF/GLB comprimido (< 10MB, Draco/meshopt, LOD)**, renderizado via `three.js` ou Google `model-viewer` com fallback WebGL. Só faz sentido depois de validar demanda e de existir conversor CAD→glTF.
- **QR-code na peça:** etiqueta durável (jobsite-grade) na fôrma/elemento → scan abre a ficha. Padrão consolidado na indústria de precast; fecha o loop físico↔digital.
- **Captura as-built:** foto/nota/checklist de conferência no campo, sincronizada ao portal interno.
- **Status de produção ao vivo:** tracker de estágio do elemento (fabricação → transporte → instalação), padrão "live inspection tracker".

### Long-term Vision (1–2 anos)
Plataforma de campo que é a fonte única viva da especificação e do status de cada elemento de fôrma, do desenho validado até o as-built, acessível por ID/QR em qualquer dispositivo — reduzindo retrabalho e disputas com transparência total entre fábrica, cliente e canteiro.

### Expansion Opportunities
- Portal do cliente com autenticação e dashboard por obra.
- Integração com ERP/produção para status em tempo real.
- Exportação de listas de materiais/painéis para compras.
- AR overlay (posicionar o 3D sobre a peça física via câmera).

---

## Technical Considerations

> Nota: decisões técnicas definitivas são responsabilidade da fase de Architecture. Abaixo, apenas balizas derivadas da pesquisa.

### Platform Requirements
- **Target:** PWA responsivo mobile-first (Android predominante no chão de fábrica/canteiro), degradando graciosamente para desktop (cliente).
- **Browser/OS:** Chrome/Android e Safari/iOS recentes; WebGL 2.0 necessário só para o 3D da Fase 2 (com fallback obrigatório).
- **Performance:** Time-to-Ficha < 3s em 4G; funcional em 3G; offline-first para o último item.

### Technology Preferences (indicativo, não vinculante)
- **Frontend:** PWA (Next.js/React combina com deploy Vercel citado pelo dono). Service worker para cache offline.
- **Backend:** reaproveitar o FastAPI existente expondo endpoints **read-only públicos e separados** dos endpoints internos autenticados — nunca reusar o mesmo controller sem checagem de autorização.
- **Database:** o mesmo store do pipeline; expor apenas projeção pública (view) sem campos sensíveis.
- **Hosting:** frontend em Vercel/CDN; assets SVG/imagem via CDN (Cloudflare/CloudFront) para latência de campo.

### Architecture Considerations
- **Integration:** ler dados já validados do pipeline CAD-ANALYZER; materiais/painéis exigem estruturação nova a montante.
- **Security/Compliance (crítico):**
  - IDs **não-adivinháveis** (UUID/slug) — sequencial é convite a enumeração (36,9% dos IDORs reais usam IDs sequenciais).
  - **Autorização server-side** é a defesa primária, não a ofuscação. Mesmo com UUID, validar escopo.
  - **Rate limiting + logging de enumeração** em todos os endpoints por ID.
  - Projeção pública mínima: nunca expor dado comercial/pessoal do cliente na resposta pública.

---

## Constraints & Assumptions

### Constraints
- **Budget:** não especificado — assumir enxuto; preferir reuso de infra existente (FastAPI, dados do pipeline) a construir do zero.
- **Timeline:** não especificado; MVP deliberadamente estreito para entregar valor rápido.
- **Resources:** equipe pequena; o app não pode exigir geração de conteúdo novo (consome dado existente).
- **Technical:** materiais e painéis estruturados **ainda não existem** — é dependência a montante, não trabalho de front. 3D não tem pipeline de conversão hoje.

### Key Assumptions
- Os dados de N1/N3 já validados são acessíveis programaticamente e renderizáveis como SVG/imagem em mobile. **[Confiança: Alta]**
- Existe (ou é viável derivar) lista de materiais e de painéis estruturada a partir dos dados do pipeline. **[Confiança: Baixa — validar]**
- O ID mencionado pelo dono (obra/pavimento/item) tem formato estável e resolvível de forma única. **[Confiança: Média]**
- Público de campo usa majoritariamente Android com 3G/4G instável. **[Confiança: Média-Alta, alinhado à literatura]**
- Há apetite real do cliente por autoconsulta (vs. preferir contato humano). **[Confiança: Média — validar com clientes]**
- É aceitável do ponto de vista comercial/contratual expor especificação técnica de fôrma "publicamente" (via ID protegido). **[Confiança: Baixa — decisão de negócio/jurídica pendente]**

---

## Risks & Open Questions

### Key Risks
- **[CRÍTICO] Vazamento cross-cliente via ID público (IDOR/BOLA):** se o ID for adivinhável e não houver autorização server-side, cliente A enumera IDs e lê obras de B. É o risco #1. Impacto: quebra de confidencialidade comercial, dano reputacional/jurídico. OWASP 2025 mantém Broken Access Control em #1. **Mitigação:** IDs UUID/slug + autorização por escopo + rate limiting + monitoramento de enumeração + projeção pública mínima. Considerar gate "código de obra + PIN" para dados sensíveis.
- **[CRÍTICO] Confidencialidade comercial do dado:** mesmo sem enumeração, "acesso livre pela internet" a especificações pode conflitar com contratos/expectativa dos clientes. **Mitigação:** decisão explícita de negócio sobre o que é realmente público vs. protegido por código; possivelmente dois níveis (metadados públicos, detalhe atrás de código).
- **[ALTO] Viewer 3D — custo/complexidade:** não há pipeline CAD→glTF; 3D em phone de baixo custo sofre (devs reportam performance ruim vs. `model-viewer`). Risco de estourar prazo/orçamento por uma feature "cool" de valor não validado. **Mitigação:** cortar do MVP; validar demanda antes; usar glTF comprimido + LOD + fallback quando for a hora.
- **[ALTO] Materiais/painéis inexistentes hoje:** features prometidas dependem de estruturação de dado a montante que talvez não exista. **Mitigação:** validar disponibilidade do dado ANTES de comprometer no MVP; se indisponível, entregar N1/N3 primeiro e materiais/painéis em incremento.
- **[MÉDIO] Performance de SVG grande em mobile/3G:** desenhos N3 densos podem ser pesados. **Mitigação:** SVG otimizado/rasterização progressiva, CDN, lazy load, cache PWA.
- **[MÉDIO] UX de campo mal calibrada = abandono:** se não for legível ao sol/com luvas, vira protótipo ignorado. **Mitigação:** alto contraste, alvos grandes, teste com operadores reais (critério de sucesso do MVP).
- **[MÉDIO] Formato/unicidade do ID:** se IDs colidem ou o usuário não sabe qual digitar, taxa de sucesso de busca despenca. **Mitigação:** validar taxonomia de IDs; UX de busca com autocomplete/desambiguação.

### Open Questions
- A lista de materiais e a lista de painéis estruturadas existem no pipeline hoje, ou precisam ser criadas? Qual o esforço a montante?
- Qual o formato canônico do ID de obra/pavimento/item e ele é único e estável?
- Qual o modelo de acesso desejado pelo negócio: 100% público, público-com-código, ou autenticado leve? (condiciona toda a arquitetura de segurança)
- Há requisito contratual/jurídico sobre exposição pública de especificação de fôrma?
- O dado N3 já sai como SVG renderizável, ou como DXF que exige conversão para web?
- Volume esperado de consultas/dia (dimensiona infra e rate limiting)?
- Existe demanda validada do cliente por autoconsulta, ou é hipótese do dono do produto?

### Areas Needing Further Research
- Entrevistas com 2–3 funcionários de fôrma e 1–2 construtores (validar fluxo por ID e UX de campo).
- Auditoria do pipeline: disponibilidade real de materiais/painéis/SVG.
- Benchmark de conversão CAD/DXF→glTF (preparar Fase 2).
- Decisão de segurança/jurídica sobre modelo de acesso.

---

## Appendices

### A. Research Summary (fontes de campo, jul/2026)

**UX de campo e rastreamento de precast (confirmado):**
- ID único persistente por elemento, carregado do design → fabricação → transporte → instalação é a prática consagrada; substitui "planilhas Excel atualizadas à mão".
- No scan/consulta, expor propriedades do elemento, status atual, desenhos e histórico. "Live inspection tracker" é padrão de valor.
- Desafios ambientais reais: **luz solar (usar alto contraste), luvas/EPI, conectividade instável**. Offline com sync automático e indicador de status é essencial. Baixo treinamento é fator de adoção.
- QR-code é o mecanismo dominante de acesso físico→digital em precast; etiquetas precisam ser jobsite-grade.

**Segurança (IDOR/BOLA — OWASP 2025):**
- Broken Access Control é #1 no OWASP Top 10 2025; BOLA é API1 desde 2019, "Easy/Widespread".
- IDs sequenciais aparecem em **36,9%** dos IDORs reais reportados. Defesa primária = autorização server-side; UUID é complemento, não substituto. Rate limiting + monitoramento de enumeração recomendados.
- Caso real 2025 (CVE-2025-13526): parâmetro `order_id` confiável na URL vazou dados de clientes por troca de ID.

**Viewer 3D em mobile:**
- CAD nativo é inadequado para mobile; **glTF/GLB (< 10MB, Draco, LOD)** é o padrão. Phones de baixo custo sofrem mesmo com viewers bem-feitos; `model-viewer` do Google é baseline leve com fallback. Requer WebGL 2.0 + fallback 2D. Loading pode levar 10–30s em conexão ruim — reforça deixar 3D fora do MVP.

### C. References
- Visibuild — QR codes precast: https://visibuild.com/customer-stories/qr-codes-precast-concrete/
- StruSoft IMPACT — tracking precast elements: https://strusoft.com/software/impact-precast/tracking-precast-concrete-elements/qr-codes/
- Autodesk Construction — QR codes: https://www.autodesk.com/blogs/construction/4-ways-qr-codes-can-improve-construction-outcomes/
- Fieldwire (Hilti) — Mobile BIM viewer: https://www.fieldwire.com/bim/
- AlterSquare — Mobile-first design for construction: https://altersquare.io/mobile-first-design-for-construction-management-software-field-usability-guide/
- OWASP — IDOR: https://owasp.org/www-community/attacks/insecure_direct_object_reference
- MDN — IDOR: https://developer.mozilla.org/en-US/docs/Web/Security/Attacks/IDOR
- glTF Viewer — mobile guide: https://gltfviewer.net/docs/mobile-guide
- uMake — optimize 3D for mobile CAD: https://www.umake.com/blog/how-to-optimize-3d-models-for-mobile-cad-apps
- AlterSquare — three.js viewer guide: https://altersquare.io/building-3d-viewers-in-the-browser-threejs-implementation-guide/

---

## Next Steps

### Immediate Actions
1. **Validar dependências de dado:** confirmar com a equipe do pipeline se materiais/painéis estruturados e N3 renderizável em SVG existem hoje. (bloqueia escopo do MVP)
2. **Decisão de negócio sobre modelo de acesso:** 100% público vs. código-de-obra vs. autenticado leve — com input jurídico/comercial. (bloqueia arquitetura de segurança)
3. **Confirmar taxonomia/unicidade do ID** de obra/pavimento/item.
4. **Entrevistas rápidas** com 1–2 funcionários de fôrma e 1 construtor para validar o fluxo por ID e requisitos de UX de campo.
5. Handoff para **@pm (Morgan)** gerar o PRD a partir deste brief.

### PM Handoff
Este Project Brief fornece o contexto completo para o **App de Consulta Pública CAD-ANALYZER**. Recomenda-se iniciar em modo de geração de PRD, revisando o brief e resolvendo as Open Questions (especialmente disponibilidade de dado de materiais/painéis e modelo de acesso) antes de definir requisitos funcionais. O escopo recomendado: **MVP read-only 2D com segurança forte; 3D e QR na Fase 2.**
