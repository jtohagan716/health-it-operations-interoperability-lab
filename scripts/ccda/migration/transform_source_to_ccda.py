from pathlib import Path
from lxml import etree

SOURCE = Path("examples/ccda/migration/avery-source.xml")
XSLT = Path("examples/ccda/migration/source-to-ccda.xsl")
TARGET = Path("examples/ccda/migration/avery-target-ccda.xml")

source = etree.parse(str(SOURCE))
stylesheet = etree.parse(str(XSLT))

transform = etree.XSLT(stylesheet)
result = transform(source)

TARGET.write_bytes(
    etree.tostring(
        result,
        pretty_print=True,
        xml_declaration=True,
        encoding="UTF-8",
    )
)

print(TARGET)
