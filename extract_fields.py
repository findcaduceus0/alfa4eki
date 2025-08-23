import sys
import re
import zlib
from pathlib import Path
from PyPDF2 import PdfReader


def extract_text(path: Path) -> list[str]:
    """Return decoded text chunks from a PDF using its embedded ToUnicode map."""
    reader = PdfReader(path.open('rb'))
    font = next(iter(reader.pages[0].get('/Resources').get_object()['/Font'].values())).get_object()
    cmap = font['/ToUnicode'].get_data().decode('latin1')
    code_to_char = {}
    for line in cmap.splitlines():
        if line.startswith('<') and '> <' in line:
            left, right = line.split('> <')
            code = left[1:]
            ch = bytes.fromhex(right[:-1]).decode('utf-16-be')
            code_to_char[code] = ch

    data = path.read_bytes()
    start = data.index(b'9 0 obj')
    s = data.index(b'stream\r\n', start) + len(b'stream\r\n')
    e = data.index(b'\r\nendstream', s)
    content = zlib.decompress(data[s:e]).decode('latin1')
    result = []
    for hexstring in re.findall(r'<([0-9A-F]+)> Tj', content):
        text = ''.join(code_to_char.get(hexstring[i:i+4], '?') for i in range(0, len(hexstring), 4))
        result.append(text)
    return result


def main() -> None:
    if len(sys.argv) != 2:
        print('usage: python extract_fields.py FILE.pdf')
        raise SystemExit(1)
    for line in extract_text(Path(sys.argv[1])):
        print(line)


if __name__ == '__main__':
    main()
