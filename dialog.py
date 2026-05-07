"""
dialog.py — Main GUI dialog for QRVIZ.

Features
--------
* Single-band continuous rendering with percentile / min-max / manual stretch.
* Discrete / classified rendering with per-class colour, label, and decimal.
* RGB three-band composite.
* All rasterio-style colormaps (custom + full Matplotlib library).
* Grid label rotation (X and Y axes independently, 0–360°).
* Grid label size, tick count, and decimal-place control.
* Coordinate format: DMS, DM, Decimal Degree, UTM/Metre.
* Pointed or box colourbar with configurable geometry and orientation.
* Multi-map layout series: user-selects rows × cols (e.g. 2×2, 3×2).
  Each sub-map can be assigned a different layer / band / colormap.
* Export single map or full layout (PNG 300 DPI, SVG, TIFF, PDF).

License: GNU GPL v2 or later
"""

import os
import numpy as np

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QComboBox, QCheckBox, QPushButton,
    QDoubleSpinBox, QSpinBox, QFileDialog, QSizePolicy,
    QWidget, QRadioButton, QButtonGroup, QGridLayout,
    QLineEdit, QTabWidget, QScrollArea, QMessageBox, QSplitter,
    QColorDialog, QFrame, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView,
)
from qgis.PyQt.QtGui import (
    QFontDatabase, QPixmap, QIcon, QPainter, QColor, QFont,
)
from qgis.PyQt.QtCore import Qt, QSize
from qgis.core import QgsProject, QgsMapLayerType, QgsRasterLayer

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.ticker as mticker
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec

from .colormaps import CUSTOM_PALETTES, COLORMAPS


# ─────────────────────────────────────────────────────────────────────────────
#  DiscreteClassRow — one row widget for a single classified grid code
# ─────────────────────────────────────────────────────────────────────────────
class DiscreteClassRow(QWidget):
    DEFAULT_PALETTE = [
        "#e41a1c", "#377eb8", "#4daf4a", "#984ea3", "#ff7f00",
        "#a65628", "#f781bf", "#999999", "#ffff33", "#a6cee3",
        "#1f78b4", "#b2df8a", "#33a02c", "#fb9a99", "#fdbf6f",
        "#cab2d6", "#6a3d9a", "#ffff99", "#b15928", "#8dd3c7",
    ]

    def __init__(self, gridcode, color_hex=None, label="", decimals=2, parent=None):
        super().__init__(parent)
        self.gridcode = gridcode
        self._color = color_hex or "#888888"

        row = QHBoxLayout(self)
        row.setContentsMargins(2, 2, 2, 2)
        row.setSpacing(6)

        self.btn_color = QPushButton()
        self.btn_color.setFixedSize(26, 26)
        self.btn_color.setToolTip("Click to choose class colour")
        self.btn_color.clicked.connect(self._pick_color)
        self._apply_color_style()
        row.addWidget(self.btn_color)

        self.le_hex = QLineEdit(self._color)
        self.le_hex.setFixedWidth(72)
        self.le_hex.setPlaceholderText("#rrggbb")
        self.le_hex.textChanged.connect(self._on_hex_changed)
        row.addWidget(self.le_hex)

        lbl_val = QLabel(f"<b>{gridcode}</b>")
        lbl_val.setFixedWidth(46)
        lbl_val.setAlignment(Qt.AlignCenter)
        lbl_val.setStyleSheet("color:#93c5fd; font-size:12px;")
        row.addWidget(lbl_val)

        row.addWidget(QLabel("Label:"))
        self.le_label = QLineEdit(label if label else str(gridcode))
        self.le_label.setMinimumWidth(80)
        row.addWidget(self.le_label, stretch=1)

        row.addWidget(QLabel("Dec:"))
        self.sp_decimals = QSpinBox()
        self.sp_decimals.setRange(0, 6)
        self.sp_decimals.setValue(decimals)
        self.sp_decimals.setFixedWidth(46)
        row.addWidget(self.sp_decimals)

    def _apply_color_style(self):
        c = QColor(self._color)
        if c.isValid():
            luma = 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()
            txt = "#000000" if luma > 160 else "#ffffff"
            self.btn_color.setStyleSheet(
                f"background-color:{self._color}; color:{txt}; "
                f"border:1px solid #6b7280; border-radius:3px; font-size:9px;"
            )
        else:
            self.btn_color.setStyleSheet(
                "background-color:#888888; border:1px solid #6b7280; border-radius:3px;"
            )

    def _pick_color(self):
        initial = QColor(self._color) if QColor(self._color).isValid() else QColor("#888888")
        col = QColorDialog.getColor(initial, self, f"Choose Colour — Class {self.gridcode}")
        if col.isValid():
            self._color = col.name()
            self._apply_color_style()
            self.le_hex.blockSignals(True)
            self.le_hex.setText(self._color)
            self.le_hex.blockSignals(False)

    def _on_hex_changed(self, text):
        t = text.strip()
        if not t.startswith("#"):
            t = "#" + t
        c = QColor(t)
        if c.isValid():
            self._color = c.name()
            self._apply_color_style()

    def get_color(self):
        c = QColor(self._color)
        return self._color if c.isValid() else "#888888"

    def get_label(self):
        return self.le_label.text().strip() or str(self.gridcode)

    def get_decimals(self):
        return self.sp_decimals.value()


# ─────────────────────────────────────────────────────────────────────────────
#  LayoutSlotWidget — configuration for one panel in the layout series
# ─────────────────────────────────────────────────────────────────────────────
class LayoutSlotWidget(QWidget):
    """Compact row for configuring one sub-map in the multi-map layout."""

    def __init__(self, slot_index, parent=None):
        super().__init__(parent)
        self.slot_index = slot_index
        lay = QHBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(6)

        lay.addWidget(QLabel(f"<b>#{slot_index + 1}</b>"))

        lay.addWidget(QLabel("Layer:"))
        self.cb_layer = QComboBox()
        self.cb_layer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.cb_layer.setMinimumWidth(110)
        lay.addWidget(self.cb_layer, stretch=1)

        lay.addWidget(QLabel("Band:"))
        self.sp_band = QSpinBox()
        self.sp_band.setRange(1, 100)
        self.sp_band.setFixedWidth(46)
        lay.addWidget(self.sp_band)

        lay.addWidget(QLabel("Colormap:"))
        self.cb_cmap = QComboBox()
        self.cb_cmap.addItems(COLORMAPS)
        self.cb_cmap.setFixedWidth(130)
        if "NDVI_Custom" in COLORMAPS:
            self.cb_cmap.setCurrentText("NDVI_Custom")
        lay.addWidget(self.cb_cmap)

        lay.addWidget(QLabel("Title:"))
        self.le_title = QLineEdit(f"Map {slot_index + 1}")
        self.le_title.setFixedWidth(90)
        lay.addWidget(self.le_title)

        lay.addWidget(QLabel("Stretch:"))
        self.cb_stretch = QComboBox()
        self.cb_stretch.addItems(["Actual Min-Max", "Percentile 2-98", "Manual"])
        self.cb_stretch.setFixedWidth(130)
        lay.addWidget(self.cb_stretch)

        self.chk_colorbar = QCheckBox("Colorbar")
        self.chk_colorbar.setChecked(True)
        lay.addWidget(self.chk_colorbar)


# ─────────────────────────────────────────────────────────────────────────────
#  Main Dialog
# ─────────────────────────────────────────────────────────────────────────────
class QRVIZDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.setWindowFlags(Qt.Window)
        self.setWindowTitle("QRVIZ — Scientific Raster Visualization")
        self.setMinimumSize(1400, 820)

        families = QFontDatabase().families()
        pref_fonts = ["Poppins", "Segoe UI", "Ubuntu", "Arial"]
        chosen = next((f for f in pref_fonts if f in families), "")
        if chosen:
            self.setFont(QFont(chosen))

        # Internal state
        self._cached_arr = None
        self._cached_rgb = None
        self._cached_ext = None
        self._is_updating = False
        self._discrete_rows: list = []
        self._nodata_color = "#00000000"

        # Layout series state
        self._layout_slots: list = []       # list[LayoutSlotWidget]
        self._layout_cache: dict = {}       # slot_index -> (arr, ext)

        self._apply_stylesheet()
        self._build_ui()
        self._connect_live_updates()
        self.showMaximized()

    # ─── Stylesheet ───────────────────────────────────────────────────────────
    def _apply_stylesheet(self):
        self.setStyleSheet("""
            QDialog, QWidget { background-color: #1e1e2e; color: #e2e8f0; }
            QGroupBox {
                font-weight: bold; margin-top: 20px; padding-top: 14px;
                border: 1px solid #4b5563; border-radius: 6px;
            }
            QGroupBox::title {
                subcontrol-origin: margin; subcontrol-position: top left;
                left: 10px; color: #93c5fd;
            }
            QPushButton {
                background-color: #374151; color: #f3f4f6; font-weight: bold;
                border-radius: 4px; padding: 8px; border: 1px solid #4b5563;
            }
            QPushButton:hover { background-color: #4b5563; border: 1px solid #6b7280; }
            QPushButton#btn_arrow {
                padding: 0px; font-size: 14px; border-radius: 3px;
                background-color: #1e1e24;
            }
            QPushButton#btn_arrow:hover { background-color: #374151; }
            QPushButton#btn_primary {
                background-color: #1d4ed8; border: 1px solid #3b82f6;
            }
            QPushButton#btn_primary:hover { background-color: #2563eb; }
            QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {
                background-color: #374151; border: 1px solid #4b5563;
                border-radius: 4px; padding: 3px 6px; color: #e2e8f0;
            }
            QComboBox::drop-down { border: none; }
            QTabWidget::pane { border: 1px solid #4b5563; }
            QTabBar::tab {
                background-color: #374151; color: #9ca3af; padding: 6px 14px;
                border: 1px solid #4b5563; font-weight: bold;
            }
            QTabBar::tab:selected { background-color: #1e1e2e; color: #93c5fd; }
            QScrollArea { border: none; background-color: transparent; }
            QSplitter::handle { background-color: #4b5563; border-radius: 3px; margin: 4px; }
            QSplitter::handle:hover { background-color: #60a5fa; }
            QCheckBox { spacing: 6px; }
            QCheckBox::indicator {
                width: 14px; height: 14px; border: 1px solid #6b7280; border-radius: 3px;
            }
            QCheckBox::indicator:checked { background-color: #3b82f6; }
            QTableWidget {
                background-color: #1e1e2e; gridline-color: #374151;
                border: 1px solid #4b5563;
            }
            QHeaderView::section {
                background-color: #374151; color: #93c5fd;
                padding: 4px; border: 1px solid #4b5563; font-weight: bold;
            }
        """)

    # ─── UI Build ─────────────────────────────────────────────────────────────
    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        hdr.setSpacing(10)
        lbl_logo = QLabel()
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        if os.path.exists(icon_path):
            px = QPixmap(icon_path).scaled(36, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            lbl_logo.setPixmap(px)
        hdr.addWidget(lbl_logo)
        lbl_title = QLabel("QRVIZ")
        f = self.font(); f.setPointSize(18); f.setBold(True)
        lbl_title.setFont(f)
        lbl_title.setStyleSheet("color: #93c5fd;")
        hdr.addWidget(lbl_title)
        lbl_sub = QLabel("Scientific Raster Visualization for QGIS")
        lbl_sub.setStyleSheet("color: #9ca3af; font-size: 12px;")
        hdr.addWidget(lbl_sub)
        hdr.addStretch()
        main_layout.addLayout(hdr)

        # ── Top-level tab widget ───────────────────────────────────────────────
        self.top_tabs = QTabWidget()
        main_layout.addWidget(self.top_tabs, stretch=1)

        # Tab 1: Single Map
        self._build_single_map_tab()
        # Tab 2: Layout Series
        self._build_layout_series_tab()

    # ─────────────────────────────────────────────────────────────────────────
    #  TAB 1 — Single Map
    # ─────────────────────────────────────────────────────────────────────────
    def _build_single_map_tab(self):
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(4, 4, 4, 4)

        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setHandleWidth(8)

        # ── LEFT PANEL ────────────────────────────────────────────────────────
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setMinimumWidth(340)
        left_scroll.setFrameShape(QScrollArea.NoFrame)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(12)
        left_layout.setContentsMargins(4, 4, 8, 4)

        # Group 1 — Layer
        grp_layer = QGroupBox("1. Layer & Band")
        g1 = QVBoxLayout(grp_layer)
        g1.setSpacing(10); g1.setContentsMargins(12, 18, 12, 12)

        self.btn_open = QPushButton("OPEN RASTER FILE")
        self.btn_open.setObjectName("btn_primary")
        self.btn_open.setMinimumHeight(34)
        self.btn_open.clicked.connect(self._open_raster_file)
        g1.addWidget(self.btn_open)

        lay_sel = QHBoxLayout()
        lay_sel.addWidget(QLabel("Layer:"))
        self.cb_layer = QComboBox()
        self.cb_layer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.cb_layer.currentIndexChanged.connect(self._on_layer_changed)
        lay_sel.addWidget(self.cb_layer)
        g1.addLayout(lay_sel)

        mode_lay = QHBoxLayout()
        self.rb_single = QRadioButton("Single Band")
        self.rb_rgb = QRadioButton("RGB")
        self.rb_single.setChecked(True)
        bg = QButtonGroup(self)
        bg.addButton(self.rb_single); bg.addButton(self.rb_rgb)
        self.rb_single.toggled.connect(self._toggle_band_mode)
        mode_lay.addWidget(self.rb_single); mode_lay.addWidget(self.rb_rgb)
        g1.addLayout(mode_lay)

        band_grid = QGridLayout()
        self.lbl_band = QLabel("Band:")
        self.sp_band = QSpinBox(); self.sp_band.setMinimum(1); self.sp_band.setMaximum(100)
        band_grid.addWidget(self.lbl_band, 0, 0); band_grid.addWidget(self.sp_band, 0, 1)
        self.lbl_r = QLabel("R:"); self.sp_r = QSpinBox(); self.sp_r.setRange(1, 100); self.sp_r.setValue(1)
        self.lbl_g = QLabel("G:"); self.sp_g = QSpinBox(); self.sp_g.setRange(1, 100); self.sp_g.setValue(2)
        self.lbl_b = QLabel("B:"); self.sp_b = QSpinBox(); self.sp_b.setRange(1, 100); self.sp_b.setValue(3)
        for w in [self.lbl_r, self.sp_r, self.lbl_g, self.sp_g, self.lbl_b, self.sp_b]:
            w.setVisible(False)
        band_grid.addWidget(self.lbl_r, 1, 0); band_grid.addWidget(self.sp_r, 1, 1)
        band_grid.addWidget(self.lbl_g, 1, 2); band_grid.addWidget(self.sp_g, 1, 3)
        band_grid.addWidget(self.lbl_b, 2, 0); band_grid.addWidget(self.sp_b, 2, 1)
        g1.addLayout(band_grid)

        px_lay = QHBoxLayout()
        px_lay.addWidget(QLabel("Max pixels (k):"))
        self.sp_maxpx = QSpinBox(); self.sp_maxpx.setRange(50, 10000); self.sp_maxpx.setValue(1000)
        px_lay.addWidget(self.sp_maxpx)
        g1.addLayout(px_lay)

        self.btn_read = QPushButton("READ DATA & RENDER")
        self.btn_read.setObjectName("btn_primary")
        self.btn_read.setMinimumHeight(34)
        self.btn_read.clicked.connect(self._read_and_render)
        g1.addWidget(self.btn_read)
        left_layout.addWidget(grp_layer)

        # Group 2 — Color Mode
        grp_color = QGroupBox("2. Color Mode & Stretch")
        g2_outer = QVBoxLayout(grp_color)
        g2_outer.setContentsMargins(8, 18, 8, 8); g2_outer.setSpacing(6)

        self.tab_color_mode = QTabWidget()
        self.tab_color_mode.setStyleSheet("QTabBar::tab { padding: 4px 12px; font-weight: bold; }")

        # -- Continuous tab
        tab_cont = QWidget()
        g2 = QGridLayout(tab_cont)
        g2.setSpacing(10); g2.setContentsMargins(8, 10, 8, 8)

        g2.addWidget(QLabel("Stretch:"), 0, 0)
        self.cb_stretch = QComboBox()
        self.cb_stretch.addItems(["Actual Min-Max", "Percentile", "Manual Min-Max"])
        self.cb_stretch.currentIndexChanged.connect(self._toggle_stretch_opts)
        g2.addWidget(self.cb_stretch, 0, 1, 1, 3)

        self.lbl_pmin = QLabel("Pmin (%):"); self.sp_pmin = QDoubleSpinBox()
        self.sp_pmin.setRange(0, 49); self.sp_pmin.setValue(2); self.sp_pmin.setSingleStep(0.5)
        self.lbl_pmax = QLabel("Pmax (%):"); self.sp_pmax = QDoubleSpinBox()
        self.sp_pmax.setRange(51, 100); self.sp_pmax.setValue(98); self.sp_pmax.setSingleStep(0.5)
        g2.addWidget(self.lbl_pmin, 1, 0); g2.addWidget(self.sp_pmin, 1, 1)
        g2.addWidget(self.lbl_pmax, 1, 2); g2.addWidget(self.sp_pmax, 1, 3)

        self.lbl_vmin = QLabel("vmin:"); self.le_vmin = QLineEdit("0")
        self.lbl_vmax = QLabel("vmax:"); self.le_vmax = QLineEdit("1")
        g2.addWidget(self.lbl_vmin, 2, 0); g2.addWidget(self.le_vmin, 2, 1)
        g2.addWidget(self.lbl_vmax, 2, 2); g2.addWidget(self.le_vmax, 2, 3)

        g2.addWidget(QLabel("Colormap:"), 3, 0)
        cmap_lay = QHBoxLayout(); cmap_lay.setContentsMargins(0, 0, 0, 0); cmap_lay.setSpacing(4)
        self.btn_cmap_prev = QPushButton("◀"); self.btn_cmap_prev.setObjectName("btn_arrow")
        self.btn_cmap_prev.setFixedSize(26, 26); self.btn_cmap_prev.clicked.connect(self._cmap_prev)
        self.lbl_cmap_preview = QLabel()
        self.lbl_cmap_preview.setFixedHeight(26)
        self.lbl_cmap_preview.setStyleSheet("border: 1px solid #4b5563; border-radius: 4px;")
        self.lbl_cmap_preview.setScaledContents(True)
        self.btn_cmap_next = QPushButton("▶"); self.btn_cmap_next.setObjectName("btn_arrow")
        self.btn_cmap_next.setFixedSize(26, 26); self.btn_cmap_next.clicked.connect(self._cmap_next)
        cmap_lay.addWidget(self.btn_cmap_prev)
        cmap_lay.addWidget(self.lbl_cmap_preview, stretch=1)
        cmap_lay.addWidget(self.btn_cmap_next)
        g2.addLayout(cmap_lay, 3, 1, 1, 3)

        self.cmap_idx = COLORMAPS.index("NDVI_Custom") if "NDVI_Custom" in COLORMAPS else 0

        self.chk_reverse_cmap = QCheckBox("Reverse")
        self.chk_reverse_cmap.toggled.connect(self._on_reverse_toggled)
        g2.addWidget(self.chk_reverse_cmap, 4, 1, 1, 3)

        self.chk_nodata_transp = QCheckBox("Transparent Nodata")
        self.chk_nodata_transp.setChecked(True)
        g2.addWidget(self.chk_nodata_transp, 5, 0, 1, 4)

        self.tab_color_mode.addTab(tab_cont, "🎨 Continuous")

        # -- Discrete tab
        tab_disc = QWidget()
        disc_outer = QVBoxLayout(tab_disc)
        disc_outer.setContentsMargins(8, 8, 8, 8); disc_outer.setSpacing(6)

        self.btn_scan_classes = QPushButton("⟳  SCAN GRIDCODES")
        self.btn_scan_classes.setObjectName("btn_primary")
        self.btn_scan_classes.setMinimumHeight(30)
        self.btn_scan_classes.clicked.connect(self._scan_discrete_classes)
        disc_outer.addWidget(self.btn_scan_classes)

        dec_row = QHBoxLayout()
        dec_row.addWidget(QLabel("Set All Decimals:"))
        self.sp_global_decimals = QSpinBox()
        self.sp_global_decimals.setRange(0, 6); self.sp_global_decimals.setValue(2)
        self.sp_global_decimals.setFixedWidth(50)
        dec_row.addWidget(self.sp_global_decimals)
        btn_apply_dec = QPushButton("Apply"); btn_apply_dec.setFixedHeight(26)
        btn_apply_dec.clicked.connect(self._apply_global_decimals)
        dec_row.addWidget(btn_apply_dec); dec_row.addStretch()
        disc_outer.addLayout(dec_row)

        nd_row = QHBoxLayout()
        nd_row.addWidget(QLabel("Nodata Colour:"))
        self.btn_nodata_color = QPushButton()
        self.btn_nodata_color.setFixedSize(26, 26)
        self.btn_nodata_color.setStyleSheet(
            "background-color: transparent; border: 1px dashed #6b7280; border-radius:3px;"
        )
        self.btn_nodata_color.clicked.connect(self._pick_nodata_color)
        self.le_nodata_hex = QLineEdit("transparent")
        self.le_nodata_hex.setFixedWidth(90); self.le_nodata_hex.setReadOnly(True)
        nd_row.addWidget(self.btn_nodata_color); nd_row.addWidget(self.le_nodata_hex)
        nd_row.addStretch()
        disc_outer.addLayout(nd_row)

        self.chk_disc_legend = QCheckBox("Show Discrete Legend")
        self.chk_disc_legend.setChecked(True)
        disc_outer.addWidget(self.chk_disc_legend)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #374151;"); disc_outer.addWidget(sep)

        lbl_hint = QLabel("Click 'SCAN GRIDCODES' after data is loaded.\n"
                           "Set colour (swatch/hex), label, and decimals per class.")
        lbl_hint.setWordWrap(True)
        lbl_hint.setStyleSheet("color:#9ca3af; font-size:11px;")
        disc_outer.addWidget(lbl_hint)

        self._disc_scroll = QScrollArea()
        self._disc_scroll.setWidgetResizable(True)
        self._disc_scroll.setMinimumHeight(200)
        self._disc_scroll.setFrameShape(QScrollArea.StyledPanel)
        self._disc_classes_container = QWidget()
        self._disc_classes_layout = QVBoxLayout(self._disc_classes_container)
        self._disc_classes_layout.setContentsMargins(4, 4, 4, 4)
        self._disc_classes_layout.setSpacing(4)
        self._disc_classes_layout.addStretch()
        self._disc_scroll.setWidget(self._disc_classes_container)
        disc_outer.addWidget(self._disc_scroll, stretch=1)

        self.tab_color_mode.addTab(tab_disc, "🗂 Discrete")
        self.tab_color_mode.currentChanged.connect(self._trigger_live_update)
        g2_outer.addWidget(self.tab_color_mode)

        self._toggle_stretch_opts()
        self._update_cmap_preview()
        left_layout.addWidget(grp_color)

        # Group 3 — Export
        grp_export = QGroupBox("3. Export")
        g_exp = QVBoxLayout(grp_export)
        g_exp.setSpacing(8); g_exp.setContentsMargins(12, 18, 12, 12)
        self.btn_export = QPushButton("EXPORT IMAGE")
        self.btn_export.setMinimumHeight(34)
        self.btn_export.clicked.connect(self.export_figure)
        g_exp.addWidget(self.btn_export)
        left_layout.addWidget(grp_export)

        left_layout.addStretch()
        left_scroll.setWidget(left_panel)
        self.main_splitter.addWidget(left_scroll)

        # ── CENTRE PANEL ──────────────────────────────────────────────────────
        centre = QWidget()
        centre_lay = QVBoxLayout(centre)
        centre_lay.setContentsMargins(4, 0, 4, 0); centre_lay.setSpacing(8)

        self.fig_map = Figure()
        self.canvas_map = FigureCanvas(self.fig_map)
        self.toolbar_map = NavigationToolbar(self.canvas_map, self)
        self.toolbar_map.setStyleSheet("background-color: transparent; border: none;")

        centre_lay.addWidget(self.toolbar_map)
        centre_lay.addWidget(self.canvas_map)

        self.lbl_status = QLabel("Open or select a raster layer, then click 'READ DATA & RENDER'.")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.lbl_status.setStyleSheet("font-weight: bold; padding: 6px; color: #9ca3af;")
        centre_lay.addWidget(self.lbl_status)
        self.main_splitter.addWidget(centre)

        # ── RIGHT PANEL ───────────────────────────────────────────────────────
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setMinimumWidth(310)
        right_scroll.setFrameShape(QScrollArea.NoFrame)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(12); right_layout.setContentsMargins(8, 4, 4, 4)

        # Group 4 — Display
        grp_disp = QGroupBox("4. Display Control")
        gg = QGridLayout(grp_disp)
        gg.setSpacing(10); gg.setContentsMargins(12, 18, 12, 12)

        gg.addWidget(QLabel("Background:"), 0, 0)
        self.cb_bg_color = QComboBox()
        self.cb_bg_color.addItems(["Soft Black", "White", "Transparent (Dark Text)", "Transparent (Light Text)"])
        gg.addWidget(self.cb_bg_color, 0, 1, 1, 3)

        self.chk_legend = QCheckBox("Show Colorbar / Legend")
        self.chk_legend.setChecked(True)
        gg.addWidget(self.chk_legend, 1, 0, 1, 4)

        self.chk_axes = QCheckBox("Show Coordinate Axes")
        self.chk_axes.setChecked(True)
        gg.addWidget(self.chk_axes, 2, 0, 1, 4)

        self.chk_grid = QCheckBox("Show Grid Lines")
        self.chk_grid.setChecked(True)
        gg.addWidget(self.chk_grid, 3, 0, 1, 4)

        right_layout.addWidget(grp_disp)

        # Group 5 — Title & Font
        grp_font = QGroupBox("5. Title & Font")
        gf = QGridLayout(grp_font)
        gf.setSpacing(10); gf.setContentsMargins(12, 18, 12, 12)

        gf.addWidget(QLabel("Font:"), 0, 0)
        self.cb_font_family = QComboBox()
        self.cb_font_family.addItems(QFontDatabase().families())
        for pref in ["Poppins", "Segoe UI", "Ubuntu"]:
            if pref in QFontDatabase().families():
                self.cb_font_family.setCurrentText(pref); break
        gf.addWidget(self.cb_font_family, 0, 1, 1, 3)

        gf.addWidget(QLabel("Map Title:"), 1, 0)
        self.le_title = QLineEdit("")
        gf.addWidget(self.le_title, 1, 1, 1, 3)

        gf.addWidget(QLabel("Title Size:"), 2, 0)
        self.sp_title_size = QSpinBox(); self.sp_title_size.setRange(6, 40); self.sp_title_size.setValue(14)
        gf.addWidget(self.sp_title_size, 2, 1)

        right_layout.addWidget(grp_font)

        # Group 6 — Map Geometry & Coordinates
        grp_coords = QGroupBox("6. Map Geometry & Coordinates")
        gmc = QGridLayout(grp_coords)
        gmc.setSpacing(10); gmc.setContentsMargins(12, 18, 12, 12)

        gmc.addWidget(QLabel("Pos X:"), 0, 0)
        self.sp_map_x = QDoubleSpinBox(); self.sp_map_x.setRange(0, 1); self.sp_map_x.setSingleStep(0.01); self.sp_map_x.setValue(0.08)
        gmc.addWidget(self.sp_map_x, 0, 1)
        gmc.addWidget(QLabel("Pos Y:"), 0, 2)
        self.sp_map_y = QDoubleSpinBox(); self.sp_map_y.setRange(0, 1); self.sp_map_y.setSingleStep(0.01); self.sp_map_y.setValue(0.12)
        gmc.addWidget(self.sp_map_y, 0, 3)

        gmc.addWidget(QLabel("Width:"), 1, 0)
        self.sp_map_w = QDoubleSpinBox(); self.sp_map_w.setRange(0.05, 1); self.sp_map_w.setSingleStep(0.01); self.sp_map_w.setValue(0.85)
        gmc.addWidget(self.sp_map_w, 1, 1)
        gmc.addWidget(QLabel("Height:"), 1, 2)
        self.sp_map_h = QDoubleSpinBox(); self.sp_map_h.setRange(0.05, 1); self.sp_map_h.setSingleStep(0.01); self.sp_map_h.setValue(0.80)
        gmc.addWidget(self.sp_map_h, 1, 3)

        gmc.addWidget(QLabel("Coord Format:"), 2, 0)
        self.cb_coord_format = QComboBox()
        self.cb_coord_format.addItems([
            "DMS (Degree Minute Second)",
            "DM (Degree Minute)",
            "D (Decimal Degree)",
            "Default (UTM / Metre)",
        ])
        gmc.addWidget(self.cb_coord_format, 2, 1, 1, 3)

        gmc.addWidget(QLabel("Coord Font Size:"), 3, 0)
        self.sp_coord_size = QSpinBox(); self.sp_coord_size.setRange(4, 30); self.sp_coord_size.setValue(9)
        gmc.addWidget(self.sp_coord_size, 3, 1)

        gmc.addWidget(QLabel("Coord Decimals:"), 3, 2)
        self.sp_coord_decimals = QSpinBox()
        self.sp_coord_decimals.setRange(0, 8); self.sp_coord_decimals.setValue(4)
        self.sp_coord_decimals.setToolTip(
            "Number of decimal places shown in coordinate tick labels\n"
            "(applies to Decimal Degree and UTM/Metre modes)"
        )
        gmc.addWidget(self.sp_coord_decimals, 3, 3)

        # ── Label rotation ─────────────────────────────────────────────────
        gmc.addWidget(QLabel("X-label Rotation:"), 4, 0)
        self.sp_xlabel_rotation = QSpinBox()
        self.sp_xlabel_rotation.setRange(0, 360); self.sp_xlabel_rotation.setValue(0)
        self.sp_xlabel_rotation.setSuffix("°")
        self.sp_xlabel_rotation.setToolTip(
            "Rotation of X-axis (longitude) tick labels in degrees.\n"
            "45° or 90° avoids label overlap for dense ticks."
        )
        gmc.addWidget(self.sp_xlabel_rotation, 4, 1)

        gmc.addWidget(QLabel("Y-label Rotation:"), 4, 2)
        self.sp_ylabel_rotation = QSpinBox()
        self.sp_ylabel_rotation.setRange(0, 360); self.sp_ylabel_rotation.setValue(90)
        self.sp_ylabel_rotation.setSuffix("°")
        self.sp_ylabel_rotation.setToolTip(
            "Rotation of Y-axis (latitude) tick labels in degrees.\n"
            "0° = horizontal (easier to read); 90° = vertical (default Matplotlib)."
        )
        gmc.addWidget(self.sp_ylabel_rotation, 4, 3)

        gmc.addWidget(QLabel("X Tick Count:"), 5, 0)
        self.sp_xtick_count = QSpinBox(); self.sp_xtick_count.setRange(2, 20); self.sp_xtick_count.setValue(5)
        gmc.addWidget(self.sp_xtick_count, 5, 1)

        gmc.addWidget(QLabel("Y Tick Count:"), 5, 2)
        self.sp_ytick_count = QSpinBox(); self.sp_ytick_count.setRange(2, 20); self.sp_ytick_count.setValue(5)
        gmc.addWidget(self.sp_ytick_count, 5, 3)

        gmc.addWidget(QLabel("Grid Style:"), 6, 0)
        self.cb_grid_style = QComboBox()
        self.cb_grid_style.addItems(["Solid (-)", "Dashed (--)", "Dotted (:)"])
        self.cb_grid_style.setCurrentText("Dashed (--)")
        gmc.addWidget(self.cb_grid_style, 6, 1, 1, 3)

        right_layout.addWidget(grp_coords)

        # Group 7 — Colorbar
        grp_cbar = QGroupBox("7. Colorbar Layout")
        gcb = QGridLayout(grp_cbar)
        gcb.setSpacing(10); gcb.setContentsMargins(12, 18, 12, 12)

        gcb.addWidget(QLabel("Orientation:"), 0, 0)
        self.cb_orient = QComboBox(); self.cb_orient.addItems(["horizontal", "vertical"])
        gcb.addWidget(self.cb_orient, 0, 1)

        gcb.addWidget(QLabel("End Style:"), 0, 2)
        self.cb_legend_style = QComboBox()
        self.cb_legend_style.addItems(["Both Pointed", "Right Pointed (Max)", "Left Pointed (Min)", "Box (Standard)"])
        gcb.addWidget(self.cb_legend_style, 0, 3)

        gcb.addWidget(QLabel("Colorbar Label:"), 1, 0)
        self.le_cbar_label = QLineEdit("Value")
        gcb.addWidget(self.le_cbar_label, 1, 1, 1, 3)

        gcb.addWidget(QLabel("Pos X:"), 2, 0)
        self.sp_leg_x = QDoubleSpinBox(); self.sp_leg_x.setRange(0, 1); self.sp_leg_x.setSingleStep(0.01); self.sp_leg_x.setValue(0.20)
        gcb.addWidget(self.sp_leg_x, 2, 1)
        gcb.addWidget(QLabel("Pos Y:"), 2, 2)
        self.sp_leg_y = QDoubleSpinBox(); self.sp_leg_y.setRange(0, 1); self.sp_leg_y.setSingleStep(0.01); self.sp_leg_y.setValue(0.05)
        gcb.addWidget(self.sp_leg_y, 2, 3)

        gcb.addWidget(QLabel("Length:"), 3, 0)
        self.sp_leg_w = QDoubleSpinBox(); self.sp_leg_w.setRange(0.01, 1); self.sp_leg_w.setSingleStep(0.01); self.sp_leg_w.setValue(0.60)
        gcb.addWidget(self.sp_leg_w, 3, 1)
        gcb.addWidget(QLabel("Thickness:"), 3, 2)
        self.sp_leg_h = QDoubleSpinBox(); self.sp_leg_h.setRange(0.01, 1); self.sp_leg_h.setSingleStep(0.01); self.sp_leg_h.setValue(0.03)
        gcb.addWidget(self.sp_leg_h, 3, 3)

        gcb.addWidget(QLabel("Label Size:"), 4, 0)
        self.sp_leg_lbl_size = QSpinBox(); self.sp_leg_lbl_size.setRange(6, 30); self.sp_leg_lbl_size.setValue(10)
        gcb.addWidget(self.sp_leg_lbl_size, 4, 1)
        gcb.addWidget(QLabel("Tick Size:"), 4, 2)
        self.sp_leg_tick_size = QSpinBox(); self.sp_leg_tick_size.setRange(6, 30); self.sp_leg_tick_size.setValue(9)
        gcb.addWidget(self.sp_leg_tick_size, 4, 3)

        self.chk_ticks = QCheckBox("Dynamic Ticks"); self.chk_ticks.setChecked(False)
        gcb.addWidget(self.chk_ticks, 5, 0, 1, 2)
        gcb.addWidget(QLabel("Tick Count:"), 5, 2)
        self.sp_tick_count = QSpinBox(); self.sp_tick_count.setRange(2, 30); self.sp_tick_count.setValue(5)
        gcb.addWidget(self.sp_tick_count, 5, 3)

        gcb.addWidget(QLabel("Label Pad:"), 6, 0)
        self.sp_leg_pad_label = QSpinBox(); self.sp_leg_pad_label.setRange(-50, 100); self.sp_leg_pad_label.setValue(5)
        gcb.addWidget(self.sp_leg_pad_label, 6, 1)
        gcb.addWidget(QLabel("Tick Pad:"), 6, 2)
        self.sp_leg_pad_tick = QSpinBox(); self.sp_leg_pad_tick.setRange(-50, 100); self.sp_leg_pad_tick.setValue(2)
        gcb.addWidget(self.sp_leg_pad_tick, 6, 3)

        gcb.addWidget(QLabel("Tick Decimals:"), 7, 0)
        self.sp_cbar_decimals = QSpinBox()
        self.sp_cbar_decimals.setRange(0, 8); self.sp_cbar_decimals.setValue(4)
        self.sp_cbar_decimals.setToolTip(
            "Number of decimal places for colorbar tick labels.\n"
            "Applies to both automatic and fixed tick modes."
        )
        gcb.addWidget(self.sp_cbar_decimals, 7, 1)

        right_layout.addWidget(grp_cbar)

        btn_close = QPushButton("CLOSE")
        btn_close.setMinimumHeight(34)
        btn_close.clicked.connect(self.close)
        right_layout.addWidget(btn_close)
        right_layout.addStretch()
        right_scroll.setWidget(right_panel)
        self.main_splitter.addWidget(right_scroll)

        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setStretchFactor(2, 0)
        self.main_splitter.setSizes([360, 780, 360])
        tab_layout.addWidget(self.main_splitter)

        self.top_tabs.addTab(tab, "🗺  Single Map")

    # ─────────────────────────────────────────────────────────────────────────
    #  TAB 2 — Layout Series
    # ─────────────────────────────────────────────────────────────────────────
    def _build_layout_series_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(8, 8, 8, 8); lay.setSpacing(10)

        # ── Layout grid configuration ─────────────────────────────────────────
        cfg = QGroupBox("Layout Grid Configuration")
        cfg_lay = QHBoxLayout(cfg)
        cfg_lay.setSpacing(16)

        cfg_lay.addWidget(QLabel("Columns:"))
        self.sp_layout_cols = QSpinBox(); self.sp_layout_cols.setRange(1, 6); self.sp_layout_cols.setValue(2)
        cfg_lay.addWidget(self.sp_layout_cols)

        cfg_lay.addWidget(QLabel("Rows:"))
        self.sp_layout_rows = QSpinBox(); self.sp_layout_rows.setRange(1, 6); self.sp_layout_rows.setValue(2)
        cfg_lay.addWidget(self.sp_layout_rows)

        btn_build = QPushButton("BUILD LAYOUT GRID")
        btn_build.setObjectName("btn_primary")
        btn_build.clicked.connect(self._build_layout_slots)
        cfg_lay.addWidget(btn_build)

        cfg_lay.addWidget(QLabel("H-space:"))
        self.sp_hspace = QDoubleSpinBox(); self.sp_hspace.setRange(0, 1); self.sp_hspace.setValue(0.25); self.sp_hspace.setSingleStep(0.05)
        cfg_lay.addWidget(self.sp_hspace)

        cfg_lay.addWidget(QLabel("W-space:"))
        self.sp_wspace = QDoubleSpinBox(); self.sp_wspace.setRange(0, 1); self.sp_wspace.setValue(0.25); self.sp_wspace.setSingleStep(0.05)
        cfg_lay.addWidget(self.sp_wspace)

        cfg_lay.addWidget(QLabel("Fig size (in):"))
        self.sp_fig_w = QSpinBox(); self.sp_fig_w.setRange(6, 40); self.sp_fig_w.setValue(16)
        cfg_lay.addWidget(self.sp_fig_w)
        cfg_lay.addWidget(QLabel("×"))
        self.sp_fig_h = QSpinBox(); self.sp_fig_h.setRange(4, 30); self.sp_fig_h.setValue(10)
        cfg_lay.addWidget(self.sp_fig_h)

        cfg_lay.addStretch()
        lay.addWidget(cfg)

        # ── Slot configuration scroll area ────────────────────────────────────
        self._slot_scroll = QScrollArea()
        self._slot_scroll.setWidgetResizable(True)
        self._slot_scroll.setMinimumHeight(200)
        self._slot_scroll.setMaximumHeight(320)
        self._slot_scroll.setFrameShape(QScrollArea.StyledPanel)
        self._slot_container = QWidget()
        self._slot_layout = QVBoxLayout(self._slot_container)
        self._slot_layout.setSpacing(4); self._slot_layout.setContentsMargins(4, 4, 4, 4)
        self._slot_layout.addStretch()
        self._slot_scroll.setWidget(self._slot_container)
        lay.addWidget(self._slot_scroll)

        # ── Render / export buttons ───────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_render_layout = QPushButton("READ ALL & RENDER LAYOUT")
        btn_render_layout.setObjectName("btn_primary")
        btn_render_layout.setMinimumHeight(34)
        btn_render_layout.clicked.connect(self._render_layout)
        btn_row.addWidget(btn_render_layout)

        btn_export_layout = QPushButton("EXPORT LAYOUT")
        btn_export_layout.setMinimumHeight(34)
        btn_export_layout.clicked.connect(self._export_layout)
        btn_row.addWidget(btn_export_layout)
        lay.addLayout(btn_row)

        # ── Layout canvas ─────────────────────────────────────────────────────
        self.fig_layout = Figure()
        self.canvas_layout = FigureCanvas(self.fig_layout)
        self.toolbar_layout = NavigationToolbar(self.canvas_layout, self)
        self.toolbar_layout.setStyleSheet("background-color: transparent; border: none;")
        lay.addWidget(self.toolbar_layout)
        lay.addWidget(self.canvas_layout, stretch=1)

        self.lbl_layout_status = QLabel("Configure the grid above and click 'BUILD LAYOUT GRID'.")
        self.lbl_layout_status.setAlignment(Qt.AlignCenter)
        self.lbl_layout_status.setStyleSheet("color: #9ca3af; padding: 4px;")
        lay.addWidget(self.lbl_layout_status)

        self.top_tabs.addTab(tab, "📐 Layout Series")

    # ─── Discrete helpers ──────────────────────────────────────────────────────
    def _scan_discrete_classes(self):
        if self._cached_arr is None:
            QMessageBox.warning(self, "No Data",
                                "Click 'READ DATA & RENDER' first before scanning gridcodes.")
            return
        valid = self._cached_arr[np.isfinite(self._cached_arr)]
        if len(valid) == 0:
            QMessageBox.warning(self, "Empty Data", "No valid (finite) pixel values detected.")
            return
        unique_vals = np.unique(valid)
        if len(unique_vals) > 100:
            ret = QMessageBox.question(
                self, "Many Classes",
                f"{len(unique_vals)} unique values detected.\n"
                f"Continue building {len(unique_vals)} class rows?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if ret != QMessageBox.Yes:
                return
        self._build_discrete_rows(unique_vals)
        self._trigger_live_update()

    def _build_discrete_rows(self, unique_vals):
        for row in self._discrete_rows:
            row.setParent(None); row.deleteLater()
        self._discrete_rows.clear()
        palette = DiscreteClassRow.DEFAULT_PALETTE
        current_dec = self.sp_global_decimals.value()
        for i, v in enumerate(unique_vals):
            color = palette[i % len(palette)]
            is_int = float(v).is_integer()
            label = str(int(v)) if is_int else f"{v:.{current_dec}f}"
            row_w = DiscreteClassRow(
                gridcode=v, color_hex=color, label=label,
                decimals=current_dec, parent=self._disc_classes_container,
            )
            row_w.le_label.textChanged.connect(self._trigger_live_update)
            row_w.sp_decimals.valueChanged.connect(self._trigger_live_update)
            row_w.le_hex.textChanged.connect(self._trigger_live_update)
            row_w.btn_color.clicked.connect(self._trigger_live_update)
            n = self._disc_classes_layout.count()
            self._disc_classes_layout.insertWidget(n - 1, row_w)
            self._discrete_rows.append(row_w)

    def _apply_global_decimals(self):
        dec = self.sp_global_decimals.value()
        for row in self._discrete_rows:
            row.sp_decimals.blockSignals(True)
            row.sp_decimals.setValue(dec)
            row.sp_decimals.blockSignals(False)
        self._trigger_live_update()

    def _pick_nodata_color(self):
        initial = QColor(self._nodata_color) if QColor(self._nodata_color).isValid() else QColor(Qt.transparent)
        col = QColorDialog.getColor(initial, self, "Choose Nodata Colour", QColorDialog.ShowAlphaChannel)
        if col.isValid():
            if col.alpha() == 0:
                self._nodata_color = "#00000000"
                self.btn_nodata_color.setStyleSheet(
                    "background-color: transparent; border: 1px dashed #6b7280; border-radius:3px;"
                )
                self.le_nodata_hex.setText("transparent")
            else:
                self._nodata_color = col.name()
                self.btn_nodata_color.setStyleSheet(
                    f"background-color:{self._nodata_color}; border:1px solid #6b7280; border-radius:3px;"
                )
                self.le_nodata_hex.setText(self._nodata_color)
        self._trigger_live_update()

    def _is_discrete_mode(self):
        return self.tab_color_mode.currentIndex() == 1

    # ─── Colormap cycler ───────────────────────────────────────────────────────
    def _cmap_prev(self):
        self.cmap_idx = (self.cmap_idx - 1) % len(COLORMAPS)
        self._update_cmap_preview(); self._trigger_live_update()

    def _cmap_next(self):
        self.cmap_idx = (self.cmap_idx + 1) % len(COLORMAPS)
        self._update_cmap_preview(); self._trigger_live_update()

    def _on_reverse_toggled(self):
        self._update_cmap_preview(); self._trigger_live_update()

    def _update_cmap_preview(self):
        cmap_name = COLORMAPS[self.cmap_idx]
        w, h = 250, 24
        pixmap = QPixmap(w, h)
        painter = QPainter(pixmap)
        try:
            suffix = "_r" if self.chk_reverse_cmap.isChecked() else ""
            cmap = plt.get_cmap(cmap_name + suffix)
        except Exception:
            cmap = plt.get_cmap("viridis")
        for x in range(w):
            c = cmap(x / max(1, w - 1))
            painter.setPen(QColor(int(c[0] * 255), int(c[1] * 255), int(c[2] * 255)))
            painter.drawLine(x, 0, x, h)
        painter.end()
        self.lbl_cmap_preview.setPixmap(pixmap)
        self.lbl_cmap_preview.setToolTip(cmap_name)

    # ─── Live-update wiring ────────────────────────────────────────────────────
    def _connect_live_updates(self):
        self.cb_orient.currentTextChanged.connect(self._auto_position_legend)
        for w in [self.cb_stretch, self.cb_legend_style, self.cb_grid_style,
                  self.cb_bg_color, self.cb_coord_format, self.cb_font_family]:
            w.currentIndexChanged.connect(self._trigger_live_update)
        for s in [self.sp_pmin, self.sp_pmax, self.sp_map_x, self.sp_map_y,
                  self.sp_map_w, self.sp_map_h, self.sp_leg_x, self.sp_leg_y,
                  self.sp_leg_w, self.sp_leg_h, self.sp_coord_size, self.sp_title_size,
                  self.sp_leg_lbl_size, self.sp_leg_tick_size, self.sp_tick_count,
                  self.sp_leg_pad_label, self.sp_leg_pad_tick,
                  self.sp_xlabel_rotation, self.sp_ylabel_rotation,
                  self.sp_xtick_count, self.sp_ytick_count,
                  self.sp_coord_decimals, self.sp_cbar_decimals]:
            s.valueChanged.connect(self._trigger_live_update)
        for c in [self.chk_legend, self.chk_ticks, self.chk_axes, self.chk_grid,
                  self.chk_nodata_transp, self.chk_disc_legend]:
            c.toggled.connect(self._trigger_live_update)
        for le in [self.le_vmin, self.le_vmax, self.le_cbar_label, self.le_title]:
            le.textChanged.connect(self._trigger_live_update)

    def _auto_position_legend(self, orient):
        self._is_updating = True
        if orient == "vertical":
            self.sp_leg_x.setValue(0.88); self.sp_leg_y.setValue(0.20)
            self.sp_leg_w.setValue(0.03); self.sp_leg_h.setValue(0.60)
        else:
            self.sp_leg_x.setValue(0.20); self.sp_leg_y.setValue(0.05)
            self.sp_leg_w.setValue(0.60); self.sp_leg_h.setValue(0.03)
        self._is_updating = False
        self._trigger_live_update()

    # ─── Layer helpers ─────────────────────────────────────────────────────────
    def populate_layers(self):
        self.cb_layer.clear()
        layers = [
            lyr for lyr in QgsProject.instance().mapLayers().values()
            if lyr.type() == QgsMapLayerType.RasterLayer
        ]
        for lyr in layers:
            self.cb_layer.addItem(lyr.name(), lyr.id())
        # Also update layout slots
        for slot in self._layout_slots:
            current = slot.cb_layer.currentText()
            slot.cb_layer.clear()
            for lyr in layers:
                slot.cb_layer.addItem(lyr.name(), lyr.id())
            if current:
                slot.cb_layer.setCurrentText(current)

    def _open_raster_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Raster File", "",
            "Raster Files (*.tif *.tiff *.geotiff *.img *.vrt *.nc *.hdf *.h5)",
        )
        if path:
            rlayer = QgsRasterLayer(path, os.path.basename(path))
            if rlayer.isValid():
                QgsProject.instance().addMapLayer(rlayer)
                self.populate_layers()
                self.cb_layer.setCurrentText(rlayer.name())
            else:
                QMessageBox.warning(self, "Error", "Failed to load raster file.")

    def _on_layer_changed(self):
        lyr = self._get_layer()
        if lyr:
            nb = lyr.bandCount()
            for sp in [self.sp_band, self.sp_r, self.sp_g, self.sp_b]:
                sp.setMaximum(nb)

    def _get_layer(self):
        lid = self.cb_layer.currentData()
        if not lid:
            return None
        return QgsProject.instance().mapLayer(lid)

    def _toggle_band_mode(self):
        single = self.rb_single.isChecked()
        self.lbl_band.setVisible(single); self.sp_band.setVisible(single)
        self.btn_cmap_prev.setEnabled(single); self.btn_cmap_next.setEnabled(single)
        self.chk_reverse_cmap.setEnabled(single)
        for w in [self.lbl_r, self.sp_r, self.lbl_g, self.sp_g, self.lbl_b, self.sp_b]:
            w.setVisible(not single)
        self._cached_arr = None; self._cached_rgb = None

    def _toggle_stretch_opts(self):
        mode = self.cb_stretch.currentText()
        pct = "Percentile" in mode; manual = "Manual" in mode
        self.lbl_pmin.setVisible(pct); self.sp_pmin.setVisible(pct)
        self.lbl_pmax.setVisible(pct); self.sp_pmax.setVisible(pct)
        self.lbl_vmin.setVisible(manual); self.le_vmin.setVisible(manual)
        self.lbl_vmax.setVisible(manual); self.le_vmax.setVisible(manual)

    # ─── Data reading ──────────────────────────────────────────────────────────
    def _read_band(self, lyr, band_no, max_px_k=1000):
        provider = lyr.dataProvider()
        extent = lyr.extent()
        width = lyr.width(); height = lyr.height()
        max_px = max_px_k * 1000
        total_px = width * height
        if total_px > max_px:
            scale = (max_px / total_px) ** 0.5
            width = max(1, int(width * scale))
            height = max(1, int(height * scale))
        block = provider.block(band_no, extent, width, height)
        nodata = provider.sourceNoDataValue(band_no)
        has_nodata = provider.sourceHasNoDataValue(band_no)
        arr = np.zeros((height, width), dtype=np.float64)
        for row in range(height):
            for col in range(width):
                arr[row, col] = block.value(row, col)
        if has_nodata:
            mask = np.isclose(arr, nodata, rtol=0, atol=1e-6)
            arr = np.where(mask, np.nan, arr)
        return arr, extent

    def _read_and_render(self):
        lyr = self._get_layer()
        if lyr is None:
            return
        self.lbl_status.setText("Reading raster data… please wait.")
        self.btn_read.setEnabled(False); self.repaint()
        try:
            if self.rb_single.isChecked():
                self._cached_arr, self._cached_ext = self._read_band(lyr, self.sp_band.value(), self.sp_maxpx.value())
                self._cached_rgb = None
            else:
                r, ext = self._read_band(lyr, self.sp_r.value(), self.sp_maxpx.value())
                g, _ = self._read_band(lyr, self.sp_g.value(), self.sp_maxpx.value())
                b, _ = self._read_band(lyr, self.sp_b.value(), self.sp_maxpx.value())
                self._cached_rgb = (r, g, b); self._cached_ext = ext; self._cached_arr = None
            self._trigger_live_update()
            self.lbl_status.setText("Data ready.")
        except Exception as e:
            self.lbl_status.setText(f"Error: {e}")
        finally:
            self.btn_read.setEnabled(True)

    def _trigger_live_update(self):
        if self._is_updating:
            return
        if self._cached_arr is None and self._cached_rgb is None:
            return
        self._live_update()

    def _apply_stretch(self, arr):
        valid = arr[np.isfinite(arr)]
        if len(valid) == 0:
            return 0.0, 1.0
        mode = self.cb_stretch.currentText()
        if mode == "Actual Min-Max":
            vmin, vmax = float(valid.min()), float(valid.max())
        elif "Percentile" in mode:
            vmin = float(np.percentile(valid, self.sp_pmin.value()))
            vmax = float(np.percentile(valid, self.sp_pmax.value()))
        else:  # Manual
            try:
                vmin, vmax = float(self.le_vmin.text()), float(self.le_vmax.text())
            except ValueError:
                vmin, vmax = float(valid.min()), float(valid.max())
        if np.isclose(vmin, vmax):
            vmax = vmin + 1
        return vmin, vmax

    # ─── Coordinate tick formatters ────────────────────────────────────────────
    def _make_lon_formatter(self):
        fmt = self.cb_coord_format.currentText()
        dec = self.sp_coord_decimals.value()

        def formatter(x, pos):
            if "Default" in fmt:
                return f"{x:.{dec}f}"
            val = abs(x); d_lbl = "E" if x >= 0 else "W"
            if "DMS" in fmt:
                d = int(val); m = int((val - d) * 60)
                s = (val - d - m / 60.0) * 3600
                return f"{d}°{m}'{s:.1f}\" {d_lbl}"
            if "DM" in fmt:
                d = int(val); m = (val - d) * 60
                return f"{d}°{m:.{dec}f}' {d_lbl}"
            return f"{val:.{dec}f}° {d_lbl}"
        return formatter

    def _make_lat_formatter(self):
        fmt = self.cb_coord_format.currentText()
        dec = self.sp_coord_decimals.value()

        def formatter(y, pos):
            if "Default" in fmt:
                return f"{y:.{dec}f}"
            val = abs(y); d_lbl = "N" if y >= 0 else "S"
            if "DMS" in fmt:
                d = int(val); m = int((val - d) * 60)
                s = (val - d - m / 60.0) * 3600
                return f"{d}°{m}'{s:.1f}\" {d_lbl}"
            if "DM" in fmt:
                d = int(val); m = (val - d) * 60
                return f"{d}°{m:.{dec}f}' {d_lbl}"
            return f"{val:.{dec}f}° {d_lbl}"
        return formatter

    # ─── Axis styling helper ───────────────────────────────────────────────────
    def _style_axes(self, ax, txt_col, font_fam, fig_bg):
        """Apply coordinate labels, rotation, grid, and spine styling to an axis."""
        coord_size = self.sp_coord_size.value()
        ax.tick_params(colors=txt_col, labelsize=coord_size)

        # Set tick density
        ax.xaxis.set_major_locator(mticker.MaxNLocator(nbins=self.sp_xtick_count.value()))
        ax.yaxis.set_major_locator(mticker.MaxNLocator(nbins=self.sp_ytick_count.value()))

        # Set coordinate formatters
        if "Default" not in self.cb_coord_format.currentText():
            ax.xaxis.set_major_formatter(mticker.FuncFormatter(self._make_lon_formatter()))
            ax.yaxis.set_major_formatter(mticker.FuncFormatter(self._make_lat_formatter()))
        else:
            dec = self.sp_coord_decimals.value()
            ax.xaxis.set_major_formatter(mticker.FormatStrFormatter(f"%.{dec}f"))
            ax.yaxis.set_major_formatter(mticker.FormatStrFormatter(f"%.{dec}f"))

        # Apply label rotation
        x_rot = self.sp_xlabel_rotation.value()
        y_rot = self.sp_ylabel_rotation.value()
        x_ha = "right" if 10 < x_rot < 350 else "center"
        y_ha = "right"

        for tick in ax.get_xticklabels():
            tick.set_fontfamily(font_fam)
            tick.set_rotation(x_rot)
            tick.set_ha(x_ha)
        for tick in ax.get_yticklabels():
            tick.set_fontfamily(font_fam)
            tick.set_rotation(y_rot)
            tick.set_ha(y_ha)

        for sp_item in ax.spines.values():
            sp_item.set_color(txt_col)

        # Grid
        if self.chk_grid.isChecked():
            ls = ("--" if "Dashed" in self.cb_grid_style.currentText()
                  else ":" if "Dotted" in self.cb_grid_style.currentText() else "-")
            ax.grid(True, color=txt_col, linestyle=ls, linewidth=0.4, alpha=0.5)

    # ─── Main render ───────────────────────────────────────────────────────────
    def _get_theme(self):
        bg = self.cb_bg_color.currentText()
        if "Soft Black" in bg:
            return "#2b2b2b", "#2b2b2b", "#e2e8f0"
        if "White" in bg:
            return "white", "white", "black"
        if "Dark Text" in bg:
            return "none", "none", "black"
        return "none", "none", "white"

    def _live_update(self):
        self.fig_map.clf()
        if self._cached_ext is None:
            return

        ext = self._cached_ext
        plot_ext = [ext.xMinimum(), ext.xMaximum(), ext.yMinimum(), ext.yMaximum()]
        fig_bg, ax_bg, txt_col = self._get_theme()
        font_fam = self.cb_font_family.currentText()

        self.fig_map.patch.set_facecolor(fig_bg)

        ax = self.fig_map.add_axes([
            self.sp_map_x.value(), self.sp_map_y.value(),
            self.sp_map_w.value(), self.sp_map_h.value(),
        ])
        if ax_bg != "none":
            ax.set_facecolor(ax_bg)

        title = self.le_title.text()
        if title:
            ax.set_title(title, color=txt_col, fontfamily=font_fam,
                         fontsize=self.sp_title_size.value(), pad=10, fontweight="bold")

        if not self.chk_axes.isChecked():
            ax.axis("off")
        else:
            self._style_axes(ax, txt_col, font_fam, fig_bg)

        # Render branch
        if self._is_discrete_mode() and self.rb_single.isChecked() and self._cached_arr is not None:
            self._render_discrete(ax, ax_bg, txt_col, font_fam, plot_ext)
        elif self.rb_single.isChecked() and self._cached_arr is not None:
            self._render_continuous(ax, ax_bg, txt_col, font_fam, plot_ext)
        elif self.rb_rgb.isChecked() and self._cached_rgb is not None:
            self._render_rgb(ax, plot_ext)

        self.canvas_map.draw()

    # ─── Discrete render ───────────────────────────────────────────────────────
    def _render_discrete(self, ax, ax_bg, txt_col, font_fam, plot_ext):
        arr = self._cached_arr
        if len(self._discrete_rows) == 0:
            valid = arr[np.isfinite(arr)]
            if len(valid) > 0:
                unique_vals = np.unique(valid)
                if len(unique_vals) <= 100:
                    self._build_discrete_rows(unique_vals)
                else:
                    self.lbl_status.setText("Too many unique values. Click 'SCAN GRIDCODES' to confirm.")
                    return

        rows = self._discrete_rows
        if not rows:
            return

        height, width = arr.shape
        rgba = np.zeros((height, width, 4), dtype=np.uint8)
        nodata_qcol = QColor(self._nodata_color)
        if nodata_qcol.isValid() and nodata_qcol.alpha() > 0:
            nd_rgba = np.array(
                [nodata_qcol.red(), nodata_qcol.green(), nodata_qcol.blue(), nodata_qcol.alpha()],
                dtype=np.uint8,
            )
        else:
            nd_rgba = np.array([0, 0, 0, 0], dtype=np.uint8)
        rgba[~np.isfinite(arr)] = nd_rgba

        for row_w in rows:
            gc = row_w.gridcode
            qc = QColor(row_w.get_color())
            if not qc.isValid():
                qc = QColor("#888888")
            mask = np.isfinite(arr) & np.isclose(arr, gc, rtol=0, atol=0.5)
            rgba[mask] = [qc.red(), qc.green(), qc.blue(), 255]

        ax.imshow(rgba, extent=plot_ext, interpolation="nearest", aspect="equal", origin="upper")

        if self.chk_legend.isChecked() and self.chk_disc_legend.isChecked():
            patches = []
            for row_w in rows:
                dec = row_w.get_decimals(); gc = row_w.gridcode
                is_int = float(gc).is_integer()
                gc_str = str(int(gc)) if (is_int and dec == 0) else f"{gc:.{dec}f}"
                lbl = row_w.get_label()
                display_lbl = f"{lbl}  ({gc_str})" if lbl != gc_str else lbl
                patches.append(mpatches.Patch(
                    facecolor=row_w.get_color(), edgecolor=txt_col,
                    linewidth=0.6, label=display_lbl,
                ))
            ncol = max(1, (len(patches) + 11) // 12)
            leg = self.fig_map.legend(
                handles=patches, loc="lower left",
                bbox_to_anchor=(self.sp_leg_x.value(), self.sp_leg_y.value()),
                bbox_transform=self.fig_map.transFigure,
                framealpha=0.85,
                facecolor=ax_bg if ax_bg != "none" else "#2b2b2b",
                edgecolor=txt_col,
                fontsize=self.sp_leg_tick_size.value(),
                title=self.le_cbar_label.text(),
                title_fontsize=self.sp_leg_lbl_size.value(),
                ncol=ncol,
            )
            leg.get_title().set_color(txt_col)
            leg.get_title().set_fontfamily(font_fam)
            leg.get_title().set_fontweight("bold")
            for text in leg.get_texts():
                text.set_color(txt_col); text.set_fontfamily(font_fam)

    # ─── Continuous render ─────────────────────────────────────────────────────
    def _render_continuous(self, ax, ax_bg, txt_col, font_fam, plot_ext,
                            cmap_override=None, vmin_override=None, vmax_override=None,
                            show_colorbar=True):
        arr = self._cached_arr
        valid_data = arr[np.isfinite(arr)]
        vmin, vmax = (vmin_override, vmax_override) if vmin_override is not None else self._apply_stretch(arr)
        actual_min = float(valid_data.min()) if len(valid_data) > 0 else vmin
        actual_max = float(valid_data.max()) if len(valid_data) > 0 else vmax

        cmap_name = cmap_override if cmap_override else COLORMAPS[self.cmap_idx]
        if not cmap_override and self.chk_reverse_cmap.isChecked():
            cmap_name += "_r"
        try:
            cmap = plt.get_cmap(cmap_name).copy()
        except Exception:
            cmap = plt.get_cmap("viridis").copy()
        if self.chk_nodata_transp.isChecked():
            cmap.set_bad(alpha=0)

        im = ax.imshow(
            arr, cmap=cmap, vmin=vmin, vmax=vmax,
            extent=plot_ext, interpolation="bilinear", aspect="equal", origin="upper",
        )

        if show_colorbar and self.chk_legend.isChecked():
            cax = self.fig_map.add_axes([
                self.sp_leg_x.value(), self.sp_leg_y.value(),
                self.sp_leg_w.value(), self.sp_leg_h.value(),
            ])
            extend_opt = self.cb_legend_style.currentText()
            extend_str = ("both" if "Both" in extend_opt else
                          "max" if "Right" in extend_opt else
                          "min" if "Left" in extend_opt else "neither")
            cb = self.fig_map.colorbar(
                im, cax=cax, orientation=self.cb_orient.currentText(),
                extend=extend_str, extendfrac=0.04, drawedges=False,
            )
            cb.set_label(
                self.le_cbar_label.text(), color=txt_col, fontfamily=font_fam,
                fontsize=self.sp_leg_lbl_size.value(), fontweight="bold",
                labelpad=self.sp_leg_pad_label.value(),
            )
            cb.ax.tick_params(colors=txt_col, labelsize=self.sp_leg_tick_size.value(),
                              pad=self.sp_leg_pad_tick.value())
            for tick in cb.ax.get_xticklabels() + cb.ax.get_yticklabels():
                tick.set_fontfamily(font_fam)

            dec = self.sp_cbar_decimals.value()
            tc = self.sp_tick_count.value()
            if self.chk_ticks.isChecked():
                cb.locator = mticker.MaxNLocator(nbins=tc, prune="both")
                cb.update_ticks()
            else:
                ticks_pos = np.linspace(vmin, vmax, tc)
                cb.set_ticks(ticks_pos)
                if tc == 2:
                    cb.set_ticklabels([f"{actual_min:.{dec}f}", f"{actual_max:.{dec}f}"])
                else:
                    lbls = (
                        [f"{actual_min:.{dec}f}"]
                        + [f"{t:.{dec}f}" for t in ticks_pos[1:-1]]
                        + [f"{actual_max:.{dec}f}"]
                    )
                    cb.set_ticklabels(lbls)
            cb.outline.set_edgecolor(txt_col); cb.outline.set_linewidth(0.8)

        return im

    # ─── RGB render ────────────────────────────────────────────────────────────
    def _render_rgb(self, ax, plot_ext):
        def norm(a):
            v0, v1 = self._apply_stretch(a)
            a_c = np.clip(a, v0, v1)
            return (a_c - v0) / (v1 - v0 + 1e-12)
        rgb = np.dstack([
            norm(self._cached_rgb[0]),
            norm(self._cached_rgb[1]),
            norm(self._cached_rgb[2]),
        ])
        ax.imshow(rgb, extent=plot_ext, interpolation="bilinear", aspect="equal", origin="upper")

    # ─── Export single map ─────────────────────────────────────────────────────
    def export_figure(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Image", "",
            "PNG (*.png);;SVG (*.svg);;TIFF (*.tif);;PDF (*.pdf)",
        )
        if not path:
            return
        dpi = 300 if path.lower().endswith((".png", ".tif")) else 150
        self.fig_map.savefig(
            path, dpi=dpi, bbox_inches="tight",
            facecolor=self.fig_map.get_facecolor(),
            transparent=("Transparent" in self.cb_bg_color.currentText()),
        )
        self.lbl_status.setText(f"Exported: {path}")
        QMessageBox.information(self, "Success", f"Image saved:\n{path}")

    # ─────────────────────────────────────────────────────────────────────────
    #  Layout Series Methods
    # ─────────────────────────────────────────────────────────────────────────
    def _build_layout_slots(self):
        """Create slot configuration rows for the chosen grid dimensions."""
        for slot in self._layout_slots:
            slot.setParent(None); slot.deleteLater()
        self._layout_slots.clear()
        self._layout_cache.clear()

        n_rows = self.sp_layout_rows.value()
        n_cols = self.sp_layout_cols.value()
        n_slots = n_rows * n_cols

        raster_layers = [
            lyr for lyr in QgsProject.instance().mapLayers().values()
            if lyr.type() == QgsMapLayerType.RasterLayer
        ]

        for i in range(n_slots):
            slot = LayoutSlotWidget(i)
            for lyr in raster_layers:
                slot.cb_layer.addItem(lyr.name(), lyr.id())
            n = self._slot_layout.count()
            self._slot_layout.insertWidget(n - 1, slot)
            self._layout_slots.append(slot)

        self.lbl_layout_status.setText(
            f"Layout grid: {n_rows} rows × {n_cols} cols = {n_slots} maps. "
            "Configure each slot then click 'READ ALL & RENDER LAYOUT'."
        )

    def _render_layout(self):
        """Read data for all slots and render the multi-map figure."""
        if not self._layout_slots:
            QMessageBox.warning(self, "No Layout",
                                "Click 'BUILD LAYOUT GRID' first to configure the layout.")
            return

        n_rows = self.sp_layout_rows.value()
        n_cols = self.sp_layout_cols.value()
        n_slots = n_rows * n_cols

        fig_bg, ax_bg, txt_col = self._get_theme()
        font_fam = self.cb_font_family.currentText()

        self.lbl_layout_status.setText("Reading data for all slots… please wait.")
        self.repaint()

        self.fig_layout.clf()
        self.fig_layout.set_size_inches(self.sp_fig_w.value(), self.sp_fig_h.value())
        self.fig_layout.patch.set_facecolor(fig_bg)

        gs = gridspec.GridSpec(
            n_rows, n_cols,
            figure=self.fig_layout,
            hspace=self.sp_hspace.value(),
            wspace=self.sp_wspace.value(),
        )

        for i, slot in enumerate(self._layout_slots[:n_slots]):
            row_i = i // n_cols
            col_i = i % n_cols
            ax = self.fig_layout.add_subplot(gs[row_i, col_i])
            if ax_bg != "none":
                ax.set_facecolor(ax_bg)

            # Retrieve layer
            lid = slot.cb_layer.currentData()
            lyr = QgsProject.instance().mapLayer(lid) if lid else None
            if lyr is None:
                ax.text(0.5, 0.5, "No layer\nselected",
                        ha="center", va="center", color=txt_col, transform=ax.transAxes)
                ax.set_title(slot.le_title.text(), color=txt_col, fontfamily=font_fam, fontsize=10)
                continue

            # Read band
            try:
                arr, extent = self._read_band(lyr, slot.sp_band.value(), max_px_k=500)
            except Exception as e:
                ax.text(0.5, 0.5, f"Read error:\n{e}",
                        ha="center", va="center", color="#ef4444", transform=ax.transAxes,
                        fontsize=8, wrap=True)
                continue

            plot_ext = [
                extent.xMinimum(), extent.xMaximum(),
                extent.yMinimum(), extent.yMaximum(),
            ]

            # Stretch
            valid_data = arr[np.isfinite(arr)]
            stretch_mode = slot.cb_stretch.currentText()
            if len(valid_data) > 0:
                if "Actual" in stretch_mode:
                    vmin, vmax = float(valid_data.min()), float(valid_data.max())
                elif "Percentile" in stretch_mode:
                    vmin = float(np.percentile(valid_data, 2))
                    vmax = float(np.percentile(valid_data, 98))
                else:
                    vmin, vmax = float(valid_data.min()), float(valid_data.max())
            else:
                vmin, vmax = 0.0, 1.0
            if np.isclose(vmin, vmax):
                vmax = vmin + 1

            # Colormap
            cmap_name = slot.cb_cmap.currentText()
            try:
                cmap = plt.get_cmap(cmap_name).copy()
            except Exception:
                cmap = plt.get_cmap("viridis").copy()
            cmap.set_bad(alpha=0)

            im = ax.imshow(
                arr, cmap=cmap, vmin=vmin, vmax=vmax,
                extent=plot_ext, interpolation="bilinear",
                aspect="equal", origin="upper",
            )

            # Colorbar for this sub-map
            if slot.chk_colorbar.isChecked():
                cb = self.fig_layout.colorbar(im, ax=ax, fraction=0.04, pad=0.02,
                                               extend="both", extendfrac=0.04)
                cb.ax.tick_params(colors=txt_col, labelsize=7)
                cb.outline.set_edgecolor(txt_col)
                for tick in cb.ax.get_xticklabels() + cb.ax.get_yticklabels():
                    tick.set_fontfamily(font_fam)

            # Coordinate styling
            ax.tick_params(colors=txt_col, labelsize=self.sp_coord_size.value())
            x_rot = self.sp_xlabel_rotation.value()
            y_rot = self.sp_ylabel_rotation.value()
            x_ha = "right" if 10 < x_rot < 350 else "center"
            for tick in ax.get_xticklabels():
                tick.set_rotation(x_rot); tick.set_ha(x_ha); tick.set_fontfamily(font_fam)
            for tick in ax.get_yticklabels():
                tick.set_rotation(y_rot); tick.set_ha("right"); tick.set_fontfamily(font_fam)
            for sp_item in ax.spines.values():
                sp_item.set_color(txt_col)

            # Grid lines
            if self.chk_grid.isChecked():
                ls = ("--" if "Dashed" in self.cb_grid_style.currentText()
                      else ":" if "Dotted" in self.cb_grid_style.currentText() else "-")
                ax.grid(True, color=txt_col, linestyle=ls, linewidth=0.3, alpha=0.4)

            # Title
            ax.set_title(slot.le_title.text(), color=txt_col, fontfamily=font_fam,
                         fontsize=self.sp_title_size.value(), fontweight="bold", pad=6)

        self.canvas_layout.draw()
        self.lbl_layout_status.setText(
            f"Layout rendered: {n_rows}×{n_cols} maps. Ready to export."
        )

    def _export_layout(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Layout", "",
            "PNG (*.png);;SVG (*.svg);;TIFF (*.tif);;PDF (*.pdf)",
        )
        if not path:
            return
        dpi = 300 if path.lower().endswith((".png", ".tif")) else 150
        self.fig_layout.savefig(
            path, dpi=dpi, bbox_inches="tight",
            facecolor=self.fig_layout.get_facecolor(),
            transparent=("Transparent" in self.cb_bg_color.currentText()),
        )
        self.lbl_layout_status.setText(f"Layout exported: {path}")
        QMessageBox.information(self, "Success", f"Layout saved:\n{path}")