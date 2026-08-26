"""Generate myglimmer's Open Graph / Twitter share card.

Palette and type are pulled straight from index.html so the card reads as the
same object as the app: cream ground, Instrument Serif headline, amber mark.
Rendered at 2x and downsampled so the vector star edges stay clean.
"""
import math
import os
from PIL import Image, ImageDraw, ImageFont

SP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "og-image.png")

S = 2                      # supersample factor
W, H = 1200 * S, 630 * S
M = 88 * S                 # safe margin: crops differ per platform, keep clear

CREAM = (250, 247, 242)
INK = (28, 26, 23)
INK_LIGHT = (107, 101, 96)
AMBER = (219, 155, 29)
RULE = (28, 26, 23, 26)

serif = lambda px: ImageFont.truetype(f"{SP}/InstrumentSerif.ttf", px * S)
sans = lambda px: ImageFont.truetype(f"{SP}/AlbertSans.ttf", px * S)


def star4(cx, cy, R, inner=0.22, rot=0.0):
    """Four-pointed star matching the ✦ in the wordmark."""
    pts = []
    for i in range(8):
        a = math.radians(rot + i * 45)
        rad = R if i % 2 == 0 else R * inner
        pts.append((cx + rad * math.sin(a), cy - rad * math.cos(a)))
    return pts


def tracked(d, xy, text, font, fill, track=0):
    """PIL has no letter-spacing; step glyph by glyph."""
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=font, fill=fill)
        x += d.textlength(ch, font=font) + track
    return x


img = Image.new("RGB", (W, H), CREAM)
d = ImageDraw.Draw(img)

# Ambient star, low-alpha so it reads as watermark rather than clip art.
glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
ImageDraw.Draw(glow).polygon(
    star4(W - 246 * S, H // 2, 196 * S, inner=0.19), fill=AMBER + (30,)
)
img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
d = ImageDraw.Draw(img)

# ── Wordmark: My ✦ Glimmer ───────────────────────────────────────────────────
wm = serif(36)
x, y = M, M - 6 * S
d.text((x, y), "My", font=wm, fill=INK)
x += d.textlength("My", font=wm) + 7 * S
asc = wm.getbbox("M")[3] - wm.getbbox("M")[1]
sr = 11 * S
d.polygon(star4(x + sr, y + asc * 0.62, sr, inner=0.33), fill=AMBER)
x += sr * 2 + 7 * S
d.text((x, y), "Glimmer", font=wm, fill=INK)

# ── Headline ─────────────────────────────────────────────────────────────────
hl = serif(88)
lines = ["One beautiful thing.", "Every day."]
lead = 97 * S
top = 214 * S
for i, ln in enumerate(lines):
    d.text((M, top + i * lead), ln, font=hl, fill=INK)

# ── Rule + subline ───────────────────────────────────────────────────────────
ry = top + len(lines) * lead + 42 * S
d.line([(M, ry), (M + 132 * S, ry)], fill=AMBER, width=2 * S)

sub = sans(25)
d.text((M, ry + 30 * S), "Anonymous. Once a day. 100% human.", font=sub, fill=INK_LIGHT)

# ── Footer URL ───────────────────────────────────────────────────────────────
url = sans(19)
tracked(d, (M, H - M - 14 * S), "MYGLIMMER.DAY", url, INK_LIGHT, track=2.2 * S)

img = img.resize((1200, 630), Image.LANCZOS)
img.save(OUT, "PNG", optimize=True)
print("wrote", OUT, img.size)
