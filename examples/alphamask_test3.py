
import struct
from pathlib import Path

from PIL import Image


# ---------------------------------------------------------------------
# Paste the contents of ONE <d:blob> here.
# Whitespace is ignored.
# ---------------------------------------------------------------------

HEX_DATA = """

"""

import struct
from pathlib import Path
from PIL import Image


# ---------------------------------------------------------------------
# Texture dimensions
# ---------------------------------------------------------------------

WIDTH = 2048
HEIGHT = 2048

BLOCK_SIZE = 16
BLOCK_WIDTH = 4
BLOCK_HEIGHT = 4

BLOCKS_X = WIDTH // 4
BLOCKS_Y = HEIGHT // 4


# ---------------------------------------------------------------------
# BC1 colour decoding
# ---------------------------------------------------------------------

def rgb565_to_rgb(c):
    r = ((c >> 11) & 0x1F) * 255 // 31
    g = ((c >> 5) & 0x3F) * 255 // 63
    b = (c & 0x1F) * 255 // 31
    return r, g, b


def decode_bc1(block):
    c0, c1, bits = struct.unpack("<HHI", block)

    p0 = rgb565_to_rgb(c0)
    p1 = rgb565_to_rgb(c1)

    if c0 > c1:
        p2 = tuple((2 * p0[i] + p1[i]) // 3 for i in range(3))
        p3 = tuple((p0[i] + 2 * p1[i]) // 3 for i in range(3))
        palette = [p0, p1, p2, p3]
    else:
        p2 = tuple((p0[i] + p1[i]) // 2 for i in range(3))
        palette = [p0, p1, p2, (0, 0, 0)]

    return [
        palette[(bits >> (2 * i)) & 3]
        for i in range(16)
    ]


# ---------------------------------------------------------------------
# Interpolated alpha decoding
# ---------------------------------------------------------------------

def decode_interp_alpha(block):

    a0 = block[0]
    a1 = block[1]

    # Build the eight-entry interpolation palette.
    if a0 > a1:
        palette = [
            a0,
            a1,
            (6 * a0 + a1) // 7,
            (5 * a0 + 2 * a1) // 7,
            (4 * a0 + 3 * a1) // 7,
            (3 * a0 + 4 * a1) // 7,
            (2 * a0 + 5 * a1) // 7,
            (a0 + 6 * a1) // 7,
        ]

    else:
        palette = [
            a0,
            a1,
            (4 * a0 + a1) // 5,
            (3 * a0 + 2 * a1) // 5,
            (2 * a0 + 3 * a1) // 5,
            (a0 + 4 * a1) // 5,
            0,
            255,
        ]

    # Six bytes contain sixteen packed 3-bit indices.
    selector_bits = int.from_bytes(block[2:8], "little")

    return [
        palette[(selector_bits >> (3 * i)) & 7]
        for i in range(16)
    ]


# ---------------------------------------------------------------------
# Parse existing HEX_DATA
# ---------------------------------------------------------------------

hex_string = "".join(HEX_DATA.split())

if len(hex_string) % 2:
    raise ValueError("Odd number of hexadecimal characters.")

data = bytes.fromhex(hex_string)

if len(data) % BLOCK_SIZE:
    raise ValueError("Data is not divisible by 16 bytes.")

blocks = [
    data[i:i + BLOCK_SIZE]
    for i in range(0, len(data), BLOCK_SIZE)
]

expected_blocks = BLOCKS_X * BLOCKS_Y

print("Texture information")
print("-------------------")
print(f"Bytes: {len(data)}")
print(f"Blocks: {len(blocks)}")
print(f"Expected blocks: {expected_blocks}")

if len(blocks) != expected_blocks:
    raise ValueError("Block count does not match dimensions.")


# ---------------------------------------------------------------------
# Create output images
# ---------------------------------------------------------------------

out = Path("interp_alpha_decoded")
out.mkdir(exist_ok=True)

color_image = Image.new("RGB", (WIDTH, HEIGHT))
alpha_image = Image.new("L", (WIDTH, HEIGHT))
rgba_image = Image.new("RGBA", (WIDTH, HEIGHT))

color_pixels = color_image.load()
alpha_pixels = alpha_image.load()
rgba_pixels = rgba_image.load()


# ---------------------------------------------------------------------
# Decode all blocks
# ---------------------------------------------------------------------

for block_index, block in enumerate(blocks):

    bx = block_index % BLOCKS_X
    by = block_index // BLOCKS_X

    alpha_data = block[:8]
    color_data = block[8:16]

    alphas = decode_interp_alpha(alpha_data)
    colors = decode_bc1(color_data)

    for i in range(16):

        x = bx * 4 + (i % 4)
        y = by * 4 + (i // 4)

        alpha = alphas[i]
        color = colors[i]

        color_pixels[x, y] = color
        alpha_pixels[x, y] = alpha

        rgba_pixels[x, y] = (
            color[0],
            color[1],
            color[2],
            alpha
        )

    if block_index % 10000 == 0:
        print(f"Processed {block_index}/{len(blocks)}")


# ---------------------------------------------------------------------
# Save output
# ---------------------------------------------------------------------

color_image.save(out / "color_only.png")
alpha_image.save(out / "alpha_decoded.png")
rgba_image.save(out / "rgba_decoded.png")

print()
print("Finished.")
print(f"Output: {out.resolve()}")
print("  color_only.png")
print("  alpha_decoded.png")
print("  rgba_decoded.png")