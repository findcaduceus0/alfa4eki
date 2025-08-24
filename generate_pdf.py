import os, zlib, pathlib, io, re
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Dict, Tuple

import ids

# Allow overriding template and charmap via environment variables so the
# generator can reproduce different reference PDFs without modifying the
# source code.
TEMPLATE_PATH = pathlib.Path(os.environ.get("PDF_TEMPLATE", "pdf 16.pdf"))
CHARMAP_PATH = pathlib.Path(os.environ.get("CHARMAP_PDF", "pdf.pdf"))


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

    # discover placeholders for dynamic fields by decoding content stream
    segments = re.findall(r'<([0-9A-F]+)>', uncomp)
    decoded = [
        ''.join(code_to_char.get(seg[i:i+4], '') for i in range(0, len(seg), 4)).replace('\u00A0', ' ')
        for seg in segments
    ]
    labels = {
        'Сформирована': 'form_date',
        'Сумма перевода': 'amount',
        'Комиссия': 'commission',
        'Дата и время перевода': 'date',
        'Номер операции': 'oper',
        'Получатель': 'recipient',
        'Номер телефона получателя': 'phone',
        'Банк получателя': 'bank',
        'Счёт списания': 'account',
        'Идентификатор операции в СБП': 'id',
        'Сообщение получателю': 'message',
    }
    placeholders: Dict[str, str] = {}
    i = 0
    while i < len(decoded):
        text = decoded[i].strip()
        if text in labels:
            key = labels[text]
            i += 1
            while i < len(decoded) and decoded[i].strip() == '':
                i += 1
            if i < len(decoded):
                placeholders[key] = segments[i]
        else:
            i += 1
    if len(placeholders) != len(labels):
        raise ValueError('failed to locate all placeholders in template')
    return objects, order, char_to_code, uncomp, placeholders

OBJECTS, ORDER, CHAR_TO_CODE, CONTENT_TEMPLATE, PLACEHOLDERS = _parse_template()

_MSK_TZ = timezone(timedelta(hours=3))


@dataclass
class ReceiptFields:
    form_date: str = '22.08.2025 11:28 мск'
    amount: str = '0,01 RUR'
    commission: str = '0 RUR'
    # The recipient field in the template contains a trailing space before
    # the line break. Keep the same default so regenerating the reference
    # PDF does not rely on implicit padding logic.
    recipient: str = 'Михаил Сергеевич К '
    phone: str = '7й526247787'
    bank: str = 'В-Банк'
    account: str = '408178100088600й7530'
    message: str = 'Перевод денеАнЕГ средств'


def _format_msk(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_MSK_TZ)
    else:
        dt = dt.astimezone(_MSK_TZ)
    return dt.strftime("%d.%m.%Y %H:%M:%S мск")

def _encode(text: str) -> str:
    text = text.replace(' ', '\u00A0')
    return ''.join(CHAR_TO_CODE[ch] for ch in text)


def generate_pdf_with_ids(
    when: datetime,
    file_id: str | None,
    out_path: pathlib.Path,
    *,
    prefix: str = "B",
    node: str = "7310",
    route: str = "K",
    code4: str = "2001",
    tail7: str = "1571101",
    pp: str = "42",
    fields: ReceiptFields | None = None,
    form_date: str = '22.08.2025 11:28 мск',
    amount: str = '0,01 RUR',
    commission: str = '0 RUR',
    recipient: str = 'Михаил Сергеевич К ',
    phone: str = '7й526247787',
    bank: str = 'В-Банк',
    account: str = '408178100088600й7530',
    message: str = 'Перевод денеАнЕГ средств',
) -> Tuple[str, str, str]:
    sbp_id = ids.generate_sbp_id(
        when,
        prefix=prefix,
        node=node,
        route=route,
        code4=code4,
        tail7=tail7,
    )
    operation = ids.generate_op_number(when, pp=pp)
    date_time = _format_msk(when)
    if file_id is None:
        file_id = ids.generate_file_id()
    else:
        ids.validate_file_id(file_id)
    fields = fields or ReceiptFields(
        form_date=form_date,
        amount=amount,
        commission=commission,
        recipient=recipient,
        phone=phone,
        bank=bank,
        account=account,
        message=message,
    )
    generate_pdf(
        date_time,
        operation,
        sbp_id,
        file_id,
        out_path,
        fields=fields,
    )
    return operation, sbp_id, file_id

def generate_pdf(
    date_time: str,
    operation: str,
    sbp_id: str,
    file_id: str,
    out_path: pathlib.Path,
    *,
    fields: ReceiptFields | None = None,
    form_date: str = '22.08.2025 11:28 мск',
    amount: str = '0,01 RUR',
    commission: str = '0 RUR',
    recipient: str = 'Михаил Сергеевич К ',
    phone: str = '7й526247787',
    bank: str = 'В-Банк',
    account: str = '408178100088600й7530',
    message: str = 'Перевод денеАнЕГ средств',
):
    ids.validate_file_id(file_id)
    fields = fields or ReceiptFields(
        form_date=form_date,
        amount=amount,
        commission=commission,
        recipient=recipient,
        phone=phone,
        bank=bank,
        account=account,
        message=message,
    )
    # prepare new uncompressed content
    new_content = CONTENT_TEMPLATE
    replacements = {
        PLACEHOLDERS['form_date']: fields.form_date,
        PLACEHOLDERS['amount']: fields.amount,
        PLACEHOLDERS['commission']: fields.commission,
        PLACEHOLDERS['date']: date_time,
        PLACEHOLDERS['oper']: operation,
        PLACEHOLDERS['recipient']: fields.recipient,
        PLACEHOLDERS['phone']: fields.phone,
        PLACEHOLDERS['bank']: fields.bank,
        PLACEHOLDERS['account']: fields.account,
        PLACEHOLDERS['id']: sbp_id,
        PLACEHOLDERS['message']: fields.message,
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
    sub = parser.add_subparsers(dest='mode', required=True)

    manual = sub.add_parser('manual', help='use explicit identifiers')
    manual.add_argument('date_time')
    manual.add_argument('operation')
    manual.add_argument('sbp_id')
    manual.add_argument('file_id')
    manual.add_argument('output')
    manual.add_argument('--form-date', default='22.08.2025 11:28 мск')
    manual.add_argument('--amount', default='0,01 RUR')
    manual.add_argument('--commission', default='0 RUR')
    manual.add_argument('--recipient', default='Михаил Сергеевич К ')
    manual.add_argument('--phone', default='7й526247787')
    manual.add_argument('--bank', default='В-Банк')
    manual.add_argument('--account', default='408178100088600й7530')
    manual.add_argument('--message', default='Перевод денеАнЕГ средств')

    auto = sub.add_parser('auto', help='generate identifiers automatically')
    auto.add_argument('when', help='ISO timestamp')
    auto.add_argument('file_id', nargs='?')
    auto.add_argument('output')
    auto.add_argument('--prefix', default='B')
    auto.add_argument('--node', default='7310')
    auto.add_argument('--route', default='K')
    auto.add_argument('--code4', default='2001')
    auto.add_argument('--tail7', default='1571101')
    auto.add_argument('--pp', default='42')
    auto.add_argument('--form-date', default='22.08.2025 11:28 мск')
    auto.add_argument('--amount', default='0,01 RUR')
    auto.add_argument('--commission', default='0 RUR')
    auto.add_argument('--recipient', default='Михаил Сергеевич К ')
    auto.add_argument('--phone', default='7й526247787')
    auto.add_argument('--bank', default='В-Банк')
    auto.add_argument('--account', default='408178100088600й7530')
    auto.add_argument('--message', default='Перевод денеАнЕГ средств')

    args = parser.parse_args()

    if args.mode == 'manual':
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
    else:
        when = datetime.fromisoformat(args.when)
        generate_pdf_with_ids(
            when,
            args.file_id,
            pathlib.Path(args.output),
            prefix=args.prefix,
            node=args.node,
            route=args.route,
            code4=args.code4,
            tail7=args.tail7,
            pp=args.pp,
            form_date=args.form_date,
            amount=args.amount,
            commission=args.commission,
            recipient=args.recipient,
            phone=args.phone,
            bank=args.bank,
            account=args.account,
            message=args.message,
        )
