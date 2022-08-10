# Python Backend Starter App

Provides small examples of various [Clowder](https://github.com/RedHatInsights/clowder/) providers by making use of [app-common-python](https://github.com/RedHatInsights/app-common-python) and some other small example pieces of code to attempt to help app developers get started more quickly.

There is also additional documentation in `python_starter/views.py` and `python_starters/starter_helper.py`.

---
## Requirements
In order to run this you'll need to have the following installed:
* The openshift CLI, [oc](https://docs.openshift.com/container-platform/4.8/cli_reference/openshift_cli/getting-started-cli.html)
* [Podman](https://podman.io/getting-started/installation.html)
* [Minikube](https://minikube.sigs.k8s.io/docs/start/)
* The Kubernetes command-line tool, [Kubectl](https://kubernetes.io/docs/tasks/tools/)
* [Python3](https://www.python.org/downloads/)—the starter app itself is using Python 3.9
* [Bonfire](https://pypi.org/project/crc-bonfire/)
* The json processor [jq](https://stedolan.github.io/jq/download/)
* [Pytest](https://docs.pytest.org/en/latest/) if you want to run the tests

---
## Building
The entire project can be built with `make all`, which starts minikube, builds the container, prepares the namespace, and then starts the app.
Further iteration can be done with a simple `make` command, and the entire app as well as minikube and built folders can be torn down with `make clean`.

Currently, a cloud services secret is required in order to build the app, and by default is three folders above the Python starter root folder to prevent it from being accidentally published.

An example of what your [Quay.io](https://quay.io/) pull secret should look like is shown below.

```yml
apiVersion: v1
kind: Secret
metadata:
  name: quay-cloudservices-pull
data:
  .dockerconfigjson: ewogICJhdXRocyI6IHsKICAgICJxdWF5LmlvIjogewogICAgICAiYXV0aCI6ICJIZWxsbyEgVGhpcyBpcyBhbiBleGFtcGxlIHN0cmluZyBJIGVuY29kZWQgaW50byBiYXNlIDY0IHRoYXQgd29uJ3QgYWN0dWFsbHkgd29yayBhcyBhIHF1YXkgc2VjcmV0LCBob3BlIHlvdSdyZSBoYXZpbmcgYSBnb29kIGRheSA6KSIsCiAgICAgICJlbWFpbCI6ICIiCiAgICB9CiAgfQp9Cg==
type: kubernetes.io/dockerconfigjson
```

If you want to run anything locally without putting it inside of your minikube container, you will need to ensure you have an environment variable set so Clowder (through app-common-python) knows where to find information. You can do this, for example, by running
```bash
ACG_CONFIG=test.json python <some_python_file.py>
```

---
## Included
Examples currently in the repository include:
* Liveness and readiness probe examples, which are found at the `/livez` and `/readyz` endpoints. If these are disabled, Clowder uses the `/healthz` endpoint instead.
    * These endpoints and any other endpoints can be accessed by forwarding the web port, which defaults to `8000`:
        ```sh
        oc port-forward --namespace=boot svc/starterapp-worker-service 8000
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
    * It may be worth noting that the Unleash client, by default, refreshes its feature flags every 15 seconds. If this is deemed to be too slow, the connection can be initialized with a smaller refresh interval, e.g.
        ```python
        scaffolding.feature_flags_conn(refresh_interval=1)
        ```
        See the [Unleash docs](https://docs.getunleash.io/unleash-client-python/unleashclient.html) for more information.
* A ClowdJobInvocation (CJI) found within the `clowdapp.yaml` file under the first `object` in the template, then under `spec: jobs: name: example-cji`.
    * The CJI is triggered as a job by the *second* `object` in the template, then under `spec: jobs: example-cji`
    * Once the app is running, this can be verified to have run with:
        ```sh
        oc get pods --namespace=boot | grep starterapp-example-cji | awk '{print $1}' | while read a; do oc logs --namespace=boot $a; done
        ```
* A CronJob, found within the `clowdapp.yaml` file under the first `object` in the template, then under `spec: jobs: name: example-cronjob`
    * Once the app is running, this can be verified to be running on a schedule with:
        ```sh
        oc get pods --namespace=boot | grep starterapp-example-cronjob | awk '{print $1}' | while read a; do oc logs --namespace=boot $a; done
        ```
All provider connections pass any additional arguments and keyword arguments to the relevant initialization functions.

---
## Tests
Some unit tests are included to ensure that the app works as expected, and can be run using `pytest` after forwarding the web port. For example

```sh
oc port-forward --namespace=boot svc/starterapp-worker-service 8000
```
in one terminal and then `pytest` in another.
