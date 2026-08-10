# Checklist do gate de evidência

## Escopo

- [ ] `project_id` resolvido sem ambiguidade.
- [ ] Obra, pavimento, classe, item, nível, parte e variante explícitos.
- [ ] DB real e Python 3.12 confirmados.

## Proveniência

- [ ] Cada conclusão cita fonte, caminho, hash e versão do adaptador.
- [ ] N1 não é usado como prova de si próprio.
- [ ] N3 recebe somente N1 + contrato/configuração.
- [ ] N2/N4 aparecem apenas como comparação independente.
- [ ] HTML/checkbox é apresentação, não ground truth.

## Rota de execução

- [ ] Mudança N1 usa headless único com `--wait`.
- [ ] Mudança apenas N3/N4 usa gerador/ficha individual, sem headless.
- [ ] Gate visual usa `g2v_harness.py --backend cli` e o PNG foi lido.
- [ ] Não há execução AutoCAD/headless paralela.

## Decisão

- [ ] `CONFIRMAR` somente com adaptador autorizado (LAJ/PIL/FV/LV) e evidência independente.
- [ ] PASS de um segmento/contrato FV/LV não é tratado como ficha/viga inteira aprovada.
- [ ] Autoridade da classe confere com `data/authority_matrix.json`.
- [ ] Achado tem causa geral; nenhuma medida foi hardcodada por item.
- [ ] Fix executado tem regressão proporcional e nenhum FAIL novo.

## RAG

- [ ] Consulta filtra classe, família, campo, tier e escopo.
- [ ] T1/T2 é citado; T3 nunca confirma campo.
- [ ] Candidato exige aprovação humana; promoção não é automática.
