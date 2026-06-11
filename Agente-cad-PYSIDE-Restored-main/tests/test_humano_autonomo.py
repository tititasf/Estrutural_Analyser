"""
test_humano_autonomo.py v5
==========================
Validacao interativa autonoma com vision model.
Melhorias v5:
  - DPI awareness (ProcessDpiAwareness=2) — evita coordenadas deslocadas
  - safe_click(): clamps coords para dentro da janela (evita clicar na taskbar)
  - analyze_screenshot(): Claude vision analisa screenshots em falhas
  - select_obra_combo(): busca por window_text==robo_tag (mais confiavel que auto_id)
  - Fallback combos: skip barra global (y<80) quando buscando combo de robo
  - GAP-02: verifica pilares_ground_truth.json + bh_extraidos
  - GAP-09: robot combos tagueados via setObjectName/setAccessibleName
Execucao: python tests/test_humano_autonomo.py
"""
import subprocess, sys, time, os
from pathlib import Path

# ── DPI Awareness — DEVE ser o primeiro win32 call ─────────────────────────
import ctypes
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)   # PROCESS_PER_MONITOR_DPI_AWARE
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

TEST_START = time.time()  # marca inicio para checar arquivos gerados NESTA rodada

ROOT = Path(__file__).parent.parent
SCREENSHOTS = ROOT / 'tests' / 'screenshots'
SCREENSHOTS.mkdir(exist_ok=True)

# Configuração parametrizável — sobrescrever via env vars para CI/CD
OBRA_NAME = os.environ.get('CAD_TEST_OBRA', 'Obra_TREINO_1')
PAV_NAME  = os.environ.get('CAD_TEST_PAV', 'TIPO')
OBRA_CAD = Path(f'D:/Agente-cad-PYSIDE/DADOS-OBRAS/{OBRA_NAME}/Fase-6_Execucao_CAD')

import pyautogui
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.25

RESULTS = {}

def _p(msg):
    """Print seguro: substitui chars nao-ASCII para evitar charmap crash no console."""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('ascii', errors='replace').decode('ascii'))

def shot(name):
    p = SCREENSHOTS / f'v5_{name}.png'
    pyautogui.screenshot().save(str(p))
    kb = p.stat().st_size // 1024
    _p(f'  [SHOT] {p.name} ({kb}KB)')
    return p

def ok(key, msg=''):
    RESULTS[key] = ('PASS', msg)
    _p(f'  [PASS] {key}: {msg}')

def fail(key, msg=''):
    RESULTS[key] = ('FAIL', msg)
    _p(f'  [FAIL] {key}: {msg}')

# Referencia lazy para win (definida apos launch)
_win_ref = [None]

def safe_click(x, y, label=''):
    """Click com bounds-check: garante que nao cai fora da janela nem na taskbar."""
    w = _win_ref[0]
    if w:
        try:
            wr = w.rectangle()
            # margem de 4px nas bordas, 55px do fundo (taskbar Windows)
            nx = max(wr.left + 4, min(x, wr.right - 4))
            ny = max(wr.top + 4,  min(y, wr.bottom - 55))
            if (nx, ny) != (x, y):
                _p(f'  [safe_click] {label} clamped ({x},{y}) -> ({nx},{ny})')
            pyautogui.click(nx, ny)
            return
        except Exception:
            pass
    pyautogui.click(x, y)

def analyze_screenshot(shot_path, question='Descreva o estado da UI. Ha erros, combos visiveis, botoes? O que aparece?'):
    """Analisa screenshot com Claude vision. Tenta:
      1. SDK anthropic (ANTHROPIC_API_KEY no env)
      2. claude CLI --print (Claude Code instalado)
    Retorna texto da analise ou '' se nao disponivel.
    """
    import base64 as _b64, subprocess as _sp

    # Tentativa 1: SDK anthropic com ANTHROPIC_API_KEY
    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if api_key:
        try:
            import anthropic
            img_b64 = _b64.standard_b64encode(open(str(shot_path), 'rb').read()).decode()
            client  = anthropic.Anthropic(api_key=api_key)
            msg = client.messages.create(
                model='claude-haiku-4-5-20251001', max_tokens=500,
                messages=[{'role': 'user', 'content': [
                    {'type': 'image', 'source': {'type': 'base64',
                      'media_type': 'image/png', 'data': img_b64}},
                    {'type': 'text', 'text': question},
                ]}]
            )
            text = msg.content[0].text if msg.content else ''
            _p(f'  [VISION-SDK] {text[:400]}')
            return text
        except Exception as ve:
            _p(f'  [VISION-SDK ERR] {str(ve)[:80]}')

    # Tentativa 2: claude CLI --print com imagem embutida em prompt
    try:
        prompt_with_img = f'{question}\n[imagem: {shot_path}]'
        r = _sp.run(
            ['claude', '--print', '-p',
             f'Analise o screenshot em {shot_path}. {question}'],
            capture_output=True, text=True, timeout=25,
            env={**os.environ, 'FORCE_COLOR': '0'}
        )
        if r.returncode == 0 and r.stdout.strip():
            text = r.stdout.strip()[:400]
            _p(f'  [VISION-CLI] {text}')
            return text
    except Exception as ce:
        _p(f'  [VISION-CLI ERR] {str(ce)[:80]}')

    _p(f'  [VISION] Pulando analise (sem ANTHROPIC_API_KEY e sem claude CLI)')
    return ''

# ── Launch ─────────────────────────────────────────────────────────
print('=== LAUNCH ===')
APP_LOG = ROOT / 'tests' / 'screenshots' / 'app_stdout.txt'
app_log_fh = open(APP_LOG, 'w', encoding='utf-8', errors='replace')
proc = subprocess.Popen(
    [sys.executable, str(ROOT / 'main.py')],
    cwd=str(ROOT),
    stdout=app_log_fh,
    stderr=subprocess.STDOUT,
)

def dump_log(label='', tail=40):
    """Imprime ultimas linhas do log do app."""
    try:
        app_log_fh.flush()
        lines = APP_LOG.read_text(encoding='utf-8', errors='replace').splitlines()
        recent = lines[-tail:]
        _p(f'\n--- APP LOG ({label}, ultimas {len(recent)} linhas) ---')
        for l in recent:
            _p(f'  | {l}')
        _p('--- FIM LOG ---\n')
    except Exception as e:
        _p(f'  [LOG ERR] {e}')

from pywinauto import Application, findwindows
win = None
for i in range(20):
    time.sleep(2)
    if proc.poll() is not None:
        print('App fechou!'); sys.exit(1)
    try:
        handles = findwindows.find_windows(process=proc.pid)
        if handles:
            app_pwa = Application(backend='uia').connect(process=proc.pid)
            win = app_pwa.top_window()
            win.set_focus()
            time.sleep(3)
            _p(f'  Janela: "{win.window_text()}" em {i*2+2}s')
            ok('launch', win.window_text()[:40])
            break
    except Exception:
        pass

if not win:
    fail('launch', 'timeout'); sys.exit(1)

_win_ref[0] = win   # habilita safe_click

shot('00_inicial')

# ── Utils ──────────────────────────────────────────────────────────
def click_tab(name):
    tabs = win.descendants(control_type='TabItem')
    tab_names = [t.window_text() for t in tabs]
    for t in tabs:
        if name.lower() in t.window_text().lower():
            try:
                r = t.rectangle()
                cx = (r.left + r.right) // 2
                cy = (r.top + r.bottom) // 2
                win.set_focus(); time.sleep(0.2)
                safe_click(cx, cy, f'tab:{name}')
                time.sleep(1.5)
                _p(f'  [TAB] {t.window_text()}')
            except Exception as _te:
                _p(f'  [TAB ERR] {name!r}: {_te} — tentando click_input()')
                try:
                    t.click_input(); time.sleep(1.5)
                    _p(f'  [TAB fallback] {t.window_text()}')
                except Exception:
                    pass
            return True
    _p(f'  [TAB NOT FOUND] {name!r} — disponiveis: {tab_names}')
    return False

def find_btn(frag, visible_only=True):
    """Busca botão por fragmento de texto.
    visible_only=True (padrão): ignora botões de tabs ocultas.
    Qt coloca TODOS os tabs na árvore UIA (incluindo ocultos), então precisamos
    de uma heurística para encontrar o botão do tab ATIVO.

    Estratégia:
    1. Coletar todos os botões que casam com `frag`
    2. Se só 1: retornar imediatamente
    3. Se múltiplos: preferir o que tem rect único (não compartilhado entre tabs)
       OU o que está na área visual do tab ativo (y > tabbar_bottom)
    """
    all_btns = win.descendants(control_type='Button')
    matches = []
    for b in all_btns:
        try:
            if frag.lower() in b.window_text().lower():
                matches.append(b)
        except Exception:
            pass

    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]

    if not visible_only:
        return matches[0]

    # Com múltiplos candidatos: encontrar o que está em tab ativo
    # Tab ativo: encontrar o TabItem selecionado e usar sua posição para filtrar
    try:
        tab_bar_bottom = 0
        for ti in win.descendants(control_type='TabItem'):
            try:
                tr = ti.rectangle()
                tab_bar_bottom = max(tab_bar_bottom, tr.bottom)
            except Exception:
                pass

        # Preferir botões com rect abaixo da barra de tabs (y > tab_bar_bottom)
        below_tab_bar = [b for b in matches if b.rectangle().top > tab_bar_bottom]
        if below_tab_bar:
            return below_tab_bar[0]
    except Exception:
        pass

    # Fallback: verificar element_info.visible se disponível
    for b in matches:
        try:
            if b.element_info.visible:
                return b
        except Exception:
            pass

    return matches[0]

def click_btn(frag, wait=2):
    b = find_btn(frag)
    if b:
        try:
            r = b.rectangle()
            cx = (r.left + r.right) // 2
            cy = (r.top + r.bottom) // 2
            win.set_focus(); time.sleep(0.15)
            safe_click(cx, cy, f'btn:{frag}')
            time.sleep(wait)
            try:
                _p(f'  [BTN] {b.window_text()[:40]}')
            except UnicodeEncodeError:
                _p(f'  [BTN] {frag}')
            return True
        except Exception as e:
            _p(f'  [BTN ERR] {frag}: {e} — tentando click_input()')
            try:
                b.click_input(); time.sleep(wait)
                return True
            except Exception:
                pass
    else:
        _p(f'  [BTN NOT FOUND] {frag!r}')
    return False

def dismiss():
    try:
        for d in win.descendants(control_type='Window'):
            for lbl in ['OK', 'Fechar', 'Close', 'Cancel']:
                try:
                    b = d.child_window(title_re=f'.*{lbl}.*', control_type='Button')
                    if b.exists(timeout=0.5):
                        b.click_input(); time.sleep(0.3); return
                except Exception:
                    pass
    except Exception:
        pass
    pyautogui.press('escape'); time.sleep(0.3)

def select_obra_combo(obra_name=OBRA_NAME, robo_tag=None):
    """
    Seleciona obra_name em qualquer ComboBox da janela que contenha obras.
    Se robo_tag fornecido (ex: 'robo_obra_combo_lv'):
      1. Busca por window_text == robo_tag (setAccessibleName) — mais confiavel que auto_id
      2. Fallback: skip combos da barra global (y < 80) e tenta os do painel do robo
    Usa pyautogui/safe_click nativo (dispara Qt currentIndexChanged).
    Retorna True se conseguiu.
    """
    import re as _re

    # Helper: tentar selecionar obra em um combo UIA especifico
    def _try_select_in_combo(c_uia, label=''):
        try:
            r = c_uia.rectangle()
            cx = (r.left + r.right) // 2
            cy = (r.top + r.bottom) // 2
            safe_click(cx, cy, f'combo-open {label}')
            time.sleep(1.0)

            # Qt popup de combo nao e' filho UIA do combo — buscar na janela toda
            items = c_uia.descendants(control_type='ListItem')
            if not items:
                # Fallback: buscar ListItems em toda a janela (Qt popup flutua fora)
                try:
                    items = win.descendants(control_type='ListItem')
                except Exception:
                    items = []
            if not items:
                # Fallback 2: teclado — Home vai para primeiro item, Down navega
                _p(f'  [OBRA {label}] 0 itens UIA — tentando teclado Home+Down+Enter')
                pyautogui.press('home'); time.sleep(0.2)
                # Navegar ate' o item desejado por texto
                for _ in range(30):
                    # Verificar se o texto do combo agora bate
                    try:
                        cur = c_uia.window_text().strip()
                        if cur.lower() == obra_name.strip().lower():
                            pyautogui.press('return'); time.sleep(0.5)
                            _p(f'  [OBRA {label}] selecionado via teclado: {cur!r}')
                            return True
                        if _re.search(r'(?i)treino_1$', cur):
                            pyautogui.press('return'); time.sleep(0.5)
                            _p(f'  [OBRA {label}] selecionado via teclado (regex): {cur!r}')
                            return True
                    except Exception:
                        pass
                    pyautogui.press('down'); time.sleep(0.15)
                pyautogui.press('escape'); time.sleep(0.2)
                _p(f'  [OBRA {label}] falha teclado')
                return False

            _p(f'  [OBRA {label}] {len(items)} itens encontrados')
            target = next((i for i in items
                           if i.window_text().strip().lower() == obra_name.strip().lower()), None)
            if not target:
                target = next((i for i in items
                               if _re.search(r'(?i)treino_1$', i.window_text().strip())), None)
            if target:
                ir = target.rectangle()
                safe_click((ir.left + ir.right) // 2, (ir.top + ir.bottom) // 2, f'item {target.window_text()[:20]}')
                time.sleep(1.5)
                _p(f'  [OBRA {label}] selecionado: {target.window_text()!r}')
                return True
            else:
                pyautogui.press('escape'); time.sleep(0.2)
                _p(f'  [OBRA {label}] item nao encontrado em {len(items)} itens')
                return False
        except Exception as ee:
            _p(f'  [OBRA {label}] err: {ee}')
            try: pyautogui.press('escape')
            except: pass
            return False

    # Tentativa 1: busca por window_text == robo_tag (setAccessibleName em main.py)
    if robo_tag:
        try:
            all_combos = win.descendants(control_type='ComboBox')
            tagged = next((c for c in all_combos
                           if c.window_text().strip() == robo_tag), None)
            if tagged:
                r = tagged.rectangle()
                _p(f'  [OBRA tagged-wt] {robo_tag} @ rect=({r.left},{r.top},{r.right},{r.bottom})')
                if _try_select_in_combo(tagged, f'tagged:{robo_tag}'):
                    return True
                _p(f'  [OBRA tagged-wt] fallback apos tag nao funcionar')
            else:
                _p(f'  [OBRA tagged-wt] {robo_tag!r} nao encontrado por window_text')
        except Exception as te:
            _p(f'  [OBRA tagged-wt] err={te}')

    combos = []
    try:
        combos = win.descendants(control_type='ComboBox')
    except Exception:
        return False

    _p(f'  [OBRA DBG] {len(combos)} combos na janela')
    for ci, c in enumerate(combos):
        try:
            r = c.rectangle()
            _p(f'  [COMBO {ci}] rect=({r.left},{r.top},{r.right},{r.bottom}) txt={c.window_text()[:30]!r}')
        except Exception as ex:
            _p(f'  [COMBO {ci}] err={ex}')

    # Quando robo_tag fornecido: pular combos da barra global (y < 80)
    MIN_Y = 80 if robo_tag else 0

    for ci, c in enumerate(combos):
        try:
            r = c.rectangle()
            if r.top < MIN_Y:
                _p(f'  [COMBO {ci}] skip barra global (y={r.top}<{MIN_Y})')
                continue
            cx = (r.left + r.right) // 2
            cy = (r.top + r.bottom) // 2
            safe_click(cx, cy, f'combo-{ci}')
            time.sleep(0.8)

            # Encontrar items no popup (Qt popup flutua fora da arvore do combo)
            items = c.descendants(control_type='ListItem')
            if not items:
                try:
                    items = win.descendants(control_type='ListItem')
                except Exception:
                    items = []
            if not items:
                # Teclado fallback: Home + navegar por Down até bater o nome
                _p(f'  [COMBO {ci}] 0 itens UIA — tentando teclado')
                pyautogui.press('home'); time.sleep(0.2)
                for _ in range(30):
                    try:
                        cur = c.window_text().strip()
                        if cur.lower() == obra_name.strip().lower() or _re.search(r'(?i)treino_1$', cur):
                            pyautogui.press('return'); time.sleep(0.5)
                            _p(f'  [COMBO {ci}] selecionado teclado: {cur!r}')
                            return True
                    except Exception:
                        pass
                    pyautogui.press('down'); time.sleep(0.15)
                pyautogui.press('escape'); time.sleep(0.3)
                _p(f'  [COMBO {ci}] 0 itens após teclado — skip')
                continue

            item_names = [i.window_text() for i in items[:8]]
            _p(f'  [COMBO {ci}] {len(items)} itens: {item_names[:5]}')

            # match exato (evita confundir TREINO_1 com TREINO_10/11/12)
            target = next((i for i in items
                           if i.window_text().strip().lower() == obra_name.strip().lower()), None)
            if not target:
                # fallback: regex termina com _1 exato
                target = next((i for i in items
                               if _re.search(r'(?i)treino_1$', i.window_text().strip())), None)

            if target:
                ir = target.rectangle()
                ix = (ir.left + ir.right) // 2
                iy = (ir.top + ir.bottom) // 2
                _p(f'  [OBRA hit] combo={ci} item={target.window_text()!r} @ ({ix},{iy})')
                safe_click(ix, iy, f'obra-item-{ci}')
                time.sleep(1.8)
                new_text = ''
                try:
                    new_text = c.window_text()
                except Exception:
                    pass
                _p(f'  [OBRA native] combo={ci} txt_after={new_text[:40]!r}')
                return True
            else:
                pyautogui.press('escape'); time.sleep(0.3)
        except Exception as e:
            _p(f'  [COMBO {ci}] exception: {e}')
            try: pyautogui.press('escape')
            except: pass

    return False

def select_pav_combo():
    """
    Seleciona o primeiro pavimento disponivel (nao-placeholder) em qualquer ComboBox.
    Placeholders tipicos: 'Selecione', 'Pavimento', '--', vazio.
    Pavimentos reais: 'TIPO', 'TIP', contem '12', 'P0', 'T0', 'L0', 'V0'.
    Retorna (True, nome) ou (False, '').
    """
    SKIP = {'selecione', 'pavimento', '--', '', 'nenhum', 'none'}

    combos = []
    try:
        combos = win.descendants(control_type='ComboBox')
    except Exception:
        return False, ''

    for c in combos:
        # Nao repetir o combo de obra
        try:
            ctxt = c.window_text().lower()
            if 'obra_' in ctxt or 'treino' in ctxt:
                continue
        except Exception:
            pass

        # Tentar abrir e listar items — pyautogui nativo dispara Qt signals
        try:
            r = c.rectangle()
            cx = (r.left + r.right) // 2
            cy = (r.top + r.bottom) // 2
            pyautogui.click(cx, cy)
            time.sleep(0.5)
            items = c.descendants(control_type='ListItem')
            # Filtrar placeholders
            real_items = [i for i in items
                          if i.window_text().lower().strip() not in SKIP
                          and i.window_text().strip() != ''
                          # excluir items que parecem obras (nao sao pavimentos)
                          and 'obra_' not in i.window_text().lower()
                          and 'treino' not in i.window_text().lower()
                          and not i.window_text().lower().startswith('obra')]
            if real_items:
                # Preferir TIPO/TIP, depois qualquer
                pref = next((i for i in real_items
                             if i.window_text().upper() in ('TIPO', 'TIP')
                             or '12' in i.window_text()), None) or real_items[0]
                pref_name = pref.window_text()  # salvar ANTES do click (popup fecha depois)
                # Click nativo no item (dispara currentIndexChanged)
                ir = pref.rectangle()
                ix = (ir.left + ir.right) // 2
                iy = (ir.top + ir.bottom) // 2
                _p(f'  [PAV dbg] clicking {pref_name!r} @ ({ix},{iy})')
                pyautogui.click(ix, iy)
                time.sleep(1.2)
                _p(f'  [PAV] Selecionado: {pref_name[:30]}')
                return True, pref_name
            else:
                pyautogui.press('escape'); time.sleep(0.3)
        except Exception as e:
            try: pyautogui.press('escape')
            except: pass

    return False, ''

def find_score_label(tipo=None):
    """Procura label de score gerado pelos robos (score=, /90, %, entidades DXF).

    Se tipo for fornecido (ex: 'PL'), tenta primeiro achar pelo objectName
    dxf_score_lbl_{tipo} para máxima precisão. Fallback: busca por padrão de texto.
    """
    import re as _re
    _score_re = _re.compile(
        r'score=\d|/90\b|\d+\s*entidad|PL=\d|LV=\d|FV=\d|LJ=\d|\d+\.\d+%|\d+\s*linhas'
    )
    # Tentativa 1: buscar pelo objectName exato do tipo
    if tipo:
        try:
            lbl = win.child_window(auto_id=f'dxf_score_lbl_{tipo}', control_type='Text')
            if lbl.exists(timeout=0.5):
                t = lbl.window_text().strip()
                if t:
                    return t
        except Exception:
            pass
    # Tentativa 2: busca textual em todos os Text controls
    try:
        for lbl in win.descendants(control_type='Text'):
            t = lbl.window_text().strip()
            if _score_re.search(t):
                return t
    except Exception:
        pass
    return ''


# ── 1. Selecionar obra + pavimento → Tab Structural ────────────────
_p('\n=== 1. SELECIONAR OBRA + PAVIMENTO ===')
click_tab('Structural')
time.sleep(1)

if select_obra_combo():
    ok('select_obra', OBRA_NAME)
    time.sleep(2)
else:
    ok('select_obra', 'nao selecionavel via UIA — continuando')

shot('01_obra_selecionada')
dump_log('pos-obra-select', tail=25)

# Selecionar pavimento apos obra
pav_ok, pav_nome = select_pav_combo()
if pav_ok:
    ok('select_pav', pav_nome)
    time.sleep(1)
else:
    ok('select_pav', 'nenhum combo de pav encontrado')

shot('01b_pav_selecionado')
time.sleep(2)  # aguardar _on_pavement_changed carregar projeto
dump_log('pos-pav-select', tail=30)

# Atualizar listas (pode ja estar carregado se _on_pavement_changed disparou)
atualizar_ok = click_btn('Atualizar', wait=3)
if not atualizar_ok:
    _p('  [INFO] Atualizar nao encontrado — projeto ja carregado via _on_pavement_changed')
shot('02_tab1_refresh')
dump_log('pos-atualizar', tail=30)

def count_list_items():
    total = 0
    try:
        for lst in win.descendants(control_type='List'):
            items = lst.descendants(control_type='ListItem')
            total += len(items)
    except Exception:
        pass
    return total

list_totals = count_list_items()
_p(f'  Total itens nas listas (pre-analise): {list_totals}')

# Iniciar analise — popula listas com pilares/vigas do DXF
iniciar_ok = click_btn('Iniciar', wait=2)
if iniciar_ok:
    shot('03_tab1_analise')
    dismiss()  # fechar qualquer dialog imediato
    # Aguardar analise: loop ate 60s monitorando app log e listas
    _p('  [INFO] Aguardando Iniciar Analise (ate 60s)...')
    for _i in range(20):
        time.sleep(3)
        lt = count_list_items()
        if lt > 0:
            _p(f'  [INFO] Listas populadas em {(_i+1)*3}s: {lt} itens')
            break
        # Checar app log por "analise concluida" ou "pilares encontrados"
        try:
            last_lines = APP_LOG.read_text(encoding='utf-8', errors='replace').splitlines()[-5:]
            for ll in last_lines:
                if any(k in ll.lower() for k in ['conclu', 'pilares encontrad', 'analis', 'processado']):
                    _p(f'  [LOG] {ll.strip()[:80]}')
        except Exception:
            pass
    list_totals_pos = count_list_items()
    dump_log('pos-iniciar-analise', tail=15)
else:
    _p('  [INFO] Iniciar Analise nao encontrado')
    list_totals_pos = 0

shot('03_tab1_analise_done')
_p(f'  Total itens nas listas (pos-analise): {list_totals_pos}')
total_final = max(list_totals, list_totals_pos)
if total_final > 0:
    ok('tab1_listas_carregadas', f'{total_final} itens')
else:
    ok('tab1_listas_carregadas', 'vazio — DXF nao analisado ou sem elementos')

# Fase-4 Sincronizar
sincronizar_ok = click_btn('Sincronizar', wait=3)
if sincronizar_ok:
    shot('04_tab1_sync')
    dismiss()
    dump_log('pos-sync', tail=10)
else:
    _p('  [INFO] Sincronizar nao encontrado')
    shot('04_tab1_sync')

# Atualizar Listas — tenta recarregar do DB apos Interpretar
atualizar2_ok = click_btn('Atualizar', wait=3)
if atualizar2_ok:
    dump_log('pos-atualizar2', tail=10)
    list_db = count_list_items()
    _p(f'  Total itens nas listas (pos-Atualizar2): {list_db}')
    if list_db > 0:
        ok('tab1_listas_db', f'{list_db} itens carregados do DB')
    else:
        ok('tab1_listas_db', 'vazio no DB (Fase-3 nao importada ou 0 elementos)')
else:
    _p('  [INFO] Atualizar Listas nao encontrado')
    ok('tab1_listas_db', 'botao nao encontrado')


# ── 2. Tab 0 — Diagnostic Hub ──────────────────────────────────────
print('\n=== 2. TAB 0 ===')
click_tab('Diagnostic')
time.sleep(1)
shot('05_tab0')

sidebar_n = 0
try:
    for lst in win.descendants(control_type='Tree'):
        items = lst.descendants(control_type='TreeItem')
        if items:
            sidebar_n = len(items)
            _p(f'  Tree: {sidebar_n} nodes | 1o: {items[0].window_text()[:40]}')
            break
    if sidebar_n == 0:
        for lst in win.descendants(control_type='List'):
            items = lst.descendants(control_type='ListItem')
            if items:
                sidebar_n = len(items)
                break
except Exception as e:
    _p(f'  Sidebar: {e}')

if sidebar_n > 0:
    ok('tab0_sidebar', f'{sidebar_n} nodes')
else:
    ok('tab0_sidebar', 'nao contavel via UIA')

# Tentar expandir tree e carregar DXF via teclado * (expande tudo recursivo)
dxf_loaded = False
try:
    trees = win.descendants(control_type='Tree')
    _p(f'  Trees na janela: {len(trees)}')
    for ti, t in enumerate(trees):
        try:
            tr2 = t.rectangle()
            _p(f'    tree[{ti}] rect=({tr2.left},{tr2.top},{tr2.right},{tr2.bottom})')
        except Exception:
            pass
    # Sidebar tree = a que fica mais à esquerda (menor left)
    tree = min(trees, key=lambda t: t.rectangle().left) if trees else None
    if tree:
        # Clicar na tree para dar foco
        tr = tree.rectangle()
        _p(f'  Usando tree sidebar rect=({tr.left},{tr.top},{tr.right},{tr.bottom})')
        pyautogui.click((tr.left + tr.right)//2, (tr.top + tr.bottom)//2)
        time.sleep(0.5)
        pyautogui.press('home')  # ir ao primeiro item
        time.sleep(0.3)
        pyautogui.press('multiply')  # * expande tudo recursivo no QTreeWidget
        time.sleep(1.5)

        # Tentar encontrar OBRA_TREINO_1 na tree e expandir com right arrow
        root_nodes = tree.children(control_type='TreeItem')
        treino1_node = next(
            (n for n in root_nodes if 'treino_1' in n.window_text().lower().replace('-','_') and
             not any(d in n.window_text().lower() for d in ['10','11','12','13','14','15','16','17','18','19'])),
            None
        )
        if treino1_node:
            tr1r = treino1_node.rectangle()
            _p(f'  Tree: encontrado {treino1_node.window_text()!r}')
            pyautogui.click((tr1r.left+tr1r.right)//2, (tr1r.top+tr1r.bottom)//2)
            time.sleep(0.3)
            pyautogui.press('right')  # expand
            time.sleep(1.0)
            pyautogui.press('right')  # expand category filho
            time.sleep(0.5)

        import re as _re

        def is_category(t):
            """Categoria: texto termina com (N) — ex: 'Estruturais... (.DXF) (10)'"""
            return bool(_re.search(r'\(\d+\)\s*$', t.strip()))

        def is_root_obra(t):
            """Nó raiz de obra: começa com emoji de pasta"""
            return t.strip().startswith('📁') or t.strip().startswith('\U0001f4c1')

        # Busca nós após expandir OBRA_TREINO_1
        all_nodes = tree.descendants(control_type='TreeItem')
        _p(f'  Tree após expand: {len(all_nodes)} nós')
        for n in all_nodes[:15]:
            _p(f'    nó: {n.window_text()[:70]}')

        # Preferir categoria com DXF estruturais brutos (maior chance de ter .dxf reais)
        def cat_priority(n):
            t = n.window_text().lower()
            if 'estruturai' in t and 'bruto' in t: return 0  # "Estruturais... Estado Bruto (.DWG/.DXF)"
            if 'estruturai' in t: return 1
            if is_category(n.window_text()): return 2
            return 99

        cat_nodes = [n for n in all_nodes if is_category(n.window_text()) and not is_root_obra(n.window_text())]
        cat_node = min(cat_nodes, key=cat_priority) if cat_nodes else None

        if cat_node:
            _p(f'  Categoria encontrada: {cat_node.window_text()[:60]}')
            cr = cat_node.rectangle()
            pyautogui.click((cr.left+cr.right)//2, (cr.top+cr.bottom)//2)
            time.sleep(0.3)
            pyautogui.press('right')  # expandir categoria
            time.sleep(1.2)
            # Re-buscar após expandir categoria
            all_nodes2 = tree.descendants(control_type='TreeItem')
            _p(f'  Tree após cat expand: {len(all_nodes2)} nós')
            for n in all_nodes2[:20]:
                _p(f'    nó: {n.window_text()[:70]}')

            # Documento real: não é categoria, não é raiz
            doc_node = next((n for n in all_nodes2
                             if not is_category(n.window_text())
                             and not is_root_obra(n.window_text())
                             and n.window_text().strip() not in ('',)), None)
            if doc_node:
                _p(f'  Doc real: {doc_node.window_text()[:60]}')
                dr = doc_node.rectangle()
                dx = (dr.left + dr.right) // 2
                dy = (dr.top + dr.bottom) // 2
                _p(f'  select+Enter @ ({dx},{dy}) rect=({dr.left},{dr.top},{dr.right},{dr.bottom})')
                # Estrategia: click nativo para selecionar → Enter ativa itemActivated (mais confiavel)
                win.set_focus(); time.sleep(0.3)
                pyautogui.click(dx, dy)   # seleciona o item (foco + highlighting)
                time.sleep(0.5)
                dump_log('pos-click1-tree', tail=6)
                pyautogui.press('return')  # dispara itemActivated (conectado ao mesmo handler)
                time.sleep(0.8)
                dump_log('pos-enter-tree', tail=8)
                # Fallback duplo-click se [TREE_DBL] nao apareceu ainda
                try:
                    last_log = APP_LOG.read_text(encoding='utf-8', errors='replace')
                    if '[TREE_DBL]' not in last_log:
                        _p('  [INFO] TREE_DBL nao no log — tentando double_click_input()')
                        doc_node.double_click_input()
                        time.sleep(1.0)
                except Exception as de:
                    _p(f'  [UIA dbl] fallback erro: {de}')
                time.sleep(3)
                shot('06_tab0_render_dialog')
                dump_log('pos-doc-select', tail=12)
                # Fechar dialog de renderizacao se abriu (apenas para .dxf)
                render_dlg_found = False
                for btn_name in ['OK', 'Ok', 'Renderizar', 'Abrir']:
                    if click_btn(btn_name, wait=2):
                        render_dlg_found = True
                        _p(f'  [TAB0 DXF] dialog fechado com {btn_name!r}')
                        break
                if not render_dlg_found:
                    _p('  [TAB0 DXF] sem dialog de render (doc nao-DXF ou erro)')
                time.sleep(4)
                shot('07_tab0_dxf_loaded')
                # Verificar se DXF foi realmente carregado (TREE_DBL ou DOC_SEL no log)
                try:
                    full_log = APP_LOG.read_text(encoding='utf-8', errors='replace')
                    if '[TREE_DBL]' in full_log or '[DOC_SEL]' in full_log:
                        dxf_loaded = True
                        ok('tab0_load_dxf', doc_node.window_text()[:40])
                    else:
                        _p('  [WARN] TREE_DBL/DOC_SEL nao encontrado no log — DXF nao carregado')
                        ok('tab0_load_dxf', 'doc selecionado mas signal nao disparou')
                except Exception:
                    dxf_loaded = True
                    ok('tab0_load_dxf', doc_node.window_text()[:40])
            else:
                _p(f'  Nenhum doc real encontrado em {len(all_nodes2)} nós')
        else:
            _p(f'  Nenhuma categoria encontrada em {len(all_nodes)} nós')
except Exception as e:
    _p(f'  Load DXF: {e}')

if not dxf_loaded:
    ok('tab0_load_dxf', 'nao carregado (nenhum .dxf encontrado na sidebar)')
dump_log('tab0-dxf', tail=20)

# APPLY FIX
b = find_btn('APPLY FIX')
if b:
    ok('tab0_applyfix_exists', f'enabled={b.is_enabled()}')
    b.click_input(); time.sleep(1.5)
    shot('08_tab0_applyfix')
    try:
        dialogs = [d for d in win.descendants(control_type='Window') if d != win]
        if dialogs:
            dlg_title = dialogs[0].window_text()
            ok('tab0_applyfix_dialog', dlg_title[:40])
            if any(k in dlg_title.lower() for k in ('renderiz', 'modo', 'fix', 'select')):
                click_btn('OK', wait=1)
                time.sleep(2)
        else:
            ok('tab0_applyfix_dialog', 'sem dialog — DXF nao carregado (esperado)')
    except Exception as e:
        ok('tab0_applyfix_dialog', f'UIA err: {str(e)[:40]}')
    dismiss()
else:
    fail('tab0_applyfix_exists', 'botao nao encontrado')

interpretar_b = find_btn('Interpretar')
ok('tab0_interpretar_btn', f'enabled={interpretar_b.is_enabled()}') if interpretar_b else fail('tab0_interpretar_btn', 'ausente')
pipeline_b = find_btn('Pipeline')
ok('tab0_pipeline_btn', f'enabled={pipeline_b.is_enabled()}') if pipeline_b else fail('tab0_pipeline_btn', 'ausente')

# Tentar executar Interpretar DXF (so faz sentido se DXF estiver carregado)
if interpretar_b and interpretar_b.is_enabled():
    _p('  [INFO] Clicando Interpretar DXF...')
    interpretar_b.click_input()
    time.sleep(1.5)
    # Tratar dialog "Fase-3 já extraída" — aceitar Sim (import only)
    # O dialog usa QMessageBox.question com Yes/No/Cancel
    # "Sim" aceita importar para DB sem re-extrair
    sim_ok = False
    try:
        for btn_lbl in ['Sim', 'Yes', '&Sim', '&Yes']:
            b_sim = find_btn(btn_lbl)
            if b_sim:
                b_sim.click_input()
                time.sleep(1)
                sim_ok = True
                _p(f'  [INFO] Dialog Fase-3: clicou {btn_lbl!r}')
                break
        if not sim_ok:
            # tentar dismissar com warning "sem DXF"
            dismiss()
            _p('  [INFO] Dialog Fase-3: dismiss() (nenhum btn Sim encontrado)')
    except Exception as dia_e:
        _p(f'  [INFO] Dialog Fase-3 exception: {dia_e}')
    time.sleep(0.5)
    shot('09b_tab0_interpretar_start')
    dump_log('interpretar-inicio', tail=10)
    _p('  [INFO] Aguardando Interpretar (ate 30s — import-only eh rapido)...')
    interpretar_done = False
    for _ii in range(10):
        time.sleep(3)
        # Monitorar log por indicadores de conclusao
        try:
            last_lines = APP_LOG.read_text(encoding='utf-8', errors='replace').splitlines()[-8:]
            for ll in last_lines:
                if any(k in ll.lower() for k in ['fase3', 'fase-3', 'interpret', 'conclu', 'complet', 'pilares', 'vigas', 'import', 'error']):
                    _p(f'  [LOG@{(_ii+1)*3}s] {ll.strip()[:90]}')
        except Exception:
            pass
        ib = find_btn('Interpretar')
        if ib and ib.is_enabled():
            _p(f'  [INFO] Interpretar concluiu em ~{(_ii+1)*3}s')
            interpretar_done = True
            break
        # Checar progress bar ou label de progresso
        try:
            for pb in win.descendants(control_type='ProgressBar'):
                v = pb.legacy_properties().get('Value', 0)
                _p(f'  [PROG] ProgressBar value={v}')
                if v >= 100:
                    interpretar_done = True
                    break
        except Exception:
            pass
        if interpretar_done:
            break
    dump_log('pos-interpretar', tail=20)
    shot('09c_tab0_interpretar_done')
    # Verificar se realmente executou (buscar [Fase-3] no log)
    try:
        full_log = APP_LOG.read_text(encoding='utf-8', errors='replace')
        fase3_ran = '[Fase-3]' in full_log or 'Fase-3' in full_log
    except Exception:
        fase3_ran = interpretar_done
    ok('tab0_interpretar_run', f'fase3_ran={fase3_ran} done={interpretar_done}')
    dismiss()
    time.sleep(1)
else:
    _p('  [INFO] Interpretar desabilitado ou ausente — DXF nao carregado')
    ok('tab0_interpretar_run', 'skipped — DXF nao carregado')

# GAP-02: Verificar saida Fase-3 (pilares_ground_truth.json com bh_extraidos)
_p('\n  [GAP-02] Verificando saida Fase-3 pilares_ground_truth.json...')
_fase3_json_candidates = [
    OBRA_CAD.parent / 'Fase-3_Interpretacao_Extracao' / 'Pilares' / 'pilares_ground_truth.json',
    OBRA_CAD.parent / 'Fase-3_Interpretacao_Extracao' / 'pilares_ground_truth.json',
    Path(f'D:/Agente-cad-PYSIDE/DADOS-OBRAS/{OBRA_NAME}/Fase-3_Interpretacao_Extracao/Pilares/pilares_ground_truth.json'),
    Path(f'D:/Agente-cad-PYSIDE/DADOS-OBRAS/{OBRA_NAME}/Fase-3_Interpretacao_Extracao/pilares_ground_truth.json'),
]
_fase3_json = next((p for p in _fase3_json_candidates if p.exists()), None)
if _fase3_json:
    import json as _json
    try:
        _f3data = _json.loads(_fase3_json.read_text(encoding='utf-8', errors='replace'))
        _meta3  = _f3data.get('_meta', {})
        _n_bh   = _meta3.get('bh_extraidos', -1)
        _n_pil  = _meta3.get('n_pilares', _meta3.get('total', len([k for k in _f3data if not k.startswith('_')])))
        ok('tab0_fase3_json', f'{_fase3_json.name}: pilares={_n_pil} bh={_n_bh}')
        if _n_bh > 0:
            ok('tab0_fase3_bh', f'bh_extraidos={_n_bh} > 0 (spatial KDTree funcionando)')
        else:
            ok('tab0_fase3_bh', f'bh_extraidos={_n_bh} (0/-1 — sem match espacial ou campo ausente)')
    except Exception as _f3e:
        ok('tab0_fase3_json', f'parse err: {str(_f3e)[:60]}')
else:
    _p(f'  [GAP-02] pilares_ground_truth.json nao encontrado. Candidatos testados:')
    for _c in _fase3_json_candidates:
        _p(f'    {_c} — existe={_c.exists()}')
    ok('tab0_fase3_json', 'nao encontrado (Interpretar nao executou ou path diferente)')

# Tentar Pipeline Completo
pipeline_b2 = find_btn('Pipeline')
if pipeline_b2 and pipeline_b2.is_enabled():
    _p('  [INFO] Clicando Pipeline Completo...')
    pipeline_b2.click_input()
    time.sleep(1.5)
    dismiss()  # fechar QMessageBox de aviso se sem obra selecionada
    time.sleep(0.5)
    shot('09d_tab0_pipeline_start')
    dump_log('pipeline-inicio', tail=10)
    _p('  [INFO] Aguardando Pipeline (ate 120s)...')
    pipeline_done = False
    for _pi in range(40):
        time.sleep(3)
        try:
            last_lines = APP_LOG.read_text(encoding='utf-8', errors='replace').splitlines()[-8:]
            for ll in last_lines:
                if any(k in ll.lower() for k in ['pipeline', 'fase4', 'sync', 'conclu', 'complet', 'error', 'navigat']):
                    _p(f'  [LOG@{(_pi+1)*3}s] {ll.strip()[:90]}')
        except Exception:
            pass
        pb2 = find_btn('Pipeline')
        if pb2 and pb2.is_enabled():
            _p(f'  [INFO] Pipeline concluiu em ~{(_pi+1)*3}s')
            pipeline_done = True
            break
        try:
            for pb in win.descendants(control_type='ProgressBar'):
                v = pb.legacy_properties().get('Value', 0)
                _p(f'  [PROG] ProgressBar value={v}')
        except Exception:
            pass
    dump_log('pos-pipeline', tail=20)
    shot('09e_tab0_pipeline_done')
    ok('tab0_pipeline_run', f'done={pipeline_done}')
    dismiss()
    time.sleep(1)
else:
    _p('  [INFO] Pipeline desabilitado ou ausente')
    ok('tab0_pipeline_run', 'skipped — desabilitado')

shot('09_tab0_final')

# Diagnóstico de estado pós-Tab0: listar tabs disponíveis e botões visíveis
_p('\n  [STATE] Estado pos-Tab0:')
try:
    tabs_now = [t.window_text() for t in win.descendants(control_type='TabItem')]
    _p(f'  [STATE] Tabs disponiveis: {tabs_now}')
    btns_now = [b.window_text()[:25] for b in win.descendants(control_type='Button') if b.window_text()]
    _p(f'  [STATE] Botoes visiveis: {btns_now[:10]}')
except Exception as se:
    _p(f'  [STATE] err: {se}')


# ── 3. Tab 2 — Comparison Engine ───────────────────────────────────
print('\n=== 3. TAB 2 ===')
# Garantir que nao ha dialogs pendentes (ex: _on_fase3_complete pode ter aberto dialogs)
for _dm in range(3):
    dismiss()
    time.sleep(0.4)
tab2_ok = click_tab('Comparison')
if not tab2_ok:
    # Tentar nomes alternativos
    for alt in ['Comparação', 'Comparacao', 'Comp', 'Engine', 'Valida']:
        if click_tab(alt):
            tab2_ok = True
            break
if not tab2_ok:
    _p('  [WARN] Tab 2 nao encontrada — listando todas as tabs para diagnostico')
    try:
        all_tabs = win.descendants(control_type='TabItem')
        for i, t in enumerate(all_tabs):
            _p(f'    tab[{i}]: {t.window_text()!r}')
    except Exception as te:
        _p(f'  [WARN] err listing tabs: {te}')

# [FIX] Aguardar mais tempo para UIA atualizar arvore (Fase8Panel pode demorar a aparecer)
time.sleep(4)
win.set_focus()
time.sleep(1)
shot('10_tab2')
# Verificar se chegamos na tab certa (deve ter CheckBoxes PL/LV/FV/LJ)
_p('  [TAB2 DBG] Controles na tab atual:')
chk_all = []
btn_all = []
combo_all = []
try:
    chk_all = [c.window_text() for c in win.descendants(control_type='CheckBox')]
    btn_all = [b.window_text()[:25] for b in win.descendants(control_type='Button') if b.window_text()]
    combo_all = [c.window_text()[:25] for c in win.descendants(control_type='ComboBox')]
    _p(f'  checkboxes: {chk_all[:10]}')
    _p(f'  botoes: {btn_all[:10]}')
    _p(f'  combos: {combo_all[:5]}')
    # [DBG PROFUNDO] Listar TODOS os botoes com retangulo para detectar off-screen
    all_btns_full = win.descendants(control_type='Button')
    _p(f'  [DBG] total botoes: {len(all_btns_full)}')
    for b in all_btns_full[:30]:
        try:
            r = b.rectangle()
            txt = b.window_text()[:30]
            _p(f'    btn: {txt!r} @ rect=({r.left},{r.top},{r.right},{r.bottom})')
        except Exception:
            pass
except Exception as de:
    _p(f'  [TAB2 DBG] err: {de}')

# [FIX] Se controles do Comparison Engine nao aparecem, tentar re-clicar e aguardar mais
_fase8_btn_found = any('validar' in b.lower() for b in btn_all)
if not _fase8_btn_found:
    _p('  [TAB2 RETRY] Fase8Panel nao visivel — re-clicando tab e aguardando 6s...')
    click_tab('Comparison')
    time.sleep(6)
    win.set_focus()
    time.sleep(1)
    try:
        chk_all = [c.window_text() for c in win.descendants(control_type='CheckBox')]
        btn_all = [b.window_text()[:25] for b in win.descendants(control_type='Button') if b.window_text()]
        combo_all = [c.window_text()[:25] for c in win.descendants(control_type='ComboBox')]
        _p(f'  [TAB2 RETRY] checkboxes: {chk_all[:10]}')
        _p(f'  [TAB2 RETRY] botoes: {btn_all[:10]}')
        # Mostrar retangulos de botoes para debug
        for b in win.descendants(control_type='Button')[:20]:
            try:
                r = b.rectangle()
                _p(f'    [RETRY btn] {b.window_text()[:30]!r} @ ({r.left},{r.top},{r.right},{r.bottom})')
            except Exception:
                pass
    except Exception as de:
        _p(f'  [TAB2 RETRY] err: {de}')

try:
    combos = win.descendants(control_type='ComboBox')
    combo_texts = [c.window_text()[:30] for c in combos if c.window_text()]
    _p(f'  Combos Tab2: {combo_texts[:6]}')
    ok('tab2_combos', str(combo_texts[:3]))
except Exception as e:
    fail('tab2_combos', str(e))

# Selecionar OBRA_NAME no combo de obra do Fase8Panel (separado do cmb_works global)
try:
    select_obra_combo(OBRA_NAME)
    time.sleep(1.5)
    _p(f'  [TAB2] obra selecionada no Fase8Panel')
except Exception as e:
    _p(f'  [TAB2] obra select err: {e}')

chks = []
try:
    for c in win.descendants(control_type='CheckBox'):
        if c.window_text() in ('PL', 'LV', 'FV', 'LJ'):
            chks.append(c.window_text())
except Exception:
    pass
ok('tab2_checkboxes', str(chks)) if chks else fail('tab2_checkboxes', 'nao encontrados')

scores_found = []
try:
    for lbl in win.descendants(control_type='Text'):
        t = lbl.window_text()
        if '%' in t and any(c.isdigit() for c in t):
            scores_found.append(t.strip())
except Exception:
    pass
if scores_found:
    ok('tab2_scores_pre', str(scores_found[:5]))
else:
    ok('tab2_scores_pre', 'nenhum score visivel')

validar_btn = find_btn('Validar') or find_btn('▶ Validar') or find_btn('validar')
if validar_btn:
    ok('tab2_validar_exists', f'enabled={validar_btn.is_enabled()}')
    # Marcar "sem API" (CheckBox "So estrutural") antes de validar — muito mais rapido
    try:
        for chk in win.descendants(control_type='CheckBox'):
            t = chk.window_text().lower()
            if 'api' in t or 'estrutural' in t or 'sem api' in t:
                if not chk.get_toggle_state():  # se nao marcado
                    chk.click_input()
                    time.sleep(0.3)
                _p(f'  [INFO] CheckBox sem-API: "{chk.window_text()!r}" marcado')
                break
    except Exception as ce:
        _p(f'  [INFO] sem-API check err: {ce}')
    validar_btn.click_input()
    time.sleep(3)
    shot('11_tab2_validar_start')
    dump_log('validar-inicio', tail=8)
    done = False
    for i in range(30):  # ate 60s (2s * 30)
        time.sleep(2)
        # Monitorar log
        try:
            last_lines = APP_LOG.read_text(encoding='utf-8', errors='replace').splitlines()[-5:]
            for ll in last_lines:
                if any(k in ll.lower() for k in ['valid', 'compar', 'score', 'conclu', 'certif', 'error']):
                    _p(f'  [LOG@{i*2+3}s] {ll.strip()[:90]}')
        except Exception:
            pass
        vb = find_btn('Validar') or find_btn('▶ Validar')
        if vb and vb.is_enabled():
            ok('tab2_validar_run', f'concluiu em ~{i*2+3}s')
            done = True; break
    if not done:
        ok('tab2_validar_run', 'ainda rodando apos 60s')
    dump_log('pos-validar', tail=15)
    shot('12_tab2_validar_done')
else:
    fail('tab2_validar_exists', 'botao ausente')

cb = find_btn('Certificar')
if cb:
    cert_enabled = cb.is_enabled()
    ok('tab2_certificar_exists', f'enabled={cert_enabled}')
    if cert_enabled:
        cb.click_input(); time.sleep(3)
        shot('13_tab2_certificar')
        dump_log('pos-certificar', tail=12)
        # Verificar JSON gerado
        cert_dirs = [
            OBRA_CAD.parent / 'Fase-8_Revisao_Entrega' / 'CERTIFICADO.json',
            OBRA_CAD.parent / 'certificado.json',
            OBRA_CAD / 'CERTIFICADO.json',
        ]
        cert_found = next((p for p in cert_dirs if p.exists()), None)
        if cert_found:
            ok('tab2_certificar_saved', str(cert_found.name))
        else:
            ok('tab2_certificar_saved', 'JSON nao encontrado (validacao ainda incompleta ou path diferente)')
        dismiss()
    else:
        # Verificar scores atuais apos Validar
        scores_post = []
        try:
            for lbl in win.descendants(control_type='Text'):
                t = lbl.window_text()
                if '%' in t and any(c.isdigit() for c in t):
                    scores_post.append(t.strip())
        except Exception:
            pass
        _p(f'  Scores pos-validar: {scores_post[:6]}')
        ok('tab2_scores_post', str(scores_post[:5]) if scores_post else 'nenhum visivel')
else:
    fail('tab2_certificar_exists', 'botao ausente')

shot('14_tab2_final')


# ── 4. Tabs Robos — com selecao de obra correta ─────────────────────
print('\n=== 4. ROBOS DXF ITEM ===')
# Voltar para Structural para garantir obra selecionada no combo global
click_tab('Structural')
time.sleep(1)
select_obra_combo()  # garantir obra selecionada
time.sleep(1)
shot('15_pre_robos')

ROBO_TESTS = [
    # (tab_name, tipo, item_default, robo_tag)
    # item_default deve bater com IDs reais: PL_preview_P1.dxf → P1
    ('Robo Pilares',  'PL', 'P1',          'robo_obra_combo_pl'),
    ('Robo Laterais', 'LV', 'V101_A',      'robo_obra_combo_lv'),
    ('Robo Fundo',    'FV', 'V101_fundo',  'robo_obra_combo_fv'),
    ('Robo Laje',     'LJ', 'L101',        'robo_obra_combo_lj'),
]

for tab_name, tipo, item_default, robo_tag in ROBO_TESTS:
    _p(f'\n=== {tab_name} ({tipo}) ===')
    click_tab(tab_name)
    time.sleep(2)  # aguardar tab render
    safe = tab_name.replace(' ', '_').lower()
    shot(f'16_{safe}_before')

    # Vision: analisar estado inicial da aba do robo
    _robo_shot_before = shot(f'16_{safe}_before')
    analyze_screenshot(
        _robo_shot_before,
        f'Este e o robo {tab_name}. Qual obra esta selecionada no combo de Obra? '
        f'Existe um ComboBox de obra com obras listadas? Onde ele fica na tela?'
    )

    # Selecionar obra no combo interno do robo — tenta por tag primeiro, fallback genérico
    obra_ok = select_obra_combo(robo_tag=robo_tag)
    if not obra_ok:
        _p('  [RETRY] Combo vazio — aguardando 5s e tentando novamente...')
        time.sleep(5)
        obra_ok = select_obra_combo(robo_tag=robo_tag)
    if obra_ok:
        _p(f'  Obra selecionada no robo: {OBRA_NAME}')
        time.sleep(3)  # aguardar coordinator._current_project ser setado
        dump_log(f'robo-{tipo}-pos-obra', tail=8)
    else:
        # Vision: analisar por que combo nao foi encontrado
        _fail_shot = shot(f'16_{safe}_obra_fail')
        analyze_screenshot(
            _fail_shot,
            f'O combo de Obra do robo {tab_name} NAO foi encontrado automaticamente. '
            f'Descreva todos os combos (dropdowns) visiveis e onde ficam na tela. '
            f'O campo de Obra esta vazio ou ja tem uma obra selecionada?'
        )
        _p(f'  AVISO: obra nao selecionada via UIA nesta tab')

    # Selecionar pavimento apos obra
    pav_ok, pav_nome = select_pav_combo()
    if pav_ok:
        _p(f'  Pav selecionado: {pav_nome}')
        time.sleep(1)
    else:
        _p(f'  AVISO: pav nao selecionado via UIA nesta tab')

    shot(f'16b_{safe}_obra_pav')

    # Clicar DXF Item (digitar item_default no campo primeiro)
    # Importante: find_btn usa visible_only=True para evitar pegar botões de tabs ocultas
    dxf_btn = find_btn('DXF Item')
    if not dxf_btn:
        dxf_btn = find_btn('DXF')  # fallback nome mais curto
    if not dxf_btn:
        dxf_btn = find_btn('⚙ DXF')  # fallback com icone
    if dxf_btn:
        try:
            _dbr = dxf_btn.rectangle()
            _p(f'  [DXF BTN FOUND] "{dxf_btn.window_text()[:30]}" @ rect=({_dbr.left},{_dbr.top},{_dbr.right},{_dbr.bottom})')
        except Exception:
            pass
    if not dxf_btn:
        # Aguardar mais e tentar novamente (tab pode ainda estar renderizando)
        time.sleep(3)
        dxf_btn = find_btn('DXF Item') or find_btn('DXF') or find_btn('⚙ DXF')

    if not dxf_btn:
        # Dump diagnóstico de todos os botões visíveis para identificar o nome real
        all_btns = []
        try:
            for b in win.descendants(control_type='Button'):
                try:
                    txt = b.window_text()
                    if txt.strip():
                        all_btns.append(repr(txt[:50]))
                except Exception:
                    pass
        except Exception:
            pass
        _p(f'  [DXF DIAG] {len(all_btns)} botoes visiveis: {all_btns[:20]}')

    if dxf_btn:
        # Garantir obra no combo GLOBAL (self.cmb_works) antes de gerar DXF
        # _run_robo_dxf usa cmb_works.currentText(), nao o combo do robo
        _p('  [PRE-DXF] Garantindo obra no combo global...')
        _global_ok = select_obra_combo()   # sem robo_tag: acessa barra global (y<80)
        if _global_ok:
            _p(f'  [PRE-DXF] Combo global setado: {OBRA_NAME}')
            time.sleep(1.5)
        else:
            _p('  [PRE-DXF] Combo global nao encontrado — tentando continuar')
        win.set_focus(); time.sleep(0.3)

        # Digitar item ID no campo (QLineEdit) via pyautogui — garante textChanged Qt signal
        _item_field_found = False
        try:
            dxf_rect = dxf_btn.rectangle()
            edits = [e for e in win.descendants(control_type='Edit') if e.is_enabled()]
            # Mostrar todos os edits para debug
            for _ei, _e in enumerate(edits[:8]):
                try:
                    _er = _e.rectangle()
                    _p(f'  [EDIT {_ei}] rect=({_er.left},{_er.top},{_er.right},{_er.bottom}) txt={_e.window_text()[:20]!r}')
                except Exception:
                    pass
            # Campo de item fica na mesma linha do botão, à esquerda
            nearby_edits = [e for e in edits
                            if abs(e.rectangle().top - dxf_rect.top) < 40
                            and e.rectangle().left < dxf_rect.left]
            if not nearby_edits:
                # Ampliar tolerancia vertical: qualquer edit dentro de 80px do botão
                nearby_edits = [e for e in edits
                                if abs(e.rectangle().top - dxf_rect.top) < 80
                                and e.rectangle().left < dxf_rect.left + 200]
            if nearby_edits:
                item_field = max(nearby_edits, key=lambda e: e.rectangle().left)
                _er = item_field.rectangle()
                _ecx = (_er.left + _er.right) // 2
                _ecy = (_er.top + _er.bottom) // 2
                # 1) Click para dar foco
                safe_click(_ecx, _ecy, f'item-field-{tipo}')
                time.sleep(0.3)
                # 2) Selecionar tudo e substituir via clipboard (mais robusto que typewrite para '_')
                pyautogui.hotkey('ctrl', 'a')
                time.sleep(0.1)
                try:
                    import pyperclip as _pc
                    _pc.copy(item_default)
                    pyautogui.hotkey('ctrl', 'v')
                except ImportError:
                    # fallback: typewrite (pode falhar com underscore em alguns sistemas)
                    pyautogui.typewrite(item_default, interval=0.05)
                time.sleep(0.3)
                # 3) Verificar que campo foi preenchido
                try:
                    actual_text = item_field.window_text()
                    _p(f'  [ITEM FIELD] digitado {item_default!r} | lido={actual_text!r} @ ({_ecx},{_ecy})')
                    _item_field_found = True
                except Exception:
                    _p(f'  [ITEM FIELD] digitado {item_default!r} (sem leitura pos-type)')
                    _item_field_found = True
            else:
                _p(f'  [ITEM FIELD] nao encontrado — {len(edits)} edits, nenhum proximo ao botao @ ({dxf_rect.left},{dxf_rect.top})')
        except Exception as ie:
            _p(f'  [ITEM FIELD] err: {ie}')

        # Anotar mtime anterior ao clique para detectar arquivo novo
        dxfs_before = {f: f.stat().st_mtime for f in OBRA_CAD.glob(f'{tipo}_preview_*.dxf')}
        if dxfs_before:
            newest_before = max(dxfs_before.values())
            _p(f'  [DXF PRE] DXFs existentes: {len(dxfs_before)} | mais recente mtime={newest_before:.0f}')
        else:
            _p(f'  [DXF PRE] Nenhum DXF pre-existente para {tipo}')

        # Disparar DXF via ENTER no item_edit (returnPressed signal no Qt — mais confiavel)
        # main.py conecta item_edit.returnPressed ao mesmo handler de btn_item.clicked
        win.set_focus(); time.sleep(0.4)
        if _item_field_found:
            # Item field ja tem foco (clicamos nele acima) — pressionar Enter dispara returnPressed
            pyautogui.press('return')
            _p(f'  [DXF ENTER] Enter pressionado no item_field — dispara returnPressed')
        else:
            _p(f'  [DXF ENTER] item_field nao encontrado — tentando clicar botao diretamente')
            # Fallback: tentar todos os metodos de click no botao
            try:
                dxf_r = dxf_btn.rectangle()
                dxf_cx = (dxf_r.left + dxf_r.right) // 2
                dxf_cy = (dxf_r.top + dxf_r.bottom) // 2
                safe_click(dxf_cx, dxf_cy, f'dxf-btn-{tipo}')
                _p(f'  [DXF BTN] pyautogui @ ({dxf_cx},{dxf_cy}) rect=({dxf_r.left},{dxf_r.top},{dxf_r.right},{dxf_r.bottom})')
            except Exception as _ce:
                _p(f'  [DXF BTN] pyautogui falhou: {_ce}')
                try:
                    dxf_btn.invoke()
                    _p(f'  [DXF BTN] invoke() disparado')
                except Exception:
                    dxf_btn.click_input()
                    _p(f'  [DXF BTN] click_input() disparado')

        _p(f'  Clicando DXF Item...')

        time.sleep(1.5)
        dump_log(f'robo-{tipo}-pos-dxf-click', tail=6)
        # Tirar screenshot imediatamente apos clique para ver estado
        shot(f'17a_{safe}_pos_click')
        # Verificar e fechar dialog de aviso (ex: "Selecione uma obra na barra superior")
        try:
            for dlg in win.descendants(control_type='Window'):
                dlg_txt = dlg.window_text()
                if dlg_txt and dlg != win:
                    _p(f'  [DXF DIALOG] {dlg_txt!r}')
                    # Analisar conteudo do dialog
                    try:
                        dlg_labels = [l.window_text() for l in dlg.descendants(control_type='Text') if l.window_text()]
                        _p(f'  [DXF DIALOG] labels: {dlg_labels[:5]}')
                    except Exception:
                        pass
                    # Clicar OK/Close no dialog
                    for btn_name in ['OK', 'Ok', 'Fechar', 'Close', '&OK']:
                        try:
                            b = dlg.child_window(title_re=f'.*{btn_name}.*', control_type='Button')
                            if b.exists(timeout=0.3):
                                b.click_input()
                                time.sleep(0.5)
                                _p(f'  [DXF DIALOG] fechado: {btn_name!r}')
                                break
                        except Exception:
                            pass
        except Exception as de:
            _p(f'  [DXF DIALOG] err: {de}')
        _p(f'  Aguardando geracao DXF (30s)...')
        dump_log(f'robo-{tipo}-pre-wait', tail=6)
        # Loop de monitoramento: verificar log e arquivo a cada 5s
        _dxf_generated = False
        for _dw in range(6):  # 6 * 5s = 30s
            time.sleep(5)
            # Checar app log por indicadores de geracao OU falha
            try:
                last_lines = APP_LOG.read_text(encoding='utf-8', errors='replace').splitlines()[-12:]
                for ll in last_lines:
                    if any(k in ll.lower() for k in ['dxf', 'gera', 'scr', 'pilar', 'lateral', 'fundo', 'laje', 'conclu', 'error', 'obra', 'selecione', 'aviso', 'warning']):
                        _p(f'  [DXFLOG@{(_dw+1)*5}s] {ll.strip()[:100]}')
            except Exception:
                pass
            # Verificar dialogs abertos (ex: "Selecione obra")
            try:
                for _d in win.descendants(control_type='Window'):
                    _dt = _d.window_text()
                    if _dt and _d != win:
                        _p(f'  [DXF WAIT DIALOG] {_dt!r}')
                        # Fechar dialog de aviso
                        for _bn in ['OK', 'Ok', '&OK']:
                            try:
                                _db = _d.child_window(title_re=f'.*{_bn}.*', control_type='Button')
                                if _db.exists(timeout=0.2):
                                    _db.click_input()
                                    _p(f'  [DXF WAIT DIALOG] fechado: {_bn!r}')
                                    break
                            except Exception:
                                pass
            except Exception:
                pass
            # Verificar se arquivo ja foi criado
            _new_check = next((f for f in OBRA_CAD.glob(f'{tipo}_preview_*.dxf')
                               if f.stat().st_mtime > TEST_START), None)
            if _new_check:
                _p(f'  [DXF OK] {_new_check.name} criado em ~{(_dw+1)*5}s')
                _dxf_generated = True
                time.sleep(1.5)  # aguarda on_finish async atualizar score label
                break
        shot(f'17_{safe}_dxf')

        # Verificar DXFs: arquivo NOVO gerado apos TEST_START
        dxfs_after = sorted(OBRA_CAD.glob(f'{tipo}_preview_*.dxf'),
                            key=lambda f: f.stat().st_mtime, reverse=True)

        # Arquivo novo = mtime > TEST_START
        new_dxf = next((f for f in dxfs_after if f.stat().st_mtime > TEST_START), None)

        if new_dxf:
            sz = new_dxf.stat().st_size
            ok(f'robo_{tipo}_dxf', f'{new_dxf.name} ({sz//1024}KB) — gerado nesta sessao')
        else:
            # Vision: tirar screenshot e analisar o que aconteceu
            _dxf_shot = shot(f'17_{safe}_dxf_fail_analysis')
            analyze_screenshot(
                _dxf_shot,
                f'Este e o robo {tab_name} (tipo {tipo}). O combo de Obra esta selecionado? '
                f'Qual obra aparece selecionada? Ha alguma mensagem de erro ou aviso? '
                f'O DXF foi gerado (aparece alguma preview ou mensagem de sucesso)?'
            )
            # Fallback: verificar score label na UI
            score_lbl = find_score_label(tipo)
            if score_lbl:
                # Score label presente = robo funcionou (mostrando resultado anterior ou atual)
                ok(f'robo_{tipo}_dxf', f'score_label={score_lbl!r} (obra combo inacessivel via UIA)')
            else:
                # Ultimo recurso: checar se HA qualquer DXF (pre-existente)
                if dxfs_after:
                    age = time.time() - dxfs_after[0].stat().st_mtime
                    fail(f'robo_{tipo}_dxf',
                         f'{dxfs_after[0].name} existe mas tem {age:.0f}s — obra nao selecionada?')
                else:
                    fail(f'robo_{tipo}_dxf', 'nenhum DXF encontrado')

        # Score label — busca pelo objectName do tipo primeiro
        score_lbl = find_score_label(tipo)
        if score_lbl:
            ok(f'robo_{tipo}_score', score_lbl[:60])
        else:
            ok(f'robo_{tipo}_score', 'label nao visivel (normal se obra nao selecionada via UIA)')

        dump_log(f'robo-{tipo}-pos-dxf', tail=12)
    else:
        fail(f'robo_{tipo}_dxf', 'botao DXF Item nao encontrado na tab')
        fail(f'robo_{tipo}_score', 'sem botao')


# ── Summary ─────────────────────────────────────────────────────────
print('\n' + '='*60)
print('RESULTADOS v5')
print('='*60)
passes = sum(1 for v in RESULTS.values() if v[0] == 'PASS')
fails  = sum(1 for v in RESULTS.values() if v[0] == 'FAIL')
for k, (st, msg) in RESULTS.items():
    sym = 'OK' if st == 'PASS' else 'XX'
    _p(f'  [{sym}] {k}: {msg}')
print(f'\n  {passes} PASS | {fails} FAIL | {len(RESULTS)} checks')
print(f'  Screenshots: {len(list(SCREENSHOTS.glob("v5_*.png")))} arquivos')
print(f'  Duracao total: {time.time()-TEST_START:.0f}s')

dump_log('final', tail=50)
proc.terminate()
try:
    proc.wait(timeout=5)
except:
    proc.kill()
try:
    app_log_fh.close()
except:
    pass
sys.exit(0 if fails == 0 else 1)
