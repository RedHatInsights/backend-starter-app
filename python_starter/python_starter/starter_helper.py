import environ
import psycopg2
from psycopg2.extensions import connection
from redis import Redis
from app_common_python import LoadedConfig, isClowderEnabled
from confluent_kafka import Consumer, Producer
from minio import Minio
from prometheus_client import start_http_server
from requests.exceptions import InvalidSchema
from typing import Optional
from UnleashClient import UnleashClient


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
            If clowder is not enabled, the config is not loaded, or there is
            no metadata for the app.
        """
        if not isClowderEnabled():
            raise ValueError("😿Clowder is not enabled")
        self.environment = environ.Env()
        if LoadedConfig is None:
            raise ValueError("LoadedConfig is None, impossible to continue")
        if LoadedConfig.metadata is None:
            raise ValueError(
                "Please check that the Clowder config file contains a section "
                "for metadata and that a name is specified within the metadata")

        self.app_name = LoadedConfig.metadata.name
        self._init_db()
        self._init_in_memory_db()
        self._init_kafka()
        self._init_minio()
        self._init_cloudwatch()
        self._init_metrics()
        self._init_feature_flags()

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
        self.db_sslmode = None
        self.db_sslrootcert = None
        if LoadedConfig.database.rdsCa:
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
            host = self.in_memory_db_host = self.environment.get_value(
                "REDIS_HOST", default="localhost")
            port = self.in_memory_db_port = self.environment.get_value(
                "REDIS_PORT", default="6379")
        else:
            self.in_memory_db_enabled = True
            host = self.in_memory_db_host = LoadedConfig.inMemoryDb.hostname
            port = self.in_memory_db_port = LoadedConfig.inMemoryDb.port
        self.default_redis_url = f"redis://{host}:{port}/0"

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
            self.kafka_server = f"{self.kafka_host}:{self.kafka_port}"
        else:
            self.kafka_enabled = False

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
            host = self.object_store_hostname = LoadedConfig.objectStore.hostname
            port = self.object_store_port = LoadedConfig.objectStore.port
            self.object_store_tls = LoadedConfig.objectStore.tls
            self.object_store_access_key = LoadedConfig.objectStore.accessKey
            self.object_store_secret_key = LoadedConfig.objectStore.secretKey
            self.object_store_server = f"{host}:{port}"

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

    def _init_feature_flags(self):
        """
        Initializes feature flags. Called on initialization of the class.
        """
        assert LoadedConfig is not None
        if LoadedConfig.featureFlags is None:
            self.feature_flags_enabled = False
            return

        self.feature_flags_enabled = True
        ff = LoadedConfig.featureFlags
        self.feature_flags_client_access_token = ff.clientAccessToken
        # LoadedConfig.featureFlags.scheme.valueAsString() requires an enum, but
        # LoadedConfig.featureFlags.scheme is an Enum
        scheme = ff.scheme.valueAsString(ff.scheme)
        self.feature_flags_url = f"{scheme}://{ff.hostname}:{ff.port}/api"

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

    def database_conn(self, autocommit: Optional[bool] = None) -> connection:
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
            # Set the autocommit state if it was specified
            if autocommit is not None:
                self._database_connection.autocommit = autocommit
            # Attempt to return cached connection
            return self._database_connection
        # If cached connection is not available, create a new one
        except AttributeError as e:
            # But only if the database is enabled
            if self.database_enabled:
                self._database_connection = psycopg2.connect(
                    host=self.db_hostname,
                    port=self.db_port,
                    database=self.db_name,
                    user=self.db_username,
                    password=self.db_password,
                    sslmode=self.db_sslmode,
                    sslrootcert=self.db_sslrootcert)
                # On connection creation, set the autocommit state if specified
                if autocommit is not None:
                    self._database_connection.autocommit = autocommit
                return self._database_connection
            raise ProviderError("Database is not enabled") from e

    def admin_database_conn(self,
                            autocommit: Optional[bool] = None) -> connection:
        """
        Returns an admin connection to the database specified by the Clowder
        config.

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
            # Set the autocommit state if it was specified
            if autocommit is not None:
                self._admin_database_connection.autocommit = autocommit
            # Attempt to return cached connection
            return self._admin_database_connection
        # If cached connection is not available, create a new one
        except AttributeError as e:
            # But only if the database is enabled
            if self.database_enabled:
                self._admin_database_connection = psycopg2.connect(
                    host=self.db_hostname,
                    port=self.db_port,
                    database=self.db_name,
                    user=self.db_admin_username,
                    password=self.db_admin_password,
                    sslmode=self.db_sslmode,
                    sslrootcert=self.db_sslrootcert)
                # On connection creation, set the autocommit state if specified
                if autocommit is not None:
                    self._admin_database_connection.autocommit = autocommit
                return self._admin_database_connection
            raise ProviderError("Database is not enabled") from e

    def object_store_conn(self) -> Minio:
        """
        Returns a connection to the object store specified by the Clowder
        config.

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
            # Attempt to return cached connection
            return self._minio_conn
        # If cached connection is not available, create a new one
        except AttributeError as e:
            # But only if the object store is enabled
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
            # Attempt to return cached consumer
            return self._kafka_consumer_conn
        # If cached consumer is not available, create a new one
        except AttributeError as e:
            # But only if Kafka is enabled
            if self.kafka_enabled:
                self._kafka_consumer_conn = Consumer({
                    "bootstrap.servers": self.kafka_server,
                    "group.id": __name__
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
            # Attempt to return cached producer
            return self._kafka_producer_conn
        # If cached producer is not available, create a new one
        except AttributeError as e:
            # But only if Kafka is enabled
            if self.kafka_enabled:
                self._kafka_producer_conn = Producer({
                    "bootstrap.servers": self.kafka_server,
                    "client.id": __name__
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
            # Attempt to return cached connection
            return self._redis_conn
        # If cached connection is not available, create a new one
        except AttributeError as e:
            # But only if the in-memory database is enabled
            if self.in_memory_db_enabled:
                self._redis_conn = Redis(host=self.in_memory_db_host,
                                         port=self.in_memory_db_port)
                return self._redis_conn
            raise ProviderError("In-memory db is not enabled") from e

    def feature_flags_conn(self) -> UnleashClient:
        """
        Returns a connection to the feature flags server specified by the
        Clowder config.

        Returns
        -------
        UnleashClient
            A connection to the feature flags server

        Raises
        ------
        ProviderError
            If the feature flags server is not enabled in the Clowder config
            but this method is called.
        """
        try:
            # Attempt to return cached connection
            return self._feature_flags_conn
        # If cached connection is not available, create a new one
        except AttributeError as e:
            # But only if feature flags is enabled
            if self.feature_flags_enabled:
                # Unleash client takes custom_headers as dict | None, so we
                # can directly pass client access token I believe
                feature_flags_connection = UnleashClient(
                    url=self.feature_flags_url,
                    app_name=self.app_name,
                    custom_headers=self.feature_flags_client_access_token)
                # Feature flags connections require initialization, and if
                # they fail, we should raise an error and also delete the
                # connection that we just created
                try:
                    feature_flags_connection.initialize_client()
                    self._feature_flags_conn = feature_flags_connection
                    return self._feature_flags_conn
                except InvalidSchema:
                    raise ProviderError("Invalid featureflags schema") from e
            raise ProviderError("Feature flags server is not enabled") from e
