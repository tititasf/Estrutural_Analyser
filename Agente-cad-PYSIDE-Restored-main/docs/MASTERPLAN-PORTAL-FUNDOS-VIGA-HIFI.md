# MASTERPLAN — Fundos de Viga HI-FI no Portal Web

**Versão:** 1.0  
**Data:** 2026-09-09  
**Status:** pronto para implementação  
**Referência visual/funcional:** `http://127.0.0.1:8766/V301.html` — `FV — V301`, HTML 2.0  
**Pack canônico inspecionado:** `scripts/arete/html_fichas/Obra_TREINO_1/TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA_20260804_162045_fundos_viga_hifi_v20/fundos_viga/V301.html`

## 1. Objetivo

Levar a classe **Fundos de viga** do portal da VPS à mesma profundidade de leitura e operação da ficha V301 de referência, mantendo:

- a experiência HI-FI e a hierarquia visual da ficha;
- dados reais da obra, viga, segmento, N1 e N3;
- SVG vetorial com pan/zoom por `viewBox`;
- navegação por viga e por segmento;
- validação, anotações, marcações de erro e auditoria persistidas no servidor;
- vínculo explícito entre cada campo, desenho e artefato que o originou.

O resultado não será um iframe do HTML local. Será uma implementação nativa do portal, responsiva e operacional, usando o HTML apenas como **golden de UX e paridade**.

## 2. Decisões fechadas

1. **Uma viga é a unidade principal da tela.** Segmentos são subitens da viga.
2. **N1 e N3 compartilham o mesmo viewer contextual**, com filtro `Todos | S1…Sn`.
3. **SA, C1, C2, C3 e N3 são camadas explícitas**, não imagens soltas em cartões desconectados.
4. **O portal não raspa o HTML em tempo de execução para obter campos.** Campos vêm de fontes estruturadas; o pack HTML fornece SVG/evidência somente enquanto não existir um artefato estruturado equivalente.
5. **Nenhuma decisão operacional fica apenas em `localStorage`.** Tudo que o usuário salva é persistido no backend com autor, data e versão da rodada.
6. **N2 e N4 permanecem evidências de comparação/QA**, nunca entrada silenciosa do N1 ou do N3.
7. **Sem hardcode para V301.** V301 é golden inicial; a solução deve funcionar para as 36 vigas e 87 segmentos do pack e depois para outras obras.
8. **Ausência é exibida como ausência.** O portal nunca inventa N2, N3, N4, camada QA, painel ou campo.

## 3. Contrato observado na referência V301

A inspeção real da página confirmou os seguintes blocos e comportamentos.

### 3.1 Cabeçalho e navegação

- título `FV — V301`;
- quantidade `16 segmento(s)`;
- selo `HTML 2.0`;
- anterior/próximo e posição `1/36`;
- seletor de viga com 36 vigas;
- contador resumido `FV · 16 segs`.

### 3.2 Ficha resumida da viga

- nome da viga;
- quantidade de segmentos;
- tabela `Interpretação dos segmentos` com:
  - segmento;
  - comprimento;
  - largura;
  - altura da viga;
  - nível da viga;
  - ponto inicial;
  - ponto final;
  - quantidade de painéis N3.

Cada linha expande os detalhes N3 do segmento. Em `V301/S1`, por exemplo, a ficha mostra dois painéis (`244 × 19` e `61,5 × 19`), chanfros e aberturas por posição.

### 3.3 Viewer unificado

- camadas `SA`, `C1`, `C2`, `C3`, `N3`;
- selos humanos `H✓`, `H✗` ou `H·`;
- selos agênticos `A1/A2 Certo`, `X` ou pendente, conforme o contrato do looping;
- filtro `Todos | 1…16`;
- zoom no cursor, pan por arraste, reset e duplo-clique;
- modo de marcação de ponto;
- destaque SA suave;
- sincronização entre camada ativa e segmento selecionado.

### 3.4 Revisão e diagnóstico

- validação humana individual de SA/C1/C2/C3;
- anotação humana geral;
- abas dos agentes 1 e 2 e sugestão final C3;
- veredito e justificativa estruturada;
- ficha individual recolhível de cada segmento;
- evidências agregadas N2/N3/N4;
- fichas agregadas;
- diagnóstico da cadeia;
- quality gates da viga;
- marcação da ficha como errada.

## 4. Estado atual do portal e gaps

| Área | Portal atual | Alvo |
|---|---|---|
| Lista lateral | agrupa fundo por viga e abre segmentos | manter, acrescentando estado/gates por viga |
| Detalhe FV | abre um segmento isolado | abrir a **ficha da viga**, com segmentos dentro dela |
| Campos | pares genéricos `label/valor`; `Comprimento` e `Largura` usam o mesmo `_dim` | DTO FV explícito e sem ambiguidade |
| N1 | um SVG do item selecionado | contextual da viga + local por segmento |
| N3 | foto isolada quando encontrada | camada sincronizada + painéis/chanfros/aberturas por segmento |
| C1/C2/C3 | não há experiência FV equivalente | camadas reais, com estado e proveniência |
| Anotações | validações genéricas de campo/item | revisão por viga, camada, segmento e ponto |
| Persistência da ficha local | `localStorage` e servidor de notas opcional | banco/arquivo controlado pelo portal |
| Ausências | cartão simples | estado explícito com causa, path esperado e ação segura |
| Auditoria | parcial | autor, timestamps, rodada, hashes e histórico |

Gap crítico conhecido: `_FIELD_ID_SEGMENTO_SUFIXO['fundo']` mapeia `Comprimento` e `Largura` para `_dim`. Antes da UI final, o backend precisa expor campos FV semanticamente separados e indicar a proveniência de cada um.

## 5. Arquitetura-alvo

```text
estado_<pav>.json ─┐
beams.data_json ───┼─> FvFichaService ─> DTO FV versionado ─> API do portal
production_manifest│        │                                  │
SVG/DXF N1/N3 ─────┤        ├─> matriz de disponibilidade      ├─> ficha nativa FV
notes/QA reais ────┘        └─> hashes/proveniência             └─> persistência/auditoria
```

### 5.1 Backend

Criar um serviço dedicado, preferencialmente `portal/app/fv_ficha.py`, responsável por:

- resolver a viga inteira a partir de qualquer `item_id` de segmento;
- ordenar segmentos por `segment_index`/ocorrência, não por string;
- normalizar identidade, dimensões, nível, apoios e contorno local;
- resolver N1 contextual e N1 local de cada segmento;
- resolver o N3 da rodada de produção ativa e seus painéis;
- resolver C1/C2/C3 e os respectivos vereditos quando existirem;
- produzir matriz de disponibilidade sem sintetizar dados faltantes;
- anexar proveniência e hash de cada artefato;
- detectar inconsistências como segmento duplicado, índice faltante, dimensão ambígua e N3 obsoleto.

`ficha_reader.py` continua como leitor genérico. A regra rica de composição da ficha FV fica no serviço FV, evitando transformar o leitor comum em um novo monólito.

### 5.2 DTO proposto

```json
{
  "schema": "portal.fv.ficha/v1",
  "obra_id": "...",
  "pavimento": "13_PAV",
  "beam": {
    "name": "V301",
    "position": 1,
    "total_beams": 36,
    "segment_count": 16
  },
  "run": {
    "id": "...",
    "manifest_path": "...",
    "generated_at": "...",
    "fresh": true
  },
  "segments": [
    {
      "id": "...",
      "index": 1,
      "length_cm": 305.5,
      "width_cm": 19,
      "beam_height_cm": 55,
      "level": 852.19,
      "support_start": "P1",
      "support_end": "V312",
      "n1": {"svg": "...", "points": [], "source": {}, "gates": []},
      "n3": {
        "available": true,
        "panels": [{"index": 1, "length_cm": 244, "width_cm": 19}],
        "chamfers": {},
        "openings": {}
      }
    }
  ],
  "context": {
    "layers": {
      "sa": {"available": true, "svg": "...", "human_verdict": "valid"},
      "c1": {"available": true, "svg": "...", "agent_verdict": "correct"},
      "c2": {"available": false},
      "c3": {"available": false},
      "n3": {"available": true, "svg": "..."}
    }
  },
  "evidence": {"n2": {}, "n3": {}, "n4": {}},
  "pipeline": [],
  "quality_gates": [],
  "revision": {"etag": "...", "status": "open"}
}
```

O DTO nunca devolve um número sem unidade/proveniência interna. A apresentação pode ocultar detalhes técnicos, mas o payload deve permitir auditoria.

### 5.3 API

Adicionar rotas específicas, sem quebrar as rotas N1 atuais:

| Método e rota | Função |
|---|---|
| `GET /obras/{obra_id}/fv?{pavimento}` | lista de vigas, contagens e estado resumido |
| `GET /obras/{obra_id}/fv/{beam}?{pavimento}` | DTO completo da ficha |
| `GET /obras/{obra_id}/fv/{beam}/artifacts/{layer}` | SVG permitido da camada, com ETag |
| `PUT /obras/{obra_id}/fv/{beam}/review` | anotação/veredito geral, com controle de concorrência |
| `PUT /obras/{obra_id}/fv/{beam}/layers/{layer}/verdict` | validação humana da camada |
| `PUT /obras/{obra_id}/fv/{beam}/segments/{index}/review` | revisão de segmento |
| `POST /obras/{obra_id}/fv/{beam}/points` | marcação de ponto ancorada no SVG/CAD |
| `DELETE /obras/{obra_id}/fv/{beam}/points/{point_id}` | remoção auditável do ponto |
| `POST /obras/{obra_id}/fv/{beam}/flag-error` | marcação explícita de erro |

Toda escrita recebe `If-Match`/`revision`, registra usuário e retorna a revisão nova. Conflitos retornam `409`, nunca sobrescrevem silenciosamente.

## 6. Experiência de usuário no portal

### 6.1 Navegação lateral

- uma lista de vigas `V301`, `V302`, ...;
- cada linha mostra total de segmentos e estado agregado;
- selecionar a viga abre a ficha completa;
- a expansão local continua mostrando `S1…Sn` para acesso direto;
- `+ Criar segmento` mantém o fluxo já existente para o estrutural limpo;
- botão `← Estrutural limpo` permanece disponível.

### 6.2 Ordem da ficha principal

1. cabeçalho da viga e navegação anterior/próxima;
2. resumo da viga;
3. tabela compacta dos segmentos;
4. barra de camadas e selos;
5. filtro de segmento;
6. viewer contextual unificado;
7. painel de revisão humana;
8. detalhes recolhíveis por segmento;
9. evidências e diagnósticos avançados recolhidos por padrão.

Essa ordem reproduz a profundidade da referência sem despejar toda a instrumentação na primeira dobra da página.

### 6.3 Viewer

- SVG inline ou servido de endpoint autenticado e inserido como SVG real;
- pan/zoom exclusivamente por alteração de `viewBox`;
- wheel ancorado no cursor;
- drag em coordenadas SVG;
- duplo-clique e botão para reset;
- mesma câmera para SA/C1/C2/C3 quando compartilham espaço;
- N3 sincronizado relativamente quando o `viewBox` for diferente;
- troca de camada sem perder zoom ou segmento selecionado;
- `Todos` mostra a viga inteira; `S#` enquadra o segmento e reduz opacidade dos demais;
- ponto de revisão salva coordenada CAD, camada, segmento e transformação usada;
- teclado: setas entre segmentos, `0` para Todos, `R` para reset, sem sequestrar campos de texto.

### 6.4 Tabela de segmentos

- cabeçalho fixo;
- linha selecionável e expansível;
- seleção da linha sincroniza o filtro do viewer;
- valores numéricos alinhados e unidades no cabeçalho;
- expansão mostra painéis N3, chanfros, aberturas, gates e proveniência;
- valores divergentes recebem estado visual e explicação, não apenas cor;
- ausência de N3 mostra `não materializado` e a causa detectada.

### 6.5 Responsividade e densidade

- desktop: ficha em uma coluna larga; tabela e viewer ocupam toda a área útil;
- sidebar recolhível já existente deve liberar largura para o viewer;
- telas estreitas: tabela vira cartões de segmento, sem rolagem horizontal da página;
- detalhes avançados são `details/summary` ou acordeões acessíveis;
- estilo integrado ao portal, mantendo as cores semânticas da referência, não o fundo escuro integral da ficha local.

## 7. Persistência real

Não migrar literalmente as chaves de `localStorage`. Criar registros estruturados com:

- `obra_id`, `pavimento`, `beam`, `segment_index` opcional;
- `scope`: `beam`, `segment`, `layer`, `point`, `error`;
- `layer`: `sa`, `c1`, `c2`, `c3`, `n3`;
- `verdict`, `note`, `coordinates`, `author_id`;
- `run_id`, hashes dos artefatos vistos e versão do schema;
- `created_at`, `updated_at`, histórico/versão.

As validações existentes de item/campo continuam válidas, mas a ficha FV ganha uma camada de revisão própria. Não usar a tabela operacional do portal como substituto do estado de curadoria; definir migração e backup antes de produção.

## 8. Plano de implementação

### Fase 0 — Golden e inventário

- congelar V301 como golden visual inicial;
- extrair um manifesto de referência da página: vigas, segmentos, campos, camadas, selos e estados;
- selecionar golden secundário: uma viga simples, uma multi-segmento, uma com chanfro/abertura e uma `VF*`;
- documentar quais blocos são operacionais e quais são somente QA avançado.

**Gate:** inventário reproduz `36 vigas`, `87 segmentos` e `V301 = 16` sem diferença de conjunto.

### Fase 1 — Contrato de dados FV

- implementar `FvFichaService` e DTO `portal.fv.ficha/v1`;
- separar comprimento, largura, altura e nível;
- resolver apoios locais e globais sem misturá-los;
- materializar painel/chamfer/opening N3 a partir da fonte real;
- anexar run, freshness, paths e hashes.

**Gate:** snapshot JSON de V301 corresponde à tabela da referência e passa em schema estrito.

### Fase 2 — API somente leitura

- criar lista e detalhe FV;
- implementar cache por hash/mtime e invalidação após nova rodada;
- usar ETag nos SVGs e no DTO;
- bloquear path traversal e acesso entre membros/obras.

**Gate:** testes de autorização, ausência, stale run e payload completo.

### Fase 3 — Ficha nativa somente leitura

- criar `portal/app/static/fv_ficha.js` e `fv_ficha.css`;
- abrir a ficha por viga a partir da sidebar atual;
- implementar cabeçalho, tabela, acordeões e estados vazios;
- manter o detalhe genérico para outras classes.

**Gate:** V301 navegável sem iframe e sem erro no console.

### Fase 4 — Viewer unificado

- reutilizar o contrato canônico de pan/zoom `viewBox`;
- implementar camadas SA/C1/C2/C3/N3 e filtro Todos/S#;
- sincronizar câmera, seleção e tabela;
- carregar camadas sob demanda e cancelar requests obsoletos;
- manter SVG vetorial e texto legível em zoom profundo.

**Gate:** paridade visual das camadas e nitidez em zoom; nenhuma transformação CSS de escala.

### Fase 5 — Revisão e persistência

- criar migração/tabelas ou repositório de revisão versionado;
- implementar vereditos humanos, notas, pontos e marcação de erro;
- autosave com debounce, indicador `salvando/salvo/falhou` e retry explícito;
- implementar conflito de revisão e histórico.

**Gate:** duas sessões não sobrescrevem uma à outra; reload mantém tudo; auditoria identifica autor e artefato visto.

### Fase 6 — QA agêntico e diagnósticos

- integrar os estados A1/A2/C3 existentes ao DTO;
- exibir justificativas e propostas sem promovê-las automaticamente;
- expor evidências N2/N3/N4 e quality gates recolhidos;
- diferenciar `ausente`, `falhou`, `obsoleto`, `não aplicável` e `disponível`.

**Gate:** os selos seguem exatamente o contrato do procedimento QA FV e não confundem `A1 julgou SA` com `A1 julgou C1`.

### Fase 7 — Paridade de lote e implantação

- rodar testes em todas as vigas do pack;
- comparar conjuntos de vigas/segmentos e campos chave;
- executar QA visual em golden set;
- publicar sob feature flag `PORTAL_FV_HIFI_V1`;
- canário na Obra_TREINO_1/13_PAV;
- habilitar por obra e só depois globalmente.

**Gate final:** nenhum delta estrutural não explicado, nenhum erro de console/API e rollback testado.

## 9. Estratégia de testes

### 9.1 Unitários

- ordenação numérica de segmentos;
- dimensões e unidades;
- apoio local versus global;
- painéis, chanfros e aberturas;
- seleção da rodada de produção mais recente válida;
- detecção de manifesto obsoleto;
- matriz de disponibilidade;
- serialização do DTO.

### 9.2 Integração/API

- autenticação e escopo de obra;
- V301 com 16 segmentos;
- viga simples e `VF*`;
- N3 presente/ausente;
- C1/C2/C3 presente/ausente;
- ETag e `409` de concorrência;
- persistência/reload de revisão e pontos.

### 9.3 Browser/E2E

- sidebar → viga → ficha;
- anterior/próximo e seletor;
- expandir segmento;
- tabela ↔ subaba ↔ viewer sincronizados;
- trocar SA/C1/C2/C3/N3 preservando câmera;
- zoom, pan, reset e duplo-clique;
- salvar nota, veredito, ponto e erro;
- falha de rede com feedback e recuperação;
- teclado e acessibilidade básica.

### 9.4 Paridade Arete/visual

- conjunto exato de vigas e segmentos;
- dimensões com tolerância documentada de `0,05 cm`;
- mesmo significado de tags e apoios;
- SVG full-render, não extrato LINE-only;
- screenshots controlados para V301 e goldens secundários;
- inspeção humana dos pixels e do comportamento de zoom;
- N1/N3 nunca aprovados apenas por contagem.

Arquivos de teste sugeridos:

- `portal/tests/test_portal_fv_ficha_service.py`
- `portal/tests/test_portal_fv_routes.py`
- `portal/tests/test_portal_fv_review.py`
- `portal/tests/test_portal_fv_ui.py`
- `portal/tests/test_portal_fv_panzoom.py`
- `portal/tests/test_portal_fv_parity.py`

## 10. Critérios de aceite

A entrega só está pronta quando:

- [ ] selecionar `V301` abre uma ficha de viga, não apenas um segmento genérico;
- [ ] a tabela mostra os 16 segmentos e os oito campos observados na referência;
- [ ] expandir `S1` mostra seus dois painéis N3 e estados de chanfros/aberturas;
- [ ] SA/C1/C2/C3/N3 exibem apenas artefatos reais;
- [ ] `Todos | S1…S16` sincroniza tabela e desenho;
- [ ] zoom/pan usam `viewBox` e permanecem nítidos;
- [ ] revisões sobrevivem a reload, logout/login e outra máquina;
- [ ] cada decisão registra autor, horário, rodada e hashes;
- [ ] todas as 36 vigas e 87 segmentos do golden são alcançáveis;
- [ ] diferenças para o HTML local são apenas adaptações deliberadas de layout, não perda de informação ou função;
- [ ] o fluxo antigo continua disponível durante o canário e o rollback foi executado em ensaio.

## 11. Rollout e rollback na VPS

1. snapshot do código, banco de portal e configuração;
2. deploy do backend/API sem habilitar UI;
3. testes de leitura na VPS;
4. deploy dos assets com hash de versão;
5. ativar flag apenas para a Obra_TREINO_1;
6. validar V301 e goldens pelo botão/fluxo real do portal;
7. observar logs, latência e erros de frontend;
8. ampliar gradualmente.

Rollback: desligar a feature flag e voltar ao detalhe genérico; a nova persistência de revisão permanece preservada e não deve bloquear a versão anterior.

## 12. Riscos e controles

| Risco | Controle |
|---|---|
| copiar o HTML monolítico de 2,25 MB por viga | componentes nativos + SVG/camadas sob demanda |
| dados visualmente iguais, mas de rodada antiga | run id, hash, freshness e manifest explícitos |
| confundir N1 com N2/N4 | proveniência por campo/artefato e fronteiras do manual FV |
| decisões perdidas no browser | persistência server-side e indicador de save |
| regressão no zoom | teste que proíbe CSS scale e verifica alteração do viewBox |
| hardcode de V301 | lote completo + goldens de famílias distintas |
| tela excessivamente pesada | lazy load, acordeões, cache ETag e descarte de SVG inativo |
| implantação quebrar outras classes | feature flag e serviço/JS/CSS exclusivos de FV |

## 13. Sequência recomendada de execução

Começar por **Fases 0–4 em modo somente leitura**. Isso entrega rapidamente a profundidade visual correta sem risco de corromper validações. Em seguida implementar a persistência real (Fase 5), integrar o QA (Fase 6) e somente então promover na VPS (Fase 7).

O primeiro marco demonstrável deve ser:

> No portal local, selecionar Fundos de viga → V301 e obter a ficha nativa com 16 linhas, detalhes N3 de S1, camadas SA/N3 reais, filtro de segmento e pan/zoom canônico — sem iframe e sem escrita.

Depois desse marco, a paridade funcional de revisão é adicionada com segurança.

## 14. Documentos canônicos relacionados

- `docs/MASTERPLAN-ARETE-FUNDO-VIGA.md`
- `docs/SA-ANALISE/CLASSES/FV.md`
- `docs/PROCEDIMENTO-QA-FV-N1-CONTEXTUAL.md`
- `docs/QA-VISAO-EVIDENCIA-CANONICA.md`
- `docs/PADRAO-SVG-WEB-PANZOOM-VIEWBOX.md`
- `docs/PROVENIENCIA-CAMPOS-FV.md`
- `docs/PERSISTENCIA-HEADLESS-SA.md`

