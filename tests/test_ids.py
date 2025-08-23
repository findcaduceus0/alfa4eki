import pathlib, sys
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
from datetime import datetime, timezone, timedelta


import ids


WHEN = datetime(2025, 8, 17, 22, 41, 38, tzinfo=timezone(timedelta(hours=3)))


def setup_function(_):
    ids._SBP_COUNTER.clear()
    ids._OP_COUNTER.clear()


def test_generate_sbp_id():
    sbp_id = ids.generate_sbp_id(WHEN)
    assert len(sbp_id) == 32
    ids.validate_sbp_id(sbp_id)
    assert sbp_id.startswith("B5")
    assert sbp_id[2:5] == "229"
    assert sbp_id[5:11] == "194138"
    assert sbp_id[11:15] == "7310"
    assert sbp_id[15] == "K"
    assert sbp_id[16:21] == "00001"
    assert sbp_id[21:25] == "2001"
    assert sbp_id[25:] == "1571101"


def test_generate_op_number():
    opn = ids.generate_op_number(WHEN)
    assert len(opn) == 16
    ids.validate_op_number(opn)
    assert opn.startswith("C42170825")


def test_sbp_sequence_increment():
    first = ids.generate_sbp_id(WHEN)
    second = ids.generate_sbp_id(WHEN)
    assert first[16:21] == "00001"
    assert second[16:21] == "00002"
