# QA fast paths — campos N1 e artefatos N3/N4

## Limite de autoridade

Um probe ultragranular responde somente às hipóteses declaradas no request. Um
`PASS` de identidade, dimensão e contato não aprova o item, a ficha, a
interpretação completa, o desenho ou o gate visual. N2/N4 não alimentam N1/N3.

## 1. Campo ou vínculo N1 específico

Use `qa_n1_field_probe.py` quando o dado já estiver persistido ou quando quiser
testar um candidato por overlay, sem escrever no DB. Cada campo declara classe,
item, fonte, caminho e transformação. O mesmo request pode cruzar PIL, FV, LV e
LAJ para consolidar uma hipótese localizada.

```powershell
py -3.12 -X utf8 scripts/arete/qa_n1_field_probe.py `
  --request scripts/arete/qa_requests/examples/pil_p35_face_d_v328.json `
  --out scripts/arete/relatorios/qa_field_probes/p35_face_d_v328.json
```

Fontes mínimas disponíveis: `payload`, `geometry`, `sides`, `extra`,
`confidence` e `column`, conforme a classe. Somente as colunas solicitadas são
lidas. O resultado registra campos, checks, snapshots, proveniência e tempo.

Um overlay tem o formato abaixo e nunca é persistido:

```json
{"fields": {"pillar.face_d.beam_name": "V999"}}
```

Para hipóteses recorrentes, use `qa_profile_probe.py`; ele carrega o catálogo
específico de PIL/LAJ/FV/LV. O escopo é obrigatório e as famílias FV/LV têm
allowlists separadas apesar de compartilharem `beams.data_json`.

```powershell
py -3.12 -X utf8 scripts/arete/qa_profile_probe.py `
  --classe PIL --probe face_beam_identity_dimension_contact `
  --item P35 --var face=D --project-id <ID>
```

## 2. Quando ainda usar headless

- Ajuste de regra sobre valores já persistidos: probe focado, sem headless.
- Mudança em extração, associação CAD ou materialização N1: headless canônico,
  granular, único e com `--wait`; depois repetir o probe.
- Ajuste só de desenho N3/N4: gerador individual e ficha de motor, sem headless.
- Certificação: regressões e gates completos continuam obrigatórios.

## 3. Paridade contrato → payload → DXF → HTML

Use `qa_artifact_parity.py` para declarar campos equivalentes em cada artefato.
O resultado prova somente a cadeia declarada e não substitui leitura visual.
Metadado DXF ausente fica explícito; não é inferido do HTML.

`ficha_motor_item.py --contract ROTULO=arquivo.json` registra hashes do contrato,
DXF, SVG e HTML. O render DXF→SVG usa cache por conteúdo.

Antes da ficha, `qa_n3_smoke.py` verifica cada variante declarada: identidade do
contrato no DXF, texto e camadas mínimas do perfil. Esse PASS não valida abertura,
vazio, recorte, cotagem ou equivalência geométrica.

```powershell
py -3.12 -X utf8 scripts/arete/qa_n3_smoke.py `
  --classe LV --item V301 `
  --contract A_PARA=<contrato.json> --dxf A_PARA=<artefato.dxf> `
  --contract A_PASSA=<contrato.json> --dxf A_PASSA=<artefato.dxf>
```

Catálogo detalhado: `docs/QA-PERFIS-CLASSES-SA-N1-N3.md`.

## 4. Cache e benchmark

O cache inclui versão do motor, request/overlay e hashes das linhas ou arquivos
usados. Mudança em qualquer entrada gera outra chave. Cache não muda autoridade.

```powershell
py -3.12 -X utf8 scripts/arete/qa_fastpath_benchmark.py `
  --request scripts/arete/qa_requests/examples/pil_p35_face_d_v328.json `
  --iterations 20 `
  --out scripts/arete/relatorios/qa_field_probes/benchmark_p35.json
```

O benchmark compara o mesmo conjunto de checks sem cache e aquecido, e exige
resultado semântico idêntico.

## 5. RAG

Consulta RAG é consultiva e particionada por classe, família, campo, tier, obra e
pavimento quando o schema disponibiliza esses campos. Se um filtro pedido não
existir no schema, a consulta é marcada degradada e não pode satisfazer
`--rag-evidence required`.
