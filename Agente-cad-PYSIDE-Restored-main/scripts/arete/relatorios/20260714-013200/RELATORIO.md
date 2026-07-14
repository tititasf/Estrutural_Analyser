# Relatório Arete — LAJ N1, dois SVGs de evidência

## Escopo

- Projeto: `4869be2b-f17c-410b-a9c8-98a887ec1c95` — `Obra_TREINO_1` / `13_PAV`.
- Classe: `LAJ`; piloto definido por evidência persistida: `L318`, `L304`, `L319`, `L326`.
- Sem leitura de N2/N4 para formar contorno, apoios, obstáculos, união ou paginação N1/N3.
- Sem escrita de dados produtivos, sem alteração de JSONs Fase-4 e sem selo golden.

## Predicado de aceitação, definido antes da rodada

1. Cada ficha LAJ deve apresentar exatamente dois SVGs N1 provenientes do mesmo DXF:
   local para contorno/contato e contextual para topologia.
2. O SVG local deve identificar visualmente a laje-alvo; o contextual não pode ser
   interpretado como prova de apoio por proximidade.
3. A ausência de entidade cross-classe materializada deve resultar em `PENDENTE`, não
   em `PASS`, nem exceção fatal.
4. A promoção de fast path LAJ depende de equivalência canônica por campos, links,
   geometria, contagens e diagnósticos; não foi promovida nesta rodada.

## Alterações

- `src/ui/widgets/preficha_laje_html.py`
  - substituiu a única evidência N1 por `N1 próximo / SA` e `N1 contexto / SA`;
  - ambas pedem SVG ao mesmo renderizador/DXF e não fazem fallback PNG;
  - o pipeline exige ambos para considerar N1 materializado.
- `src/ui/widgets/pre_validation_dialog.py`
  - para `focus_mode='slab'`, `context_view='far'` abre janela contextual distinta;
  - adiciona a legenda SVG `ALVO N1: <laje>`; não cria vínculo de apoio.
- `scripts/arete/qa_profile_probe.py`
  - entidade cross-classe resolvida no payload mas ausente no DB retorna `PENDENTE`;
  - impede que um link como `L318 → P22` seja aprovado por inferência.

## Seleção por dados

| Item | Família coberta | Evidência persistida |
|---|---|---|
| L318 | apoios múltiplos/cortes | 7 vértices, 11 apoios, 5 cortes |
| L304 | simples | retangular, 5 vértices |
| L319 | contorno recortado/apoios | 8 vértices, 4 apoios, 3 cortes |
| L326 | chanfro/contorno complexo | 18 vértices |

## Verificação executada

- `pytest tests/test_preficha_laje_html.py tests/test_qa_profile_probe.py -q`: **14 PASS**.
- `py_compile` para os três módulos alterados: **PASS**.
- `qa_profile_probe` L318: **PENDENTE esperado**. O vínculo local resolve `P22`, mas
  `PIL:P22` não está materializado neste projeto. Resultado:
  `scripts/arete/relatorios/qa_profile_probes/20260714_012942_LAJ_L318_5c481adb.json`.
- `gerar_status.py`: gerou `docs/STATUS.md`.

## Headless, visual e persistência

Foi chamado exclusivamente o headless canônico com `--wait` e escopo limitado:

```text
headless_sa_analise.py --project-id 4869be2b-f17c-410b-a9c8-98a887ec1c95 \
  --secao lajes --item L318 L304 L319 L326 --wait
```

Na primeira tentativa ele aguardou corretamente o dono vivo da trava e não abriu
interface, mas falhou antes de materializar fichas/DB por regressão externa:

```text
NameError: name '_fv_global_boundary_link' is not defined
main.py::_process_beam_intelligent
```

Log: `scripts/arete/relatorios/20260714-qa-laj-n1-headless.err.log`.

Outro fluxo corrigiu a dependência no escopo correto de `main.py`; a segunda tentativa
canônica, ainda em `READ_ONLY`, completou em **170,77 s**:

- quatro itens LAJ foram materializados: L304, L318, L319 e L326;
- diagnóstico LAJ: L304 e L326 `EXCELENTE`; L318 `REGULAR` (IoU 0,9495, delta
  de área 5,32%); L319 `RUIM` (IoU 0,7777, delta 14,38%);
- quatro DXFs N3 foram gerados e o manifesto Arete foi escrito em
  `scripts/arete/html_fichas/Obra_TREINO_1/TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA_20260714_015744/`.

O G2-V/N1-V CLI foi emitido e lido para L318/L319. Os dois SVGs N1 aparecem e são
distintos; contudo os alertas geométricos continuam visíveis/numéricos. Veredito:
**SUSPEITO, sem PASS e sem selo**. Evidências:

- `scripts/arete/relatorios/g2v/20260714_015948/LAJ_L318_n1xn2.png`;
- `scripts/arete/relatorios/g2v/20260714_015948/LAJ_L319_n1xn2.png`;
- `scripts/arete/relatorios/g2v/20260714_015948/relatorio.json`.

Smokes N3 estruturais: **PASS** para PAINEIS/L304, OBSTACULOS/L319 e UNIOES/L318
(identidade, texto e camadas). Eles não substituem a divergência geométrica N1.

Não houve `--persist-db`: a persistência parcial continua suspensa até corrigir L318/L319
e comparar os campos/links/geometria com o caminho canônico.

## Próximo passo seguro

Atacar universalmente as causas de contorno de L318/L319 em `slab_tracer`, com microciclo
e regressão dos quatro itens. Só após equivalência por campos, links, geometria, contagens
e diagnósticos promover o fast path LAJ e habilitar persistência parcial. Não há base para
selar golden nesta rodada.

## Atualização — prévia N1 fresca (read-only)

O diagnóstico anterior não refletia o `SlabTracer` atual para itens já selados: o merge
canônico protege corretamente o objeto humano inteiro para persistência, mas por isso o
pack somente-leitura renderizava `points` históricos. Foi adicionada uma sobreposição
estritamente efêmera no `headless_sa_analise.py`: preserva selo/metadados humanos, mas
usa apenas a geometria N1 recém-traçada do mesmo DXF para ficha e diagnóstico. Ela nunca
é enviada ao DB.

Microciclo canônico posterior, ainda com `--wait` e `READ_ONLY`:

```text
headless_sa_analise.py --project-id 4869be2b-f17c-410b-a9c8-98a887ec1c95 \
  --secao lajes --item L318 L319 --wait
```

- L318: **EXCELENTE**, IoU `0.99998284`, delta de área `0.0017%`; o contorno fresco tem
  largura `3139` e degrau estrutural correto. A divergência anterior era estado N1 velho,
  não defeito novo de motor.
- L319: visualmente, N1 e o recorte N2 exibem a mesma topologia em L/chanfrada. O
  diagnóstico numérico continua RUIM porque um metadado geométrico auxiliar do DB ainda é
  retangular. Por decisão humana, o recorte N2 aprovado é a referência do 13º pavimento;
  portanto esse alerta é não bloqueante para a consolidação, sem copiar N2 para N1 nem
  alterar o motor.

O N1-V CLI foi relido e preenchido como **SUSPEITO** para ambos, sem PASS: o layout atual
das fichas não prova todas as cotas, painéis, HLAZ e hachuras exigidos pelo checklist.
Evidência: `scripts/arete/relatorios/g2v/20260714_021517/relatorio.json`.

### Regressão do piloto completo

O mesmo caminho canônico foi repetido para L304, L318, L319 e L326. Todas as quatro
fichas têm `5` SVGs, dos quais `2` são evidências N1 (próximo e contexto) com legenda
de alvo. Diagnóstico fresco:

| Item | Resultado | IoU | Delta de área | Leitura |
|---|---:|---:|---:|---|
| L304 | EXCELENTE | 0.99971890 | 0.0281% | simples, sem regressão |
| L318 | EXCELENTE | 0.99998284 | 0.0017% | degrau longo resolvido |
| L319 | RUIM* | 0.78924231 | 15.9007% | metadado N2 auxiliar diverge do recorte humano aprovado; não bloqueante |
| L326 | EXCELENTE | 0.99998877 | 0.0012% | chanfro/contorno complexo sem regressão |

Artefatos: `scripts/arete/html_fichas/Obra_TREINO_1/TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA_20260714_022204/`
e `scripts/arete/relatorios/diagnosticos_laj/Obra_TREINO_1/13_PAV/20260714_022154/`.
