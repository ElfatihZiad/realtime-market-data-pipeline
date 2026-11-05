# Flink 2.1.3.
#
# The runtime version is set by whichever connector supports the narrowest
# range. In Phase 2 that was Kafka/Avro, which capped us at 2.2. Phase 3 adds
# Iceberg, whose newest Flink runtime is iceberg-flink-runtime-2.1 — so 2.1 it
# is, with the Kafka and Avro connectors moved to their matching 2.1 builds.
# See docs/adr/0010-flink-version-follows-connectors.md.
FROM flink:2.1.3-java17

ARG KAFKA_CONNECTOR=5.0.0-2.1
ARG AVRO_REGISTRY=2.1.2
ARG ICEBERG=1.11.0
# Iceberg's Flink connector wants org.apache.hadoop.conf.Configuration on the
# classpath even when no HDFS is involved — the catalog plumbing reaches for
# it. The Flink image bundles no Hadoop, so supply the shaded uber jar. It is
# old (Hadoop 2.8.3) but it is one file and nothing here actually talks to
# HDFS; it exists only to satisfy that import.
ARG SHADED_HADOOP=2.8.3-10.0
ARG ICEBERG_AWS=1.11.0
ARG FLINK_MAVEN=https://repo1.maven.org/maven2/org/apache/flink
ARG ICEBERG_MAVEN=https://repo1.maven.org/maven2/org/apache/iceberg

RUN set -eux; \
    curl -fsSL -o /opt/flink/lib/flink-sql-connector-kafka.jar \
        "${FLINK_MAVEN}/flink-sql-connector-kafka/${KAFKA_CONNECTOR}/flink-sql-connector-kafka-${KAFKA_CONNECTOR}.jar"; \
    curl -fsSL -o /opt/flink/lib/flink-sql-avro-confluent-registry.jar \
        "${FLINK_MAVEN}/flink-sql-avro-confluent-registry/${AVRO_REGISTRY}/flink-sql-avro-confluent-registry-${AVRO_REGISTRY}.jar"; \
    curl -fsSL -o /opt/flink/lib/iceberg-flink-runtime.jar \
        "${ICEBERG_MAVEN}/iceberg-flink-runtime-2.1/${ICEBERG}/iceberg-flink-runtime-2.1-${ICEBERG}.jar"; \
    curl -fsSL -o /opt/flink/lib/flink-shaded-hadoop-2-uber.jar \
        "${FLINK_MAVEN}/flink-shaded-hadoop-2-uber/${SHADED_HADOOP}/flink-shaded-hadoop-2-uber-${SHADED_HADOOP}.jar"; \
    curl -fsSL -o /opt/flink/lib/iceberg-aws-bundle.jar \
        "${ICEBERG_MAVEN}/iceberg-aws-bundle/${ICEBERG_AWS}/iceberg-aws-bundle-${ICEBERG_AWS}.jar"; \
    chown flink:flink /opt/flink/lib/*.jar

# The Prometheus reporter ships with Flink but sits in opt/, which is not on
# the classpath. Moving it into lib/ is what turns on :9249.
RUN cp /opt/flink/opt/flink-metrics-prometheus-*.jar /opt/flink/lib/
