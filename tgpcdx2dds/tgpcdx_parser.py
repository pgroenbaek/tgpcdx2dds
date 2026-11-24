"""
This file is part of TgPcDx2Dds.

Copyright (C) 2026 Peter Grønbæk Andersen <peter@grnbk.io>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import re
import xml.etree.ElementTree as ET

from .formats import FORMATS
from .xml_helper import local_name, find_child, find_text


def parse_texture_xml(xml_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()

    mip_entries = []

    for element in root.iter():
        if local_name(element.tag) != "cHcImageDx":
            continue

        format_element = find_child(element, "Format")
        blob_element = find_child(element, "blob")

        if format_element is None or blob_element is None:
            continue

        format_text = (format_element.text or "").strip()

        if format_text not in FORMATS:
            raise ValueError(f"Texture format '{format_text}' not supported")

        width = int(find_text(element, "Width"))
        height = int(find_text(element, "Height"))

        swizzled = find_text(element, "IsSwizzled").lower()

        if swizzled not in ("0", "false"):
            raise ValueError(f"Swizzled texture not supported: {width}x{height}")

        hex_data = re.sub(r"\s+", "", blob_element.text or "")

        if len(hex_data) % 2:
            raise ValueError(f"Odd number of hexadecimal characters in {width}x{height} mip.")

        data = bytes.fromhex(hex_data)

        block_size = FORMATS[format_text]["block_size"]

        blocks_x = (width + 3) // 4
        blocks_y = (height + 3) // 4

        expected_size = blocks_x * blocks_y * block_size

        if len(data) != expected_size:
            raise ValueError(f"Incorrect blob size for {width}x{height}: expected {expected_size}, got {len(data)}")

        mip_entries.append({
            "format": format_text,
            "width": width,
            "height": height,
            "data": data,
        })

    if not mip_entries:
        raise ValueError("No supported compressed texture mip found.")

    mip_entries.sort(key=lambda mip: mip["width"] * mip["height"], reverse=True)

    return mip_entries