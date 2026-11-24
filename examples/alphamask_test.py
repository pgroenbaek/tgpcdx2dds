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
from PIL import Image, ImageDraw


# ---------------------------------------------------------------------
# Texture dimensions
# ---------------------------------------------------------------------

WIDTH = 2048
HEIGHT = 2048

BLOCK_SIZE = 16
BLOCK_WIDTH = 4
BLOCK_HEIGHT = 4

BLOCKS_X = WIDTH // BLOCK_WIDTH
BLOCKS_Y = HEIGHT // BLOCK_HEIGHT


# ---------------------------------------------------------------------
# BC1 RGB decoding (standard BC3 color half)
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

        p2 = tuple(
            (2 * p0[i] + p1[i]) // 3
            for i in range(3)
        )

        p3 = tuple(
            (p0[i] + 2 * p1[i]) // 3
            for i in range(3)
        )

        palette = [p0, p1, p2, p3]

        alpha = [255, 255, 255, 255]

    else:

        p2 = tuple(
            (p0[i] + p1[i]) // 2
            for i in range(3)
        )

        palette = [
            p0,
            p1,
            p2,
            (0, 0, 0)
        ]

        alpha = [
            255,
            255,
            255,
            0
        ]

    pixels = []

    for i in range(16):

        index = (bits >> (2 * i)) & 3

        rgb = palette[index]

        pixels.append((
            rgb[0],
            rgb[1],
            rgb[2],
            alpha[index]
        ))

    return pixels


# ---------------------------------------------------------------------
# BC3 alpha decoding
# ---------------------------------------------------------------------

def decode_bc3_alpha(data):

    a0 = data[0]
    a1 = data[1]

    alpha_bits = int.from_bytes(
        data[2:8],
        "little"
    )

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

    return [
        palette[(alpha_bits >> (i * 3)) & 7]
        for i in range(16)
    ]


# ---------------------------------------------------------------------
# Raw channel unpackers
# ---------------------------------------------------------------------

def unpack_8bit(data):

    return [
        data[i]
        for i in range(min(16, len(data)))
    ]


def unpack_4bit(data):

    bits = int.from_bytes(data, "little")

    return [
        ((bits >> (i * 4)) & 0xF) * 17
        for i in range(16)
    ]


def unpack_2bit(data):

    bits = int.from_bytes(data, "little")

    return [
        ((bits >> (i * 2)) & 3) * 85
        for i in range(16)
    ]


def unpack_1bit(data):

    bits = int.from_bytes(data, "little")

    return [
        255 if ((bits >> i) & 1) else 0
        for i in range(16)
    ]


def expand_to_16(values, default=255):

    if len(values) == 16:
        return values

    if len(values) == 8:
        return [
            value
            for v in values
            for value in (v, v)
        ]

    if len(values) == 4:
        return [
            value
            for v in values
            for value in (v, v, v, v)
        ]

    return (values + [default] * 16)[:16]


# ---------------------------------------------------------------------
# First 8 bytes: separate alpha/mask interpretations
# ---------------------------------------------------------------------

def layout_split_32(block, alpha_first=True):

    data = block[:8]

    first = data[:4]
    second = data[4:8]

    if alpha_first:
        alpha_data = first
        mask_data = second
    else:
        mask_data = first
        alpha_data = second

    return (
        expand_to_16(unpack_8bit(alpha_data)),
        expand_to_16(unpack_8bit(mask_data))
    )


def layout_split_16(block, alpha_first=True):

    data = block[:8]

    first = data[:4]
    second = data[4:8]

    if alpha_first:
        alpha_data = first
        mask_data = second
    else:
        mask_data = first
        alpha_data = second

    return (
        unpack_4bit(alpha_data),
        unpack_4bit(mask_data)
    )


def layout_interleaved_bytes(block, alpha_first=True):

    data = block[:8]

    first = data[0::2]
    second = data[1::2]

    if alpha_first:
        alpha_data = first
        mask_data = second
    else:
        mask_data = first
        alpha_data = second

    return (
        expand_to_16(unpack_8bit(alpha_data)),
        expand_to_16(unpack_8bit(mask_data))
    )


def layout_interleaved_nibbles(block, alpha_first=True):

    alpha = []
    mask = []

    for byte in block[:8]:

        low = byte & 0x0F
        high = (byte >> 4) & 0x0F

        alpha.append(low * 17)
        mask.append(high * 17)

    if not alpha_first:
        alpha, mask = mask, alpha

    return (
        expand_to_16(alpha),
        expand_to_16(mask)
    )


def layout_interleaved_bits(block, alpha_first=True):

    bits = int.from_bytes(
        block[:8],
        "little"
    )

    alpha = []
    mask = []

    for i in range(32):

        alpha_value = (bits >> (i * 2)) & 1
        mask_value = (bits >> (i * 2 + 1)) & 1

        alpha.append(alpha_value * 255)
        mask.append(mask_value * 255)

    if not alpha_first:
        alpha, mask = mask, alpha

    return (
        expand_to_16(alpha),
        expand_to_16(mask)
    )


def layout_separate_4bit_alpha_1bit_mask(block):

    bits = int.from_bytes(
        block[:8],
        "little"
    )

    alpha = []
    mask = []

    # 16 pixels:
    # 4 bits alpha + 1 bit mask = 80 bits.
    # This layout is included as a diagnostic candidate,
    # using the available 64 bits for the first 12 pixels.
    for i in range(16):

        alpha_value = (bits >> (i * 4)) & 0xF

        mask_value = (bits >> (i + 48)) & 1

        alpha.append(alpha_value * 17)
        mask.append(mask_value * 255)

    return alpha, mask


def layout_separate_1bit_mask_4bit_alpha(block):

    bits = int.from_bytes(
        block[:8],
        "little"
    )

    alpha = []
    mask = []

    for i in range(16):

        mask_value = (bits >> i) & 1
        alpha_value = (bits >> (16 + i * 3)) & 0x7

        alpha.append(alpha_value * 255 // 7)
        mask.append(mask_value * 255)

    return alpha, mask


# ---------------------------------------------------------------------
# Layout registry
# ---------------------------------------------------------------------

LAYOUTS = {

    "split32_alpha_mask":
        lambda b: layout_split_32(b, True),

    "split32_mask_alpha":
        lambda b: layout_split_32(b, False),

    "split16_alpha_mask":
        lambda b: layout_split_16(b, True),

    "split16_mask_alpha":
        lambda b: layout_split_16(b, False),

    "interleaved_bytes_alpha_mask":
        lambda b: layout_interleaved_bytes(b, True),

    "interleaved_bytes_mask_alpha":
        lambda b: layout_interleaved_bytes(b, False),

    "interleaved_nibbles_alpha_mask":
        lambda b: layout_interleaved_nibbles(b, True),

    "interleaved_nibbles_mask_alpha":
        lambda b: layout_interleaved_nibbles(b, False),

    "interleaved_bits_alpha_mask":
        lambda b: layout_interleaved_bits(b, True),

    "interleaved_bits_mask_alpha":
        lambda b: layout_interleaved_bits(b, False),

    "alpha4_mask1":
        layout_separate_4bit_alpha_1bit_mask,

    "mask1_alpha3":
        layout_separate_1bit_mask_4bit_alpha,

}


# ---------------------------------------------------------------------
# BC3 interpretations of first 8 bytes
# ---------------------------------------------------------------------

def layout_bc3_alpha_only(block):

    alpha = decode_bc3_alpha(block[:8])

    return alpha, [255] * 16


def layout_bc3_alpha_as_mask(block):

    mask = decode_bc3_alpha(block[:8])

    return [255] * 16, mask


LAYOUTS["bc3_alpha_only"] = layout_bc3_alpha_only
LAYOUTS["bc3_alpha_as_mask"] = layout_bc3_alpha_as_mask


# ---------------------------------------------------------------------
# Mask application modes
# ---------------------------------------------------------------------

MASK_MODES = {

    "multiply":
        lambda a, m: a * m // 255,

    "alpha_only":
        lambda a, m: a,

    "mask_only":
        lambda a, m: m,

    "invert_mask":
        lambda a, m: a * (255 - m) // 255,

    "max":
        lambda a, m: max(a, m),

    "min":
        lambda a, m: min(a, m),

}


# ---------------------------------------------------------------------
# Decoder factory
# ---------------------------------------------------------------------

def make_decoder(layout_func, mask_func):

    def decode(block):

        alpha, mask = layout_func(block)

        colors = decode_bc1(
            block[8:16]
        )

        pixels = []

        for i, rgba in enumerate(colors):

            final_alpha = mask_func(
                alpha[i],
                mask[i]
            )

            pixels.append((
                rgba[0],
                rgba[1],
                rgba[2],
                final_alpha
            ))

        return pixels

    return decode


# ---------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------

def render(blocks, decoder):

    image = Image.new(
        "RGBA",
        (WIDTH, HEIGHT)
    )

    for block_index, block in enumerate(blocks):

        pixels = decoder(block)

        block_x = block_index % BLOCKS_X
        block_y = block_index // BLOCKS_X

        for pixel_index, pixel in enumerate(pixels):

            px = pixel_index % 4
            py = pixel_index // 4

            x = block_x * 4 + px
            y = block_y * 4 + py

            image.putpixel(
                (x, y),
                pixel
            )

    return image


# ---------------------------------------------------------------------
# Parse hexadecimal texture data
# ---------------------------------------------------------------------

hex_string = "".join(
    HEX_DATA.split()
)

if len(hex_string) % 2:
    raise ValueError("Odd number of hexadecimal characters.")

data = bytes.fromhex(hex_string)

print()
print("Texture:")
print(f"  Dimensions: {WIDTH} x {HEIGHT}")
print(f"  Bytes: {len(data)}")
print(f"  Expected: {WIDTH * HEIGHT}")
print(f"  Blocks: {len(data) // BLOCK_SIZE}")
print(f"  Expected blocks: {BLOCKS_X * BLOCKS_Y}")
print()

if len(data) != WIDTH * HEIGHT:
    print("WARNING: byte count differs from expected size.")

if len(data) % BLOCK_SIZE:
    raise ValueError("Texture data is not divisible by 16 bytes.")

blocks = [
    data[i:i + BLOCK_SIZE]
    for i in range(0, len(data), BLOCK_SIZE)
]


# ---------------------------------------------------------------------
# Output directory
# ---------------------------------------------------------------------

out = Path("alphamask_test")
out.mkdir(exist_ok=True)


# ---------------------------------------------------------------------
# Generate combinations
# ---------------------------------------------------------------------

results = []

total = len(LAYOUTS) * len(MASK_MODES)
current = 0

print(f"Generating {total} tests...")
print()

for layout_name, layout_func in LAYOUTS.items():

    for mask_name, mask_func in MASK_MODES.items():

        current += 1

        name = f"{layout_name}_{mask_name}"

        print(
            f"[{current:03d}/{total}] {name}"
        )

        try:

            decoder = make_decoder(
                layout_func,
                mask_func
            )

            image = render(
                blocks,
                decoder
            )

            image.save(
                out / f"{name}.png"
            )

            results.append(
                (name, image.copy())
            )

        except Exception as e:

            print(f"    FAILED: {e}")


# ---------------------------------------------------------------------
# Contact sheet
# ---------------------------------------------------------------------

THUMB_SIZE = 180
LABEL_HEIGHT = 32
COLUMNS = 5

rows = (
    len(results) + COLUMNS - 1
) // COLUMNS

sheet = Image.new(
    "RGB",
    (
        COLUMNS * THUMB_SIZE,
        rows * (THUMB_SIZE + LABEL_HEIGHT)
    ),
    "white"
)

draw = ImageDraw.Draw(sheet)

for i, (name, image) in enumerate(results):

    x = (i % COLUMNS) * THUMB_SIZE

    y = (i // COLUMNS) * (
        THUMB_SIZE + LABEL_HEIGHT
    )

    thumbnail = image.convert("RGB")

    thumbnail.thumbnail(
        (THUMB_SIZE, THUMB_SIZE)
    )

    sheet.paste(
        thumbnail,
        (x, y)
    )

    draw.text(
        (x + 2, y + THUMB_SIZE + 4),
        name,
        fill="black"
    )


contact_sheet = out / "CONTACT_SHEET.png"

sheet.save(contact_sheet)


# ---------------------------------------------------------------------
# Finished
# ---------------------------------------------------------------------

print()
print("======================================")
print("Finished.")
print()
print(f"Individual images: {out}")
print(f"Contact sheet:     {contact_sheet}")
print(f"Successful tests:  {len(results)} / {total}")
print("======================================")
