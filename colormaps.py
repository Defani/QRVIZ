"""
colormaps.py — Custom palette registry for QRVIZ.

Registers domain-specific colormaps (remote sensing, vegetation indices,
mangrove, water, urban, terrain) alongside the standard Matplotlib palette
library.  All palettes are registered via plt.colormaps so they are available
anywhere Matplotlib is used within QGIS.
"""

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

# ─────────────────────────────────────────────────────────────────────────────
#  Domain-specific custom palettes (hex colour lists, low → high)
# ─────────────────────────────────────────────────────────────────────────────
CUSTOM_PALETTES = {
    # Vegetation / NDVI
    "NDVI_Custom": [
        "#FFFFFF", "#CE7E45", "#DF923D", "#F1B555", "#FCD163",
        "#99B718", "#74A901", "#66A000", "#529400", "#3E8601",
        "#207401", "#056201", "#004C00",
    ],
    "RdYlGn_Custom": [
        "#d73027", "#f46d43", "#fdae61", "#fee08b",
        "#d9ef8b", "#a6d96a", "#66bd63", "#1a9850",
    ],
    "Custom_BlkRdYlGn": [
        "#000000", "#a50026", "#d73027", "#f46d43", "#fdae61",
        "#fee08b", "#ffffbf", "#d9ef8b", "#a6d96a", "#66bd63",
        "#1a9850", "#006837",
    ],
    "YlGn_Custom": [
        "#ffffe5", "#f7fcb9", "#d9f0a3", "#addd8e",
        "#78c679", "#41ab5d", "#238443", "#005a32",
    ],
    "Red2Green": [
        "#a50026", "#d73027", "#f46d43", "#fdae61", "#fee08b",
        "#ffffbf", "#d9ef8b", "#a6d96a", "#66bd63", "#1a9850", "#006837",
    ],
    "Brown2Green": [
        "#8c510a", "#bf812d", "#dfc27d", "#f6e8c3", "#f5f5f5",
        "#c7eae5", "#80cdc1", "#35978f", "#01665e",
    ],
    # Water / Ocean
    "Water": ["#00008b", "#0000ff", "#00bfff", "#add8e6", "#ffffff"],
    "Ocean_Deep": [
        "#00204d", "#00336f", "#0a4f8c", "#1a6ba8", "#2a8bc3",
        "#3aaad0", "#55c5d8", "#7dd7df", "#aae8e8", "#d5f5f5",
    ],
    # Urban / Built-up
    "Urban": [
        "#1a9850", "#a6d96a", "#fee08b",
        "#fdae61", "#f46d43", "#d73027",
    ],
    # Agriculture
    "Agriculture": [
        "#3f260b", "#835216", "#c7a52f",
        "#e3e94b", "#7fc41d", "#2f800e", "#134504",
    ],
    # Terrain / Elevation
    "Terrain_Custom": [
        "#006600", "#009900", "#33cc33", "#ffff00",
        "#ff9900", "#cc6600", "#993300", "#ffffff",
    ],
    # Diverging
    "RdBu_Custom": [
        "#b2182b", "#ef8a62", "#fddbc7",
        "#f7f7f7", "#d1e5f0", "#67a9cf", "#2166ac",
    ],
    "Spectral_Custom": [
        "#d53e4f", "#f46d43", "#fdae61", "#fee08b", "#ffffbf",
        "#e6f598", "#abdda4", "#66c2a5", "#3288bd",
    ],
    # Sequential — Blue
    "Blues_Custom": [
        "#f7fbff", "#deebf7", "#c6dbef", "#9ecae1",
        "#6baed6", "#4292c6", "#2171b5", "#084594",
    ],
    # Perceptually uniform
    "Viridis_Custom": [
        "#440154", "#414487", "#2a788e",
        "#22a884", "#7ad151", "#fde725",
    ],
    "Magma_Custom": [
        "#000004", "#3b0f70", "#8c2981",
        "#de4968", "#fe9f6d", "#fcfdbf",
    ],
    "Inferno_Custom": [
        "#000004", "#20114b", "#57157e", "#912281",
        "#cb4679", "#eb7852", "#fdb32f", "#f0f921",
    ],
    "Plasma_Custom": [
        "#0d0887", "#46039f", "#7201a8", "#9c179e", "#bd3786",
        "#d8576b", "#ed7953", "#fb9f3a", "#fdca26", "#f0f921",
    ],
    "Cividis_Custom": [
        "#00204d", "#00336f", "#164870", "#345e75", "#50737b",
        "#6e8a83", "#8ea28c", "#b0bb98", "#d3d4a6", "#f6edb3",
    ],
    # Greyscale
    "Greys_Custom": [
        "#ffffff", "#f0f0f0", "#d9d9d9", "#bdbdbd",
        "#969696", "#737373", "#525252", "#252525",
    ],
    # Rainbow (use sparingly — perceptually non-uniform)
    "Rainbow_Custom": [
        "#ff0000", "#ff7f00", "#ffff00",
        "#00ff00", "#0000ff", "#4b0082", "#8b00ff",
    ],
    # Mangrove-specific
    "Mangrove": [
        "#f5f5dc", "#c8e6c9", "#a5d6a7", "#66bb6a",
        "#388e3c", "#1b5e20", "#0a3d1f", "#051a0d",
    ],
    "Carbon_Stock": [
        "#fff9c4", "#fff176", "#ffee58", "#fdd835",
        "#f9a825", "#e65100", "#bf360c", "#4e342e",
    ],
    "SAR_Backscatter": [
        "#000000", "#1a1a2e", "#16213e", "#0f3460",
        "#533483", "#e94560", "#f5a623", "#ffffff",
    ],
}

# Register all custom palettes with Matplotlib
for _name, _hex_colors in CUSTOM_PALETTES.items():
    _cmap = mcolors.LinearSegmentedColormap.from_list(_name, _hex_colors)
    try:
        plt.colormaps.register(_cmap, name=_name, force=True)
    except AttributeError:
        plt.register_cmap(name=_name, cmap=_cmap)

# ─────────────────────────────────────────────────────────────────────────────
#  Full ordered colormap list (custom first, then standard Matplotlib)
# ─────────────────────────────────────────────────────────────────────────────
COLORMAPS = list(CUSTOM_PALETTES.keys()) + [
    # Perceptually uniform
    "viridis", "plasma", "magma", "inferno", "cividis",
    # Diverging
    "RdYlGn", "RdYlBu", "BrBG", "PRGn", "PiYG", "seismic", "coolwarm",
    # Sequential
    "YlGn", "YlGnBu", "GnBu", "BuGn", "PuBuGn", "PuBu", "BuPu",
    "RdPu", "PuRd", "OrRd", "YlOrRd", "YlOrBr", "Purples",
    "Blues", "Greens", "Oranges", "Reds",
    # Misc
    "gray", "bone", "copper", "terrain", "ocean", "gist_earth",
    "hot", "cool", "rainbow", "jet", "hsv",
    "pink", "spring", "summer", "autumn", "winter",
    "flag", "prism", "nipy_spectral", "gist_rainbow",
]
# Deduplicate while preserving order
COLORMAPS = list(dict.fromkeys(COLORMAPS))
