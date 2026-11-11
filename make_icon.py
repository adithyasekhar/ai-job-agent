"""Draws the CareerPilot AI icon (assets/icon.png + icon.ico): a yellow paper plane over a white swoosh on slate."""
import os

from PIL import Image, ImageDraw

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jobagent", "assets")
S = 512
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle([16, 16, S - 16, S - 16], radius=112, fill=(31, 41, 55, 255))  # #1F2937 slate

# swoosh: one smooth white curve under the plane (quadratic Bezier, tapering)
p0, p1, p2 = (78, 300), (150, 470), (372, 372)
pts = [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
        (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]) for t in [i / 60 for i in range(61)]]
for i in range(60):
    w = int(18 + 26 * (i / 60))  # thin at the start, thick toward the plane
    d.line([pts[i], pts[i + 1]], fill=(255, 255, 255, 255), width=w)
    d.ellipse([pts[i + 1][0] - w / 2, pts[i + 1][1] - w / 2, pts[i + 1][0] + w / 2, pts[i + 1][1] + w / 2], fill=(255, 255, 255, 255))

# paper plane (yellow #FFC700 with a darker fold)
plane = [(440, 80), (150, 250), (240, 285), (270, 390), (315, 305), (395, 345)]
d.polygon(plane, fill=(255, 199, 0, 255))
d.polygon([(240, 285), (440, 80), (270, 390)], fill=(224, 168, 0, 255))
d.polygon([(240, 285), (440, 80), (315, 305)], fill=(255, 214, 51, 255))

img.save(os.path.join(out, "icon.png"))
img.save(os.path.join(out, "icon.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("icon written")
