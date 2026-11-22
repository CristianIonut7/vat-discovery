from src.sources.website import guess_domains, extract_vat, ch_number_on_page


def test_guess_domains():
    d = guess_domains("FRESH ART CLUB LTD")
    assert "freshartclub.co.uk" in d and "freshartclub.com" in d
    assert "fresh-art-club.co.uk" in d
    assert guess_domains("INGR TECHNOLOGY LTD")[0] == "ingrtechnology.co.uk"


def test_extract_labelled_and_prefixed():
    t = "Registered in England No. 01081551. VAT number: 660 4548 36."
    assert extract_vat(t) == [("660454836", True)]
    assert extract_vat("Our ref GB787440102 thanks") == [("787440102", False)]
    assert extract_vat("Vat Reg 173140925GB") == [("173140925", True)]


def test_extract_rejects_noise():
    assert extract_vat("Call 660454836 now") == []          # no label, no prefix
    assert extract_vat("VAT No: 660454837") == []           # bad checksum
    assert extract_vat("VAT 1660454836") == []              # part of longer number


def test_ch_number():
    assert ch_number_on_page("Company No. 1081551", "01081551")
    assert ch_number_on_page("Company number 01081551.", "01081551")
    assert not ch_number_on_page("Company No. 10815512", "01081551")
    assert ch_number_on_page("Registered SC123456", "SC123456")