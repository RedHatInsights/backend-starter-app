.DEFAULT_GOAL := push_pod
.PHONY: minikube_start build_and_run clean

PERSONAL_SECRET ?= ../../../rh-ee-jtoftum-secret.yml
QUAY_SECRET ?= ../../../quay-cloudservices-pull.yml
# BUILD_TAG ?= $(shell git rev-parse --short=7 HEAD)
# TAG=`cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 7 | head -n 1`
# TODO: Fix image tag to auto-increment or auto-hash
BUILD_TAG ?= 001
HOST ?= 127.0.0.1
LOCATION ?= :5000/starterapp:$(BUILD_TAG)
IMG ?= $(HOST)$(LOCATION)

all: minikube_start build
	# Start minikube, build image, and push locally
build: build_container push_pod
	# Build image and push locally without starting minikube
fresh: clean all
	# Remove all minikube instances and start from scratch

minikube_start:
	# Start up clowder in minikube instance
	@echo "Starting minikube"
	minikube start --cpus 4 --disk-size 36GB --memory 16GB --driver=kvm2 --addons registry --addons ingress
	@echo "Curling clowder prereqs"
	curl https://raw.githubusercontent.com/RedHatInsights/clowder/master/build/kube_setup.sh | bash
	@echo "Applying clowder"
	minikube kubectl -- apply -f https://github.com/RedHatInsights/clowder/releases/download/v0.33.0/clowder-manifest-v0.33.0.yaml --validate=false

build_container:
	# Container build
	@echo "Building container"
	podman build -t starterapp .

	# Minikube needs to know where to get the image from so push locally
	podman build -t $(IMG) .

push_pod:
	# Clowdapp start
	podman push ${IMG} $(shell minikube ip)$(LOCATION) --tls-verify=false
	oc create namespace boot --dry-run=client -o yaml | oc apply -f -
	oc apply -f $(PERSONAL_SECRET) --namespace=boot
	oc apply -f $(QUAY_SECRET) --namespace=boot
	bonfire deploy-env --namespace=boot
	# oc process -f clowapp.yaml -p IMG=(IMG) -p HOST=$(HOST) -p LOCATION=$(LOCATION) -p TAG=$(TAG) -o yaml | oc apply -f -
	oc apply -f clowdapp.yaml --namespace=boot

run_local:
	# Run starter app
	@echo "Running Container"
	podman run -e ACG_CONFIG="/test.json" -it localhost/starterapp
	@echo "Container stopped"

clean:
	@echo "Cleaning container"
	minikube delete
