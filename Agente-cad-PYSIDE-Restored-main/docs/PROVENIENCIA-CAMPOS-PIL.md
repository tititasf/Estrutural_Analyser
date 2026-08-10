# Proveniência de campos PIL — contrato inicial

**Classe:** pilares (PIL)
**Estado (2026-07-15):** `validation_ready` — adaptador
`PilEvidenceAuditor` (`scripts/arete/qa_evidence_auditor.py`) implementado e
testado (`tests/test_qa_evidence_auditor_pil.py`). Cobre identity_geometry
(`pilar_segs`/`name`/`dim`) e faces (`p_s{face}_l1_n`/`p_s{face}_v`) +
`connections` derivado. Ver seção "Promoção" abaixo para o que já foi
provado vs. o que ainda falta.

## Evidência primária

1. polígono do pilar no DXF/N1 e suas faces ordenadas;
2. rótulo/cota com posição e camada, associado à mesma geometria;
3. contato geométrico com laje/viga, com face identificável;
4. ficheiro/HTML N1 apenas como apresentação; N2/N4 apenas comparação independente.

| Família observada | Campos/padrão | Categoria | Prova mínima | Tratamento especial |
|---|---|---|---|---|
| Geometria | `pilar_segs` | (a) extração | polígono fechado e não degenerado | não reduzir L/U/circular a bbox retangular |
| Identidade | `name` | (a) extração | texto canônico `P...` associado ao polígono | texto distante não é rótulo do pilar |
| Dimensão | `dim` | (a)/(b) | cota ou duas paredes identificadas | `VF...` não é dimensão de seção |
| Relação de face com laje | `p_s[A-H]_l*_n` | (a) relação | face do pilar + laje nomeada + contato/adjacência | nome de laje sem face/contato |
| Relação de face com viga | `p_s[A-H]_v_*_[nd]` | (a) relação | face + viga + dimensão/posição correspondente | copiar relação da face vizinha |
| Conexões resumidas | `connections` | (b) derivado | relações de face já comprovadas | lista livre que contradiz as faces |

## Regras críticas

- Pilar não retangular requer prova por faces/partes; comparação simples de largura × comprimento é inválida.
- Face, nome da viga/laje e geometria devem concordar. Qualquer um sem os outros permanece pendente.
- Relações entre pavimentos são contexto consultivo, jamais cópia de atributos do pavimento vizinho.

## Promoção

**Provado em produção (2026-07-15, P35/13_PAV, pilar retangular):**
- `pilar_segs`, `name`, `dim`: CONFIRMAR via bbox/rótulo, independente do
  link bruto (achado real: link `dim` apontava pro rótulo de uma viga
  vizinha, `V328`, não pra cota do pilar — adaptador ignora esse link e usa
  `extra.fields["Dimensão (b x h)"]` + bbox, registrando o link ruim como
  finding `PIL-DIM-LINK-MISLABELED`, sem travar o campo).
- `p_s{face}_v`: re-derivado de `pillar_face_beams.enrich_pillar_report_with_beams`
  (motor puro, sem Qt) — cobre viga que passa, que para/chega, e Caso 4
  (face interior ao corpo da viga). Evidência = `evidence_segments` (linhas
  reais do DXF), não o texto persistido.
- `p_s{face}_l1_n`: contato geométrico real via Shapely
  (`pillar.distance(slab)`), não o nome do link. Achado real: P35 tinha
  `p_sD_l1_n=L325` persistido, mas L325 está a 556cm de distância — o
  adaptador corretamente recusa (`PENDENTE`), não confirma um nome sem
  contato.
  **Causa raiz corrigida (2026-07-16):** o pipeline só escrevia
  `p_s{face}_l1_n` quando `pillar_face_beams` confirmava laje na face
  (`content_type` em `laje`/`both`); faces 100% ocupadas por viga
  (`content_type='viga'`, sem laje geométrica) ficavam sem proteção e
  caíam na busca textual cega por raio do `PillarAnalyzer`
  (`_analyze_field`, radius=800, sem checagem de contato) — que podia
  gravar o nome de uma laje distante. Fix: `main.py` agora escreve
  `SEM LAJE` como valor autoritativo quando a face é só-viga
  (`main.py` — bloco `# Popular campos p_s{side}_*`), e
  `src/core/pillar_analyzer.py::analyze` respeita esse marcador
  (`_face_beam_authoritative_fields`) para não sobrescrever. Regenerado
  no DB via `scripts/arete/fix_pil_l1n_no_slab_contact.py` (dry-run→apply,
  tolerância 15cm, preserva campos `validated_fields_json`): 43 de 46
  pilares do 13_PAV tinham o mesmo padrão (distâncias de 24cm a 616cm,
  vários vãos/aberturas reais do projeto) — todos corrigidos para
  `SEM LAJE`, reauditados como `N/A_CONFIRMADO` (confidence high). Nenhum
  `PENDENTE` restante em `p_s{face}_l1_n` na classe PIL do projeto após o
  fix.
- `connections`: derivado (categoria b) das faces já confirmadas na mesma
  rodada; diverge → `REVISAR_HUMANO`.
  **Causa raiz corrigida (2026-07-16):** não havia dois motores divergentes —
  `main.py:6407` chama o MESMO `enrich_pillar_report_with_beams`. O bug era
  do próprio adaptador: comparava `connections` persistido só contra
  `face_beams` (passa/para/interior, só A/B), mas vínculos por alinhamento de
  parede em C/D (`source: beam_wall_alignment`) só existem na lista `lajes`
  do motor (a mesma que `main.py` persiste como `connections.details`),
  nunca em `face_beams`. Fix: `_audit_connections` agora compara contra
  `face_beams` **união** as entradas `beam_wall_alignment` de `lajes` (a
  mesma rodada do motor, via `_enriched_report_for`, que cacheia as duas
  saídas). Usar só `lajes` sozinho regride (perde a cobertura A/B que só
  `face_beams` tem — testado e revertido). 2 testes de regressão em
  `tests/test_qa_evidence_auditor_pil.py` com a geometria real de P11/V302.
  Resultado: 37/46 pilares selados (de 30); REVISAR_HUMANO real restante
  (9 itens, 12 campos) é um padrão distinto — candidatos de viga diferentes
  escolhidos por `connections` vs `p_s{face}_v` na mesma rodada (ex. P29 face
  C: `connections`→V306, `p_sC_v`→VF202) — provável bug de desambiguação em
  `pillar_face_beams.py`, não investigado a fundo ainda.

**Ainda não provado / pendente para promoção completa:**
- Pilares L/U/circular/especial (só retangular testado até agora).
- `p_s{face}_v` ainda não entra no conjunto estático de campos obrigatórios
  do selo (`REQUIRED_PIL_BASE_FIELDS`) — contribui evidência mas não
  bloqueia/libera o selo geral nesta primeira versão; promover isso exige
  decidir o que fazer quando uma face genuinamente não tem viga nenhuma
  (hoje vira `N/A_CONFIRMADO`, o que já seria suficiente, mas não foi
  incluído no set obrigatório por cautela).
- Regressão cross-classe PIL↔FV/LV (checar que nenhuma decisão PIL
  altera/consulta campo de FV/LV além do que já era consultivo read-only).
