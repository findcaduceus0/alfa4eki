import os
import pathlib
import importlib


def test_recreate_uploaded(tmp_path):
    # Ensure the generator parses the uploaded PDF as its template.
    os.environ['PDF_TEMPLATE'] = 'file_761814.pdf'
    import generate_pdf
    importlib.reload(generate_pdf)
    out = tmp_path / 'out.pdf'
    generate_pdf.generate_pdf(
        '31.07.2025 22:44:47 мск',
        'C163107252025837',
        'A52121944483950C0000040011570301',
        '06f23bf2b75ca27053851f7be875ad79',
        out,
        form_date='31.07.2025 23:50 мск',
        amount='3 003 RUR',
        commission='0 RUR',
        recipient='Галина Григорьевна А',
        phone='79832605711',
        bank='Т-Банк',
        account='40817810709900080272',
        message='Перевод денежных средств',
    )
    assert out.read_bytes() == pathlib.Path('file_761814.pdf').read_bytes()
