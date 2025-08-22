import zlib, re, pathlib, io
from typing import Dict

TEMPLATE_PATH = pathlib.Path('pdf 16.pdf')
CHARMAP_PATH = pathlib.Path('pdf.pdf')


def _extract_char_map(path: pathlib.Path) -> Dict[str, str]:
    """Return mapping of characters to hex codes from a PDF file."""
    from PyPDF2 import PdfReader

    char_to_code: Dict[str, str] = {}
    reader = PdfReader(path.open('rb'))
    for page in reader.pages:
        resources = page.get('/Resources')
        if resources is None:
            continue
        resources = resources.get_object()
        fonts = resources.get('/Font', {})
        for font in fonts.values():
            font_obj = font.get_object()
            if '/ToUnicode' not in font_obj:
                continue
            cmap = font_obj['/ToUnicode'].get_data().decode('latin1')
            for line in cmap.splitlines():
                if line.startswith('<') and '>' in line:
                    parts = line.split()
                    if (
                        len(parts) >= 2
                        and parts[0].startswith('<')
                        and parts[1].startswith('<')
                    ):
                        src = parts[0][1:-1]
                        dst = parts[1][1:-1]
                        try:
                            ch = bytes.fromhex(dst).decode('utf-16-be')
                        except Exception:
                            continue
                        char_to_code[ch] = src
    return char_to_code

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
    code_to_char: Dict[str, str] = {}
    char_to_code: Dict[str, str] = {}
    for line in cmap.splitlines():
        if line.startswith('<') and '>' in line:
            parts = line.split()
            if len(parts) >= 2 and parts[0].startswith('<') and parts[1].startswith('<'):
                src = parts[0][1:-1]
                dst = parts[1][1:-1]
                try:
                    ch = bytes.fromhex(dst).decode('utf-16-be')
                except Exception:
                    continue
                code_to_char[src] = ch
                char_to_code[ch] = src
    if CHARMAP_PATH.exists():
        extra = _extract_char_map(CHARMAP_PATH)
        for ch, code in extra.items():
            char_to_code.setdefault(ch, code)
    # get uncompressed content template
    raw_content = reader.get_object(IndirectObject(9,0,reader))._data
    uncomp = zlib.decompress(raw_content).decode('latin1')
    return objects, order, char_to_code, uncomp

OBJECTS, ORDER, CHAR_TO_CODE, CONTENT_TEMPLATE = _parse_template()

# precompute hex strings for fields in template

def _encode(text: str) -> str:
    text = text.replace(' ', '\u00A0')
    return ''.join(CHAR_TO_CODE[ch] for ch in text)

OLD_FORM_DATE = _encode('22.08.2025 11:28 мск')
OLD_AMOUNT = _encode('0,01 RUR ')
OLD_COMMISSION = _encode('0 RUR ')
OLD_DATE = _encode('18.08.2025 17:34:11 мск ')
OLD_OPER = _encode('C421808250875533 ')
OLD_FIO = _encode('Михаил Сергеевич К ')
OLD_PHONE = _encode('7й526247787')
OLD_BANK = _encode('В-Банк')
OLD_ACCOUNT = _encode('408178100088600й7530')
OLD_ID   = _encode('A52301434118691P0000060011571101')
OLD_MESSAGE = _encode('Перевод денеАнЕГ средств')

def generate_pdf(
    date_time: str,
    operation: str,
    sbp_id: str,
    file_id: str,
    out_path: pathlib.Path,
    *,
    form_date: str = '22.08.2025 11:28 мск',
    amount: str = '0,01 RUR',
    commission: str = '0 RUR',
    recipient: str = 'Михаил Сергеевич К',
    phone: str = '7й526247787',
    bank: str = 'В-Банк',
    account: str = '408178100088600й7530',
    message: str = 'Перевод денеАнЕГ средств',
):
    # prepare new uncompressed content
    new_content = CONTENT_TEMPLATE
    replacements = {
        OLD_FORM_DATE: form_date,
        OLD_AMOUNT: amount,
        OLD_COMMISSION: commission,
        OLD_DATE: date_time,
        OLD_OPER: operation,
        OLD_FIO: recipient,
        OLD_PHONE: phone,
        OLD_BANK: bank,
        OLD_ACCOUNT: account,
        OLD_ID: sbp_id,
        OLD_MESSAGE: message,
    }
    for old, new in replacements.items():
        enc_new = _encode(new)
        if old.endswith('000A') and not enc_new.endswith('000A'):
            enc_new += '000A'
        new_content = new_content.replace(f'<{old}>', f'<{enc_new}>')
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
    import argparse

    parser = argparse.ArgumentParser(description='Generate PDF receipt')
    parser.add_argument('date_time')
    parser.add_argument('operation')
    parser.add_argument('sbp_id')
    parser.add_argument('file_id')
    parser.add_argument('output')
    parser.add_argument('--form-date', default='22.08.2025 11:28 мск')
    parser.add_argument('--amount', default='0,01 RUR')
    parser.add_argument('--commission', default='0 RUR')
    parser.add_argument('--recipient', default='Михаил Сергеевич К ')
    parser.add_argument('--phone', default='7й526247787')
    parser.add_argument('--bank', default='В-Банк')
    parser.add_argument('--account', default='408178100088600й7530')
    parser.add_argument('--message', default='Перевод денеАнЕГ средств')
    args = parser.parse_args()

    generate_pdf(
        args.date_time,
        args.operation,
        args.sbp_id,
        args.file_id,
        pathlib.Path(args.output),
        form_date=args.form_date,
        amount=args.amount,
        commission=args.commission,
        recipient=args.recipient,
        phone=args.phone,
        bank=args.bank,
        account=args.account,
        message=args.message,
    )
