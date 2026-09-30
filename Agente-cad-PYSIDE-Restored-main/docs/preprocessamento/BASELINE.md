# Baseline do pré-processamento

Data: 2026-09-22. Escopo: P00 do plano de pré-processamento.

Este documento registra o ponto de partida antes da implementação. Nenhum motor
foi executado e nenhum dado de produção foi alterado para produzir esta baseline.

## Paridade local × VPS

Hashes SHA-256 lidos em `D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main`
e `/opt/cad-analyzer`:

| Arquivo | Local | VPS | Estado |
|---|---|---|---|
| `main.py` | `fcaea4b206bf3337981d4e25b371dd966c6cdb4606fee1982c254e7d0ced0c98` | igual | igual |
| `src/core/niveis_extractor.py` | `b2966422ef27d5ccbd47f13873e4a8cf176cbdbd04c67930baebc42f07c6e7bc` | igual | igual |
| `src/ui/modules/diagnostic_hub.py` | `f2e3f7f3e0c2f2370ebc0e6246d4a380e09242812bbf6cb136a0966e9033afb0` | igual | igual |
| `src/ui/widgets/pre_validation_dialog.py` | `bf5d70a718d77de847631a24f4b61a5cf5a7f6485767022b8d1eee5044eeefc8` | `5edec261fb58ce9ba83f573372cbcad3fffa96e715436412fcb20318d62cd2e6` | divergente; não copiar por inteiro |
| `scripts/arete/headless_sa_analise.py` | `e3f42315050618b22c190952c09f369ea5ab336549de8d393ea08a5a281fa628` | igual | igual |
| `portal/app/ficha_reader.py` | `bfc412e0661de349cb24cc190dc49400bb7fb1193379ffbae3104636ced8784a` | igual | igual |
| `portal/app/jobs.py` | `b21d367aa2bfbd71de26737d9ea8b1c6e230e4623bc2ad5a135fd97656ffd281` | igual | igual |
| `portal/app/pipeline_runner.py` | `d2559bea00e07fa04df3d1d5062fbbf101ec06beced8dafc8f12cd18339f32f8` | igual | igual |
| `portal/app/static/drill_grade.js` | `b4f49c244da619a5720a56dccac420f8a17ad6b4b1d2029b5772ebc9cdf1bd2d` | igual | igual |

## Chamadas e efeitos colaterais conhecidos

| Componente | Leitura útil | Escritas/efeitos | Decisão inicial |
|---|---|---|---|
| `PreProcessAllWorker`, `diagnostic_hub.py` | recortes aprovados, loaders e tracers | salva entidades estruturais no DB, agrega torres e grava `pre_processamento_estado*.json` | proibido chamar diretamente no portal |
| `_run_legacy_analysis`, `headless_sa_analise.py` | pipeline real que monta pilares, lajes, vigas, níveis e cortes | cache pickle; com HTML salva estado, fichas, diagnósticos e manifestos | somente consumidor de referência até isolamento comprovado |
| `_run_pavimento_preprocess`, `main.py` | resolve detalhe e convenção de pilares | acopla estado da janela e diálogo Qt ao fluxo SA | não reutilizar como serviço web |
| `niveis_extractor.py` | funções puras de texto e mapa de cotas | resolvedor de arquivos percorre diretório e possui fallback legado | permitir apenas funções puras com fontes explícitas |
| `slab_level_inference.py` | seleção conservadora de nível e proveniência | muta objetos recebidos em alguns helpers | permitir sobre cópias isoladas |
| `portal/app/jobs.py` | fila persistente e recuperação | altera estado de jobs e possui pós-processamento específico do SA | novo ramo deve retornar antes do fluxo genérico SA |
| `portal/app/pipeline_runner.py` | subprocessos, runtime 3.12, artefatos e manifests | pode registrar projeto, executar motores e publicar resultados | não usar para pré-processamento até existir adapter isolado |

## Allowlist inicial

- Leitura de DXF por fonte resolvida e autorizada.
- Funções puras de `src/core/niveis_extractor.py`, recebendo textos/fontes explícitos.
- Funções conservadoras de `src/core/slab_level_inference.py`, usando cópias.
- Estruturas de leitura do cadastro de recortes do portal.
- Hash SHA-256 de conteúdo e escrita somente em diretório novo de staging de testes.

## Lista proibida até prova de isolamento

- Chamar `PreProcessAllWorker` no worker web.
- Escrever em `pillars`, `beams`, `slabs`, `projects` ou `pre_processing`.
- Gravar/substituir `estado_<pav>.json`, `convencao_pilares.json` ou JSONs Fase-4.
- Gerar N3/N5 ou alterar validações humanas.
- Reutilizar cache N1 sem incluir a revisão do contexto consumido na chave.
- Resolver convenção escolhendo o primeiro arquivo encontrado por caminhada de diretório.
- Copiar `pre_validation_dialog.py` local para a VPS enquanto as versões divergem.

## Gate P00

P00 concluído documentalmente: paridade registrada, efeitos colaterais mapeados e
allowlist definida. P01 pode criar apenas contratos e testes isolados; adapters
continuam bloqueados até o estudo de consumo P26.
