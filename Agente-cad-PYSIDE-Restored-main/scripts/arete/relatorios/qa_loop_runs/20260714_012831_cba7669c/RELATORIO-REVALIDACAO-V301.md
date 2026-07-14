# Revalidação LV — V301

## Concluído

- O headless canônico com `--wait --persist-db` foi reexecutado após a extração
  de `src/core/beam_support_links.py`; concluiu e publicou seis DXFs N3 de
  V301: PARA/PASSA × Corte/A/B.
- A probe `V301_four_contracts_v6_pass.json` passou 39/39 checks: quatro
  contratos, lado, comportamento, `generation_ready`, `source_key`,
  `source_slot`, isolamento, ausência de fallback FV, apoio LV `V309A` e
  contato geométrico.
- O smoke `n3_smoke_V301_v2.json` passou nas seis variantes. A vista Corte
  valida somente as camadas que lhe pertencem.
- A ficha de revisão focada foi publicada em `ficha_motor_n3_V301/index.html`.

## Visual G5-V

Não selado. A imagem HTML carregada pelo harness apontou para outro run N3;
isso não prova os DXFs do fast path alvo. O fallback DXF que escolhia qualquer
arquivo com o mesmo nome foi fechado: LV exige a ficha HTML com Corte, A e B,
e não pode cair em `FV_preview_V301`.

Próximo passo: publicar a ficha granular a partir dos mesmos seis DXFs N3 do
run e repetir G5-V CLI, então seguir V327, V330 e V322.
