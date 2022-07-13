import time
import random
from datetime import datetime
import os

from app_common_python import LoadedConfig, KafkaTopics
from confluent_kafka import Consumer, Producer
from flask import Flask, request
from minio import Minio
from prometheus_client import Counter, Gauge, start_http_server

import clowder_info

clowder_info.print_info()

print(f"\n\n🚀\tStarted at: {datetime.now()}\n")

APP = Flask(__name__)
KAFKA_SERVER = clowder_info.KAFKA_SERVER
CONSUMER = Consumer({
    "bootstrap.servers": KAFKA_SERVER,
    "group.id": __name__
    #  "auto.offset.reset": "earliest"
})

# This just gets the first key it can and uses that
PRODUCER_TOPIC = next(iter(KafkaTopics))
UNCONSUMED_MESSAGES = Gauge("unconsumed_messages",
                            "Number of unconsumed messages")
CONSUMED_MESSAGES = Counter("consumed_messages", "Number of consumed messages")
PRODUCED_MESSAGES = Counter("produced_messages", "Number of produced messages")
HEALTH_CALLS = Counter("health_calls", "Number of health calls")

if LoadedConfig is None:
    raise ValueError("LoadedConfig is None, impossible to continue")

if LoadedConfig.objectStore is not None:
    MINIO_CLIENT = Minio(clowder_info.MINIO_SERVER,
                         access_key=clowder_info.MINIO_ACCESSKEY,
                         secret_key=clowder_info.MINIO_SECRETKEY,
                         secure=False)
    MINIO_ENABLED = True
    if not MINIO_CLIENT.bucket_exists("testbucket"):
        MINIO_CLIENT.make_bucket("testbucket")
else:
    MINIO_ENABLED = False


def start_prometheus():
    # if Clowder is enabled then prometheus is always set
    print(f"Metrics port: {clowder_info.METRICS_PORT}")
    start_http_server(port=clowder_info.METRICS_PORT)


# Generate a basic file to be used as a test file, and get them all
@APP.route('/minio', methods=['GET'])
def minio_get():
    print("In minio_get")
    if not MINIO_ENABLED:
        return "Minio is not enabled"
    objects = list(MINIO_CLIENT.list_objects("testbucket"))
    print(objects)
    return "Printed info"


@APP.route('/minio', methods=['POST', 'PUT'])
def minio_put():
    print("In minio_put")
    if not MINIO_ENABLED:
        return "Minio is not enabled"
    # Write a file containing a random string locally as an example for Minio
    current_time = datetime.now()
    with open(f"{current_time}.txt", "w") as f:
        f.write(str(random.getrandbits(1024)))
    # Upload the file to Minio
    MINIO_CLIENT.fput_object("testbucket", f"{current_time}.txt",
                             f"{current_time}.txt")
    # Delete the temp file
    os.remove(f"{current_time}.txt")
    return "OK"


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
    consumer_topics = list(KafkaTopics)
    print(f"Consumer topics: {consumer_topics}")
    CONSUMER.subscribe(consumer_topics)
    messages = {}
    start = time.time()
    # For some reason Kafka will sometimes return 0 messages, so if we consume
    # a couple times until something shows up, we should get messages
    # while time.time() < start + 5:
    # Let's consume upwards of 5000 messages
    # * Tried timeout as long as 60 seconds, still not working as intended
    # * But maybe it's just because kafka is weird and groupID overlap and such
    # ? Possibly reach out to Chris Mitchell per Ben
    print("Starting loop")
    while time.time() < start + 2.5:
        print("\tIn loop")
        current_messages = CONSUMER.consume(num_messages=5000, timeout=0.25)
        print(f"\tCurrent Messages: {current_messages}")
        for message in current_messages:
            print(f"\t\tMessage: {message}")
            # message.timestamp() might be useful as well
            topic, value = message.topic(), message.value().decode('utf-8')

            if topic not in messages:
                messages[topic] = []
            messages[topic].append(value)
        if len(messages) > 0:
            print(f"Messages: {messages}")
            break
    print("Out of loop")
    CONSUMER.unsubscribe()
    CONSUMED_MESSAGES.inc()
    UNCONSUMED_MESSAGES.dec()
    print(f"Messages: {messages}")
    return messages


@APP.route('/kafka', methods=['PUT', 'POST'])
def kafka_put():
    producer = Producer({
        "bootstrap.servers": KAFKA_SERVER,
        "client.id": __name__
    })
    request_data = request.get_data()
    print(f"Produced {request_data} on topic: '{PRODUCER_TOPIC}'")
    producer.produce(PRODUCER_TOPIC, request_data)
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
#        Minio - In progress 🔄
#        In-memory db - In progress 🔄
#        Postgres - In progress 🔄
#        Metrics - In progress 🔄
#        InitContainer
#        CronJob
#        CJI
#        Feature Flags - Unleash
# 3. Eventually be able to `oc process`/`oc apply` the starter app
if __name__ == '__main__':
    # ? Clowder defaults to port 9000 for metrics, but this is raised:
    # ? OSError: [Errno 98] Address already in use
    # ? How should we deal with the conflict?
    # ? Reach out to Pete
    # start_prometheus()
    PORT = LoadedConfig.publicPort
    print(f"public port: {PORT}")
    APP.run(host='0.0.0.0', port=PORT, debug=True)
# Build stuff
# Push to quay

# oc get service
# oc port-forward svc/starterapp-worker-service 8000
# oc port-forward svc/env-boot-minio 9000
