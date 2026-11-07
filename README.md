# Layers Panel Tools

QGIS plugin that adds buttons to the toolbar of the existing Layers panel: visibility schemes, batch select, layer manager, batch export, polygon select, feature counts, basemap presets, solo, flash locate, and more. Each button, and each function inside a multi-function button, can have its own title and keyboard shortcut.

- **Page:** https://yuyouhui.online/tools/qgis/layers-panel-tools/
- **Issues:** https://github.com/AutoFYQ323/layers-panel-tools/issues
- **QGIS:** 3.28 through 4.99 (Qt 5 and Qt 6)
- **License:** GNU GPL v2 (`layers_panel_tools/LICENSE`)
- **Languages:** Chinese, English, Spanish, French, Arabic. The first open follows the QGIS interface language, then the system language; anything else starts in English. The choice is remembered. Arabic lays plugin windows out from right to left.
- **Data:** local project layers and files you choose. This plugin does not download data, sign in to a website, or call an external service.

After installation there is no icon on the main QGIS toolbar. Every button, including the settings button, sits on the Layers panel toolbar. Eleven tools are on by default. Fourteen more are one click away in Layers Panel Tools settings.

Install the folder `layers_panel_tools` from `layers_panel_tools_1.0.0.zip`, or copy it to `[QGIS profile]/python/plugins/layers_panel_tools`. Quit QGIS completely and open it again.

Shortcuts work only while the QGIS main window has focus. A shortcut already used by QGIS or by another button is refused, and the holder is named.
