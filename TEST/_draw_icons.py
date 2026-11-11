# -*- coding: utf-8 -*-
"""Draw 32x32 toolbar icons. Each one is a different picture of its job."""

import os

from PIL import Image, ImageDraw

OUT = os.path.join(os.path.dirname(__file__), "icon_drafts")
BLUE = (21, 101, 192, 255)
SOFT = (21, 101, 192, 70)
INK = (21, 101, 192, 255)


def new():
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    return image, ImageDraw.Draw(image)


def save(image, name):
    os.makedirs(OUT, exist_ok=True)
    small = image.resize((32, 32), Image.Resampling.LANCZOS)
    small.save(os.path.join(OUT, name + ".png"))


def organize():
    image, draw = new()
    draw.rounded_rectangle((8, 10, 40, 22), radius=3, outline=BLUE, width=3)
    draw.rounded_rectangle((14, 26, 50, 38), radius=3, outline=BLUE, width=3)
    draw.rounded_rectangle((8, 42, 44, 54), radius=3, outline=BLUE, width=3)
    save(image, "organize")


def repair():
    image, draw = new()
    draw.arc((8, 16, 30, 40), 200, 40, fill=BLUE, width=4)
    draw.arc((34, 24, 56, 48), 20, 220, fill=BLUE, width=4)
    draw.line((18, 22, 28, 32), fill=BLUE, width=4)
    draw.line((36, 32, 46, 42), fill=BLUE, width=4)
    save(image, "repair")


def find():
    image, draw = new()
    draw.ellipse((8, 8, 40, 40), outline=BLUE, width=4)
    draw.line((36, 36, 54, 54), fill=BLUE, width=5)
    save(image, "find")


def layer_manager():
    image, draw = new()
    draw.rounded_rectangle((8, 8, 40, 22), radius=3, fill=SOFT, outline=BLUE, width=3)
    draw.rounded_rectangle((14, 24, 46, 38), radius=3, fill=SOFT, outline=BLUE, width=3)
    draw.rounded_rectangle((20, 40, 52, 54), radius=3, fill=SOFT, outline=BLUE, width=3)
    save(image, "layer_manager")


def show_all():
    image, draw = new()
    draw.arc((6, 22, 58, 50), 200, 340, fill=BLUE, width=4)
    draw.ellipse((24, 18, 40, 34), outline=BLUE, width=4)
    draw.ellipse((29, 23, 35, 29), fill=BLUE)
    save(image, "show_all")


def hide_all():
    image, draw = new()
    draw.arc((6, 22, 58, 50), 200, 340, fill=BLUE, width=4)
    draw.ellipse((24, 18, 40, 34), outline=BLUE, width=4)
    draw.line((12, 50, 52, 12), fill=BLUE, width=4)
    save(image, "hide_all")


def edit_timeline():
    image, draw = new()
    draw.ellipse((10, 10, 54, 54), outline=BLUE, width=4)
    draw.line((32, 32, 32, 18), fill=BLUE, width=3)
    draw.line((32, 32, 44, 38), fill=BLUE, width=3)
    draw.arc((4, 28, 22, 46), 120, 300, fill=BLUE, width=3)
    draw.polygon([(6, 34), (4, 44), (14, 40)], fill=BLUE)
    save(image, "edit_timeline")


def export():
    image, draw = new()
    draw.rounded_rectangle((8, 14, 44, 50), radius=3, outline=BLUE, width=3)
    draw.line((46, 18, 46, 46), fill=BLUE, width=4)
    draw.polygon([(40, 28), (58, 32), (40, 36)], fill=BLUE)
    save(image, "export")


def poly_select():
    image, draw = new()
    points = [(32, 8), (54, 24), (46, 52), (16, 52), (10, 24)]
    draw.line(points + [points[0]], fill=BLUE, width=3)
    for x, y in points:
        draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=BLUE)
    save(image, "poly_select")


def select():
    image, draw = new()
    tops = (10, 28, 46)
    for index, top in enumerate(tops):
        draw.rounded_rectangle((8, top, 22, top + 12), radius=2, outline=BLUE, width=3)
        if index < 2:
            draw.line((11, top + 6, 14, top + 10), fill=BLUE, width=3)
            draw.line((14, top + 10, 20, top + 3), fill=BLUE, width=3)
        draw.line((28, top + 6, 54, top + 6), fill=BLUE, width=3)
    save(image, "select")


def move():
    image, draw = new()
    draw.rounded_rectangle((22, 22, 42, 42), radius=3, outline=BLUE, width=3)
    draw.polygon([(32, 6), (24, 18), (40, 18)], fill=BLUE)
    draw.polygon([(32, 58), (24, 46), (40, 46)], fill=BLUE)
    draw.polygon([(6, 32), (18, 24), (18, 40)], fill=BLUE)
    draw.polygon([(58, 32), (46, 24), (46, 40)], fill=BLUE)
    save(image, "move")


def opacity():
    image, draw = new()
    draw.rounded_rectangle((10, 10, 54, 54), radius=6, outline=BLUE, width=3)
    draw.pieslice((14, 14, 50, 50), 90, 270, fill=BLUE)
    save(image, "opacity")


def labels():
    image, draw = new()
    draw.polygon([(18, 50), (32, 10), (46, 50)], outline=BLUE)
    draw.line((22, 38, 42, 38), fill=BLUE, width=3)
    draw.line((18, 50, 32, 10), fill=BLUE, width=4)
    draw.line((46, 50, 32, 10), fill=BLUE, width=4)
    save(image, "labels")


def switch():
    image, draw = new()
    draw.rounded_rectangle((8, 12, 56, 28), radius=8, outline=BLUE, width=3)
    draw.ellipse((36, 14, 52, 26), fill=BLUE)
    draw.rounded_rectangle((8, 36, 56, 52), radius=8, outline=BLUE, width=3)
    draw.ellipse((12, 38, 28, 50), fill=BLUE)
    save(image, "switch")


def basemap():
    image, draw = new()
    draw.rounded_rectangle((8, 12, 56, 52), radius=4, outline=BLUE, width=3)
    draw.line((8, 28, 56, 28), fill=BLUE, width=2)
    draw.line((8, 40, 56, 40), fill=BLUE, width=2)
    draw.line((24, 12, 24, 52), fill=BLUE, width=2)
    draw.line((40, 12, 40, 52), fill=BLUE, width=2)
    draw.polygon([(32, 16), (28, 26), (36, 26)], fill=BLUE)
    save(image, "basemap")


def style():
    image, draw = new()
    draw.line((18, 46, 40, 16), fill=BLUE, width=5)
    draw.polygon([(36, 12), (50, 18), (42, 24)], fill=BLUE)
    draw.ellipse((10, 44, 22, 56), outline=BLUE, width=3)
    save(image, "style")


def files():
    image, draw = new()
    draw.rounded_rectangle((16, 8, 48, 48), radius=3, outline=BLUE, width=3)
    draw.rounded_rectangle((10, 14, 42, 54), radius=3, fill=(255, 255, 255, 230), outline=BLUE, width=3)
    draw.line((16, 26, 36, 26), fill=BLUE, width=2)
    draw.line((16, 34, 34, 34), fill=BLUE, width=2)
    draw.line((16, 42, 30, 42), fill=BLUE, width=2)
    save(image, "files")


def main():
    organize()
    repair()
    find()
    layer_manager()
    show_all()
    hide_all()
    edit_timeline()
    export()
    poly_select()
    select()
    move()
    opacity()
    labels()
    switch()
    basemap()
    style()
    files()


if __name__ == "__main__":
    main()
