<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet
    version="1.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns="urn:hl7-org:v3"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    exclude-result-prefixes="xsl">

  <xsl:output method="xml" indent="yes" encoding="UTF-8"/>

  <xsl:template match="/MigrationSource">

    <ClinicalDocument>
      <realmCode code="US"/>

      <typeId
        root="2.16.840.1.113883.1.3"
        extension="POCD_HD000040"/>

      <templateId
        root="2.16.840.1.113883.10.20.22.1.2"
        extension="2015-08-01"/>

      <id
        root="2.16.840.1.113883.19.5.99999.1"
        extension="MIGRATION-AVERY-0001"/>

      <code
        code="34133-9"
        codeSystem="2.16.840.1.113883.6.1"
        codeSystemName="LOINC"
        displayName="Summarization of Episode Note"/>

      <title>Migration Validation Patient Summary</title>

      <effectiveTime value="20260914"/>

      <confidentialityCode
        code="N"
        codeSystem="2.16.840.1.113883.5.25"/>

      <languageCode code="en-US"/>

      <recordTarget>
        <patientRole>
          <id
            root="2.16.840.1.113883.19.5.99999.1"
            extension="AVERY-MIGRATION-0001"/>

          <patient>
            <name>
              <given>
                <xsl:value-of select="Patient/Given"/>
              </given>

              <family>
                <xsl:value-of select="Patient/Family"/>
              </family>
            </name>

            <administrativeGenderCode
              codeSystem="2.16.840.1.113883.5.1">

              <xsl:attribute name="code">
                <xsl:value-of
                  select="Patient/AdministrativeSex/@code"/>
              </xsl:attribute>

              <xsl:attribute name="displayName">
                <xsl:value-of
                  select="Patient/AdministrativeSex"/>
              </xsl:attribute>

            </administrativeGenderCode>

            <birthTime>
              <xsl:attribute name="value">
                <xsl:value-of select="Patient/BirthDate"/>
              </xsl:attribute>
            </birthTime>

          </patient>
        </patientRole>
      </recordTarget>

      <component>
        <structuredBody>

          <component>
            <section>

              <templateId
                root="2.16.840.1.113883.10.20.22.2.1.1"
                extension="2014-06-09"/>

              <code
                code="10160-0"
                codeSystem="2.16.840.1.113883.6.1"
                codeSystemName="LOINC"
                displayName="History of medication use"/>

              <title>Medications</title>

              <xsl:for-each select="Medications/Medication">

                <entry typeCode="DRIV">

                  <substanceAdministration
                    classCode="SBADM"
                    moodCode="EVN">

                    <templateId
                      root="2.16.840.1.113883.10.20.22.4.16"
                      extension="2014-06-09"/>

                    <id
                      root="2.16.840.1.113883.19.5.99999.2"/>

                    <statusCode code="completed"/>

                    <routeCode
                      codeSystem="2.16.840.1.113883.3.26.1.1"
                      codeSystemName="Medication Route FDA">

                      <xsl:attribute name="code">
                        <xsl:value-of select="Route/@code"/>
                      </xsl:attribute>

                      <xsl:attribute name="displayName">
                        <xsl:value-of select="Route"/>
                      </xsl:attribute>

                    </routeCode>

                    <doseQuantity>
                      <xsl:attribute name="value">
                        <xsl:value-of select="Dose"/>
                      </xsl:attribute>

                      <xsl:attribute name="unit">
                        <xsl:value-of select="Dose/@unit"/>
                      </xsl:attribute>
                    </doseQuantity>

                    <consumable>
                      <manufacturedProduct classCode="MANU">

                        <manufacturedMaterial>

                          <code
                            codeSystem="2.16.840.1.113883.6.88">

                            <xsl:attribute name="codeSystemName">
                              <xsl:value-of
                                select="CodeSystemName"/>
                            </xsl:attribute>

                            <xsl:attribute name="displayName">
                              <xsl:value-of
                                select="DisplayName"/>
                            </xsl:attribute>

                          </code>

                        </manufacturedMaterial>

                      </manufacturedProduct>
                    </consumable>

                  </substanceAdministration>

                </entry>

              </xsl:for-each>

            </section>
          </component>

          <component>
            <section>

              <templateId
                root="2.16.840.1.113883.10.20.22.2.22.1"
                extension="2015-08-01"/>

              <code
                code="46240-8"
                codeSystem="2.16.840.1.113883.6.1"
                codeSystemName="LOINC"
                displayName="Encounters"/>

              <title>Encounters</title>

              <xsl:for-each select="Encounters/Encounter">

                <entry typeCode="DRIV">

                  <encounter
                    classCode="ENC"
                    moodCode="EVN">

                    <templateId
                      root="2.16.840.1.113883.10.20.22.4.49"
                      extension="2015-08-01"/>

                    <code
                      code="185347001"
                      codeSystem="2.16.840.1.113883.6.96"
                      codeSystemName="SNOMED CT">

                      <xsl:attribute name="displayName">
                        <xsl:value-of select="Description"/>
                      </xsl:attribute>

                    </code>

                    <effectiveTime>
                      <xsl:attribute name="value">
                        <xsl:value-of select="EffectiveTime"/>
                      </xsl:attribute>
                    </effectiveTime>

                    <participant typeCode="LOC">
                      <participantRole classCode="SDLOC">
                        <playingEntity classCode="PLC">
                          <name>
                            <xsl:value-of select="Facility"/>
                          </name>
                        </playingEntity>
                      </participantRole>
                    </participant>

                  </encounter>

                </entry>

              </xsl:for-each>

            </section>
          </component>

        </structuredBody>
      </component>

    </ClinicalDocument>

  </xsl:template>

</xsl:stylesheet>
