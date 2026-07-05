# MASTERPLAN — Produção & Soberania: do laboratório ao uso real da equipe
**Versão:** 1.1 — adenda §1-A (DP-10 a DP-14: ingestão via Drive, definição de N5, governança de liberação, MVP enxuto); P2 e arquitetura (§3) ajustados
**Data:** 2026-07-03 (v1.0) / 2026-07-05 (v1.1)
**Autor:** Fable (Consultor/Estrategista) — decisões de produto confirmadas pelo dono em 2026-07-03 e 2026-07-05
**Status:** ATIVO — complementa `MASTERPLAN-ARETE-QUALITY-GATES.md` (qualidade) e
`ARETE-MCP-RAG-HARMONIZACAO.md` (dados). Este doc cobre o eixo que faltava: **produto**.

---

> # 🥇 PRINCÍPIO DE PRODUTO (decidido pelo dono, 2026-07-03)
> **NÃO é SaaS. NÃO é app distribuído. É um sistema soberano centralizado.**
> O sistema roda em UM lugar (workstation do dono); a equipe (3–5 pessoas) envia obras
> e recebe resultados por um portal web na VPN. **Governança única:** só o dono valida,
> cura e altera. A equipe comenta erros e observações (evidência T0 do contrato de
> harmonização), jamais decide. Objetivo de negócio: **autoridade no nicho — trabalho de
> dias em minutos.**

---

## 1. Decisões de Produto (registradas — não rediscutir sem o dono)

| ID | Decisão | Racional |
|----|---------|----------|
| DP-1 | **Sem distribuição de binário.** Nenhum build entregue a terceiros. | Histórico real de builds fracassados; N máquinas = N ambientes para suportar com 1 dev. Centralizar elimina o problema na raiz. |
| DP-2 | **Servidor = workstation do dono + VPN (Tailscale ou equivalente).** | Custo zero, AutoCAD disponível durante a transição, controle físico total. VPS é degrau futuro (ver §6, WS-C). |
| DP-3 | **Interface da equipe = portal web mínimo, com login simples por membro.** | Comentário assinado = proveniência T0 real; equipe nunca vê botões de curadoria. A app PySide6 permanece ferramenta exclusiva do dono. |
| DP-4 | **Entregáveis da equipe: DXFs de formas (N3) + fichas HTML de conferência.** Quantitativos/planilhas vêm depois (DP-7). | As fichas HTML headless já existem (infra Arete) — o portal serve o que já é gerado. |
| DP-5 | **SCR NÃO é entregável da equipe ⇒ AutoCAD sai do produto.** Entrada DWG→DXF migra de `accoreconsole` para ODA File Converter. | Soberania: "usamos AutoCAD, não dependemos dele". Sem SCR na ponta da equipe, a única dependência restante é a conversão de entrada — substituível por ferramenta gratuita e multiplataforma. |
| DP-6 | **Embeddings continuam NVIDIA NIM (4096-dim).** Dependência externa aceita conscientemente; revisão quando houver condição de contratar modelo superior. | Decisão do dono: modelos locais atuais são inferiores para o caso. Mitigação: RAG é camada opcional — o pipeline de processamento NÃO pode bloquear se o NIM estiver fora (R5, §8). |
| DP-7 | **Quantitativos (lista de materiais) só APÓS estabilidade de qualidade.** As fichas já contêm a informação de materiais; falta a camada de conversão ficha→lista. | "Carroça atrás dos bois": contar materiais sobre resultado não certificado é contar errado com precisão. Gate de entrada: classe em Arete estável (ver P6). |
| DP-8 | **Horizonte: ~30 dias para a primeira obra real da equipe no portal.** | Agressivo e assumido. Se conflitar com qualidade, o portal desliza — a qualidade não (DP-9). |
| DP-9 | **Execução intercalada: Arete é o trabalho principal; portal entra em janelas curtas.** | A infra do portal é pequena (fichas já existem); a qualidade é o produto de verdade. |

## 1-A. Adenda (2026-07-05) — Ingestão, N5 e Governança de Liberação

Decisões que faltavam em §1 para fechar o P2 (transporte de arquivo, definição exata
de N5, quem libera o entregável final, forma do MVP):

| ID | Decisão | Racional |
|----|---------|----------|
| DP-10 | **Transporte de obra = Google Drive real (API, service account), 1 pasta por usuário.** NÃO é upload direto no portal. | Escolha explícita do dono contra a recomendação (upload direto via VPN seria mais simples/soberano). Motivo aceito: equipe já usa Drive, sync automático, funciona com servidor offline. Custo: dependência externa + cotas de API — mitigar reaproveitando R5 (degradar, não bloquear, se o Drive estiver indisponível). |
| DP-11 | **Detecção de obra nova = polling periódico da API do Drive** (não webhook, não botão manual de "sincronizar"). | MVP: zero infra extra, sem endpoint público exposto (mantém regra de fronteira §3 — nenhuma porta pública). Latência de minutos é aceitável para um pipeline que leva dias. |
| DP-12 | **N5 usa a definição que já existe no código** (`src/core/n5_assembler.py::assemble_n5`, label da UI: *"N5 consolida previews N3 → 1 DXF final por classe suportada"*) — **1 DXF por classe+pavimento**, montado a partir dos previews N3 de cada item. NÃO é promoção de status do N3, nem prancha única multi-classe com carimbo. | Erro de generalização cometido na sessão de 2026-07-03/05 (perguntado como se fosse conceito novo do produto) — é conceito **já implementado**, o portal só expõe o que existe. |
| DP-13 | **Selo final do N5 = self-service do próprio usuário**, liberado ao concluir as validações de interpretação (N1) e desenho (N3) que competem a ele. | Evita o dono virar gargalo de cada obra. Reconciliar com R3 (rótulo `certificado`/`beta`): self-service libera o *download*, mas o rótulo de certificação Arete da classe continua vindo do funil do dono — o usuário nunca confunde "eu validei minha parte" com "o motor está certificado". |
| DP-14 | **MVP = fluxo completo enxuto.** Todas as 6 etapas (upload/triagem/recortes/SA/validação/N5) entram desde a v1, com UX simples (listas de aprovação, ficha+viewer básico) — nada fica cortado para uma v2. | Decisão do dono contra as alternativas mais conservadoras ("MVP até o processamento" ou "MVP das validações primeiro"); aceita mais superfície agora em troca de não reabrir escopo depois. |

**Tensão registrada, não resolvida:** DP-10 (Drive como transporte) e a redação original do
gate P2 (§4, "upload de obra" direto no portal) descrevem mecanismos diferentes. P2 abaixo
já foi ajustado para refletir DP-10/DP-11 — se uma sessão futura reabrir o transporte,
atualizar ali e aqui juntos.

## 2. O insight central: o portal já está ~80% construído

A infra criada para QA interno do Arete **É** a interface da equipe:

| Peça do Arete (existe hoje) | Papel no portal |
|---|---|
| `headless_sa_analise.py` → fichas HTML N1–N4 por item | Página de resultado navegável por obra/pavimento/classe |
| SVG inline nos cards (texto como DOM) | Conferência fina sem depender de zoom de imagem |
| `_error_marker_block` (checkbox ERRADA + nota) | Formulário de comentário da equipe |
| Log de triagem JSONL + modelo de eventos (harmonização §7) | Persistência dos comentários como evidência T0 assinada |
| Geradores STOG → DXF N3 | Arquivo entregável para download |

O que falta é **infra de volta**, não produto novo: upload, fila de jobs, servir as
fichas por HTTP, login, e trocar `localStorage` por persistência server-side.

## 3. Arquitetura alvo

```
[Equipe 3–5]  ──Google Drive (API)──►  [Workstation do dono = SERVIDOR]
  • sobe DWG/DXF na pasta pessoal        • Poller Drive (DP-11): varre pastas por usuário,
    do Drive (fora da VPN)                 detecta obra nova, baixa via service account
                                          • Portal web (FastAPI, na VPN): login, jobs,
[Equipe 3–5]  ──VPN (Tailscale)──►         resultados, self-service do N5 (DP-13)
  • acessa portal                        • Fila de jobs → pipeline headless (CLI, sem UI)
  • baixa N5 (DXF por classe, DP-12)     • Motores: SA, motor_reverso_*, geradores STOG
  • navega fichas HTML                   • ODA File Converter (DWG→DXF, sem AutoCAD)
  • comenta erros (T0 assinado)          • SQLite project_data.vision + LanceDB (RAG/NIM)
[Dono — local, fora do portal]
  • App PySide6 = cabine de governança (curadoria, aprovação, Hub)
  • Claude Code = evolução dos motores (loop Arete continua)
```

Regras de fronteira:
- O portal **lê** artefatos e **grava apenas**: obras enviadas, jobs, comentários T0.
  Nunca escreve em fichas, golden, regras ou tabelas de curadoria.
- Nenhuma porta exposta à internet pública — acesso somente via VPN.
- Comentário da equipe = evidência T0 (`marcado_por: "equipe:<login>"`), entra no mesmo
  funil da triagem Arete; **curadoria/decisão continua exclusiva do dono** (invariante 1
  e 2 do contrato de harmonização).

## 4. Gates de Produção (P0–P6)

Mesma lógica dos gates G: um gate só abre com o anterior fechado. `PASS`/`FAIL`/`N/A`.

### P0 — Definição de produto ✅ (fechado com este documento)
Usuário, escopo, entregáveis, governança e anti-escopo definidos e registrados (§1, §7).

### P1 — Pipeline headless ponta a ponta (CLI, zero UI)
- [ ] Comando único processa 1 obra: entrada DXF (ou DWG via ODA) → fases → DXFs N3 +
      fichas HTML, sem abrir janela nenhuma.
- [ ] `headless_sa_analise.py` é a base; o que ainda depender de estado de UI é extraído
      **pontualmente** (strangler fig, §5) com regressão golden verde.
- [ ] Flag `--secao` implementada (item 6 do checklist do procedimento geral) — job por
      classe sem pagar o pavimento inteiro.
- **PASS:** 1 obra TREINO processada por comando único na máquina-servidor, saídas
  idênticas às geradas pelo caminho atual (hash/contagem).

### P2 — Portal mínimo (modo mono-usuário: só o dono)
- [ ] Poller do Google Drive (DP-10/DP-11): service account, 1 pasta por usuário,
      varredura periódica detecta obra nova e baixa para a área de trabalho do servidor.
- [ ] Serviço web local (FastAPI ou equivalente): login básico, lista as obras
      detectadas pelo poller, fila de jobs (1 job por vez — respeita a restrição de
      nunca paralelizar accoreconsole enquanto ele existir), página de resultados
      servindo as fichas HTML existentes e as 6 etapas do fluxo enxuto (DP-14),
      download self-service do N5 por classe+pavimento (DP-12/DP-13). **Reusar
      `scripts/arete/single_instance.py`** (trava anti-OOM criada 03/07, já ativa no
      headless: lock de arquivo liberado pelo SO mesmo em crash — testes em
      `tests/test_single_instance.py`) como base da exclusão mútua da fila.
- [ ] Comentários persistidos server-side (substituem `localStorage`), gravados no
      modelo de eventos com autor, `run_id` e `engine_version`.
- **PASS:** uma obra colocada na pasta do Drive de um usuário de teste é detectada pelo
  poller, processada, e o usuário consegue navegar as fichas e liberar seu próprio N5
  via navegador, na VPN, sem o dono tocar em nada no meio.

### P3 — Acesso remoto seguro
- [ ] VPN instalada (Tailscale ou equivalente), portal acessível apenas dentro dela.
- [ ] Logins criados para os 3–5 membros; teste real com ≥1 membro externo.
- [ ] Smoke test de serviço: máquina reinicia → serviço volta → processa 1 item → serve
      a ficha. (Substitui o antigo item "smoke test de build" — não há mais build.)
- **PASS:** membro externo faz upload e recebe resultado sem nenhuma intervenção manual
  do dono no meio.

### P4 — Piloto com equipe (dentro do horizonte de ~30 dias)
- [ ] 1 obra real, ≥2 membros, ciclo completo: upload → processamento → conferência nas
      fichas → comentários T0 assinados.
- [ ] Resultados rotulados por classe com o status de certificação Arete
      (`certificado` / `beta`) — a equipe sabe o que é confiável e o que está em treino.
- [ ] Retro com a equipe: o que faltou no resultado para o trabalho deles.
- **PASS:** a obra foi útil de verdade (substituiu trabalho manual) e o feedback está no
  funil de triagem.

### P5 — Operação estável
- [ ] Backup automático diário: `project_data.vision`, `GOLDEN/`, logs de triagem,
      LanceDB (destino fora da máquina — segundo disco ou nuvem).
- [ ] Toda run gravada com `engine_version` (commit) — reprodutibilidade de resultado.
- [ ] Rotina de atualização documentada (git pull + restart do serviço) com smoke test.
- [ ] STATUS gerado por script (WS-D) publicado no próprio portal — o dono vê o estado
      real sem abrir doc à mão.
- **PASS:** 2 semanas de uso sem perda de dado e sem intervenção não documentada.

### P6 — Quantitativos (gated por qualidade — DP-7)
Gate de entrada: classe com Arete estável (100% na TREINO_1 + zero regressão em 2 rodadas).
- [ ] Especificação da lista de materiais por classe (o que a ficha já contém vs o que
      precisa de cálculo novo).
- [ ] Conversor ficha→lista de materiais **por fórmula geral** (Regra de Ouro vale aqui
      também — zero hardcode por obra).
- [ ] Validação: quantitativo de 1 obra TREINO conferido manualmente pelo dono antes de
      aparecer no portal.
- **PASS:** planilha por obra disponível no portal para classes certificadas.

## 5. Regra de método: o monólito NÃO será "quebrado"

Preocupação legítima do dono (2026-07-03): desfazer o monólito `main.py` arrisca
corromper o que funciona. **Acordado:**

1. **Nenhum big-bang.** `main.py` não é refatorado por princípio estético.
2. **Strangler fig:** toda lógica NOVA nasce fora do monólito (headless-first, como
   `headless_sa_analise.py` já fez). Código existente só é extraído quando um gate P
   precisar dele rodando headless — um pedaço por vez.
3. **Rede de segurança obrigatória:** cada extração roda a regressão golden completa +
   comparação de saída (hash/contagem) antes/depois. Saída mudou = extração FAIL,
   reverte.
4. A app PySide6 **continua existindo e funcionando** como está — ela vira a cabine de
   governança do dono, não é aposentada.

## 6. Workstreams (execução intercalada — DP-9)

| WS | Nome | Conteúdo | Fonte canônica |
|----|------|----------|----------------|
| WS-A | **Qualidade (principal)** | Loop Arete por classe até 100% TREINO_1 e depois demais obras; FV reaberto (29/06: 20/26, causa `SARR_5CM`) é o FAIL ativo; itens 2–7 do checklist do procedimento geral (schema v2 do log, rollup de concordância, diagnóstico numérico headless, checkbox PIL/FV, `--secao`, visão macro) | `ARETE-LOOP-PROCEDIMENTO-GERAL.md` |
| WS-B | **Portal & serviço** | Gates P1→P5 (§4) | este doc |
| WS-C | **Soberania de dependências** | ODA File Converter substitui accoreconsole na entrada; consolidar vector store em **LanceDB** (aposentar ChromaDB; remover FAISS do MCP spec); NIM mantido (DP-6) | este doc + `ARETE-MCP-RAG-HARMONIZACAO.md` |
| WS-D | **Dados & governança** | Migrar log de triagem para modelo de eventos imutáveis (harmonização §7) ANTES de generalizar checkbox para PIL/FV; ~~script `STATUS`~~ **FEITO 03/07** (`scripts/arete/gerar_status.py` → `docs/STATUS.md`); mapa de taxonomias de gates (§9) | `ARETE-MCP-RAG-HARMONIZACAO.md` |
| WS-E | **Higiene documental** | CLAUDE.md (workspace e app) atualizados; `docs/README.md` reescrito como índice real; docs superseded marcados | este doc |

### Plano de 30 dias (DP-8) — ordem sugerida, qualidade manda

| Semana | WS-B (portal) | WS-A/C/D (paralelo em janelas) |
|--------|---------------|-------------------------------|
| 1 | P1: pipeline headless E2E + `--secao` | WS-A: atacar FV `SARR_5CM`; WS-D: migração do log p/ eventos |
| 2 | P2: portal mono-usuário (upload/jobs/fichas/comentários) | WS-A: loop da próxima classe; WS-D: script STATUS |
| 3 | P3: VPN + logins + teste com 1 membro | WS-C: ODA na entrada + regressão |
| 4 | P4: piloto com obra real da equipe | WS-A contínuo; retro do piloto |

Se qualquer semana estourar: **portal desliza, Arete não** (DP-8/DP-9).

### Kit de delegação (criado 03/07)

Para executar por modelo menor: `docs/HANDOFF-PRODUCAO-EXECUTOR.md` (regras do executor)
+ stories autocontidas em `docs/stories/STORY-EXEC-*.md`. **Uma story por sessão.**
Antes de delegar uma story, confirmar que nenhuma sessão paralela está no mesmo
território (ex.: STORY-EXEC-03 = item 8 do checklist do procedimento geral — a sessão
de LV pode reivindicá-lo).

## 7. Anti-escopo (o que este plano proíbe)

- ❌ Distribuir binário, instalador ou "versão para amigos".
- ❌ SaaS, multi-tenant, exposição pública do portal.
- ❌ Curadoria/validação por qualquer pessoa além do dono.
- ❌ Ativar MCP ou ingestão produtiva de RAG antes dos gatilhos do contrato de
  harmonização (nada neste plano constitui o gatilho — portal com login NÃO é
  "múltiplos agentes concorrentes").
- ❌ Quantitativos antes do gate P6.
- ❌ Refatoração big-bang do `main.py` (§5).
- ❌ Processar "todas as obras de uma vez" — a marcha incremental do Arete continua.

## 8. Riscos

| # | Risco | Prob. | Mitigação |
|---|-------|-------|-----------|
| R1 | 30 dias estourar por conflito com Arete | Alta | DP-9: portal desliza; comunicar nova data à equipe cedo |
| R2 | Máquina única = ponto único de falha | Média | P5 backup externo diário; VPS Linux como degrau futuro quando WS-C fechar |
| R3 | Equipe conferir resultado não certificado como se fosse final | Média | Rótulo `certificado`/`beta` por classe em toda página de resultado (P4) |
| R4 | Passo do pipeline preso à UI travar o P1 | Média | Extração pontual com golden como rede (§5); se inextraível barato, o passo roda via app em modo assistido até resolver |
| R5 | NIM fora do ar / custo | Baixa | RAG é camada opcional: pipeline processa sem consulta RAG; fila degrada, não quebra |
| R6 | Upload malicioso/lixo no portal | Baixa | Só VPN + login; parsing exclusivamente via ezdxf (nunca executar conteúdo); limite de tamanho; quarentena de job com erro |
| R7 | Comentários da equipe poluírem a triagem | Média | Namespace próprio (`equipe:*`) no funil T0; dono tria antes de virar causa-raiz — mesmo fluxo humano já existente |
| R8 | Google Drive API fora do ar, cota estourada, ou revogação de credencial (DP-10) | Baixa | Poller loga e reagenda, não derruba o serviço (mesmo padrão de degradação do R5); obra fica "aguardando ingestão" no portal em vez de erro |
| R9 | Usuário libera N5 self-service (DP-13) de uma classe ainda `beta` sem perceber | Média | Rótulo `certificado`/`beta` (R3) fica visível também na tela de liberação do N5, não só na listagem de resultado |

## 9. Mapa de taxonomias de gates (resolve deriva documental)

Duas nomenclaturas coexistem nos docs; equivalência oficial:

| Masterplan Arete (G0–G6) | Harmonização (G-*) | Mede |
|---|---|---|
| G0 Sanidade | (pré-condição de todos) | Par ficha+recorte válido |
| G1 Round-trip | parte de G-REVERSO | Dados da ficha sobrevivem N2→N4→N2′ |
| G2 Paridade canônica | G-REVERSO | Extrator reverso + gerador N4 |
| G3 UI/Persistência | (transversal, sem par) | App real reflete o DB |
| G4 Convergência N1 | G-INTERPRETACAO | SA compreende o estrutural limpo |
| G5 N3 vs N4 | G-PRODUCAO | Rota produtiva sem vazamento de gabarito |
| G6 Golden/Regressão | G-REGRESSAO | Generalização sem regredir |
| (novo, sem par G0–G6) | G-CROP | Aprendizado de recorte |
| Gates P0–P6 (este doc) | — | Produto/operação, eixo ortogonal aos dois acima |

## 10. Definition of Done

- **Produção v1:** P0–P5 PASS + piloto P4 com utilidade real confirmada pela equipe.
- **Soberania v1:** zero AutoCAD no pipeline do servidor (WS-C) + backup externo ativo.
- **Autonomia de qualidade (meta do dono):** todas as obras TREINO em Arete 100% sem
  hardcode + taxa de concordância auto×humano alta e estável (métrica §4.2 do
  procedimento geral) — este é o critério objetivo de "eficientes em ser autônomos",
  medido, não declarado.
- **Quantitativos v1:** P6 PASS nas classes certificadas.

---

*Fable (Consultor/Estrategista) — 2026-07-03*
*Revisão deste plano: ao fim do piloto P4 ou em qualquer mudança de decisão DP-*.*
