# Alumnos
- Cibrian, Stefanie
- Moya, Wayner
- Ruiz, Ana Pamela

# Custom Kubernetes Scheduler

This repository provides a minimal custom scheduler written in **Python** using the
`kubernetes` Python client. It includes two variants:

- **main (polling)**: polling loop that finds Pending pods and binds them.
- **(watch-based)**: Watch based with taints and tolerances.

## Quickstart

```bash
# 0) Prereqs
#    kind, kubectl, Docker

# 1) Create a kind cluster
make create-cluster

# 2) Build & load image
make build
make kind-load

# For Polling scheduler
# 3.1) Deploy ServiceAccount/RBAC + Deployment
make deploy-poll

# 3.2) Schedule a test Pod using your scheduler
make test-poll

# 3.3) CleanUp
make undeploy-poll

# For Watch Scheduler
# 4.1) Deploy ServiceAccount/RBAC + Deployment
make deploy-watch

# 4.2) Add taints
make taint-label

# 4.3) Schedule a test Pod using your scheduler
make test-watch

# 4.3) CleanUp
make undeploy-watch

# 5) Watch logs for binding output
make logs


```
Cleanup:
```bash
kind delete cluster --name sched-lab
```
