# Flink 2.2.1, not 2.3: the Kafka and Avro-registry SQL connectors have no
# build for 2.3 yet (newest are flink-sql-connector-kafka 5.0.0-2.2 and
# flink-sql-avro-confluent-registry 2.2.1). Run the newest Flink your
# connectors actually support, not the newest Flink.
FROM flink:2.2.1-java17

ARG KAFKA_CONNECTOR=5.0.0-2.2
ARG AVRO_REGISTRY=2.2.1
ARG MAVEN=https://repo1.maven.org/maven2/org/apache/flink

RUN set -eux; \
    curl -fsSL -o /opt/flink/lib/flink-sql-connector-kafka.jar \
        "${MAVEN}/flink-sql-connector-kafka/${KAFKA_CONNECTOR}/flink-sql-connector-kafka-${KAFKA_CONNECTOR}.jar"; \
    curl -fsSL -o /opt/flink/lib/flink-sql-avro-confluent-registry.jar \
        "${MAVEN}/flink-sql-avro-confluent-registry/${AVRO_REGISTRY}/flink-sql-avro-confluent-registry-${AVRO_REGISTRY}.jar"; \
    chown flink:flink /opt/flink/lib/*.jar
