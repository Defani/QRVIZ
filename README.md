
# <img src="icon.png" alt="RasterViz Icon" width="56" valign="middle"> RasterViz — Scientific Raster Visualization Plugin for QGIS

<p align="left">
  <a href="https://defani.github.io/QRasterVIZ/"><img src="https://img.shields.io/badge/Plugin_Web_Page-Visit-4f8fff?style=flat-square&logo=google-chrome&logoColor=white" alt="Plugin Web Page"/></a>
  <a href="https://plugins.qgis.org/"><img src="https://img.shields.io/badge/QGIS_Plugin-Pending_Review-brightgreen?style=flat-square&logo=qgis&logoColor=white" alt="QGIS Plugin"/></a>
  <a href="https://github.com/Defani/QRasterVIZ/releases"><img src="https://img.shields.io/badge/version-1.1.0-blue?style=flat-square" alt="Version"/></a>
  <a href="https://www.gnu.org/licenses/old-licenses/gpl-2.0.html"><img src="https://img.shields.io/badge/license-GPL--2.0--or--later-green?style=flat-square" alt="License"/></a>
  <a href="https://github.com/Defani/QRasterVIZ/issues"><img src="https://img.shields.io/badge/issues-open-orange?style=flat-square" alt="Issues"/></a>
</p>

> **RasterViz** provides a practical way to create publication-quality raster visualizations styled after `rasterio.show()` directly inside QGIS.
---

## Overview

QGIS provides adequate native raster symbology, but generating a publication-ready figure — with a properly styled colorbar, geographic coordinate labels, consistent typography, and controlled stretch — still requires switching to Python scripts or external GIS software. **RasterViz** closes that gap.

The plugin renders raster data through **Matplotlib** (using the `Qt5Agg` backend embedded directly in the QGIS dialog), so every figure it produces is visually identical to what a researcher would generate with:

```python
import rasterio, matplotlib.pyplot as plt
from rasterio.plot import show
src = rasterio.open("ndvi.tif")
show(src, cmap="RdYlGn", title="NDVI")
```

— but with zero scripting required and with far more control over stretch, colorbar geometry, coordinate format, label rotation, and multi-map layout.

---

## Key Features

| Category | Capability |
|---|---|
| **Rendering modes** | Single-band continuous, Discrete/classified, RGB composite |
| **Stretch** | Actual min–max, Percentile (configurable low/high), Manual vmin/vmax |
| **Colormaps** | 24 domain-specific custom palettes + full Matplotlib library (≈ 60 named colormaps) |
| **Colorbar** | Horizontal / vertical; pointed (both/max/min/neither); position, size, label, tick count, tick decimals all configurable |
| **Coordinates** | DMS, DM, Decimal Degree, UTM/Metre; independent X/Y tick count, font size, decimal places |
| **Label rotation** | Independent X-axis and Y-axis tick label rotation (0–360°) |
| **Grid lines** | Solid, dashed, dotted; toggleable |
| **Background** | Soft Black, White, Transparent (dark text), Transparent (light text) |
| **Typography** | Any font installed on the system; configurable sizes for title, coordinates, colorbar |
| **Discrete mapping** | Auto scan gridcodes, per-class colour (swatch + hex), editable label, per-class decimal places |
| **Layout series** | Configurable N×M grid of maps; each sub-map has independent layer, band, colormap, stretch, title, colorbar toggle |
| **Export** | PNG (300 DPI), SVG, GeoTIFF, PDF |
| **Live preview** | All parameter changes re-render instantly from a cached NumPy array — no disk re-read |

---

## Package Dependencies

RasterViz is built entirely on packages that ship with QGIS on all major platforms. **No additional pip installation is required** for standard usage.

| Package | Role | Ships with QGIS |
|---|---|---|
| **PyQGIS** (`qgis.core`, `qgis.PyQt`) | Layer access, raster data provider, QGIS GUI integration | ✅ Yes |
| **PyQt5** (`PyQt5.QtWidgets`, `.QtGui`, `.QtCore`) | All dialog, widget, and layout construction | ✅ Yes |
| **NumPy** | Raster array operations, stretch computation, RGBA image assembly | ✅ Yes |
| **Matplotlib** (`pyplot`, `colors`, `ticker`, `patches`, `gridspec`, `backend_qt5agg`) | Figure rendering, colormap registry, colorbar, tick formatting | ✅ Yes |
| `os` | File path resolution | ✅ Python stdlib |

> **Summary:** `PyQGIS + PyQt5 + NumPy + Matplotlib` — all bundled with the standard QGIS installation on Windows (OSGeo4W), Linux, and macOS.

---

## Installation

### Requirements

- QGIS **≥ 3.0** (tested up to 3.x series)
- Python **≥ 3.6** (comes with QGIS)
- NumPy, Matplotlib (both included in QGIS default install)

### Install via QGIS Plugin Manager (Recommended)

> *Pending official QGIS plugin repository approval.*

1. Open QGIS → **Plugins** → **Manage and Install Plugins…**
2. Search for **RasterViz** in the *All* tab.
3. Click **Install Plugin**.
4. Access via **Raster** menu → **QRVIZ** → **QRVIZ — Scientific Raster Visualization**.

### Install from ZIP

1. Download the latest release ZIP from the [Releases page](https://github.com/Defani/QRasterVIZ/releases).
2. Open QGIS → **Plugins** → **Manage and Install Plugins…** → **Install from ZIP**.
3. Browse to the downloaded `.zip` file and click **Install Plugin**.

### Install from Source

```bash
# Clone the repository
git clone https://github.com/Defani/QRasterVIZ.git

# Copy the plugin folder to your QGIS plugins directory
# Windows (OSGeo4W):
cp -r QRasterVIZ/qrviz %APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\qrviz

# Linux:
cp -r QRasterVIZ/qrviz ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/qrviz

# macOS:
cp -r QRasterVIZ/qrviz ~/Library/Application\ Support/QGIS/QGIS3/profiles/default/python/plugins/qrviz
```

Then in QGIS: **Plugins → Manage and Install Plugins → Installed** — tick **QRVIZ** to activate.

---

## Plugin Interface

<img width="1920" height="1080" alt="Screenshot 2026-05-09 175743" src="https://github.com/user-attachments/assets/f7f9681c-5d44-42c7-9fd0-674c364b42d2" />




**Left panel — input controls:**

- **Group 1 — Layer & Band:** Open raster file or select a loaded QGIS layer. Toggle Single Band / RGB mode. Set max pixel resolution for preview.
- **Group 2 — Color Mode & Stretch:** Tab-switch between Continuous and Discrete mode. Full stretch and colormap controls.
- **Group 3 — Export:** Save the current figure.

**Right panel — rendering controls:**

- **Group 4 — Display Control:** Background colour, show/hide grid, axes, colorbar.
- **Group 5 — Title & Font:** Map title text, font family (all system fonts), font sizes.
- **Group 6 — Map Geometry & Coordinates:** Figure axes position (X, Y, W, H as fractions), coordinate format, font size, decimal places, X/Y label rotation, tick count, grid line style.
- **Group 7 — Colorbar Layout:** Orientation, end style (pointed / box), position, length, thickness, label, tick count, tick decimal places, padding.

---

## Quick Start Tutorial

### 1. Open a Raster Layer

Open QGIS and load a single-band GeoTIFF (e.g. an NDVI image derived from Sentinel-2). The layer will appear in the QGIS layer panel.

Launch the plugin via **Raster → QRVIZ → QRVIZ — Scientific Raster Visualization**, or click the toolbar icon.


https://github.com/user-attachments/assets/43229022-5ed2-4978-8b63-0e794f954e4b


In **Group 1**, either:
- Click **OPEN RASTER FILE** to browse directly to a `.tif`, `.img`, or `.vrt`, or
- Select an already-loaded layer from the **Layer** dropdown.

Leave **Single Band** selected. Set **Band: 1** (or whichever band contains your index values).

Click **READ DATA & RENDER**.

The raster will appear in the centre canvas with the default `NDVI_Custom` colormap applied.

---

### 2. Configure Stretch

In **Group 2 → Continuous tab**, three stretch modes are available:

| Mode | When to use |
|---|---|
| **Actual Min–Max** | When the raster has been properly scaled (e.g. NDVI already −1 to 1) |
| **Percentile** | Default recommendation — clips outlier pixels. Default: 2nd–98th percentile |
| **Manual Min–Max** | Enter exact `vmin` / `vmax` values for reproducible figures across dates |

For an NDVI raster, set **Percentile**, `Pmin = 2`, `Pmax = 98`. The canvas updates immediately.

---

### 3. Choose a Colormap


https://github.com/user-attachments/assets/9c410ae5-5bf6-426d-8e4b-c6c43d1b9ed4


Use the **◀ ▶** arrows in Group 2 to cycle through the colormap library. A colour ramp preview is shown inline.

For vegetation mapping, recommended palettes:

```
NDVI_Custom       — white → brown → yellow → dark green (rasterio-style)
RdYlGn_Custom     — red → yellow → green (diverging)
Custom_BlkRdYlGn  — black → red → yellow → dark green (high-contrast)
Mangrove          — beige → progressively dark forest green
```

Enable **Reverse** to invert any palette (e.g. for SAR backscatter where bright = high).

---

### 4. Tune Coordinate Labels


https://github.com/user-attachments/assets/22b17462-122c-447a-a239-de7761c4976c


In **Group 6 — Map Geometry & Coordinates**:

1. Set **Coord Format** to `D (Decimal Degree)` for standard geographic layers.
2. Set **Coord Decimals** to `4` (sufficient for sub-metre precision in degree space).
3. Set **X Tick Count** = `5`, **Y Tick Count** = `5`.
4. Set **X-label Rotation** = `45°` to prevent label overlap on dense longitude ticks.
5. Set **Y-label Rotation** = `0°` for horizontal latitude labels (easier to read).

---

### 5. Style the Colorbar

In **Group 7 — Colorbar Layout**:


https://github.com/user-attachments/assets/649f535d-ab7b-485d-859e-70d888b7b099


1. Set **Orientation** = `horizontal`.
2. Set **End Style** = `Both Pointed` — replicates the rasterio aesthetic.
3. Set **Colorbar Label** = `NDVI`.
4. Leave **Pos X = 0.20**, **Pos Y = 0.05**, **Length = 0.60**, **Thickness = 0.03** (defaults centre the bar below the map).
5. Set **Tick Count** = `5`, **Tick Decimals** = `2`.

The canvas updates live with every change.

---

### 6. Export

In **Group 3**, click **EXPORT IMAGE**. Choose PNG for raster output at 300 DPI, or PDF / SVG for vector-preserving formats.


https://github.com/user-attachments/assets/c7030b7b-450f-4e09-81d7-db49638dab80


---

## Feature Reference

### Single Band — Continuous Rendering

The core rendering path reads the selected band via `QgsRasterDataProvider.block()`, downsamples to a configurable maximum pixel count (default 1,000,000 px) to maintain GUI responsiveness, and caches the result as a NumPy `float64` array. Subsequent parameter changes (stretch, colormap, colorbar) re-render from the cache without disk access.

Nodata values identified by the QGIS data provider are masked as `np.nan` and rendered as transparent pixels when "Transparent Nodata" is checked.

### Discrete / Classified Rendering

Switch to the **Discrete** tab in Group 2. After clicking **READ DATA & RENDER**, click **SCAN GRIDCODES** to automatically detect all unique pixel values. Each class gets its own row with:

- Colour swatch button (opens `QColorDialog`)
- Hex colour input field (live validation)
- Editable text label (shown in the patch legend)
- Decimal places spinbox (controls how the gridcode value is displayed in the legend)

A **Set All Decimals** control applies a uniform decimal count across all rows. A **Nodata Colour** picker (with alpha support) controls the nodata pixel colour independently.

### RGB Three-Band Composite

Select **RGB** mode in Group 1 and assign band indices to R, G, B channels. Each channel is independently stretched using the chosen stretch mode before compositing. Suitable for Sentinel-2 true-colour (B4/B3/B2) or false-colour composites.

### Coordinate Label Control

Four coordinate formats are supported:

| Format | Example output |
|---|---|
| DMS | `106°49'0.0" E` |
| DM | `106°49.000' E` |
| Decimal Degree | `106.8167° E` |
| Default (UTM/Metre) | `476234.0000` |

Tick label rotation is controlled independently for the X-axis (longitude) and Y-axis (latitude). A rotation of 45° on X labels prevents overlap when tick density is high. Y labels at 0° produce horizontal text, which is more readable for latitude values.

### Colormap Library

RasterViz registers **24 domain-specific custom palettes** at startup alongside the full standard Matplotlib palette library, giving access to approximately **60+ named colormaps** in total.

**Custom domain-specific palettes:**

| Palette name | Domain |
|---|---|
| `NDVI_Custom` | NDVI / vegetation greenness |
| `RdYlGn_Custom` | Diverging vegetation health |
| `Custom_BlkRdYlGn` | High-contrast NDVI (dark background maps) |
| `YlGn_Custom` | Sequential green (leaf area, canopy cover) |
| `Red2Green` | Stress-to-health gradient |
| `Brown2Green` | Soil-to-vegetation transition |
| `Mangrove` | Mangrove canopy density |
| `Carbon_Stock` | Biomass / carbon stock (yellow → dark brown) |
| `SAR_Backscatter` | SAR intensity (dark → bright) |
| `Water` | Water depth / turbidity |
| `Ocean_Deep` | Bathymetry / deep water |
| `Urban` | Land use / LULC (vegetation → built-up) |
| `Agriculture` | Cropland mapping |
| `Terrain_Custom` | Elevation / DEM |
| `RdBu_Custom` | Diverging anomaly maps |
| `Spectral_Custom` | General-purpose spectral |
| `Blues_Custom` | Rainfall / moisture sequential |
| `Viridis_Custom` | Perceptually uniform (general) |
| `Magma_Custom` | Perceptually uniform (dark → bright) |
| `Inferno_Custom` | Perceptually uniform (high contrast) |
| `Plasma_Custom` | Perceptually uniform (purple → yellow) |
| `Cividis_Custom` | Colour-vision-deficiency safe |
| `Greys_Custom` | Panchromatic / grayscale |
| `Rainbow_Custom` | Multi-class thematic (use sparingly) |

All palettes are also available in reversed form by enabling **Reverse** in the GUI.

### Colorbar / Legend Layout

For continuous mode, the colorbar is rendered as a Matplotlib `colorbar` instance on a manually positioned `axes`. Four end styles are available:

- **Both Pointed** — the rasterio default; triangular extensions on both ends indicating data extends beyond the mapped range.
- **Right Pointed (Max)** — only the high end is clipped.
- **Left Pointed (Min)** — only the low end is clipped.
- **Box (Standard)** — rectangular, no extension arrows.

All positional and size parameters are specified as fractions of the figure [0, 1], making them scale-independent. The **Auto-position** feature snaps the colorbar to sensible default positions when switching between horizontal and vertical orientation.

For discrete mode, a Matplotlib `legend` with colour patches replaces the continuous colorbar. Patch labels combine the user-defined class label and the numeric gridcode.

### Multi-Map Layout Series

The **Layout Series** tab allows generating a publication-ready figure containing N×M sub-maps from different layers, bands, or colormaps in a single export.

1. Set **Columns** and **Rows** (e.g. 2×2 for four maps, 3×2 for six maps).
2. Click **BUILD LAYOUT GRID** — a configuration row appears for each sub-map.
3. For each sub-map, assign: layer, band, colormap, stretch mode, title, colorbar toggle.
4. Set overall figure dimensions (inches), H-spacing, and W-spacing between panels.
5. Click **READ ALL & RENDER LAYOUT** — data for all slots is read and the multi-panel figure is assembled using `matplotlib.gridspec.GridSpec`.
6. Click **EXPORT LAYOUT** to save.

Coordinate styling (label rotation, format, decimals, grid) from the Single Map tab applies to all sub-maps in the layout, ensuring visual consistency across panels.

### Export

| Format | DPI | Notes |
|---|---|---|
| PNG | 300 | Raster; suitable for journal submission |
| TIFF | 300 | Raster; lossless for archive |
| SVG | 150 | Vector; scalable for poster / slide use |
| PDF | 150 | Vector; suitable for print |

Transparent background exports (PNG / SVG) are fully supported when a transparent background theme is selected.

---

## Codebase Structure

```
qrviz/
├── __init__.py          # QGIS plugin entry point (classFactory)
├── qrviz.py             # QRVIZPlugin class — initGui, unload, run
├── dialog.py            # Main dialog (1 693 lines)
│   ├── DiscreteClassRow     # Per-class colour/label widget
│   ├── LayoutSlotWidget     # Per-slot config widget for layout series
│   └── QRVIZDialog          # Main QDialog
│       ├── _build_single_map_tab()
│       ├── _build_layout_series_tab()
│       ├── _render_continuous()
│       ├── _render_discrete()
│       ├── _render_rgb()
│       ├── _render_layout()
│       ├── _style_axes()        # Rotation, tick count, formatters
│       ├── _make_lon_formatter()
│       ├── _make_lat_formatter()
│       └── export_figure() / _export_layout()
├── colormaps.py         # Custom palette registry (152 lines)
│   ├── CUSTOM_PALETTES  # 24 domain-specific colormaps
│   └── COLORMAPS        # Master ordered list (~60 entries)
├── metadata.txt         # QGIS plugin metadata
├── icon.png             # Toolbar icon
└── LICENSE              # GNU GPL v2 or later
```

**Total source lines: 1,895** across 4 Python files.

---

## Technical Notes

**Raster reading** uses `QgsRasterDataProvider.block()` — the native PyQGIS API — so it respects the layer's CRS, nodata value, and any QGIS-side processing applied to the layer. It does not require `rasterio` or `GDAL` to be installed separately.

**Resolution management:** The `Max pixels (k)` spinbox controls the maximum number of pixels loaded into the preview array. At 1,000 k (= 1,000,000 px), a 10,000 × 10,000 raster is downsampled to approximately 1,000 × 1,000 for the preview. For export-quality rendering, increase this value.

**Live preview** is achieved by caching the NumPy array after the first read and re-calling `_live_update()` on any parameter change signal. The Matplotlib figure is cleared (`fig.clf()`) and redrawn from the cached array, so no I/O occurs during parameter adjustments.

**Coordinate formatters** are implemented as Python closures returned by `_make_lon_formatter()` / `_make_lat_formatter()`, capturing the current format and decimal settings at render time. They are passed to `ax.xaxis.set_major_formatter(mticker.FuncFormatter(...))`.

---

## Contributing

Contributions, bug reports, and feature requests are welcome via the [issue tracker](https://github.com/Defani/QRasterVIZ/issues).

Please follow these guidelines:

- Write code comments in **English**.
- Follow **PEP 8** style conventions.
- Do not commit generated files (`*.pyc`, `__pycache__`, `ui_*.py`, `resources_rc.py`).
- Do not include `.git`, `__MACOSX`, or `.DS_Store` directories in any zip submissions to the QGIS plugin repository.
- Test on at minimum Windows (OSGeo4W) and Linux before opening a pull request.
- Ensure the plugin folder name does not repeat the word "plugin".

---

## License

GNU General Public License v2.0 or later. See [LICENSE](LICENSE) for full terms.

This plugin uses Matplotlib and NumPy, which are distributed under the BSD License. PyQGIS and PyQt5 are distributed under the GNU GPL v2.

---

## Citation

If RasterViz contributes to published research, please cite the software as:

```
Alfitriansyah, D. A. (2026). RasterViz: Scientific Raster Visualization Plugin for QGIS
(Version 1.1.0) [Software]. https://github.com/Defani/QRasterVIZ
```

---

<p align="center">
  Built with PyQGIS · NumPy · Matplotlib · PyQt5 &nbsp;|&nbsp;
  <a href="https://github.com/Defani/QRasterVIZ">github.com/Defani/QRasterVIZ</a>
</p>
