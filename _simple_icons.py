# -*- coding: utf-8 -*-
"""工具条图标：64px 扁平色块绘成，再缩成 32×32 透明 PNG 写入 layers_panel_tools/icons/。

新增按钮时在本脚本里加同名绘制函数，并在 main() 的列表里登记，然后运行：
    python "H:\\QGIS\\Marketplace\\LayersPanelTools\\_simple_icons.py"
不要用复杂文生图；同一张图不要给两个按钮用。
"""

import os

from PIL import Image, ImageDraw

OUT = os.path.join(os.path.dirname(__file__), "layers_panel_tools", "icons")
BG = (0, 0, 0, 0)
BLUE = (47, 128, 237, 255)
GREEN = (46, 160, 67, 255)
ORANGE = (232, 120, 35, 255)
RED = (214, 69, 69, 255)
PURPLE = (130, 80, 220, 255)
GRAY = (110, 118, 128, 255)


def save(img, name):
    Image.open(img).resize((32, 32), Image.Resampling.LANCZOS).save(os.path.join(OUT, name + ".png"), "PNG")


def new():
    im = Image.new("RGBA", (64, 64), BG)
    return im, ImageDraw.Draw(im)


def _finish(im, name):
    path = os.path.join(OUT, "_tmp_%s.png" % name)
    im.save(path, "PNG")
    save(path, name)
    os.remove(path)


def organize():
    im, d = new()
    for y, c in ((14, BLUE), (28, GREEN), (42, ORANGE)):
        d.rounded_rectangle((14, y, 50, y + 10), radius=3, fill=c)
    _finish(im, "organize")


def repair():
    im, d = new()
    d.arc((10, 22, 54, 54), 200, 340, fill=BLUE, width=6)
    d.line((18, 20, 28, 30), fill=BLUE, width=5)
    d.line((42, 34, 52, 44), fill=ORANGE, width=5)
    _finish(im, "repair")


def find():
    im, d = new()
    d.ellipse((12, 12, 40, 40), outline=BLUE, width=6)
    d.line((36, 36, 52, 52), fill=BLUE, width=6)
    _finish(im, "find")


def layer_manager():
    im, d = new()
    for y, c in ((10, BLUE), (24, GREEN), (38, ORANGE)):
        d.rounded_rectangle((12, y, 52, y + 12), radius=4, fill=c)
    _finish(im, "layer_manager")


def show_all():
    im, d = new()
    d.ellipse((22, 18, 42, 34), fill=GREEN)
    d.polygon([(12, 36), (52, 36), (32, 52)], outline=GREEN, width=5)
    _finish(im, "show_all")


def hide_all():
    im, d = new()
    d.ellipse((22, 18, 42, 34), fill=GRAY)
    d.line((12, 48, 52, 16), fill=RED, width=6)
    _finish(im, "hide_all")


def edit_timeline():
    im, d = new()
    d.ellipse((14, 14, 50, 50), outline=PURPLE, width=5)
    d.line((32, 32, 32, 22), fill=PURPLE, width=4)
    d.line((32, 32, 42, 36), fill=PURPLE, width=4)
    _finish(im, "edit_timeline")


def export():
    im, d = new()
    d.rounded_rectangle((14, 18, 40, 50), radius=4, fill=GREEN)
    d.polygon([(44, 28), (58, 34), (44, 40)], fill=BLUE)
    _finish(im, "export")


def poly_select():
    im, d = new()
    pts = [(32, 10), (54, 26), (46, 52), (18, 52), (10, 26)]
    d.polygon(pts, outline=ORANGE, width=5)
    for x, y in pts:
        d.ellipse((x - 4, y - 4, x + 4, y + 4), fill=BLUE)
    _finish(im, "poly_select")


def select():
    im, d = new()
    d.rectangle((12, 14, 26, 28), outline=BLUE, width=4)
    d.rectangle((12, 34, 26, 48), outline=GREEN, width=4)
    d.line((32, 22, 54, 22), fill=GRAY, width=5)
    d.line((32, 42, 54, 42), fill=GRAY, width=5)
    _finish(im, "select")


def move():
    im, d = new()
    d.rounded_rectangle((24, 24, 40, 40), radius=3, outline=BLUE, width=5)
    d.polygon([(32, 6), (26, 18), (38, 18)], fill=GREEN)
    _finish(im, "move")


def opacity():
    im, d = new()
    d.rounded_rectangle((12, 12, 52, 52), radius=6, outline=BLUE, width=5)
    d.rectangle((12, 12, 30, 52), fill=BLUE)
    _finish(im, "opacity")


def labels():
    im, d = new()
    d.polygon([(32, 12), (20, 46), (44, 46)], fill=GREEN)
    d.line((22, 36, 42, 36), fill=WHITE if False else (255, 255, 255, 255), width=4)
    _finish(im, "labels")


def switch():
    im, d = new()
    d.rounded_rectangle((10, 16, 54, 30), radius=12, fill=GRAY)
    d.ellipse((36, 18, 50, 28), fill=GREEN)
    d.rounded_rectangle((10, 36, 54, 50), radius=12, fill=GRAY)
    d.ellipse((14, 38, 28, 48), fill=BLUE)
    _finish(im, "switch")


def basemap():
    im, d = new()
    d.rounded_rectangle((10, 14, 54, 50), radius=4, outline=BLUE, width=4)
    d.line((10, 28, 54, 28), fill=GREEN, width=3)
    d.line((10, 40, 54, 40), fill=GREEN, width=3)
    _finish(im, "basemap")


def style():
    im, d = new()
    d.line((16, 46, 42, 18), fill=ORANGE, width=6)
    d.ellipse((40, 12, 52, 24), fill=PURPLE)
    _finish(im, "style")


def feature_count():
    im, d = new()
    for x, c in ((14, BLUE), (28, GREEN), (42, ORANGE)):
        d.rectangle((x, 14, x + 10, 50), fill=c)
    _finish(im, "feature_count")


def copy_files():
    im, d = new()
    d.rounded_rectangle((8, 18, 30, 46), radius=4, outline=BLUE, width=4)
    d.rounded_rectangle((34, 18, 56, 46), radius=4, fill=GREEN)
    d.polygon([(42, 10), (36, 18), (48, 18)], fill=ORANGE)
    _finish(im, "copy_files")


def split_field():
    im, d = new()
    d.rounded_rectangle((10, 12, 54, 28), radius=4, fill=BLUE)
    d.rounded_rectangle((10, 36, 30, 52), radius=3, fill=GREEN)
    d.rounded_rectangle((38, 36, 54, 52), radius=3, fill=ORANGE)
    _finish(im, "split_field")


def layer_tags():
    im, d = new()
    for x, c in ((14, RED), (28, ORANGE), (42, GREEN)):
        d.ellipse((x, 20, x + 16, 36), fill=c)
    d.rounded_rectangle((12, 42, 52, 54), radius=3, outline=GRAY, width=3)
    _finish(im, "layer_tags")


def flicker():
    im, d = new()
    d.rounded_rectangle((8, 20, 30, 44), radius=4, fill=BLUE)
    d.rounded_rectangle((34, 20, 56, 44), radius=4, outline=ORANGE, width=4)
    d.polygon([(24, 12), (24, 52), (14, 42), (14, 22)], fill=GRAY)
    _finish(im, "flicker")


def solo():
    im, d = new()
    for x in (10, 26, 42):
        d.ellipse((x, 12, x + 14, 26), outline=GRAY, width=3)
    d.ellipse((22, 34, 42, 54), fill=GREEN)
    _finish(im, "solo")


def rename():
    im, d = new()
    d.rectangle((10, 14, 40, 20), fill=GRAY)
    d.rectangle((10, 26, 54, 32), fill=BLUE)
    d.line((10, 44, 54, 44), fill=GRAY, width=5)
    d.line((44, 20, 20, 52), fill=ORANGE, width=5)
    _finish(im, "rename")


def flash():
    im, d = new()
    d.polygon(
        [(32, 6), (38, 24), (56, 26), (42, 36), (48, 54), (32, 44), (16, 54), (22, 36), (8, 26), (26, 24)],
        fill=ORANGE,
    )
    _finish(im, "flash")


def flash_blink():
    im, d = new()
    d.polygon(
        [(32, 6), (38, 24), (56, 26), (42, 36), (48, 54), (32, 44), (16, 54), (22, 36), (8, 26), (26, 24)],
        fill=BLUE,
    )
    _finish(im, "flash_blink")


def scale_check():
    im, d = new()
    d.line((8, 50, 54, 50), fill=GRAY, width=4)
    for x in (14, 26, 38, 50):
        d.line((x, 44, x, 50), fill=GRAY, width=3)
    d.ellipse((20, 10, 48, 38), outline=BLUE, width=5)
    d.line((44, 34, 54, 44), fill=BLUE, width=5)
    _finish(im, "scale_check")


def perf():
    im, d = new()
    d.pieslice((8, 12, 56, 60), 180, 360, outline=GRAY, width=5)
    d.line((32, 36, 48, 20), fill=RED, width=5)
    d.ellipse((28, 32, 36, 40), fill=BLUE)
    _finish(im, "perf")


def main():
    for fn in (
        organize,
        repair,
        find,
        layer_manager,
        show_all,
        hide_all,
        edit_timeline,
        export,
        poly_select,
        select,
        move,
        opacity,
        labels,
        switch,
        basemap,
        style,
        feature_count,
        copy_files,
        split_field,
        layer_tags,
        solo,
        rename,
        flash,
        flash_blink,
        scale_check,
        perf,
    ):
        fn()


if __name__ == "__main__":
    main()
