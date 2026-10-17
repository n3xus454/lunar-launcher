# language: Python 3.11, file: launcher.py
import subprocess, sys, time
from pathlib import Path

from PyQt6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, QPoint, QParallelAnimationGroup,
    QTimer
)
from PyQt6.QtGui import QPixmap, QShortcut, QKeySequence
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFileDialog, QMessageBox, QFrame, QStackedWidget,
    QGridLayout, QScrollArea, QLineEdit, QComboBox, QMenu,
    QGraphicsOpacityEffect
)

from lunar_core import (
    ROMS, COVERS, DESCS, ASSETS, CONS_IMG, INTROS, GAMEPLAY, CFG_PATH, STATE_PATH,
    DEF_CFG, DEF_STATE, PALETTES, STRIPES, style, load_json, save_json,
    scan, cover, description, write_description, fuzzy_score, hsize, htime,
    gameplay_video,
    sfx, Splash, Intro, DescEditor, GameTile, WatermarkBg, GameplayBg, load_pixel_font,
    load_collections, save_collections, col_for, STATUSES, STATUS_COLORS,
    load_playlists, save_playlists, StatsWindow, PlaylistPicker, ImportDialog,
    SettingsDialog, load_settings,
    backup_save_for, open_retroarch_no_game, CorePicker,
    CONSOLE_EXTS, get_core_for, get_roms_dir_for,
)

CONSOLE_NAMES = {
    "ps1": "PlayStation",
    "ps2": "PlayStation 2",
    "snes": "Super Nintendo",
    "genesis": "Sega Genesis",
    "nes": "Nintendo NES",
    "arcade": "Arcade",
    "gba": "Game Boy Advance",
    "n64": "Nintendo 64",
}

class Launcher(QMainWindow):
    def __init__(self, console_key, console_name):
        super().__init__()
        self.cfg = load_json(CFG_PATH, DEF_CFG)
        self.state = load_json(STATE_PATH, DEF_STATE)
        self.ck = console_key
        self.name = console_name
        self.setWindowTitle(f"{console_name} — Lunar")
        self.setStyleSheet(style(console_key))
        self.cur_filter = self.state.get("filter", "Toutes")
        self.cur_sort = self.state.get("sort", "Titre")
        self.cur_status = "Tous"
        self.cur_playlist = "Aucune"
        self.q = ""
        self.sel = None
        self.games = []
        self.col = load_collections()
        self.playlists = load_playlists()
        self._launched = None
        self._ts = None
        self._panel_visible = False
        self._panel_anim = None
        self._cascade_timer = None
        self._cascade_tiles = []
        self._cascade_index = 0

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 14, 16, 10)
        root.setSpacing(10)

        # header
        header = QHBoxLayout()
        header.setSpacing(12)
        logo = QLabel(f"| |  {console_name.upper()}")
        logo.setObjectName("hero")
        header.addWidget(logo)
        self.hsub = QLabel("")
        self.hsub.setObjectName("sub")
        header.addWidget(self.hsub)
        header.addStretch(1)
        b_stats = QPushButton("Stats")
        b_stats.clicked.connect(self.open_stats)
        header.addWidget(b_stats)
        b_import = QPushButton("Ajouter des jeux")
        b_import.clicked.connect(self.open_import)
        header.addWidget(b_import)
        b_ra_open = QPushButton("Ouvrir RetroArch")
        b_ra_open.clicked.connect(self.open_retroarch)
        header.addWidget(b_ra_open)
        b_home = QPushButton("Accueil")
        b_home.clicked.connect(self.go_home)
        header.addWidget(b_home)
        b_ra = QPushButton("RetroArch")
        b_ra.clicked.connect(self.pick_ra)
        header.addWidget(b_ra)
        b_rescan = QPushButton("Rescanner")
        b_rescan.clicked.connect(self.refresh)
        header.addWidget(b_rescan)
        root.addLayout(header)

        # accent stripe
        strip = QHBoxLayout()
        strip.setSpacing(0)
        for col in STRIPES[console_key]:
            bar = QFrame()
            bar.setObjectName("stripe")
            bar.setFixedHeight(4)
            bar.setStyleSheet(f"background: {col};")
            strip.addWidget(bar, 1)
        root.addLayout(strip)

        # filters
        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Rechercher…")
        self.search.textChanged.connect(self.on_search)
        bar.addWidget(self.search, 2)
        self.regc = QComboBox()
        self.regc.addItems(["Toutes", "USA", "EUR", "JAP"])
        self.regc.setCurrentText(self.cur_filter)
        self.regc.currentTextChanged.connect(self.on_f)
        bar.addWidget(self.regc, 1)
        self.srtc = QComboBox()
        self.srtc.addItems(["Titre", "Région", "Taille", "Favoris", "Récemment joués", "Temps de jeu"])
        self.srtc.setCurrentText(self.cur_sort)
        self.srtc.currentTextChanged.connect(self.on_s)
        bar.addWidget(self.srtc, 1)
        self.statc = QComboBox()
        self.statc.addItems(["Tous"] + STATUSES)
        self.statc.currentTextChanged.connect(self.on_stat)
        bar.addWidget(self.statc, 1)
        self.plc = QComboBox()
        self.plc.currentTextChanged.connect(self.on_playlist)
        bar.addWidget(self.plc, 1)
        root.addLayout(bar)

        # main area
        main = QHBoxLayout()
        main.setSpacing(12)
        left_wrap = QWidget()
        left_wrap.setObjectName("leftWrap")
        left_wrap.setStyleSheet("QWidget#leftWrap { background: transparent; }")
        left_layout = QVBoxLayout(left_wrap)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        self.watermark = WatermarkBg(left_wrap, accent=PALETTES[console_key][0])
        self.watermark.setGeometry(0, 0, 10, 10)
        self.watermark.lower()

        self.gameplay_bg = GameplayBg(left_wrap)
        self.gameplay_bg.setVisible(False)

        self.scroll = QScrollArea(left_wrap)
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("background: transparent; border: none;")
        self.scroll.viewport().setStyleSheet("background: transparent;")
        self.scroll.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.gh = QWidget()
        self.gh.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.gh.setStyleSheet("background: transparent;")
        self.grid = QGridLayout(self.gh)
        self.grid.setSpacing(14)
        self.grid.setContentsMargins(4, 4, 4, 4)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.scroll.setWidget(self.gh)
        left_layout.addWidget(self.scroll)
        self.scroll.raise_()
        main.addWidget(left_wrap, 1)
        self._left_wrap = left_wrap

        # ---------- panneau de droite ----------
        a, ah, sec, dk, pn, ph, bd, tx, td = PALETTES[console_key]
        self.detail = QFrame()
        self.detail.setMinimumWidth(0)
        self.detail.setMaximumWidth(0)
        self.detail.setStyleSheet(f"QFrame {{ background: {pn}; border: 1px solid {bd}; border-radius: 12px; }}")
        self.detail.setVisible(False)
        dl = QVBoxLayout(self.detail)
        dl.setContentsMargins(18, 18, 18, 18)
        dl.setSpacing(10)

        cover_wrap = QFrame()
        cover_wrap.setFixedHeight(320)
        cover_wrap.setStyleSheet(f"QFrame {{ background: {dk}; border: 1px solid {bd}; border-radius: 8px; }}")
        cwl = QVBoxLayout(cover_wrap)
        cwl.setContentsMargins(8, 8, 8, 8)
        cwl.setSpacing(0)
        self.cv = QLabel("Pas de jaquette")
        self.cv.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cv.setStyleSheet(f"background: transparent; color: {td}; font-size: 13px; border: none;")
        cwl.addWidget(self.cv)
        dl.addWidget(cover_wrap)

        self.ttl = QLabel("")
        self.ttl.setObjectName("ttl")
        self.ttl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ttl.setWordWrap(True)
        self.ttl.setContentsMargins(0, 8, 0, 0)
        dl.addWidget(self.ttl)

        self.meta = QLabel("")
        self.meta.setObjectName("meta")
        self.meta.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.meta.setWordWrap(True)
        dl.addWidget(self.meta)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {bd}; border: none;")
        dl.addWidget(sep)

        self.desc_label = QLabel("Sélectionne un jeu.")
        self.desc_label.setObjectName("desc")
        self.desc_label.setWordWrap(True)
        self.desc_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        desc_box = QFrame()
        desc_box.setObjectName("descbox")
        desc_box.setFixedHeight(220)
        dbl = QVBoxLayout(desc_box)
        dbl.setContentsMargins(0, 0, 0, 0)
        dscroll = QScrollArea()
        dscroll.setWidgetResizable(True)
        dscroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        dscroll.setStyleSheet("background: transparent; border: none;")
        dscroll.setWidget(self.desc_label)
        dbl.addWidget(dscroll)
        dl.addWidget(desc_box)

        dl.addStretch(1)

        self.edit_btn = QPushButton("Modifier la description")
        self.edit_btn.clicked.connect(self.edit_desc)
        dl.addWidget(self.edit_btn)
        self.close_panel_btn = QPushButton("Fermer le panneau")
        self.close_panel_btn.clicked.connect(self.hide_panel)
        dl.addWidget(self.close_panel_btn)

        sep2 = QFrame()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet(f"background: {bd}; border: none;")
        dl.addWidget(sep2)

        self.bp = QPushButton("JOUER")
        self.bp.setObjectName("play")
        self.bp.clicked.connect(self.play_sel)
        self.bp.setMinimumHeight(58)
        dl.addWidget(self.bp)

        main.addWidget(self.detail, 0)
        root.addLayout(main, 1)

        self.status = self.statusBar()
        self.status.setStyleSheet(f"background: {pn}; color: {td}; border-top: 1px solid {bd}; padding: 4px;")

        QShortcut(QKeySequence("Ctrl+Alt+P"), self, activated=self.open_settings)

        self.refresh_playlists_combo()
        self.refresh()

    # =====================
    #   RESIZE
    # =====================
    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "_left_wrap") and self._left_wrap:
            w = self._left_wrap.width()
            h = self._left_wrap.height()
            if hasattr(self, "watermark") and self.watermark:
                self.watermark.setGeometry(0, 0, w, h)

    # =====================
    #   NAVIGATION
    # =====================
    def go_home(self):
        self._save()
        p = self.parent()
        while p is not None:
            if isinstance(p, MainController):
                p.show_splash()
                return
            p = p.parent()

    def _save(self):
        self.state["filter"] = self.cur_filter
        self.state["sort"] = self.cur_sort
        save_json(STATE_PATH, self.state)

    def pick_ra(self):
        s = load_settings(self.cfg)
        p, _ = QFileDialog.getOpenFileName(self, "RetroArch", s.get("retroarch_path", ""))
        if p:
            s["retroarch_path"] = p
            save_json(CFG_PATH, self.cfg)

    def open_retroarch(self):
        ok = open_retroarch_no_game(self.cfg)
        if not ok:
            QMessageBox.warning(self, "RetroArch introuvable",
                                "Configure le chemin dans Ctrl+Alt+P.")

    # =====================
    #   FILTERS
    # =====================
    def on_search(self, t):
        self.q = t.strip()
        self.rebuild()

    def on_f(self, t):
        self.cur_filter = t
        self._save()
        self.rebuild()

    def on_s(self, t):
        self.cur_sort = t
        self._save()
        self.rebuild()

    def on_stat(self, t):
        self.cur_status = t
        self.rebuild()

    def on_playlist(self, t):
        self.cur_playlist = t
        self.rebuild()

    def refresh_playlists_combo(self):
        current = self.plc.currentText() if self.plc.count() else "Aucune"
        self.plc.blockSignals(True)
        self.plc.clear()
        self.plc.addItem("Aucune")
        for name in sorted(self.playlists.keys()):
            self.plc.addItem(name)
        idx = self.plc.findText(current)
        if idx >= 0:
            self.plc.setCurrentIndex(idx)
        self.plc.blockSignals(False)
        self.cur_playlist = self.plc.currentText() or "Aucune"

    # =====================
    #   DATA
    # =====================
    def refresh(self):
        d = get_roms_dir_for(self.ck, self.cfg)
        d.mkdir(parents=True, exist_ok=True)
        self.games = scan(d, self.ck)
        self.playlists = load_playlists()
        self.refresh_playlists_combo()
        self.rebuild()
        self.hsub.setText(f"{len(self.games)} jeu(x)  ·  {self.name}")

    def filtered(self):
        g = self.games[:]
        if self.cur_filter != "Toutes":
            g = [x for x in g if x["region"] == self.cur_filter]
        if self.cur_status != "Tous":
            g = [x for x in g if col_for(self.col, x["path"]).get("status", "") == self.cur_status]
        if self.cur_playlist != "Aucune":
            paths = self.playlists.get(self.cur_playlist, [])
            g = [x for x in g if x["path"] in paths]
        if self.q:
            scored = [(fuzzy_score(self.q, x["title"]), x) for x in g]
            g = [x for s, x in scored if s >= 0.55]
            g.sort(key=lambda x: -fuzzy_score(self.q, x["title"]))
        favs = set(self.cfg.get("favorites", []))
        recents = list(self.cfg.get("recent", []))
        playtime = self.cfg.get("playtime", {})
        if self.cur_sort == "Favoris":
            g = [x for x in g if x["path"] in favs]
        elif self.cur_sort == "Récemment joués":
            order = {p: i for i, p in enumerate(recents)}
            g = [x for x in g if x["path"] in order]
            g.sort(key=lambda x: order[x["path"]])
        if self.cur_sort == "Titre":
            g.sort(key=lambda x: x["title"].lower())
        elif self.cur_sort == "Région":
            g.sort(key=lambda x: (x["region"], x["title"].lower()))
        elif self.cur_sort == "Taille":
            g.sort(key=lambda x: -x["size"])
        elif self.cur_sort == "Temps de jeu":
            g.sort(key=lambda x: -playtime.get(x["path"], 0))
        elif self.cur_sort == "Favoris":
            g.sort(key=lambda x: x["title"].lower())
        if self.cur_sort not in ("Récemment joués", "Temps de jeu"):
            g = sorted(g, key=lambda x: 0 if x["path"] in favs else 1)
        return g

    def clear(self):
        while self.grid.count():
            it = self.grid.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()

    def rebuild(self):
        self.clear()
        games = self.filtered()
        cd = Path(self.cfg["covers_dir"])
        favs = set(self.cfg.get("favorites", []))
        s = load_settings(self.cfg)
        tile_size = {"small": 170, "medium": 220, "large": 280}.get(s.get("tile_size", "medium"), 220)
        show_status = s.get("show_status_badges", True)
        show_rating = s.get("show_ratings", True)
        if self._cascade_timer is not None:
            self._cascade_timer.stop()
        if not games:
            e = QLabel("Aucun jeu dans ce filtre.")
            e.setStyleSheet(f"color: {PALETTES[self.ck][8]}; font-size: 14px; padding: 40px;")
            self.grid.addWidget(e, 0, 0)
            self.status.showMessage("0 jeu")
            return
        cols = 4
        tiles = []
        for i, g in enumerate(games):
            cv = cover(cd, g["title"])
            c = col_for(self.col, g["path"])
            t = GameTile(
                g, self.ck, cv, g["path"] in favs,
                delay_ms=0,
                status=c.get("status", ""),
                rating=c.get("rating", 0),
                tile_size=tile_size,
                show_status=show_status,
                show_rating=show_rating,
            )
            t.clicked.connect(self.on_click)
            t.rclick.connect(self.on_rclick)
            self.grid.addWidget(t, i // cols, i % cols)
            tiles.append(t)
        self._cascade_tiles = tiles
        self._cascade_index = 0
        if self._cascade_timer is None:
            self._cascade_timer = QTimer(self)
            self._cascade_timer.timeout.connect(self._run_cascade)
        self._cascade_timer.start(35)
        self.status.showMessage(f"{len(games)} jeu(x)")

    def _run_cascade(self):
        if self._cascade_index >= len(self._cascade_tiles):
            self._cascade_timer.stop()
            return
        tile = self._cascade_tiles[self._cascade_index]
        try:
            tile._anim.start()
        except Exception:
            pass
        self._cascade_index += 1

    # =====================
    #   PANNEAU DETAIL
    # =====================
    def show_panel(self):
        if self._panel_visible:
            return
        self._panel_visible = True
        self.detail.setVisible(True)
        grp = QParallelAnimationGroup(self)
        a_min = QPropertyAnimation(self.detail, b"minimumWidth")
        a_min.setDuration(220)
        a_min.setStartValue(0)
        a_min.setEndValue(420)
        a_min.setEasingCurve(QEasingCurve.Type.OutCubic)
        a_max = QPropertyAnimation(self.detail, b"maximumWidth")
        a_max.setDuration(220)
        a_max.setStartValue(0)
        a_max.setEndValue(420)
        a_max.setEasingCurve(QEasingCurve.Type.OutCubic)
        grp.addAnimation(a_min)
        grp.addAnimation(a_max)
        self._panel_anim = grp
        grp.start()

    def hide_panel(self):
        if not self._panel_visible:
            return
        self._panel_visible = False
        cur_w = self.detail.width()
        grp = QParallelAnimationGroup(self)
        a_min = QPropertyAnimation(self.detail, b"minimumWidth")
        a_min.setDuration(200)
        a_min.setStartValue(cur_w)
        a_min.setEndValue(0)
        a_min.setEasingCurve(QEasingCurve.Type.InCubic)
        a_max = QPropertyAnimation(self.detail, b"maximumWidth")
        a_max.setDuration(200)
        a_max.setStartValue(cur_w)
        a_max.setEndValue(0)
        a_max.setEasingCurve(QEasingCurve.Type.InCubic)
        grp.addAnimation(a_min)
        grp.addAnimation(a_max)
        grp.finished.connect(lambda: self.detail.setVisible(False))
        self._panel_anim = grp
        grp.start()
        self.sel = None

    # =====================
    #   SELECTION
    # =====================
    def on_click(self, g):
        self.sel = g
        self.ttl.setText(g["title"])
        parts = [g["region"], hsize(g["size"])]
        if g.get("disc"):
            parts.append(f"Disque {g['disc']}")
        if g.get("rev"):
            parts.append(g["rev"])
        pt = self.cfg.get("playtime", {}).get(g["path"], 0)
        if pt > 0:
            parts.append(f"Joue {htime(pt)}")
        c = col_for(self.col, g["path"])
        s = c.get("sessions", 0)
        if s > 0:
            parts.append(f"{s} session" + ("s" if s > 1 else ""))
        in_pls = [name for name, paths in self.playlists.items() if g["path"] in paths]
        if in_pls:
            parts.append("Playlists : " + ", ".join(in_pls))
        self.meta.setText("  ·  ".join(parts))

        cv = cover(Path(self.cfg["covers_dir"]), g["title"])
        if cv:
            self.cv.setPixmap(QPixmap(str(cv)).scaled(
                380, 380,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
        else:
            self.cv.setText("Pas de jaquette")
            self.cv.setPixmap(QPixmap())

        d = description(g["title"])
        if d:
            self.desc_label.setText(d)
        else:
            self.desc_label.setText(
                f"Pas de description pour ce jeu.\n\n"
                f"Clique sur Modifier la description pour en ajouter une.\n\n"
                f"Titre : {g['title']}"
            )
        self.show_panel()

    # =====================
    #   CLIC DROIT
    # =====================
    def on_rclick(self, g):
        m = QMenu(self)
        favs = set(self.cfg.get("favorites", []))
        a1 = m.addAction("Retirer des favoris" if g["path"] in favs else "Ajouter aux favoris")
        a1.triggered.connect(lambda: self.toggle_fav(g))

        stat_menu = m.addMenu("Statut")
        current = col_for(self.col, g["path"]).get("status", "")
        for s in STATUSES:
            label = f"[X] {s}" if s == current else s
            a = stat_menu.addAction(label)
            a.triggered.connect(lambda checked=False, st=s: self.set_status(g, st))
        if current:
            a_clear = stat_menu.addAction("— Effacer")
            a_clear.triggered.connect(lambda: self.set_status(g, ""))

        rate_menu = m.addMenu("Note")
        cur_r = col_for(self.col, g["path"]).get("rating", 0)
        for r in range(1, 6):
            stars = "*" * r + "-" * (5 - r)
            label = f"[X] {stars}" if r == cur_r else stars
            a = rate_menu.addAction(label)
            a.triggered.connect(lambda checked=False, rt=r: self.set_rating(g, rt))
        if cur_r > 0:
            a_clear = rate_menu.addAction("— Effacer")
            a_clear.triggered.connect(lambda: self.set_rating(g, 0))

        pl_menu = m.addMenu("Playlists")
        a_pl_edit = pl_menu.addAction("Gerer les playlists pour ce jeu…")
        a_pl_edit.triggered.connect(lambda: self.edit_playlists(g))

        a_core = m.addAction("Core pour ce jeu…")
        a_core.triggered.connect(lambda: self.pick_core_for(g))

        a2 = m.addAction("Ouvrir le dossier du jeu")
        a2.triggered.connect(lambda: self.open_folder(g))
        m.exec(self.cursor().pos())

    def set_status(self, g, status):
        c = col_for(self.col, g["path"])
        c["status"] = status
        save_collections(self.col)
        self.rebuild()
        if self.sel and self.sel["path"] == g["path"]:
            self.on_click(g)

    def set_rating(self, g, rating):
        c = col_for(self.col, g["path"])
        c["rating"] = rating
        save_collections(self.col)
        self.rebuild()
        if self.sel and self.sel["path"] == g["path"]:
            self.on_click(g)

    def toggle_fav(self, g):
        favs = set(self.cfg.get("favorites", []))
        if g["path"] in favs:
            favs.remove(g["path"])
        else:
            favs.add(g["path"])
        self.cfg["favorites"] = list(favs)
        save_json(CFG_PATH, self.cfg)
        self.rebuild()

    def open_folder(self, g):
        p = Path(g["path"])
        if p.exists():
            subprocess.Popen(["explorer", "/select,", str(p)])

    # =====================
    #   DESCRIPTION / PLAYLISTS / CORE
    # =====================
    def edit_desc(self):
        if not self.sel:
            QMessageBox.information(self, "Aucun jeu", "Sélectionne un jeu d'abord.")
            return
        cur = description(self.sel["title"]) or ""
        dlg = DescEditor(self, self.sel["title"], cur)
        if dlg.exec():
            write_description(self.sel["title"], dlg.result_text())
            self.desc_label.setText(dlg.result_text() or "Pas de description.")

    def edit_playlists(self, g):
        self.playlists = load_playlists()
        dlg = PlaylistPicker(self, g, self.playlists)
        dlg.exec()
        if dlg.result is not None:
            self.playlists = dlg.result
        self.refresh_playlists_combo()
        self.rebuild()
        if self.sel and self.sel["path"] == g["path"]:
            self.on_click(g)

    def pick_core_for(self, g):
        c = col_for(self.col, g["path"])
        current = c.get("core", "")
        dlg = CorePicker(self, g, current)
        if dlg.exec():
            c["core"] = dlg.result_core or ""
            save_collections(self.col)

    # =====================
    #   STATS / IMPORT / SETTINGS
    # =====================
    def open_stats(self):
        self.col = load_collections()
        StatsWindow(self, self.cfg, self.col, self.games).exec()

    def open_import(self):
        dlg = ImportDialog(self, self.ck)
        if dlg.exec():
            self.refresh()

    def open_settings(self):
        dlg = SettingsDialog(self, self.cfg)
        if dlg.exec():
            self.rebuild()

    # =====================
    #   LANCEMENT
    # =====================
    def play_sel(self):
        if not self.sel:
            QMessageBox.information(self, "Aucun jeu", "Sélectionne un jeu d'abord.")
            return
        s = load_settings(self.cfg)
        ra = s.get("retroarch_path", "").strip()
        c_entry = col_for(self.col, self.sel["path"])
        override_core = c_entry.get("core", "").strip()
        core = override_core if override_core else get_core_for(self.ck, self.cfg)
        if not ra or not Path(ra).exists():
            QMessageBox.warning(self, "RetroArch introuvable",
                                "Configure le chemin dans Ctrl+Alt+P.")
            return
        if not core or not Path(core).exists():
            QMessageBox.warning(self, "Core introuvable", core)
            return
        try:
            backup_save_for(self.sel["path"], keep=5)
        except Exception:
            pass
        recents = [p for p in self.cfg.get("recent", []) if p != self.sel["path"]]
        recents.insert(0, self.sel["path"])
        self.cfg["recent"] = recents[:20]
        save_json(CFG_PATH, self.cfg)
        c = col_for(self.col, self.sel["path"])
        c["sessions"] = c.get("sessions", 0) + 1
        c["last_played"] = int(time.time())
        save_collections(self.col)
        self._launched = self.sel
        self._ts = time.time()
        try:
            subprocess.Popen([ra, "-L", core, self.sel["path"], "-f"])
            self.status.showMessage(f"Lance : {Path(self.sel['path']).name}")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", str(e))

    def record_playtime(self):
        if self._launched is None or self._ts is None:
            return
        el = int(time.time() - self._ts)
        if el < 5:
            self._launched = None
            self._ts = None
            return
        pt = self.cfg.get("playtime", {})
        pt[self._launched["path"]] = pt.get(self._launched["path"], 0) + el
        self.cfg["playtime"] = pt
        save_json(CFG_PATH, self.cfg)
        self._launched = None
        self._ts = None


# =====================
#   MAIN CONTROLLER
# =====================
class MainController(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Lunar Launcher")
        self.setStyleSheet(f"background: {PALETTES['ps1'][3]};")
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.splash = Splash()
        self.bg = self.splash.bg
        self.splash.picked.connect(self.on_pick)
        self.stack.addWidget(self.splash)
        self.intro = None
        self.launchers = {}
        QShortcut(QKeySequence("Ctrl+Alt+P"), self, activated=self.open_settings)
        self.showFullScreen()

    def open_settings(self):
        cfg = load_json(CFG_PATH, DEF_CFG)
        dlg = SettingsDialog(self, cfg)
        if dlg.exec():
            s = load_settings(cfg)
            for lc in self.launchers.values():
                lc.cfg = cfg
                lc.rebuild()
            if hasattr(self.splash, "bg"):
                if s.get("animated_bg", True):
                    self.splash.bg.timer.start(33)
                else:
                    self.splash.bg.timer.stop()
                self.splash.bg.update()

    def on_pick(self, k):
        if k not in CONSOLE_NAMES:
            QMessageBox.information(self, "Bientot", "Console non supportee pour l'instant.")
            return
        cfg = load_json(CFG_PATH, DEF_CFG)
        s = load_settings(cfg)
        intro_file = INTROS / f"{k}.mp4"
        self.intro = Intro(intro_file if intro_file.exists() else None,
                           volume=s.get("intro_volume", 0.6))
        self.intro.done.connect(lambda key=k: self.show_launcher(key))
        self.stack.addWidget(self.intro)
        self._fade_to(self.intro)
        self.intro.setFocus()

    def _fade_to(self, widget):
        current = self.stack.currentWidget()
        if current is widget:
            return
        eff_out = QGraphicsOpacityEffect(current)
        current.setGraphicsEffect(eff_out)
        anim_out = QPropertyAnimation(eff_out, b"opacity")
        anim_out.setDuration(150)
        anim_out.setStartValue(1.0)
        anim_out.setEndValue(0.0)
        anim_out.setEasingCurve(QEasingCurve.Type.OutCubic)

        def switch_and_fade_in():
            self.stack.setCurrentWidget(widget)
            eff_in = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(eff_in)
            anim_in = QPropertyAnimation(eff_in, b"opacity")
            anim_in.setDuration(200)
            anim_in.setStartValue(0.0)
            anim_in.setEndValue(1.0)
            anim_in.setEasingCurve(QEasingCurve.Type.InCubic)
            anim_in.finished.connect(lambda: widget.setGraphicsEffect(None))
            widget._fade_anim = anim_in
            anim_in.start()
            current.setGraphicsEffect(None)

        anim_out.finished.connect(switch_and_fade_in)
        widget._fade_out_anim = anim_out
        anim_out.start()

    def show_launcher(self, console_key):
        sfx().play("swoosh")
        if console_key not in self.launchers:
            name = CONSOLE_NAMES.get(console_key, console_key.upper())
            lc = Launcher(console_key, name)
            self.launchers[console_key] = lc
            self.stack.addWidget(lc)
        self.launchers[console_key].refresh()
        self._fade_to(self.launchers[console_key])

    def show_splash(self):
        sfx().play("swoosh")
        for lc in self.launchers.values():
            lc.record_playtime()
        self._fade_to(self.splash)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_F11:
            self.showNormal() if self.isFullScreen() else self.showFullScreen()
        elif e.key() == Qt.Key.Key_Escape and self.isFullScreen():
            self.showNormal()
        else:
            super().keyPressEvent(e)

    def closeEvent(self, e):
        cfg = load_json(CFG_PATH, DEF_CFG)
        s = load_settings(cfg)
        if s.get("confirm_quit", True):
            r = QMessageBox.question(self, "Quitter", "Fermer le launcher ?")
            if r != QMessageBox.StandardButton.Yes:
                e.ignore()
                return
        for lc in self.launchers.values():
            lc._save()
            lc.record_playtime()
        super().closeEvent(e)


# =====================
#   ENTRY POINT
# =====================
def main():
    ROMS.mkdir(exist_ok=True)
    for ck in CONSOLE_EXTS:
        (ROMS / ck).mkdir(exist_ok=True)
    COVERS.mkdir(exist_ok=True)
    DESCS.mkdir(exist_ok=True)
    ASSETS.mkdir(exist_ok=True)
    CONS_IMG.mkdir(exist_ok=True)
    INTROS.mkdir(exist_ok=True)
    GAMEPLAY.mkdir(exist_ok=True)
    (ASSETS / "fonts").mkdir(exist_ok=True)
    app = QApplication(sys.argv)
    app.setApplicationName("Lunar Launcher")
    load_pixel_font()
    win = MainController()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()