#!/usr/bin/env python
"""
qa_error_review.py — Janela de navegador persistente para triagem de erros
nas fichas granulares (lajes/pilares/fundos de viga).

As fichas geradas por preficha_laje_html.py (e futuramente pilares/FV) têm,
como último campo, um checkbox "Marcar esta ficha como ERRADA" + campo de
nota, salvos automaticamente em localStorage a cada mudança.

localStorage vive no PERFIL do navegador que abriu o arquivo, não no arquivo
.html em si — por isso um agente que abre o mesmo .html com um navegador
"limpo" não vê nada. Este script resolve isso usando SEMPRE o mesmo perfil
fixo em disco (scripts/arete/.qa_profiles/{obra}_{pav}/) tanto para a janela
que o usuário usa para marcar quanto para a leitura posterior.

Uso:
    # 1. Abre uma janela visível para o usuário navegar e marcar erros.
    #    O comando fica bloqueado até a janela ser fechada.
    python qa_error_review.py open --dir scripts/arete/html_fichas/Obra_TREINO_1/{RUN}/lajes

    # 2. Depois que a janela for fechada, lê as marcações do mesmo perfil.
    python qa_error_review.py read --dir scripts/arete/html_fichas/Obra_TREINO_1/{RUN}/lajes
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROFILES_DIR = _SCRIPT_DIR / '.qa_profiles'


_RUN_TIMESTAMP_SUFFIX = re.compile(r'_\d{8}_\d{6}$')


def _profile_dir_for(section_dir: Path) -> Path:
    """Perfil fixo por obra/pavimento, independente do timestamp do run,
    para que marcações sobrevivam a uma nova geração de HTMLs."""
    # section_dir tipicamente: .../html_fichas/{obra}/{pav_ts}/lajes
    # pav_ts tem sufixo _YYYYMMDD_HHMMSS do momento da geração — removido
    # para que reruns do mesmo pavimento caiam no mesmo perfil.
    parts = section_dir.resolve().parts
    try:
        idx = parts.index('html_fichas')
        obra = parts[idx + 1]
        pav_ts = parts[idx + 2]
    except (ValueError, IndexError):
        obra, pav_ts = 'obra', section_dir.parent.name
    pav = _RUN_TIMESTAMP_SUFFIX.sub('', pav_ts)
    slug = re.sub(r'[^\w\-]', '_', f'{obra}_{pav}')[:80]
    d = _PROFILES_DIR / slug
    d.mkdir(parents=True, exist_ok=True)
    return d


def _screen_size() -> tuple[int, int]:
    """Resolução real da tela primária (Windows). Usada para sincronizar o
    viewport interno do Playwright com o tamanho físico da janela — com
    `--start-maximized` sozinho, o CSS às vezes calcula o layout como se a
    janela fosse menor que o espaço realmente disponível (o scroll vertical
    aparece "no meio" da tela em vez de na borda direita de verdade)."""
    try:
        import ctypes
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    except Exception:
        return 1920, 1080


def open_review_window(section_dir: Path, start_page: str = 'index.html') -> None:
    """Abre uma janela visível de Chromium com perfil persistente e bloqueia
    até o usuário fechar a janela (todas as páginas)."""
    from playwright.sync_api import sync_playwright

    profile = _profile_dir_for(section_dir)
    url = 'file:///' + (section_dir / start_page).resolve().as_posix()
    screen_w, screen_h = _screen_size()
    # Margem para a barra de título/abas do Chrome não cortar conteúdo.
    win_w, win_h = screen_w, screen_h - 80

    print(f'[qa] perfil: {profile}')
    print(f'[qa] abrindo: {url}')
    print(f'[qa] janela: {win_w}x{win_h} (tela {screen_w}x{screen_h})')
    print('[qa] marque os erros normalmente; salva sozinho a cada mudança.')
    print('[qa] feche a janela do navegador quando terminar.')

    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            str(profile), headless=False,
            viewport={'width': win_w, 'height': win_h},
            args=[
                f'--window-size={screen_w},{screen_h}',
                '--window-position=0,0',
            ],
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(url)

        # Bloqueia até todas as páginas/janelas do contexto fecharem.
        while True:
            time.sleep(1)
            try:
                if len(context.pages) == 0:
                    break
            except Exception:
                break
        try:
            context.close()
        except Exception:
            pass

    print('[qa] janela fechada.')


def read_marked_errors(section_dir: Path, index_page: str = 'index.html') -> list[dict]:
    """Reabre o mesmo perfil (headless) e lê todas as chaves aten_erro_*
    salvas em localStorage. Retorna lista de {item, erro, nota}."""
    from playwright.sync_api import sync_playwright

    profile = _profile_dir_for(section_dir)
    url = 'file:///' + (section_dir / index_page).resolve().as_posix()

    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            str(profile), headless=True,
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(url)
        data = page.evaluate(
            """() => {
                const out = [];
                for (let i = 0; i < localStorage.length; i++) {
                    const k = localStorage.key(i);
                    if (!k || k.indexOf('aten_erro_') !== 0) continue;
                    let obj;
                    try { obj = JSON.parse(localStorage.getItem(k)); }
                    catch (e) { continue; }
                    const nome = k.split('_').pop();
                    if (obj.erro || (obj.nota || '').trim()) {
                        out.push({ item: nome, erro: !!obj.erro, nota: obj.nota || '' });
                    }
                }
                out.sort((a, b) => a.item.localeCompare(b.item));
                return out;
            }"""
        )
        context.close()

    return data


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='cmd', required=True)

    p_open = sub.add_parser('open', help='Abre janela visível para marcar erros')
    p_open.add_argument('--dir', required=True, help='Pasta da seção (ex: .../lajes)')
    p_open.add_argument('--page', default='index.html')

    p_read = sub.add_parser('read', help='Lê as marcações do perfil já usado')
    p_read.add_argument('--dir', required=True, help='Pasta da seção (ex: .../lajes)')
    p_read.add_argument('--page', default='index.html')
    p_read.add_argument('--json', action='store_true', help='Saída em JSON puro')

    args = ap.parse_args()
    section_dir = Path(args.dir)
    if not section_dir.is_dir():
        raise SystemExit(f'Diretório não encontrado: {section_dir}')

    if args.cmd == 'open':
        open_review_window(section_dir, args.page)
    elif args.cmd == 'read':
        results = read_marked_errors(section_dir, args.page)
        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            if not results:
                print('Nenhum item marcado.')
            for r in results:
                flag = 'ERRO' if r['erro'] else 'nota'
                print(f'[{flag}] {r["item"]}: {r["nota"]}')


if __name__ == '__main__':
    main()
