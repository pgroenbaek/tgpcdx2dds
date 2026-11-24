import argparse
import re
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image


# ---------------------------------------------------------------------
# Block sizes
# ---------------------------------------------------------------------

BLOCK_SIZE = 16
BC1_BLOCK_SIZE = 8


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
# Interpolated alpha decoding (DXT5-style)
# ---------------------------------------------------------------------

def decode_interp_alpha(block):
    a0 = block[0]
    a1 = block[1]

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

    selector_bits = int.from_bytes(block[2:8], "little")

    return [
        palette[(selector_bits >> (3 * i)) & 7]
        for i in range(16)
    ]


# ---------------------------------------------------------------------
# Explicit alpha decoding (DXT3-style)
# ---------------------------------------------------------------------

def decode_expl_alpha(block):
    if len(block) != 8:
        raise ValueError("Explicit alpha block must be 8 bytes.")

    bits = int.from_bytes(block, "little")

    return [
        ((bits >> (4 * i)) & 0xF) * 17
        for i in range(16)
    ]


# ---------------------------------------------------------------------
# XML helpers
# ---------------------------------------------------------------------

def local_name(tag):
    return tag.split("}")[-1]


def find_child(element, name):
    for child in element:
        if local_name(child.tag) == name:
            return child
    return None


def find_text(element, name):
    child = find_child(element, name)

    if child is None or child.text is None:
        raise ValueError(f"Missing XML element: {name}")

    return child.text.strip()


def parse_texture_xml(xml_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()

    supported_formats = (
        "HC_IMAGE_FORMAT_COMPRESSED",
        "HC_IMAGE_FORMAT_COMPRESSED_INTERP_ALPHA",
        "HC_IMAGE_FORMAT_COMPRESSED_EXPL_ALPHA",
    )

    mip_entries = []

    for element in root.iter():
        if local_name(element.tag) != "cHcImageDx":
            continue

        fmt_element = find_child(element, "Format")
        blob_element = find_child(element, "blob")

        if fmt_element is None or blob_element is None:
            continue

        fmt = (fmt_element.text or "").strip()

        if fmt not in supported_formats:
            continue

        width = int(find_text(element, "Width"))
        height = int(find_text(element, "Height"))
        swizzled = find_text(element, "IsSwizzled").lower()

        if swizzled not in ("0", "false"):
            raise ValueError(
                f"Swizzled texture not supported: {width}x{height}"
            )

        hex_data = re.sub(r"\s+", "", blob_element.text or "")

        if len(hex_data) % 2:
            raise ValueError("Odd number of hexadecimal characters.")

        data = bytes.fromhex(hex_data)

        block_size = (
            BC1_BLOCK_SIZE
            if fmt == "HC_IMAGE_FORMAT_COMPRESSED"
            else BLOCK_SIZE
        )

        expected_size = (
            ((width + 3) // 4) *
            ((height + 3) // 4) *
            block_size
        )

        if len(data) != expected_size:
            raise ValueError(
                f"Incorrect blob size for {width}x{height}: "
                f"expected {expected_size}, got {len(data)}"
            )

        mip_entries.append({
            "format": fmt,
            "width": width,
            "height": height,
            "data": data,
        })

    if not mip_entries:
        raise ValueError("No supported compressed texture mip found.")

    return mip_entries


# ---------------------------------------------------------------------
# Decode selected mip
# ---------------------------------------------------------------------

def decode_texture(mip, output_dir, texture_name):
    width = mip["width"]
    height = mip["height"]
    fmt = mip["format"]
    data = mip["data"]

    blocks_x = (width + 3) // 4

    if fmt == "HC_IMAGE_FORMAT_COMPRESSED":
        block_size = BC1_BLOCK_SIZE
        alpha_decoder = None
        alpha_suffix = None
    elif fmt == "HC_IMAGE_FORMAT_COMPRESSED_INTERP_ALPHA":
        block_size = BLOCK_SIZE
        alpha_decoder = decode_interp_alpha
        alpha_suffix = "_alpha_interp"
    elif fmt == "HC_IMAGE_FORMAT_COMPRESSED_EXPL_ALPHA":
        block_size = BLOCK_SIZE
        alpha_decoder = decode_expl_alpha
        alpha_suffix = "_alpha"
    else:
        raise ValueError(f"Unsupported format: {fmt}")

    blocks = [
        data[i:i + block_size]
        for i in range(0, len(data), block_size)
    ]

    color_image = Image.new("RGB", (width, height))
    color_pixels = color_image.load()

    alpha_image = None
    alpha_pixels = None

    if alpha_decoder is not None:
        alpha_image = Image.new("L", (width, height))
        alpha_pixels = alpha_image.load()

    print()
    print(f"Format: {fmt}")
    print(f"Dimensions: {width}x{height}")
    print(f"Blocks: {len(blocks)}")

    for block_index, block in enumerate(blocks):
        bx = block_index % blocks_x
        by = block_index // blocks_x

        if alpha_decoder is None:
            colors = decode_bc1(block)
            alphas = None
        else:
            alpha_data = block[:8]
            color_data = block[8:16]

            alphas = alpha_decoder(alpha_data)
            colors = decode_bc1(color_data)

        for i in range(16):
            x = bx * 4 + (i % 4)
            y = by * 4 + (i // 4)

            if x >= width or y >= height:
                continue

            color_pixels[x, y] = colors[i]

            if alpha_pixels is not None:
                alpha_pixels[x, y] = alphas[i]

        if block_index % 10000 == 0:
            print(f"Processed {block_index}/{len(blocks)}")

    output_dir.mkdir(parents=True, exist_ok=True)

    rgb_path = output_dir / f"{texture_name}.png"
    color_image.save(rgb_path)

    print()
    print("Finished.")
    print(f"  {rgb_path}")

    if alpha_image is not None:
        alpha_path = output_dir / f"{texture_name}{alpha_suffix}.png"
        alpha_image.save(alpha_path)
        print(f"  {alpha_path}")


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Decode RailWorks compressed textures."
    )

    parser.add_argument(
        "xml",
        type=Path,
        help="Path to the RailWorks texture XML file."
    )

    parser.add_argument(
        "--mip-width",
        type=int,
        default=None,
        help="Select a mip by width, e.g. 2048. Defaults to largest mip."
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output directory. Defaults to the XML file's directory."
    )

    args = parser.parse_args()

    xml_path = args.xml.resolve()

    if not xml_path.is_file():
        raise FileNotFoundError(xml_path)

    mips = parse_texture_xml(xml_path)

    print("Available mip levels:")
    for i, mip in enumerate(mips):
        print(
            f"  {i}: {mip['width']}x{mip['height']} "
            f"{mip['format']}"
        )

    if args.mip_width is not None:
        candidates = [
            mip for mip in mips
            if mip["width"] == args.mip_width
        ]

        if not candidates:
            raise ValueError(
                f"No mip with width {args.mip_width} found."
            )

        mip = candidates[0]
    else:
        mip = max(
            mips,
            key=lambda item: item["width"] * item["height"]
        )

    filename = xml_path.name
    suffix = ".TgPcDx.xml"

    if filename.lower().endswith(suffix.lower()):
        texture_name = filename[:-len(suffix)]
    else:
        texture_name = xml_path.stem

    output_dir = (
        args.output.resolve()
        if args.output is not None
        else xml_path.parent
    )

    decode_texture(mip, output_dir, texture_name)


if __name__ == "__main__":
    main()