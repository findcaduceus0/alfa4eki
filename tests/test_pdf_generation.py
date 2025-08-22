import pathlib, sys
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
from generate_pdf import generate_pdf

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
