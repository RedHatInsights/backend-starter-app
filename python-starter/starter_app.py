from re import I
import time
from datetime import datetime

from app_common_python import LoadedConfig
from confluent_kafka import Consumer, Producer
from flask import Flask, jsonify, request
from prometheus_client import Info, Summary, start_http_server, Counter, Gauge

import clowder_info

clowder_info.print_info()
APP = Flask(__name__)
KAFKA_SERVER = clowder_info.KAFKA_SERVER
CONSUMER = Consumer({
    "bootstrap.servers": KAFKA_SERVER,
    "group.id": __name__,
    #  "auto.offset.reset": "earliest"
})
UNCONSUMED_MESSAGES = Gauge("unconsumed_messages",
                            "Number of unconsumed messages")
CONSUMED_MESSAGES = Counter("consumed_messages", "Number of consumed messages")
PRODUCED_MESSAGES = Counter("produced_messages", "Number of produced messages")
HEALTH_CALLS = Counter("health_calls", "Number of health calls")

if LoadedConfig is None:
    raise ValueError("LoadedConfig is None, impossible to continue")

print(f"\n\n🚀\tStarted at: {datetime.now()}\n")


def start_prometheus():
    # if Clowder is enabled then prometheus is always set
    start_http_server(port=clowder_info.PROMETHEUS_PORT)


@APP.route('/livez', methods=['GET', 'PUT', 'POST'])
def liveness():
    print("In liveness()")
    return "In liveness()"


@APP.route('/readyz', methods=['GET', 'PUT', 'POST'])
def readiness():
    print("In readiness()")
    return 'In readiness()'


@APP.route('/healthz', methods=['GET', 'PUT', 'POST'])
def health():
    HEALTH_CALLS.inc()
    print("In health()")
    return 'In health()'


@APP.route('/kafka', methods=['GET'])
def kafka_get():
    CONSUMER.subscribe([topic.name for topic in LoadedConfig.kafka.topics])
    messages = {}
    start = time.time()
    # For some reason Kafka will sometimes return 0 messages, so if we consume
    # a couple times until something shows up, we should get messages
    #? Is there a better way to do this?
    while time.time() < start + 3:
        # Let's consume upwards of 5000 messages
        current_messages = CONSUMER.consume(num_messages=5000, timeout=0.5)
        for message in current_messages:
            # message.timestamp() might be useful as well
            topic, value = message.topic(), message.value().decode('utf-8')
            if topic not in messages:
                messages[topic] = []
            messages[topic].append(value)
        if len(messages) > 0:
            break
    CONSUMER.unsubscribe()
    CONSUMED_MESSAGES.inc()
    UNCONSUMED_MESSAGES.dec()
    return messages


@APP.route('/kafka', methods=['PUT', 'POST'])
def kafka_put():
    producer = Producer({
        "bootstrap.servers": KAFKA_SERVER,
        "client.id": __name__
    })
    request_data = request.get_data()
    #? Get topic from the request?
    # LoadedConfig.kafka.topics contains a list of topics, maybe just pick one?
    producer.produce('test-topic', request_data)
    producer.flush()
    PRODUCED_MESSAGES.inc()
    UNCONSUMED_MESSAGES.inc()
    return f"In kafka_put() with request_data: {request_data}\n"


# @APP.route('/')
# def root():
#     print("In root()")
#     return 'In root()'


# 0. dummy API for liveness and readiness probes ✅ (apparently clowder built-in)
# 1. Get simple API to send/receive messages through kafka ✅
# 2. get examples for each clowder provider:
#        Kafka - Finished, sort of ✅
#              - Has a bug 🐛 (possibly in Flask?) The issue is that sometimes
#                the GET method returns {} instead of the messages we want
#        Web - Finished ✅
#        In-memory db - In progress 🔄
#        Postgres - In progress 🔄
#        Minio - In progress 🔄
#        Metrics - In progress 🔄
#        InitContainer
#        CronJob
#        CJI
#        Feature Flags - Unleash
# 3. Eventually be able to `oc process`/`oc apply` the starter app
if __name__ == '__main__':
    #? Figure out what's going on with prometheus:
    #? OSError: [Errno 98] Address already in use
    #? Presumably something else is already running on port 9000
    #? start_prometheus()
    PORT = LoadedConfig.publicPort
    print(f"PORT: {PORT}")
    APP.run(host='0.0.0.0', port=PORT, debug=True)
# Build stuff
# Push to quay

# oc get service
# oc port-forward svc/starterapp-worker-service 8000
# oc port-forward svc/env-boot-minio 9000
