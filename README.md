# Layers Panel Tools

QGIS plugin that adds buttons to the toolbar of the existing Layers panel. Version **1.0.5**. There is no icon on the main QGIS toolbar, and the built-in Layers panel is not replaced.

- **Page:** https://yuyouhui.online/tools/qgis/layers-panel-tools/
- **Issues:** https://github.com/AutoFYQ323/layers-panel-tools/issues
- **QGIS:** 3.28 through 4.99 (Qt 5 and Qt 6)
- **License:** GNU GPL v2 (`layers_panel_tools/LICENSE`)
- **Languages:** 中文, English, Español, Français, العربية. The first open follows the QGIS interface language, then the system language; anything else starts in English. The choice is remembered. Arabic lays plugin windows out from right to left.
- **Data:** local project layers and files you choose. This plugin does not download data, sign in to a website, or call an external service.

## On by default (14)

Labels, batch select, layer manager, edit timeline, batch export, polygon select, feature count, visibility schemes, basemap presets, solo, flash locate, layer actions, line marks, class export.

Thirteen more are one click away in the settings button at the end of the same toolbar: organize, repair sources, find, show all, hide all, move, opacity, copy style, rename, copy files, color tags, scale check, and render check. The old “split by field into subset layers” button is gone. Writing one file per field value is class export.

## What 1.0.5 adds

- **Batch export** can write one file per layer, or one merged file. KML, GML, GeoPackage, and SQLite keep several layers in one file. Excel and ODS keep one sheet per layer. A CSV file cannot hold several sheets: leave “one table” unchecked and the plugin writes a same-name Excel workbook, one sheet per layer; check it and every layer goes into one CSV table, with each field name kept once. A dialog says where the files were written.
- **Layer actions:** clear every vector feature, start editing, save and stop editing, copy an empty layer, or copy the layer with its features. Start editing and save-and-close stay quiet when they succeed.
- **Line marks:** label the start, the end, and the length in metres at the ends of the selected lines. Nothing is written into the layer.
- **Class export:** one layer, one file per legend class or per distinct field value. A classified layer starts on legend classes; any other layer starts on a field. The format starts as ESRI Shapefile. Classified layers are listed in bold red.
- **Layer right-click:** the System properties page can reorder, hide, and rename native items, and can add the plugin actions that belong on that menu. The list shows `original(custom)`; the menu itself shows only the name inside the parentheses. Reset on that page restores only the menu.

Each button, and each function inside a multi-function button, can have its own title and keyboard shortcut. Shortcuts work only while the QGIS main window has focus. A shortcut already used by QGIS or by another button is refused, and the holder is named.

When only a category row is selected, solo, flash, and “toggle the selected category” act on that category. A selected layer row still acts on the whole layer.

## Install

1. Download [layers_panel_tools_1.0.5.zip](https://github.com/AutoFYQ323/layers-panel-tools/releases), or use the `layers_panel_tools` folder in this repository. The same zip is also on the page above, named `layers-panel-tools-1.0.5.zip`. You can also search for Layers Panel Tools in the QGIS plugin repository.
2. In QGIS: **Plugins → Manage and Install Plugins → Install from ZIP**.
3. Quit QGIS completely and open it again. Buttons are on the Layers panel toolbar. Settings is the last button on that bar.

## Develop

Run checks with the QGIS Python (this machine: QGIS 3.40.11):

```
python layers_panel_tools/check_i18n.py
python layers_panel_tools/self_test.py
```

`check_i18n.py` requires every user-visible sentence in 中文, English, Español, Français, and العربية. Pack with `python TEST/pack_release.py`. The zip is written in `TEST` and is not committed.
