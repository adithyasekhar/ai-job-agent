"""Draws the app icon (assets/icon.png + icon.ico)."""
import os
from PIL import Image, ImageDraw, ImageFont

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jobagent", "assets")
S = 512
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
# vertical indigo -> violet gradient in a rounded square
grad = Image.new("RGBA", (S, S))
gd = ImageDraw.Draw(grad)
for y in range(S):
    t = y / S
    gd.line([(0, y), (S, y)], fill=(int(79 + 45 * t), int(70 - 10 * t), int(229 + 10 * t), 255))
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle([16, 16, S - 16, S - 16], radius=112, fill=255)
img.paste(grad, (0, 0), mask)
d = ImageDraw.Draw(img)
# briefcase
d.rounded_rectangle([118, 190, 394, 380], radius=34, fill=(255, 255, 255, 255))
d.rounded_rectangle([200, 140, 312, 200], radius=22, outline=(255, 255, 255, 255), width=22)
d.rectangle([118, 262, 394, 274], fill=(99, 82, 236, 255))
# sparkle (AI) badge
cx, cy, r = 370, 150, 62
d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(250, 204, 21, 255))
pts = [(cx, cy - 38), (cx + 10, cy - 10), (cx + 38, cy), (cx + 10, cy + 10), (cx, cy + 38), (cx - 10, cy + 10), (cx - 38, cy), (cx - 10, cy - 10)]
d.polygon(pts, fill=(255, 255, 255, 255))
img.save(os.path.join(out, "icon.png"))
img.save(os.path.join(out, "icon.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("icon written")
