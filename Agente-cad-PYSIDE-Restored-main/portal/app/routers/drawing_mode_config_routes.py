"""Owner-managed global N3 drawing profiles, with optimistic concurrency."""
import sqlite3
from fastapi import APIRouter, Depends, HTTPException, Request, File, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
from scripts import drawing_mode_config as profiles
from .. import access
from ..dbdep import get_db_conn
from .. import drawing_frame, example_crops
from .paginas_routes import _membro_da_sessao, _render

router = APIRouter(tags=['drawing-mode-config'])


class ExampleCropPayload(BaseModel):
    kind: str
    name: str = ''
    rectangles: list[list[float]]


@router.get('/app/configuracao-modos/{mode}/{cls}/exemplos/{token}/recortes')
def list_example_crops(mode: str, cls: str, token: str, request: Request, conn: sqlite3.Connection = Depends(get_db_conn)):
    member(request, conn)
    try:
        return {'crops': example_crops.listing(mode, cls, token), 'types': example_crops.TYPES.get(profiles.key_for(cls).split('_')[0], {})}
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc


@router.get('/app/configuracao-modos/{mode}/{cls}/exemplos/{token}/recortes/original')
def example_crop_source(mode: str, cls: str, token: str, request: Request, conn: sqlite3.Connection = Depends(get_db_conn)):
    member(request, conn)
    try:
        mapping = example_crops.source(mode, cls, token)
        return mapping
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc


@router.get('/app/configuracao-modos/{mode}/{cls}/exemplos/{token}/recortes/original/preview')
def example_crop_source_preview(mode: str, cls: str, token: str, request: Request, conn: sqlite3.Connection = Depends(get_db_conn)):
    member(request, conn)
    try:
        example_crops.source(mode, cls, token)
        return preview_response(example_crops.root_for(mode, cls, token) / 'source.svg', request)
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc


@router.post('/app/configuracao-modos/{mode}/{cls}/exemplos/{token}/recortes')
def create_example_crop(mode: str, cls: str, token: str, body: ExampleCropPayload, request: Request, conn: sqlite3.Connection = Depends(get_db_conn)):
    owner(request, conn)
    try:
        result = example_crops.create(mode, cls, token, body.kind, body.name, body.rectangles)
        return {'crop': result, 'crops': example_crops.listing(mode, cls, token)}
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc


@router.get('/app/configuracao-modos/{mode}/{cls}/exemplos/{token}/recortes/{crop_id}/preview')
def example_crop_preview(mode: str, cls: str, token: str, crop_id: str, request: Request, conn: sqlite3.Connection = Depends(get_db_conn)):
    member(request, conn)
    try: return preview_response(example_crops.crop_path(mode, cls, token, crop_id), request)
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc


@router.delete('/app/configuracao-modos/{mode}/{cls}/exemplos/{token}/recortes/{crop_id}')
def delete_example_crop(mode: str, cls: str, token: str, crop_id: str, request: Request, conn: sqlite3.Connection = Depends(get_db_conn)):
    owner(request, conn)
    try: return {'crops': example_crops.remove(mode, cls, token, crop_id)}
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc


def owner(request, conn):
    current = member(request, conn)
    if not access.eh_dono(current): raise HTTPException(403, 'Somente o dono pode alterar exemplos globais')
    origin = request.headers.get('origin')
    if origin:
        from urllib.parse import urlsplit
        if urlsplit(origin).netloc != request.headers.get('host'): raise HTTPException(403, 'Origem inválida')
    return current


def preview_response(path, request):
    accepted = request.headers.get('accept-encoding', '')
    gzip_enabled = any(part.strip().split(';')[0] == 'gzip' and not __import__('re').search(r';\s*q=0(?:\.0*)?\s*$', part) for part in accepted.split(','))
    compact = drawing_frame.compact_preview(path, gzip_enabled)
    headers = {'Cache-Control': 'private, no-cache', 'Vary': 'Accept-Encoding'}
    if compact.suffix == '.gz': headers['Content-Encoding'] = 'gzip'
    return FileResponse(compact, media_type='image/svg+xml', headers=headers)


@router.get('/app/configuracao-modos/{mode}/{cls}/exemplos')
def get_examples(mode: str, cls: str, request: Request, conn: sqlite3.Connection = Depends(get_db_conn)):
    member(request, conn)
    try: return {'examples': drawing_frame.examples(mode, cls)}
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc


@router.post('/app/configuracao-modos/{mode}/{cls}/exemplos')
def upload_example(mode: str, cls: str, request: Request, arquivo: UploadFile = File(...), conn: sqlite3.Connection = Depends(get_db_conn)):
    owner(request, conn)
    try: return {'examples': drawing_frame.add_example(mode, cls, arquivo.filename, arquivo.file.read(drawing_frame.MAX_BYTES + 1))}
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc


@router.delete('/app/configuracao-modos/{mode}/{cls}/exemplos/{token}')
def delete_example(mode: str, cls: str, token: str, request: Request, conn: sqlite3.Connection = Depends(get_db_conn)):
    owner(request, conn)
    try: return {'examples': drawing_frame.remove_example(mode, cls, token)}
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc


@router.get('/app/configuracao-modos/{mode}/{cls}/exemplos/{token}/preview')
def example_preview(mode: str, cls: str, token: str, request: Request, conn: sqlite3.Connection = Depends(get_db_conn)):
    member(request, conn)
    try: path = drawing_frame.preview(mode, cls, token, 'drawing_examples')
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc
    if not path.exists(): raise HTTPException(404, 'Exemplo não encontrado')
    return preview_response(path, request)


def _single_document_routes(segment: str, collection: str, label: str):
    """Documentos por modo/classe; mantém a referência atual usada pelos motores."""
    base = '/app/configuracao-modos/{mode}/{cls}/' + segment

    def get_frame(mode: str, cls: str, request: Request, conn: sqlite3.Connection = Depends(get_db_conn)):
        member(request, conn)
        try:
            return {'frame': drawing_frame.metadata(mode, cls, collection),
                    'documents': drawing_frame.documents(mode, cls, collection)}
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    def upload_frame(mode: str, cls: str, request: Request, arquivo: UploadFile = File(...), conn: sqlite3.Connection = Depends(get_db_conn)):
        current = member(request, conn)
        if not access.eh_dono(current):
            raise HTTPException(403, f'Somente o dono pode alterar {label} globais')
        origin = request.headers.get('origin')
        if origin:
            from urllib.parse import urlsplit
            if urlsplit(origin).netloc != request.headers.get('host'):
                raise HTTPException(403, 'Origem inválida')
        content = arquivo.file.read(drawing_frame.MAX_BYTES + 1)
        try:
            frame = drawing_frame.store(mode, cls, arquivo.filename, content, collection)
            return {'frame': frame, 'documents': drawing_frame.documents(mode, cls, collection)}
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    def frame_preview(mode: str, cls: str, token: str, request: Request, conn: sqlite3.Connection = Depends(get_db_conn)):
        member(request, conn)
        try:
            path = drawing_frame.preview(mode, cls, token, collection)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        if not path.exists():
            raise HTTPException(404, 'Documento não encontrado')
        return preview_response(path, request)

    def delete_frame(mode: str, cls: str, token: str, request: Request, conn: sqlite3.Connection = Depends(get_db_conn)):
        owner(request, conn)
        try:
            frame = drawing_frame.remove_frame(mode, cls, token, collection)
            return {'frame': frame, 'documents': drawing_frame.documents(mode, cls, collection)}
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc

    router.add_api_route(base, get_frame, methods=['GET'])
    router.add_api_route(base, upload_frame, methods=['POST'])
    router.add_api_route(base + '/{token}/preview', frame_preview, methods=['GET'])
    router.add_api_route(base + '/{token}', delete_frame, methods=['DELETE'])


_single_document_routes('moldura', drawing_frame.FRAMES, 'molduras')
_single_document_routes('indices-legendas', drawing_frame.LEGENDS, 'índices e legendas')


def member(request, conn):
    result = _membro_da_sessao(request, conn)
    if result is None:
        raise HTTPException(401, 'Sessão expirada')
    return result


@router.get('/app/configuracao-modos/pagina')
def config_page(request: Request, retorno: str = '/app/obras', conn: sqlite3.Connection = Depends(get_db_conn)):
    current = _membro_da_sessao(request, conn)
    if current is None:
        return RedirectResponse('/login', status_code=303)
    from urllib.parse import urlsplit
    target = urlsplit(retorno)
    if target.scheme or target.netloc or not (target.path == '/app/obras' or target.path.startswith('/app/obras/')):
        retorno = '/app/obras'
    return _render(request, 'drawing_mode_config.html', {
        'membro': current, 'nav_ativo': 'configuracao_modos', 'retorno': retorno,
    })


@router.get('/app/configuracao-modos')
def get_config(request: Request, conn: sqlite3.Connection = Depends(get_db_conn)):
    current = member(request, conn)
    value = profiles.catalog()
    value['can_edit'] = access.eh_dono(current)
    return value


class UpdateProfile(BaseModel):
    revision: int
    settings: dict


@router.put('/app/configuracao-modos/{mode}/{cls}')
def put_config(mode: str, cls: str, body: UpdateProfile, request: Request, conn: sqlite3.Connection = Depends(get_db_conn)):
    current = member(request, conn)
    if not access.eh_dono(current):
        raise HTTPException(403, 'Somente o dono pode alterar configurações globais')
    origin = request.headers.get('origin')
    if origin:
        from urllib.parse import urlsplit
        if urlsplit(origin).netloc != request.headers.get('host'):
            raise HTTPException(403, 'Origem inválida')
    try:
        revision = profiles.save(mode, cls, body.settings, body.revision, current['id'])
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {'revision': revision, 'settings': profiles.effective(mode, cls)}
