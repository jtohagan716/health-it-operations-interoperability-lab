FROM orthancteam/orthanc@sha256:ffdfa1141b6b89a631c10d5ac612e18b934d601c3501e73b597bd700ecfd4004

ARG WORKLISTS_PLUGIN_VERSION=0.9.2

ADD --checksum=sha256:9bcfcd01bf889a95f740afd0452e689367d6ec10e9c3ca2a9e9c1ecb4d8b7960 \
    https://orthanc.uclouvain.be/downloads/linux-standard-base/orthanc-worklists/${WORKLISTS_PLUGIN_VERSION}/libOrthancWorklists.so \
    /usr/share/orthanc/plugins/libOrthancWorklists.so

RUN chmod 0555 /usr/share/orthanc/plugins/libOrthancWorklists.so

LABEL org.opencontainers.image.title="Interop Lab Orthanc with Worklists"
LABEL org.opencontainers.image.description="Pinned Orthanc 1.13.0 with Orthanc Worklists 0.9.2"
LABEL org.opencontainers.image.version="1.13.0-worklists-0.9.2"
LABEL org.opencontainers.image.source="https://orthanc.uclouvain.be/"
