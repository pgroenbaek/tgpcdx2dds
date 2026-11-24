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
# BC1 color decoding
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

    pixels = []

    for i in range(16):
        index = (bits >> (2 * i)) & 3
        pixels.append(palette[index])

    return pixels


# ---------------------------------------------------------------------
# Render a 4x4 block of grayscale values
# ---------------------------------------------------------------------

def write_block(image, block_index, values):

    bx = block_index % BLOCKS_X
    by = block_index // BLOCKS_X

    for i, value in enumerate(values):

        x = bx * 4 + (i % 4)
        y = by * 4 + (i // 4)

        image.putpixel((x, y), value)


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

print("Texture information")
print("-------------------")
print(f"Bytes: {len(data)}")
print(f"Blocks: {len(blocks)}")
print(f"Expected blocks: {BLOCKS_X * BLOCKS_Y}")

if len(blocks) != BLOCKS_X * BLOCKS_Y:
    raise ValueError(
        "Block count does not match WIDTH and HEIGHT. "
        "Check the texture dimensions."
    )


# ---------------------------------------------------------------------
# Create output images
# ---------------------------------------------------------------------

out = Path("interp_alpha_diagnostics")
out.mkdir(exist_ok=True)

color_image = Image.new("RGB", (WIDTH, HEIGHT))

nibble_image = Image.new("L", (WIDTH, HEIGHT))

byte_images = [
    Image.new("L", (WIDTH, HEIGHT))
    for _ in range(8)
]


# ---------------------------------------------------------------------
# Process blocks
# ---------------------------------------------------------------------

for block_index, block in enumerate(blocks):

    alpha_data = block[:8]
    color_data = block[8:16]

    # Decode color half
    colors = decode_bc1(color_data)

    bx = block_index % BLOCKS_X
    by = block_index // BLOCKS_X

    for i, color in enumerate(colors):

        x = bx * 4 + (i % 4)
        y = by * 4 + (i // 4)

        color_image.putpixel((x, y), color)

    # Display all 64 bits as sixteen 4-bit values.
    packed = int.from_bytes(alpha_data, "little")

    nibbles = [
        ((packed >> (i * 4)) & 0xF) * 17
        for i in range(16)
    ]

    write_block(
        nibble_image,
        block_index,
        nibbles
    )

    # Display each original byte independently.
    for byte_index in range(8):

        value = alpha_data[byte_index]

        write_block(
            byte_images[byte_index],
            block_index,
            [value] * 16
        )

    if block_index % 10000 == 0:
        print(f"Processed {block_index}/{len(blocks)} blocks")


# ---------------------------------------------------------------------
# Save results
# ---------------------------------------------------------------------

color_image.save(out / "color_only.png")

nibble_image.save(out / "raw_nibbles.png")

for i, image in enumerate(byte_images):
    image.save(out / f"raw_byte_{i}.png")


print()
print("Finished.")
print(f"Output directory: {out.resolve()}")
print("Generated:")
print("  color_only.png")
print("  raw_nibbles.png")

for i in range(8):
    print(f"  raw_byte_{i}.png")

from collections import Counter

endpoint_pairs = Counter()
selector_values = Counter()
block_patterns = Counter()

for block in blocks:

    alpha_data = block[:8]

    a0 = alpha_data[0]
    a1 = alpha_data[1]

    packed = int.from_bytes(alpha_data[2:8], "little")

    endpoint_pairs[(a0, a1)] += 1

    selectors = [
        (packed >> (3 * i)) & 7
        for i in range(16)
    ]

    selector_values.update(selectors)

    block_patterns[
        (a0, a1, tuple(selectors))
    ] += 1


print("\nMOST COMMON ENDPOINT PAIRS")

for pair, count in endpoint_pairs.most_common(30):
    print(f"{pair[0]:3d}, {pair[1]:3d}: {count}")


print("\nSELECTOR DISTRIBUTION")

for value, count in sorted(selector_values.items()):
    print(f"{value}: {count}")


print("\nMOST COMMON BLOCK PATTERNS")

for pattern, count in block_patterns.most_common(20):
    a0, a1, selectors = pattern

    print(
        f"A0={a0:02X} A1={a1:02X} "
        f"selectors={selectors} count={count}"
    )