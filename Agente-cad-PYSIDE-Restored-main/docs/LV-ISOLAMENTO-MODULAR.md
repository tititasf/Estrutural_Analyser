# LV — isolamento modular e limites de edição

Este mapa reduz colisões sem criar cópias divergentes da regra estrutural.

## Núcleos com responsabilidade única

- `src/core/lv_generation_contract.py`: constrói os quatro contratos canônicos
  `A_PARA`, `B_PARA`, `A_PASSA` e `B_PASSA`. Não decide UI nem ficha.
- `src/core/beam_support_links.py`: normaliza somente metadados de apoio global.
  Não calcula dimensão LV e não usa FV como fallback.
- `src/core/lv_support_contact.py`: prova contato local entre um segmento LV e
  um apoio nomeado. Um rótulo de limite global que não toca o segmento é
  descartado; o módulo nunca escolhe um apoio alternativo por proximidade.
- `src/ui/widgets/preficha_lateral_html.py`: apresenta evidência; não interpreta
  N1, não modifica contratos e não persiste dados.
- `scripts/arete/headless_sa_analise.py`: única porta de execução/persistência
  headless. Orquestra; não duplica regra de contrato.
- `scripts/arete/qa_profile_probe.py` e `qa_n3_smoke.py`: provas declarativas,
  sem escrita no DB. A prova de apoio infere a classe pelo identificador real
  (`P*` → PIL, `V*` → LV, `L*` → LAJ), nunca força PIL.
- `scripts/arete/g2v_harness.py`: veredito visual CLI. Para LV, Corte/A/B são
  três vistas; um DXF único nunca pode ser escolhido por glob como substituto.

## Regra de autonomia por agente

Agentes podem editar livremente documentos sob `docs/LV-*`, relatórios LV e
testes diretamente vinculados a módulos LV. Para tocar `main.py` ou um módulo
compartilhado, a alteração exige causa reproduzível e deve ser extraída para um
helper neutro quando servir a mais de uma classe — como
`beam_support_links.py`. Isso evita prender a regra LV a um método grande e
evita disputa com PIL, LAJ ou FV.

## Fronteira de dados

N1 alimenta N3; N2 alimenta N4. N2/N4 nunca preenchem campo ou dimensão LV de
N1. FV pode ser lido como contexto de apoio apenas quando houver prova, mas
nunca como fallback de dimensão lateral. Corte é contexto comum e não permite
espelhar A/B nem PARA/PASSA.

## Estado desta extração

O helper de apoio que estava aninhado em `main.py` foi removido para
`src/core/beam_support_links.py`; o fast-path invalida cache também quando
`lv_generation_contract.py` muda. Os contratos continuam quatro estruturas
independentes e a ficha N1 emite exatamente uma vista próxima e uma contextual
por segmento.

Em 14/07, o caso V327 provou por geometria que V328 é uma viga paralela, não
um apoio da lateral: os dois eixos estão separados por 146 cm. O endpoint P27
intersecta a lateral. A passagem FV→LV agora depende de
`lv_support_contact.py`, preservando somente campos explicitamente validados
pelo humano.
