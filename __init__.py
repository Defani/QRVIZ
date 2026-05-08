# QRVIZ — Scientific Raster Visualization for QGIS
# License: GNU GPL v2 or later
# https://github.com/Defani/QRVIZ


def classFactory(iface):
    from .qrviz import QRVIZPlugin
    return QRVIZPlugin(iface)
