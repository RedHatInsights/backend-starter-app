.DEFAULT_GOAL := quick_build

# TODO: Fix personal stuff
QUAY_SECRET ?= ../../../quay-cloudservices-pull.yml
IMAGE_TAG := $(shell cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 7 | head -n 1)
HOST ?= 127.0.0.1
LOCATION ?= :5000/starterapp
IMAGE ?= $(HOST)$(LOCATION)

# From a clean slate, `make all`
# After that `make`

all: minikube_start build
	# Start minikube, build image, and push locally
build: build_container push_pod namespace_prep apply_clowdapp
	# Build image and push locally without starting minikube
quick_build: build_container push_pod apply_clowdapp
	# Build image and push locally without starting minikube
	# No need to prep namespace
fresh: clean all
	# Remove all minikube instances and start from scratch


minikube_start:
	# Start up clowder in minikube instance
	@echo "Starting minikube"
	minikube start --cpus 4 --disk-size 36GB --memory 16GB --driver=kvm2 --addons registry --addons ingress
	@echo "Curling clowder prereqs"
	curl https://raw.githubusercontent.com/RedHatInsights/clowder/master/build/kube_setup.sh | bash
	@echo "Applying clowder"
	# TODO: Get latest clowder version from github automagically
	minikube kubectl -- apply -f https://github.com/RedHatInsights/clowder/releases/download/v0.42.0/clowder-manifest-v0.42.0.yaml --validate=false


build_container:
	# Container build
	@echo "Building container"
	# Minikube needs to know where to get the image from so push locally
	podman build -t $(IMAGE):$(IMAGE_TAG) .


push_pod:
	# Clowdapp start
	podman push ${IMAGE}:$(IMAGE_TAG) $(shell minikube ip)$(LOCATION):$(IMAGE_TAG) --tls-verify=false


namespace_prep:
	oc create namespace boot --dry-run=client -o yaml | oc apply -f -
	oc apply -f $(QUAY_SECRET) --namespace=boot
	bonfire deploy-env --namespace=boot


apply_clowdapp:
	# oc apply -f clowdapp.yaml --namespace=boot
	oc process --local -f clowdapp.yaml -p IMAGE=$(IMAGE) -p IMAGE_TAG=$(IMAGE_TAG) -o yaml | oc apply --namespace=boot -f -


run_local:
	# Run starter app
	@echo "Running Container"
	podman run -e ACG_CONFIG="/test.json" -it localhost/starterapp
	@echo "Container stopped"

remove_build:
	rm -rf ./build
	rm -rf ./__pycache__

clean:
	@echo "Cleaning container"
	minikube delete
	rm -rf ./build
	rm -rf ./__pycache__
