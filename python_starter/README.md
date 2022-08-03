# Python Backend Starter App

Provides small examples of various [Clowder](https://github.com/RedHatInsights/clowder/) providers by making use of [app-common-python](https://github.com/RedHatInsights/app-common-python) and some other small example pieces of code to attempt to help app developers get started more quickly.

There is also additional documentation in `python_starter/views.py` and `python_starters/starter_helper.py`.

Examples currently in the repository include:
* Liveness and readiness probe examples, which are found at the `/livez` and `/readyz` endpoints. If these are disabled, Clowder uses the `/healthz` endpoint instead.
    * These endpoints and any other endpoints can be accessed by forwarding the web port, which defaults to `8000`:
        ```sh
        oc port-forward --namespace=boot svc/starterapp-worker-service 8000;
        ```
        then visit http://127.0.0.1:8000/`$endpoint`, where `$endpoint` is one of the endpoints listed, such as http://127.0.0.1:8000/livez.

* Kafka, with the usage of the [Confluent Kafka library](https://github.com/confluentinc/confluent-kafka-python), at the `/kafka` endpoint.
* In-memory database, with the [redis-py library](https://github.com/redis/redis-py), at the `/redis` endpoint.
* PostgreSQL database, with the [psycopg2 library](https://github.com/psycopg/psycopg2/), at the `/postgres` endpoint.
* Object storage, with the [Minio library](https://github.com/minio/minio-py/), at the `/minio` endpoint.
* Prometheus, with the [prometheus-client library](https://github.com/prometheus/client_python), and defaults to port `9000`.
* Feature Flags, with the [Unleash Client library](https://github.com/Unleash/unleash-client-python), at the `/featureflag` endpoint.
    * Feature Flags can be set by forwarding the feature flags port, which defaults to 4242:
        ```sh
        oc port-forward --namespace=boot svc/env-boot-featureflags 4242
        ```
        and then going to http://127.0.0.1:4242/.
* A ClowdJobInvocation (CJI) found within the `clowdapp.yaml` file under the first `object` in the template, then under `spec: jobs: name: example-cji`.
    * The CJI is triggered as a job by the *second* `object` in the template, then under `spec: jobs: example-cji`
    * Once the app is running, this can be verified to be running with:
        ```sh
        oc get pods --namespace=boot | grep starterapp-example-cji | awk '{print $1}' | while read a; do oc logs --namespace=boot $a; done;
        ```
* A CronJob, found within the `clowdapp.yaml` file under the first `object` in the template, then under `spec: jobs: name: example-cronjob`
    * Once the app is running, this can be verified to have run with:
        ```sh
        oc get pods --namespace=boot | grep starterapp-example-cron | awk '{print $1}' | while read a; do oc logs --namespace=boot $a; done;
        ```
---
## Tests
Some unit tests are included to ensure that the app works as expected, and can be run using `pytest` after forwarding the web port. For example

```sh
oc port-forward --namespace=boot svc/starterapp-worker-service 8000;
```
in one terminal and then `pytest` in another.
