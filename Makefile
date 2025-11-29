APP=my-py-scheduler
APP-WATCH=my-py-scheduler-watch
KIND_CLUSTER=sched-lab

.PHONY: build kind-load deploy test logs undeploy

create-cluster:
	kind create cluster --config kind-multi-node.yml --name $(KIND_CLUSTER)

build:
	cd Polling-Scheduler && docker build -t $(APP):latest .
	cd ../Watch-Scheduler && docker build -t $(APP-WATCH):latest .

kind-load:
	kind load docker-image $(APP):latest --name $(KIND_CLUSTER)
	kind load docker-image $(APP-WATCH):latest --name $(KIND_CLUSTER)

deploy-poll:
	kubectl apply -f Polling-Scheduler/rbac-deploy.yaml

deploy-watch:
	kubectl apply -f Watch-Scheduler/rbac-deploy.yaml

test-poll:
	kubectl apply -f test-pod.yaml

test-watch:
	kubectl apply -f test-pod.yaml
	kubectl apply -f test-prod.yaml

undeploy-poll:
	kubectl delete -f Polling-Scheduler/rbac-deploy.yaml --ignore-not-found
	kubectl delete -f test-pod.yaml --ignore-not-found

undeploy-watch:
	kubectl delete -f Watch-Scheduler/rbac-deploy.yaml --ignore-not-found
	kubectl delete -f test-pod.yaml --ignore-not-found
	kubectl delete -f test-prod.yaml --ignore-not-found 

logs:
	kubectl -n kube-system logs deploy/my-scheduler -f

taint-label:
	kubectl taint nodes sched-lab-worker3 dedicated=prod:NoSchedule
	kubectl label nodes sched-lab-worker3 env=prod