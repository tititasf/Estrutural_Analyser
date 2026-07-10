# Masterplan — OBRAS DRIVE (integração app desktop ↔ portal web)

**Status:** Fase 1 em execução | **Data:** 2026-07-10

## Objetivo

Permitir que o dono acesse, na app desktop (Gerenciar Projetos + Diagnostic Hub),
as obras que a equipe sobe pelo portal web — mesmo motor de recorte, mesmo dado,
sem precisar baixar a obra inteira manualmente.

**Fase 1 (este masterplan cobre só isso):** sincronizar apenas os **recortes**
(torre_1.dxf), com download sob demanda por arquivo. Ficha/validação SA
compartilhada fica para uma fase futura (fora de escopo aqui).

## Arquitetura atual (mapeada, não hipótese)

| Peça | Onde | Observação |
|------|------|------------|
| Lista de obras locais | `src/ui/widgets/project_manager.py:7528` `load_works_combo()` | Lê `db.get_all_works()` (SQLite `project_data.vision`, tabela `works`, só nome). Já existe precedente de "categoria sentinela" (`"⚠️ Pavimentos Sem Obra"`, `UserRole="__NO_WORK__"`, linha 7543) — é o padrão a reaproveitar. |
| Clique numa obra | `project_manager.py:7562` `load_projects()` | Filtra `db.get_projects()` por `work_name`, monta `ProjectCard`s. Abrir um DXF emite `Signal(str, str)` `request_open_bruto(obra_name, file_path)` (linhas 42-43, 4868). |
| Wiring | `main.py:3068-3080` | `project_manager.request_open_bruto.connect(diagnostic_module.open_bruto)` — é a `MainWindow` quem liga os dois módulos, não um chama o outro direto. |
| Entrada do Hub | `src/ui/modules/diagnostic_hub.py:3688` `open_bruto(obra_name, file_path)` | Usa conexão SQLite própria e hardcoded pro mesmo `project_data.vision`, tabelas **`obra_triagem`** e **`obra_recortes`** (diferentes das tabelas do portal). Identifica obra por **nome (string)**, nunca por UUID. |
| Paths de recorte | `diagnostic_hub.py:22` `DADOS_OBRAS_ROOT` + `:2756` `_get_obra_root_path` | Hardcoded `D:/Agente-cad-PYSIDE/DADOS-OBRAS/<obra_name>/Fase-2_Triagem/recortes/<bruto_stem>/` — mesma convenção do portal (`torre_crop.py`) e do `scripts/obra_crop_engine.py`. |
| Fallback de path já existente | `diagnostic_hub.py:1743` `_resolve_dxf_path()` | Tenta path cru → remapeia raiz do drive → `rglob` pelo nome. **Nunca baixa nada.** Ponto de interceptação natural pro download sob demanda. |
| Cliente HTTP pro portal | — | **Não existe.** `requests` já é dependência (usado em outro lugar). Portal roda em `http://127.0.0.1:{PORTAL_PORT}` (`portal/app/config.py`, default 21380). |
| Endpoint de listagem | `portal/app/routers/obras_routes.py:63` `GET /obras` | **Já existe**, já devolve TODAS as obras se o membro for "dono". Reaproveitar direto. |
| Endpoint de arquivo bruto | `obras_routes.py:390` `GET /obras/{id}/documentos/{doc_id}/arquivo` | Já existe (adicionado nesta sessão), serve `FileResponse` real. |
| Endpoint de arquivo de recorte | — | **Não existe.** Os endpoints de "foto" de recorte só devolvem SVG renderizado (`recortes_routes.py:208`), nunca o `.dxf` cru. **Precisa ser criado.** |

## Gap de identidade (obra local = nome; portal = UUID)

O Hub identifica obra e recorte só por nome de string nas tabelas `obra_triagem`/
`obra_recortes`. Reescrever o Hub pra entender UUID é invasivo demais pra Fase 1.
**Decisão:** obra Drive vira um "espelho" local — mesma pasta
`DADOS-OBRAS/<nome>/Fase-2_Triagem/recortes/<bruto>/`, mesmas linhas em
`obra_triagem`/`obra_recortes` — só que o `.dxf` em si só é baixado quando o
dono efetivamente pede pra ver aquele item. Isso reaproveita 100% do código do
Hub sem reescrevê-lo.

## Plano de execução — Fase 1

1. **Portal:** novo endpoint `GET /obras/{obra_id}/recortes/brutos/{bruto_id}/{item_id}/arquivo`
   servindo o `.dxf` real (`FileResponse`), espelhando o padrão já usado pra documentos.
2. **Desktop — cliente novo:** `src/core/drive_client.py` — login (sessão via cookie,
   mesma auth do portal), `listar_obras()`, `listar_documentos(obra_id)`,
   `listar_brutos(obra_id)`, `listar_itens(obra_id, bruto_id)`,
   `baixar_recorte(obra_id, bruto_id, item_id, destino)`.
3. **Desktop — registro local:** tabela nova `drive_obras (obra_nome PK, portal_obra_id,
   portal_bruto_id, portal_item_id)` em `project_data.vision` — mapeia o espelho local
   de volta pro UUID do portal, usada só pelo passo 5.
4. **Desktop — Gerenciar Projetos:** em `load_works_combo()`, seção extra "☁️ OBRAS DRIVE"
   (mesmo padrão do sentinela `__NO_WORK__`) chamando `drive_client.listar_obras()`.
   Selecionar uma obra Drive cria o espelho local (pasta + linhas `obra_triagem`/
   `obra_recortes`, sem baixar DXF nenhum ainda) e abre normalmente via
   `request_open_bruto` — o Hub nem percebe diferença.
5. **Desktop — download sob demanda:** em `diagnostic_hub.py`, quando
   `_resolve_dxf_path` (ou o chamador, `_on_bruto_selected`/`_run_crop_engine`)
   não encontra o arquivo localmente E existe registro em `drive_obras` pra aquele
   bruto/item, chama `drive_client.baixar_recorte(...)` pro path esperado, mostra
   status "Baixando do Drive…", e só então resolve/abre.

## Fora de escopo (fases futuras, não implementadas agora)

- Sincronizar ficha/validação SA entre web e app (dono mencionou decidir depois).
- Upload no sentido reverso (app → portal).
- Cache/expiração de arquivos baixados.
