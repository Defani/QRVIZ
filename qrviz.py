"""
QRVIZ — Scientific Raster Visualization Plugin for QGIS
Provides publication-quality raster rendering styled after rasterio.show(),
with full GUI controls for colormaps, stretch, coordinate labels, grid,
colorbar orientation, label rotation, and multi-map layout series.

License: GNU GPL v2 or later
Repository: https://github.com/Defani/QRVIZ
"""

import os
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon


class QRVIZPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dialog = None

    def initGui(self):
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()
        self.action = QAction(icon, "QRVIZ — Scientific Raster Visualization", self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToRasterMenu("&QRVIZ", self.action)

    def unload(self):
        self.iface.removeToolBarIcon(self.action)
        self.iface.removePluginRasterMenu("&QRVIZ", self.action)
        del self.action

    def run(self):
        if self.dialog is None:
            from .dialog import QRVIZDialog
            self.dialog = QRVIZDialog(self.iface)
        self.dialog.populate_layers()
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
