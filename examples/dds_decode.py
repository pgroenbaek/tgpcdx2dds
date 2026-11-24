import argparse
import re
import struct
import xml.etree.ElementTree as ET
from pathlib import Path


# ---------------------------------------------------------------------
# DDS format definitions
# ---------------------------------------------------------------------

FORMATS = {
    "HC_IMAGE_FORMAT_COMPRESSED": {
        "block_size": 8,
        "dds_type": "DXT1",
        "color_offset": 0,
    },
    "HC_IMAGE_FORMAT_COMPRESSED_INTERP_ALPHA": {
        "block_size": 16,
        "dds_type": "DXT1",
        "color_offset": 8,
    },
    "HC_IMAGE_FORMAT_COMPRESSED_EXPL_ALPHA": {
        "block_size": 16,
        "dds_type": "DXT3",
        "color_offset": 0,
    },
}

# DDS header flags
DDSD_CAPS = 0x1
DDSD_HEIGHT = 0x2
DDSD_WIDTH = 0x4
DDSD_PIXELFORMAT = 0x1000
DDSD_LINEARSIZE = 0x80000
DDSD_MIPMAPCOUNT = 0x20000

# DDS pixel format flags
DDPF_FOURCC = 0x4

# DDS caps
DDSCAPS_COMPLEX = 0x8
DDSCAPS_TEXTURE = 0x1000
DDSCAPS_MIPMAP = 0x400000


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


# ---------------------------------------------------------------------
# Parse texture XML
# ---------------------------------------------------------------------

def parse_texture_xml(xml_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()

    mip_entries = []

    for element in root.iter():
        if local_name(element.tag) != "cHcImageDx":
            continue

        fmt_element = find_child(element, "Format")
        blob_element = find_child(element, "blob")

        if fmt_element is None or blob_element is None:
            continue

        fmt = (fmt_element.text or "").strip()

        if fmt not in FORMATS:
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
            raise ValueError(
                f"Odd number of hexadecimal characters in {width}x{height} mip."
            )

        data = bytes.fromhex(hex_data)

        block_size = FORMATS[fmt]["block_size"]

        blocks_x = (width + 3) // 4
        blocks_y = (height + 3) // 4

        expected_size = blocks_x * blocks_y * block_size

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

    # Largest mip first.
    mip_entries.sort(
        key=lambda mip: mip["width"] * mip["height"],
        reverse=True
    )

    return mip_entries


# ---------------------------------------------------------------------
# Build DDS header
# ---------------------------------------------------------------------

def make_dds_header(width, height, fourcc, block_size, mip_count):
    blocks_x = (width + 3) // 4
    blocks_y = (height + 3) // 4

    linear_size = blocks_x * blocks_y * block_size

    flags = (
        DDSD_CAPS
        | DDSD_HEIGHT
        | DDSD_WIDTH
        | DDSD_PIXELFORMAT
        | DDSD_LINEARSIZE
    )

    caps = DDSCAPS_TEXTURE

    if mip_count > 1:
        flags |= DDSD_MIPMAPCOUNT
        caps |= DDSCAPS_COMPLEX | DDSCAPS_MIPMAP

    # DDS_PIXELFORMAT structure: 32 bytes.
    pixel_format = struct.pack(
        "<8I",
        32,             # dwSize
        DDPF_FOURCC,    # dwFlags
        int.from_bytes(fourcc, "little"),
        0,              # dwRGBBitCount
        0,              # dwRBitMask
        0,              # dwGBitMask
        0,              # dwBBitMask
        0,              # dwABitMask
    )

    # DDS_HEADER structure: 124 bytes.
    header = struct.pack(
        "<7I",
        124,            # dwSize
        flags,          # dwFlags
        height,         # dwHeight
        width,          # dwWidth
        linear_size,    # dwPitchOrLinearSize
        0,              # dwDepth
        mip_count,      # dwMipMapCount
    )

    reserved = struct.pack("<11I", *([0] * 11))

    caps_data = struct.pack(
        "<5I",
        caps,           # dwCaps
        0,              # dwCaps2
        0,              # dwCaps3
        0,              # dwCaps4
        0,              # dwReserved2
    )

    return b"DDS " + header + reserved + pixel_format + caps_data


# ---------------------------------------------------------------------
# Write DDS file
# ---------------------------------------------------------------------
def write_dds(mips, output_path):
    if not mips:
        raise ValueError("No mip levels supplied.")

    fmt = mips[0]["format"]

    for mip in mips:
        if mip["format"] != fmt:
            raise ValueError(
                "Mip levels use different formats. "
                "They cannot be combined into one DDS mip chain."
            )

    format_info = FORMATS[fmt]
    dds_type = format_info["dds_type"]
    color_offset = format_info["color_offset"]

    width = mips[0]["width"]
    height = mips[0]["height"]

    dds_block_size = 8 if dds_type == "DXT1" else 16

    header = make_dds_header(
        width,
        height,
        dds_type.encode("ascii"),
        dds_block_size,
        len(mips)
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("wb") as file:
        file.write(header)

        for index, mip in enumerate(mips):
            if fmt == "HC_IMAGE_FORMAT_COMPRESSED_INTERP_ALPHA":
                # Extract the BC1 colour block from each 16-byte block.
                block_count = len(mip["data"]) // 16

                mip_data = b"".join(
                    mip["data"][i * 16 + color_offset:
                                i * 16 + color_offset + 8]
                    for i in range(block_count)
                )

            else:
                # Preserve original DXT1 or DXT3 blocks.
                mip_data = mip["data"]

            file.write(mip_data)

            print(
                f"Written mip {index}: "
                f"{mip['width']}x{mip['height']} "
                f"({len(mip_data):,} bytes)"
            )

    print()
    print("Finished.")
    print(f"RailWorks format: {fmt}")
    print(f"DDS format: {dds_type}")
    print(f"Mip levels: {len(mips)}")
    print(f"Output: {output_path}")
def convert_file(xml_path, output_dir=None, mip_width=None):
    print()
    print("=" * 70)
    print(f"Converting: {xml_path}")
    print("=" * 70)

    mips = parse_texture_xml(xml_path)

    print("Available mip levels:")

    for i, mip in enumerate(mips):
        print(
            f"  {i}: {mip['width']}x{mip['height']} "
            f"{mip['format']}"
        )

    if mip_width is not None:
        mips = [
            mip for mip in mips
            if mip["width"] == mip_width
        ]

        if not mips:
            raise ValueError(f"No mip with width {mip_width} found.")

        mips = [mips[0]]

    filename = xml_path.name
    suffix = ".TgPcDx.xml"

    if filename.lower().endswith(suffix.lower()):
        texture_name = filename[:-len(suffix)]
    else:
        texture_name = xml_path.stem

    if output_dir is None:
        destination = xml_path.parent
    else:
        destination = output_dir

    output_path = destination / f"{texture_name}.dds"

    write_dds(mips, output_path)


def main():
    parser = argparse.ArgumentParser(
        description="Convert RailWorks compressed texture XML files to DDS."
    )

    parser.add_argument(
        "input",
        type=Path,
        help="Path to a .TgPcDx.xml file or a folder containing them."
    )

    parser.add_argument(
        "--mip-width",
        type=int,
        default=None,
        help="Export only the mip with this width."
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output directory. Defaults to the source file/folder."
    )

    args = parser.parse_args()

    input_path = args.input.resolve()

    if not input_path.exists():
        raise FileNotFoundError(input_path)

    if input_path.is_file():
        if not input_path.name.lower().endswith(".tgpcdx.xml"):
            raise ValueError("Input file must end in .TgPcDx.xml")

        files = [input_path]

    elif input_path.is_dir():
        files = sorted(
            path for path in input_path.rglob("*")
            if path.is_file()
            and path.name.lower().endswith(".tgpcdx.xml")
        )

    else:
        raise ValueError(f"Invalid input: {input_path}")

    if not files:
        print("No .TgPcDx.xml files found.")
        return

    print(f"Found {len(files)} texture file(s).")

    successful = 0
    failed = 0

    for xml_path in files:
        try:
            convert_file(
                xml_path,
                output_dir=args.output.resolve() if args.output else None,
                mip_width=args.mip_width
            )
            successful += 1

        except Exception as error:
            failed += 1
            print(f"\nERROR converting {xml_path}: {error}")

    print()
    print("=" * 70)
    print("CONVERSION SUMMARY")
    print("=" * 70)
    print(f"Successful: {successful}")
    print(f"Failed:     {failed}")
    print(f"Total:      {len(files)}")


if __name__ == "__main__":
    main()