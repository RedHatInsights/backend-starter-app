from kafka import KafkaProducer
import random
import time
from app_common_python import LoadedConfig, isClowderEnabled
import environ
from os import listdir


print("""\n\n
##############################################################################
                             Running starter app
##############################################################################
""")
CLOWDER_ENABLED = isClowderEnabled()
if CLOWDER_ENABLED:
    print("\n😸\tClowder is enabled")
else:
    print("\n😿\tClowder is disabled")

# I don't know why we're going up 3 directory levels, since
# `ROOT_DIR = "/"` should work just fine I'd think?
ROOT_DIR = environ.Path(__file__) - 3
# print(f"ROOT_DIR: {ROOT_DIR}")


if LoadedConfig is None:
    raise ValueError("\n🚫\tLoadedConfig is None, impossible to continue")

ENVIRONMENT = environ.Env()

print("\n✍️\tKafka:")
if CLOWDER_ENABLED:
    if LoadedConfig.kafka is None:
        print("\t  🚫 LoadedConfig.kafka is None")
    else:
        kafka_broker = LoadedConfig.kafka.brokers[0]
        KAFKA_HOST = kafka_broker.hostname
        KAFKA_PORT = kafka_broker.port
        KAFKA_SERVER = f"{KAFKA_HOST}:{KAFKA_PORT}"
        print(f"\t▪ KAFKA_SERVER: {KAFKA_SERVER}")
else:
    KAFKA_HOST = "localhost"
    KAFKA_PORT = "9092"
    KAFKA_SERVER = f"{KAFKA_HOST}:{KAFKA_PORT}"
    print(f"\t▪ KAFKA_SERVER: {KAFKA_SERVER}")

print("\n🗄️\tDatabase:")
# Database stuff
if LoadedConfig.database is None:
    print("\t🚫 LoadedConfig.database is None")
    db_options = {}
elif LoadedConfig.database.rdsCa:
    db_options = {
        "OPTIONS": {
            "sslmode": ENVIRONMENT.get_value("PGSSLMODE", default="prefer"),
            "sslrootcert": LoadedConfig.rds_ca(),
        }
    }
else:
    db_options = {}
print(f"\t▪ db_options: {db_options}")

print("\n💾\tIn-memory db:")
if CLOWDER_ENABLED:
    if LoadedConfig.inMemoryDb is None:
        print("\t🚫 LoadedConfig.inMemoryDb is None")
    else:
        REDIS_HOST = LoadedConfig.inMemoryDb.hostname
        REDIS_PORT = LoadedConfig.inMemoryDb.port
        DEFAULT_REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
        print(f"\t▪ Default redis url: {DEFAULT_REDIS_URL}")
else:
    REDIS_HOST = ENVIRONMENT.get_value("REDIS_HOST", default="localhost")
    REDIS_PORT = ENVIRONMENT.get_value("REDIS_PORT", default="6379")
    DEFAULT_REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
    print(f"\t▪ Default redis url: {DEFAULT_REDIS_URL}")



print("\n☁️\tCloudWatch:")
# CW settings
if CLOWDER_ENABLED:
    if ENVIRONMENT.bool("CW_NULL_WORKAROUND", default=True):
        CW_AWS_ACCESS_KEY_ID = None
        CW_AWS_SECRET_ACCESS_KEY = None
        CW_AWS_REGION_NAME = None
        CW_LOG_GROUP = None
        print(f"\t▪ CW_AWS_ACCESS_KEY_ID: {CW_AWS_ACCESS_KEY_ID}")
        print(f"\t▪ CW_AWS_SECRET_ACCESS_KEY: {CW_AWS_SECRET_ACCESS_KEY}")
        print(f"\t▪ CW_AWS_REGION_NAME: {CW_AWS_REGION_NAME}")
        print(f"\t▪ CW_LOG_GROUP: {CW_LOG_GROUP}")
    elif LoadedConfig.logging is None:
        print("\t🚫 LoadedConfig.logging is None")
    elif LoadedConfig.logging.cloudwatch is None:
        print("\t🚫 LoadedConfig.logging.cloudwatch is None")
    else:
        CW_AWS_ACCESS_KEY_ID = LoadedConfig.logging.cloudwatch.accessKeyId
        CW_AWS_SECRET_ACCESS_KEY = LoadedConfig.logging.cloudwatch.secretAccessKey
        CW_AWS_REGION_NAME = LoadedConfig.logging.cloudwatch.region
        CW_LOG_GROUP = LoadedConfig.logging.cloudwatch.logGroup
        print(f"\t▪ CW_AWS_ACCESS_KEY_ID: {CW_AWS_ACCESS_KEY_ID}")
        print(f"\t▪ CW_AWS_SECRET_ACCESS_KEY: {CW_AWS_SECRET_ACCESS_KEY}")
        print(f"\t▪ CW_AWS_REGION_NAME: {CW_AWS_REGION_NAME}")
        print(f"\t▪ CW_LOG_GROUP: {CW_LOG_GROUP}")
else:
    print("\t🚫 Clowder is disabled")
    CW_AWS_ACCESS_KEY_ID = ENVIRONMENT.get_value("CW_AWS_ACCESS_KEY_ID",
                                                 default=None)
    CW_AWS_SECRET_ACCESS_KEY = ENVIRONMENT.get_value(
        "CW_AWS_SECRET_ACCESS_KEY", default=None)
    CW_AWS_REGION = ENVIRONMENT.get_value("CW_AWS_REGION", default="us-east-1")
    CW_LOG_GROUP = ENVIRONMENT.get_value("CW_LOG_GROUP",
                                         default="platform-dev")
    print(f"\t▪ CW_AWS_ACCESS_KEY_ID: {CW_AWS_ACCESS_KEY_ID}")
    print(f"\t▪ CW_AWS_SECRET_ACCESS_KEY: {CW_AWS_SECRET_ACCESS_KEY}")
    print(f"\t▪ CW_AWS_REGION: {CW_AWS_REGION}")
    print(f"\t▪ CW_LOG_GROUP: {CW_LOG_GROUP}")

CW_CREATE_LOG_GROUP = ENVIRONMENT.bool("CW_CREATE_LOG_GROUP", default=False)

# If clowder is enabled we should grab the s3 connection info in addition
print("\n📦\tMINIO:")
if LoadedConfig.objectStore is None:
    print("\t🚫 LoadedConfig.objectStore is None")
else:
    MINIO_HOSTNAME = LoadedConfig.objectStore.hostname
    MINIO_PORT = LoadedConfig.objectStore.port
    MINIO_TLS = LoadedConfig.objectStore.tls
    MINIO_ACCESSKEY = LoadedConfig.objectStore.accessKey
    MINIO_SECRETKEY = LoadedConfig.objectStore.secretKey
    MINIO_SERVER = f"{MINIO_HOSTNAME}:{MINIO_PORT}"
    print(f'\t▪ Minio server: {MINIO_SERVER}')
    print(f'\t▪ Minio access key: {MINIO_ACCESSKEY}')
    print(f'\t▪ Minio secret key: {MINIO_SECRETKEY}')
    print(f'\t▪ Minio tls: {MINIO_TLS}')


print("\n🐷\tThat's all, folks!")
# producer = KafkaProducer(bootstrap_servers=KAFKA_SERVER)
# for _ in range(20):
#     num = random.randint(0, 100)
#     numstr = str(num).encode('utf-8')
#     producer.send('quickstart-events', bytes(numstr))
#     time.sleep(1)

# 0. Get django running for simple API to send/receive messages through kafka
# 0.1. Do file stuff through django
# 1. dummy API for liveness and readiness probes
# 2. get examples for each clowder provider:
#        In-memory db ✅
#        CronJob
#        CJI
#        Feature Flags
#        Web
#        Metrics
#        InitContainer
# 3. Eventually be able to `oc process`/`oc apply` the starter app

# Build stuff
# Push to quay
while True:
    time.sleep(1)
