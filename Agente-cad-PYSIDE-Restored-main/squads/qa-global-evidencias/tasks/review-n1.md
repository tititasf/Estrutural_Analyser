---
task: review-n1
agent: aegis
inputs: [scope.json, evidence-index.json]
outputs: [decisoes.jsonl, achados.jsonl, perguntas.jsonl]
mutates: false
scripts:
  - scripts/arete/qa_n1_field_probe.py
  - scripts/arete/qa_profile_probe.py
  - scripts/arete/qa_evidence_auditor.py
  - scripts/arete/headless_sa_analise.py
---

# Revisar N1

1. Para hipótese localizada em snapshot já persistido, declarar os campos e
   checks em `qa_n1_field_probe.py`; pode cruzar classes sem copiar atributos.
2. Para hipótese modelada no perfil da classe, usar `qa_profile_probe.py` com
   `--project-id` (ou `--use-profile-sample` consciente).
3. Para cobertura ampla do snapshot, executar `qa_evidence_auditor.py review`.
4. Se extrator/vínculo mudou, materializar com `headless_sa_analise.py --secao ... --item ... --wait` antes de revisar.
5. Exigir adaptador de classe para confirmar geometria, faces, segmentos ou painéis.
6. Em **FV/LV** genérico, usar `TRILHA_N1_OBSERVADA` ou `PENDENTE`, nunca `CONFIRMAR` pleno.
7. Em **LAJ/PIL**, `CONFIRMAR` só via adaptador (`LajEvidenceAuditor` / `PilEvidenceAuditor`).
8. N1 não prova a si próprio; HTML e checkbox também não.
9. Consultar `data/authority_matrix.json` se houver dúvida de selo.

## Aceite positivo

- Cada decisão cita evidência independente ou permanece `PENDENTE`.
- Probe: apenas os checks declarados recebem PASS/FAIL/PENDENTE; cache frio e
  aquecido têm o mesmo resultado semântico.
- Escopo inequívoco (`project_id`).

## Aceite negativo (o que PASS **não** autoriza)

- PASS de probe/profile **não** aprova item, ficha, pavimento ou classe.
- Review genérico FV/LV **não** grava `apply` nem selo laranja.
- Cobertura PIL (`qa_pil_coverage`) **não** sozinha libera apply.
- Score de sessão / arquivo aberto / HTML **não** fecham interpretação.


### Rastreio de confiança por região e segmento — QA-NIV-RASTREIO-20261003

Antes de perguntar ao dono ou alterar score, seguir `source_fact_ids` até as fontes independentes; registrar CAD/handles, região principal ou interna, posição do corte, datum, unidade, cobertura e fator de transferência. Fonte inferida com somente nome da laje ou ID de coleção não equivale a uma cota CAD rastreada. Uma região medida não confirma automaticamente outra região da mesma laje. Não contar a mesma origem em FV/LV/LAJ como provas independentes.

Conferir primeiro se o problema é leitura/associação: corte com haste interrompida pode conservar delta de abas, mas não comprova altura absoluta; ligar a aba à região realmente tocada e à espessura correspondente. Não elevar confiança apenas pelo nome do método ou por concordância que nasceu do mesmo fato. Avisos de níveis múltiplos só podem ser removidos após resolver a região proprietária e o contato; não apagar a penalidade genericamente.

FV e LV têm contratos próprios de geometria, apoios e segmentos. Transferência de nível com fonte independente congelada, prova espacial e grafo acíclico é permitida; não autoriza copiar esses outros campos nem equiparar a quantidade de segmentos. Padrão aprovado pelo dono, medida e derivação permanecem origens distintas. Score é suporte de evidência, não probabilidade calibrada; melhorar rastreabilidade pode mudar o suporte somente após validação por faixa, sem selo automático.

Pergunta humana deve indicar o trecho e alternativas concretas após tentar cortes, hachuras, cotas, regiões LAJ e correspondência FV/LV. Falha do coletor em encontrar uma fonte não prova ausência no desenho. Caso datado e diagnóstico reproduzível: `scripts/arete/relatorios/20261003-nivel-padrao/remaining-audit.json`; não transformar seu resultado em regra fixa por item.


### Harmonia das confirmações — NIV-HARMONIA-GATES-20261003

Contrato canônico: docs/INTERPRETACAO-NIVEIS-POR-REGIAO-E-SEGMENTO.md, seção Harmonia de fontes, gates e explicação. Plano aprovado; implementação nova delegada e não certificada por este texto.

- Auditar origem/revisão, associação espacial, grandeza/unidade/datum, exceções/completude da leitura e concordância por intervalo.
- Separar corte CAD e seção A/B reconstruída. Nível herdado em corte reconstruído, N3/N4 ou outra classe não é nova prova; deduplicar raízes físicas compartilhadas. RAG é regra/contexto, não voto.
- Fonte forte não apaga conflito válido. Entradas necessárias limitam o caminho; alternativas fracas irrelevantes não devem ser confundidas com essas entradas.
- Exigir fontes congeladas, grafo acíclico e preservação humana; PIL não certifica de volta FV/LV/LAJ.
- Percentual com explicação por unidade: fonte, cálculo, confirmações independentes, gates e limitações. Confiança do nome não é confiança do nível. Nenhum bônus arbitrário ou probabilidade sem calibração independente.
- Comparar baseline/revisão por unidade e testar duplicação, permutação, ciclos, contradições, degraus, cortes interrompidos, ausência de laje e passagem por pilar. Relatar implementação, teste, publicação, consumo e PNG separadamente.


### Caminho de evidência v18 — NIV-EVIDENCIA-CAMINHOS-20261003

Implementação do plano acima no motor v18 (`level_provenance.py`, rubrica `level_evidence_completeness_v1.1-best-validated-path`). Ao revisar um nível:
- Ler `support_explanation` do fato: fonte principal/tipo de origem, cadeia de cálculo, origens, confirmações (sem bônus), limitações e gates. Gate `fail` em origem, ciclo, fontes presentes, grandeza ou transferência = nível não certificável.
- Associação FV↔corte só vale com `cut_association=stem_matches_fv_section` (tronco com profundidade/largura da FV); `contact_only` mantém o mais fraco.
- Corte girado só re-prova valor existente; espessura de asa desenhada ≠ h declarado = abstenção correta (ex.: L303, L321 no 13_PAV), não FAIL do motor.
- `evidence_provenance` da torre deve ter ciclos=0, fontes ausentes=0 e violações de aumento=0. Resultado datado: scripts/arete/relatorios/20261003-evidencia-caminhos/RELATORIO.md.

### Datum comum v19 — NIV-DATUM-COMUM-20261003

Fundo resolvido por `standard_beam_top_principal_slab` com aviso `lower_adjacent_slab_closed_by_top_panel`: conferir que as fontes são a laje no datum + o datum do pavimento, que toda laje em `lower_contact_slabs` está abaixo do datum e que nenhuma laje acima toca o fundo (laje acima = abstenção obrigatória; só corte/hachura mudam a viga). Laje sem cota no DXF continua fraca e não é FAIL do motor. Resultado datado: scripts/arete/relatorios/20261003-faixas-sem-raiz/RELATORIO.md.

### Nível de laje em camadas v20 — NIV-LAJE-CAMADAS-20261003

Laje com `method` = `slab_neighbor_continuity_without_step_cut` (teto 85) ou `slab_neighbor_majority_vote` (teto 75): conferir em `neighbor_votes` que cada vizinha está do outro lado de uma viga real (seção de FV no corredor, não distância), que cada voto vem de origem CAD/humana distinta e que nenhum voto tem a própria laje alvo nas raízes (ciclicidade). Empate deve abster. Voto através de viga em `proven_step_lines` (pares CAD já diferem) deve estar em `withheld_votes`, nunca contado. Valor da camada diferente do SA aparece em `slab_level_layers.not_applied`, nunca aplicado. Aviso `drawn_wing_thickness_differs_from_declared_h`: o h declarado vence a asa desenhada; a asa só re-prova o valor que já existe. Não há hachura de laje como evidência. Regra: docs/INTERPRETACAO-NIVEIS-POR-REGIAO-E-SEGMENTO.md, seção NIV-LAJE-CAMADAS-20261003.
