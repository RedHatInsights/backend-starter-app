import os
import random
import threading
import time
from datetime import datetime

import psycopg2
import redis
from app_common_python import KafkaTopics, LoadedConfig
from confluent_kafka import Consumer, Producer
from flask import Flask, make_response, request
from minio import Minio
from prometheus_client import Counter, Gauge, start_http_server

import clowder_info

clowder_info.print_info()

print(f"\n\n🚀\tStarted at: {datetime.now()}\n")

if LoadedConfig is None:
    raise ValueError("LoadedConfig is None, impossible to continue")

APP = Flask(__name__)
KAFKA_SERVER = clowder_info.KAFKA_SERVER
CONSUMER = Consumer({"bootstrap.servers": KAFKA_SERVER, "group.id": __name__})

# This just gets the first key it can and uses that
PRODUCER_TOPIC = next(iter(KafkaTopics))
UNCONSUMED_MESSAGES = Gauge("unconsumed_messages",
                            "Number of unconsumed messages")
CONSUMED_MESSAGES = Counter("consumed_messages", "Number of consumed messages")
PRODUCED_MESSAGES = Counter("produced_messages", "Number of produced messages")
HEALTH_CALLS = Counter("health_calls", "Number of health calls")

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

REDIS_CONN = redis.Redis(host=clowder_info.REDIS_HOST,
                         port=clowder_info.REDIS_PORT)

# TODO: Add checking to this
# pg_options = clowder_info.db_options["OPTIONS"]
# POSTGRES_CONN = psycopg2.connect(
#     host=pg_options['hostname'],
#     port=pg_options['port'],
#     database="suppliers",
#     user="postgres",
#     password="Abcd1234"
#     )


def start_prometheus():
    # if Clowder is enabled then prometheus is always set
    print(f"Metrics port: {clowder_info.METRICS_PORT}")
    start_http_server(port=clowder_info.METRICS_PORT)
    print("Prometheus server started")


# Generate a basic file to be used as a test file, and get them all
@APP.route('/minio', methods=['GET'])
def minio_get():
    """
    Handles GET requests to the /minio endpoint. Returns object data from Minio.
    """
    print("In minio_get")
    if not MINIO_ENABLED:
        return "Minio is not enabled"
    objects = list(MINIO_CLIENT.list_objects("testbucket"))
    return {
        obj.object_name: {
            "size": obj.size,
            "last_modified": obj.last_modified,
        }
        for obj in objects
    }


@APP.route('/minio', methods=['POST', 'PUT'])
def minio_put():
    """
    Handles PUT and POST requests to the /minio endpoint. Adds example files
    to an example bucket called `testbucket` with the file name as the timestamp
    and the file contents as a string of random bits.
    """
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


@APP.route('/redis', methods=['GET'])
def redis_get():
    """
    Handles GET requests to the /redis endpoint. Returns the value associated
    with the specified key. If the key does not exist, returns a 404.

    `key` is a required input to the request.
    """
    print("In redis_get()")
    key = request.args.get("key")
    if key is None:
        return make_response("No key specified", 400)
    result = REDIS_CONN.get(key)
    print(f"Redis result: {result}")
    if result is None:
        return make_response("Key not found in database", 404)
    return result


@APP.route('/redis', methods=['POST', 'PUT'])
def redis_put():
    """
    Handles PUT and POST requests to the /redis endpoint. Adds a message to
    the specified key in the Redis database. If the key already exists, it is
    overwritten.

    `key` and `value` are required inputs to the request.
    """
    print("In redis_put()")
    key = request.args.get("key")
    if key is None:
        return make_response("No key provided", 400)
    value = request.args.get("value")
    if value is None:
        return make_response("No value provided", 400)
    result = REDIS_CONN.set(key, value)
    if not result:
        return make_response("Failed to set properly", 500)
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


MESSAGES = {}


# TODO: Replace this function with one that pushes to Postgres
# That would be much safer than this temp approach
def consume_messages():
    global MESSAGES
    CONSUMER.subscribe(list(KafkaTopics))
    while True:
        messages = MESSAGES.copy()
        msg = CONSUMER.poll(timeout=1.0)
        if msg is None:
            continue
        if msg.error():
            print(f"Consumer error: {msg.error()}")
            continue
        # message.timestamp() might be useful as well
        topic, value = msg.topic(), msg.value().decode('utf-8')
        if topic not in messages:
            messages[topic] = []
        messages[topic].append(value)
        MESSAGES = messages
        UNCONSUMED_MESSAGES.dec()
        CONSUMED_MESSAGES.inc()
        print(f"  Consumed message: {msg.value()}")


# TODO: Replace this function with one that pulls from Postgres
# complementary to the consume_messages() function
@APP.route('/kafka', methods=['GET'])
def kafka_get():
    global MESSAGES
    print(f"Copying messages {MESSAGES}")
    messages_copy = MESSAGES.copy()
    MESSAGES = {}
    return messages_copy


@APP.route('/kafka', methods=['PUT', 'POST'])
def kafka_put():
    producer = Producer({
        "bootstrap.servers": KAFKA_SERVER,
        "client.id": __name__
    })
    request_data = request.get_data()
    producer.produce(PRODUCER_TOPIC, request_data)
    print(f"Produced {request_data} on topic: '{PRODUCER_TOPIC}'")
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
#  - At some point, I need to convert from Flask to Django
# 2. get examples for each clowder provider:
#        Web - Finished ✅
#        Minio - In progress ✅
#        In-memory db - In progress ✅
#        Kafka - In progress 🔄
#        Postgres - In progress 🔄
#        Metrics - In progress 🔄
#        InitContainer
#        CronJob
#        CJI
#        Feature Flags - Unleash
# 3. Eventually be able to `oc process`/`oc apply` the starter app

# Current goals:
# - Figure out connection to postgres
#   It looks like insights-core, vmaas, and insights-host-inventory all have
#   references to psycopg2
# - Get example of redis
if __name__ == '__main__':
    # We need to have a thread for consume_messages() to run in the background

    CONSUMER_THREAD = threading.Thread(target=consume_messages)
    CONSUMER_THREAD.start()

    start_prometheus()
    PORT = LoadedConfig.publicPort
    print(f"public port: {PORT}")
    APP.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)

# Build stuff
# Push to quay

# oc get service
# oc port-forward svc/starterapp-worker-service 8000
# oc port-forward svc/env-boot-minio 9000
