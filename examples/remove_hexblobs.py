import re
from pathlib import Path

input_file = Path("lint_body.TgPcDx.xml")
output_file = Path("lint_body_cleaned.TgPcDx.xml")

data = input_file.read_text()

pattern = r'^(?:[0-9A-Fa-f]{16}\s+){3}[0-9A-Fa-f]{16}(?:\r?\n|$)'

data = re.sub(pattern, '', data, flags=re.MULTILINE)

output_file.write_text(data)

print(f"Saved cleaned file to: {output_file}")