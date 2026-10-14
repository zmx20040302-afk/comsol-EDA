from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps


root = Path(sys.argv[1])
files = sorted(root.glob("page-*.png"))
for offset in range(0, len(files), 6):
    subset = files[offset : offset + 6]
    sheet = Image.new("RGB", (1500, 1100 * math.ceil(len(subset) / 3)), "white")
    for index, path in enumerate(subset):
        image = Image.open(path).convert("RGB")
        thumb = ImageOps.contain(image, (480, 1060))
        x = (index % 3) * 500 + 10
        y = (index // 3) * 1100 + 30
        sheet.paste(thumb, (x, y))
        ImageDraw.Draw(sheet).text((x, 5 + (index // 3) * 1100), path.stem, fill="black")
    sheet.save(root / f"contact-{offset // 6 + 1}.png")
print(f"pages={len(files)} contacts={math.ceil(len(files) / 6)}")
