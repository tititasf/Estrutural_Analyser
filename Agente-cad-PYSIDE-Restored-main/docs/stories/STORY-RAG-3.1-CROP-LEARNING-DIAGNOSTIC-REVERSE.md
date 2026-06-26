# STORY RAG-3.1 - Crop Learning no Diagnostic Reverse Hub

## Objetivo

Separar a aprovacao manual de recorte da validacao de ficha/campos/N4.

Quando o usuario aprova um recorte no Diagnostic Reverse Hub, o sistema deve aprender a
recortar melhor por classe, mas nao deve promover a ficha F5/N2 para T1, nao deve validar
campos e nao deve validar N4.

## Contexto

Fonte de arquitetura:

- `D:\Agente-cad-PYSIDE\MASTERPLAN-CEREBRO-RAG-MULTIMODAL-v1.0.md` v2.3
- Secao 3.7: Aprendizado de Recorte no Fluxo Reverso
- EPIC RAG-3.1: Hook de aprendizado de recorte no Diagnostic Reverse Hub

Decisao do dono:

> A aprovacao manual do recorte valida somente o recorte, mas tambem deve ensinar o
> sistema a recortar melhor cada classe, inclusive classes futuras.

## Arquivos alvo

Localizar antes de editar:

- `src/ui/modules/diagnostic_reverse_hub.py`
- storage/eventos existentes para `training_events` / `rag_validation_events`
- se nao existir storage adequado, criar migracao/tabela `crop_learning_events`
- Curadoria em `src/ui/widgets/project_manager.py` apenas se a story incluir exibicao

## Comportamento esperado

Ao aprovar recorte:

1. Gravar evento `crop_learning_event`.
2. Persistir:
   - obra
   - pavimento
   - classe
   - source_dxf
   - source_layer
   - source_color
   - bbox_json
   - polygon_json, se houver
   - margin_profile_json
   - nearby_entities_json
   - approved_by
   - approved_at
   - method_version
   - status = `validated`
3. Disponibilizar esse exemplo para o motor de recorte consultar em sugestoes futuras.
4. Atualizar metricas da Curadoria/Memoria de Recortes quando existir UI.

## Nao fazer

- Nao chamar `indexar_validados.py` para a F5 por causa do recorte.
- Nao marcar `reverse_eng_fichas.status = aprovado` por causa do recorte.
- Nao marcar campos como validados.
- Nao validar N4.
- Nao promover T0 para T1 no RAG global de fichas.
- Nao apagar historico ao desvalidar; usar tombstone/revogacao.

## Gate de aceite

- Aprovar um recorte cria exatamente um evento de crop learning.
- A F5 vinculada continua T0/draft/extracted ate validacao explicita de campos.
- Query global de fichas nao passa a retornar essa F5 apenas por causa do recorte.
- O proximo ciclo de sugestao de recorte consegue consultar exemplos CROP-T1 da mesma classe.
- Teste automatizado cobre que aprovacao de recorte nao promove F5.

## Validacao minima

Rodar ou criar teste focado:

```powershell
python -m pytest tests -k "crop_learning or diagnostic_reverse"
```

Smoke manual:

1. Abrir Diagnostic Reverse Hub.
2. Selecionar uma classe e um recorte candidato.
3. Aprovar recorte.
4. Confirmar evento de recorte gravado.
5. Confirmar que F5/N2 nao virou T1 e N4 nao foi validado.
