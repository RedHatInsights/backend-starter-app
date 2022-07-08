from app_common_python import LoadedConfig, isClowderEnabled
import environ

#? should we assume clowder is always enabled and raise an error if not?
CLOWDER_ENABLED = isClowderEnabled()
ENVIRONMENT = environ.Env()

if LoadedConfig is None:
    raise ValueError("\n🚫\tLoadedConfig is None, impossible to continue")

# Kafka
if CLOWDER_ENABLED and LoadedConfig.kafka is not None:
    kafka_broker = LoadedConfig.kafka.brokers[0]
    KAFKA_HOST = kafka_broker.hostname
    KAFKA_PORT = kafka_broker.port
    KAFKA_SERVER = f"{KAFKA_HOST}:{KAFKA_PORT}"
else:
    KAFKA_HOST = "localhost"
    KAFKA_PORT = "9092"
    KAFKA_SERVER = f"{KAFKA_HOST}:{KAFKA_PORT}"

# Database
if LoadedConfig.database is None:
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
# input Host, Port, User, Password into db_options
if LoadedConfig.database is not None:
    db_options["OPTIONS"]["hostname"] = LoadedConfig.database.hostname
    db_options["OPTIONS"]["port"] = LoadedConfig.database.port
    db_options["OPTIONS"]["username"] = LoadedConfig.database.username
    db_options["OPTIONS"]["password"] = LoadedConfig.database.password
    #? add adminUsername or adminPassword?



# in-memory db
if CLOWDER_ENABLED and LoadedConfig.inMemoryDb is not None:
    REDIS_HOST = LoadedConfig.inMemoryDb.hostname
    REDIS_PORT = LoadedConfig.inMemoryDb.port
    DEFAULT_REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
else:
    REDIS_HOST = ENVIRONMENT.get_value("REDIS_HOST", default="localhost")
    REDIS_PORT = ENVIRONMENT.get_value("REDIS_PORT", default="6379")
    DEFAULT_REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"

# CloudWatch
if CLOWDER_ENABLED and not ENVIRONMENT.bool("CW_NULL_WORKAROUND",
                                            default=True):
    CW_AWS_ACCESS_KEY_ID = LoadedConfig.logging.cloudwatch.accessKeyId
    CW_AWS_SECRET_ACCESS_KEY = LoadedConfig.logging.cloudwatch.secretAccessKey
    CW_AWS_REGION_NAME = LoadedConfig.logging.cloudwatch.region
    CW_LOG_GROUP = LoadedConfig.logging.cloudwatch.logGroup
else:
    CW_AWS_ACCESS_KEY_ID = ENVIRONMENT.get_value("CW_AWS_ACCESS_KEY_ID",
                                                 default=None)
    CW_AWS_SECRET_ACCESS_KEY = ENVIRONMENT.get_value(
        "CW_AWS_SECRET_ACCESS_KEY", default=None)
    CW_AWS_REGION_NAME = ENVIRONMENT.get_value("CW_AWS_REGION",
                                               default="us-east-1")
    CW_LOG_GROUP = ENVIRONMENT.get_value("CW_LOG_GROUP",
                                         default="platform-dev")

CW_CREATE_LOG_GROUP = ENVIRONMENT.bool("CW_CREATE_LOG_GROUP", default=False)

# Minio
if LoadedConfig.objectStore is not None:
    MINIO_HOSTNAME = LoadedConfig.objectStore.hostname
    MINIO_PORT = LoadedConfig.objectStore.port
    MINIO_TLS = LoadedConfig.objectStore.tls
    MINIO_ACCESSKEY = LoadedConfig.objectStore.accessKey
    MINIO_SECRETKEY = LoadedConfig.objectStore.secretKey
    MINIO_SERVER = f"{MINIO_HOSTNAME}:{MINIO_PORT}"\

# Prometheus
PROMETHEUS_PORT = LoadedConfig.metricsPort


def print_info():
    print("""\n\n
##############################################################################
                            Running starter app
##############################################################################
    """)

    if CLOWDER_ENABLED:
        print("\n😸\tClowder is enabled")
    else:
        print("\n😿\tClowder is disabled")

    if LoadedConfig is None:
        raise ValueError("\n🚫\tLoadedConfig is None, impossible to continue")

    print("\n✍️\tKafka:")
    if CLOWDER_ENABLED:
        if LoadedConfig.kafka is None:
            print("\t  🚫 LoadedConfig.kafka is None")
        else:
            print(f"\t▪ KAFKA_SERVER: {KAFKA_SERVER}")
    else:
        print(f"\t▪ KAFKA_SERVER: {KAFKA_SERVER}")

    print("\n🗄️\tDatabase:")
    # Database stuff
    if LoadedConfig.database is None:
        print("\t🚫 LoadedConfig.database is None")
    print(f"\t▪ db_options: {db_options}")

    print("\n💾\tIn-memory db:")
    if CLOWDER_ENABLED:
        if LoadedConfig.inMemoryDb is None:
            print("\t🚫 LoadedConfig.inMemoryDb is None")
        else:
            print(f"\t▪ Default redis url: {DEFAULT_REDIS_URL}")
    else:
        print(f"\t▪ Default redis url: {DEFAULT_REDIS_URL}")

    print("\n☁️\tCloudWatch:")
    # CW settings
    if CLOWDER_ENABLED:
        if ENVIRONMENT.bool("CW_NULL_WORKAROUND", default=True):
            print(f"\t▪ CW_AWS_ACCESS_KEY_ID: {CW_AWS_ACCESS_KEY_ID}")
            print(f"\t▪ CW_AWS_SECRET_ACCESS_KEY: {CW_AWS_SECRET_ACCESS_KEY}")
            print(f"\t▪ CW_AWS_REGION_NAME: {CW_AWS_REGION_NAME}")
            print(f"\t▪ CW_LOG_GROUP: {CW_LOG_GROUP}")
        elif LoadedConfig.logging is None:
            print("\t🚫 LoadedConfig.logging is None")
        elif LoadedConfig.logging.cloudwatch is None:
            print("\t🚫 LoadedConfig.logging.cloudwatch is None")
        else:
            print(f"\t▪ CW_AWS_ACCESS_KEY_ID: {CW_AWS_ACCESS_KEY_ID}")
            print(f"\t▪ CW_AWS_SECRET_ACCESS_KEY: {CW_AWS_SECRET_ACCESS_KEY}")
            print(f"\t▪ CW_AWS_REGION_NAME: {CW_AWS_REGION_NAME}")
            print(f"\t▪ CW_LOG_GROUP: {CW_LOG_GROUP}")
    else:
        print(f"\t▪ CW_AWS_ACCESS_KEY_ID: {CW_AWS_ACCESS_KEY_ID}")
        print(f"\t▪ CW_AWS_SECRET_ACCESS_KEY: {CW_AWS_SECRET_ACCESS_KEY}")
        print(f"\t▪ CW_AWS_REGION: {CW_AWS_REGION_NAME}")
        print(f"\t▪ CW_LOG_GROUP: {CW_LOG_GROUP}")

    print(f"\t▪ CW_CREATE_LOG_GROUP: {CW_CREATE_LOG_GROUP}")

    # If clowder is enabled we should grab the s3 connection info in addition
    print("\n📦\tMinio:")
    if LoadedConfig.objectStore is not None:
        print(f'\t▪ Minio server: {MINIO_SERVER}')
        print(f'\t▪ Minio access key: {MINIO_ACCESSKEY}')
        print(f'\t▪ Minio secret key: {MINIO_SECRETKEY}')
        print(f'\t▪ Minio tls: {MINIO_TLS}')
    else:
        print("\t🚫 LoadedConfig.objectStore is None")

    print("\n📈\tPrometheus:")
    print(f"\t▪ Prometheus port: {PROMETHEUS_PORT}")

    print("\n🐷\tThat's all, folks!")