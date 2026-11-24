# tgpcdx2dds

[![GitHub release (latest by date)](https://img.shields.io/github/v/release/pgroenbaek/tgpcdx2dds?style=flat&label=Latest%20Version)](https://github.com/pgroenbaek/tgpcdx2dds/releases)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![License MIT](https://img.shields.io/badge/License-MIT-lightgrey?style=flat&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA2NDAgNTEyIj4KICA8IS0tIEZvbnQgQXdlc29tZSBGcmVlIDYuNy4yIGJ5IEBmb250YXdlc29tZSAtIGh0dHBzOi8vZm9udGF3ZXNvbWUuY29tIExpY2Vuc2UgLSBodHRwczovL2ZvbnRhd2Vzb21lLmNvbS9saWNlbnNlL2ZyZWUgQ29weXJpZ2h0IDIwMjUgRm9udGljb25zLCBJbmMuIC0tPgogIDxwYXRoIGZpbGw9IndoaXRlIiBkPSJNMzg0IDMybDEyOCAwYzE3LjcgMCAzMiAxNC4zIDMyIDMycy0xNC4zIDMyLTMyIDMyTDM5OC40IDk2Yy01LjIgMjUuOC0yMi45IDQ3LjEtNDYuNCA1Ny4zTDM1MiA0NDhsMTYwIDBjMTcuNyAwIDMyIDE0LjMgMzIgMzJzLTE0LjMgMzItMzIgMzJsLTE5MiAwLTE5MiAwYy0xNy43IDAtMzItMTQuMy0zMi0zMnMxNC4zLTMyIDMyLTMybDE2MCAwIDAtMjk0LjdjLTIzLjUtMTAuMy00MS4yLTMxLjYtNDYuNC01Ny4zTDEyOCA5NmMtMTcuNyAwLTMyLTE0LjMtMzItMzJzMTQuMy0zMiAzMi0zMmwxMjggMGMxNC42LTE5LjQgMzcuOC0zMiA2NC0zMnM0OS40IDEyLjYgNjQgMzJ6bTU1LjYgMjg4bDE0NC45IDBMNTEyIDE5NS44IDQzOS42IDMyMHpNNTEyIDQxNmMtNjIuOSAwLTExNS4yLTM0LTEyNi03OC45Yy0yLjYtMTEgMS0yMi4zIDYuNy0zMi4xbDk1LjItMTYzLjJjNS04LjYgMTQuMi0xMy44IDI0LjEtMTMuOHMxOS4xIDUuMyAyNC4xIDEzLjhsOTUuMiAxNjMuMmM1LjcgOS44IDkuMyAyMS4xIDYuNyAzMi4xQzYyNy4yIDM4MiA1NzQuOSA0MTYgNTEyIDQxNnpNMTI2LjggMTk1LjhMNTQuNCAzMjBsMTQ0LjkgMEwxMjYuOCAxOTUuOHpNLjkgMzM3LjFjLTIuNi0xMSAxLTIyLjMgNi43LTMyLjFsOTUuMi0xNjMuMmM1LTguNiAxNC4yLTEzLjggMjQuMS0xMy44czE5LjEgNS4zIDI0LjEgMTMuOGw5NS4yIDE2My4yYzUuNyA5LjggOS4zIDIxLjEgNi43IDMyLjFDMjQyIDM4MiAxODkuNyA0MTYgMTI2LjggNDE2UzExLjcgMzgyIC45IDMzNy4xeiIvPgo8L3N2Zz4=&logoColor=%23ffffff)](https://github.com/pgroenbaek/tgpcdx2dds/blob/master/LICENSE)

A cross-platform CLI and Python module for batch converting TgPcDx textures to DDS.

## Installation

The CLI or Python module can be installed in the following ways:

### Standalone CLI executable

Download the standalone CLI executable from the [Releases](https://github.com/pgroenbaek/tgpcdx2dds/releases) page for your operating system, then extract it somewhere you can find it.

See [Usage](#Usage) for details on how to use the CLI.

### Python module from PyPI

```sh
pip install --upgrade tgpcdx2dds
```

### Python module from wheel

If you have downloaded a `.whl` file from the [Releases](https://github.com/pgroenbaek/tgpcdx2dds/releases) page, install it with:

```sh
pip install path/to/tgpcdx2dds-<version>‑py3‑none‑any.whl
```

Replace `<version>` with the actual version number in the filename.

### Python module from source

```sh
git clone https://github.com/pgroenbaek/tgpcdx2dds.git
pip install --upgrade ./tgpcdx2dds
```

## Usage

### Unpacking `.TgPcDx` files to xml

This CLI / Python module does not read `.TgPcDx` files directly. First unpack them to `.TgPcDx.xml` using the `serz.exe` program included with Railworks and TS Classic.

#### Unpacking on Windows
On windows, the use the following command in PowerShell to convert all files in a directory and its sub directories.

Replace paths to the `serz.exe` file and the asset directory.

```ps1
$Serz="D:\Path\To\serz.exe";
$AssetRoot="D:\Path\To\Asset";

gci $AssetRoot -Recurse -File -Include *.TgPcDx | % { & $Serz $_.FullName "/xml:$($_.FullName).xml" }
```

#### Unpacking on Linux via `wine`
On Linux, use the following bash script to achieve the same.

Wine is required to be installed on the system in order to do this on Linux.

```bash
SERZ="/path/to/serz.exe"
ASSET_ROOT="/path/to/Asset"

find "$ASSET_ROOT" -type f -iname '*.TgPcDx' -print0 |
while IFS= read -r -d '' file; do
    winfile=$(winepath -w "$file")
    wine "$SERZ" "$winfile" "/xml:${winfile}.xml"
done
```

### Running the CLI

#### Windows

```ps1
.\tgpcdx2dds.exe inputfile.TgPcDx.xml
```

#### Linux

```bash
./tgpcdx2dds inputfile.TgPcDx.xml
```

### Running as a Python module

```bash
python3 -m tgpcdx2dds inputfile.TgPcDx.xml
```

Note that a directory can be supplied to the CLI and Python module instead an input file.

In that case, all files with the `.TgPcDx.xml` extension present in the folder and its subfolders will be converted to `.dds`.

### Using the module in Python scripts

```python
from pathlib import Path
from tgpcdx2dds import convert_tgpcdx_xml_to_dds

input_path: Path = Path("path/to/inputfile.TgPcDx.xml")

convert_tgpcdx_xml_to_dds(
    input_path,
    output_dir=None, # Supply a dir if you want a different output folder
    mip_width=None # Supply a number like 256, 512, 1024 for a specific mip level only.
)
```

Comparable parameters to `output_dir` and `mip_width` also exist on the CLI.

Use the `--output` and `--mip-width` parameters there.

## Building

### Prerequisites

A Python 3.8+ installation is needed for building the module and standalone CLI executable.

In addition, Nuitka is required for building the standalone CLI executable, install it from `pip` using:

```bash
pip install "nuitka[onefile]"
```

### Building the wheel and CLI executable:

#### Windows

Run the following command in PowerShell:

```ps1
.\tools\package_windows.ps1
```

#### Linux

Run the following command in a terminal:

```bash
./tools/package_linux.sh
```

## License
This project is licensed under the [MIT License](https://github.com/pgroenbaek/tgpcdx2dds/blob/master/LICENSE).