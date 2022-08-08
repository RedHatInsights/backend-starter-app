import environ
import psycopg2
from app_common_python import LoadedConfig, isClowderEnabled

number_of_messages = 100
environment = environ.Env()

db_sslmode = None
db_sslrootcert = None
if LoadedConfig.database.rdsCa:
    db_sslmode = environment.get_value("PGSSLMODE", default="prefer")
    db_sslrootcert = LoadedConfig.rds_ca()

db_conn = psycopg2.connect(host=LoadedConfig.database.hostname,
                           port=LoadedConfig.database.port,
                           database=LoadedConfig.database.name,
                           user=LoadedConfig.database.username,
                           password=LoadedConfig.database.password,
                           sslmode=db_sslmode,
                           sslrootcert=db_sslrootcert)

db_conn.autocommit = True

print("Connected to Postgres")
SQL = "CREATE TABLE IF NOT EXISTS init_container (id SERIAL PRIMARY KEY, message VARCHAR(255));"
with db_conn.cursor() as cursor:
    cursor.execute(SQL)
print("Created init_container table")

SQL = "INSERT INTO init_container (message) VALUES ('Hello from the init container');"

for _ in range(number_of_messages):
    with db_conn.cursor() as cursor:
        cursor.execute(SQL)
