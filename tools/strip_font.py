#!/usr/bin/env python3
"""
BDF font optimizer - strips to ASCII and converts to PCF.
Usage: python strip_font.py input.bdf output.pcf
"""

import os
import shutil
import subprocess
import sys
import tempfile


def strip_bdf(input_path, output_path, char_range=(32, 126)):
    """Strip BDF to minimal ASCII."""
    with open(input_path, "r") as f:
        lines = f.read().split("\n")

    output = []
    in_char = False
    char_lines = []
    encoding = None
    kept = 0

    for line in lines:
        s = line.strip()

        if s.startswith("STARTCHAR"):
            in_char = True
            char_lines = [line]
            continue

        if in_char:
            char_lines.append(line)
            if s.startswith("ENCODING"):
                try:
                    encoding = int(s.split()[1])
                except (IndexError, ValueError):
                    encoding = None
            if s == "ENDCHAR":
                in_char = False
                if encoding is not None and char_range[0] <= encoding <= char_range[1]:
                    output.extend(char_lines)
                    kept += 1
                char_lines = []
            continue

        if s.startswith("CHARS "):
            output.append("CHARS_PLACEHOLDER")
            continue

        output.append(line)

    content = "\n".join(output).replace("CHARS_PLACEHOLDER", f"CHARS {kept}")
    with open(output_path, "w") as f:
        f.write(content)

    print(f"Stripped: {kept} chars kept")
    return output_path


def main():
    if len(sys.argv) < 3:
        print("Usage: python strip_font.py input.bdf output.pcf")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    # Strip BDF into a private temp file
    fd, stripped = tempfile.mkstemp(suffix=".bdf")
    os.close(fd)
    strip_bdf(input_path, stripped)

    # Convert to PCF
    if output_path.endswith(".pcf"):
        try:
            subprocess.run(["bdftopcf", "-o", output_path, stripped], check=True)
            print(f"Created: {output_path} ({os.path.getsize(output_path)} bytes)")
            os.remove(stripped)
        except FileNotFoundError:
            bdf_path = output_path[: -len(".pcf")] + ".bdf"
            print(
                f"bdftopcf not found (brew install bdftopcf), keeping BDF: {bdf_path}"
            )
            shutil.move(stripped, bdf_path)
    else:
        shutil.move(stripped, output_path)


if __name__ == "__main__":
    main()
