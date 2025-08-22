import pathlib, sys
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
from generate_pdf import generate_pdf, _encode

TEMPLATE_VALUES = (
    "18.08.2025 17:34:11 мск",
    "C421808250875533",
    "A52301434118691P0000060011571101",
    "0a3bf3ec9afc3fdd8e058d7c4b481b6c",
)

def test_recreate_template(tmp_path):
    out = tmp_path / "out.pdf"
    generate_pdf(*TEMPLATE_VALUES, out)
    assert out.read_bytes() == pathlib.Path("pdf 16.pdf").read_bytes()


def _get_content(path: pathlib.Path) -> str:
    import zlib

    data = path.read_bytes()
    start = data.index(b"9 0 obj")
    stream_start = data.index(b"stream\r\n", start) + len(b"stream\r\n")
    stream_end = data.index(b"\r\nendstream", stream_start)
    comp = data[stream_start:stream_end]
    return zlib.decompress(comp).decode("latin1")


def test_custom_fields(tmp_path):
    out = tmp_path / "out.pdf"
    file_id = "1234567890abcdef1234567890abcdef"
    generate_pdf(
        "01.01.2025 00:00 мск",
        "OP123",
        "ID456",
        file_id,
        out,
        form_date="02.02.2025 01:01 мск",
        amount="1,23 RUR",
        commission="1 RUR",
        recipient="Иван Иванов ",
        phone="79998887766",
        bank="Банк",
        account="111111",
        message="Тест",
    )
    content = _get_content(out)
    assert _encode("02.02.2025 01:01 мск") in content
    assert _encode("1,23 RUR ") in content
    assert _encode("1 RUR ") in content
    assert _encode("01.01.2025 00:00 мск ") in content
    assert _encode("OP123 ") in content
    assert _encode("Иван Иванов ") in content
    assert _encode("79998887766") in content
    assert _encode("Банк") in content
    assert _encode("111111") in content
    assert _encode("ID456") in content
    assert _encode("Тест") in content
    trailer = out.read_bytes()[-100:]
    assert (
        f"<{file_id}><{file_id}>".encode("ascii") in trailer
    )
