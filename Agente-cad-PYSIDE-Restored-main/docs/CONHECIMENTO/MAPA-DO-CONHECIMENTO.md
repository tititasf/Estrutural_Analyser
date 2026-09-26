# Mapa do Conhecimento — base global da empresa

**Status:** canônico · **Criado:** 2026-09-25 · **Escopo:** global (todas as obras)

Este é o ponto de entrada do conhecimento. Ele não repete o que os docs dizem: diz
**onde** cada tipo de saber mora, **qual fonte vence** em conflito e **o que está
obsoleto**. Serve a humanos, agentes (Claude Code, Codex) e à busca semântica
(`scripts/kb/kb_query.py`).

| Preciso de… | Vá para |
|---|---|
| o significado de um termo (N3, selo laranja, Para/Passa…) | [GLOSSARIO.md](GLOSSARIO.md) |
| saber se o dono já decidiu algo | [DECISOES-DO-DONO.md](DECISOES-DO-DONO.md) |
| saber se um doc ainda vale | [FONTES-E-STATUS.md](FONTES-E-STATUS.md) (gerado) |
| achar o módulo que faz X | [MAPA-CODIGO.md](MAPA-CODIGO.md) (gerado) |
| buscar por assunto | `python scripts/kb/kb_query.py "sua pergunta"` |
| entender a harmonização e o que limpar | [PLANO-HARMONIZACAO.md](PLANO-HARMONIZACAO.md) |
| preparar a base de uma obra | [CONTRATO-KB-MULTIOBRA.md](CONTRATO-KB-MULTIOBRA.md) |

---

## 1. Hierarquia de autoridade (quem vence em conflito)

1. **Decisão do dono registrada** ([DECISOES-DO-DONO.md](DECISOES-DO-DONO.md), com fonte).
   Uma decisão mais nova revoga a mais antiga sobre o mesmo ponto.
2. **Números e estado** → sempre gerados: `docs/STATUS.md` (`scripts/arete/gerar_status.py`)
   e o relatório mais recente em `scripts/arete/relatorios/`. Número escrito à mão envelhece.
3. **Regras de trabalho** → `CLAUDE.md` do workspace e do repo (fonte única; `AGENTS.md`
   e `GEMINI.md` são ponteiros).
4. **Procedimento e scripts válidos** → `docs/LOOPING-CANONICO.md` §1 (fora dele = não usar).
5. **Entrega (o que é pronto, o que fazer primeiro)** → `docs/MASTERPLAN-CONSOLIDACAO-ENTREGA.md`.
6. **Qualidade de motor por classe** → manuais `docs/SA-ANALISE/CLASSES/{PIL,LV,FV,LAJ}.md`
   e contratos de classe (ex.: `CONTRATO-RIGIDO-MOTOR-LV-N3-N4.md`).
7. **Docs `historico`** explicam o porquê de decisões passadas; nunca são procedimento.
8. **Docs `legado`** não se seguem (ver [FONTES-E-STATUS.md](FONTES-E-STATUS.md)).

O código é a verdade do *comportamento*; os docs acima são a verdade da *intenção*.
Divergência entre os dois é achado a registrar, não a resolver por suposição.

---

## 2. O negócio em uma página

- **O que a empresa faz:** projeto de **fôrmas para concreto armado** (pilares, vigas,
  lajes) a partir da planta estrutural do cliente. O entregável são **pranchas DXF de
  fôrma**; os materiais (chapas, sarrafos, garfos, madeira) derivam delas.
- **Padrão de desenho:** **STOG** — o padrão das pranchas humanas da empresa, portado dos
  robôs SCR/AutoCAD legados para geradores DXF (`scripts/gerar_{pl,lv,fv,lj}_dxf_stog.py`).
- **Documentos internos:** PI (Processo Interno do projetista — pé-direito, cotas,
  m², chapas, garfos, madeira por pavimento) e NSC (proposta comercial). Conhecimento
  extraído de 18 PDFs de obras reais: `../../../docs/HANDOFF-B-KNOWLEDGE-EXTRACTION.md`.
- **Entrevistas de domínio** (como o projetista pensa cada elemento):
  `docs/interviews/{PILARES,VIGAS,LAJES}.md`.
- **Produto:** o sistema CAD-ANALYZER lê a planta, interpreta cada elemento e gera as
  pranchas. **Web é o produto** (portal da equipe de 3–5 pessoas); a app PySide é o
  laboratório do dono (decisão de 2026-07-30).
- **Soberania:** sem distribuir binário; servidor próprio (VPS Hetzner) + portal;
  AutoCAD sai do produto (DXF via ODA). `docs/MASTERPLAN-PRODUCAO-SOBERANIA.md`.

---

## 3. O pipeline — níveis N1 a N5

| Nível | O que é | Quem produz | Onde vive |
|---|---|---|---|
| **N1** | interpretação da planta estrutural (campos do SA) | Structural Analyzer (`src/core/`, `beam_interpreters/`, `slab_tracer`, `pillar_*`) | DB `project_data.vision` (beams/pillars/slabs) |
| **N2** | ficha extraída do desenho STOG **humano** (gabarito) | motores reversos `scripts/motor_reverso_{pil,lv,fv,laj}.py` | `reverse_eng_fichas`, recortes em `DADOS-OBRAS/<obra>/Fase-2_Triagem/recortes_reversos/` |
| **N3** | DXF do robô gerado **de N1** (via conversão Fase-4) | geradores STOG + adaptadores N1→robô | `DADOS-OBRAS/<obra>/Fase-4_Sincronizacao/`, previews |
| **N4** | DXF do robô gerado **de N2** (prova do gerador) | mesmos geradores, a partir da ficha N2 | `DADOS-OBRAS/<obra>/Fase-6_Execucao_CAD/n4/` |
| **N5** | prancha final: 1 DXF por classe + pavimento, consolidado dos N3 | `src/core/n5_assembler.py` / `portal/app/n5_release.py` | portal (liberação self-service) |

Fronteiras que não se cruzam: **N2/N4 nunca alimentam N1/N3** (só comparam); o schema
N1 é imutável (convergência na camada de conversão). Detalhe:
`docs/PIPELINE-VISAO-N2-N3-N4-ANTIALUCINACAO.md`, `docs/MASTERPLAN-ENGENHARIA-REVERSA.md`.

**Fases de dados de uma obra** (`DADOS-OBRAS/<obra>/`): `Fase-0_STOG_KB` · `Fase-1_Ingestao`
· `Fase-2_Triagem` (recortes) · `Fase-3_Interpretacao_Extracao` · `Fase-4_Sincronizacao`
(JSONs N1→robô, **intocáveis**) · `Fase-5_Geracao_Scripts` · `Fase-6_Execucao_CAD` (N4)
· `Fase-7_Consolidacao` · `Fase-8_Revisao_Entrega`.

---

## 4. As quatro classes

Ordem de dificuldade/importância: **PIL e LV > FV > LAJ** (definição de pronto).

| Classe | Manual canônico | Semântica dos campos | Proveniência | Regras de interpretação | QA N1 |
|---|---|---|---|---|---|
| **PIL** pilar (faces ABCD, CIMA, GRADES) | `SA-ANALISE/CLASSES/PIL.md` | `SEMANTICA-PILAR-NOVA.md` | `PROVENIENCIA-CAMPOS-PIL.md` | `INTERPRETACAO-PILARES-ABCD.md`, `INTERPRETACAO-VIGA-CHEGA-VAO-E-FACE.md`, `PADRAO-TAGS-DESTAQUE-AGENTICO-PIL.md` | `PROCEDIMENTO-QA-PIL-N1-CONTEXTUAL.md` |
| **LV** lateral de viga (VC + faces A/B, Para/Passa) | `SA-ANALISE/CLASSES/LV.md` | `SEMANTICA-VIGA-NOVA.md` | `PROVENIENCIA-CAMPOS-LV.md` | `CONTRATO-RIGIDO-MOTOR-LV-N3-N4.md` (regras G0–G10), `LV-COMPREENDER-INTERPRETACAO-FICHAS-N2-N4.md` | `PROCEDIMENTO-QA-LV-N1-CONTEXTUAL.md` |
| **FV** fundo de viga (segmentos, apoios, nível) | `SA-ANALISE/CLASSES/FV.md` | `SEMANTICA-VIGA-NOVA.md` | `PROVENIENCIA-CAMPOS-FV.md` | `NIVEL-SEGMENTO-FUNDO-VIGA.md`, `SPEC-VIGA-SPLIT-FV-LV.md` | `PROCEDIMENTO-QA-FV-N1-CONTEXTUAL.md` |
| **LAJ** laje (hachura de apoio, HLAZ, painéis) | `SA-ANALISE/CLASSES/LAJ.md` | `SEMANTICA-LAJE-NOVA.md` | `PROVENIENCIA-CAMPOS-LAJ.md` | `RAG-GROUNDTRUTH-LAJ-13PAV.md` | `PROCEDIMENTO-QA-LAJ-N1-CONTEXTUAL.md` |

Diários de evolução por classe (histórico, não procedimento): `SA-ANALISE/HISTORICO/*.md`.
Perfis de QA por classe: `QA-PERFIS-CLASSES-SA-N1-N3.md` + `squads/qa-global-evidencias/data/class_profiles/`.
Robôs SCR legados (semântica original): `ROBO_SCR_PATTERNS.md`, `CALCULOS_ALGORITMOS.md`, `ROBOS_GUIDE.md`.

---

## 5. Qualidade — Arete e QA

| Tema | Fonte |
|---|---|
| Gates G0–G6, definição de Arete | `docs/MASTERPLAN-ARETE-QUALITY-GATES.md` |
| O único loop válido + quarentena de scripts | `docs/LOOPING-CANONICO.md` |
| Como executar o loop por classe | `docs/ARETE-LOOP-PROCEDIMENTO-GERAL.md` |
| Hierarquia de validação (G2 sozinho não sela) | `LOOPING-CANONICO.md` §1.5 |
| Evidência visual (agente lê PNG do SVG canônico, `--zoom`) | `docs/QA-VISAO-EVIDENCIA-CANONICA.md`, `QA-INVENTARIO-MINIMO-VALIDACAO-VISUAL.md` |
| Selos azul/rosa/laranja/verde | `docs/CONVENCAO-SELOS-VALIDACAO.md` |
| Squad QA Global de Evidências (Aegis) | `squads/qa-global-evidencias/`, skill `qa-global-evidencias` |
| Autoridade por classe | `squads/qa-global-evidencias/data/authority_matrix.json` |
| Entrega ponta a ponta com qualidade máxima | `docs/REGRA-ENTREGA-E2E-QUALIDADE-MAXIMA.md` |
| Dúvida ao dono como ficha visual | `CLAUDE.md` regra 5d, `scripts/arete/gerar_duvida_html.py` |
| Triagem de erros | `docs/ARETE-TRIAGEM-ERROS.md` |

---

## 6. Produto, portal e infraestrutura

| Tema | Fonte |
|---|---|
| Definição de pronto, caminho crítico, escape hatch | `docs/MASTERPLAN-CONSOLIDACAO-ENTREGA.md` |
| Decisões de produto DP-1…DP-14, gates P0–P6 | `docs/MASTERPLAN-PRODUCAO-SOBERANIA.md` |
| Portal (arquitetura, dados, UX, QA, devops) | `docs/HANDOFF-{ARCHITECT,DATAENGINEER,UX,QA,DEVOPS}-PORTAL.md` |
| Servidor VPS Hetzner (vigente) | `docs/HANDOFF-DEVOPS-VPS-HETZNER.md` |
| Obras via Google Drive | `docs/MASTERPLAN-OBRAS-DRIVE.md` |
| Pré-processamento por pavimento/torre | `docs/PLANO-PREPROCESSAMENTO-PAVIMENTO-TORRES.md`, `docs/preprocessamento/` |
| App de consulta pública (fôrmas por ID) | `docs/planning/app-consulta-publica/` |
| Python 3.12 obrigatório | `CLAUDE.md` do repo, `../../../docs/PYTHON-3.12-RUNTIME.md` |
| Git + DVC | `docs/GIT_DVC_GUIDE.md` |

---

## 7. Dados

| O quê | Onde |
|---|---|
| DB real (SQLite) | `D:/Agente-cad-PYSIDE/project_data.vision` — o de dentro do repo é stale |
| Schema do DB | `docs/ARQUITETURA-DB-COMPLETA.md` |
| Fichas N2 / recortes | tabelas `reverse_eng_fichas`, `reverse_eng_recortes` |
| Obras | `D:/Agente-cad-PYSIDE/DADOS-OBRAS/<obra>/` (Obra_TREINO_1 = obra de treino; 13_PAV = escopo da Fase A) |
| Índice da base global | `D:/Agente-cad-PYSIDE/KB-GLOBAL/kb_global.sqlite` (derivado; `kb_build.py` recria) |

---

## 8. Camadas de conhecimento e RAG (o que é o quê)

| Camada | O que guarda | Autoridade | Estado |
|---|---|---|---|
| **Docs canônicos** (este mapa aponta) | intenção, regras, procedimento | fonte primária | vivo |
| **KB global** (`kb_build.py` → SQLite) | índice buscável dos docs + glossário + decisões + regras T1+ | só aponta para a fonte; nunca é prova sozinha | vivo |
| **`semantic_rag_kb`** (tabela no DB) | regras semânticas por classe/campo, com tier | T1+ entra na KB; T0 fica em quarentena | vivo (QA consome) |
| **KB por obra** (futuro, mesmo esquema) | conhecimento de UMA obra | isolado por obra | contrato pronto: [CONTRATO-KB-MULTIOBRA.md](CONTRATO-KB-MULTIOBRA.md) |
| **Mini-RAG de sessão** (`qa_session_index.py`) | índice espacial do DXF de um pavimento | evidência local | latente |
| ByteRover, FAISS, `stog_rag_db` | notas/vetores antigos | nenhuma | **legado** — ver [PLANO-HARMONIZACAO.md](PLANO-HARMONIZACAO.md) |

Tiers de confiança (herdados de `docs/POLITICA-CONFIANCA-RAG.md`): **T0** quarentena ·
**T1** validado por humano em uma obra · **T2** consolidado em ≥2 obras · **TX** revogado.
**RAG nunca é prova única**: o resultado de busca aponta a fonte; a decisão exige abrir
a fonte e, em QA, evidência local da obra.

---

## 9. Como os agentes usam esta base

1. Antes de agir num tema, rodar `kb_query.py "<tema>"` e abrir as 2–3 fontes do topo.
2. Termo desconhecido → GLOSSARIO. Dúvida de convenção → DECISOES-DO-DONO antes de perguntar.
3. Fonte com status `legado`/`candidato_obsoleto` não se segue; `historico` só explica.
4. Conhecimento novo vai para o doc canônico do tema (nunca para a KB direto); a KB é
   reconstruída do texto. Decisão nova do dono → linha nova em DECISOES-DO-DONO.
