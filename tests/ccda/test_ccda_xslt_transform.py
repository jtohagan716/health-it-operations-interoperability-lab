from pathlib import Path

from lxml import etree


XML_PATH = Path("examples/ccda/avery-testpatient-ccd.xml")
XSL_PATH = Path("examples/ccda/ccda-summary.xsl")


def transform_ccda() -> str:
    xml = etree.parse(str(XML_PATH))
    xsl = etree.parse(str(XSL_PATH))

    transform = etree.XSLT(xsl)
    result = transform(xml)

    return str(result)


def test_xslt_transformation_produces_html():
    html = transform_ccda()

    assert "<html" in html
    assert "C-CDA Clinical Summary" in html


def test_xslt_preserves_patient_identity():
    html = transform_ccda()

    assert "Avery Testpatient" in html
    assert "19800115" in html


def test_xslt_preserves_medication_semantics():
    html = transform_ccda()

    assert "lisinopril 10 MG Oral Tablet" in html
    assert "10 mg" in html
    assert "By Mouth" in html


def test_xslt_preserves_expected_encounters():
    html = transform_ccda()

    assert "Routine office visit - synthetic interoperability lab encounter" in html
    assert "Persistent cough" in html

    assert "202608132322+0000" in html
    assert "202608251544+0000" in html

BROKEN_XSL_PATH = Path(
    "tests/ccda/fixtures/ccda-summary-broken.xsl"
)


def test_broken_xslt_demonstrates_semantic_loss():
    xml = etree.parse(str(XML_PATH))
    xsl = etree.parse(str(BROKEN_XSL_PATH))

    transform = etree.XSLT(xsl)
    result = transform(xml)

    html = str(result)

    assert "lisinopril 10 MG Oral Tablet" in html
    assert "10 mg" in html

    # The source C-CDA contains the route, but this defective
    # transformation silently drops it.
    assert "By Mouth" not in html