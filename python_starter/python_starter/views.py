import os
import random
import threading
from datetime import datetime
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from app_common_python import KafkaTopics, LoadedConfig
from prometheus_client import Counter, Gauge

from . import starter_helper

scaffolding = starter_helper.StarterHelper()

UNSEEN_MESSAGES = Gauge("unseen_messages", "Number of unseen messages")
CONSUMED_MESSAGES = Counter("consumed_messages", "Number of consumed messages")
PRODUCED_MESSAGES = Counter("produced_messages", "Number of produced messages")
HEALTH_CALLS = Counter("health_calls", "Number of health calls")

MESSAGES = {}


# NOTE: this is intended to be used in production, a safer method should be used
# than saving the messages directly to memory.
def consume_messages():
    global MESSAGES
    consumer = scaffolding.kafka_consumer()
    consumer.subscribe(list(KafkaTopics))
    while True:
        messages = MESSAGES.copy()
        msg = consumer.poll(timeout=1.0)
        if msg is None:
            continue
        if msg.error():
            print(f"Consumer error: {msg.error()}")
            continue
        # message.timestamp() might be useful as well
        # also, msg.value() is a bytes object, not a string, so decode it
        topic, value = msg.topic(), msg.value().decode("utf-8")
        if topic not in messages:
            messages[topic] = []
        messages[topic].append(value)
        MESSAGES = messages
        CONSUMED_MESSAGES.inc()
        print(f"  Consumed message: {msg.value()}")


# NOTE: https://docs.djangoproject.com/en/4.0/ref/csrf/
# The approaches below (and in particular the `csrf_exempt` decorator) are not
# necessarily safe to be used in a production environment


# complementary to the consume_messages() function
def kafka_get(request) -> HttpResponse:
    global MESSAGES
    print(f"Copying messages {MESSAGES}")
    messages_copy = MESSAGES.copy()
    MESSAGES = {}
    UNSEEN_MESSAGES.dec(len(messages_copy))
    return JsonResponse(messages_copy)


def kafka_put(request) -> HttpResponse:
    """
    http://127.0.0.1:8000/kafka?message=hello
    """
    producer = scaffolding.kafka_producer()
    query_dict = request.GET
    request_data = query_dict.get("message", None)
    if request_data is None:
        return HttpResponse("No message provided", status=400)
    # This just gets the first key it can and uses that as the topic
    producer_topic = next(iter(KafkaTopics))
    producer.produce(producer_topic, request_data)
    print(f"Produced {request_data} on topic: '{producer_topic}'")
    producer.flush()
    PRODUCED_MESSAGES.inc()
    UNSEEN_MESSAGES.inc()
    return HttpResponse(f"In kafka_put() with request_data: {request_data}")


@csrf_exempt
def handle_kafka(request) -> HttpResponse:
    if request.method == 'GET':
        return kafka_get(request)
    elif request.method in ['POST', 'PUT']:
        return kafka_put(request)
    return HttpResponse("Invalid method", status_code=400)


# Generate a basic file to be used as a test file, and get them all
def minio_get(request) -> HttpResponse:
    """
    Handles GET requests to the /minio endpoint. Returns object data from Minio.
    """
    print("In minio_get()")
    if not scaffolding.object_store_enabled:
        return HttpResponse("Minio is not enabled")
    minio_client = scaffolding.object_store_conn()
    objects = list(minio_client.list_objects("example-bucket"))
    return JsonResponse({
        obj.object_name: {
            "size": obj.size,
            "last_modified": obj.last_modified,
        }
        for obj in objects
    })


def minio_put(request) -> HttpResponse:
    """
    Handles PUT and POST requests to the /minio endpoint. Adds example files
    to an example bucket called `testbucket` with the file name as the timestamp
    and the file contents as a string of random bits.
    """
    print("In minio_put()")
    if not scaffolding.object_store_enabled:
        return HttpResponse("Minio is not enabled")
    minio_client = scaffolding.object_store_conn()
    # Write a file containing a random string locally as an example for Minio
    current_time = datetime.now()
    with open(f"{current_time}.txt", "w") as f:
        f.write(str(random.getrandbits(1024)))
    if not minio_client.bucket_exists("example-bucket"):
        minio_client.make_bucket("example-bucket")
    # Upload the file to Minio
    minio_client.fput_object("example-bucket", f"{current_time}.txt",
                             f"{current_time}.txt")
    # Delete the temp file
    os.remove(f"{current_time}.txt")
    return HttpResponse(f"Inserted {current_time}.txt into Minio")


@csrf_exempt
def handle_minio(request) -> HttpResponse:
    if request.method == 'GET':
        return minio_get(request)
    elif request.method in ['POST', 'PUT']:
        return minio_put(request)
    return HttpResponse("Invalid method")


def redis_get(request) -> HttpResponse:
    """
    Handles GET requests to the /redis endpoint. Returns the value associated
    with the specified key. If the key does not exist, returns a 404.

    `key` is a required input to the request.
    """
    print("In redis_get()")
    if not scaffolding.in_memory_db_enabled:
        return HttpResponse("Redis is not enabled")
    query_dict = request.GET
    key = query_dict.get("key", None)
    if key is None:
        return HttpResponse("No key specified", 400)
    result = scaffolding.in_memory_db_conn().get(key)
    print(f"Redis result: {result}")
    if result is None:
        return HttpResponse("Key not found in database", 404)
    return HttpResponse(result)


def redis_put(request) -> HttpResponse:
    """
    Handles PUT and POST requests to the /redis endpoint. Adds a message to
    the specified key in the Redis database. If the key already exists, it is
    overwritten.

    `key` and `value` are required inputs to the request.
    """
    print("In redis_put()")

    query_dict = request.GET
    key = query_dict.get("key", None)
    if key is None:
        return HttpResponse("No key provided", 400)
    value = query_dict.get("value", None)
    if value is None:
        return HttpResponse("No value provided", 400)
    result = scaffolding.in_memory_db_conn().set(key, value)
    if not result:
        return HttpResponse("Failed to set properly", 500)
    return HttpResponse("Set {key} to {value}")


@csrf_exempt
def handle_redis(request) -> HttpResponse:
    if request.method == 'GET':
        return redis_get(request)
    elif request.method in ['POST', 'PUT']:
        return redis_put(request)
    return HttpResponse("Invalid method")


def postgres_get(request) -> HttpResponse:
    print("In postgres_get()")
    cursor = scaffolding.database_conn().cursor()
    SQL = "SELECT * FROM example_table;"
    cursor.execute(SQL)
    return JsonResponse(dict(cursor))


@csrf_exempt
def postgres_init_get(request) -> HttpResponse:
    print("In postgres_init_get()")
    cursor = scaffolding.database_conn().cursor()
    SQL = "SELECT * FROM init_container;"
    cursor.execute(SQL)
    return JsonResponse(dict(cursor))


def postgres_put(request) -> HttpResponse:
    """
    Handles PUT and POST requests to the /postgres endpoint. Inserts messages
    into the database.
    """
    print("In postgres_put()")
    cursor = scaffolding.database_conn().cursor()
    # This is the approach recommended by psycopg2
    # https://www.psycopg.org/docs/usage.html#the-problem-with-the-query-parameters
    SQL = "INSERT INTO example_table (message) VALUES (%s);"
    query_dict = request.GET
    message = (query_dict.get("message", None), )
    cursor.execute(SQL, message)
    return HttpResponse(f"Inserted message {message} into database")


@csrf_exempt
def feature_flag_get(request) -> HttpResponse:
    """
    Handles GET requests to the /featureflag endpoint. Returns the value of the
    specified feature flag. If the flag does not exist, returns False.

    `flag` is a required input to the request.
    """
    if request.method != 'GET':
        return HttpResponse("Invalid method", 400)
    print("In feature_flag_get()")
    query_dict = request.GET
    print("After query_dict")
    flag = query_dict.get("flag", None)
    print("After flag")
    if flag is None:
        return HttpResponse("No flag specified", 400)
    print("After flag not None check")
    connection = scaffolding.feature_flags_conn()
    print("Connection complete")
    result = connection.is_enabled(flag)
    print(f"Feature flag result: {result}")
    if result is None:
        return HttpResponse("Flag not found in database", 404)
    return HttpResponse(result)


@csrf_exempt
def handle_postgres(request) -> HttpResponse:
    if request.method == 'GET':
        return postgres_get(request)
    elif request.method in ['POST', 'PUT']:
        return postgres_put(request)
    return HttpResponse("Invalid method")


# /livez
@csrf_exempt
def liveness(request) -> HttpResponse:
    print("In liveness()")
    return HttpResponse("In liveness()")


# /readyz
@csrf_exempt
def readiness(request) -> HttpResponse:
    print("In readiness()")
    return HttpResponse("In readiness()")


# /healthz
@csrf_exempt
def health(request) -> HttpResponse:
    print(f"Request: {request}")
    print(f"Request type: {type(request)}")
    HEALTH_CALLS.inc()
    print("In health()")
    return HttpResponse("In health()")


def start_app() -> None:
    assert LoadedConfig is not None

    scaffolding.print_all_info()

    print(f"\n\n🚀\tStarter App started at: {datetime.now()}\n")
    # We need to have a thread for consume_messages() to run in the background
    CONSUMER_THREAD = threading.Thread(target=consume_messages)
    CONSUMER_THREAD.start()
    print("Started consumer thread")
    postgres_conn = scaffolding.database_conn(autocommit=True)
    print("Connected to Postgres")
    SQL = "CREATE TABLE IF NOT EXISTS example_table (id SERIAL PRIMARY KEY, message VARCHAR(255));"
    with postgres_conn.cursor() as cursor:
        cursor.execute(SQL)
    print("Created example_table")
    scaffolding.start_prometheus()
    print("Started prometheus")


# 0. dummy API for liveness and readiness probes ✅ (apparently clowder built-in)
# 1. Get simple API to send/receive messages through kafka ✅
#  - At some point, I need to convert from Flask to Django
# 2. get examples for each clowder provider:
#        Web - Finished ✅
#        Minio - Finished ✅
#        In-memory db - Finished ✅
#        Kafka - Finished ✅
#        Postgres - Finished ✅
#        Metrics - Finished ✅
#        InitContainer - Finished ✅
#        Feature Flags - Finished ✅
#        CronJob
#        CJI
# 3. Eventually be able to `oc process`/`oc apply` the starter app

# Build stuff
# Push to quay

# oc get service
# oc port-forward svc/starterapp-worker-service 8000
# oc port-forward svc/env-boot-minio 9000
