"""Social card (1200x630) and favicon, using a real invader and ship cropped from the replayed footage."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

A = Path(__file__).resolve().parents[1] / "assets"
BG, INK, MEM, JEV = (6, 7, 8), (236, 230, 216), (231, 166, 74), (134, 217, 157)


def font(names, size):
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            continue
    return ImageFont.load_default()


frame = Image.open(A / "regime_A.png").convert("RGB")  # 480x630, 3x scale
px = frame.load()
for yy in range(frame.height):
    for xx in range(frame.width):
        if px[xx, yy] == (0, 0, 0):
            px[xx, yy] = BG
invader = frame.crop((172, 90, 204, 125))              # top-row invader
ship = frame.crop((136, 553, 162, 583))

og = Image.new("RGB", (1200, 630), BG)
d = ImageDraw.Draw(og)
big = font(["seguibl.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"], 92)
it = font(["georgiai.ttf", "timesi.ttf", "DejaVuSerif-Italic.ttf"], 84)
mono = font(["consola.ttf", "cour.ttf", "DejaVuSansMono.ttf"], 22)
d.text((80, 150), "MEMORY HELPS.", font=big, fill=INK)
d.text((80, 270), "Until the world changes.", font=it, fill=MEM)
d.text((80, 520), "JEV × MITOSIS × TENKI  ·  A SPACE INVADERS EXPERIMENT", font=mono, fill=(146, 140, 128))
inv = invader.resize((invader.width * 3, invader.height * 3), Image.NEAREST)
for i in range(4):
    og.paste(inv, (780 + i * 100, 60))
sh = ship.resize((ship.width * 3, ship.height * 3), Image.NEAREST)
og.paste(sh, (1030, 470))
og.save(A / "og.png")
fav = invader.resize((64, 64), Image.NEAREST)
fav.save(A / "favicon.png")
print("ok")
