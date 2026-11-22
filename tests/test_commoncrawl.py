from src.sources.commoncrawl import extract_ch, norm_ch


def test_norm_ch():
    assert norm_ch("1081551") == "01081551"
    assert norm_ch("SC123456") == "SC123456"
    assert norm_ch("sc 123456") == "SC123456"


def test_extract_ch_variants():
    assert extract_ch("Registered in England No. 01081551. VAT 660454836") == ["01081551"]
    assert extract_ch("Company number: 1081551") == ["01081551"]
    assert extract_ch("Registered in England and Wales, company no 12659342") == ["12659342"]
    assert extract_ch("Company Registration Number SC123456") == ["SC123456"]
    assert extract_ch("Reg. No. 08692717") == ["08692717"]


def test_extract_ch_ignores_unlabelled():
    assert extract_ch("Call 01081551 or order 12659342") == []