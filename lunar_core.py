# language: Python 3.11, file: lunar_core.py
import json, re, sys, unicodedata, shutil, time
from pathlib import Path
from difflib import SequenceMatcher

from PyQt6.QtCore import (
    Qt, QUrl, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve
)
from PyQt6.QtGui import (
    QPixmap, QColor, QPainter, QLinearGradient, QBrush, QFontDatabase
)
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QGridLayout, QGraphicsOpacityEffect, QGraphicsDropShadowEffect,
    QLineEdit, QComboBox, QScrollArea, QMenu, QTextEdit, QDialog,
    QFileDialog, QMessageBox, QListWidget, QListWidgetItem, QInputDialog,
    QCheckBox, QSlider
)

try:
    from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
    from PyQt6.QtMultimediaWidgets import QVideoWidget
    HAS_MM = True
except ImportError:
    HAS_MM = False

BASE = Path(__file__).resolve().parent
ROMS = BASE / "roms"
COVERS = BASE / "covers"
DESCS = BASE / "descriptions"
ASSETS = BASE / "assets"
CONS_IMG = ASSETS / "consoles"
INTROS = ASSETS / "intros"
GAMEPLAY = ASSETS / "gameplay"
FONTS = ASSETS / "fonts"
CFG_PATH = BASE / "config.json"
STATE_PATH = BASE / "state.json"
COL_PATH = BASE / "collections.json"
PLAYLISTS_PATH = BASE / "playlists.json"

CONSOLE_EXTS = {
    "ps1":     {".chd", ".bin", ".cue", ".iso", ".img", ".pbp", ".m3u"},
    "ps2":     {".iso", ".chd", ".bin"},
    "snes":    {".smc", ".sfc", ".fig", ".swc"},
    "genesis": {".md", ".gen", ".bin", ".smd"},
    "nes":     {".nes", ".fds", ".unf"},
    "gba":     {".gba", ".agb"},
    "arcade":  {".zip"},
    "n64":     {".z64", ".n64", ".v64"},
}
EXTS = set().union(*CONSOLE_EXTS.values())

DEF_CFG = {
    "retroarch_path": r"E:\ps1-launcher\RetroArch\retroarch.exe",
    "cores": {
        "ps1": r"E:\ps1-launcher\RetroArch\cores\swanstation_libretro.dll",
        "snes": r"E:\ps1-launcher\RetroArch\cores\snes9x2010_libretro.dll",
        "nes": r"E:\ps1-launcher\RetroArch\cores\mesen_libretro.dll",
        "genesis": r"E:\ps1-launcher\RetroArch\cores\genesis_plus_gx_libretro.dll",
        "gba": r"E:\ps1-launcher\RetroArch\cores\mgba_libretro.dll",
        "arcade": r"E:\ps1-launcher\RetroArch\cores\mame2016_libretro.dll",
    },
    "roms_dir": str(ROMS),
    "covers_dir": str(COVERS),
    "favorites": [],
    "playtime": {},
    "recent": [],
}
DEF_STATE = {"filter": "Toutes", "sort": "Titre"}

PALETTES = {
    "ps1":     ("#2E6DB4", "#4A8FD9", "#E63946", "#0E1116", "#161A20", "#1E242C", "#2A313B", "#E6EAF0", "#7C8794"),
    "ps2":     ("#1E5AA8", "#3B7ED0", "#7FA8E0", "#0A1526", "#122036", "#1A2C48", "#243654", "#E6EEF8", "#7A8DA8"),
    "snes":    ("#8B5FBF", "#B085E0", "#D9C8F0", "#1A1A22", "#232330", "#2E2E3E", "#3A3A4C", "#ECE8F4", "#8C8AA0"),
    "genesis": ("#2B4C8C", "#4A6DC0", "#C8313E", "#0A0F1C", "#131A2C", "#1C2540", "#242E4E", "#E4E8F4", "#7A82A0"),
    "nes":     ("#C8313E", "#E85A66", "#FFFFFF", "#1C1418", "#261B20", "#33252C", "#432E38", "#F4E8EC", "#907A82"),
    "arcade":  ("#D18B2C", "#F0AA48", "#E0309C", "#0E0E14", "#171722", "#20202E", "#2C2C3E", "#F0ECF4", "#8C88A0"),
    "gba":     ("#5C3A8F", "#8B5FBF", "#E0C8F0", "#151021", "#1F1830", "#2A2142", "#3A2F55", "#EDE4F4", "#8C82A0"),
    "n64":     ("#2B5C8C", "#4A8FD9", "#F4C430", "#0E1420", "#161E2C", "#1E2A3C", "#2A3A50", "#E4ECF4", "#7A88A0"),
}
STRIPES = {
    "ps1":     ["#E63946", "#F4C430", "#3EA55F", "#2E6DB4"],
    "ps2":     ["#1E5AA8", "#7FA8E0", "#E6EEF8", "#1E5AA8"],
    "snes":    ["#8B5FBF", "#D9C8F0", "#5F5F7A", "#8B5FBF"],
    "genesis": ["#C8313E", "#2B4C8C", "#4A6DC0", "#E4E8F4"],
    "nes":     ["#C8313E", "#FFFFFF", "#7A7A7A", "#C8313E"],
    "arcade":  ["#E0309C", "#D18B2C", "#30D0E0", "#F0ECF4"],
    "gba":     ["#5C3A8F", "#8B5FBF", "#E0C8F0", "#5C3A8F"],
    "n64":     ["#2B5C8C", "#4A8FD9", "#F4C430", "#E4ECF4"],
}
CONSOLES = [
    ("ps1", "PlayStation", "ps1.mp4"),
    ("ps2", "PlayStation 2", "ps2.mp4"),
    ("snes", "Super Nintendo", "snes.mp4"),
    ("genesis", "Sega Genesis", "genesis.mp4"),
    ("nes", "Nintendo NES", "nes.mp4"),
    ("arcade", "Arcade", "arcade.mp4"),
]

STATUSES = ["À jouer", "En cours", "Terminé", "Abandonné"]
STATUS_COLORS = {
    "À jouer":   "#7C8794",
    "En cours":  "#3EA55F",
    "Terminé":   "#2E6DB4",
    "Abandonné": "#E63946",
}

_PIXEL_FONT_LOADED = False
_PIXEL_FONT_NAME = None
def load_pixel_font():
    global _PIXEL_FONT_LOADED, _PIXEL_FONT_NAME
    if _PIXEL_FONT_LOADED:
        return _PIXEL_FONT_NAME
    path = FONTS / "PressStart2P-Regular.ttf"
    if not path.exists():
        return None
    fid = QFontDatabase.addApplicationFont(str(path))
    if fid < 0:
        return None
    families = QFontDatabase.applicationFontFamilies(fid)
    if families:
        _PIXEL_FONT_LOADED = True
        _PIXEL_FONT_NAME = families[0]
        return _PIXEL_FONT_NAME
    return None

def load_collections():
    if COL_PATH.exists():
        try:
            return json.loads(COL_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def save_collections(col):
    COL_PATH.write_text(json.dumps(col, indent=2, ensure_ascii=False), encoding="utf-8")

def col_for(col, path, create=True):
    if path not in col and create:
        col[path] = {"status": "", "rating": 0, "sessions": 0, "last_played": 0, "core": ""}
    entry = col.get(path, {})
    entry.setdefault("status", "")
    entry.setdefault("rating", 0)
    entry.setdefault("sessions", 0)
    entry.setdefault("last_played", 0)
    entry.setdefault("core", "")
    return entry

def load_playlists():
    if PLAYLISTS_PATH.exists():
        try:
            return json.loads(PLAYLISTS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def save_playlists(pl):
    PLAYLISTS_PATH.write_text(json.dumps(pl, indent=2, ensure_ascii=False), encoding="utf-8")

class SoundFx:
    def __init__(self):
        self._sounds = {}
    def play(self, name):
        pass

_SFX = None
def sfx():
    global _SFX
    if _SFX is None:
        _SFX = SoundFx()
    return _SFX

def style(key):
    a, ah, sec, dk, pn, ph, bd, tx, td = PALETTES[key]
    pixel = _PIXEL_FONT_NAME or "Segoe UI"
    return f"""
QMainWindow, QWidget {{ background: {dk}; color: {tx}; font-family: 'Segoe UI'; font-size: 13px; }}
QLabel {{ background: transparent; border: none; }}
QLabel#hero {{ color: {tx}; font-size: 22px; font-weight: 800; letter-spacing: 2px; padding: 2px 10px; font-family: '{pixel}'; }}
QLabel#sub {{ color: {td}; font-size: 12px; padding: 0 10px; }}
QLabel#ttl {{ color: {tx}; font-size: 14px; font-weight: 700; padding: 14px 8px 4px 8px; font-family: '{pixel}'; }}
QLabel#meta {{ color: {td}; font-size: 12px; padding: 0 8px; }}
QLabel#desc {{ color: {tx}; font-size: 13px; padding: 12px; line-height: 150%; }}
QPushButton {{ background: {ph}; color: {tx}; border: 1px solid {bd}; border-radius: 10px; padding: 8px 14px; font-weight: 500; }}
QPushButton:hover {{ background: {a}; border-color: {ah}; color: #FFF; }}
QPushButton#play {{ background: {a}; border: 1px solid {ah}; color: #FFF; font-size: 13px; font-weight: 800; padding: 16px 20px; letter-spacing: 1.5px; border-radius: 10px; font-family: '{pixel}'; }}
QPushButton#play:hover {{ background: {ah}; }}
QLineEdit, QComboBox {{ background: {pn}; color: {tx}; border: 1px solid {bd}; border-radius: 8px; padding: 8px 12px; }}
QLineEdit:focus, QComboBox:hover {{ border: 1px solid {a}; }}
QComboBox QAbstractItemView {{ background: {pn}; color: {tx}; selection-background-color: {a}; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: {pn}; width: 10px; border-radius: 5px; }}
QScrollBar::handle:vertical {{ background: {bd}; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {a}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QFrame#stripe {{ border: none; }}
QFrame#descbox {{ background: {dk}; border: 1px solid {bd}; border-radius: 8px; }}
QTextEdit {{ background: {dk}; color: {tx}; border: 1px solid {bd}; border-radius: 8px; padding: 8px; }}
QListWidget {{ background: {pn}; color: {tx}; border: 1px solid {bd}; border-radius: 8px; padding: 6px; }}
QListWidget::item {{ padding: 6px 8px; border-radius: 4px; }}
QListWidget::item:selected {{ background: {a}; color: #FFF; }}
QCheckBox {{ color: {tx}; padding: 4px; }}
QSlider::groove:horizontal {{ height: 6px; background: {bd}; border-radius: 3px; }}
QSlider::handle:horizontal {{ background: {a}; width: 16px; margin: -5px 0; border-radius: 8px; }}
"""

def load_json(p, default):
    if p.exists():
        try:
            j = json.loads(p.read_text(encoding="utf-8"))
            for k, v in default.items():
                j.setdefault(k, v)
            return j
        except Exception:
            pass
    p.write_text(json.dumps(default, indent=2, ensure_ascii=False), encoding="utf-8")
    return dict(default)

def save_json(p, j):
    p.write_text(json.dumps(j, indent=2, ensure_ascii=False), encoding="utf-8")

def get_core_for(console_key, cfg):
    cores = cfg.get("cores", {})
    if console_key in cores and cores[console_key]:
        return cores[console_key]
    s = cfg.get("settings", {})
    return s.get("core_path", "")

def get_roms_dir_for(console_key, cfg):
    base = Path(cfg.get("roms_dir", str(ROMS)))
    return base / console_key

# ---------- scan / fuzzy ----------
REG_RE = re.compile(r"\((USA|Europe|Japan|World|France|Germany|Spain|Italy|E|U|J|UE|JU|En,Fr,Es)\)", re.I)
DISC_RE = re.compile(r"\(Disc\s*(\d+)\)", re.I)
REV_RE = re.compile(r"\((Rev\s*[\d.]+|V[\d.]+)\)", re.I)

def clean(fn):
    s = Path(fn).stem
    out = []
    d = 0
    for ch in s:
        if ch == "(":
            d += 1
        elif ch == ")":
            if d > 0:
                d -= 1
        elif d == 0:
            out.append(ch)
    return " ".join("".join(out).strip(" -_").split()) or s

def region(fn):
    m = REG_RE.search(fn)
    if not m:
        return "—"
    r = m.group(1).upper()
    if r in ("USA", "U"):
        return "USA"
    if r in ("JAPAN", "J"):
        return "JAP"
    if r in ("E", "EUROPE", "FRANCE", "GERMANY", "SPAIN", "ITALY", "UE"):
        return "EUR"
    return r

def disc_num(fn):
    m = DISC_RE.search(fn)
    return int(m.group(1)) if m else 0

def revision(fn):
    m = REV_RE.search(fn)
    return m.group(1) if m else ""

def normalize(s):
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "", s)

def fuzzy_score(q, t):
    nq, nt = normalize(q), normalize(t)
    if not nq:
        return 1.0
    if nq in nt:
        return 1.0
    return SequenceMatcher(None, nq, nt).ratio()

def scan(console_dir, console_key=None):
    if not console_dir.exists():
        return []
    exts = CONSOLE_EXTS.get(console_key, EXTS) if console_key else EXTS
    found = {}
    for p in console_dir.rglob("*"):
        if not p.is_file():
            continue
        e = p.suffix.lower()
        if e == ".cue":
            found.setdefault(p.stem, p)
            continue
        if e in exts:
            found[p.stem] = p
    games = []
    for p in found.values():
        try:
            sz = p.stat().st_size
        except Exception:
            sz = 0
        games.append({
            "title": clean(p.name),
            "raw": p.name,
            "region": region(p.name),
            "size": sz,
            "path": str(p),
            "disc": disc_num(p.name),
            "rev": revision(p.name),
        })
    games.sort(key=lambda x: (x["title"].lower(), x["disc"]))
    return games

def cover(cd, t):
    if not cd.exists():
        return None
    w = normalize(t)
    for p in cd.iterdir():
        if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"} and normalize(p.stem) == w:
            return p
    return None

def description(title):
    if not DESCS.exists():
        return None
    target = normalize(title)
    for p in DESCS.iterdir():
        if p.is_file() and p.suffix.lower() == ".txt" and normalize(p.stem) == target:
            try:
                return p.read_text(encoding="utf-8").strip()
            except Exception:
                return None
    return None

def write_description(title, text):
    DESCS.mkdir(exist_ok=True)
    p = DESCS / f"{title}.txt"
    p.write_text(text, encoding="utf-8")
    return p

def gameplay_video(title):
    if not GAMEPLAY.exists():
        return None
    target = normalize(title)
    for p in GAMEPLAY.iterdir():
        if p.suffix.lower() in {".mp4", ".webm", ".mkv", ".mov"} and normalize(p.stem) == target:
            return p
    return None

def hsize(n):
    if n <= 0:
        return "—"
    for u in ("o", "Ko", "Mo", "Go"):
        if n < 1024:
            return f"{n:.0f} {u}"
        n /= 1024
    return f"{n:.1f} To"

def htime(sec):
    if sec < 60:
        return f"{sec}s"
    if sec < 3600:
        return f"{sec // 60}min"
    return f"{sec // 3600}h{(sec % 3600) // 60:02d}"

# ---------- fond animé du splash ----------
class AnimatedBg(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.t = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(33)
        self.lower()
        self._cur = self._palette_colors("ps1")
        self._target = self._palette_colors("ps1")
        self._blend = 1.0
        self._rebuild_dots("ps1")

    def _palette_colors(self, key):
        return (QColor(PALETTES[key][3]), QColor(PALETTES[key][4]), QColor(PALETTES[key][5]))

    def _rebuild_dots(self, key):
        ah = QColor(PALETTES[key][1])
        self._dots = []
        for i in range(10):
            c = QColor(ah)
            c.setAlpha(28 + (i % 3) * 14)
            self._dots.append((c, 3 + (i % 4)))

    def set_console(self, key):
        self._cur = self._blend_colors(self._cur, self._target, self._blend)
        self._target = self._palette_colors(key)
        self._blend = 0.0
        self._rebuild_dots(key)

    def _blend_colors(self, a, b, t):
        return tuple(self._lerp(c1, c2, t) for c1, c2 in zip(a, b))

    def _lerp(self, c1, c2, t):
        r = int(c1.red() * (1 - t) + c2.red() * t)
        g = int(c1.green() * (1 - t) + c2.green() * t)
        b = int(c1.blue() * (1 - t) + c2.blue() * t)
        return QColor(r, g, b)

    def _tick(self):
        self.t += 0.007
        if self.t > 1.0:
            self.t = 0.0
        if self._blend < 1.0:
            self._blend += 0.06
            if self._blend > 1.0:
                self._blend = 1.0
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        c1, c2, c3 = self._blend_colors(self._cur, self._target, self._blend)
        g = QLinearGradient(0, 0, w, h)
        s = self.t
        g.setColorAt(0.0, c1)
        g.setColorAt(0.45 + 0.1 * s, c2)
        g.setColorAt(1.0, c3)
        p.fillRect(self.rect(), QBrush(g))
        p.setPen(Qt.PenStyle.NoPen)
        shift = int(self.t * 300)
        for i, (col, size) in enumerate(self._dots):
            x = (i * 173 + shift) % max(1, w)
            y = (i * 97 + shift // 2) % max(1, h)
            p.setBrush(col)
            p.drawEllipse(x, y, size, size)

# ---------- filigrane ----------
class WatermarkBg(QWidget):
    def __init__(self, parent=None, accent="#2E6DB4"):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._accent = QColor(accent)
        self._accent.setAlpha(16)
        self._glyphs = ["△", "○", "✕", "□"]
        self._grid_size = 130

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(self._accent)
        f = p.font()
        f.setPointSize(34)
        f.setFamily("Segoe UI Symbol")
        p.setFont(f)
        w, h = self.width(), self.height()
        idx = 0
        y = 40
        while y < h + self._grid_size:
            x = 40
            while x < w + self._grid_size:
                p.drawText(x, y, self._glyphs[idx % 4])
                idx += 1
                x += self._grid_size
            y += self._grid_size

# ---------- gameplay bg (placeholder) ----------
class GameplayBg(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setVisible(False)
        self.player = None
    def set_source(self, path, target_opacity=None):
        pass
    def stop(self):
        pass

# ---------- tuile de console (splash) ----------
class ConsoleTile(QFrame):
    clicked = pyqtSignal(str)
    hovered = pyqtSignal(str)
    def __init__(self, key, name):
        super().__init__()
        self.key = key
        a, ah, sec, dk, pn, ph, bd, tx, td = PALETTES[key]
        self.setFixedSize(260, 300)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._base = f"ConsoleTile {{ background: {pn}; border: 2px solid {bd}; border-radius: 14px; }}"
        self._hover = f"ConsoleTile {{ background: {ph}; border: 2px solid {a}; border-radius: 14px; }}"
        self.setStyleSheet(self._base)
        l = QVBoxLayout(self)
        l.setContentsMargins(16, 20, 16, 16)
        l.setSpacing(12)
        img = QLabel()
        img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img.setFixedHeight(180)
        img.setStyleSheet("background: transparent; border: none;")
        p = CONS_IMG / f"{key}.png"
        if p.exists():
            img.setPixmap(QPixmap(str(p)).scaled(220, 170, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            img.setText(f"[{name}]")
            img.setStyleSheet(f"background: transparent; border: none; color: {a}; font-size: 16px; font-weight: 800;")
        l.addWidget(img, 1)
        lab = QLabel(name)
        lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lab.setStyleSheet(f"color: {tx}; font-size: 15px; font-weight: 700; background: transparent; letter-spacing: 1px;")
        l.addWidget(lab)
        bar = QFrame()
        bar.setFixedHeight(4)
        bar.setStyleSheet(f"background: {a}; border-radius: 2px;")
        l.addWidget(bar)
    def enterEvent(self, e):
        self.setStyleSheet(self._hover)
        self.move(self.x(), self.y() - 4)
        w = self.window()
        bg = getattr(w, "bg", None)
        if bg is not None:
            bg.set_console(self.key)
        self.hovered.emit(self.key)
    def leaveEvent(self, e):
        self.setStyleSheet(self._base)
        self.move(self.x(), self.y() + 4)
    def mousePressEvent(self, e):
        sfx().play("launch")
        self.clicked.emit(self.key)

# ---------- splash ----------
class Splash(QWidget):
    picked = pyqtSignal(str)
    def __init__(self):
        super().__init__()
        self.bg = AnimatedBg(self)
        self.bg.resize(self.size())
        self.bg.stackUnder(self)
        r = QVBoxLayout(self)
        r.setContentsMargins(60, 50, 60, 30)
        r.setSpacing(16)
        h = QLabel("Choisis ta console")
        h.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h.setStyleSheet(f"color: {PALETTES['ps1'][7]}; font-size: 30px; font-weight: 800; letter-spacing: 3px; background: transparent; border: none; font-family: '{_PIXEL_FONT_NAME or 'Segoe UI'}';")
        r.addWidget(h)
        r.addSpacing(30)
        g = QGridLayout()
        g.setHorizontalSpacing(26)
        g.setVerticalSpacing(26)
        g.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for i, (k, n, intro) in enumerate(CONSOLES):
            t = ConsoleTile(k, n)
            t.clicked.connect(self.picked.emit)
            g.addWidget(t, i // 3, i % 3)
        r.addLayout(g, 1)
    def resizeEvent(self, e):
        self.bg.resize(self.size())

# ---------- intro ----------
class Intro(QWidget):
    done = pyqtSignal()
    def __init__(self, video_path, volume=0.6):
        super().__init__()
        self.setStyleSheet("background: black;")
        self._finished = False
        l = QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        if video_path and Path(video_path).exists() and HAS_MM:
            self.video = QVideoWidget()
            self.video.setStyleSheet("background: black;")
            l.addWidget(self.video)
            self.pl = QMediaPlayer()
            self.au = QAudioOutput()
            self.au.setVolume(volume)
            self.pl.setAudioOutput(self.au)
            self.pl.setVideoOutput(self.video)
            self.pl.mediaStatusChanged.connect(self._on_status)
            self.pl.mediaStatusChanged.connect(self._maybe_play)
            self.pl.errorOccurred.connect(self._on_error)
            self.pl.setSource(QUrl.fromLocalFile(str(video_path)))
        else:
            self.video = None
            self.pl = None
            w = QWidget()
            w.setStyleSheet("background: black;")
            wl = QVBoxLayout(w)
            wl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lg = QLabel("PS")
            lg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lg.setStyleSheet("color: white; font-size: 200px; font-weight: 900; letter-spacing: 14px;")
            wl.addWidget(lg)
            sub = QLabel("Sony Computer Entertainment")
            sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sub.setStyleSheet("color: #AAA; font-size: 16px; letter-spacing: 8px; padding-top: 24px;")
            wl.addWidget(sub)
            l.addWidget(w, 1)
            o1 = QGraphicsOpacityEffect(lg)
            lg.setGraphicsEffect(o1)
            a1 = QPropertyAnimation(o1, b"opacity")
            a1.setDuration(1200)
            a1.setStartValue(0.0)
            a1.setEndValue(1.0)
            a1.setEasingCurve(QEasingCurve.Type.InOutQuad)
            o2 = QGraphicsOpacityEffect(sub)
            sub.setGraphicsEffect(o2)
            a2 = QPropertyAnimation(o2, b"opacity")
            a2.setDuration(900)
            a2.setStartValue(0.0)
            a2.setEndValue(1.0)
            a1.finished.connect(a2.start)
            a1.start()
            QTimer.singleShot(3200, self._finish)
    def _maybe_play(self, status):
        if self.pl is not None and status == QMediaPlayer.MediaStatus.LoadedMedia:
            self.pl.play()
    def _on_status(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._finish()
    def _on_error(self, err, err_str):
        if self.pl is not None and self.pl.mediaStatus() == QMediaPlayer.MediaStatus.InvalidMedia:
            QTimer.singleShot(1500, self._finish)
    def _finish(self):
        if self._finished:
            return
        self._finished = True
        self.done.emit()
    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self._finish()
        else:
            super().keyPressEvent(e)
    def mousePressEvent(self, e):
        e.ignore()

# ---------- éditeur de description ----------
class DescEditor(QDialog):
    def __init__(self, parent, title, current):
        super().__init__(parent)
        self.setWindowTitle(f"Description — {title}")
        self.resize(600, 400)
        if parent is not None:
            self.setStyleSheet(parent.styleSheet())
        l = QVBoxLayout(self)
        lbl = QLabel(f"Description de : {title}")
        lbl.setStyleSheet("font-size: 14px; font-weight: 600; padding: 4px;")
        l.addWidget(lbl)
        self.edit = QTextEdit()
        self.edit.setPlainText(current or "")
        l.addWidget(self.edit, 1)
        btns = QHBoxLayout()
        cancel = QPushButton("Annuler")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Sauvegarder")
        save.setObjectName("play")
        save.clicked.connect(self.accept)
        btns.addStretch(1)
        btns.addWidget(cancel)
        btns.addWidget(save)
        l.addLayout(btns)
    def result_text(self):
        return self.edit.toPlainText()

# ---------- tuile de jeu (avec ombre au survol) ----------
class GameTile(QFrame):
    clicked = pyqtSignal(dict)
    rclick = pyqtSignal(dict)
    hovered = pyqtSignal(dict)
    unhovered = pyqtSignal(dict)
    def __init__(self, g, ck, cv, fav, delay_ms=0, status="", rating=0,
                 tile_size=220, show_status=True, show_rating=True):
        super().__init__()
        self.g = g
        a, ah, sec, dk, pn, ph, bd, tx, td = PALETTES[ck]
        self._accent = a
        h_tile = int(tile_size * 1.42)
        self.setFixedSize(tile_size, h_tile)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._base = f"GameTile {{ background: {pn}; border: 2px solid {bd}; border-radius: 12px; }}"
        self._hover = f"GameTile {{ background: {ph}; border: 2px solid {a}; border-radius: 12px; }}"
        self.setStyleSheet(self._base)

        # Ombre portée sur la tuile elle-même
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(0)
        self._shadow.setColor(QColor(0, 0, 0, 0))
        self._shadow.setOffset(0, 0)
        self.setGraphicsEffect(self._shadow)

        # Fade-in sur le contenu interne
        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(0.0)
        self._anim = QPropertyAnimation(self._effect, b"opacity")
        self._anim.setDuration(220)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        if delay_ms > 0:
            QTimer.singleShot(delay_ms, self._anim.start)
        else:
            self._anim.start()

        self._hover_anim = QPropertyAnimation(self, b"pos")
        self._hover_anim.setDuration(110)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._is_hovered = False
        self._base_y = None
        pixel = _PIXEL_FONT_NAME or "Segoe UI"
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(6)
        img_size = tile_size - 25
        self._cover_wrap = QFrame()
        self._cover_wrap.setFixedHeight(img_size)
        self._cover_wrap.setStyleSheet(self._cover_style(hover=False))
        cw = QVBoxLayout(self._cover_wrap)
        cw.setContentsMargins(0, 0, 0, 0)
        cw.setSpacing(0)
        img = QLabel()
        img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if cv:
            img.setPixmap(QPixmap(str(cv)).scaled(img_size, img_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            img.setText(g["title"][:40])
            img.setWordWrap(True)
            img.setStyleSheet(f"background: {dk}; color: {td}; font-family: '{pixel}'; font-size: 9px; padding: 8px; border: none;")
        cw.addWidget(img)
        lay.addWidget(self._cover_wrap)
        # Le fade-in s'applique au contenu (l'ombre reste sur la tuile)
        self._cover_wrap.setGraphicsEffect(self._effect)
        t = QLabel(g["title"])
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.setWordWrap(True)
        t.setStyleSheet(f"color: {tx}; font-family: '{pixel}'; font-size: 8px; font-weight: 600; background: transparent;")
        lay.addWidget(t)
        parts = [g["region"], hsize(g["size"])]
        if g.get("disc"):
            parts.insert(1, f"D{g['disc']}")
        m = QLabel("  ·  ".join(parts))
        m.setAlignment(Qt.AlignmentFlag.AlignCenter)
        m.setStyleSheet(f"color: {td}; font-family: '{pixel}'; font-size: 7px; background: transparent;")
        lay.addWidget(m)
        if fav:
            s = QLabel("★")
            s.setAlignment(Qt.AlignmentFlag.AlignCenter)
            s.setStyleSheet(f"color: {sec}; font-size: 14px;")
            lay.addWidget(s)
        if status and show_status:
            badge = QLabel(status)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            color = STATUS_COLORS.get(status, "#7C8794")
            badge.setStyleSheet(f"background: {color}; color: #FFF; font-family: '{pixel}'; font-size: 7px; font-weight: 700; border-radius: 6px; padding: 4px 6px;")
            lay.addWidget(badge)
        if rating > 0 and show_rating:
            stars = "★" * rating + "☆" * (5 - rating)
            rate = QLabel(stars)
            rate.setAlignment(Qt.AlignmentFlag.AlignCenter)
            rate.setStyleSheet("color: #F4C430; font-size: 12px; letter-spacing: 1px;")
            lay.addWidget(rate)
    def _cover_style(self, hover=False):
        a = self._accent if hover else "#2A313B"
        top_alpha = 60 if hover else 32
        mid_alpha = 10 if hover else 20
        bot_alpha = 30 if hover else 45
        return f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255,255,255,{top_alpha}),
                    stop:0.08 rgba(255,255,255,10),
                    stop:0.5 rgba(0,0,0,{mid_alpha}),
                    stop:1 rgba(0,0,0,{bot_alpha}));
                border: 1px solid {a};
                border-radius: 6px;
            }}
        """
    def enterEvent(self, e):
        if self._is_hovered:
            return
        self._is_hovered = True
        self.setStyleSheet(self._hover)
        self._cover_wrap.setStyleSheet(self._cover_style(hover=True))
        if self._base_y is None:
            self._base_y = self.y()
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self.pos())
        self._hover_anim.setEndValue(self.pos().__class__(self.x(), self._base_y - 4))
        self._hover_anim.start()
        self._shadow.setBlurRadius(24)
        self._shadow.setColor(QColor(0, 0, 0, 130))
        self._shadow.setOffset(0, 6)
        self.hovered.emit(self.g)
    def leaveEvent(self, e):
        if not self._is_hovered:
            return
        self._is_hovered = False
        self.setStyleSheet(self._base)
        self._cover_wrap.setStyleSheet(self._cover_style(hover=False))
        if self._base_y is None:
            return
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self.pos())
        self._hover_anim.setEndValue(self.pos().__class__(self.x(), self._base_y))
        self._hover_anim.start()
        self._shadow.setBlurRadius(0)
        self._shadow.setColor(QColor(0, 0, 0, 0))
        self._shadow.setOffset(0, 0)
        self.unhovered.emit(self.g)
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.RightButton:
            self.rclick.emit(self.g)
        else:
            sfx().play("click")
            self.clicked.emit(self.g)

# ---------- stats ----------
class StatsWindow(QDialog):
    def __init__(self, parent, cfg, collections, games_all):
        super().__init__(parent)
        self.setWindowTitle("Statistiques — Lunar")
        self.resize(560, 600)
        if parent is not None:
            self.setStyleSheet(parent.styleSheet())
        l = QVBoxLayout(self)
        l.setContentsMargins(20, 20, 20, 20)
        l.setSpacing(10)
        title = QLabel("Statistiques globales")
        title.setStyleSheet("font-size: 18px; font-weight: 800; padding: 4px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.addWidget(title)
        l.addSpacing(6)
        playtime = cfg.get("playtime", {})
        recent = cfg.get("recent", [])
        favorites = cfg.get("favorites", [])
        total_time = sum(playtime.values())
        total_sessions = sum(c.get("sessions", 0) for c in collections.values())
        total_games = len(games_all)
        def row(label, value):
            h = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setStyleSheet("font-size: 13px; color: #AAA;")
            val = QLabel(str(value))
            val.setStyleSheet("font-size: 13px; font-weight: 700;")
            val.setAlignment(Qt.AlignmentFlag.AlignRight)
            h.addWidget(lbl)
            h.addStretch(1)
            h.addWidget(val)
            l.addLayout(h)
        row("Jeux dans la bibliothèque", total_games)
        row("Temps de jeu total", htime(total_time) if total_time else "—")
        row("Sessions lancées", total_sessions)
        row("Favoris", len(favorites))
        row("Récemment joués", len(recent))
        l.addSpacing(8)
        sep = QLabel("Statuts de collection")
        sep.setStyleSheet("font-size: 14px; font-weight: 700; padding-top: 6px; color: #FFF;")
        l.addWidget(sep)
        status_counts = {s: 0 for s in STATUSES}
        for c in collections.values():
            s = c.get("status", "")
            if s in status_counts:
                status_counts[s] += 1
        for s in STATUSES:
            row(s, status_counts.get(s, 0))
        l.addSpacing(8)
        sep2 = QLabel("Top 5 — jeux les plus joués")
        sep2.setStyleSheet("font-size: 14px; font-weight: 700; padding-top: 6px; color: #FFF;")
        l.addWidget(sep2)
        top = sorted(playtime.items(), key=lambda x: -x[1])[:5]
        if not top:
            empty = QLabel("Aucun temps de jeu enregistré.")
            empty.setStyleSheet("color: #AAA; font-size: 12px; padding: 4px;")
            l.addWidget(empty)
        else:
            for path, secs in top:
                name = Path(path).stem
                row(name[:44], htime(secs))
        l.addStretch(1)
        close = QPushButton("Fermer")
        close.setObjectName("play")
        close.clicked.connect(self.accept)
        l.addWidget(close)

# ---------- playlists ----------
class PlaylistPicker(QDialog):
    def __init__(self, parent, game, playlists):
        super().__init__(parent)
        self.setWindowTitle(f"Playlists — {game['title']}")
        self.resize(420, 460)
        if parent is not None:
            self.setStyleSheet(parent.styleSheet())
        self.game = game
        self.playlists = playlists
        self.result = None
        l = QVBoxLayout(self)
        l.setContentsMargins(16, 16, 16, 16)
        l.setSpacing(8)
        t = QLabel(f"Playlists pour :\n{game['title']}")
        t.setWordWrap(True)
        t.setStyleSheet("font-size: 13px; font-weight: 600; padding-bottom: 6px;")
        l.addWidget(t)
        self.listw = QListWidget()
        self._refresh()
        l.addWidget(self.listw, 1)
        btns = QHBoxLayout()
        b_new = QPushButton("+ Nouvelle")
        b_new.clicked.connect(self._new)
        b_del = QPushButton("Supprimer")
        b_del.clicked.connect(self._del)
        b_close = QPushButton("Fermer")
        b_close.setObjectName("play")
        b_close.clicked.connect(self.accept)
        btns.addWidget(b_new)
        btns.addWidget(b_del)
        btns.addStretch(1)
        btns.addWidget(b_close)
        l.addLayout(btns)
    def _refresh(self):
        self.listw.clear()
        for name, paths in self.playlists.items():
            in_it = self.game["path"] in paths
            item = QListWidgetItem(f"{'[X]' if in_it else '[ ]'}  {name}  ({len(paths)})")
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.listw.addItem(item)
        self.listw.itemClicked.connect(self._toggle)
    def _toggle(self, item):
        name = item.data(Qt.ItemDataRole.UserRole)
        if not name:
            return
        paths = self.playlists.get(name, [])
        if self.game["path"] in paths:
            paths.remove(self.game["path"])
        else:
            paths.append(self.game["path"])
        self.playlists[name] = paths
        save_playlists(self.playlists)
        self.result = self.playlists
        self._refresh()
    def _new(self):
        name, ok = QInputDialog.getText(self, "Nouvelle playlist", "Nom de la playlist :")
        if ok and name.strip():
            name = name.strip()
            if name not in self.playlists:
                self.playlists[name] = []
            self.playlists[name].append(self.game["path"])
            save_playlists(self.playlists)
            self.result = self.playlists
            self._refresh()
    def _del(self):
        item = self.listw.currentItem()
        if not item:
            return
        name = item.data(Qt.ItemDataRole.UserRole)
        if not name:
            return
        if QMessageBox.question(self, "Supprimer", f"Supprimer la playlist {name} ?") == QMessageBox.StandardButton.Yes:
            self.playlists.pop(name, None)
            save_playlists(self.playlists)
            self.result = self.playlists
            self._refresh()

# ---------- import ----------
class ImportDialog(QDialog):
    def __init__(self, parent, console_key):
        super().__init__(parent)
        self.setWindowTitle("Importer des jeux")
        self.resize(640, 520)
        if parent is not None:
            self.setStyleSheet(parent.styleSheet())
        self.console_key = console_key
        self.files_to_add = []
        ext_set = CONSOLE_EXTS.get(console_key, EXTS)
        ext_str = " ".join(f"*{e}" for e in sorted(ext_set))
        l = QVBoxLayout(self)
        l.setContentsMargins(16, 16, 16, 16)
        l.setSpacing(10)
        title = QLabel("Importer des ROMs")
        title.setStyleSheet("font-size: 18px; font-weight: 800; padding: 4px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.addWidget(title)
        subtitle = QLabel(f"Les fichiers seront copiés dans :\nE:\\ps1-launcher\\roms\\{console_key}\\")
        subtitle.setStyleSheet("font-size: 12px; color: #AAA; padding: 4px;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.addWidget(subtitle)
        row = QHBoxLayout()
        self.btn_pick = QPushButton("Choisir des fichiers…")
        self.btn_pick.clicked.connect(self._pick_files)
        self.btn_pick_folder = QPushButton("Choisir un dossier…")
        self.btn_pick_folder.clicked.connect(self._pick_folder)
        row.addWidget(self.btn_pick)
        row.addWidget(self.btn_pick_folder)
        l.addLayout(row)
        self.listw = QListWidget()
        l.addWidget(self.listw, 1)
        self.summary = QLabel("Aucun fichier sélectionné.")
        self.summary.setStyleSheet("color: #AAA; font-size: 12px; padding: 4px;")
        l.addWidget(self.summary)
        btns = QHBoxLayout()
        b_clear = QPushButton("Vider la liste")
        b_clear.clicked.connect(self._clear)
        b_cancel = QPushButton("Annuler")
        b_cancel.clicked.connect(self.reject)
        b_import = QPushButton("Importer")
        b_import.setObjectName("play")
        b_import.clicked.connect(self._do_import)
        btns.addWidget(b_clear)
        btns.addStretch(1)
        btns.addWidget(b_cancel)
        btns.addWidget(b_import)
        l.addLayout(btns)
        self._ext_set = ext_set
        self._ext_str = ext_str
    def _add_paths(self, paths):
        for p in paths:
            p = Path(p)
            if p.suffix.lower() in self._ext_set and p not in self.files_to_add:
                self.files_to_add.append(p)
        self._refresh()
    def _refresh(self):
        self.listw.clear()
        total = 0
        for p in self.files_to_add:
            try:
                sz = p.stat().st_size
                total += sz
            except Exception:
                sz = 0
            item = QListWidgetItem(f"{p.name}    ({hsize(sz)})")
            item.setData(Qt.ItemDataRole.UserRole, str(p))
            self.listw.addItem(item)
        n = len(self.files_to_add)
        if n == 0:
            self.summary.setText("Aucun fichier sélectionné.")
        else:
            self.summary.setText(f"{n} fichier(s)  ·  {hsize(total)} au total")
    def _pick_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Choisir des ROMs", str(BASE),
            f"ROMs ({self._ext_str});;Tous les fichiers (*)"
        )
        if files:
            self._add_paths(files)
    def _pick_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Choisir un dossier", str(BASE))
        if d:
            found = []
            for p in Path(d).rglob("*"):
                if p.is_file() and p.suffix.lower() in self._ext_set:
                    found.append(p)
            self._add_paths(found)
    def _clear(self):
        self.files_to_add = []
        self._refresh()
    def _do_import(self):
        if not self.files_to_add:
            QMessageBox.information(self, "Rien à importer", "Ajoute au moins un fichier.")
            return
        dest_dir = Path(ROMS) / self.console_key
        dest_dir.mkdir(parents=True, exist_ok=True)
        ok = 0
        skipped = 0
        for src in self.files_to_add:
            dst = dest_dir / src.name
            if dst.exists():
                skipped += 1
                continue
            try:
                shutil.copy2(src, dst)
                ok += 1
            except Exception as e:
                print(f"[import] erreur copie {src} : {e}")
        QMessageBox.information(
            self, "Import terminé",
            f"{ok} fichier(s) copié(s).\n{skipped} déjà présent(s), ignoré(s)."
        )
        self.accept()

# ---------- settings ----------
DEFAULT_SETTINGS = {
    "intro_volume": 0.6,
    "show_status_badges": True,
    "show_ratings": True,
    "tile_size": "medium",
    "animated_bg": True,
    "confirm_quit": True,
    "retroarch_path": r"E:\ps1-launcher\RetroArch\retroarch.exe",
    "core_path": r"E:\ps1-launcher\RetroArch\cores\swanstation_libretro.dll",
}
def load_settings(cfg):
    s = cfg.setdefault("settings", {})
    for k, v in DEFAULT_SETTINGS.items():
        s.setdefault(k, v)
    return s
def save_settings(cfg):
    save_json(CFG_PATH, cfg)

class SettingsDialog(QDialog):
    def __init__(self, parent, cfg):
        super().__init__(parent)
        self.setWindowTitle("Paramètres — Lunar")
        self.resize(560, 620)
        if parent is not None:
            self.setStyleSheet(parent.styleSheet())
        self.cfg = cfg
        self.s = load_settings(cfg)
        l = QVBoxLayout(self)
        l.setContentsMargins(20, 20, 20, 20)
        l.setSpacing(12)
        title = QLabel("Paramètres")
        title.setStyleSheet("font-size: 18px; font-weight: 800; padding: 4px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.addWidget(title)
        l.addWidget(self._section("Audio"))
        self.slider_vol = QSlider(Qt.Orientation.Horizontal)
        self.slider_vol.setRange(0, 100)
        self.slider_vol.setValue(int(self.s["intro_volume"] * 100))
        self.vol_label = QLabel(f"{self.slider_vol.value()}%")
        self.vol_label.setStyleSheet("font-weight: 700; min-width: 40px;")
        self.slider_vol.valueChanged.connect(lambda v: self.vol_label.setText(f"{v}%"))
        h_vol = QHBoxLayout()
        h_vol.addWidget(QLabel("Volume des intros"))
        h_vol.addWidget(self.slider_vol, 1)
        h_vol.addWidget(self.vol_label)
        l.addLayout(h_vol)
        l.addWidget(self._section("Affichage"))
        self.cb_badges = QCheckBox("Afficher les badges de statut sur les tuiles")
        self.cb_badges.setChecked(self.s["show_status_badges"])
        l.addWidget(self.cb_badges)
        self.cb_ratings = QCheckBox("Afficher les étoiles de note sur les tuiles")
        self.cb_ratings.setChecked(self.s["show_ratings"])
        l.addWidget(self.cb_ratings)
        self.cb_bg = QCheckBox("Fond animé")
        self.cb_bg.setChecked(self.s["animated_bg"])
        l.addWidget(self.cb_bg)
        h_size = QHBoxLayout()
        h_size.addWidget(QLabel("Taille des tuiles"))
        self.cmb_size = QComboBox()
        self.cmb_size.addItems(["Petit", "Moyen", "Grand"])
        idx = {"small": 0, "medium": 1, "large": 2}.get(self.s["tile_size"], 1)
        self.cmb_size.setCurrentIndex(idx)
        h_size.addWidget(self.cmb_size, 1)
        l.addLayout(h_size)
        l.addWidget(self._section("Comportement"))
        self.cb_quit = QCheckBox("Demander confirmation avant de quitter")
        self.cb_quit.setChecked(self.s["confirm_quit"])
        l.addWidget(self.cb_quit)
        l.addWidget(self._section("RetroArch"))
        h_ra = QHBoxLayout()
        h_ra.addWidget(QLabel("Chemin retroarch.exe"))
        self.le_ra = QLineEdit(self.s["retroarch_path"])
        h_ra.addWidget(self.le_ra, 1)
        b_ra = QPushButton("Parcourir…")
        b_ra.clicked.connect(self._pick_ra)
        h_ra.addWidget(b_ra)
        l.addLayout(h_ra)
        h_core = QHBoxLayout()
        h_core.addWidget(QLabel("Core PS1 par défaut"))
        self.le_core = QLineEdit(self.s["core_path"])
        h_core.addWidget(self.le_core, 1)
        b_core = QPushButton("Parcourir…")
        b_core.clicked.connect(self._pick_core)
        h_core.addWidget(b_core)
        l.addLayout(h_core)
        l.addWidget(self._section("Configuration"))
        h_cfg = QHBoxLayout()
        b_reset = QPushButton("Réinitialiser")
        b_reset.clicked.connect(self._reset)
        b_export = QPushButton("Exporter")
        b_export.clicked.connect(self._export)
        b_import = QPushButton("Importer")
        b_import.clicked.connect(self._import)
        h_cfg.addWidget(b_reset)
        h_cfg.addWidget(b_export)
        h_cfg.addWidget(b_import)
        h_cfg.addStretch(1)
        l.addLayout(h_cfg)
        l.addStretch(1)
        btns = QHBoxLayout()
        b_cancel = QPushButton("Annuler")
        b_cancel.clicked.connect(self.reject)
        b_save = QPushButton("Sauvegarder")
        b_save.setObjectName("play")
        b_save.clicked.connect(self._save_and_close)
        btns.addStretch(1)
        btns.addWidget(b_cancel)
        btns.addWidget(b_save)
        l.addLayout(btns)
    def _section(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet("font-size: 14px; font-weight: 700; padding-top: 8px; color: #FFF;")
        return lbl
    def _pick_ra(self):
        p, _ = QFileDialog.getOpenFileName(self, "retroarch.exe", self.le_ra.text())
        if p:
            self.le_ra.setText(p)
    def _pick_core(self):
        p, _ = QFileDialog.getOpenFileName(self, "core .dll", self.le_core.text(), "Libretro core (*.dll);;Tous les fichiers (*)")
        if p:
            self.le_core.setText(p)
    def _reset(self):
        if QMessageBox.question(self, "Réinitialiser", "Remettre tous les réglages par défaut ?") == QMessageBox.StandardButton.Yes:
            self.slider_vol.setValue(int(DEFAULT_SETTINGS["intro_volume"] * 100))
            self.cb_badges.setChecked(DEFAULT_SETTINGS["show_status_badges"])
            self.cb_ratings.setChecked(DEFAULT_SETTINGS["show_ratings"])
            self.cb_bg.setChecked(DEFAULT_SETTINGS["animated_bg"])
            self.cmb_size.setCurrentIndex(1)
            self.cb_quit.setChecked(DEFAULT_SETTINGS["confirm_quit"])
            self.le_ra.setText(DEFAULT_SETTINGS["retroarch_path"])
            self.le_core.setText(DEFAULT_SETTINGS["core_path"])
    def _export(self):
        p, _ = QFileDialog.getSaveFileName(self, "Exporter la config", str(BASE / f"config_export_{int(time.time())}.json"), "JSON (*.json)")
        if p:
            save_json(Path(p), self.cfg)
    def _import(self):
        p, _ = QFileDialog.getOpenFileName(self, "Importer une config", str(BASE), "JSON (*.json)")
        if p:
            try:
                j = json.loads(Path(p).read_text(encoding="utf-8"))
                self.cfg.clear()
                self.cfg.update(j)
                load_settings(self.cfg)
                QMessageBox.information(self, "Import OK", "Config importée. Redémarre le launcher pour tout appliquer.")
            except Exception as e:
                QMessageBox.critical(self, "Erreur import", str(e))
    def _save_and_close(self):
        s = self.s
        s["intro_volume"] = self.slider_vol.value() / 100.0
        s["show_status_badges"] = self.cb_badges.isChecked()
        s["show_ratings"] = self.cb_ratings.isChecked()
        s["animated_bg"] = self.cb_bg.isChecked()
        s["tile_size"] = ["small", "medium", "large"][self.cmb_size.currentIndex()]
        s["confirm_quit"] = self.cb_quit.isChecked()
        s["retroarch_path"] = self.le_ra.text().strip()
        s["core_path"] = self.le_core.text().strip()
        save_settings(self.cfg)
        self.accept()

# ---------- backup saves ----------
SAVES_DIR = BASE / "RetroArch" / "saves"
SAVES_BACKUP = BASE / "saves_backup"

def backup_save_for(game_path, keep=5):
    try:
        rom_path = Path(game_path)
        srm_name = rom_path.stem + ".srm"
        srm_path = None
        for sub in SAVES_DIR.rglob(srm_name):
            srm_path = sub
            break
        if srm_path is None or not srm_path.exists():
            return None
        title = clean(rom_path.name)
        dest_dir = SAVES_BACKUP / title
        dest_dir.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y-%m-%d_%H-%M-%S")
        dest = dest_dir / f"{ts}.srm"
        shutil.copy2(srm_path, dest)
        copies = sorted(dest_dir.glob("*.srm"), key=lambda p: p.name, reverse=True)
        for old in copies[keep:]:
            try:
                old.unlink()
            except Exception:
                pass
        return dest
    except Exception as e:
        print(f"[backup] erreur : {e}")
        return None

def open_retroarch_no_game(cfg):
    s = load_settings(cfg)
    ra = s.get("retroarch_path", "").strip()
    if not ra or not Path(ra).exists():
        return False
    try:
        import subprocess
        subprocess.Popen([ra])
        return True
    except Exception as e:
        print(f"[retroarch] erreur : {e}")
        return False

# ---------- core picker ----------
class CorePicker(QDialog):
    def __init__(self, parent, game, current_core):
        super().__init__(parent)
        self.setWindowTitle(f"Core pour : {game['title']}")
        self.resize(560, 240)
        if parent is not None:
            self.setStyleSheet(parent.styleSheet())
        self.result_core = None
        l = QVBoxLayout(self)
        l.setContentsMargins(16, 16, 16, 16)
        l.setSpacing(10)
        info = QLabel("Core spécifique pour ce jeu.\nLaisse vide pour utiliser le core par défaut de la console.")
        info.setStyleSheet("font-size: 12px; color: #AAA; padding: 4px;")
        info.setWordWrap(True)
        l.addWidget(info)
        h = QHBoxLayout()
        h.addWidget(QLabel("Chemin du .dll"))
        self.le = QLineEdit(current_core or "")
        h.addWidget(self.le, 1)
        b_pick = QPushButton("Parcourir…")
        b_pick.clicked.connect(self._pick)
        h.addWidget(b_pick)
        l.addLayout(h)
        h2 = QHBoxLayout()
        b_clear = QPushButton("Effacer (core par défaut)")
        b_clear.clicked.connect(lambda: self.le.setText(""))
        h2.addWidget(b_clear)
        h2.addStretch(1)
        l.addLayout(h2)
        l.addStretch(1)
        btns = QHBoxLayout()
        b_cancel = QPushButton("Annuler")
        b_cancel.clicked.connect(self.reject)
        b_ok = QPushButton("Sauvegarder")
        b_ok.setObjectName("play")
        b_ok.clicked.connect(self._save)
        btns.addStretch(1)
        btns.addWidget(b_cancel)
        btns.addWidget(b_ok)
        l.addLayout(btns)
    def _pick(self):
        p, _ = QFileDialog.getOpenFileName(self, "Choisir un core", self.le.text() or str(BASE), "Libretro core (*.dll);;Tous les fichiers (*)")
        if p:
            self.le.setText(p)
    def _save(self):
        self.result_core = self.le.text().strip()
        self.accept()