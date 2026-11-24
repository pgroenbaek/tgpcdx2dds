import struct
from pathlib import Path

from PIL import Image


# ---------------------------------------------------------------------
# Paste the contents of ONE <d:blob> here.
# Whitespace is ignored.
# ---------------------------------------------------------------------

HEX_DATA = """

"""


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
# BC helpers
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

        index = (
            bits >>
            (2 * i)
        ) & 3

        rgb = palette[index]

        pixels.append(
            (
                rgb[0],
                rgb[1],
                rgb[2],
                alpha[index]
            )
        )

    return pixels


def decode_bc2(block):
    alpha_bits = int.from_bytes(
        block[:8],
        "little"
    )

    color_pixels = decode_bc1(
        block[8:16]
    )

    pixels = []

    for i, rgba in enumerate(color_pixels):

        alpha = (
            (alpha_bits >> (4 * i))
            & 0xF
        ) * 17

        pixels.append(
            (
                rgba[0],
                rgba[1],
                rgba[2],
                alpha
            )
        )

    return pixels


# ---------------------------------------------------------------------
# BC3 alpha decoding
# ---------------------------------------------------------------------

def bc3_alpha_standard(block):

    a0 = block[0]
    a1 = block[1]

    alpha_bits = int.from_bytes(
        block[2:8],
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
        palette[
            (alpha_bits >> (i * 3)) & 7
        ]
        for i in range(16)
    ]


def bc3_alpha_reverse_bytes(block):

    alpha = block[:8][::-1]

    temp = alpha + block[8:16]

    return bc3_alpha_standard(
        temp
    )


def bc3_alpha_swap_endpoints(block):

    temp = bytearray(block)

    temp[0], temp[1] = (
        temp[1],
        temp[0]
    )

    return bc3_alpha_standard(
        bytes(temp)
    )


def bc3_alpha_inverted(block):

    values = bc3_alpha_standard(
        block
    )

    return [
        255 - value
        for value in values
    ]


def bc3_alpha_reverse_bits(block):

    alpha_bits = int.from_bytes(
        block[2:8],
        "little"
    )

    reversed_bits = 0

    for i in range(48):

        bit = (
            alpha_bits >> i
        ) & 1

        reversed_bits |= (
            bit << (47 - i)
        )

    temp = bytearray(block)

    temp[2:8] = (
        reversed_bits.to_bytes(
            6,
            "little"
        )
    )

    return bc3_alpha_standard(
        bytes(temp)
    )


def bc3_alpha_reverse_index_order(block):

    a0 = block[0]
    a1 = block[1]

    alpha_bits = int.from_bytes(
        block[2:8],
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

    values = []

    for i in range(16):

        source_pixel = 15 - i

        index = (
            alpha_bits >>
            (source_pixel * 3)
        ) & 7

        values.append(
            palette[index]
        )

    return values


def bc3_alpha_force_255(block):
    return [255] * 16


def bc3_alpha_force_0(block):
    return [0] * 16


def bc3_alpha_raw_a0(block):
    return [block[0]] * 16


def bc3_alpha_raw_a1(block):
    return [block[1]] * 16


ALPHA_DECODERS = {

    "standard":
        bc3_alpha_standard,

    "reverse_bytes":
        bc3_alpha_reverse_bytes,

    "swap_endpoints":
        bc3_alpha_swap_endpoints,

    "inverted":
        bc3_alpha_inverted,

    "reverse_bits":
        bc3_alpha_reverse_bits,

    "reverse_index_order":
        bc3_alpha_reverse_index_order,

    "force_255":
        bc3_alpha_force_255,

    "force_0":
        bc3_alpha_force_0,

    "raw_a0":
        bc3_alpha_raw_a0,

    "raw_a1":
        bc3_alpha_raw_a1,
}


# ---------------------------------------------------------------------
# BC3 decoder factory
#
# IMPORTANT:
# The RGB half (bytes 8-15) remains completely standard.
# Only the alpha decoder changes.
# ---------------------------------------------------------------------

def make_bc3_decoder(alpha_decoder):

    def decode(block):

        alpha_values = alpha_decoder(
            block
        )

        color_pixels = decode_bc1(
            block[8:16]
        )

        pixels = []

        for i, rgba in enumerate(
            color_pixels
        ):

            pixels.append(
                (
                    rgba[0],
                    rgba[1],
                    rgba[2],
                    alpha_values[i]
                )
            )

        return pixels

    return decode


# ---------------------------------------------------------------------
# Decoders
# ---------------------------------------------------------------------

DECODERS = {

    "BC1":
        decode_bc1,

    "BC2":
        decode_bc2,
}


for alpha_name, alpha_decoder in (
    ALPHA_DECODERS.items()
):

    DECODERS[
        f"BC3_{alpha_name}"
    ] = make_bc3_decoder(
        alpha_decoder
    )


# ---------------------------------------------------------------------
# 16-byte block permutations
# ---------------------------------------------------------------------

def perm_identity(b):
    return b


def perm_reverse(b):
    return b[::-1]


def perm_swap_halves(b):
    return (
        b[8:16] +
        b[0:8]
    )


def perm_reverse_halves(b):
    return (
        b[7::-1] +
        b[15:7:-1]
    )


def perm_reverse_first_half(b):
    return (
        b[0:8][::-1] +
        b[8:16]
    )


def perm_reverse_second_half(b):
    return (
        b[0:8] +
        b[8:16][::-1]
    )


def perm_swap_32(b):
    return (
        b[4:8] +
        b[0:4] +
        b[12:16] +
        b[8:12]
    )


def perm_reverse_32(b):
    return (
        b[3::-1] +
        b[7:3:-1] +
        b[11:7:-1] +
        b[15:11:-1]
    )


def perm_reverse_each_32(b):
    return (
        b[0:4][::-1] +
        b[4:8][::-1] +
        b[8:12][::-1] +
        b[12:16][::-1]
    )


def perm_swap_16(b):
    return (
        b[2:4] +
        b[0:2] +
        b[6:8] +
        b[4:6] +
        b[10:12] +
        b[8:10] +
        b[14:16] +
        b[12:14]
    )


def perm_reverse_each_16(b):

    result = bytearray()

    for i in range(
        0,
        16,
        2
    ):

        result.extend(
            b[i:i + 2][::-1]
        )

    return bytes(result)


PERMUTATIONS = {

    "normal":
        perm_identity,

    "reverse":
        perm_reverse,

    "swap_halves":
        perm_swap_halves,

    "reverse_halves":
        perm_reverse_halves,

    "reverse_first_half":
        perm_reverse_first_half,

    "reverse_second_half":
        perm_reverse_second_half,

    "swap_32":
        perm_swap_32,

    "reverse_32":
        perm_reverse_32,

    "reverse_each_32":
        perm_reverse_each_32,

    "swap_16":
        perm_swap_16,

    "reverse_each_16":
        perm_reverse_each_16,
}


# ---------------------------------------------------------------------
# Block ordering
# ---------------------------------------------------------------------

def order_normal(blocks):
    return blocks


def order_flip_x(blocks):

    result = [None] * len(blocks)

    for y in range(
        BLOCKS_Y
    ):

        for x in range(
            BLOCKS_X
        ):

            src = (
                y * BLOCKS_X +
                x
            )

            dst = (
                y * BLOCKS_X +
                (BLOCKS_X - 1 - x)
            )

            result[dst] = blocks[src]

    return result


def order_flip_y(blocks):

    result = [None] * len(blocks)

    for y in range(
        BLOCKS_Y
    ):

        for x in range(
            BLOCKS_X
        ):

            src = (
                y * BLOCKS_X +
                x
            )

            dst = (
                (BLOCKS_Y - 1 - y)
                * BLOCKS_X +
                x
            )

            result[dst] = blocks[src]

    return result


def order_flip_xy(blocks):

    result = [None] * len(blocks)

    for y in range(
        BLOCKS_Y
    ):

        for x in range(
            BLOCKS_X
        ):

            src = (
                y * BLOCKS_X +
                x
            )

            dst = (
                (BLOCKS_Y - 1 - y)
                * BLOCKS_X +
                (BLOCKS_X - 1 - x)
            )

            result[dst] = blocks[src]

    return result


BLOCK_ORDERS = {

    "normal":
        order_normal,

    "flip_x":
        order_flip_x,

    "flip_y":
        order_flip_y,

    "flip_xy":
        order_flip_xy,
}


# ---------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------

def render(
    blocks,
    decoder
):

    image = Image.new(
        "RGBA",
        (
            WIDTH,
            HEIGHT
        )
    )

    for block_index, block in enumerate(
        blocks
    ):

        pixels = decoder(
            block
        )

        block_x = (
            block_index %
            BLOCKS_X
        )

        block_y = (
            block_index //
            BLOCKS_X
        )

        for pixel_index, pixel in enumerate(
            pixels
        ):

            px = pixel_index % 4
            py = pixel_index // 4

            x = (
                block_x * 4 +
                px
            )

            y = (
                block_y * 4 +
                py
            )

            image.putpixel(
                (
                    x,
                    y
                ),
                pixel
            )

    return image


# ---------------------------------------------------------------------
# Parse hex
# ---------------------------------------------------------------------

hex_string = "".join(
    HEX_DATA.split()
)

if len(hex_string) % 2:

    raise ValueError(
        "Odd number of hexadecimal characters."
    )


data = bytes.fromhex(
    hex_string
)


print()
print("Texture:")
print(
    f"  {WIDTH} x {HEIGHT}"
)

print(
    f"  Bytes: {len(data)}"
)

print(
    f"  Expected: "
    f"{WIDTH * HEIGHT}"
)

print(
    f"  Blocks: "
    f"{len(data) // BLOCK_SIZE}"
)

print(
    f"  Expected blocks: "
    f"{BLOCKS_X * BLOCKS_Y}"
)

print()


if len(data) != WIDTH * HEIGHT:

    print(
        "WARNING: byte count does not equal "
        "WIDTH * HEIGHT."
    )


if len(data) % BLOCK_SIZE:

    raise ValueError(
        "Texture data is not divisible "
        "by 16 bytes."
    )


blocks = [

    data[i:i + BLOCK_SIZE]

    for i in range(
        0,
        len(data),
        BLOCK_SIZE
    )
]


# ---------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------

out = Path(
    "decode_test"
)

out.mkdir(
    exist_ok=True
)


# ---------------------------------------------------------------------
# Generate every combination
# ---------------------------------------------------------------------

results = []

total = (
    len(PERMUTATIONS)
    * len(BLOCK_ORDERS)
    * len(DECODERS)
)

current = 0


print(
    f"Generating {total} tests..."
)

print()


for perm_name, perm_func in (
    PERMUTATIONS.items()
):

    transformed = [

        perm_func(block)

        for block in blocks
    ]

    for order_name, order_func in (
        BLOCK_ORDERS.items()
    ):

        ordered = order_func(
            transformed
        )

        for decoder_name, decoder in (
            DECODERS.items()
        ):

            current += 1

            name = (
                f"{decoder_name}_"
                f"{perm_name}_"
                f"{order_name}"
            )

            print(
                f"[{current:03d}/{total}] "
                f"{name}"
            )

            try:

                image = render(
                    ordered,
                    decoder
                )

                filename = (
                    out /
                    f"{name}.png"
                )

                image.save(
                    filename
                )

                results.append(
                    (
                        name,
                        image.copy()
                    )
                )

            except Exception as e:

                print(
                    f"    FAILED: {e}"
                )


# ---------------------------------------------------------------------
# Contact sheet
# ---------------------------------------------------------------------

THUMB_SIZE = 160
LABEL_HEIGHT = 28
COLUMNS = 5

rows = (
    len(results) +
    COLUMNS - 1
) // COLUMNS


sheet = Image.new(
    "RGB",
    (
        COLUMNS * THUMB_SIZE,
        rows * (
            THUMB_SIZE +
            LABEL_HEIGHT
        )
    ),
    "white"
)


draw = ImageDraw.Draw(
    sheet
)


for i, (name, image) in enumerate(
    results
):

    x = (
        i % COLUMNS
    ) * THUMB_SIZE

    y = (
        i // COLUMNS
    ) * (
        THUMB_SIZE +
        LABEL_HEIGHT
    )

    thumbnail = image.convert(
        "RGB"
    )

    thumbnail.thumbnail(
        (
            THUMB_SIZE,
            THUMB_SIZE
        )
    )

    sheet.paste(
        thumbnail,
        (
            x,
            y
        )
    )

    draw.text(
        (
            x + 2,
            y + THUMB_SIZE + 3
        ),
        name,
        fill="black"
    )


contact_sheet = (
    out /
    "CONTACT_SHEET.png"
)


sheet.save(
    contact_sheet
)


print()
print(
    "======================================"
)

print(
    "Finished."
)

print()

print(
    f"Individual images: {out}"
)

print(
    f"Contact sheet:     {contact_sheet}"
)

print(
    "======================================"
)