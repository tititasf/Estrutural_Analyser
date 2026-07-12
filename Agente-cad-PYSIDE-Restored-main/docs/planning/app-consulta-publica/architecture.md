# Architecture — App de Consulta Pública CAD-ANALYZER (Consulta de Fôrmas por ID)

> **Fase:** Architecture
> **Autor:** Aria (AIOS Architect) — para CEO-Planejamento (Athena)
> **Fontes:** `project-brief.md` (Atlas), `prd.md` (Morgan), e **verificação de código real** desta sessão
> **Data:** 2026-07-11
> **Status:** Decisiva (não apresenta opções sem escolher — cada decisão está justificada)
> **Mantra aplicado:** Arquitetura perfeita, execução pragmática, qualidade garantida por testes. Segurança é feature de primeira classe, não hardening posterior.

---

## 0. TL;DR — Decisão de Stack (para leitura de 30 segundos)

| Camada | Decisão | Porquê (1 linha) |
|---|---|---|
| **Frontend** | **Next.js 14 (App Router) como PWA**, app-shell SSG + fetch client-side, `noindex` | PWA/service-worker maduro; app-shell estático = first paint rápido em 3G; dado é privado → **sem SSR/SSG do conteúdo** (evita vazar ficha em cache de CDN/crawler) |
| **Backend** | **NOVA API FastAPI dedicada, processo separado, 100% read-only** (`consulta-publica`) | Isolamento físico do portal interno; nenhuma rota autenticada reusada; zero caminho de escrita possível |
| **Fonte de dados** | **DB público denormalizado próprio** (`public_consulta.db`, aberto `mode=ro`) + **artefatos de arquivo já existentes** (estado JSON, fichas HTML SVG, JSON LV) | A API pública **nunca toca** `portal_data.db` nem `project_data.vision`; lê só o que um *publisher* interno já projetou |
| **ID de consulta** | **Token opaco aleatório base62 (10 chars), backed por tabela**, minted no ato de publicação | Não-sequencial, não-adivinhável, revogável, não expõe taxonomia interna, pronto para QR (F2) |
| **LV (painéis)** | **Ler os JSON já persistidos** em `Fase-4_Sincronizacao/JSON_Vigas_Laterais/*.json` | **Achado real:** o motor já grava o contrato LV em disco — **zero re-execução do PySide** |
| **Deploy** | **Vercel (só frontend)** + **API no mesmo servidor do portal, porta 21390, atrás de Cloudflare** | Vercel serverless não roda esta stack (SQLite + filesystem); frontend desacoplado consome API em servidor real |

---

## 1. Contexto verificado (o que é real, não suposição)

Toda decisão abaixo se apoia em código lido nesta sessão, não no brief:

1. **Endpoints N1/N3 já retornam SVG pronto.** `portal/app/routers/n1_routes.py` + `portal/app/ficha_reader.py` produzem `foto_n1`/`foto_n3` como **string SVG embutida**, extraída das fichas HTML já geradas pelo SA (`extrair_fotos_ficha` → `_parse_html_cache`). **Nenhuma conversão de formato é necessária.** A lógica de leitura é reutilizável quase verbatim.
2. **A lista de painéis LV JÁ ESTÁ EM DISCO.** Verificado: `DADOS-OBRAS/{obra}/Fase-4_Sincronizacao/JSON_Vigas_Laterais/LV-PARA/V301_A.json` contém exatamente o schema de saída de `build_lv_generation_contracts` (`panels`, `total_width`, `h_section`, `structural_segments`, ...). **O motor SA já materializa o contrato LV durante a Fase-4.** Portanto a API pública **não precisa** importar `src/core/lv_generation_contract.py` nem rodar PySide6 — basta ler o JSON. Isto derruba o risco de acoplamento com o desktop.
3. **`obra_id` já é UUID.** `repository._new_id()` = `uuid.uuid4()`. Não-sequencial ✅. **Mas** `pavimento` (`"TERREO"`, `"13_PAV"`) e `item_id` (`"P1"`, `"V301"`) são **strings adivinháveis/enumeráveis** — não podem ser expostos crus (confirma NFR1).
4. **Fronteira de DB já é sagrada no código.** `portal/db/connection.py` **proíbe fisicamente** abrir `project_data.vision` (raise em `get_connection`). O portal já separa `portal_data.db` (operacional) de `project_data.vision` (curadoria). Vamos **estender essa disciplina**: a API pública não abre **nenhum** dos dois.
5. **Autorização interna é por membro/dono.** `access.pode_ver_obra()` liga obra→`membro_id`. Esse modelo é **irrelevante e perigoso** para a app pública — reusar `n1_routes` (que exige `Depends(auth.exige_login)`) seria acoplar a superfície pública ao controlador autenticado. **Rejeitado explicitamente** (satisfaz NFR4).
6. **Portal roda FastAPI puro, uvicorn, bind `127.0.0.1:21380`**, config por env em `portal/app/config.py`. Boa base para clonar o padrão numa segunda app isolada.

---

## 2. Princípio arquitetural central: Isolamento por Projeção (Publisher/Reader)

O risco #1 (IDOR/BOLA/vazamento cross-cliente, OWASP A01) é **estrutural**, não de código. A defesa mais forte é **tornar o vazamento fisicamente impossível**, não confiar em checagens espalhadas. Adotamos o padrão **Publisher/Reader com projeção denormalizada**:

```
┌─────────────────────────── ZONA INTERNA (autenticada) ───────────────────────────┐
│                                                                                   │
│   Portal interno (FastAPI, :21380, login/senha)                                   │
│   ├── portal_data.db        (RW)  ── operacional, membros, obras, validações      │
│   ├── project_data.vision   (RO)  ── curadoria Arete (nunca aberto pela pública)  │
│   └── DADOS-OBRAS/{obra}/   (RW)  ── estado_<pav>.json, fichas HTML, JSON LV       │
│                                                                                   │
│   ▼  PUBLISHER (novo, interno, AUTENTICADO — comando do dono/curador)            │
│      "publicar obra X" → mint de códigos opacos + denormaliza projeção mínima     │
│                                                                                   │
└──────────────────────────────────┬────────────────────────────────────────────────┘
                                    │ escreve UMA vez, no ato de publicar
                                    ▼
                        ┌───────────────────────────┐
                        │  public_consulta.db (RW    │  ← escrito SÓ pelo Publisher
                        │  só pelo Publisher)        │
                        │  código → projeção mínima  │
                        └─────────────┬─────────────┘
                                      │ mode=ro (read-only absoluto)
┌─────────────────────────── ZONA PÚBLICA (sem login) ──────────────┼────────────────┐
│                                                                    ▼                │
│   API Consulta Pública (FastAPI, :21390, read-only)                                 │
│   ├── public_consulta.db      (mode=ro)  ── resolve código → obra_dir/pav/item      │
│   ├── DADOS-OBRAS/{obra}/...   (open 'r') ── SVG + JSON LV (paths pré-resolvidos)   │
│   └── SEM conexão com portal_data.db nem project_data.vision                        │
│                                                                                     │
└──────────────────────────────────┬──────────────────────────────────────────────────┘
                                    │ HTTPS, CORS travado no domínio Vercel
                                    ▼
                    Cloudflare (CDN + WAF + rate limit)  ──►  PWA Next.js (Vercel)
```

**Consequência de segurança:** mesmo que a API pública seja 100% comprometida, o atacante:
- não tem conexão de escrita para lugar nenhum (DB aberto `mode=ro`; sem credencial do portal);
- só enxerga obras **explicitamente publicadas** (as que o Publisher projetou);
- só enxerga a **projeção mínima** (sem `cliente`, `criterios_cliente`, `membro_id`, comentários, `senha_hash`, etc. — campos que existem em `portal_obras`/`portal_membros` e **jamais** são copiados para `public_consulta.db`).

`[AUTO-DECISION]` **Modelo de acesso = "público, porém só o que foi publicado".** O brief/PRD deixam aberto "100% público vs código+PIN". Escolho: acesso livre por código opaco, **mas um item só existe publicamente se um código foi mintado para ele** (ato deliberado de publicação interna). Isso dá a fronteira cliente-A-vs-B *by construction* (obra não publicada é invisível) sem introduzir login/PIN (que o dono rejeitou). Razão: satisfaz NFR5 (zero vazamento) e a decisão do dono ("sem cadastro") simultaneamente; a "confidencialidade comercial" (R2) vira uma decisão explícita de *publicar ou não*, controlada pelo dono, não um efeito colateral de um ID adivinhado.

---

## 3. Esquema de ID opaco de consulta

### 3.1 Formato do código

- **Token aleatório base62** (`[0-9A-Za-z]`), **10 caracteres** → ~59 bits de entropia (`62^10 ≈ 8.4×10^17`). Inadivinhável por força bruta sob rate limiting.
- Gerado com **CSPRNG** (`secrets.token_bytes` → base62), **não** derivado de nenhum dado interno (não é hash de `obra_id`+`item` — derivar vazaria estrutura e seria offline-adivinhável se a chave vazasse).
- Case-**sensitive** no armazenamento, mas a busca aceita *trim* de espaços (NFR/FR7). **Não** normalizamos case (base62 usa maiúsculas E minúsculas distintas) — o campo de busca instrui "cole o código". Para QR (F2) o case é irrelevante ao usuário (scan).
- **Dois tipos (`kind`)**: `obra` (código de obra → lista pavimentos/itens) e `item` (código de item → ficha). Mesmo espaço de token, distinguidos pela coluna `kind`. Um código nunca revela seu tipo antes da resolução (mesma resposta 404 genérica).

`[AUTO-DECISION]` **Token table-backed em vez de HMAC stateless.** Alternativa considerada: codificar `(obra_id,pav,classe,item)` cifrado/assinado (stateless, sem tabela). **Rejeitada** porque: (a) fica longo (ruim para digitação/QR), (b) não é revogável sem lista de revogação (que reintroduz estado), (c) rotação de chave invalida todos os códigos impressos em peças físicas (F2 QR). Token aleatório + tabela é curto, revogável item-a-item, e sobrevive à rotação de segredos. Razão: durabilidade do código impresso na peça (requisito F2) + revogabilidade.

### 3.2 Armazenamento — `public_consulta.db` (novo, SQLite, escrito só pelo Publisher)

```sql
-- Projeção pública mínima. NENHUM campo comercial/pessoal do cliente entra aqui.
CREATE TABLE public_codes (
    code            TEXT PRIMARY KEY,          -- token base62(10), CSPRNG
    kind            TEXT NOT NULL CHECK (kind IN ('obra','item')),
    -- resolução interna (nunca serializada crua na resposta pública):
    obra_id         TEXT NOT NULL,             -- UUID (uso interno da API, não exposto)
    obra_dir        TEXT NOT NULL,             -- path absoluto já resolvido (anti-traversal)
    pavimento       TEXT,                      -- null p/ kind='obra'
    classe          TEXT,                      -- null p/ kind='obra'
    item_id         TEXT,                      -- null p/ kind='obra'
    -- projeção de exibição (denormalizada — o que a resposta pública PODE mostrar):
    tipo_elemento   TEXT,                      -- 'pilar'|'laje'|'viga_lateral'|'viga_fundo'
    titulo_publico  TEXT,                      -- rótulo seguro (ex.: "Pilar P1")
    obra_rotulo     TEXT,                      -- rótulo neutro da obra (NÃO o nome do cliente)
    -- controle:
    revoked         INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    publish_batch   TEXT                       -- id do lote de publicação (revogar obra inteira)
);

CREATE INDEX idx_public_codes_batch ON public_codes(publish_batch);
CREATE INDEX idx_public_codes_obra  ON public_codes(obra_id);

-- Log de acesso/enumeração (append-only, escrito pela própria API pública em um
-- 2º arquivo RW mínimo — ver §5.3 sobre a exceção de escrita controlada).
```

**Regra de projeção (Publisher):** o Publisher lê `portal_data.db` + `DADOS-OBRAS` (na zona interna, autenticado) e copia **apenas** os campos acima. Campos proibidos de atravessar a fronteira (existem em `portal_obras`/`portal_membros`, verificados no `repository.py`): `cliente`, `criterios_cliente`, `data_solicitacao`, `data_entrega`, `observacoes`, `membro_id`, `login`, `nome`, `email`, `senha_hash`, `descricao`, comentários da equipe. O `obra_rotulo` é um rótulo neutro derivado do `nome` da obra **somente se** o dono marcar como seguro; default = código curto anônimo (ex.: "Obra ·· A3F"). `[AUTO-DECISION]` default anônimo para o rótulo da obra — razão: o `nome` da obra em `portal_obras` pode conter o nome do cliente; expô-lo violaria R2. O dono opta ativamente por um rótulo público.

### 3.3 Geração e resolução

**Geração (Publisher, interno, autenticado):**
```
publicar(obra_id):
  batch = uuid4()
  para cada pavimento em descobrir_pavimentos(obra_dir):
    estado = ler_estado_pavimento(obra_dir, pav)
    para cada classe, item em listar_itens_n1(estado, classe):
      code = base62(secrets.token_bytes(8))[:10]   # colisão ~impossível; UNIQUE garante
      INSERT public_codes(code, 'item', obra_id, obra_dir, pav, classe, item.item_id,
                          tipo_elemento(classe), titulo_publico(item), obra_rotulo, batch)
    code_obra = base62(...)  # 1 código de obra
    INSERT public_codes(code_obra, 'obra', obra_id, obra_dir, pav=null, ...)
```
O Publisher roda **na zona interna** (novo endpoint autenticado no portal `POST /admin/publicar/{obra_id}`, ou comando CLI). Escreve em `public_consulta.db`. **É o único processo com escrita nesse arquivo.**

**Resolução (API pública, read-only):**
```
GET /api/v1/resolve/{code}:
  row = SELECT * FROM public_codes WHERE code=? AND revoked=0   (mode=ro)
  se row is None: 404 genérico  (idêntico a código malformado — FR6/NFR)
  se kind='obra':  retorna lista de pavimentos/itens (só códigos de item do mesmo obra_id)
  se kind='item':  retorna ficha (via obra_dir/pav/classe/item pré-resolvidos)
```
**Revogação:** `UPDATE public_codes SET revoked=1 WHERE publish_batch=?` (obra inteira) ou por `code`. Feito pelo Publisher/portal interno.

---

## 4. API pública read-only — contrato de endpoints

Prefixo `/api/v1`. Todos `GET`. Nenhum `POST/PUT/DELETE/PATCH` existe no router público (garantia estrutural, testável). Servida em `127.0.0.1:21390`, exposta via Cloudflare.

| Método | Rota | Descrição | Cache |
|---|---|---|---|
| `GET` | `/api/v1/resolve/{code}` | Resolve código → `{kind, ...}`. `obra`→índice; `item`→metadados da ficha (sem SVG pesado) | `private, no-store` (dado por código) |
| `GET` | `/api/v1/ficha/{code}` | Ficha do item: identificação + campos N1 + refs de SVG + flag `tem_lv` | `private, max-age=300` |
| `GET` | `/api/v1/ficha/{code}/svg/{nivel}` | `nivel ∈ {n1,n3}`. Retorna `image/svg+xml` puro (não JSON) | `public, max-age=31536000, immutable` (ETag = hash do SVG) |
| `GET` | `/api/v1/ficha/{code}/paineis-lv` | Lista de painéis LV (lê os JSON de `JSON_Vigas_Laterais`), agrupada por lado/behavior | `public, max-age=3600` |
| `GET` | `/api/v1/obra/{code}` | Índice de uma obra publicada: pavimentos → itens (só códigos, títulos e tipo) | `private, max-age=60` |
| `GET` | `/api/v1/health` | Liveness (sem dado sensível) | `no-store` |

### 4.1 Reuso máximo (não recomputar o que já existe)

- **N1/N3 SVG:** a API pública **importa a lógica de leitura** de `ficha_reader.py` (`ler_estado_pavimento`, `listar_itens_n1`, `obter_item_n1`, `extrair_fotos_ficha`) — **sem** as dependências de `auth`/`access`/`repository`. `[AUTO-DECISION]` extrair `ficha_reader.py` para um módulo compartilhado `src/shared/ficha_reader.py` (ou pip-instalável interno) importado pelas duas apps, em vez de copiar. Razão: capability preservation — evita divergência de lógica de parsing entre portal e app pública (heurística "never lose capability / single source of truth"). Se a extração for custosa no MVP, aceitável **copiar** com teste de paridade (escape hatch), mas o alvo é módulo compartilhado.
- **Painéis LV:** **ler o JSON já materializado** em `Fase-4_Sincronizacao/JSON_Vigas_Laterais/{LV-PARA,LV-PASSA}/{beam}_{A,B}.json`. A API só filtra/serializa os campos públicos (`panels[].width/height1/height2/panel_type`, `total_width`, `h_section`). **Não importa `lv_generation_contract.py`.** Se um JSON não existir para um item (LV não gerado), `tem_lv=false` — nunca inventa.
- **Índice de obra:** derivado de `descobrir_pavimentos` + `listar_itens_n1` sobre `estado_<pav>.json` (mesma fonte do portal), **mas** mapeando cada item ao seu **código opaco** via `public_consulta.db` — a resposta nunca contém `item_id`/`pavimento` crus, só `code` + `titulo` + `tipo`.

### 4.2 Projeção mínima — exemplo de resposta `/api/v1/ficha/{code}`

```jsonc
{
  "code": "aF3kZ9xQ2m",
  "tipo": "pilar",
  "titulo": "Pilar P1",
  "obra_rotulo": "Obra ·· A3F",         // rótulo neutro, nunca o nome do cliente
  "pavimento_label": "Pavimento Tipo",  // rótulo amigável, não a string interna "13_PAV"
  "campos": { "Classificação": "...", "Nível Relativo": "...", "Lado A": "..." },
  "atencao": "",
  "svg": {                               // URLs, NÃO o SVG embutido (payload leve)
    "n1": "/api/v1/ficha/aF3kZ9xQ2m/svg/n1",
    "n3": "/api/v1/ficha/aF3kZ9xQ2m/svg/n3"   // null se ausente
  },
  "tem_lv": true                         // → frontend chama /paineis-lv sob demanda
}
```
Note: **SVG desacoplado do JSON.** O portal interno hoje embute o SVG string em `foto_n1`/`foto_n3` (payload pesado). Para a app pública, o JSON carrega só **URLs** de SVG; o SVG vem por endpoint próprio, `image/svg+xml`, cacheável em CDN por content-hash. Ganho direto de 3G (NFR6/NFR7).

---

## 5. Segurança (defesa em profundidade — NFR1–NFR5)

### 5.1 Camadas (nenhuma isolada é suficiente)

1. **ID opaco não-sequencial** (§3) — barra enumeração estrutural. `obra_id` UUID + token 59-bit.
2. **Autorização por construção** — só resolve o que o Publisher projetou; obra não publicada é 404. Não há "escopo por usuário" a furar porque **não há usuário** — o universo público É a tabela `public_codes`. Satisfaz NFR2/NFR5 sem checagem espalhada.
3. **Read-only físico** — `public_consulta.db` aberto com `sqlite3.connect("file:...?mode=ro", uri=True)`; artefatos de arquivo abertos `open(path, 'r')`. **Nenhuma** rota de escrita no router. Nenhuma credencial do portal no processo público. Um `INSERT`/`UPDATE` acidental **falha em runtime** (SQLite ro).
4. **Projeção mínima** (§3.2) — campos comerciais/pessoais nunca cruzam a fronteira. Verificável por teste: schema de `public_consulta.db` não tem colunas proibidas.
5. **Anti-path-traversal** — `obra_dir` é path **pré-resolvido e armazenado** pelo Publisher; a API nunca constrói path a partir de input do usuário. `code` é chave de lookup, nunca componente de caminho. Após lookup, valida `resolved.is_relative_to(DADOS_OBRAS_ROOT)`.
6. **404 genérico e indistinguível** (FR6) — código inexistente, malformado, revogado ou fora de escopo → **exatamente** a mesma resposta `404 {"erro":"nao_encontrado"}` e **mesmo tempo de resposta** (evita timing oracle: lookup sempre executa, constante-time no caminho de erro).

### 5.2 Rate limiting e detecção de enumeração (NFR3)

- **Rate limit por IP** na borda **Cloudflare** (primeira linha) + **no app** (2ª linha, `slowapi`/middleware) — ex.: 60 req/min por IP em `/resolve` e `/ficha`; burst control. Defesa em profundidade: Cloudflare pode ser contornado por origin leak, então o app também limita.
- **Detecção de varredura:** rajada de 404s do mesmo IP (ex.: > N 404 em janela) → bloqueio temporário (Cloudflare rule + flag no app). Métrica "enumeração detectada/bloqueada" (KPI do PRD) instrumentada aqui.
- **CORS travado** — `Access-Control-Allow-Origin` = **exatamente** o domínio Vercel (ex.: `https://consulta.suaempresa.app`), não `*`. Bloqueia consumo por front hostil.
- **Sem listagem global** — não existe endpoint "listar todos os códigos/obras". Só se entra por um código conhecido.

### 5.3 A única escrita permitida na zona pública (controlada)

O log de acesso/enumeração precisa persistir. `[AUTO-DECISION]` o log vai para um **arquivo append-only separado** (`public_access.log` JSONL) ou um **2º SQLite dedicado `public_audit.db` aberto RW** — **fisicamente distinto** de `public_consulta.db` (que permanece `mode=ro`). Razão: mantém o DB de resolução estritamente read-only (impossível corromper a projeção), enquanto o audit trail (dado sem valor para o atacante, só telemetria) tem seu próprio arquivo com escrita mínima. Alternativa preferida se disponível: mandar telemetria para o Cloudflare/observabilidade e manter a zona pública **100% sem escrita**. No MVP, arquivo JSONL append-only é suficiente e simples.

### 5.4 Suíte de segurança obrigatória (gate de release — PRD §7/§10)

Testes de integração que **devem** estar verdes para liberar:
- Tentativa de `POST/PUT/DELETE` em qualquer rota → 405 (router não tem verbos de escrita).
- Enumeração sequencial simulada (1000 códigos aleatórios) → 100% 404, rate-limit dispara, **zero** vazamento.
- Código de obra A **nunca** resolve item de obra B (mesmo com manipulação de query/header).
- Path traversal via `code` (`../`, encoded) → 404, nunca lê fora de `DADOS-OBRAS`.
- Resposta pública não contém nenhum campo da blacklist (`cliente`, `membro_id`, `senha_hash`, ...) — asserção de schema.
- DB aberto `mode=ro`: tentativa de escrita programática → `OperationalError` (prova o read-only).

---

## 6. Frontend (PWA) — decisão e justificativa

### 6.1 Next.js 14 (App Router), deploy Vercel

**Escolhido sobre** Vite+React puro e sobre SSR-do-conteúdo:

- **PWA/offline:** service worker (via `next-pwa` ou Workbox) para cachear o **app-shell** e o **último item consultado** (NFR8). App-shell (busca, layout, ícones) é **SSG estático** → first paint quase instantâneo mesmo em 3G.
- **Conteúdo NÃO é SSR/SSG.** Correção importante ao brief: a ficha é **dado privado por código** — renderizá-la no servidor ou pré-gerá-la colocaria conteúdo sensível em **cache de CDN/edge e a expõe a crawlers**. Portanto: **client-side fetch** da ficha + `<meta name="robots" content="noindex,nofollow">` + header `X-Robots-Tag: noindex`. **SEO é explicitamente indesejado** aqui (dado de cliente não deve ser indexado). O benefício de Next.js é o *tooling PWA + app-shell + code-splitting por rota*, não SSR-para-SEO.
- **Zoom/pan de SVG (FR3):** `svg-pan-zoom` ou `react-zoom-pan-pinch` sobre o SVG servido pelo endpoint. SVG é vetorial → zoom sem perda, ideal para cotas.
- **UX de campo (NFR9):** design tokens de alto contraste, alvos ≥48px, tipografia grande — Tailwind com tema utilitário. WCAG 2.1 AA.

`[AUTO-DECISION]` Se o time preferir footprint menor, **Vite+React+`vite-plugin-pwa`** entrega o mesmo resultado funcional (app-shell estático + client fetch + service worker) com menos "peso Next". Escolho **Next.js** como default por (a) o dono já citou Vercel (fit natural), (b) ecossistema PWA/imagem/roteamento mais integrado. **Trade-off:** Next carrega runtime maior que Vite; mitigado porque não usamos SSR do conteúdo (menos superfície server). Razão da escolha: alinhamento com a menção do dono + maturidade PWA. Ambos são aceitáveis; a arquitetura de API não muda.

### 6.2 Performance mobile/3G (NFR6/NFR7)

- **SVG por CDN, imutável:** endpoint `/svg/{nivel}` com `Cache-Control: public, max-age=1y, immutable` + `ETag` (content-hash). Cloudflare cacheia; 2º acesso ao mesmo desenho = 0 hit no origin.
- **Payload leve:** JSON da ficha sem SVG embutido (só URLs). SVG carregado sob demanda (lazy) quando a aba N1/N3 abre.
- **Otimização de SVG:** o Publisher (ou um passo de build) roda `svgo` sobre os SVGs materializados para reduzir bytes (remoção de metadata, precisão de float). `[AUTO-DECISION]` fazer no publish-time, não no request-time (custo pago 1x). Razão: SVG N3 denso é o gargalo (R5); otimizar no publish evita CPU por request.
- **Service worker:** cache-first para SVG (imutável) e app-shell; network-first com fallback-cache para JSON de ficha (último item offline).
- **Compressão:** Brotli na borda Cloudflare para JSON e SVG.

---

## 7. Deploy — topologia real

O ponto crítico do brief (Vercel não roda esta stack) resolvido explicitamente:

```
┌────────────────┐     HTTPS      ┌─────────────────────┐   proxy    ┌──────────────────────────┐
│  Navegador      │ ─────────────► │  Vercel              │           │  Servidor real (o mesmo   │
│  (PWA instalada)│                │  Next.js estático    │           │  que hospeda o portal)    │
│                 │                │  (app-shell + SW)    │           │                          │
│                 │  fetch /api/*  │                      │           │  Cloudflare (CDN+WAF+RL)  │
│                 │ ──────────────────────────────────────────────►  │        │                 │
└────────────────┘                └─────────────────────┘           │        ▼                 │
                                                                     │  API Consulta Pública    │
   O que roda ONDE:                                                  │  FastAPI :21390 (uvicorn)│
   • Vercel  = SÓ o frontend Next.js (assets estáticos + SW).        │  ├─ public_consulta.db RO│
   •           NÃO roda Python, NÃO acessa SQLite, NÃO acessa disco. │  ├─ DADOS-OBRAS (read)   │
   • Servidor = API FastAPI read-only + arquivos + public_consulta.  │  └─ public_audit.db RW   │
   •           MESMO host do portal, PROCESSO e PORTA separados.     │                          │
   • Cloudflare = TLS, CDN de SVG, WAF, rate limit, cache.           │  Portal interno :21380   │
                                                                     │  (autenticado, isolado)  │
                                                                     └──────────────────────────┘
```

- **Vercel** hospeda **apenas** o Next.js exportado (app-shell estático + service worker). Consome a API por `NEXT_PUBLIC_API_BASE` (domínio Cloudflare da API). Nada de Python/SQLite/filesystem na Vercel — exatamente o limite que o dono intuía.
- **API pública** roda no **mesmo servidor do portal** (tem acesso local a `DADOS-OBRAS` e ao `public_consulta.db`), mas como **serviço/processo separado** (systemd/PM2 próprio), **porta 21390**, bind `127.0.0.1`, exposto só via **Cloudflare Tunnel** (não abre porta pública direta — mesma disciplina do portal, `config.py` já bind 127.0.0.1). `[AUTO-DECISION]` porta 21390 para a API pública (portal usa 21380); registrar no controle de portas do projeto. Razão: contiguidade com o range do portal, evita colisão.
- **Cloudflare** na frente: TLS, cache de SVG (CDN de campo, alivia origin — NFR7), WAF, rate limiting de borda (NFR3).
- **Publisher** roda na zona interna (endpoint autenticado no portal `:21380` ou CLI operado pelo dono) — a única coisa que escreve `public_consulta.db`.

**Por que não separar em outro servidor?** Considerado. Manter no mesmo host evita cópia/sync de `DADOS-OBRAS` (dezenas de obras, SVGs) e de `public_consulta.db`. O isolamento necessário é de **processo/credencial/DB-mode**, não de **máquina** — e isso já está garantido (§2, §5). Um servidor separado só adicionaria complexidade de sync de arquivos sem ganho de segurança real (a API já é read-only e sem credencial de escrita). **Trade-off aceito:** blast radius de host compartilhado mitigado por processo isolado + read-only + sem credenciais internas. Se no futuro o volume público exigir, a API é *stateless de leitura* e pode ser movida com um mount read-only de `DADOS-OBRAS`.

---

## 8. Backward compatibility e fronteiras (não quebrar o que existe)

- **Portal interno intocado.** Nenhuma rota de `n1_routes.py`/`auth.py` é modificada. A app pública é **aditiva**. O único acréscimo interno é o **Publisher** (novo endpoint/CLI autenticado) — não altera fluxo existente.
- **`ficha_reader.py`:** alvo = extrair para módulo compartilhado read-only (§4.1). Se extrair, o portal passa a importar do módulo compartilhado — mudança de import, mesma lógica, coberta por testes de paridade. Escape hatch: copiar no MVP com teste de paridade.
- **Fronteira de DB reforçada, não relaxada.** A regra existente ("`get_connection` nunca abre `project_data.vision`") é preservada; adicionamos "API pública nunca abre `portal_data.db`". Direção correta (mais restritivo).
- **Zero acoplamento com PySide6/motor SA.** A app pública não importa `src/core/lv_generation_contract.py` nem nada do desktop. Lê só JSON/SVG já em disco. (Heurística "zero coupling, max modularity" satisfeita.)

---

## 9. Alinhamento com os Epics do PRD (§11)

| Epic PRD | Cobertura arquitetural |
|---|---|
| **Epic 1 — Fundação & Consulta Segura por ID** | §2 Publisher/Reader, §3 código opaco + `public_consulta.db`, §4 `/resolve`, §5 rate-limit/anti-enum/404 genérico, §7 deploy isolado |
| **Epic 2 — Ficha N1/N3** | §4.1 reuso `ficha_reader`, §4.2 projeção, §6 zoom/pan SVG, §6.2 SVG desacoplado por CDN |
| **Epic 3 — Painéis LV** | §1.2 achado (JSON já em disco), §4 `/paineis-lv` lê `JSON_Vigas_Laterais` sem re-executar motor |
| **Epic 4 — UX de Campo & PWA Offline** | §6.1 app-shell SSG + SW, §6.2 cache offline último item + status |

**Ordem de construção recomendada:** Epic 1 primeiro e como fundação transversal (segurança não é story final). O Publisher + `public_consulta.db` + `/resolve` + rate-limit entregam uma consulta segura ponta-a-ponta (mesmo que só de identificação) antes de qualquer render de ficha.

---

## 10. Riscos residuais e trade-offs (honestidade arquitetural)

| # | Risco/Trade-off | Decisão e mitigação |
|---|---|---|
| A1 | **Host compartilhado portal+API pública** = blast radius | Aceito. Mitigado por processo isolado, DB `mode=ro`, sem credencial interna no processo público, Cloudflare Tunnel (sem porta pública direta). Reversível: API é read-stateless, movível para host próprio com mount RO de `DADOS-OBRAS`. |
| A2 | **`public_consulta.db` fica stale** se obra re-processada após publicar | Publisher re-executa no republish (novo `publish_batch`, revoga o antigo). Código impresso na peça (F2) aponta ao item, não ao batch — re-publish preserva o `code` se desejado (upsert por `obra_id+pav+classe+item`). `[AUTO-DECISION]` upsert preservando `code` no republish. Razão: durabilidade do QR físico. |
| A3 | **SVG N3 denso lento em 3G** (R5) | `svgo` no publish + CDN imutável + lazy-load por aba + Brotli. Se ainda pesado, F2 pode rasterizar fallback PNG progressivo. |
| A4 | **Extração de `ficha_reader` para módulo compartilhado** custa refactor | Escape hatch: copiar com teste de paridade no MVP; extrair depois. Não bloqueia MVP. |
| A5 | **Materiais genéricos (FR8) ausentes** | Fora do MVP por decisão do PRD. Arquitetura do `/paineis-lv` é generalizável para `/materiais/{classe}` quando o dado a montante existir (mesmo padrão: ler JSON persistido). |
| A6 | **Colisão de token** (10 chars) | `UNIQUE` na PK + retry no Publisher. Probabilidade desprezível (59 bits). |

---

## 11. Resumo das decisões inegociáveis (checklist de gate)

- [ ] API pública é **processo separado**, read-only, porta 21390, sem credencial do portal.
- [ ] `public_consulta.db` aberto **`mode=ro`**; escrito **só** pelo Publisher interno autenticado.
- [ ] API pública **nunca** abre `portal_data.db` nem `project_data.vision`.
- [ ] Código de consulta = **token base62 aleatório CSPRNG**, table-backed, revogável.
- [ ] Resposta pública = **projeção mínima** (blacklist de campos comerciais/pessoais verificada por teste).
- [ ] 404 **genérico e constante-time** para inexistente/malformado/revogado/fora-de-escopo.
- [ ] **Rate limit** em Cloudflare + app; detecção de enumeração instrumentada.
- [ ] **CORS** travado no domínio Vercel; sem endpoint de listagem global.
- [ ] Painéis LV lidos dos **JSON já persistidos** — **zero** import de `lv_generation_contract.py`/PySide.
- [ ] SVG servido por endpoint próprio (`image/svg+xml`), CDN imutável por content-hash.
- [ ] Frontend: conteúdo **client-side**, `noindex`, app-shell SSG, service worker offline.
- [ ] **Suíte de segurança verde** (§5.4) é o único gate inegociável de release.

---

*Arquitetura por Aria (AIOS Architect). Decisões fundamentadas em código real verificado nesta sessão (`n1_routes.py`, `ficha_reader.py`, `lv_generation_contract.py`, `config.py`, `connection.py`, `repository.py`, e inspeção do disco `DADOS-OBRAS`). Achado decisivo: os contratos LV já estão materializados em disco, eliminando acoplamento com o motor PySide.*
</content>
</invoke>
