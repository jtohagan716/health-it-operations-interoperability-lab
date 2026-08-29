<?xml version="1.0" encoding="UTF-8"?>

<xsl:stylesheet
    version="1.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:cda="urn:hl7-org:v3"
    exclude-result-prefixes="cda">

    <xsl:output method="html" encoding="UTF-8" indent="yes"/>

    <xsl:template match="/">
        <html>
            <head>
                <title>C-CDA Clinical Summary</title>
            </head>

            <body>
                <h1>C-CDA Clinical Summary</h1>

                <h2>Patient</h2>

                <p>
                    <strong>Name:</strong>
                    <xsl:text> </xsl:text>

                    <xsl:value-of
                        select="//cda:recordTarget/cda:patientRole/cda:patient/cda:name/cda:given"
                    />

                    <xsl:text> </xsl:text>

                    <xsl:value-of
                        select="//cda:recordTarget/cda:patientRole/cda:patient/cda:name/cda:family"
                    />
                </p>

                <p>
                    <strong>Birth Date:</strong>
                    <xsl:text> </xsl:text>

                    <xsl:value-of
                        select="//cda:recordTarget/cda:patientRole/cda:patient/cda:birthTime/@value"
                    />
                </p>

                <h2>Medications</h2>

                <ul>
                    <xsl:for-each select="//cda:substanceAdministration">

                        <li>
                            <strong>
                                <xsl:value-of
                                    select="cda:consumable/cda:manufacturedProduct/cda:manufacturedMaterial/cda:code/@displayName"
                                />
                            </strong>

                            <xsl:text> — </xsl:text>

                            <xsl:value-of select="cda:doseQuantity/@value"/>

                            <xsl:text> </xsl:text>

                            <xsl:value-of select="cda:doseQuantity/@unit"/>

                            <xsl:text>, route: </xsl:text>

                            <xsl:value-of select="cda:routeCode/@displayName"/>
                        </li>

                    </xsl:for-each>
                </ul>

                <h2>Encounters</h2>

                <ul>
                    <xsl:for-each select="//cda:encounter">

                        <li>
                            <xsl:value-of select="cda:code/@displayName"/>

                            <xsl:text> — </xsl:text>

                            <xsl:value-of select="cda:effectiveTime/@value"/>
                        </li>

                    </xsl:for-each>
                </ul>

            </body>
        </html>
    </xsl:template>

</xsl:stylesheet>