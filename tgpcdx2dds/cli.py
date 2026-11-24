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

import sys
import traceback
import argparse
from pathlib import Path
from typing import List

from . import __version__
from .converter import convert_tgpcdx_xml_to_dds


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Convert RailWorks and Train Simulator Classic textures to DDS.\n\n"
            "The source texture must first be converted to XML using serz.exe."
        ),
        epilog=(
            "Example workflow:\n\n"
            "  1. Convert .TgPcDx to XML using serz.exe:\n\n"
            "     serz.exe texture.TgPcDx /xml:texture.TgPcDx.xml\n\n"
            "  2. Convert the resulting XML to DDS:\n\n"
            "     tgpcdx2dds texture.TgPcDx.xml\n\n"
            "  You can also provide a folder to convert all .TgPcDx.xml files, "
            "including files in subdirectories."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
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

    return args


def process_files(files: List[Path], args: argparse.Namespace) -> None:
    if not files:
        print("No .TgPcDx.xml files found.")
        return

    print(f"Found {len(files)} texture file(s).\n")

    successful = 0
    failed = 0

    for xml_path in files:
        try:
            convert_tgpcdx_xml_to_dds(
                xml_path,
                output_dir=args.output.resolve() if args.output else None,
                mip_width=args.mip_width
            )
            successful += 1

        except Exception as error:
            failed += 1
            print(f"ERROR converting {xml_path}: {error}")
            traceback.print_exc()

    print("\n")
    print("=" * 70)
    print("CONVERSION SUMMARY")
    print("=" * 70)
    print(f"Successful: {successful}")
    print(f"Failed:     {failed}")
    print(f"Total:      {len(files)}")


def main() -> None:
    args = parse_args()

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
    
    process_files(files, args)
    









    
