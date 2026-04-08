# Kubernetes Fundamentals — 1-Hour Lecture Guide
### Using minikube · Manifest-first approach · Pre-built images only

---

## Overview

| Phase | Topic | Duration |
|-------|-------|----------|
| 0 | Setup & prerequisites | Pre-session |
| 1 | Architecture walkthrough | 15 min |
| 2 | Pods | 12 min |
| 3 | Deployments | 13 min |
| 4 | Services | 12 min |
| 5 | ConfigMaps, Secrets, Namespaces + Q&A | 8 min |

**Images used throughout:** `nginx`, `redis`, `busybox`

> **Philosophy:** Everything is created via `kubectl apply -f <file>.yaml`. Imperative commands (`kubectl run`, `kubectl create`) are shown once to prove it's possible — then we move to manifests for the rest of the session.

---

## Phase 0 — Setup & prerequisites (before the session)

### Install

```bash
# Docker
brew install --cask docker          # macOS
sudo apt-get install docker.io      # Ubuntu/Debian

# minikube
brew install minikube               # macOS
# Linux:
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube

# kubectl
brew install kubectl                # macOS
# Linux:
curl -LO "https://dl.k8s.io/release/$(curl -sL https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install kubectl /usr/local/bin/kubectl
```

### Start & verify

```bash
minikube start
kubectl get nodes                   # STATUS = Ready
kubectl cluster-info

# Pre-pull demo images
docker pull nginx && docker pull redis && docker pull busybox
minikube image load nginx
minikube image load redis
minikube image load busybox
```

### Checklist

| Check | Command | Expected |
|-------|---------|----------|
| Docker running | `docker info` | No error |
| minikube up | `minikube status` | Running |
| kubectl connected | `kubectl get nodes` | 1 node, Ready |
| Images available | `minikube image ls` | nginx, redis, busybox listed |

---

## Phase 1 — Kubernetes architecture (15 min)

### Key concept

Kubernetes is a **container orchestration platform**. You declare the desired state in YAML manifests; Kubernetes makes it happen and keeps it that way through a continuous reconciliation loop.

### Control plane

| Component | Role |
|-----------|------|
| **API server** | Single entry point — all `kubectl apply` calls go here |
| **etcd** | Distributed key-value store — holds all cluster state |
| **Scheduler** | Assigns pods to nodes based on available resources |
| **Controller manager** | Watches state and reconciles toward the desired state |

### Worker node

| Component | Role |
|-----------|------|
| **kubelet** | Agent on every node; reads manifests, manages pod lifecycle |
| **kube-proxy** | Handles networking rules for Services |
| **Container runtime** | Actually runs containers (Docker, containerd) |

### Inspect the cluster

```bash
kubectl cluster-info
kubectl get nodes -o wide
kubectl get pods -n kube-system     # see all control plane components
minikube dashboard                  # optional browser UI
```

> **Teaching point:** minikube collapses control plane + worker into one VM. In production you'd have separate nodes for each.

---

## Phase 2 — Pods (12 min)

### Key concept

A **Pod** is the smallest deployable unit in Kubernetes. It wraps one or more containers that share a network namespace and storage volumes.

- Each pod gets its own cluster-internal IP
- Containers inside a pod talk to each other via `localhost`
- Pods are **ephemeral** — when they die, nothing reschedules them (that's what Deployments are for)

### Imperative (show once, then never again)

```bash
# This works — but we won't do it this way
kubectl run nginx-pod --image=nginx
kubectl delete pod nginx-pod
```

### The manifest way — `02-pods/pod-nginx.yaml`

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: nginx-pod
  labels:
    app: nginx
spec:
  containers:
    - name: nginx
      image: nginx
      ports:
        - containerPort: 80
```

```bash
# Apply the manifest
kubectl apply -f 02-pods/pod-nginx.yaml

# Watch it come up
kubectl get pods -w

# Inspect
kubectl describe pod nginx-pod
kubectl logs nginx-pod

# Exec into the container
kubectl exec -it nginx-pod -- /bin/bash
# Inside: curl localhost   →  nginx welcome page
# Inside: exit

# See the full live YAML (compare with what you wrote)
kubectl get pod nginx-pod -o yaml

# Delete using the same manifest — clean and explicit
kubectl delete -f 02-pods/pod-nginx.yaml
```

> **Teaching point:** After deleting, show that nothing brings the pod back. This is the natural lead-in to Deployments.

---

## Phase 3 — Deployments (13 min)

### Key concept

A **Deployment** manages a ReplicaSet, which in turn manages a set of identical Pods. You declare desired state; Kubernetes continuously reconciles toward it.

- **Self-healing:** dead pods are automatically replaced
- **Scaling:** change `replicas` in the manifest and re-apply
- **Rolling updates:** change `image` and re-apply — zero downtime
- **Rollback:** revert with a single command

### The manifest — `03-deployments/deployment-nginx.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-deploy
  labels:
    app: nginx
spec:
  replicas: 3
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
    spec:
      containers:
        - name: nginx
          image: nginx:1.24
          ports:
            - containerPort: 80
          resources:
            requests:
              cpu: "50m"
              memory: "64Mi"
            limits:
              cpu: "100m"
              memory: "128Mi"
```

```bash
kubectl apply -f 03-deployments/deployment-nginx.yaml

kubectl get deployments
kubectl get pods                          # 3 pods running
kubectl get replicasets                   # see the RS underneath
kubectl describe deployment nginx-deploy
```

### Self-healing demo

```bash
# Kill one pod manually
kubectl delete pod <any-pod-name>

# Watch it get replaced automatically
kubectl get pods -w
```

### Scaling — edit the manifest

```yaml
# Change replicas: 3  →  replicas: 5  in deployment-nginx.yaml
spec:
  replicas: 5
```

```bash
kubectl apply -f 03-deployments/deployment-nginx.yaml
kubectl get pods                          # now 5 pods

# Scale back down — change replicas: 5 → 2
kubectl apply -f 03-deployments/deployment-nginx.yaml
kubectl get pods                          # now 2 pods
```

### Rolling update — change the image tag

```yaml
# Change image: nginx:1.24  →  image: nginx:1.25  in deployment-nginx.yaml
containers:
  - name: nginx
    image: nginx:1.25
```

```bash
kubectl apply -f 03-deployments/deployment-nginx.yaml
kubectl rollout status deployment/nginx-deploy
kubectl rollout history deployment/nginx-deploy
```

### Rollback

```bash
kubectl rollout undo deployment/nginx-deploy
kubectl rollout status deployment/nginx-deploy
```

> **Teaching point:** Scale to 5, open a second terminal with `kubectl get pods -w`, then delete two pods at once. The watch window shows the reconciliation loop in real time.

---

## Phase 4 — Services (12 min)

### Key concept

A **Service** gives a stable network endpoint to a dynamic set of Pods. Pod IPs change when pods restart — a Service provides a consistent DNS name and virtual IP backed by kube-proxy.

### Service types

| Type | Access | Use case |
|------|--------|----------|
| **ClusterIP** | Inside cluster only (default) | Internal microservice communication |
| **NodePort** | Node IP + static port (30000–32767) | Dev/testing, minikube demos |
| **LoadBalancer** | Cloud load balancer | Production external traffic |

### The manifest — `04-services/service-nginx.yaml`

```yaml
apiVersion: v1
kind: Service
metadata:
  name: nginx-service
spec:
  type: NodePort
  selector:
    app: nginx               # matches the label on Deployment pods
  ports:
    - protocol: TCP
      port: 80               # cluster-internal port
      targetPort: 80         # container port
      nodePort: 30080        # external port (optional — auto-assigned if omitted)
```

```bash
# Make sure the deployment is running with 3 replicas first
kubectl apply -f 03-deployments/deployment-nginx.yaml

# Apply the service
kubectl apply -f 04-services/service-nginx.yaml

kubectl get services
kubectl describe service nginx-service

# Get the accessible URL (minikube only)
minikube service nginx-service --url
# Open the URL in a browser — nginx welcome page!
curl $(minikube service nginx-service --url)
```

### Internal access demo — `04-services/pod-busybox.yaml`

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: busybox-client
spec:
  containers:
    - name: busybox
      image: busybox
      command: ["sleep", "3600"]   # keep it alive for testing
```

```bash
kubectl apply -f 04-services/pod-busybox.yaml

# Reach nginx by Service name — DNS resolution inside the cluster
kubectl exec -it busybox-client -- wget -qO- nginx-service

kubectl delete -f 04-services/pod-busybox.yaml
```

### Clean up phase 4

```bash
kubectl delete -f 04-services/service-nginx.yaml
kubectl delete -f 03-deployments/deployment-nginx.yaml
```

> **Teaching point:** The `selector: app: nginx` is the glue between Service and Deployment. Change it to something wrong and show the service returning no endpoints — great way to explain label selectors.

---

## Phase 5 — ConfigMaps, Secrets & Namespaces + Q&A (8 min)

### ConfigMaps — externalise configuration

Keep config out of your container image. A ConfigMap stores plain key-value data that pods consume as environment variables or mounted files.

**`05-config/configmap-app.yaml`**

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  APP_ENV: production
  LOG_LEVEL: info
  MAX_CONNECTIONS: "100"
```

**`05-config/pod-with-configmap.yaml`** — consuming ConfigMap as env vars

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: config-demo
spec:
  containers:
    - name: nginx
      image: nginx
      envFrom:
        - configMapRef:
            name: app-config
```

```bash
kubectl apply -f 05-config/configmap-app.yaml
kubectl apply -f 05-config/pod-with-configmap.yaml

kubectl get configmaps
kubectl describe configmap app-config

# Verify the env vars are injected
kubectl exec -it config-demo -- env | grep -E "APP_ENV|LOG_LEVEL|MAX_CONNECTIONS"

kubectl delete -f 05-config/pod-with-configmap.yaml
kubectl delete -f 05-config/configmap-app.yaml
```

---

### Secrets — sensitive data

Same idea as ConfigMap, but values are base64-encoded and treated with extra care (RBAC, encryption at rest in production).

**`05-config/secret-db.yaml`**

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: db-secret
type: Opaque
stringData:                  # use stringData — kubectl encodes it for you
  DB_PASSWORD: supersecret
  DB_USER: admin
```

**`05-config/pod-with-secret.yaml`** — consuming Secret as env vars

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: secret-demo
spec:
  containers:
    - name: nginx
      image: nginx
      env:
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: DB_PASSWORD
        - name: DB_USER
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: DB_USER
```

```bash
kubectl apply -f 05-config/secret-db.yaml
kubectl apply -f 05-config/pod-with-secret.yaml

kubectl get secrets
kubectl describe secret db-secret          # values are hidden

# Decode manually
kubectl get secret db-secret -o jsonpath='{.data.DB_PASSWORD}' | base64 --decode

kubectl delete -f 05-config/pod-with-secret.yaml
kubectl delete -f 05-config/secret-db.yaml
```

---

### Namespaces — logical isolation

Namespaces partition a cluster into virtual sub-clusters — useful for separating teams, environments, or applications.

**`05-config/namespace-staging.yaml`**

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: staging
```

**`05-config/deployment-redis-staging.yaml`** — scoped to the staging namespace

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis-staging
  namespace: staging
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
        - name: redis
          image: redis
          ports:
            - containerPort: 6379
```

```bash
kubectl apply -f 05-config/namespace-staging.yaml
kubectl apply -f 05-config/deployment-redis-staging.yaml

kubectl get namespaces
kubectl get pods -n staging
kubectl get pods --all-namespaces          # see everything across all namespaces

# Deleting a namespace removes everything inside it
kubectl delete -f 05-config/deployment-redis-staging.yaml
kubectl delete -f 05-config/namespace-staging.yaml
```

---

## Quick reference — kubectl cheatsheet

```bash
# Apply / delete any resource
kubectl apply -f <file>.yaml
kubectl delete -f <file>.yaml

# Get resources
kubectl get pods / deployments / services / configmaps / secrets / namespaces

# Inspect
kubectl describe <resource> <name>
kubectl logs <pod-name>
kubectl exec -it <pod-name> -- /bin/bash

# Watch in real time
kubectl get pods -w

# Output formats
kubectl get pod <name> -o yaml
kubectl get pod <name> -o json

# Namespace flag
kubectl get pods -n <namespace>
kubectl get pods --all-namespaces

# Rollout
kubectl rollout status deployment/<name>
kubectl rollout history deployment/<name>
kubectl rollout undo deployment/<name>
```

---

## All manifests at a glance

| File | Kind | Phase |
|------|------|-------|
| `02-pods/pod-nginx.yaml` | Pod | 2 |
| `03-deployments/deployment-nginx.yaml` | Deployment | 3 |
| `04-services/service-nginx.yaml` | Service | 4 |
| `04-services/pod-busybox.yaml` | Pod | 4 |
| `05-config/configmap-app.yaml` | ConfigMap | 5 |
| `05-config/pod-with-configmap.yaml` | Pod | 5 |
| `05-config/secret-db.yaml` | Secret | 5 |
| `05-config/pod-with-secret.yaml` | Pod | 5 |
| `05-config/namespace-staging.yaml` | Namespace | 5 |
| `05-config/deployment-redis-staging.yaml` | Deployment | 5 |

---

## Clean up everything

```bash
kubectl delete -f 02-pods/pod-nginx.yaml
kubectl delete -f 03-deployments/deployment-nginx.yaml
kubectl delete -f 04-services/service-nginx.yaml
kubectl delete -f 04-services/pod-busybox.yaml
kubectl delete -f 05-config/configmap-app.yaml
kubectl delete -f 05-config/pod-with-configmap.yaml
kubectl delete -f 05-config/secret-db.yaml
kubectl delete -f 05-config/pod-with-secret.yaml
kubectl delete -f 05-config/deployment-redis-staging.yaml
kubectl delete -f 05-config/namespace-staging.yaml

# Or wipe the cluster entirely
minikube stop
minikube delete
```

---

*Kubernetes Fundamentals · 1-Hour Lecture Guide · minikube edition · manifest-first*
