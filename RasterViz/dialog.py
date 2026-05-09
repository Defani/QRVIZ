"""
dialog.py — Main GUI dialog for RasterViz.

Features
--------
* Native QGIS Theme matching (no forced CSS styles).
* Single-band continuous rendering with percentile / min-max / manual stretch.
* Discrete / classified rendering with per-class colour, label, and decimal.
* RGB three-band composite.
* All rasterio-style colormaps (custom + full Matplotlib library).
* Top Toolbar for quick access (Titles, Fonts, Add Text, Move Elements).
* Advanced Discrete Legend (Shapes, Gridcode toggle, Label Padding).
* Multi-map layout series with Tabbed UI and LIVE UPDATE.
* INTERACTIVE CURSOR SELECTION: Drag-and-drop Colorbars, Legends, and Texts!
* Global Export button (PNG 300 DPI, SVG, TIFF, PDF).

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
    QColorDialog, QFrame, QFormLayout, QInputDialog
)
from qgis.PyQt.QtGui import (
    QFontDatabase, QPixmap, QPainter, QColor, QFont, QCursor
)
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsProject, QgsMapLayerType, QgsRasterLayer

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec

from .colormaps import COLORMAPS


def create_groupbox(title):
    gb = QGroupBox(title)
    f = gb.font()
    f.setBold(True)
    gb.setFont(f)
    return gb


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
        self.le_hex.textChanged.connect(self._on_hex_changed)
        row.addWidget(self.le_hex)

        lbl_val = QLabel(f"<b>{gridcode}</b>")
        lbl_val.setFixedWidth(46)
        lbl_val.setAlignment(Qt.AlignCenter)
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
                f"border:1px solid #888; border-radius:3px; font-size:9px;"
            )
        else:
            self.btn_color.setStyleSheet(
                "background-color:#888888; border:1px solid #888; border-radius:3px;"
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
        if not t.startswith("#"): t = "#" + t
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


class LayoutSlotWidget(QWidget):
    def __init__(self, slot_index, visual_changed_cb, parent=None):
        super().__init__(parent)
        self.slot_index = slot_index
        self.visual_changed_cb = visual_changed_cb
        
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 12, 8, 8)
        lay.setSpacing(12)
        
        form = QFormLayout()
        form.setSpacing(10)

        self.cb_layer = QComboBox()
        self.cb_layer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.sp_band = QSpinBox()
        self.sp_band.setRange(1, 100)
        
        lay_band_row = QHBoxLayout()
        lay_band_row.addWidget(self.cb_layer, stretch=1)
        lay_band_row.addWidget(QLabel("Band:"))
        lay_band_row.addWidget(self.sp_band)
        form.addRow("Layer Source:", lay_band_row)

        self.le_title = QLineEdit(f"Map {slot_index + 1}")
        self.le_title.textChanged.connect(self._trigger_visual)
        self.le_subtitle = QLineEdit("")
        self.le_subtitle.textChanged.connect(self._trigger_visual)
        
        title_row = QHBoxLayout()
        title_row.addWidget(self.le_title)
        title_row.addWidget(QLabel("Sub:"))
        title_row.addWidget(self.le_subtitle)
        form.addRow("Titles:", title_row)

        self.cb_cmap = QComboBox()
        self.cb_cmap.addItems(COLORMAPS)
        if "NDVI_Custom" in COLORMAPS:
            self.cb_cmap.setCurrentText("NDVI_Custom")
        self.cb_cmap.currentIndexChanged.connect(self._trigger_visual)
        
        self.chk_reverse = QCheckBox("Reverse")
        self.chk_reverse.toggled.connect(self._trigger_visual)
        
        cmap_row = QHBoxLayout()
        cmap_row.addWidget(self.cb_cmap, stretch=1)
        cmap_row.addWidget(self.chk_reverse)
        form.addRow("Colormap:", cmap_row)

        self.cb_stretch = QComboBox()
        self.cb_stretch.addItems(["Percentile 2-98", "Actual Min-Max", "Manual"])
        self.cb_stretch.currentIndexChanged.connect(self._toggle_stretch)
        form.addRow("Stretch:", self.cb_stretch)

        val_row = QHBoxLayout()
        self.lbl_v1 = QLabel("Pmin:")
        self.sp_v1 = QDoubleSpinBox()
        self.sp_v1.setRange(-99999, 99999); self.sp_v1.setValue(2); self.sp_v1.setSingleStep(0.5)
        self.sp_v1.valueChanged.connect(self._trigger_visual)
        
        self.lbl_v2 = QLabel("Pmax:")
        self.sp_v2 = QDoubleSpinBox()
        self.sp_v2.setRange(-99999, 99999); self.sp_v2.setValue(98); self.sp_v2.setSingleStep(0.5)
        self.sp_v2.valueChanged.connect(self._trigger_visual)
        
        val_row.addWidget(self.lbl_v1); val_row.addWidget(self.sp_v1)
        val_row.addWidget(self.lbl_v2); val_row.addWidget(self.sp_v2)
        form.addRow("Bounds:", val_row)

        self.chk_colorbar = QCheckBox("Show Colorbar on this Map")
        self.chk_colorbar.setChecked(True)
        self.chk_colorbar.toggled.connect(self._trigger_visual)
        form.addRow("", self.chk_colorbar)

        lay.addLayout(form)
        lay.addStretch()

    def _toggle_stretch(self):
        mode = self.cb_stretch.currentText()
        self.sp_v1.blockSignals(True); self.sp_v2.blockSignals(True)
        if "Percentile" in mode:
            self.lbl_v1.setText("Pmin:"); self.sp_v1.setValue(2)
            self.lbl_v2.setText("Pmax:"); self.sp_v2.setValue(98)
            self.sp_v1.setEnabled(True); self.sp_v2.setEnabled(True)
        elif "Manual" in mode:
            self.lbl_v1.setText("Vmin:"); self.sp_v1.setValue(0)
            self.lbl_v2.setText("Vmax:"); self.sp_v2.setValue(1)
            self.sp_v1.setEnabled(True); self.sp_v2.setEnabled(True)
        else:
            self.lbl_v1.setText("Vmin:"); self.lbl_v2.setText("Vmax:")
            self.sp_v1.setEnabled(False); self.sp_v2.setEnabled(False)
        self.sp_v1.blockSignals(False); self.sp_v2.blockSignals(False)
        self._trigger_visual()

    def _trigger_visual(self):
        if hasattr(self, "visual_changed_cb") and self.visual_changed_cb:
            self.visual_changed_cb()


class QRVIZDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.setWindowFlags(Qt.Window)
        self.setWindowTitle("RasterViz — Scientific Raster Visualization")
        self.setMinimumSize(1400, 820)

        families = QFontDatabase().families()
        pref_fonts = ["Poppins", "Segoe UI", "Ubuntu", "Arial"]
        chosen = next((f for f in pref_fonts if f in families), "")
        if chosen:
            self.setFont(QFont(chosen))

        # Core data
        self._cached_arr = None
        self._cached_rgb = None
        self._cached_ext = None
        self._is_updating = False
        self._discrete_rows = []
        self._nodata_color = "#00000000"
        
        # Interactive Drag System Variables
        self._move_mode = False
        self._drag_item = None
        self._drag_offset = (0, 0)
        self._current_cbar_ax = None
        self._current_legend = None
        self._current_texts = []
        self._title_obj = None
        self._subtitle_obj = None
        self._custom_texts = [] 
        
        # Stored text positions for persistence
        self._pos_title = None
        self._pos_subtitle = None

        # Layout Cache
        self._layout_slots = []
        self._layout_cache = {}
        self._is_updating_layout = False

        self._build_ui()
        self._connect_live_updates()
        self.showMaximized()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # ---------------- TOP TOOLBAR (Quick Access) ----------------
        top_bar = QHBoxLayout()
        top_bar.setSpacing(12)

        lbl_title = QLabel("RasterViz")
        f = self.font(); f.setPointSize(14); f.setBold(True); lbl_title.setFont(f)
        top_bar.addWidget(lbl_title)
        
        line1 = QFrame(); line1.setFrameShape(QFrame.VLine); top_bar.addWidget(line1)

        top_bar.addWidget(QLabel("Title:"))
        self.le_title = QLineEdit("My Raster Map")
        self.le_title.setFixedWidth(120)
        top_bar.addWidget(self.le_title)

        top_bar.addWidget(QLabel("Sub:"))
        self.le_subtitle = QLineEdit("")
        self.le_subtitle.setFixedWidth(120)
        top_bar.addWidget(self.le_subtitle)

        self.cb_font_family = QComboBox()
        self.cb_font_family.addItems(QFontDatabase().families())
        self.cb_font_family.setCurrentText(self.font().family())
        self.cb_font_family.setFixedWidth(120)
        top_bar.addWidget(self.cb_font_family)
        
        self.sp_title_size = QSpinBox(); self.sp_title_size.setRange(6, 40); self.sp_title_size.setValue(14)
        top_bar.addWidget(self.sp_title_size)

        line2 = QFrame(); line2.setFrameShape(QFrame.VLine); top_bar.addWidget(line2)

        self.btn_add_text = QPushButton("➕ Add Text")
        self.btn_add_text.clicked.connect(self._add_custom_text)
        top_bar.addWidget(self.btn_add_text)

        # Cursor Selection Tool for moving elements
        self.btn_move_mode = QPushButton("✋ Drag Elements: OFF")
        self.btn_move_mode.setCheckable(True)
        self.btn_move_mode.toggled.connect(self._toggle_move_mode)
        top_bar.addWidget(self.btn_move_mode)

        top_bar.addStretch()

        self.btn_global_export = QPushButton("💾 EXPORT")
        self.btn_global_export.setMinimumHeight(32); self.btn_global_export.setMinimumWidth(120)
        f_btn = self.btn_global_export.font(); f_btn.setBold(True); self.btn_global_export.setFont(f_btn)
        self.btn_global_export.clicked.connect(self._export_current_tab)
        top_bar.addWidget(self.btn_global_export)

        main_layout.addLayout(top_bar)

        # ---------------- MAIN TABS ----------------
        self.top_tabs = QTabWidget()
        main_layout.addWidget(self.top_tabs, stretch=1)

        self._build_single_map_tab()
        self._build_layout_series_tab()

    # ========================== SINGLE MAP TAB ==========================
    def _build_single_map_tab(self):
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(4, 4, 4, 4)

        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setHandleWidth(8)

        # ----- LEFT PANEL -----
        left_scroll = QScrollArea(); left_scroll.setWidgetResizable(True); left_scroll.setMinimumWidth(340)
        left_scroll.setFrameShape(QScrollArea.NoFrame)
        left_panel = QWidget(); left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(12); left_layout.setContentsMargins(4, 4, 8, 4)

        grp_layer = create_groupbox("Layer & Band")
        g1 = QVBoxLayout(grp_layer); g1.setSpacing(10); g1.setContentsMargins(12, 18, 12, 12)
        self.btn_open = QPushButton("OPEN RASTER FILE"); self.btn_open.setMinimumHeight(30)
        g1.addWidget(self.btn_open); self.btn_open.clicked.connect(self._open_raster_file)

        lay_sel = QHBoxLayout()
        lay_sel.addWidget(QLabel("Layer:")); self.cb_layer = QComboBox(); self.cb_layer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.cb_layer.currentIndexChanged.connect(self._on_layer_changed); lay_sel.addWidget(self.cb_layer)
        g1.addLayout(lay_sel)

        mode_lay = QHBoxLayout()
        self.rb_single = QRadioButton("Single Band"); self.rb_rgb = QRadioButton("RGB"); self.rb_single.setChecked(True)
        bg = QButtonGroup(self); bg.addButton(self.rb_single); bg.addButton(self.rb_rgb)
        self.rb_single.toggled.connect(self._toggle_band_mode)
        mode_lay.addWidget(self.rb_single); mode_lay.addWidget(self.rb_rgb)
        g1.addLayout(mode_lay)

        band_grid = QGridLayout()
        self.lbl_band = QLabel("Band:"); self.sp_band = QSpinBox(); self.sp_band.setMinimum(1); self.sp_band.setMaximum(100)
        band_grid.addWidget(self.lbl_band, 0, 0); band_grid.addWidget(self.sp_band, 0, 1)

        self.lbl_r = QLabel("R:"); self.sp_r = QSpinBox(); self.sp_r.setRange(1, 100); self.sp_r.setValue(1)
        self.lbl_g = QLabel("G:"); self.sp_g = QSpinBox(); self.sp_g.setRange(1, 100); self.sp_g.setValue(2)
        self.lbl_b = QLabel("B:"); self.sp_b = QSpinBox(); self.sp_b.setRange(1, 100); self.sp_b.setValue(3)

        for w in [self.lbl_r, self.sp_r, self.lbl_g, self.sp_g, self.lbl_b, self.sp_b]: w.setVisible(False)
        band_grid.addWidget(self.lbl_r, 1, 0); band_grid.addWidget(self.sp_r, 1, 1)
        band_grid.addWidget(self.lbl_g, 1, 2); band_grid.addWidget(self.sp_g, 1, 3)
        band_grid.addWidget(self.lbl_b, 2, 0); band_grid.addWidget(self.sp_b, 2, 1)
        g1.addLayout(band_grid)

        px_lay = QHBoxLayout()
        px_lay.addWidget(QLabel("Max pixels (k):")); self.sp_maxpx = QSpinBox(); self.sp_maxpx.setRange(50, 10000); self.sp_maxpx.setValue(1000)
        px_lay.addWidget(self.sp_maxpx)
        g1.addLayout(px_lay)

        self.btn_read = QPushButton("READ DATA & RENDER")
        self.btn_read.setMinimumHeight(34)
        f_b = self.btn_read.font(); f_b.setBold(True); self.btn_read.setFont(f_b)
        self.btn_read.clicked.connect(self._read_and_render)
        g1.addWidget(self.btn_read)
        left_layout.addWidget(grp_layer)

        grp_color = create_groupbox("Color Mode & Stretch")
        g2_outer = QVBoxLayout(grp_color); g2_outer.setContentsMargins(8, 18, 8, 8); g2_outer.setSpacing(6)
        self.tab_color_mode = QTabWidget()

        # Continuous Tab
        tab_cont = QWidget(); g2 = QGridLayout(tab_cont); g2.setSpacing(10); g2.setContentsMargins(8, 10, 8, 8)
        g2.addWidget(QLabel("Stretch:"), 0, 0); self.cb_stretch = QComboBox(); self.cb_stretch.addItems(["Actual Min-Max", "Percentile", "Manual Min-Max"])
        self.cb_stretch.currentIndexChanged.connect(self._toggle_stretch_opts); g2.addWidget(self.cb_stretch, 0, 1, 1, 3)

        self.lbl_pmin = QLabel("Pmin (%):"); self.sp_pmin = QDoubleSpinBox(); self.sp_pmin.setRange(0, 49); self.sp_pmin.setValue(2); self.sp_pmin.setSingleStep(0.5)
        self.lbl_pmax = QLabel("Pmax (%):"); self.sp_pmax = QDoubleSpinBox(); self.sp_pmax.setRange(51, 100); self.sp_pmax.setValue(98); self.sp_pmax.setSingleStep(0.5)
        g2.addWidget(self.lbl_pmin, 1, 0); g2.addWidget(self.sp_pmin, 1, 1)
        g2.addWidget(self.lbl_pmax, 1, 2); g2.addWidget(self.sp_pmax, 1, 3)

        self.lbl_vmin = QLabel("vmin:"); self.le_vmin = QLineEdit("0"); self.lbl_vmax = QLabel("vmax:"); self.le_vmax = QLineEdit("1")
        g2.addWidget(self.lbl_vmin, 2, 0); g2.addWidget(self.le_vmin, 2, 1)
        g2.addWidget(self.lbl_vmax, 2, 2); g2.addWidget(self.le_vmax, 2, 3)

        g2.addWidget(QLabel("Colormap:"), 3, 0)
        cmap_lay = QHBoxLayout(); cmap_lay.setContentsMargins(0, 0, 0, 0); cmap_lay.setSpacing(4)
        self.btn_cmap_prev = QPushButton("◀"); self.btn_cmap_prev.setFixedSize(26, 26); self.btn_cmap_prev.clicked.connect(self._cmap_prev)
        self.lbl_cmap_preview = QLabel(); self.lbl_cmap_preview.setFixedHeight(26); self.lbl_cmap_preview.setScaledContents(True)
        self.lbl_cmap_preview.setStyleSheet("border: 1px solid #aaa; border-radius: 4px;")
        self.btn_cmap_next = QPushButton("▶"); self.btn_cmap_next.setFixedSize(26, 26); self.btn_cmap_next.clicked.connect(self._cmap_next)
        cmap_lay.addWidget(self.btn_cmap_prev); cmap_lay.addWidget(self.lbl_cmap_preview, stretch=1); cmap_lay.addWidget(self.btn_cmap_next)
        g2.addLayout(cmap_lay, 3, 1, 1, 3)

        self.cmap_idx = COLORMAPS.index("NDVI_Custom") if "NDVI_Custom" in COLORMAPS else 0
        self.chk_reverse_cmap = QCheckBox("Reverse"); self.chk_reverse_cmap.toggled.connect(self._on_reverse_toggled)
        g2.addWidget(self.chk_reverse_cmap, 4, 1, 1, 3)
        self.chk_nodata_transp = QCheckBox("Transparent Nodata"); self.chk_nodata_transp.setChecked(True)
        g2.addWidget(self.chk_nodata_transp, 5, 0, 1, 4)
        self.tab_color_mode.addTab(tab_cont, "Continuous")

        # Discrete Tab
        tab_disc = QWidget(); disc_outer = QVBoxLayout(tab_disc); disc_outer.setContentsMargins(8, 8, 8, 8); disc_outer.setSpacing(6)
        self.btn_scan_classes = QPushButton("SCAN GRIDCODES"); self.btn_scan_classes.setMinimumHeight(30); self.btn_scan_classes.clicked.connect(self._scan_discrete_classes)
        disc_outer.addWidget(self.btn_scan_classes)

        dec_row = QHBoxLayout(); dec_row.addWidget(QLabel("Set All Decimals:"))
        self.sp_global_decimals = QSpinBox(); self.sp_global_decimals.setRange(0, 6); self.sp_global_decimals.setValue(2); self.sp_global_decimals.setFixedWidth(50)
        dec_row.addWidget(self.sp_global_decimals)
        btn_apply_dec = QPushButton("Apply"); btn_apply_dec.setFixedHeight(26); btn_apply_dec.clicked.connect(self._apply_global_decimals)
        dec_row.addWidget(btn_apply_dec); dec_row.addStretch()
        disc_outer.addLayout(dec_row)

        nd_row = QHBoxLayout(); nd_row.addWidget(QLabel("Nodata Colour:"))
        self.btn_nodata_color = QPushButton(); self.btn_nodata_color.setFixedSize(26, 26); self.btn_nodata_color.setStyleSheet("background-color: transparent; border: 1px dashed #888; border-radius:3px;")
        self.btn_nodata_color.clicked.connect(self._pick_nodata_color)
        self.le_nodata_hex = QLineEdit("transparent"); self.le_nodata_hex.setFixedWidth(90); self.le_nodata_hex.setReadOnly(True)
        nd_row.addWidget(self.btn_nodata_color); nd_row.addWidget(self.le_nodata_hex); nd_row.addStretch()
        disc_outer.addLayout(nd_row)

        self.chk_disc_legend = QCheckBox("Show Discrete Legend"); self.chk_disc_legend.setChecked(True)
        disc_outer.addWidget(self.chk_disc_legend)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        disc_outer.addWidget(sep)

        lbl_hint = QLabel("Click 'SCAN GRIDCODES' after data is loaded.\nSet colour, label, and decimals per class.")
        lbl_hint.setWordWrap(True)
        disc_outer.addWidget(lbl_hint)

        self._disc_scroll = QScrollArea(); self._disc_scroll.setWidgetResizable(True); self._disc_scroll.setMinimumHeight(200); self._disc_scroll.setFrameShape(QScrollArea.StyledPanel)
        self._disc_classes_container = QWidget(); self._disc_classes_layout = QVBoxLayout(self._disc_classes_container)
        self._disc_classes_layout.setContentsMargins(4, 4, 4, 4); self._disc_classes_layout.setSpacing(4); self._disc_classes_layout.addStretch()
        self._disc_scroll.setWidget(self._disc_classes_container)
        disc_outer.addWidget(self._disc_scroll, stretch=1)
        self.tab_color_mode.addTab(tab_disc, "Discrete")
        self.tab_color_mode.currentChanged.connect(self._trigger_live_update)
        
        g2_outer.addWidget(self.tab_color_mode)
        self._toggle_stretch_opts()
        self._update_cmap_preview()
        left_layout.addWidget(grp_color)

        left_layout.addStretch()
        left_scroll.setWidget(left_panel)
        self.main_splitter.addWidget(left_scroll)

        # ----- CENTER PANEL -----
        center_panel = QWidget(); center_lay = QVBoxLayout(center_panel); center_lay.setContentsMargins(4, 0, 4, 0); center_lay.setSpacing(8)
        tb_lay = QHBoxLayout(); tb_lay.setContentsMargins(0,0,0,0)
        btn_fit = QPushButton("Fit View"); btn_fit.clicked.connect(self._fit_view_map)
        btn_zin = QPushButton("Zoom In"); btn_zin.clicked.connect(self._zoom_in_map)
        btn_zout = QPushButton("Zoom Out"); btn_zout.clicked.connect(self._zoom_out_map)
        for b in [btn_fit, btn_zin, btn_zout]:
            fb = b.font(); fb.setBold(True); b.setFont(fb); tb_lay.addWidget(b)
        tb_lay.addStretch(); center_lay.addLayout(tb_lay)

        self.map_scroll = QScrollArea(); self.map_scroll.setWidgetResizable(True); self.map_scroll.setFrameShape(QScrollArea.NoFrame); self.map_scroll.setAlignment(Qt.AlignCenter)
        self.fig_map = Figure(); self.canvas_map = FigureCanvas(self.fig_map)
        self.map_scroll.setWidget(self.canvas_map)
        center_lay.addWidget(self.map_scroll, stretch=1)
        self.lbl_status = QLabel("Open or select a raster layer, then click 'READ DATA & RENDER'."); self.lbl_status.setAlignment(Qt.AlignCenter)
        center_lay.addWidget(self.lbl_status)
        self.main_splitter.addWidget(center_panel)

        # Matplotlib interactive drag hooks
        self.canvas_map.mpl_connect('button_press_event', self._on_drag_press)
        self.canvas_map.mpl_connect('motion_notify_event', self._on_drag_motion)
        self.canvas_map.mpl_connect('button_release_event', self._on_drag_release)

        # ----- RIGHT PANEL -----
        right_scroll = QScrollArea(); right_scroll.setWidgetResizable(True); right_scroll.setMinimumWidth(320); right_scroll.setFrameShape(QScrollArea.NoFrame)
        right_panel = QWidget(); right_layout = QVBoxLayout(right_panel); right_layout.setSpacing(12); right_layout.setContentsMargins(8, 4, 4, 4)

        grp_disp = create_groupbox("Display Control")
        gg = QGridLayout(grp_disp); gg.setSpacing(10); gg.setContentsMargins(12, 18, 12, 12)
        gg.addWidget(QLabel("Background:"), 0, 0)
        self.cb_bg_color = QComboBox(); self.cb_bg_color.addItems(["Soft Black", "White", "Transparent (Dark Text)", "Transparent (Light Text)"])
        gg.addWidget(self.cb_bg_color, 0, 1, 1, 3)
        self.chk_axes = QCheckBox("Show Coordinate Axes"); self.chk_axes.setChecked(True); gg.addWidget(self.chk_axes, 1, 0, 1, 4)
        self.chk_grid = QCheckBox("Show Grid Lines"); self.chk_grid.setChecked(True); gg.addWidget(self.chk_grid, 2, 0, 1, 4)
        right_layout.addWidget(grp_disp)

        grp_coords = create_groupbox("Map Geometry & Coordinates")
        gmc = QGridLayout(grp_coords); gmc.setSpacing(10); gmc.setContentsMargins(12, 18, 12, 12)
        gmc.addWidget(QLabel("Pos X:"), 0, 0); self.sp_map_x = QDoubleSpinBox(); self.sp_map_x.setRange(0, 1); self.sp_map_x.setSingleStep(0.01); self.sp_map_x.setValue(0.08); gmc.addWidget(self.sp_map_x, 0, 1)
        gmc.addWidget(QLabel("Pos Y:"), 0, 2); self.sp_map_y = QDoubleSpinBox(); self.sp_map_y.setRange(0, 1); self.sp_map_y.setSingleStep(0.01); self.sp_map_y.setValue(0.12); gmc.addWidget(self.sp_map_y, 0, 3)
        gmc.addWidget(QLabel("Width:"), 1, 0); self.sp_map_w = QDoubleSpinBox(); self.sp_map_w.setRange(0.05, 1); self.sp_map_w.setSingleStep(0.01); self.sp_map_w.setValue(0.85); gmc.addWidget(self.sp_map_w, 1, 1)
        gmc.addWidget(QLabel("Height:"), 1, 2); self.sp_map_h = QDoubleSpinBox(); self.sp_map_h.setRange(0.05, 1); self.sp_map_h.setSingleStep(0.01); self.sp_map_h.setValue(0.80); gmc.addWidget(self.sp_map_h, 1, 3)

        gmc.addWidget(QLabel("Format:"), 2, 0)
        self.cb_coord_format = QComboBox(); self.cb_coord_format.addItems(["DMS (Degree Minute Second)", "DM (Degree Minute)", "D (Decimal Degree)", "Default (UTM / Metre)"]); gmc.addWidget(self.cb_coord_format, 2, 1, 1, 3)
        gmc.addWidget(QLabel("Coord Size:"), 3, 0); self.sp_coord_size = QSpinBox(); self.sp_coord_size.setRange(4, 30); self.sp_coord_size.setValue(9); gmc.addWidget(self.sp_coord_size, 3, 1)
        gmc.addWidget(QLabel("Coord Dec:"), 3, 2); self.sp_coord_decimals = QSpinBox(); self.sp_coord_decimals.setRange(0, 8); self.sp_coord_decimals.setValue(4); gmc.addWidget(self.sp_coord_decimals, 3, 3)

        gmc.addWidget(QLabel("X-lbl Rot:"), 4, 0); self.sp_xlabel_rotation = QSpinBox(); self.sp_xlabel_rotation.setRange(0, 360); self.sp_xlabel_rotation.setValue(0); self.sp_xlabel_rotation.setSuffix("°"); gmc.addWidget(self.sp_xlabel_rotation, 4, 1)
        gmc.addWidget(QLabel("Y-lbl Rot:"), 4, 2); self.sp_ylabel_rotation = QSpinBox(); self.sp_ylabel_rotation.setRange(0, 360); self.sp_ylabel_rotation.setValue(90); self.sp_ylabel_rotation.setSuffix("°"); gmc.addWidget(self.sp_ylabel_rotation, 4, 3)
        gmc.addWidget(QLabel("X Tick Cnt:"), 5, 0); self.sp_xtick_count = QSpinBox(); self.sp_xtick_count.setRange(2, 20); self.sp_xtick_count.setValue(5); gmc.addWidget(self.sp_xtick_count, 5, 1)
        gmc.addWidget(QLabel("Y Tick Cnt:"), 5, 2); self.sp_ytick_count = QSpinBox(); self.sp_ytick_count.setRange(2, 20); self.sp_ytick_count.setValue(5); gmc.addWidget(self.sp_ytick_count, 5, 3)

        gmc.addWidget(QLabel("Grid Style:"), 6, 0); self.cb_grid_style = QComboBox(); self.cb_grid_style.addItems(["Solid (-)", "Dashed (--)", "Dotted (:)"]); self.cb_grid_style.setCurrentText("Dashed (--)"); gmc.addWidget(self.cb_grid_style, 6, 1, 1, 3)
        right_layout.addWidget(grp_coords)

        # Continuous Colorbar Options
        self.grp_cbar = create_groupbox("Continuous Colorbar Layout")
        gcb = QGridLayout(self.grp_cbar); gcb.setSpacing(10); gcb.setContentsMargins(12, 18, 12, 12)
        
        self.chk_legend = QCheckBox("Show Colorbar"); self.chk_legend.setChecked(True); gcb.addWidget(self.chk_legend, 0, 0, 1, 2)
        
        gcb.addWidget(QLabel("Orient:"), 1, 0); self.cb_orient = QComboBox(); self.cb_orient.addItems(["horizontal", "vertical"]); gcb.addWidget(self.cb_orient, 1, 1)
        gcb.addWidget(QLabel("End Style:"), 1, 2); self.cb_legend_style = QComboBox(); self.cb_legend_style.addItems(["Both Pointed", "Right Pointed (Max)", "Left Pointed (Min)", "Box (Standard)"]); gcb.addWidget(self.cb_legend_style, 1, 3)
        gcb.addWidget(QLabel("Label Text:"), 2, 0); self.le_cbar_label = QLineEdit("Value"); gcb.addWidget(self.le_cbar_label, 2, 1)
        self.chk_cbar_lbl_bold = QCheckBox("Bold"); self.chk_cbar_lbl_bold.setChecked(True); gcb.addWidget(self.chk_cbar_lbl_bold, 2, 2)
        self.cb_cbar_lbl_pos = QComboBox(); self.cb_cbar_lbl_pos.addItems(["Default", "Top", "Bottom", "Right", "Left"]); gcb.addWidget(self.cb_cbar_lbl_pos, 2, 3)
        gcb.addWidget(QLabel("Pos X:"), 3, 0); self.sp_leg_x = QDoubleSpinBox(); self.sp_leg_x.setRange(0, 1); self.sp_leg_x.setSingleStep(0.01); self.sp_leg_x.setValue(0.20); gcb.addWidget(self.sp_leg_x, 3, 1)
        gcb.addWidget(QLabel("Pos Y:"), 3, 2); self.sp_leg_y = QDoubleSpinBox(); self.sp_leg_y.setRange(0, 1); self.sp_leg_y.setSingleStep(0.01); self.sp_leg_y.setValue(0.05); gcb.addWidget(self.sp_leg_y, 3, 3)
        gcb.addWidget(QLabel("Length:"), 4, 0); self.sp_leg_w = QDoubleSpinBox(); self.sp_leg_w.setRange(0.01, 1); self.sp_leg_w.setSingleStep(0.01); self.sp_leg_w.setValue(0.60); gcb.addWidget(self.sp_leg_w, 4, 1)
        gcb.addWidget(QLabel("Thickness:"), 4, 2); self.sp_leg_h = QDoubleSpinBox(); self.sp_leg_h.setRange(0.01, 1); self.sp_leg_h.setSingleStep(0.01); self.sp_leg_h.setValue(0.03); gcb.addWidget(self.sp_leg_h, 4, 3)
        gcb.addWidget(QLabel("Lbl Size:"), 5, 0); self.sp_leg_lbl_size = QSpinBox(); self.sp_leg_lbl_size.setRange(6, 30); self.sp_leg_lbl_size.setValue(10); gcb.addWidget(self.sp_leg_lbl_size, 5, 1)
        gcb.addWidget(QLabel("Tick Size:"), 5, 2); tick_sz_lay = QHBoxLayout(); tick_sz_lay.setContentsMargins(0,0,0,0); self.sp_leg_tick_size = QSpinBox(); self.sp_leg_tick_size.setRange(6, 30); self.sp_leg_tick_size.setValue(9); tick_sz_lay.addWidget(self.sp_leg_tick_size); self.chk_cbar_tick_bold = QCheckBox("Bold"); tick_sz_lay.addWidget(self.chk_cbar_tick_bold); gcb.addLayout(tick_sz_lay, 5, 3)
        self.chk_ticks = QCheckBox("Dynamic Ticks"); self.chk_ticks.setChecked(False); gcb.addWidget(self.chk_ticks, 6, 0, 1, 2)
        gcb.addWidget(QLabel("Tick Count:"), 6, 2); self.sp_tick_count = QSpinBox(); self.sp_tick_count.setRange(2, 30); self.sp_tick_count.setValue(5); gcb.addWidget(self.sp_tick_count, 6, 3)
        gcb.addWidget(QLabel("Lbl Pad:"), 7, 0); self.sp_leg_pad_label = QSpinBox(); self.sp_leg_pad_label.setRange(-50, 100); self.sp_leg_pad_label.setValue(5); gcb.addWidget(self.sp_leg_pad_label, 7, 1)
        gcb.addWidget(QLabel("Tick Pad:"), 7, 2); self.sp_leg_pad_tick = QSpinBox(); self.sp_leg_pad_tick.setRange(-50, 100); self.sp_leg_pad_tick.setValue(2); gcb.addWidget(self.sp_leg_pad_tick, 7, 3)
        gcb.addWidget(QLabel("Tick Dec:"), 8, 0); self.sp_cbar_decimals = QSpinBox(); self.sp_cbar_decimals.setRange(0, 8); self.sp_cbar_decimals.setValue(4); gcb.addWidget(self.sp_cbar_decimals, 8, 1)
        right_layout.addWidget(self.grp_cbar)

        # Discrete Legend Options
        self.grp_disc_leg = create_groupbox("Discrete Legend Layout")
        gdl = QGridLayout(self.grp_disc_leg); gdl.setSpacing(10); gdl.setContentsMargins(12, 18, 12, 12)
        gdl.addWidget(QLabel("Pos X:"), 0, 0); self.sp_dleg_x = QDoubleSpinBox(); self.sp_dleg_x.setRange(0, 1); self.sp_dleg_x.setSingleStep(0.01); self.sp_dleg_x.setValue(0.05); gdl.addWidget(self.sp_dleg_x, 0, 1)
        gdl.addWidget(QLabel("Pos Y:"), 0, 2); self.sp_dleg_y = QDoubleSpinBox(); self.sp_dleg_y.setRange(0, 1); self.sp_dleg_y.setSingleStep(0.01); self.sp_dleg_y.setValue(0.05); gdl.addWidget(self.sp_dleg_y, 0, 3)
        
        gdl.addWidget(QLabel("Shape:"), 1, 0); self.cb_dleg_shape = QComboBox(); self.cb_dleg_shape.addItems(["Box", "Circle"]); gdl.addWidget(self.cb_dleg_shape, 1, 1)
        gdl.addWidget(QLabel("Sym Size:"), 1, 2); self.sp_dleg_symsize = QSpinBox(); self.sp_dleg_symsize.setRange(5, 50); self.sp_dleg_symsize.setValue(10); gdl.addWidget(self.sp_dleg_symsize, 1, 3)
        
        gdl.addWidget(QLabel("Align:"), 2, 0); self.cb_dleg_align = QComboBox(); self.cb_dleg_align.addItems(["left", "center", "right"]); gdl.addWidget(self.cb_dleg_align, 2, 1)
        gdl.addWidget(QLabel("Lbl Pad:"), 2, 2); self.sp_dleg_pad = QDoubleSpinBox(); self.sp_dleg_pad.setRange(0, 2); self.sp_dleg_pad.setSingleStep(0.1); self.sp_dleg_pad.setValue(0.5); gdl.addWidget(self.sp_dleg_pad, 2, 3)
        
        self.chk_dleg_gridcode = QCheckBox("Show Gridcode"); self.chk_dleg_gridcode.setChecked(True)
        gdl.addWidget(self.chk_dleg_gridcode, 3, 0, 1, 2)
        gdl.addWidget(QLabel("Columns:"), 3, 2); self.sp_dleg_cols = QSpinBox(); self.sp_dleg_cols.setRange(1, 10); self.sp_dleg_cols.setValue(1); gdl.addWidget(self.sp_dleg_cols, 3, 3)
        
        right_layout.addWidget(self.grp_disc_leg)

        right_layout.addStretch()
        right_scroll.setWidget(right_panel)
        self.main_splitter.addWidget(right_scroll)

        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setStretchFactor(2, 0)
        self.main_splitter.setSizes([360, 780, 360])
        tab_layout.addWidget(self.main_splitter)

        self.top_tabs.addTab(tab, "Single Map")

    # ========================== LAYOUT SERIES TAB ==========================
    def _build_layout_series_tab(self):
        tab = QWidget()
        tab_lay = QVBoxLayout(tab)
        tab_lay.setContentsMargins(4, 4, 4, 4)

        self.layout_splitter = QSplitter(Qt.Horizontal)
        self.layout_splitter.setHandleWidth(8)

        # ----- LEFT PANEL -----
        left_panel = QWidget(); left_lay = QVBoxLayout(left_panel); left_lay.setSpacing(12); left_lay.setContentsMargins(4, 4, 8, 4); left_panel.setMinimumWidth(340)

        cfg = create_groupbox("Grid Setup")
        cfg_lay = QGridLayout(cfg); cfg_lay.setSpacing(10); cfg_lay.setContentsMargins(12, 18, 12, 12)
        cfg_lay.addWidget(QLabel("Cols:"), 0, 0); self.sp_layout_cols = QSpinBox(); self.sp_layout_cols.setRange(1, 6); self.sp_layout_cols.setValue(2); cfg_lay.addWidget(self.sp_layout_cols, 0, 1)
        cfg_lay.addWidget(QLabel("Rows:"), 0, 2); self.sp_layout_rows = QSpinBox(); self.sp_layout_rows.setRange(1, 6); self.sp_layout_rows.setValue(2); cfg_lay.addWidget(self.sp_layout_rows, 0, 3)

        btn_build = QPushButton("BUILD GRID"); fb = btn_build.font(); fb.setBold(True); btn_build.setFont(fb); btn_build.clicked.connect(self._build_layout_slots)
        cfg_lay.addWidget(btn_build, 1, 0, 1, 4)
        left_lay.addWidget(cfg)

        grp_slots = create_groupbox("Map Slots Setup")
        slots_lay = QVBoxLayout(grp_slots); slots_lay.setContentsMargins(4, 18, 4, 4)
        self.tabs_slots = QTabWidget(); self.tabs_slots.setUsesScrollButtons(True)
        slots_lay.addWidget(self.tabs_slots)
        left_lay.addWidget(grp_slots, stretch=1)

        btn_render_layout = QPushButton("READ ALL DATA"); btn_render_layout.setMinimumHeight(38); f_b = btn_render_layout.font(); f_b.setBold(True); btn_render_layout.setFont(f_b)
        btn_render_layout.clicked.connect(self._read_layout_data); left_lay.addWidget(btn_render_layout)

        self.layout_splitter.addWidget(left_panel)

        # ----- CENTER PANEL -----
        center_panel = QWidget(); center_lay = QVBoxLayout(center_panel); center_lay.setContentsMargins(4, 0, 4, 0)
        tb_lay = QHBoxLayout(); tb_lay.setContentsMargins(0,0,0,0)
        btn_fit = QPushButton("Fit View"); btn_fit.clicked.connect(self._fit_view_layout)
        btn_zin = QPushButton("Zoom In"); btn_zin.clicked.connect(self._zoom_in_layout)
        btn_zout = QPushButton("Zoom Out"); btn_zout.clicked.connect(self._zoom_out_layout)
        
        for b in [btn_fit, btn_zin, btn_zout]:
            fbb = b.font(); fbb.setBold(True); b.setFont(fbb); tb_lay.addWidget(b)
        tb_lay.addStretch(); center_lay.addLayout(tb_lay)

        self.layout_scroll = QScrollArea(); self.layout_scroll.setWidgetResizable(True); self.layout_scroll.setFrameShape(QScrollArea.NoFrame); self.layout_scroll.setAlignment(Qt.AlignCenter)
        self.fig_layout = Figure(); self.canvas_layout = FigureCanvas(self.fig_layout)
        self.layout_scroll.setWidget(self.canvas_layout); center_lay.addWidget(self.layout_scroll, stretch=1)
        self.lbl_layout_status = QLabel("Click 'BUILD GRID', set maps, then 'READ ALL DATA'."); self.lbl_layout_status.setAlignment(Qt.AlignCenter)
        center_lay.addWidget(self.lbl_layout_status)
        self.layout_splitter.addWidget(center_panel)

        # ----- RIGHT PANEL -----
        right_scroll = QScrollArea(); right_scroll.setWidgetResizable(True); right_scroll.setMinimumWidth(330); right_scroll.setFrameShape(QScrollArea.NoFrame)
        right_panel = QWidget(); right_lay = QVBoxLayout(right_panel); right_lay.setSpacing(12); right_lay.setContentsMargins(8, 4, 4, 4)

        l_grp_disp = create_groupbox("Layout Display Control")
        lgg = QGridLayout(l_grp_disp); lgg.setSpacing(10); lgg.setContentsMargins(12, 18, 12, 12)
        lgg.addWidget(QLabel("Background:"), 0, 0); self.l_cb_bg_color = QComboBox(); self.l_cb_bg_color.addItems(["Soft Black", "White", "Transparent (Dark Text)", "Transparent (Light Text)"]); self.l_cb_bg_color.currentIndexChanged.connect(self._trigger_layout_draw); lgg.addWidget(self.l_cb_bg_color, 0, 1, 1, 3)
        self.l_chk_axes = QCheckBox("Show Axes"); self.l_chk_axes.setChecked(True); self.l_chk_axes.toggled.connect(self._trigger_layout_draw); lgg.addWidget(self.l_chk_axes, 1, 0, 1, 4)
        self.l_chk_grid = QCheckBox("Show Grid Lines"); self.l_chk_grid.setChecked(True); self.l_chk_grid.toggled.connect(self._trigger_layout_draw); lgg.addWidget(self.l_chk_grid, 2, 0, 1, 4)
        right_lay.addWidget(l_grp_disp)
        
        l_grp_fig = create_groupbox("Figure Size & Spacing")
        lg_fig = QGridLayout(l_grp_fig); lg_fig.setSpacing(10); lg_fig.setContentsMargins(12, 18, 12, 12)
        lg_fig.addWidget(QLabel("Fig W (in):"), 0, 0); self.sp_fig_w = QSpinBox(); self.sp_fig_w.setRange(6, 40); self.sp_fig_w.setValue(16); self.sp_fig_w.valueChanged.connect(self._trigger_layout_draw); lg_fig.addWidget(self.sp_fig_w, 0, 1)
        lg_fig.addWidget(QLabel("Fig H (in):"), 0, 2); self.sp_fig_h = QSpinBox(); self.sp_fig_h.setRange(4, 30); self.sp_fig_h.setValue(10); self.sp_fig_h.valueChanged.connect(self._trigger_layout_draw); lg_fig.addWidget(self.sp_fig_h, 0, 3)
        lg_fig.addWidget(QLabel("H-space:"), 1, 0); self.sp_hspace = QDoubleSpinBox(); self.sp_hspace.setRange(0, 1); self.sp_hspace.setValue(0.25); self.sp_hspace.setSingleStep(0.05); self.sp_hspace.valueChanged.connect(self._trigger_layout_draw); lg_fig.addWidget(self.sp_hspace, 1, 1)
        lg_fig.addWidget(QLabel("W-space:"), 1, 2); self.sp_wspace = QDoubleSpinBox(); self.sp_wspace.setRange(0, 1); self.sp_wspace.setValue(0.25); self.sp_wspace.setSingleStep(0.05); self.sp_wspace.valueChanged.connect(self._trigger_layout_draw); lg_fig.addWidget(self.sp_wspace, 1, 3)
        right_lay.addWidget(l_grp_fig)

        l_grp_coords = create_groupbox("Layout Map Geometry")
        lgmc = QGridLayout(l_grp_coords); lgmc.setSpacing(10); lgmc.setContentsMargins(12, 18, 12, 12)
        lgmc.addWidget(QLabel("Format:"), 0, 0); self.l_cb_coord_format = QComboBox(); self.l_cb_coord_format.addItems(["DMS (Degree Minute Second)", "DM (Degree Minute)", "D (Decimal Degree)", "Default (UTM / Metre)"]); self.l_cb_coord_format.currentIndexChanged.connect(self._trigger_layout_draw); lgmc.addWidget(self.l_cb_coord_format, 0, 1, 1, 3)
        lgmc.addWidget(QLabel("Coord Size:"), 1, 0); self.l_sp_coord_size = QSpinBox(); self.l_sp_coord_size.setRange(4, 30); self.l_sp_coord_size.setValue(8); self.l_sp_coord_size.valueChanged.connect(self._trigger_layout_draw); lgmc.addWidget(self.l_sp_coord_size, 1, 1)
        lgmc.addWidget(QLabel("Coord Dec:"), 1, 2); self.l_sp_coord_decimals = QSpinBox(); self.l_sp_coord_decimals.setRange(0, 8); self.l_sp_coord_decimals.setValue(2); self.l_sp_coord_decimals.valueChanged.connect(self._trigger_layout_draw); lgmc.addWidget(self.l_sp_coord_decimals, 1, 3)
        lgmc.addWidget(QLabel("X-lbl Rot:"), 2, 0); self.l_sp_x_rot = QSpinBox(); self.l_sp_x_rot.setRange(0, 360); self.l_sp_x_rot.setValue(45); self.l_sp_x_rot.valueChanged.connect(self._trigger_layout_draw); lgmc.addWidget(self.l_sp_x_rot, 2, 1)
        lgmc.addWidget(QLabel("Y-lbl Rot:"), 2, 2); self.l_sp_y_rot = QSpinBox(); self.l_sp_y_rot.setRange(0, 360); self.l_sp_y_rot.setValue(90); self.l_sp_y_rot.valueChanged.connect(self._trigger_layout_draw); lgmc.addWidget(self.l_sp_y_rot, 2, 3)
        lgmc.addWidget(QLabel("X Tick Cnt:"), 3, 0); self.l_sp_xtick_count = QSpinBox(); self.l_sp_xtick_count.setRange(2, 20); self.l_sp_xtick_count.setValue(5); self.l_sp_xtick_count.valueChanged.connect(self._trigger_layout_draw); lgmc.addWidget(self.l_sp_xtick_count, 3, 1)
        lgmc.addWidget(QLabel("Y Tick Cnt:"), 3, 2); self.l_sp_ytick_count = QSpinBox(); self.l_sp_ytick_count.setRange(2, 20); self.l_sp_ytick_count.setValue(5); self.l_sp_ytick_count.valueChanged.connect(self._trigger_layout_draw); lgmc.addWidget(self.l_sp_ytick_count, 3, 3)
        lgmc.addWidget(QLabel("Grid Style:"), 4, 0); self.l_cb_grid_style = QComboBox(); self.l_cb_grid_style.addItems(["Solid (-)", "Dashed (--)", "Dotted (:)"]); self.l_cb_grid_style.setCurrentText("Dashed (--)"); self.l_cb_grid_style.currentIndexChanged.connect(self._trigger_layout_draw); lgmc.addWidget(self.l_cb_grid_style, 4, 1, 1, 3)
        right_lay.addWidget(l_grp_coords)

        l_grp_cbar = create_groupbox("Layout Colorbar")
        lgcb = QGridLayout(l_grp_cbar); lgcb.setSpacing(10); lgcb.setContentsMargins(12, 18, 12, 12)
        lgcb.addWidget(QLabel("Orient:"), 0, 0); self.l_cb_orient = QComboBox(); self.l_cb_orient.addItems(["vertical", "horizontal"]); self.l_cb_orient.currentIndexChanged.connect(self._trigger_layout_draw); lgcb.addWidget(self.l_cb_orient, 0, 1)
        lgcb.addWidget(QLabel("End Style:"), 0, 2); self.l_cb_legend_style = QComboBox(); self.l_cb_legend_style.addItems(["Both Pointed", "Right Pointed (Max)", "Left Pointed (Min)", "Box (Standard)"]); self.l_cb_legend_style.currentIndexChanged.connect(self._trigger_layout_draw); lgcb.addWidget(self.l_cb_legend_style, 0, 3)
        lgcb.addWidget(QLabel("Label Text:"), 1, 0); self.l_le_cbar_label = QLineEdit("Value"); self.l_le_cbar_label.textChanged.connect(self._trigger_layout_draw); lgcb.addWidget(self.l_le_cbar_label, 1, 1)
        self.l_chk_cbar_lbl_bold = QCheckBox("Bold Lbl"); self.l_chk_cbar_lbl_bold.setChecked(True); self.l_chk_cbar_lbl_bold.toggled.connect(self._trigger_layout_draw); lgcb.addWidget(self.l_chk_cbar_lbl_bold, 1, 2)
        self.l_cb_cbar_lbl_pos = QComboBox(); self.l_cb_cbar_lbl_pos.addItems(["Default", "Top", "Bottom", "Right", "Left"]); self.l_cb_cbar_lbl_pos.currentIndexChanged.connect(self._trigger_layout_draw); lgcb.addWidget(self.l_cb_cbar_lbl_pos, 1, 3)
        lgcb.addWidget(QLabel("Length:"), 2, 0); self.l_sp_cb_shrink = QDoubleSpinBox(); self.l_sp_cb_shrink.setRange(0.1, 1.5); self.l_sp_cb_shrink.setSingleStep(0.05); self.l_sp_cb_shrink.setValue(0.8); self.l_sp_cb_shrink.valueChanged.connect(self._trigger_layout_draw); lgcb.addWidget(self.l_sp_cb_shrink, 2, 1)
        lgcb.addWidget(QLabel("Thickness:"), 2, 2); self.l_sp_cb_aspect = QSpinBox(); self.l_sp_cb_aspect.setRange(5, 100); self.l_sp_cb_aspect.setValue(20); self.l_sp_cb_aspect.valueChanged.connect(self._trigger_layout_draw); lgcb.addWidget(self.l_sp_cb_aspect, 2, 3)
        lgcb.addWidget(QLabel("Pad to Map:"), 3, 0); self.l_sp_cb_pad = QDoubleSpinBox(); self.l_sp_cb_pad.setRange(0.0, 1.0); self.l_sp_cb_pad.setSingleStep(0.01); self.l_sp_cb_pad.setValue(0.05); self.l_sp_cb_pad.valueChanged.connect(self._trigger_layout_draw); lgcb.addWidget(self.l_sp_cb_pad, 3, 1)
        lgcb.addWidget(QLabel("Tick Cnt:"), 3, 2); self.l_sp_tick_count = QSpinBox(); self.l_sp_tick_count.setRange(2, 30); self.l_sp_tick_count.setValue(5); self.l_sp_tick_count.valueChanged.connect(self._trigger_layout_draw); lgcb.addWidget(self.l_sp_tick_count, 3, 3)
        lgcb.addWidget(QLabel("Lbl Size:"), 4, 0); self.l_sp_leg_lbl_size = QSpinBox(); self.l_sp_leg_lbl_size.setRange(6, 30); self.l_sp_leg_lbl_size.setValue(10); self.l_sp_leg_lbl_size.valueChanged.connect(self._trigger_layout_draw); lgcb.addWidget(self.l_sp_leg_lbl_size, 4, 1)
        lgcb.addWidget(QLabel("Tick Size:"), 4, 2); tick_sz_lay = QHBoxLayout(); tick_sz_lay.setContentsMargins(0,0,0,0); self.l_sp_leg_tick_size = QSpinBox(); self.l_sp_leg_tick_size.setRange(6, 30); self.l_sp_leg_tick_size.setValue(9); self.l_sp_leg_tick_size.valueChanged.connect(self._trigger_layout_draw); tick_sz_lay.addWidget(self.l_sp_leg_tick_size); self.l_chk_cbar_tick_bold = QCheckBox("Bold"); self.l_chk_cbar_tick_bold.toggled.connect(self._trigger_layout_draw); tick_sz_lay.addWidget(self.l_chk_cbar_tick_bold); lgcb.addLayout(tick_sz_lay, 4, 3)
        lgcb.addWidget(QLabel("Lbl Pad:"), 5, 0); self.l_sp_leg_pad_label = QSpinBox(); self.l_sp_leg_pad_label.setRange(-50, 100); self.l_sp_leg_pad_label.setValue(5); self.l_sp_leg_pad_label.valueChanged.connect(self._trigger_layout_draw); lgcb.addWidget(self.l_sp_leg_pad_label, 5, 1)
        lgcb.addWidget(QLabel("Tick Pad:"), 5, 2); self.l_sp_leg_pad_tick = QSpinBox(); self.l_sp_leg_pad_tick.setRange(-50, 100); self.l_sp_leg_pad_tick.setValue(2); self.l_sp_leg_pad_tick.valueChanged.connect(self._trigger_layout_draw); lgcb.addWidget(self.l_sp_leg_pad_tick, 5, 3)
        self.l_chk_ticks = QCheckBox("Dynamic Ticks"); self.l_chk_ticks.setChecked(False); self.l_chk_ticks.toggled.connect(self._trigger_layout_draw); lgcb.addWidget(self.l_chk_ticks, 6, 0, 1, 2)
        lgcb.addWidget(QLabel("Tick Dec:"), 6, 2); self.l_sp_cbar_decimals = QSpinBox(); self.l_sp_cbar_decimals.setRange(0, 8); self.l_sp_cbar_decimals.setValue(2); self.l_sp_cbar_decimals.valueChanged.connect(self._trigger_layout_draw); lgcb.addWidget(self.l_sp_cbar_decimals, 6, 3)
        right_lay.addWidget(l_grp_cbar)

        right_lay.addStretch()
        right_scroll.setWidget(right_panel)
        self.layout_splitter.addWidget(right_scroll)

        self.layout_splitter.setStretchFactor(0, 0)
        self.layout_splitter.setStretchFactor(1, 1)
        self.layout_splitter.setStretchFactor(2, 0)
        self.layout_splitter.setSizes([360, 780, 330])
        tab_lay.addWidget(self.layout_splitter)

        self.top_tabs.addTab(tab, "Layout Series")

    # ========================== TOOLBAR ACTIONS (TEXT & MOVE) ==========================
    def _add_custom_text(self):
        text, ok = QInputDialog.getText(self, "Add Text", "Enter custom text:")
        if ok and text:
            # Added texts start explicitly in the middle
            self._custom_texts.append({'text': text, 'x': 0.5, 'y': 0.5})
            self._trigger_live_update()

    def _toggle_move_mode(self, checked):
        self._move_mode = checked
        if checked:
            self.btn_move_mode.setText("✋ Drag Elements: ON")
            self.btn_move_mode.setStyleSheet("background-color: #3b82f6; color: white;")
            self.canvas_map.setCursor(QCursor(Qt.CrossCursor))
        else:
            self.btn_move_mode.setText("✋ Drag Elements: OFF")
            self.btn_move_mode.setStyleSheet("")
            self.canvas_map.setCursor(QCursor(Qt.ArrowCursor))
            self._drag_item = None
        self._trigger_live_update()

    # ========================== INTERACTIVE DRAG-AND-DROP LOGIC ==========================
    def _on_drag_press(self, event):
        if not self._move_mode: return
        if event.x is None or event.y is None: return

        fig_w, fig_h = self.fig_map.bbox.width, self.fig_map.bbox.height
        fx, fy = event.x / fig_w, event.y / fig_h

        # 1. Check Continuous Colorbar
        if self._current_cbar_ax:
            bbox = self._current_cbar_ax.bbox
            if bbox.contains(event.x, event.y):
                cx, cy = self.sp_leg_x.value(), self.sp_leg_y.value()
                self._drag_item = ('colorbar', None)
                self._drag_offset = (fx - cx, fy - cy)
                return

        # 2. Check Discrete Legend
        if self._current_legend:
            bbox = self._current_legend.get_window_extent()
            if bbox.contains(event.x, event.y):
                cx, cy = self.sp_dleg_x.value(), self.sp_dleg_y.value()
                self._drag_item = ('legend', None)
                self._drag_offset = (fx - cx, fy - cy)
                return

        # 3. Check Main Title
        if self._title_obj:
            bbox = self._title_obj.get_window_extent()
            if bbox.contains(event.x, event.y):
                cx, cy = self._pos_title
                self._drag_item = ('title', None)
                self._drag_offset = (fx - cx, fy - cy)
                return

        # 4. Check Subtitle
        if self._subtitle_obj:
            bbox = self._subtitle_obj.get_window_extent()
            if bbox.contains(event.x, event.y):
                cx, cy = self._pos_subtitle
                self._drag_item = ('subtitle', None)
                self._drag_offset = (fx - cx, fy - cy)
                return

        # 5. Check Custom Texts
        for i, t_info in enumerate(self._current_texts):
            if t_info['obj'].get_window_extent().contains(event.x, event.y):
                cx, cy = self._custom_texts[i]['x'], self._custom_texts[i]['y']
                self._drag_item = ('custom_text', i)
                self._drag_offset = (fx - cx, fy - cy)
                return

    def _on_drag_motion(self, event):
        if not self._drag_item or not self._move_mode: return
        if event.x is None or event.y is None: return

        fig_w, fig_h = self.fig_map.bbox.width, self.fig_map.bbox.height
        fx, fy = event.x / fig_w, event.y / fig_h
        
        item_type, idx = self._drag_item
        ox, oy = self._drag_offset

        new_x = fx - ox
        new_y = fy - oy

        if item_type == 'colorbar':
            self.sp_leg_x.blockSignals(True)
            self.sp_leg_y.blockSignals(True)
            self.sp_leg_x.setValue(new_x)
            self.sp_leg_y.setValue(new_y)
            self.sp_leg_x.blockSignals(False)
            self.sp_leg_y.blockSignals(False)
            
            w = self.sp_leg_w.value() if self.cb_orient.currentText() == 'horizontal' else self.sp_leg_h.value()
            h = self.sp_leg_h.value() if self.cb_orient.currentText() == 'horizontal' else self.sp_leg_w.value()
            self._current_cbar_ax.set_position([new_x, new_y, w, h])
            
        elif item_type == 'legend':
            self.sp_dleg_x.blockSignals(True)
            self.sp_dleg_y.blockSignals(True)
            self.sp_dleg_x.setValue(new_x)
            self.sp_dleg_y.setValue(new_y)
            self.sp_dleg_x.blockSignals(False)
            self.sp_dleg_y.blockSignals(False)
            self._current_legend.set_bbox_to_anchor((new_x, new_y))

        elif item_type == 'title':
            self._pos_title = (new_x, new_y)
            self._title_obj.set_position((new_x, new_y))

        elif item_type == 'subtitle':
            self._pos_subtitle = (new_x, new_y)
            self._subtitle_obj.set_position((new_x, new_y))

        elif item_type == 'custom_text':
            self._custom_texts[idx]['x'] = new_x
            self._custom_texts[idx]['y'] = new_y
            self._current_texts[idx]['obj'].set_position((new_x, new_y))

        self.canvas_map.draw_idle()

    def _on_drag_release(self, event):
        self._drag_item = None

    # ========================== ZOOM & PAN LOGIC ==========================
    def _fit_view_map(self):
        self.map_scroll.setWidgetResizable(True)
        self.canvas_map.setMinimumSize(0, 0)
        self.canvas_map.setMaximumSize(16777215, 16777215)
        self.canvas_map.updateGeometry()

    def _zoom_in_map(self):
        self._apply_zoom_map(1.2)

    def _zoom_out_map(self):
        self._apply_zoom_map(0.8)

    def _apply_zoom_map(self, factor):
        if self.map_scroll.widgetResizable():
            curr_size = self.canvas_map.size()
            self.map_scroll.setWidgetResizable(False)
            self.canvas_map.setFixedSize(curr_size)
        current_w = self.canvas_map.width(); current_h = self.canvas_map.height()
        self.canvas_map.setFixedSize(int(current_w * factor), int(current_h * factor))

    def _fit_view_layout(self):
        self.layout_scroll.setWidgetResizable(True)
        self.canvas_layout.setMinimumSize(0, 0)
        self.canvas_layout.setMaximumSize(16777215, 16777215)
        self.canvas_layout.updateGeometry()
    
    def _zoom_in_layout(self):
        self._apply_zoom_layout(1.2)
        
    def _zoom_out_layout(self):
        self._apply_zoom_layout(0.8)
        
    def _apply_zoom_layout(self, factor):
        if self.layout_scroll.widgetResizable():
            curr_size = self.canvas_layout.size()
            self.layout_scroll.setWidgetResizable(False)
            self.canvas_layout.setFixedSize(curr_size)
        current_w = self.canvas_layout.width(); current_h = self.canvas_layout.height()
        self.canvas_layout.setFixedSize(int(current_w * factor), int(current_h * factor))

    # ========================== GLOBAL EXPORT ==========================
    def _export_current_tab(self):
        if self.top_tabs.currentIndex() == 0:
            self.export_figure()
        else:
            self._export_layout()

    # ========================== DATA READING & LIVE UPDATE LOGIC ==========================
    def _scan_discrete_classes(self):
        if self._cached_arr is None:
            QMessageBox.warning(self, "No Data", "Click 'READ DATA & RENDER' first before scanning gridcodes.")
            return
        valid = self._cached_arr[np.isfinite(self._cached_arr)]
        if len(valid) == 0: return
        unique_vals = np.unique(valid)
        if len(unique_vals) > 100:
            ret = QMessageBox.question(self, "Many Classes", f"{len(unique_vals)} unique values detected.\nContinue building {len(unique_vals)} class rows?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if ret != QMessageBox.Yes: return
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
            row_w = DiscreteClassRow(v, color_hex=color, label=label, decimals=current_dec, parent=self._disc_classes_container)
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
            row.sp_decimals.blockSignals(True); row.sp_decimals.setValue(dec); row.sp_decimals.blockSignals(False)
        self._trigger_live_update()

    def _pick_nodata_color(self):
        initial = QColor(self._nodata_color) if QColor(self._nodata_color).isValid() else QColor(Qt.transparent)
        col = QColorDialog.getColor(initial, self, "Choose Nodata Colour", QColorDialog.ShowAlphaChannel)
        if col.isValid():
            if col.alpha() == 0:
                self._nodata_color = "#00000000"
                self.btn_nodata_color.setStyleSheet("background-color: transparent; border: 1px dashed #888; border-radius:3px;")
                self.le_nodata_hex.setText("transparent")
            else:
                self._nodata_color = col.name()
                self.btn_nodata_color.setStyleSheet(f"background-color:{self._nodata_color}; border:1px solid #888; border-radius:3px;")
                self.le_nodata_hex.setText(self._nodata_color)
        self._trigger_live_update()

    def _is_discrete_mode(self): return self.tab_color_mode.currentIndex() == 1
    def _cmap_prev(self): self.cmap_idx = (self.cmap_idx - 1) % len(COLORMAPS); self._update_cmap_preview(); self._trigger_live_update()
    def _cmap_next(self): self.cmap_idx = (self.cmap_idx + 1) % len(COLORMAPS); self._update_cmap_preview(); self._trigger_live_update()
    def _on_reverse_toggled(self): self._update_cmap_preview(); self._trigger_live_update()

    def _update_cmap_preview(self):
        cmap_name = COLORMAPS[self.cmap_idx]
        w, h = 250, 24
        pixmap = QPixmap(w, h); painter = QPainter(pixmap)
        try:
            suffix = "_r" if self.chk_reverse_cmap.isChecked() else ""
            cmap = plt.get_cmap(cmap_name + suffix)
        except Exception: cmap = plt.get_cmap("viridis")
        for x in range(w):
            c = cmap(x / max(1, w - 1))
            painter.setPen(QColor(int(c[0] * 255), int(c[1] * 255), int(c[2] * 255)))
            painter.drawLine(x, 0, x, h)
        painter.end()
        self.lbl_cmap_preview.setPixmap(pixmap); self.lbl_cmap_preview.setToolTip(cmap_name)

    def _connect_live_updates(self):
        self.cb_orient.currentTextChanged.connect(self._auto_position_legend)
        for w in [self.cb_stretch, self.cb_legend_style, self.cb_grid_style, self.cb_bg_color, self.cb_coord_format, 
                  self.cb_font_family, self.cb_cbar_lbl_pos, self.cb_dleg_shape, self.cb_dleg_align]:
            w.currentIndexChanged.connect(self._trigger_live_update)
        for s in [self.sp_pmin, self.sp_pmax, self.sp_map_x, self.sp_map_y, self.sp_map_w, self.sp_map_h, self.sp_leg_x, 
                  self.sp_leg_y, self.sp_leg_w, self.sp_leg_h, self.sp_coord_size, self.sp_title_size, 
                  self.sp_leg_lbl_size, self.sp_leg_tick_size, self.sp_tick_count, self.sp_leg_pad_label, self.sp_leg_pad_tick, 
                  self.sp_xlabel_rotation, self.sp_ylabel_rotation, self.sp_xtick_count, self.sp_ytick_count, 
                  self.sp_coord_decimals, self.sp_cbar_decimals, self.sp_dleg_x, self.sp_dleg_y, self.sp_dleg_symsize,
                  self.sp_dleg_pad, self.sp_dleg_cols]:
            s.valueChanged.connect(self._trigger_live_update)
        for c in [self.chk_legend, self.chk_ticks, self.chk_axes, self.chk_grid, self.chk_nodata_transp, 
                  self.chk_disc_legend, self.chk_cbar_lbl_bold, self.chk_cbar_tick_bold, self.chk_dleg_gridcode]:
            c.toggled.connect(self._trigger_live_update)
        for le in [self.le_vmin, self.le_vmax, self.le_cbar_label, self.le_title, self.le_subtitle]:
            le.textChanged.connect(self._trigger_live_update)

    def _auto_position_legend(self, orient):
        self._is_updating = True
        if orient == "vertical":
            self.sp_leg_x.setValue(0.88); self.sp_leg_y.setValue(0.20); self.sp_leg_w.setValue(0.60); self.sp_leg_h.setValue(0.03)
        else:
            self.sp_leg_x.setValue(0.20); self.sp_leg_y.setValue(0.05); self.sp_leg_w.setValue(0.60); self.sp_leg_h.setValue(0.03)
        self._is_updating = False
        self._trigger_live_update()

    def populate_layers(self):
        self.cb_layer.clear()
        layers = [lyr for lyr in QgsProject.instance().mapLayers().values() if lyr.type() == QgsMapLayerType.RasterLayer]
        for lyr in layers: self.cb_layer.addItem(lyr.name(), lyr.id())
        for slot in self._layout_slots:
            current = slot.cb_layer.currentText(); slot.cb_layer.clear()
            for lyr in layers: slot.cb_layer.addItem(lyr.name(), lyr.id())
            if current: slot.cb_layer.setCurrentText(current)

    def _open_raster_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Raster File", "", "Raster Files (*.tif *.tiff *.geotiff *.img *.vrt *.nc *.hdf *.h5)")
        if path:
            rlayer = QgsRasterLayer(path, os.path.basename(path))
            if rlayer.isValid():
                QgsProject.instance().addMapLayer(rlayer); self.populate_layers(); self.cb_layer.setCurrentText(rlayer.name())
            else: QMessageBox.warning(self, "Error", "Failed to load raster file.")

    def _on_layer_changed(self):
        lyr = self._get_layer()
        if lyr:
            nb = lyr.bandCount()
            for sp in [self.sp_band, self.sp_r, self.sp_g, self.sp_b]: sp.setMaximum(nb)

    def _get_layer(self):
        lid = self.cb_layer.currentData()
        return QgsProject.instance().mapLayer(lid) if lid else None

    def _toggle_band_mode(self):
        single = self.rb_single.isChecked()
        self.lbl_band.setVisible(single); self.sp_band.setVisible(single)
        self.btn_cmap_prev.setEnabled(single); self.btn_cmap_next.setEnabled(single)
        self.chk_reverse_cmap.setEnabled(single)
        for w in [self.lbl_r, self.sp_r, self.lbl_g, self.sp_g, self.lbl_b, self.sp_b]: w.setVisible(not single)
        self.grp_cbar.setVisible(single)
        self.grp_disc_leg.setVisible(single)
        self._cached_arr = None; self._cached_rgb = None

    def _toggle_stretch_opts(self):
        mode = self.cb_stretch.currentText()
        pct = "Percentile" in mode; manual = "Manual" in mode
        self.lbl_pmin.setVisible(pct); self.sp_pmin.setVisible(pct)
        self.lbl_pmax.setVisible(pct); self.sp_pmax.setVisible(pct)
        self.lbl_vmin.setVisible(manual); self.le_vmin.setVisible(manual)
        self.lbl_vmax.setVisible(manual); self.le_vmax.setVisible(manual)

    def _read_band(self, lyr, band_no, max_px_k=1000):
        provider = lyr.dataProvider(); extent = lyr.extent()
        width = lyr.width(); height = lyr.height()
        max_px = max_px_k * 1000; total_px = width * height
        if total_px > max_px:
            scale = (max_px / total_px) ** 0.5
            width = max(1, int(width * scale)); height = max(1, int(height * scale))
        block = provider.block(band_no, extent, width, height)
        nodata = provider.sourceNoDataValue(band_no)
        has_nodata = provider.sourceHasNoDataValue(band_no)
        arr = np.zeros((height, width), dtype=np.float64)
        for row in range(height):
            for col in range(width): arr[row, col] = block.value(row, col)
        if has_nodata:
            mask = np.isclose(arr, nodata, rtol=0, atol=1e-6); arr = np.where(mask, np.nan, arr)
        return arr, extent

    def _read_and_render(self):
        lyr = self._get_layer()
        if lyr is None: return
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
            self._trigger_live_update(); self.lbl_status.setText("Data ready.")
        except Exception as e: self.lbl_status.setText(f"Error: {e}")
        finally: self.btn_read.setEnabled(True)

    def _trigger_live_update(self):
        if self._is_updating: return
        if self._cached_arr is None and self._cached_rgb is None: return
        
        if self._is_discrete_mode() and self.rb_single.isChecked():
            self.grp_disc_leg.setVisible(True)
            self.grp_cbar.setVisible(False)
        else:
            self.grp_disc_leg.setVisible(False)
            self.grp_cbar.setVisible(True)

        self._live_update()

    def _apply_stretch(self, arr):
        valid = arr[np.isfinite(arr)]
        if len(valid) == 0: return 0.0, 1.0
        mode = self.cb_stretch.currentText()
        if mode == "Actual Min-Max": vmin, vmax = float(valid.min()), float(valid.max())
        elif "Percentile" in mode: vmin, vmax = float(np.percentile(valid, self.sp_pmin.value())), float(np.percentile(valid, self.sp_pmax.value()))
        else:
            try: vmin, vmax = float(self.le_vmin.text()), float(self.le_vmax.text())
            except ValueError: vmin, vmax = float(valid.min()), float(valid.max())
        if np.isclose(vmin, vmax): vmax = vmin + 1
        return vmin, vmax

    def _make_lon_formatter(self, format_text, dec):
        def formatter(x, pos):
            if "Default" in format_text: return f"{x:.{dec}f}"
            val = abs(x); d_lbl = "E" if x >= 0 else "W"
            if "DMS" in format_text:
                d = int(val); m = int((val - d) * 60); s = (val - d - m / 60.0) * 3600
                return f"{d}°{m}'{s:.1f}\" {d_lbl}"
            if "DM" in format_text:
                d = int(val); m = (val - d) * 60
                return f"{d}°{m:.{dec}f}' {d_lbl}"
            return f"{val:.{dec}f}° {d_lbl}"
        return formatter

    def _make_lat_formatter(self, format_text, dec):
        def formatter(y, pos):
            if "Default" in format_text: return f"{y:.{dec}f}"
            val = abs(y); d_lbl = "N" if y >= 0 else "S"
            if "DMS" in format_text:
                d = int(val); m = int((val - d) * 60); s = (val - d - m / 60.0) * 3600
                return f"{d}°{m}'{s:.1f}\" {d_lbl}"
            if "DM" in format_text:
                d = int(val); m = (val - d) * 60
                return f"{d}°{m:.{dec}f}' {d_lbl}"
            return f"{val:.{dec}f}° {d_lbl}"
        return formatter

    def _style_axes(self, ax, txt_col, font_fam, fig_bg):
        coord_size = self.sp_coord_size.value()
        ax.tick_params(colors=txt_col, labelsize=coord_size)
        ax.xaxis.set_major_locator(mticker.MaxNLocator(nbins=self.sp_xtick_count.value()))
        ax.yaxis.set_major_locator(mticker.MaxNLocator(nbins=self.sp_ytick_count.value()))
        fmt = self.cb_coord_format.currentText()
        dec = self.sp_coord_decimals.value()

        if "Default" not in fmt:
            ax.xaxis.set_major_formatter(mticker.FuncFormatter(self._make_lon_formatter(fmt, dec)))
            ax.yaxis.set_major_formatter(mticker.FuncFormatter(self._make_lat_formatter(fmt, dec)))
        else:
            ax.xaxis.set_major_formatter(mticker.FormatStrFormatter(f"%.{dec}f"))
            ax.yaxis.set_major_formatter(mticker.FormatStrFormatter(f"%.{dec}f"))

        x_rot = self.sp_xlabel_rotation.value()
        y_rot = self.sp_ylabel_rotation.value()
        x_ha = "right" if 10 < x_rot < 350 else "center"

        for tick in ax.get_xticklabels():
            tick.set_fontfamily(font_fam); tick.set_rotation(x_rot); tick.set_ha(x_ha)
        for tick in ax.get_yticklabels():
            tick.set_fontfamily(font_fam); tick.set_rotation(y_rot); tick.set_ha("right")
        for sp_item in ax.spines.values(): sp_item.set_color(txt_col)
        if self.chk_grid.isChecked():
            ls = ("--" if "Dashed" in self.cb_grid_style.currentText() else ":" if "Dotted" in self.cb_grid_style.currentText() else "-")
            ax.grid(True, color=txt_col, linestyle=ls, linewidth=0.4, alpha=0.5)

    def _get_theme(self, bg_text):
        if "Soft Black" in bg_text: return "#2b2b2b", "#2b2b2b", "#e2e8f0"
        if "White" in bg_text: return "white", "white", "black"
        if "Dark Text" in bg_text: return "none", "none", "black"
        return "none", "none", "white"

    def _live_update(self):
        self.fig_map.clf()
        if self._cached_ext is None: return

        ext = self._cached_ext
        plot_ext = [ext.xMinimum(), ext.xMaximum(), ext.yMinimum(), ext.yMaximum()]
        fig_bg, ax_bg, txt_col = self._get_theme(self.cb_bg_color.currentText())
        font_fam = self.cb_font_family.currentText()

        self.fig_map.patch.set_facecolor(fig_bg)
        ax = self.fig_map.add_axes([self.sp_map_x.value(), self.sp_map_y.value(), self.sp_map_w.value(), self.sp_map_h.value()])
        if ax_bg != "none": ax.set_facecolor(ax_bg)

        # Clear references for new render
        self._current_cbar_ax = None
        self._current_legend = None
        self._current_texts = []
        self._title_obj = None
        self._subtitle_obj = None

        title = self.le_title.text()
        subtitle = self.le_subtitle.text()

        # Render Title/Subtitle
        if title:
            if self._pos_title is None:
                self._pos_title = (self.sp_map_x.value() + self.sp_map_w.value()/2, self.sp_map_y.value() + self.sp_map_h.value() + 0.05)
            self._title_obj = self.fig_map.text(self._pos_title[0], self._pos_title[1], title, ha='center', va='bottom', color=txt_col, fontfamily=font_fam, fontsize=self.sp_title_size.value(), fontweight="bold")
            
        if subtitle: 
            if self._pos_subtitle is None:
                self._pos_subtitle = (self.sp_map_x.value() + self.sp_map_w.value()/2, self.sp_map_y.value() + self.sp_map_h.value() + 0.01)
            self._subtitle_obj = self.fig_map.text(self._pos_subtitle[0], self._pos_subtitle[1], subtitle, ha='center', va='bottom', color=txt_col, fontfamily=font_fam, fontsize=self.sp_title_size.value()-3)

        # Render Custom Texts
        for i, ctext in enumerate(self._custom_texts):
            t_obj = self.fig_map.text(ctext['x'], ctext['y'], ctext['text'], ha='center', va='center', color=txt_col, fontfamily=font_fam, fontsize=self.sp_title_size.value()-2)
            self._current_texts.append({'obj': t_obj, 'index': i})

        if not self.chk_axes.isChecked(): ax.axis("off")
        else: self._style_axes(ax, txt_col, font_fam, fig_bg)

        # Render Data and Legends
        if self._is_discrete_mode() and self.rb_single.isChecked() and self._cached_arr is not None: 
            self._current_legend = self._render_discrete(ax, ax_bg, txt_col, font_fam, plot_ext)
        elif self.rb_single.isChecked() and self._cached_arr is not None: 
            self._render_continuous(ax, ax_bg, txt_col, font_fam, plot_ext)
        elif self.rb_rgb.isChecked() and self._cached_rgb is not None: 
            self._render_rgb(ax, plot_ext)

        self.canvas_map.draw()

    def _render_discrete(self, ax, ax_bg, txt_col, font_fam, plot_ext):
        arr = self._cached_arr
        if len(self._discrete_rows) == 0: return None
        rows = self._discrete_rows
        height, width = arr.shape
        rgba = np.zeros((height, width, 4), dtype=np.uint8)
        nodata_qcol = QColor(self._nodata_color)
        if nodata_qcol.isValid() and nodata_qcol.alpha() > 0: nd_rgba = np.array([nodata_qcol.red(), nodata_qcol.green(), nodata_qcol.blue(), nodata_qcol.alpha()], dtype=np.uint8)
        else: nd_rgba = np.array([0, 0, 0, 0], dtype=np.uint8)
        rgba[~np.isfinite(arr)] = nd_rgba

        for row_w in rows:
            gc = row_w.gridcode; qc = QColor(row_w.get_color())
            if not qc.isValid(): qc = QColor("#888888")
            mask = np.isfinite(arr) & np.isclose(arr, gc, rtol=0, atol=0.5)
            rgba[mask] = [qc.red(), qc.green(), qc.blue(), 255]

        ax.imshow(rgba, extent=plot_ext, interpolation="nearest", aspect="equal", origin="upper")

        if self.chk_legend.isChecked() and self.chk_disc_legend.isChecked():
            patches = []
            shape_opt = self.cb_dleg_shape.currentText()
            sym_size = self.sp_dleg_symsize.value()
            show_gc = self.chk_dleg_gridcode.isChecked()

            for row_w in rows:
                dec = row_w.get_decimals(); gc = row_w.gridcode
                gc_str = str(int(gc)) if (float(gc).is_integer() and dec == 0) else f"{gc:.{dec}f}"
                lbl = row_w.get_label()
                display_lbl = f"{lbl}  ({gc_str})" if show_gc else lbl
                
                if shape_opt == "Circle":
                    patches.append(Line2D([0], [0], marker='o', color='w', markerfacecolor=row_w.get_color(), markersize=sym_size/2, label=display_lbl))
                else:
                    patches.append(mpatches.Patch(facecolor=row_w.get_color(), edgecolor=txt_col, linewidth=0.6, label=display_lbl))
            
            leg = self.fig_map.legend(
                handles=patches, loc="lower left", 
                bbox_to_anchor=(self.sp_dleg_x.value(), self.sp_dleg_y.value()), 
                bbox_transform=self.fig_map.transFigure, framealpha=0.85, 
                facecolor=ax_bg if ax_bg != "none" else "#2b2b2b", 
                edgecolor=txt_col, fontsize=self.sp_leg_tick_size.value(), 
                ncol=self.sp_dleg_cols.value(),
                labelspacing=self.sp_dleg_pad.value(),
                alignment=self.cb_dleg_align.currentText()
            )
            for text in leg.get_texts(): 
                text.set_color(txt_col); text.set_fontfamily(font_fam)
            return leg
        return None

    def _render_continuous(self, ax, ax_bg, txt_col, font_fam, plot_ext, cmap_override=None, vmin_override=None, vmax_override=None, show_colorbar=True):
        arr = self._cached_arr
        valid_data = arr[np.isfinite(arr)]
        vmin, vmax = (vmin_override, vmax_override) if vmin_override is not None else self._apply_stretch(arr)
        actual_min = float(valid_data.min()) if len(valid_data) > 0 else vmin
        actual_max = float(valid_data.max()) if len(valid_data) > 0 else vmax

        cmap_name = cmap_override if cmap_override else COLORMAPS[self.cmap_idx]
        if not cmap_override and self.chk_reverse_cmap.isChecked(): cmap_name += "_r"
        try: cmap = plt.get_cmap(cmap_name).copy()
        except Exception: cmap = plt.get_cmap("viridis").copy()
        if self.chk_nodata_transp.isChecked(): cmap.set_bad(alpha=0)

        im = ax.imshow(arr, cmap=cmap, vmin=vmin, vmax=vmax, extent=plot_ext, interpolation="bilinear", aspect="equal", origin="upper")

        if show_colorbar and self.chk_legend.isChecked():
            is_vert = self.cb_orient.currentText() == "vertical"
            cax_w = self.sp_leg_h.value() if is_vert else self.sp_leg_w.value()
            cax_h = self.sp_leg_w.value() if is_vert else self.sp_leg_h.value()

            cax = self.fig_map.add_axes([self.sp_leg_x.value(), self.sp_leg_y.value(), cax_w, cax_h])
            self._current_cbar_ax = cax

            extend_opt = self.cb_legend_style.currentText()
            extend_str = ("both" if "Both" in extend_opt else "max" if "Right" in extend_opt else "min" if "Left" in extend_opt else "neither")
                          
            cb = self.fig_map.colorbar(im, cax=cax, orientation=self.cb_orient.currentText(), extend=extend_str, extendfrac=0.04, drawedges=False)
            
            lbl_text = self.le_cbar_label.text()
            fontweight_lbl = "bold" if self.chk_cbar_lbl_bold.isChecked() else "normal"
            tick_weight = "bold" if self.chk_cbar_tick_bold.isChecked() else "normal"
            lbl_pos = self.cb_cbar_lbl_pos.currentText()

            cb.set_label(lbl_text, color=txt_col, fontfamily=font_fam, fontsize=self.sp_leg_lbl_size.value(), fontweight=fontweight_lbl, labelpad=self.sp_leg_pad_label.value())
            
            if is_vert:
                if lbl_pos == "Top":
                    cb.set_label("")
                    cb.ax.set_title(lbl_text, color=txt_col, fontfamily=font_fam, fontsize=self.sp_leg_lbl_size.value(), fontweight=fontweight_lbl, pad=self.sp_leg_pad_label.value())
                elif lbl_pos == "Left": cb.ax.yaxis.set_label_position("left")
                elif lbl_pos == "Right": cb.ax.yaxis.set_label_position("right")
            else:
                if lbl_pos == "Top": cb.ax.xaxis.set_label_position("top")
                elif lbl_pos == "Bottom": cb.ax.xaxis.set_label_position("bottom")
                elif lbl_pos == "Right":
                    cb.set_label("")
                    cb.ax.text(1.02, 0.5, lbl_text, transform=cb.ax.transAxes, va='center', ha='left', color=txt_col, fontfamily=font_fam, fontsize=self.sp_leg_lbl_size.value(), fontweight=fontweight_lbl)
                elif lbl_pos == "Left":
                    cb.set_label("")
                    cb.ax.text(-0.02, 0.5, lbl_text, transform=cb.ax.transAxes, va='center', ha='right', color=txt_col, fontfamily=font_fam, fontsize=self.sp_leg_lbl_size.value(), fontweight=fontweight_lbl)

            cb.ax.tick_params(colors=txt_col, labelsize=self.sp_leg_tick_size.value(), pad=self.sp_leg_pad_tick.value())
            for tick in cb.ax.get_xticklabels() + cb.ax.get_yticklabels(): tick.set_fontfamily(font_fam); tick.set_fontweight(tick_weight)

            dec = self.sp_cbar_decimals.value(); tc = self.sp_tick_count.value()
            if self.chk_ticks.isChecked(): cb.locator = mticker.MaxNLocator(nbins=tc, prune="both"); cb.update_ticks()
            else:
                ticks_pos = np.linspace(vmin, vmax, tc); cb.set_ticks(ticks_pos)
                if tc == 2: cb.set_ticklabels([f"{actual_min:.{dec}f}", f"{actual_max:.{dec}f}"])
                else:
                    lbls = [f"{actual_min:.{dec}f}"]
                    lbls.extend([f"{t:.{dec}f}" for t in ticks_pos[1:-1]])
                    lbls.append(f"{actual_max:.{dec}f}")
                    cb.set_ticklabels(lbls)
            cb.outline.set_edgecolor(txt_col); cb.outline.set_linewidth(0.8)

        return im

    def _render_rgb(self, ax, plot_ext):
        def norm(a):
            v0, v1 = self._apply_stretch(a)
            a_c = np.clip(a, v0, v1)
            return (a_c - v0) / (v1 - v0 + 1e-12)
        rgb = np.dstack([norm(self._cached_rgb[0]), norm(self._cached_rgb[1]), norm(self._cached_rgb[2])])
        ax.imshow(rgb, extent=plot_ext, interpolation="bilinear", aspect="equal", origin="upper")

    def export_figure(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Image", "", "PNG (*.png);;SVG (*.svg);;TIFF (*.tif);;PDF (*.pdf)")
        if not path: return
        dpi = 300 if path.lower().endswith((".png", ".tif")) else 150
        self.fig_map.savefig(path, dpi=dpi, bbox_inches="tight", facecolor=self.fig_map.get_facecolor(), transparent=("Transparent" in self.cb_bg_color.currentText()))
        self.lbl_status.setText(f"Exported: {path}")
        QMessageBox.information(self, "Success", f"Image saved:\n{path}")

    # ================= LAYOUT SERIES LIVE UPDATE & RENDER LOGIC =================

    def _build_layout_slots(self):
        for slot in self._layout_slots:
            slot.setParent(None); slot.deleteLater()
        self._layout_slots.clear()
        self._layout_cache.clear()
        self.tabs_slots.clear()

        n_rows = self.sp_layout_rows.value(); n_cols = self.sp_layout_cols.value()
        n_slots = n_rows * n_cols
        raster_layers = [lyr for lyr in QgsProject.instance().mapLayers().values() if lyr.type() == QgsMapLayerType.RasterLayer]

        for i in range(n_slots):
            slot = LayoutSlotWidget(i, self._trigger_layout_draw)
            for lyr in raster_layers: slot.cb_layer.addItem(lyr.name(), lyr.id())
            slot.cb_layer.currentIndexChanged.connect(self._prompt_read_data)
            slot.sp_band.valueChanged.connect(self._prompt_read_data)
            self.tabs_slots.addTab(slot, f"Map {i+1}")
            self._layout_slots.append(slot)

        self.lbl_layout_status.setText(f"Grid built ({n_rows}×{n_cols}). Configure maps then click 'READ ALL DATA'.")

    def _prompt_read_data(self):
        self.lbl_layout_status.setText("⚠️ Source data changed. Click 'READ ALL DATA' to update.")

    def _read_layout_data(self):
        if not self._layout_slots:
            QMessageBox.warning(self, "No Layout", "Click 'BUILD GRID' first.")
            return

        self.lbl_layout_status.setText("Reading data for all slots… please wait."); self.repaint()
        self._layout_cache.clear()

        for i, slot in enumerate(self._layout_slots):
            lid = slot.cb_layer.currentData()
            lyr = QgsProject.instance().mapLayer(lid) if lid else None
            if lyr is None:
                self._layout_cache[i] = None
                continue

            try: 
                arr, extent = self._read_band(lyr, slot.sp_band.value(), max_px_k=500)
                self._layout_cache[i] = (arr, extent)
            except Exception as e:
                self._layout_cache[i] = None

        self._trigger_layout_draw()

    def _trigger_layout_draw(self):
        if self._is_updating_layout: return
        if not self._layout_cache: return
        self._draw_layout()

    def _draw_layout(self):
        n_rows = self.sp_layout_rows.value(); n_cols = self.sp_layout_cols.value()
        n_slots = n_rows * n_cols

        fig_bg, ax_bg, txt_col = self._get_theme(self.l_cb_bg_color.currentText())
        font_fam = self.l_cb_font_family.currentText()

        self.fig_layout.clf()
        self.fig_layout.set_size_inches(self.sp_fig_w.value(), self.sp_fig_h.value())
        self.fig_layout.patch.set_facecolor(fig_bg)

        gs = gridspec.GridSpec(n_rows, n_cols, figure=self.fig_layout, hspace=self.sp_hspace.value(), wspace=self.sp_wspace.value())

        for i, slot in enumerate(self._layout_slots[:n_slots]):
            row_i = i // n_cols; col_i = i % n_cols
            ax = self.fig_layout.add_subplot(gs[row_i, col_i])
            if ax_bg != "none": ax.set_facecolor(ax_bg)

            title_text = slot.le_title.text()
            subtitle_text = slot.le_subtitle.text()
            title_bold = "bold" if self.l_chk_title_bold.isChecked() else "normal"

            cache_data = self._layout_cache.get(i)
            if cache_data is None:
                ax.text(0.5, 0.5, "No Data / Error", ha="center", va="center", color="#ef4444", transform=ax.transAxes)
                ax.set_title(title_text, color=txt_col, fontfamily=font_fam, fontsize=self.l_sp_title_size.value(), fontweight=title_bold, pad=15 if subtitle_text else 6)
                if subtitle_text:
                    ax.text(0.5, 1.02, subtitle_text, ha='center', va='bottom', transform=ax.transAxes, color=txt_col, fontfamily=font_fam, fontsize=self.l_sp_sub_size.value())
                if not self.l_chk_axes.isChecked(): ax.axis("off")
                continue

            arr, extent = cache_data
            plot_ext = [extent.xMinimum(), extent.xMaximum(), extent.yMinimum(), extent.yMaximum()]
            valid_data = arr[np.isfinite(arr)]
            
            stretch_mode = slot.cb_stretch.currentText()
            v1 = slot.sp_v1.value(); v2 = slot.sp_v2.value()
            
            if len(valid_data) > 0:
                if "Actual" in stretch_mode: vmin, vmax = float(valid_data.min()), float(valid_data.max())
                elif "Percentile" in stretch_mode: vmin, vmax = float(np.percentile(valid_data, v1)), float(np.percentile(valid_data, v2))
                else: vmin, vmax = v1, v2
                actual_min = float(valid_data.min()); actual_max = float(valid_data.max())
            else: 
                vmin, vmax = 0.0, 1.0; actual_min, actual_max = 0.0, 1.0
                
            if np.isclose(vmin, vmax): vmax = vmin + 1

            cmap_name = slot.cb_cmap.currentText()
            if slot.chk_reverse.isChecked(): cmap_name += "_r"
            try: cmap = plt.get_cmap(cmap_name).copy()
            except Exception: cmap = plt.get_cmap("viridis").copy()
            cmap.set_bad(alpha=0)

            im = ax.imshow(arr, cmap=cmap, vmin=vmin, vmax=vmax, extent=plot_ext, interpolation="bilinear", aspect="equal", origin="upper")

            ax.tick_params(colors=txt_col, labelsize=self.l_sp_coord_size.value())
            fmt = self.l_cb_coord_format.currentText(); dec = self.l_sp_coord_decimals.value()

            if "Default" not in fmt:
                ax.xaxis.set_major_formatter(mticker.FuncFormatter(self._make_lon_formatter(fmt, dec)))
                ax.yaxis.set_major_formatter(mticker.FuncFormatter(self._make_lat_formatter(fmt, dec)))
            else:
                ax.xaxis.set_major_formatter(mticker.FormatStrFormatter(f"%.{dec}f"))
                ax.yaxis.set_major_formatter(mticker.FormatStrFormatter(f"%.{dec}f"))

            x_rot = self.l_sp_x_rot.value(); y_rot = self.l_sp_y_rot.value()
            x_ha = "right" if 10 < x_rot < 350 else "center"
            
            if not self.l_chk_axes.isChecked(): ax.axis("off")
            else:
                ax.xaxis.set_major_locator(mticker.MaxNLocator(nbins=self.l_sp_xtick_count.value()))
                ax.yaxis.set_major_locator(mticker.MaxNLocator(nbins=self.l_sp_ytick_count.value()))
                for tick in ax.get_xticklabels(): tick.set_rotation(x_rot); tick.set_ha(x_ha); tick.set_fontfamily(font_fam)
                for tick in ax.get_yticklabels(): tick.set_rotation(y_rot); tick.set_ha("right"); tick.set_fontfamily(font_fam)
                for sp_item in ax.spines.values(): sp_item.set_color(txt_col)

            if self.l_chk_grid.isChecked():
                ls = ("--" if "Dashed" in self.l_cb_grid_style.currentText() else ":" if "Dotted" in self.l_cb_grid_style.currentText() else "-")
                ax.grid(True, color=txt_col, linestyle=ls, linewidth=0.3, alpha=0.4)

            ax.set_title(title_text, color=txt_col, fontfamily=font_fam, fontsize=self.l_sp_title_size.value(), fontweight=title_bold, pad=15 if subtitle_text else 6)
            if subtitle_text:
                ax.text(0.5, 1.02, subtitle_text, ha='center', va='bottom', transform=ax.transAxes, color=txt_col, fontfamily=font_fam, fontsize=self.l_sp_sub_size.value())

            if slot.chk_colorbar.isChecked():
                orient = self.l_cb_orient.currentText(); end_style_opt = self.l_cb_legend_style.currentText()
                extend_str = ("both" if "Both" in end_style_opt else "max" if "Right" in end_style_opt else "min" if "Left" in end_style_opt else "neither")
                cb = self.fig_layout.colorbar(im, ax=ax, orientation=orient, extend=extend_str, extendfrac=0.04, drawedges=False, shrink=self.l_sp_cb_shrink.value(), aspect=self.l_sp_cb_aspect.value(), pad=self.l_sp_cb_pad.value())
                
                lbl_text = self.l_le_cbar_label.text(); lbl_size = self.l_sp_leg_lbl_size.value()
                tick_size = self.l_sp_leg_tick_size.value(); cbar_dec = self.l_sp_cbar_decimals.value()
                lbl_weight = "bold" if self.l_chk_cbar_lbl_bold.isChecked() else "normal"; tick_weight = "bold" if self.l_chk_cbar_tick_bold.isChecked() else "normal"
                lbl_pos = self.l_cb_cbar_lbl_pos.currentText(); lbl_pad = self.l_sp_leg_pad_label.value()

                cb.set_label(lbl_text, color=txt_col, fontfamily=font_fam, fontsize=lbl_size, fontweight=lbl_weight, labelpad=lbl_pad)
                is_vert = orient == "vertical"
                if is_vert:
                    if lbl_pos == "Top": cb.set_label(""); cb.ax.set_title(lbl_text, color=txt_col, fontfamily=font_fam, fontsize=lbl_size, fontweight=lbl_weight, pad=lbl_pad)
                    elif lbl_pos == "Left": cb.ax.yaxis.set_label_position("left")
                    elif lbl_pos == "Right": cb.ax.yaxis.set_label_position("right")
                else:
                    if lbl_pos == "Top": cb.ax.xaxis.set_label_position("top")
                    elif lbl_pos == "Bottom": cb.ax.xaxis.set_label_position("bottom")
                    elif lbl_pos == "Right": cb.set_label(""); cb.ax.text(1.02, 0.5, lbl_text, transform=cb.ax.transAxes, va='center', ha='left', color=txt_col, fontfamily=font_fam, fontsize=lbl_size, fontweight=lbl_weight)
                    elif lbl_pos == "Left": cb.set_label(""); cb.ax.text(-0.02, 0.5, lbl_text, transform=cb.ax.transAxes, va='center', ha='right', color=txt_col, fontfamily=font_fam, fontsize=lbl_size, fontweight=lbl_weight)

                cb.ax.tick_params(colors=txt_col, labelsize=tick_size, pad=self.l_sp_leg_pad_tick.value()); cb.outline.set_edgecolor(txt_col)
                tc = self.l_sp_tick_count.value()
                if self.l_chk_ticks.isChecked():
                    cb.locator = mticker.MaxNLocator(nbins=tc, prune="both"); cb.update_ticks()
                    if is_vert: cb.ax.yaxis.set_major_formatter(mticker.FormatStrFormatter(f"%.{cbar_dec}f"))
                    else: cb.ax.xaxis.set_major_formatter(mticker.FormatStrFormatter(f"%.{cbar_dec}f"))
                else:
                    ticks_pos = np.linspace(vmin, vmax, tc); cb.set_ticks(ticks_pos)
                    if tc == 2: cb.set_ticklabels([f"{actual_min:.{cbar_dec}f}", f"{actual_max:.{cbar_dec}f}"])
                    else:
                        lbls = [f"{actual_min:.{cbar_dec}f}"]; lbls.extend([f"{t:.{cbar_dec}f}" for t in ticks_pos[1:-1]]); lbls.append(f"{actual_max:.{cbar_dec}f}")
                        cb.set_ticklabels(lbls)
                for tick in cb.ax.get_xticklabels() + cb.ax.get_yticklabels(): tick.set_fontfamily(font_fam); tick.set_fontweight(tick_weight)

        self.canvas_layout.draw()
        self.lbl_layout_status.setText(f"Layout rendered: {n_rows}×{n_cols} maps. Live updates enabled.")

    def _export_layout(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Layout", "", "PNG (*.png);;SVG (*.svg);;TIFF (*.tif);;PDF (*.pdf)")
        if not path: return
        dpi = 300 if path.lower().endswith((".png", ".tif")) else 150
        self.fig_layout.savefig(path, dpi=dpi, bbox_inches="tight", facecolor=self.fig_layout.get_facecolor(), transparent=("Transparent" in self.l_cb_bg_color.currentText()))
        self.lbl_layout_status.setText(f"Layout exported: {path}")
        QMessageBox.information(self, "Success", f"Layout saved:\n{path}")
        