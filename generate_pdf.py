import zlib, re, sys, pathlib, io
from typing import Dict

TEMPLATE_PATH = pathlib.Path('pdf 16.pdf')

# We will load template and extract objects on first run

def _parse_template():
    data = TEMPLATE_PATH.read_bytes()
    # find startxref position and parse cross reference table
    startxref = data.rfind(b'startxref')
    start = startxref + len(b'startxref') + 2  # skip keyword and CRLF
    end = data.find(b'\r\n', start)
    xref_offset = int(data[start:end])
    xref = data[xref_offset:]
    lines = xref.splitlines()
    # expect lines[0]=b'xref', lines[1]=b'0 17'
    offsets = []
    for line in lines[2:2+17]:
        offsets.append(int(line[:10]))
    off_map = {i: offsets[i] for i in range(17)}
    order = [5,6,7,8,9,1,2,3,4,10,11,12,13,14,15,16]
    objects = {}
    for idx,objnum in enumerate(order):
        start = off_map[objnum]
        end = off_map[order[idx+1]] if idx+1 < len(order) else xref_offset
        objects[objnum] = data[start:end]
    # build mapping from ToUnicode
    from PyPDF2 import PdfReader
    from PyPDF2.generic import IndirectObject
    reader = PdfReader(io.BytesIO(data))
    tounicode = reader.get_object(IndirectObject(14,0,reader))._data
    cmap = zlib.decompress(tounicode).decode('latin1')
    code_to_char: Dict[str,str] = {}
    char_to_code: Dict[str,str] = {}
    for line in cmap.splitlines():
        if line.startswith('<') and '>' in line:
            parts=line.split()
            if len(parts)>=2 and parts[0].startswith('<') and parts[1].startswith('<'):
                src=parts[0][1:-1]
                dst=parts[1][1:-1]
                try:
                    ch=bytes.fromhex(dst).decode('utf-16-be')
                except Exception:
                    continue
                code_to_char[src]=ch
                char_to_code[ch]=src
    # get uncompressed content template
    raw_content = reader.get_object(IndirectObject(9,0,reader))._data
    uncomp = zlib.decompress(raw_content).decode('latin1')
    return objects, order, char_to_code, uncomp

OBJECTS, ORDER, CHAR_TO_CODE, CONTENT_TEMPLATE = _parse_template()

# precompute hex strings for fields in template

def _encode(text: str) -> str:
    text = text.replace(' ', '\u00A0')
    return ''.join(CHAR_TO_CODE[ch] for ch in text)

OLD_DATE = _encode('18.08.2025 17:34:11 мск')
OLD_OPER = _encode('C421808250875533')
OLD_ID   = _encode('A52301434118691P0000060011571101')

def generate_pdf(date_time: str, operation: str, sbp_id: str, file_id: str, out_path: pathlib.Path):
    # prepare new uncompressed content
    new_content = CONTENT_TEMPLATE
    new_content = new_content.replace(f'<{OLD_DATE}>', f'<{_encode(date_time)}>')
    new_content = new_content.replace(f'<{OLD_OPER}>', f'<{_encode(operation)}>')
    new_content = new_content.replace(f'<{OLD_ID}>',   f'<{_encode(sbp_id)}>')
    comp = zlib.compress(new_content.encode('latin1'), 6)
    obj9 = (
        b"9 0 obj\r\n" +
        f"<< /Length {len(comp)} /Filter /FlateDecode >>\r\n".encode('ascii') +
        b"stream\r\n" + comp + b"\r\nendstream\r\nendobj\r\n"
    )
    objects = OBJECTS.copy()
    objects[9] = obj9

    # build PDF
    out = bytearray(b"%PDF-1.6\r\n")
    offsets = {}
    for objnum in ORDER:
        offsets[objnum] = len(out)
        out.extend(objects[objnum])
    xref_pos = len(out)
    out.extend(b"xref\r\n0 17\r\n")
    out.extend(b"0000000000 65535 f\r\n")
    for i in range(1,17):
        out.extend(f"{offsets[i]:010d} 00000 n\r\n".encode('ascii'))
    out.extend(b"trailer\r\n<<\r\n/Size 17\r\n/Root 1 0 R\r\n/Info 2 0 R\r\n")
    out.extend(f"/ID [<{file_id}><{file_id}>]\r\n".encode('ascii'))
    out.extend(b">>\r\nstartxref\r\n")
    out.extend(f"{xref_pos}\r\n%%EOF\r\n".encode('ascii'))
    out_path.write_bytes(out)

if __name__ == '__main__':
    if len(sys.argv) != 6:
        print('Usage: generate_pdf.py DATE_TIME OPERATION SBP_ID FILE_ID OUTPUT')
        sys.exit(1)
    generate_pdf(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], pathlib.Path(sys.argv[5]))
