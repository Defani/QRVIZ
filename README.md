# RasterViz

<div align="center">



### Scientific Raster Visualization Plugin for QGIS

**Rasterio-inspired raster rendering with a fully interactive GUI for publication-quality scientific maps.**

![QGIS](https://img.shields.io/badge/QGIS-3.x-green?style=for-the-badge\&logo=qgis)
![Python](https://img.shields.io/badge/Python-3.x-blue?style=for-the-badge\&logo=python)
![License](https://img.shields.io/badge/License-GPLv3-orange?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Stable-success?style=for-the-badge)

</div>

---
<img width="1920" height="1080" alt="Screenshot 2026-05-08 015933" src="https://github.com/user-attachments/assets/a12bdfdf-45b7-4139-bf52-f913ee2e3365" />

## Overview

**RasterViz** is a professional raster visualization plugin for QGIS designed for researchers, GIS analysts, remote sensing practitioners, environmental scientists, and cartographers who require high-quality scientific raster rendering directly inside the QGIS environment.

The plugin replicates the clean visualization aesthetics of Python's `rasterio.show()` workflow while eliminating the need for external scripting or notebook-based rendering. RasterViz combines scientific visualization principles with a modern PyQt5 graphical user interface, enabling users to generate publication-ready raster maps interactively.

Unlike conventional QGIS styling workflows, RasterViz focuses on:

* Scientific color rendering
* Advanced raster stretching
* Interactive histogram analysis
* Publication-quality legends and colorbars
* Remote sensing optimized colormaps
* Fast live-preview rendering
* Export-ready scientific layouts


---

# Key Features

## Rasterio-Style Scientific Rendering

RasterViz emulates the visual philosophy of Python scientific plotting libraries such as:

* rasterio
* matplotlib
* numpy-based scientific rendering workflows

while remaining fully integrated inside QGIS through a graphical user interface.

---

## Continuous Single-Band Rendering

Render grayscale or continuous raster datasets using advanced stretch methods:

### Supported Stretch Methods

* Percentile Stretch
* Min-Max Stretch
* Manual Stretch
* Dynamic Range Adjustment

### Capabilities

* Real-time visualization updates
* Scientific colormap support
* Histogram-assisted contrast tuning
* Smooth interpolation rendering
* High-resolution output rendering



---

## Discrete / Classified Raster Visualization

RasterViz supports fully customized classified raster rendering.
<img width="1920" height="1080" alt="Screenshot 2026-05-08 023559" src="https://github.com/user-attachments/assets/40073bb4-7204-41eb-907e-263f8881ace1" />

### Features

* Automatic gridcode scanning
* Per-class color assignment
* Editable class labels
* Decimal precision control
* Custom legend appearance
* Publication-ready classified maps

Ideal for:

* Land cover classification
* Habitat mapping
* Forest type analysis
* Segmentation outputs
* Thematic raster products

---

##  RGB Composite Rendering

Generate professional RGB composite imagery directly inside QGIS.

### Supported Features

* Independent stretch per band
* Real-time preview
* Contrast enhancement
* Percentile clipping
* Scientific RGB balancing


---

## Scientific Colorbar System

RasterViz includes a highly configurable scientific colorbar engine.

### Supported Options

* Horizontal colorbar
* Vertical colorbar
* Pointed colorbar
* Extend styles:

  * both
  * max
  * min
  * neither
* Adjustable geometry
* Tick formatting
* Publication-ready styling

---



## Coordinate Formatting System

Multiple coordinate display formats are supported:

* Decimal Degree
* Degrees Minutes Seconds (DMS)
* Degrees Minutes (DM)
* Native projected coordinates
* UTM / meter coordinates

Suitable for scientific cartography and geospatial publications.

---

## Live Preview Engine

RasterViz uses cached NumPy arrays to accelerate rendering.

### Benefits

* No repeated raster re-reading
* Faster parameter adjustment
* Responsive GUI interaction
* Efficient rendering workflow

This significantly improves performance when working with large rasters.

---

## Publication-Quality Export

Export visualization outputs directly into high-resolution scientific formats.

### Supported Export Formats

* PNG (300 DPI)
* SVG
* TIFF
* PDF

Suitable for:

* Journal figures
* Conference posters
* Thesis illustrations
* Scientific reports
* Remote sensing publications

---



---

# Technical Architecture

## Built With

RasterViz is developed using:

* PyQGIS
* PyQt5
* NumPy
* Matplotlib (Qt5Agg backend)
* Scientific raster rendering workflows

---

## Core Design Principles

The plugin was designed around:

* Scientific reproducibility
* GUI-based accessibility
* High-performance rendering
* Publication-quality output
* Minimal workflow friction
* Remote sensing compatibility

---

# Installation

## Method 1 — Install from ZIP

1. Download the latest RasterViz release.
2. Open QGIS.
3. Navigate to:

```text
Plugins → Manage and Install Plugins → Install from ZIP
```

4. Select the downloaded ZIP file.
5. Activate the plugin.

---

## Method 2 — Manual Installation

1. Clone the repository:

```bash
git clone https://github.com/Defani/RasterViz.git
```

2. Copy the folder into your QGIS plugins directory.

Typical paths:

### Windows

```text
C:\Users\<username>\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins
```

### Linux

```text
~/.local/share/QGIS/QGIS3/profiles/default/python/plugins
```

### macOS

```text
~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins
```

3. Restart QGIS.
4. Enable RasterViz from the Plugin Manager.

---

# Quick Start

## Continuous Raster Workflow

1. Load a raster into QGIS.
2. Open RasterViz.
3. Select the raster layer.
4. Choose:

   * Colormap
   * Stretch method
   * Percentile or manual range
5. Adjust histogram boundaries.
6. Export the final visualization.

---

## RGB Composite Workflow

1. Open the RGB tab.
2. Select:

   * Red band
   * Green band
   * Blue band
3. Configure individual stretches.
4. Preview the composite.
5. Export the figure.

---

## Classified Raster Workflow

1. Load a classified raster.
2. Enable discrete rendering.
3. Scan raster classes automatically.
4. Assign:

   * Colors
   * Labels
   * Decimal precision
5. Generate publication-ready thematic maps.

---

# Use Cases

## Remote Sensing

* Vegetation indices
* Change detection
* Multispectral composites
* Environmental monitoring
* Mangrove ecosystem analysis

---

## Forestry Applications

* Above-ground biomass mapping
* Forest degradation analysis
* Canopy density visualization
* Conservation mapping

---

## Environmental Science

* Water quality analysis
* Coastal monitoring
* Wetland visualization
* Ecological spatial analysis

---

## Academic Research

RasterViz is suitable for:

* Scientific papers
* Undergraduate theses
* Master's dissertations
* Doctoral research
* Journal publication figures

---

# Performance Optimization

RasterViz incorporates several optimization strategies:

* Cached NumPy raster arrays
* Efficient Matplotlib rendering
* Reduced raster re-reading
* Interactive GUI refresh optimization
* Lightweight rendering architecture

These optimizations improve usability for large remote sensing datasets.

---

# Compatibility

| Component        | Supported                                      |
| ---------------- | ---------------------------------------------- |
| QGIS             | 3.x                                            |
| Python           | 3.x                                            |
| Operating System | Windows / Linux / macOS                        |
| Raster Types     | GeoTIFF, IMG, ASC, and compatible GDAL rasters |

---

# Official QGIS Plugin Repository

RasterViz is officially available on the QGIS Plugin Repository.

| Information     | Details                                                                            |
| --------------- | ---------------------------------------------------------------------------------- |
| Plugin Name     | RasterViz                                                                          |
| Plugin ID       | 5157                                                                               |
| QGIS Repository | [https://plugins.qgis.org/plugins/qrviz/](https://plugins.qgis.org/plugins/qrviz/) |

---

# Installation via QGIS Plugin Manager

1. Open QGIS.
2. Navigate to:

```text
Plugins → Manage and Install Plugins
```

3. Search for:

```text
RasterViz
```

4. Click **Install Plugin**.
5. Launch RasterViz from the Plugins menu or toolbar.

---

# Repository

Official Repository:

```text
https://github.com/Defani/RasterViz
```

---

# Author

**Defani Arman Alfitriansyah**

Remote Sensing and GIS Researcher

Specialization:

* Scientific raster visualization
* Remote sensing workflows
* Mangrove ecosystem analysis
* Google Earth Engine
* GIS cartography

Email:

```text
defaniarman@gmail.com
```

---

# License

This project is licensed under the GNU General Public License v3.0 (GPL-3.0).

The GPL license ensures that RasterViz remains free and open-source software, allowing users to study, modify, and redistribute the plugin under the same license terms.

See the LICENSE file for full license details.

---

# Citation

If you use RasterViz in academic work, please cite:

```text
Alfitriansyah, D. A. (2026). RasterViz: Scientific Raster Visualization Plugin for QGIS.
GitHub Repository: https://github.com/Defani/RasterViz
```

---

# Future Development

Planned future features include:

* Batch rendering system
* Layout manager integration
* Advanced annotation tools
* Multi-panel scientific plotting
* Additional scientific colormaps
* Interactive raster statistics
* Cloud optimized raster support
* Temporal raster visualization

---

# Acknowledgements

RasterViz was inspired by the scientific visualization ecosystem surrounding:

* rasterio
* matplotlib
* NumPy
* PyQGIS
* Open-source remote sensing workflows

Special thanks to the QGIS and scientific Python communities.

---

<div align="center">

## RasterViz

### Bringing scientific raster visualization into an interactive QGIS workflow.

</div>
