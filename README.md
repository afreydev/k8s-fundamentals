# Kubernetes Fundamentals — 1-Hour Lecture Guide

Hands-on session using minikube. No custom images to build — everything uses `nginx`, `redis`, or `busybox`. The rule for the session: create everything with `kubectl apply -f <file>.yaml`. We'll show `kubectl run` once and then leave it alone.

---

## Overview

| Phase | Topic | ~Time |
|-------|-------|-------|
| 0 | Setup & prerequisites | pre-session |
| 1 | Architecture walkthrough | 15 min |
| 2 | Pods | 12 min |
| 3 | Deployments | 13 min |
| 4 | Services | 12 min |
| 5 | ConfigMaps, Secrets, Namespaces + Q&A | 8 min |

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

Kubernetes is a **container orchestration platform**. You declare the desired state in YAML; Kubernetes figures out how to make it happen and keeps it there through a continuous reconciliation loop.

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

 > Note: minikube runs everything — control plane and worker — in a single VM. Worth pointing out so people don't think this is how production looks.

---

## Phase 2 — Pods (12 min)

A **Pod** is the smallest thing Kubernetes can schedule. It holds one or more containers that share a network namespace — so they talk to each other over `localhost` — and each pod gets its own cluster-internal IP.

The important thing to understand early: pods are ephemeral. If one dies, nothing brings it back. That's what Deployments are for.

### Imperative (show once, then move on)

```bash
# Works fine — we're just not doing it this way
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

 > After deleting, show that nothing came back — that's the natural lead-in to Deployments.

---

## Phase 3 — Deployments (13 min)

A **Deployment** manages a ReplicaSet, which manages a set of identical pods. Declare how many replicas you want — if one dies, the controller replaces it. Change the image tag and re-apply — you get a rolling update. It also gives you rollback out of the box.

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

### ReplicaSets — what's underneath the Deployment

When you apply a Deployment, Kubernetes creates a **ReplicaSet** automatically. The ReplicaSet's only job is to make sure a given number of identical pods are running at all times.

```bash
kubectl get replicasets                   # see the RS created by the deployment
kubectl describe replicaset <rs-name>     # notice the ownerReferences → Deployment
```

**ReplicaSet vs Deployment — why you almost always want a Deployment:**

| | ReplicaSet | Deployment |
|--|------------|------------|
| Keeps N pods running | Yes | Yes (via RS) |
| Rolling updates | No | Yes |
| Rollback | No | Yes |
| Manages multiple RS versions | No | Yes |

You *can* create a ReplicaSet directly with `kind: ReplicaSet`, but there is rarely a reason to. If you change the image tag in a bare ReplicaSet manifest and re-apply, **existing pods are not updated** — only new pods get the new image. A Deployment solves this by creating a new ReplicaSet and gradually migrating pods across.

### Bare ReplicaSet manifest — `03-deployments/replicaset-nginx.yaml`

```yaml
apiVersion: apps/v1
kind: ReplicaSet
metadata:
  name: nginx-rs
spec:
  replicas: 3
  selector:
    matchLabels:
      app: nginx-rs
  template:
    metadata:
      labels:
        app: nginx-rs
    spec:
      containers:
        - name: nginx
          image: nginx:1.24
          ports:
            - containerPort: 80
```

```bash
kubectl apply -f 03-deployments/replicaset-nginx.yaml
kubectl get replicasets
kubectl get pods -l app=nginx-rs
```

### Demo 1 — delete a pod and watch it come back

```bash
# Grab any pod name
kubectl get pods -l app=nginx-rs

# Open a watch in a second terminal
kubectl get pods -w

# Delete one pod from the first terminal
kubectl delete pod <pod-name>
```

**Expected result:**

```
NAME             READY   STATUS        RESTARTS   AGE
nginx-rs-4xk2p   1/1     Running       0          2m
nginx-rs-7bqrm   1/1     Terminating   0          2m   ← deleted
nginx-rs-9vzlt   1/1     Running       0          2m
nginx-rs-kcj8d   0/1     Pending       0          1s   ← new pod, already scheduled
nginx-rs-kcj8d   0/1     ContainerCreating   0   1s
nginx-rs-kcj8d   1/1     Running       0          3s   ← back to 3
```

The replacement pod has a new name and a new IP. The RS controller reacted as soon as the pod count dropped below `replicas: 3`.

The sequence under the hood:
1. `kubelet` reports the pod as gone to the API server.
2. The ReplicaSet controller sees `current < desired` and creates a new pod spec.
3. The Scheduler picks a node for it.
4. `kubelet` on that node pulls the image and starts the container.

### Demo 2 — update the image and see that existing pods are NOT replaced

Edit `replicaset-nginx.yaml` and change the image tag:

```yaml
# Change image: nginx:1.24  →  nginx:1.25
          image: nginx:1.25
```

```bash
kubectl apply -f 03-deployments/replicaset-nginx.yaml
kubectl get pods -l app=nginx-rs
```

**Expected result:** the three pods are still running. Nothing changed.

```bash
# Verify: the running pods still use the old image
kubectl get pods -l app=nginx-rs -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[0].image}{"\n"}{end}'
```

```
nginx-rs-4xk2p   nginx:1.24   ← old image, still running
nginx-rs-7bqrm   nginx:1.24
nginx-rs-9vzlt   nginx:1.24
```

The ReplicaSet controller only looks at the pod count, not the image. It has no mechanism to roll out a change to existing pods. To force the update, you would have to delete the pods manually one by one — and at that point you are reinventing what a Deployment already does automatically.

```bash
# Clean up
kubectl delete -f 03-deployments/replicaset-nginx.yaml
```

 > Good demo: open a second terminal with `kubectl get pods -w`, then delete a pod from the first. The watch window shows the reconciliation loop reacting in real time.

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

 > Scale to 5 and delete two pods at once from one terminal while watching `kubectl get pods -w` in another — makes the reconciliation loop very concrete.

---

## Bonus demo — two versions, one Service (canary pattern)

This demo makes label selectors and load balancing concrete: two Deployments run different versions of the same app, and a single Service routes traffic to both because they share a common label.

The image used is `hashicorp/http-echo` — it serves whatever string you pass as `-text`, so each version replies with a different message and you can see the balancing live.

### `06-canary/deployment-v1.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: echo-v1
spec:
  replicas: 2
  selector:
    matchLabels:
      app: echo
      version: v1
  template:
    metadata:
      labels:
        app: echo
        version: v1
    spec:
      containers:
        - name: echo
          image: hashicorp/http-echo
          args:
            - "-text=Hello from v1"
          ports:
            - containerPort: 5678
```

### `06-canary/deployment-v2.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: echo-v2
spec:
  replicas: 2
  selector:
    matchLabels:
      app: echo
      version: v2
  template:
    metadata:
      labels:
        app: echo
        version: v2
    spec:
      containers:
        - name: echo
          image: hashicorp/http-echo
          args:
            - "-text=Hello from v2"
          ports:
            - containerPort: 5678
```

### `06-canary/service-echo.yaml`

The selector only matches on `app: echo` — it intentionally ignores `version`. This means it sees all 4 pods (2 × v1, 2 × v2) as valid endpoints.

```yaml
apiVersion: v1
kind: Service
metadata:
  name: echo-service
spec:
  type: NodePort
  selector:
    app: echo          # matches BOTH versions — version label is NOT here
  ports:
    - protocol: TCP
      port: 80
      targetPort: 5678
      nodePort: 30090
```

### Apply and watch the balancing

```bash
kubectl apply -f 06-canary/deployment-v1.yaml
kubectl apply -f 06-canary/deployment-v2.yaml
kubectl apply -f 06-canary/service-echo.yaml

# Confirm all 4 pods are endpoints of the service
kubectl get pods -l app=echo --show-labels
kubectl describe service echo-service      # Endpoints should list 4 IPs

# Hit the service repeatedly — responses alternate between v1 and v2
for i in $(seq 1 10); do curl -s $(minikube service echo-service --url); done
```

Expected output — roughly half v1, half v2:

```
Hello from v1
Hello from v2
Hello from v1
Hello from v1
Hello from v2
...
```

### What this shows

- The `version` label on the pods is **not** in the Service selector, so both Deployments' pods are included as endpoints.
- kube-proxy does round-robin across all matching pods — no preference for version.
- Each Deployment is still independently managed: you can scale, update, or roll back `echo-v1` without touching `echo-v2`.

### Simulate a canary rollout by adjusting replica counts

```bash
# Send ~25% traffic to v2 by keeping 3 v1 pods and 1 v2 pod
# Edit deployment-v1.yaml → replicas: 3
# Edit deployment-v2.yaml → replicas: 1
kubectl apply -f 06-canary/deployment-v1.yaml
kubectl apply -f 06-canary/deployment-v2.yaml

for i in $(seq 1 8); do curl -s $(minikube service echo-service --url); done
# Now roughly 6 × v1, 2 × v2
```

### Clean up

```bash
kubectl delete -f 06-canary/deployment-v1.yaml
kubectl delete -f 06-canary/deployment-v2.yaml
kubectl delete -f 06-canary/service-echo.yaml
```

 > Key teaching point: the Service selector is the only thing that decides which pods receive traffic. Adding or removing a label from a pod — or from the selector — is how you include or exclude it, with no downtime and no Service restart needed.

---

## Phase 4 — Services (12 min)

Pod IPs change every time a pod restarts. A **Service** solves this by giving you a stable DNS name and virtual IP that kube-proxy keeps pointing at the current live pods.

### Service types

| Type | Access | When to use |
|------|--------|------------|
| **ClusterIP** | Inside cluster only (default) | Service-to-service calls |
| **NodePort** | Node IP + a port in 30000–32767 | Local dev, minikube demos |
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

 > The `selector: app: nginx` is the glue between Service and Deployment. Change it to something that doesn't match, re-apply, and `kubectl describe service nginx-service` will show 0 endpoints — useful for making label selectors concrete.

---

## Phase 5 — ConfigMaps, Secrets & Namespaces + Q&A (8 min)

### ConfigMaps

Keep config out of your container image. A ConfigMap holds plain key-value pairs that pods can consume as env vars or mounted files.

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

### Secrets

Same idea as ConfigMap, but values are base64-encoded and get extra treatment in real clusters — RBAC, encryption at rest. Worth being clear: base64 is not encryption, it's just encoding.

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

### Namespaces

Namespaces let you carve up a cluster into isolated slices — by team, by environment, whatever makes sense. Resources in different namespaces can share the same name without conflicting.

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
| `03-deployments/replicaset-nginx.yaml` | ReplicaSet | 3 |
| `03-deployments/deployment-nginx.yaml` | Deployment | 3 |
| `04-services/service-nginx.yaml` | Service | 4 |
| `04-services/pod-busybox.yaml` | Pod | 4 |
| `05-config/configmap-app.yaml` | ConfigMap | 5 |
| `05-config/pod-with-configmap.yaml` | Pod | 5 |
| `05-config/secret-db.yaml` | Secret | 5 |
| `05-config/pod-with-secret.yaml` | Pod | 5 |
| `05-config/namespace-staging.yaml` | Namespace | 5 |
| `05-config/deployment-redis-staging.yaml` | Deployment | 5 |
| `06-canary/deployment-v1.yaml` | Deployment | bonus |
| `06-canary/deployment-v2.yaml` | Deployment | bonus |
| `06-canary/service-echo.yaml` | Service | bonus |

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
kubectl delete -f 06-canary/deployment-v1.yaml
kubectl delete -f 06-canary/deployment-v2.yaml
kubectl delete -f 06-canary/service-echo.yaml

# Or wipe the cluster entirely
minikube stop
minikube delete
```

---

