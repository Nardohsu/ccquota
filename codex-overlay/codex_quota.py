"""Codex-only Windows usage overlay. Python standard library; no app patching."""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes as W
from datetime import datetime
import json
import math
import os
from pathlib import Path
import queue
import sys
import threading
import time
import tkinter as tk

# The app-server reader is the one ccquota.py already ships, one folder up.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ccquota import codex_app_server, parse_codex_limits  # noqa: E402

BASE = Path(__file__).resolve().parent
BG, FG, MUTED = '#242424', '#dedede', '#a5a5a5'
GREEN, YELLOW, RED = '#55cf69', '#edc96b', '#f17d7d'


def number(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)


def compact(value):
    for divisor, suffix in ((1_000_000, 'M'), (1_000, 'K')):
        if value >= divisor:
            return f'{value/divisor:.1f}{suffix}'
    return str(int(value))


def countdown(stamp, now):
    minutes = max(0, math.ceil((stamp - now) / 60))
    if minutes >= 1440:
        return f'{minutes//1440}d{minutes%1440//60}h'
    return f'{minutes//60}h{minutes%60:02d}m'


class LogUsage:
    """Incremental parsing: retain numeric token events, never conversation text.

    Sum cumulative-counter deltas so repeated quota events do not double count.
    Count cached input inside input, and reasoning inside output, exactly once.
    """
    def __init__(self, root):
        self.root = Path(root)
        self.files = {}
        self.day = None
        self.latest_limit = None

    def scan(self, now=None):
        now = time.time() if now is None else now
        day = datetime.fromtimestamp(now).date()
        if day != self.day:
            self.files.clear()
            self.latest_limit = None
            self.day = day
        paths = []
        for folder in ('sessions', 'archived_sessions'):
            paths.extend((self.root / folder).rglob('*.jsonl'))
        present = set(paths)
        for deleted in set(self.files) - present:
            del self.files[deleted]
        for path in paths:
            try:
                stat = path.stat()
                state = self.files.get(path)
                identity = (stat.st_dev, stat.st_ino)
                if state is None or state['offset'] > stat.st_size or state['identity'] != identity:
                    state = dict(offset=0, previous=0, tokens=0, events=0, identity=identity)
                    self.files[path] = state
                with path.open('rb') as stream:
                    stream.seek(state['offset'])
                    while True:
                        start = stream.tell()
                        raw = stream.readline()
                        if not raw or not raw.endswith(b'\n'):
                            state['offset'] = start
                            break
                        state['offset'] = stream.tell()
                        if b'"token_count"' not in raw:
                            continue
                        try:
                            record = json.loads(raw)
                            payload = record.get('payload') or {}
                            if record.get('type') != 'event_msg' or payload.get('type') != 'token_count':
                                continue
                            stamp = datetime.fromisoformat(record['timestamp'].replace('Z', '+00:00'))
                            timestamp = stamp.timestamp()
                            lim = payload.get('rate_limits')
                            if isinstance(lim, dict) and lim.get('limit_id') in (None, 'codex'):
                                if self.latest_limit is None or timestamp > self.latest_limit[0]:
                                    parsed = parse_codex_limits({'rateLimits': lim}, now, 'logs')
                                    if parsed:
                                        self.latest_limit = (timestamp, parsed)
                            info = payload.get('info') or {}
                            total = (info.get('total_token_usage') or {}).get('total_tokens')
                            if not number(total) or total < 0:
                                continue
                            previous = state['previous']
                            # A decreased counter begins a new accounting segment.
                            delta = total - previous if total >= previous else total
                            state['previous'] = total
                            if stamp.astimezone().date() == day and delta > 0:
                                state['tokens'] += delta
                                state['events'] += 1
                        except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
                            continue
            except OSError:
                continue
        return {'today_tokens': sum(s['tokens'] for s in self.files.values()),
                'events': sum(s['events'] for s in self.files.values()),
                'files': len(self.files), 'log_limits': self.latest_limit}


class DataSource:
    def __init__(self, root):
        self.logs = LogUsage(root)
        self.last_rpc = 0
        self.live = None

    def gather(self, force=False):
        now = time.time()
        usage = self.logs.scan(now)
        if force or now - self.last_rpc >= 60:
            self.live = codex_app_server(now)
            self.last_rpc = now
        limits = self.live
        observed = self.last_rpc
        if limits is None and usage['log_limits']:
            observed, limits = usage['log_limits']
        return dict(usage, limits=limits, observed=observed, updated=now)


class WindowFollower:
    """Read window position/process identity. Does not inspect app internals."""
    def __init__(self):
        self.user = ctypes.WinDLL('user32', use_last_error=True)
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.user.GetForegroundWindow.restype = W.HWND
        self.user.GetAncestor.argtypes = [W.HWND, W.UINT]
        self.user.GetAncestor.restype = W.HWND
        self.user.IsWindowVisible.argtypes = [W.HWND]
        self.user.IsIconic.argtypes = [W.HWND]
        self.user.GetClientRect.argtypes = [W.HWND, ctypes.POINTER(W.RECT)]
        self.user.ClientToScreen.argtypes = [W.HWND, ctypes.POINTER(W.POINT)]
        self.user.GetWindowThreadProcessId.argtypes = [W.HWND, ctypes.POINTER(W.DWORD)]
        self.kernel.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
        self.kernel.OpenProcess.restype = W.HANDLE
        self.kernel.QueryFullProcessImageNameW.argtypes = [W.HANDLE, W.DWORD, W.LPWSTR, ctypes.POINTER(W.DWORD)]
        self.kernel.CloseHandle.argtypes = [W.HANDLE]
        self.known = {}

    def is_codex(self, hwnd):
        pid = W.DWORD()
        self.user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        key = (hwnd, pid.value)
        if key not in self.known:
            handle = self.kernel.OpenProcess(0x1000, False, pid.value)
            name = ''
            if handle:
                try:
                    size = W.DWORD(32768)
                    buffer = ctypes.create_unicode_buffer(size.value)
                    if self.kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                        name = buffer.value.lower()
                finally:
                    self.kernel.CloseHandle(handle)
            # The Codex desktop package currently displays a ChatGPT window title.
            self.known[key] = Path(name).name in ('codex.exe', 'chatgpt.exe') and (
                'windowsapps' in name or 'openai' in name or 'codex' in name)
        return self.known[key]

    def foreground(self):
        return self.user.GetForegroundWindow()

    def find_codex(self):
        matches = []
        callback_type = ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
        @callback_type
        def visit(hwnd, _):
            if self.user.IsWindowVisible(hwnd) and self.is_codex(hwnd):
                matches.append(hwnd)
            return True
        self.user.EnumWindows.argtypes = [callback_type, W.LPARAM]
        self.user.EnumWindows(visit, 0)
        return matches[0] if matches else None

    def rect(self, hwnd):
        if not hwnd or not self.user.IsWindowVisible(hwnd) or self.user.IsIconic(hwnd):
            return None
        rect, point = W.RECT(), W.POINT()
        if not self.user.GetClientRect(hwnd, ctypes.byref(rect)):
            return None
        self.user.ClientToScreen(hwnd, ctypes.byref(point))
        return point.x, point.y, rect.right, rect.bottom


class Overlay:
    def __init__(self, args):
        self.args = args
        self.root = tk.Tk()
        self.root.title('Codex Quota')
        self.root.configure(bg=BG)
        self.root.overrideredirect(not args.framed)
        self.root.attributes('-topmost', True)
        self.root.geometry('+360+100')
        self.settings_path = BASE / 'settings.json'
        try:
            self.settings = json.loads(self.settings_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            self.settings = {}
        self.follow = tk.BooleanVar(value=not args.detached and self.settings.get('follow', True))
        self.offset_x = int(self.settings.get('offset_x', 0))
        self.offset_y = int(self.settings.get('offset_y', 135)) if self.settings.get('anchor') == 'bottom' else 135
        self.follower = WindowFollower() if os.name == 'nt' else None
        self.target = self.follower.find_codex() if self.follower else None
        self.target_rect = None
        self.drag = None
        self.data = None
        self.results = queue.Queue()
        self.busy = False
        self.source = DataSource(args.codex_home)
        self.top = tk.Frame(self.root, bg=BG)
        self.top.pack(fill='x', padx=12, pady=7)
        self.menu = tk.Menu(self.root, tearoff=False, bg=BG, fg=FG)
        self.menu.add_checkbutton(label='跟隨 Codex 視窗', variable=self.follow, command=self.save)
        self.menu.add_command(label='立即更新', command=lambda: self.refresh(True))
        self.menu.add_command(label='重設位置', command=self.reset)
        self.menu.add_separator()
        self.menu.add_command(label='結束', command=self.root.destroy)
        self.root.bind('<Escape>', lambda _: self.root.destroy())
        self.root.bind('<Button-3>', self.popup)
        self.root.bind('<ButtonPress-1>', self.start_drag)
        self.root.bind('<B1-Motion>', self.move_drag)
        self.root.bind('<ButtonRelease-1>', self.end_drag)
        self.render()
        self.root.after(100, self.refresh)
        self.root.after(150, self.poll)
        self.root.after(200, self.track)
        if args.smoke:
            self.root.after(2500, self.smoke)

    def save(self):
        self.settings.update(follow=self.follow.get(), offset_x=self.offset_x,
                             offset_y=self.offset_y, anchor='bottom')
        self.settings_path.write_text(json.dumps(self.settings, indent=2), encoding='utf-8')

    def reset(self):
        self.offset_x, self.offset_y = 0, 135
        self.follow.set(True)
        self.save()

    def popup(self, event):
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def start_drag(self, event):
        self.drag = event.x_root, event.y_root, self.root.winfo_x(), self.root.winfo_y()

    def move_drag(self, event):
        if self.drag:
            px, py, x, y = self.drag
            self.root.geometry(f'+{max(0, x + event.x_root-px)}+{max(0, y + event.y_root-py)}')

    def end_drag(self, event):
        if self.drag and self.target_rect:
            x, y, width, height = self.target_rect
            self.offset_x = self.root.winfo_x() - (x + (width-self.root.winfo_width())//2)
            self.offset_y = y + height - self.root.winfo_y() - self.root.winfo_height()
            self.save()
        self.drag = None

    def track(self):
        if self.follower and self.follow.get() and not self.drag:
            hwnd = self.follower.foreground()
            own = self.follower.user.GetAncestor(self.root.winfo_id(), 2)
            if hwnd != own and self.follower.is_codex(hwnd):
                self.target = hwnd
            if self.target:
                rect = self.follower.rect(self.target)
                if rect and hwnd in (self.target, own):
                    self.target_rect = rect
                    x, y, width, height = rect
                    w = self.root.winfo_reqwidth()
                    h = self.root.winfo_reqheight()
                    left = max(x, min(x+width-w, x+(width-w)//2+self.offset_x))
                    top = max(y, min(y+height-h, y+height-h-self.offset_y))
                    self.root.geometry(f'+{max(0,left)}+{max(0,top)}')
                    self.root.deiconify()
                else:
                    self.root.withdraw()
        else:
            self.root.deiconify()
        self.root.after(250, self.track)

    def refresh(self, force=False):
        if not self.busy:
            self.busy = True
            def work():
                try:
                    self.results.put(self.source.gather(force))
                except Exception:
                    self.results.put({'error': True, 'updated': time.time()})
            threading.Thread(target=work, daemon=True).start()
        if not force:
            self.root.after(15000, self.refresh)

    def poll(self):
        try:
            self.data = self.results.get_nowait()
            self.busy = False
            self.render()
        except queue.Empty:
            pass
        self.root.after(200, self.poll)

    def label(self, parent, text, color=MUTED, bold=False):
        tk.Label(parent, text=text, bg=BG, fg=color,
                 font=('Microsoft JhengHei UI', 10, 'bold' if bold else 'normal')).pack(side='left')

    def render(self):
        for child in self.top.winfo_children():
            child.destroy()
        now = time.time()
        limits = (self.data or {}).get('limits') or {}
        indicator = MUTED if self.data is None else GREEN if limits.get('source') == 'app-server' else YELLOW
        self.label(self.top, '● ', indicator)
        self.label(self.top, 'Codex  ', FG, True)
        for key, title in (('five_hour', '5h '), ('weekly', '週 ')):
            self.label(self.top, title)
            window = limits.get(key)
            if window and window['resets_at'] > now:
                pct = window['percent']
                color = RED if pct >= 90 else YELLOW if pct >= 70 else GREEN
                self.label(self.top, f'{pct}%', color, True)
                self.label(self.top, ' '+countdown(window['resets_at'], now))
            else:
                self.label(self.top, '—')
            self.label(self.top, '  ·  ')
        self.label(self.top, '今日 ')
        tokens = (self.data or {}).get('today_tokens')
        self.label(self.top, compact(tokens) if tokens is not None else '—', FG, True)

    def smoke(self):
        self.root.update_idletasks()
        (BASE / 'smoke-result.json').write_text(json.dumps({
            'width': self.root.winfo_width(), 'height': self.root.winfo_height(),
            'children': len(self.top.winfo_children()),
            'data_loaded': self.data is not None,
            'target_found': bool(self.target),
            'visible': self.root.state() == 'normal',
        }), encoding='utf-8')
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--codex-home', default=os.environ.get('CODEX_HOME', str(Path.home()/'.codex')))
    parser.add_argument('--json', action='store_true', help='Print numeric usage and exit')
    parser.add_argument('--detached', action='store_true', help='Keep visible independently of Codex')
    parser.add_argument('--smoke', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--framed', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.json:
        data = DataSource(args.codex_home).gather()
        data.pop('log_limits', None)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    if os.name == 'nt':
        if not args.smoke and not args.framed:
            # Keep a handle alive until process exit; repeated launches do nothing.
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.CreateMutexW.argtypes = [ctypes.c_void_p, W.BOOL, W.LPCWSTR]
            kernel.CreateMutexW.restype = W.HANDLE
            instance_mutex = kernel.CreateMutexW(None, False, 'Local\\CodexQuotaOverlay-v1')
            if ctypes.get_last_error() == 183:
                return
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (OSError, AttributeError):
            pass
    Overlay(args).root.mainloop()


if __name__ == '__main__':
    main()
