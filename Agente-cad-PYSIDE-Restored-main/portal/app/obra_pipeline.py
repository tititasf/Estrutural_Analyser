"""Cadeia da obra: uma fila pesada, opções congeladas e recibos por pavimento."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from fastapi import HTTPException
from src.core.vigas_drawing_config import normalize_config, require_supported_generation
from ..db import repository as repo
from . import pipeline_runner, n5_release, recortes_reader, torre_crop, viewer_pavimentos


def documentos_para_triagem(settings, obra, documentos):
    root = Path(obra['local_path']) if obra.get('local_path') else settings.dados_obras_dir / obra['nome']
    crops = root / 'Fase-2_Triagem' / 'recortes'
    completed = set()
    if crops.is_dir():
        completed = {recortes_reader.stem_bruto_canonico(p.name).casefold() for p in crops.iterdir()
                     if p.is_dir() and any(str(i.get('item_id', '')).startswith('torre')
                                           for i in torre_crop.listar_recortes_bruto(root, p.name))}
    return [d for d in documentos if d['status'] in ('pendente', 'erro') or
            (str(d['arquivo_nome']).lower().endswith(('.dxf', '.dwg'))
             and (d.get('tipo_documento_confirmado') or d.get('tipo_documento_sugerido')
                  or d.get('classe_confirmada') or d.get('classe_sugerida')) == 'Bruto'
             and recortes_reader.stem_bruto_canonico(Path(d['arquivo_nome']).stem).casefold() not in completed)]


def preprocessar_pavimento(conn, settings, obra, pavimento, run_id, progress):
    from .preprocessamento.sources import inventory_floor_sources, raw_level_references, SourceKind
    from .preprocessamento.preprocess_runner import execute_inventory_job
    root = Path(obra['local_path']) if obra.get('local_path') else settings.dados_obras_dir / obra['nome']
    documents = repo.listar_documentos_por_obra(conn, obra['id'])
    kinds = set(SourceKind)
    sources = [s for s in inventory_floor_sources(obra_dir=root, obra_id=obra['id'],
                pavimento_id=pavimento, documents=documents) if s.kind in kinds]
    frozen = {s.source_id: s.revision for s in sources}
    frozen.update({s['source_id']: s['revision'] for s in raw_level_references(root, sources)})
    floors = {d.get('pavimento_confirmado') or d.get('pavimento_sugerido') for d in documents}
    return execute_inventory_job(obra_dir=root, obra_id=obra['id'], pavimento=pavimento,
        job_id=run_id, frozen_sources=frozen,
        declarations=[{'bruto_id': s.bruto_id, 'item_id': s.item_id} for s in sources],
        progress=progress, known_floors=sorted(f for f in floors if f))


def descobrir_pavimentos(conn, settings, obra):
    """Documentos atuais com torre limpa; pastas históricas não ampliam a obra."""
    root = Path(obra['local_path']) if obra.get('local_path') else settings.dados_obras_dir / obra['nome']
    crops = root / 'Fase-2_Triagem' / 'recortes'
    if not crops.is_dir():
        return []
    documents = {recortes_reader.stem_bruto_canonico(Path(d['arquivo_nome']).stem).casefold(): d
                 for d in repo.listar_documentos_por_obra(conn, obra['id'])}
    floors = set()
    for folder in crops.iterdir():
        if not folder.is_dir():
            continue
        doc = documents.get(recortes_reader.stem_bruto_canonico(folder.name).casefold())
        if not doc:
            continue
        floor = doc.get('pavimento_confirmado') or doc.get('pavimento_sugerido')
        if floor and any(str(item.get('item_id', '')).startswith('torre')
                         for item in torre_crop.listar_recortes_bruto(root, folder.name)):
            floors.add(floor)
    return sorted(floors, key=viewer_pavimentos._ordem)


def enfileirar_cadeia(request, conn, obra, membro, body, pavimentos):
    if body.visual_mode in {'MOLDE_2', 'MOLDE_3'}:
        raise HTTPException(status_code=422, detail='Molde 2 e Molde 3 ainda não possuem desenho implementado.')
    active = conn.execute("SELECT id FROM portal_jobs WHERE obra_id=? AND status IN ('na_fila','executando')", (obra['id'],)).fetchall()
    if any(repo.obter_job_meta(conn, row['id']).get('etapa') in {'triagem', 'recortes'} for row in active):
        raise HTTPException(status_code=409, detail='Aguarde Triagem + Recortes terminar antes de iniciar a cadeia completa.')
    config = normalize_config({
        'comportamento_laterais_vigas': body.lateral_assembly,
        'fundos_vigas_possui_garfos': body.fundos_garfos,
    })
    try:
        require_supported_generation(config)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    pavimentos = list(dict.fromkeys(pavimentos))
    if not pavimentos:
        raise HTTPException(status_code=422, detail='Conclua Triagem + Recortes antes: nenhum pavimento com torre limpa encontrado.')
    if body.pavimento is not None:
        if body.pavimento not in pavimentos:
            raise HTTPException(status_code=422, detail='O pavimento selecionado não possui torre limpa nos documentos atuais. Atualize a lista após Triagem + Recortes.')
        pavimentos = [body.pavimento]
    # O ID representa o código efetivamente instalado, sem consultar Git.
    digest = hashlib.sha256()
    for name in ('obra_pipeline.py', 'pipeline_runner.py', 'n5_release.py'):
        digest.update(Path(__file__).with_name(name).read_bytes())
    meta = dict(etapa='motores_obra', pavimentos=pavimentos, visual_mode=body.visual_mode,
                vigas_config=config, membro_id=membro['id'], escopo='global')
    job_id, created = repo.enfileirar_job_unico_por_meta(
        conn, obra_id=obra['id'], meta=meta,
        chaves=('etapa', 'pavimentos', 'visual_mode', 'vigas_config'),
        engine_version='source-' + digest.hexdigest()[:16],
    )
    if created:
        request.app.state.job_meta[job_id] = meta
        repo.atualizar_estado_obra(conn, obra['id'], 'processando')
    return dict(job_id=job_id, pavimentos=pavimentos, total=len(pavimentos),
                estado='queued', reutilizado=not created)


def executar_cadeia(app_state, conn, settings, obra, job, meta, log_path):
    """Headless n3 já interpreta SA; não repetir a leitura em dois subprocessos."""
    require_supported_generation(meta['vigas_config'])
    pavimentos = meta['pavimentos']
    total = len(pavimentos) * 6  # Pré-processamento, SA+N3 e quatro N5.
    completed = []
    pending = []

    def checkpoint(pav, stage):
        current = conn.execute('SELECT status FROM portal_jobs WHERE id=?', (job['id'],)).fetchone()
        if current and current['status'] == 'cancelado':
            raise InterruptedError('Cadeia interrompida pelo operador')
        meta['cadeia'] = dict(pavimento=pav, etapa=stage, concluidos=len(completed),
                              total=total, recibos=list(completed), pavimentos=pavimentos,
                              visual_mode=meta['visual_mode'], vigas_config=meta['vigas_config'],
                              pendencias=list(pending), parcial=bool(pending))
        repo.salvar_job_meta(conn, job['id'], meta)
        app_state.job_meta[job['id']] = meta
        with log_path.open('a', encoding='utf-8') as log:
            log.write(f'{pav} · {stage} · {len(completed)}/{total}\n')

    with pipeline_runner.gate_cad_em_fundo():
        _executar_pavimentos(app_state, conn, settings, obra, job, meta, log_path,
                             pavimentos, completed, pending, checkpoint)
    checkpoint(pavimentos[-1], 'Concluído')


def _executar_pavimentos(app_state, conn, settings, obra, job, meta, log_path,
                         pavimentos, completed, pending, checkpoint):
    for index, pav in enumerate(pavimentos):
        checkpoint(pav, 'Pré-processamento')
        started = time.monotonic()
        def preprocess_progress(value):
            meta['progress'] = value
            checkpoint(pav, 'Pré-processamento')
        inventory = preprocessar_pavimento(conn, settings, obra, pav,
                                           f"{job['id']}_pav_{index + 1}", preprocess_progress)
        if inventory['status'] == 'failed':
            raise ValueError(f'{pav} · Pré-processamento: nenhum pacote de contexto utilizável; consulte o log.')
        # O inventário mantém status partial enquanto detalhes não são suportados;
        # preservar o recibo sem confundir esse estado com falha de um item N3/N5.
        completed.append(dict(pavimento=pav, etapa='Pré-processamento', result=inventory,
                              duration_s=round(time.monotonic() - started, 3)))
        checkpoint(pav, 'SA + N3')
        started = time.monotonic()
        floor_log = log_path.with_name(f'{log_path.stem}_pav_{index + 1}.log')
        # O caminho n3 publica SA e audita o manifesto N3 desta própria execução.
        result = pipeline_runner.executar_etapa(
            settings, 'n3', obra, pav=pav, secao=None, dry_run=False,
            log_path=floor_log, visual_mode=meta['visual_mode'], vigas_config=meta['vigas_config'],
        )
        if not result.ok:
            lines = result.log_tail.splitlines()
            failures = [line for line in lines if 'FALHOU' in line or 'Traceback' in line]
            detail = failures[-1] if failures else result.log_tail[-350:]
            raise ValueError(f'{pav} · SA/N3: {detail[:400]}')
        pending.extend(dict(pavimento=pav, etapa='SA + N3', detalhe=issue)
                       for issue in result.artefatos.get('item_pending', []))
        from .knowledge_scope import best_effort_sa
        best_effort_sa(obra, pav)
        completed.append(dict(pavimento=pav, etapa='SA + N3', log_path=str(floor_log),
                              duration_s=round(time.monotonic() - started, 3)))
        manifest_path = result.artefatos.get('production_manifest')
        counts = json.loads(Path(manifest_path).read_text(encoding='utf-8')).get('n1_counts', {}) if manifest_path else {}
        for classe in ('PL', 'LV', 'FV', 'LJ'):
            checkpoint(pav, 'N5 ' + classe)
            # Ausência comprovada no recibo desta rodada não é um N3 faltante.
            category = {'PL':'pillars', 'LV':'beams', 'FV':'beams', 'LJ':'slabs'}[classe]
            if counts.get(category) == 0:
                completed.append(dict(pavimento=pav, etapa='N5 ' + classe, status='sem_itens'))
                continue
            started = time.monotonic()
            release = n5_release.liberar_n5(
                conn, settings, obra=obra, classe=classe, pavimento=pav,
                membro_id=meta['membro_id'], job_id=job['id'],
                engine_version=job.get('engine_version'), dry_run=False,
                visual_mode=meta['visual_mode'], vigas_config=meta['vigas_config'],
            )
            pending.extend(dict(pavimento=pav, etapa='N5 ' + classe, **issue)
                           for issue in release.get('item_pending', []))
            completed.append(dict(pavimento=pav, etapa='N5 ' + classe,
                                  status='pendente' if not release['dxf_path'] else ('parcial' if release.get('partial') else 'completo'),
                                  release_id=release['release_id'], dxf_path=release['dxf_path']))
            completed[-1]['duration_s'] = round(time.monotonic() - started, 3)
        checkpoint(pav, 'Pavimento concluído')
