import environ
import psycopg2
from psycopg2.extensions import connection
from redis import Redis
from app_common_python import LoadedConfig, isClowderEnabled
from confluent_kafka import Consumer, Producer
from minio import Minio
from prometheus_client import start_http_server
from typing import Optional


# Class for raising Clowder provider errors
class ProviderError(Exception):

    def __init__(self, message):
        self.message = message


class StarterHelper:
    """
    A helper class for the starter app, which provides information that can be
    printed out as well as connections to various providers.
    """
    def __init__(self):
        """
        Initializes the class.

        Raises
        ------
        ValueError
            If clowder is not enabled or if the config is not loaded.
        """
        if not isClowderEnabled():
            raise ValueError("😿Clowder is not enabled")
        self.environment = environ.Env()
        if LoadedConfig is None:
            raise ValueError("LoadedConfig is None, impossible to continue")

        self._init_db()
        self._init_in_memory_db()
        self._init_kafka()
        self._init_minio()
        self._init_cloudwatch()
        self._init_metrics()

    def _init_db(self):
        """
        Initializes the database. Called on initialization of the class.
        """
        # Asserts get rid of some typecheck warnings
        assert LoadedConfig is not None

        if LoadedConfig.database is None:
            self.database_enabled = False
            return

        self.database_enabled = True
        self.db_use_rds = False
        # TODO: Create connection using rdsCa
        if LoadedConfig.database.rdsCa:
            self.db_use_rds = True
            self.db_sslmode = self.environment.get_value("PGSSLMODE",
                                                         default="prefer")
            self.db_sslrootcert = LoadedConfig.rds_ca()
        self.db_name = LoadedConfig.database.name
        self.db_hostname = LoadedConfig.database.hostname
        self.db_port = LoadedConfig.database.port
        self.db_username = LoadedConfig.database.username
        self.db_password = LoadedConfig.database.password
        self.db_admin_username = LoadedConfig.database.adminUsername
        self.db_admin_password = LoadedConfig.database.adminPassword

    def _init_in_memory_db(self):
        """
        Initializes the in-memory database. Called on initialization of the
        class.
        """
        # Asserts get rid of some typecheck warnings
        assert LoadedConfig is not None
        if LoadedConfig.inMemoryDb is None:
            self.in_memory_db_enabled = False
            self.in_memory_db_host = self.environment.get_value(
                "REDIS_HOST", default="localhost")
            self.in_memory_db_port = self.environment.get_value("REDIS_PORT",
                                                                default="6379")
        else:
            self.in_memory_db_enabled = True
            self.in_memory_db_host = LoadedConfig.inMemoryDb.hostname
            self.in_memory_db_port = LoadedConfig.inMemoryDb.port
        self.default_redis_url = f"redis://{self.in_memory_db_host}:{self.in_memory_db_port}/0"

    def _init_kafka(self):
        """
        Initializes kafka. Called on initialization of the class.
        """
        assert LoadedConfig is not None
        if LoadedConfig.kafka is not None:
            kafka_broker = LoadedConfig.kafka.brokers[0]
            self.kafka_host = kafka_broker.hostname
            self.kafka_port = kafka_broker.port
            self.kafka_enabled = True
        else:
            # ? Should this ever be called if we're using Clowder or should we
            # ? just say kafka is disabled?
            self.kafka_enabled = False
            self.kafka_host = "localhost"
            self.kafka_port = "9092"
        self.kafka_server = f"{self.kafka_host}:{self.kafka_port}"

    def _init_minio(self):
        """
        Initializes object store. Called on initialization of the class.
        """
        assert LoadedConfig is not None
        # Minio
        if LoadedConfig.objectStore is None:
            self.object_store_enabled = False
        else:
            self.object_store_enabled = True
            self.object_store_hostname = LoadedConfig.objectStore.hostname
            self.object_store_port = LoadedConfig.objectStore.port
            self.object_store_tls = LoadedConfig.objectStore.tls
            self.object_store_access_key = LoadedConfig.objectStore.accessKey
            self.object_store_secret_key = LoadedConfig.objectStore.secretKey
            self.object_store_server = f"{self.object_store_hostname}:{self.object_store_port}"

    def _init_metrics(self):
        """
        Initializes metrics. Called on initialization of the class.
        """
        assert LoadedConfig is not None
        self.prometheus_started = False
        self.metrics_port = LoadedConfig.metricsPort

    def _init_cloudwatch(self):
        """
        Initializes cloudwatch. Called on initialization of the class.
        """
        assert LoadedConfig is not None
        if LoadedConfig.logging is None:
            self.cloudwatch_enabled = False
            return
        if LoadedConfig.logging.cloudwatch is None:
            self.cloudwatch_enabled = False
            return

        self.cloudwatch_enabled = True
        if self.environment.bool("CW_NULL_WORKAROUND", default=True):
            self.cw_aws_access_key_id = self.environment.get_value(
                "CW_AWS_ACCESS_KEY_ID", default=None)
            self.cw_aws_secret_access_key = self.environment.get_value(
                "CW_AWS_SECRET_ACCESS_KEY", default=None)
            self.cw_aws_region_name = self.environment.get_value(
                "CW_AWS_REGION", default="us-east-1")
            self.cw_log_group = self.environment.get_value(
                "CW_LOG_GROUP", default="platform-dev")
        else:
            cloudwatch = LoadedConfig.logging.cloudwatch
            self.cw_aws_access_key_id = cloudwatch.accessKeyId
            self.cw_aws_secret_access_key = cloudwatch.secretAccessKey
            self.cw_aws_region_name = cloudwatch.region
            self.cw_log_group = cloudwatch.logGroup

        self.cw_create_log_group = self.environment.bool("CW_CREATE_LOG_GROUP",
                                                         default=False)

    def print_all_info(self):
        """
        Prints the information about various providers, such as whether they
        are enabled. Providers include PostgreSQL, Kafka, Minio, CloudWatch,
        and Redis.
        """
        print("""\n\n
##############################################################################
#                                Clowder Info                                #
##############################################################################
    """)
        print("\n😸\tClowder is enabled")
        self.print_kafka_info()
        self.print_database_info()
        self.print_in_memory_db_info()
        self.print_cloudwatch_info()
        self.print_object_store_info()
        print("\n🐷\tThat's all, folks!")

    def print_kafka_info(self):
        """
        Prints out the kafka info
        """
        print("\n✍️\tKafka:")
        if not self.kafka_enabled:
            print("\t🚫 LoadedConfig.kafka is None")
        else:
            print(f"\t▪ Kafka Server: {self.kafka_server}")

    def print_cloudwatch_info(self):
        """
        Prints info about cloudwatch logging.
        """
        assert LoadedConfig is not None
        print("\n☁️\tCloudWatch:")
        if self.environment.bool("CW_NULL_WORKAROUND", default=True):
            print(f"\t▪ CW_AWS_ACCESS_KEY_ID: {self.cw_aws_access_key_id}")
            print(
                f"\t▪ CW_AWS_SECRET_ACCESS_KEY: {self.cw_aws_secret_access_key}"
            )
            print(f"\t▪ CW_AWS_REGION_NAME: {self.cw_aws_region_name}")
            print(f"\t▪ CW_LOG_GROUP: {self.cw_log_group}")
        elif LoadedConfig.logging is None:
            print("\t🚫 LoadedConfig.logging is None")
        elif LoadedConfig.logging.cloudwatch is None:
            print("\t🚫 LoadedConfig.logging.cloudwatch is None")
        else:
            print(f"\t▪ CW_AWS_ACCESS_KEY_ID: {self.cw_aws_access_key_id}")
            print(
                f"\t▪ CW_AWS_SECRET_ACCESS_KEY: {self.cw_aws_secret_access_key}"
            )
            print(f"\t▪ CW_AWS_REGION_NAME: {self.cw_aws_region_name}")
            print(f"\t▪ CW_LOG_GROUP: {self.cw_log_group}")
        print(f"\t▪ CW_CREATE_LOG_GROUP: {self.cw_create_log_group}")

    def print_database_info(self) -> None:
        """
        Prints info about the database.
        """
        print("\n🗄️\tDatabase:")
        if not self.database_enabled:
            print("\t🚫 LoadedConfig.database is None")
        else:
            print(f"\t▪ Host: {self.db_hostname}")
            print(f"\t▪ Port: {self.db_port}")
            print(f"\t▪ Database: {self.db_name}")
            print(f"\t▪ Username: {self.db_username}")
            print(f"\t▪ Password: {self.db_password}")
            print(f"\t▪ Admin Username: {self.db_admin_username}")
            print(f"\t▪ Admin Password: {self.db_admin_password}")

    def print_in_memory_db_info(self) -> None:
        """
        Prints info about the in-memory database.
        """
        assert LoadedConfig is not None
        print("\n💾\tIn-memory db:")
        if not self.in_memory_db_enabled:
            print("\t🚫 LoadedConfig.inMemoryDb is None")
        else:
            print(f"\t▪ Default redis url: {self.default_redis_url}")

    def print_object_store_info(self) -> None:
        """
        Prints info about the object store.
        """
        print("\n📦\tObject store:")
        if self.object_store_enabled:
            print(f'\t▪ Object store server: {self.object_store_server}')
            print(
                f'\t▪ Object store access key: {self.object_store_access_key}')
            print(
                f'\t▪ Object store secret key: {self.object_store_secret_key}')
            print(f'\t▪ Object store tls: {self.object_store_tls}')
        else:
            print("\t🚫 LoadedConfig.objectStore is None")

    def start_prometheus(self) -> None:
        """
        Starts the prometheus server on the port specified by the Clowder
        config.
        """
        assert LoadedConfig is not None
        assert LoadedConfig.metricsPort is not None
        if not self.prometheus_started:
            start_http_server(port=int(LoadedConfig.metricsPort))
            self.prometheus_started = True

    def database_conn(self,
                      autocommit: Optional[bool] = None
                      ) -> connection:
        """
        Returns a connection to the database specified by the Clowder config.

        Parameters
        ----------
        autocommit : Optional[bool], optional
            Whether the connection should autocommit, by default None.
            If `True`, enables autocommit. If `False`, disables autocommit.
            If `None`, does not change the autocommit state, which defaults to
            false.

        Returns
        -------
        psycopg2.extensions.connection
            A connection to the database specified by the Clowder config.

        Raises
        ------
        ProviderError
            If the database is not enabled in the Clowder config but this
            method is called.
        """
        try:
            if autocommit is not None:
                self._database_connection.autocommit = autocommit
            return self._database_connection
        except AttributeError as e:
            if self.database_enabled:
                self._database_connection = psycopg2.connect(
                    host=self.db_hostname,
                    port=self.db_port,
                    database=self.db_name,
                    user=self.db_username,
                    password=self.db_password)
                if autocommit is not None:
                    self._database_connection.autocommit = autocommit
                return self._database_connection
            raise ProviderError("Database is not enabled") from e

    def admin_database_conn(self,
                            autocommit: Optional[bool] = None
                            ) -> connection:
        """
        Returns an admin connection to the database specified by the Clowder config.

        Parameters
        ----------
        autocommit : Optional[bool], optional
            Whether the connection should autocommit, by default None.
            If `True`, enables autocommit. If `False`, disables autocommit.
            If `None`, does not change the autocommit state, which defaults to
            false.

        Returns
        -------
        psycopg2.extensions.connection
            A connection to the database specified by the Clowder config.

        Raises
        ------
        ProviderError
            If the database is not enabled in the Clowder config but this
            method is called.
        """
        try:
            if autocommit is not None:
                self._admin_database_connection.autocommit = autocommit
            return self._admin_database_connection
        except AttributeError as e:
            if self.database_enabled:
                self._admin_database_connection = psycopg2.connect(
                    host=self.db_hostname,
                    port=self.db_port,
                    database=self.db_name,
                    user=self.db_username,
                    password=self.db_password)
                if autocommit is not None:
                    self._admin_database_connection.autocommit = autocommit
                return self._admin_database_connection
            raise ProviderError("Database is not enabled") from e

    def object_store_conn(self) -> Minio:
        """
        Returns a connection to the object store specified by the Clowder config.

        Returns
        -------
        Minio
            A Minio connection that can be used to access the object store.

        Raises
        ------
        ProviderError
            If the object store is not enabled in the Clowder config but this
            method is called.
        """
        try:
            return self._minio_conn
        except AttributeError as e:
            if self.object_store_enabled:
                self._minio_conn = Minio(
                    self.object_store_server,
                    access_key=self.object_store_access_key,
                    secret_key=self.object_store_secret_key,
                    secure=False)
                return self._minio_conn
            raise ProviderError("Object store is not enabled") from e

    def kafka_consumer(self) -> Consumer:
        """
        Returns a Kafka consumer that can be used to consume messages from the
        Kafka server specified by the Clowder config.

        Returns
        -------
        Consumer
            A Kafka consumer

        Raises
        ------
        ProviderError
            If Kafka is not enabled in the Clowder config but this method is
            called.
        """
        try:
            return self._kafka_consumer_conn
        except AttributeError as e:
            if self.kafka_enabled:
                self._kafka_consumer_conn = Consumer({
                    "bootstrap.servers":
                    self.kafka_server,
                    "group.id":
                    __name__
                })
                return self._kafka_consumer_conn
            raise ProviderError("Kafka is not enabled") from e

    def kafka_producer(self) -> Producer:
        """
        Returns a Kafka producer that can be used to produce messages to the
        Kafka server specified by the Clowder config.

        Returns
        -------
        Producer
            A Kafka producer

        Raises
        ------
        ProviderError
            If Kafka is not enabled in the Clowder config but this method is
            called.
        """
        try:
            return self._kafka_producer_conn
        except AttributeError as e:
            if self.kafka_enabled:
                self._kafka_producer_conn = Producer({
                    "bootstrap.servers":
                    self.kafka_server,
                    "client.id":
                    __name__
                })
                return self._kafka_producer_conn
            raise ProviderError("Kafka is not enabled") from e

    def in_memory_db_conn(self) -> Redis:
        """
        Returns a connection to the in-memory databas`e specified by the Clowder
        config.

        Returns
        -------
        Redis
            A connection to the in-memory database

        Raises
        ------
        ProviderError
            If the in-memory database is not enabled in the Clowder config but
            this method is called.
        """
        try:
            return self._redis_conn
        except AttributeError as e:
            if self.in_memory_db_enabled:
                self._redis_conn = Redis(host=self.in_memory_db_host,
                                         port=self.in_memory_db_port)
                return self._redis_conn
            raise ProviderError("In-memory db is not enabled") from e
