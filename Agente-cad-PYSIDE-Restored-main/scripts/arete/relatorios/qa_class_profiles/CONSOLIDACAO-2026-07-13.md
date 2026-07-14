# Consolidação QA por classe — 2026-07-13

## Escopo executado

- perfis N1/N3: PIL, LAJ, FV e LV;
- DB real: `D:/Agente-cad-PYSIDE/project_data.vision`;
- projeto: `dd238e47-1dc6-4f63-a760-4e7ce19a7386`;
- pavimento de prova: 13_PAV;
- nenhuma escrita no DB, nenhum headless, nenhuma API visual;
- nenhuma ficha manual protegida foi modificada.

## Provas N1 localizadas

| Classe | Item/recorte | Campos | Checks | Resultado | Relatório |
|---|---|---:|---:|---:|---|
| PIL | P35 face D | 7 | 4 | PASS | `qa_profile_probes/real_13pav_pil_p35_d_v2.json` |
| LAJ | L318 apoio/contato | 8 | 6 | PASS | `qa_profile_probes/real_13pav_laj_l318_v2.json` |
| FV | V301 segmento 1 | 7 | 6 | PASS | `qa_profile_probes/real_13pav_fv_v301_v2.json` |
| LV | V328 A/B × PARA/PASSA + origem/isolamento/apoio | 40 | 39 | PASS | `qa_profile_probes/real_13pav_lv_v328_v4.json` |

Autoridade: somente os checks declarados. Não houve aprovação integral de ficha,
item ou interpretação.

O relatório FV `real_13pav_fv_v301.json` preserva o FAIL do perfil inicial, que
tratava apoio local P1 e limite global V309A como sinônimos. A versão v2 comprova
a correção do modelo do QA, sem mudar o dado de produção.

## Provas N3 estruturais

| Classe | Item/variantes | Campos/checks | Resultado | Relatório |
|---|---|---:|---:|---|
| PIL | P35 ABCD_PARA + ABCD_PASSA | 10/10 | PASS | `qa_n3_smoke/real_13pav_pil_p35.json` |
| LAJ | L318 | 5/5 | PASS | `qa_n3_smoke/real_13pav_laj_l318.json` |
| FV | V301 FUNDO_C | 5/5 | PASS | `qa_n3_smoke/real_13pav_fv_v301.json` |
| LV | V301 A_PARA + A_PASSA | 10/10 | PASS | `qa_n3_smoke/real_13pav_lv_v301.json` |

Autoridade: identidade do contrato no DXF, existência de texto e camadas mínimas.
Não houve veredito de geometria, aberturas, vazios, recortes, cotas ou Arete visual.
O exemplo LV N1 usa V328 e o smoke N3 usa V301; são provas independentes de cada
rota, não comparação entre os dois itens.

## Hardening aplicado

- projeto-amostra deixou de ser fallback implícito;
- `PENDENTE` retorna código 2;
- spec de paridade vazia não retorna PASS;
- FV/LV possuem allowlists distintas no payload compartilhado;
- todos os quatro JSONs de perfil são exercitados pelos testes;
- smoke N3 pareia obrigatoriamente contrato e DXF por rótulo;
- manifesto da ficha contém hashes de contrato/JSON/DXF/SVG/HTML;
- perfis e rotas estão documentados em `docs/QA-PERFIS-CLASSES-SA-N1-N3.md`.

## Limites abertos

1. Smokes N3 não substituem leitura visual. O próximo passo de um item real é
   montar/abrir a ficha e registrar o veredito do dono/agente.
2. A cobertura atual é um exemplar por classe, suficiente para validar o caminho
   operacional, não para declarar todos os itens corretos.

A proveniência LV foi reconferida em V328: `source_key/source_slot` existem por
`structural_segment`, enquanto isolamento e veto ao fallback FV existem em
`_sa_meta`. O perfil v1.2 valida os quatro contratos e suas origens disjuntas.

## Regressão técnica

- 60 testes focados PASS;
- módulos Python compilados;
- skill `qa-global-evidencias`: válida;
- squad `qa-global-evidencias`: 100/100, grau S.
