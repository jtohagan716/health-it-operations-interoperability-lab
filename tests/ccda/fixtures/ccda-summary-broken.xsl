<?xml version="1.0" encoding="UTF-8"?>

<xsl:stylesheet
    version="1.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:cda="urn:hl7-org:v3"
    exclude-result-prefixes="cda">

    <xsl:output method="html" encoding="UTF-8" indent="yes"/>

    <xsl:template match="/">
        <html>
            <body>
                <h1>C-CDA Clinical Summary</h1>

                <h2>Patient</h2>

                <p>
                    <xsl:value-of
                        select="//cda:recordTarget/cda:patientRole/cda:patient/cda:name/cda:given"
                    />
                    <xsl:text> </xsl:text>
                    <xsl:value-of
                        select="//cda:recordTarget/cda:patientRole/cda:patient/cda:name/cda:family"
                    />
                </p>

                <h2>Medications</h2>

                <ul>
                    <xsl:for-each select="//cda:substanceAdministration">
                        <li>
                            <xsl:value-of
                                select="cda:consumable/cda:manufacturedProduct/cda:manufacturedMaterial/cda:code/@displayName"
                            />

                            <xsl:text> — </xsl:text>

                            <xsl:value-of select="cda:doseQuantity/@value"/>

                            <xsl:text> </xsl:text>

                            <xsl:value-of select="cda:doseQuantity/@unit"/>

                            <!-- INTENTIONAL DEFECT:
                                 routeCode is omitted -->
                        </li>
                    </xsl:for-each>
                </ul>

            </body>
        </html>
    </xsl:template>

</xsl:stylesheet>