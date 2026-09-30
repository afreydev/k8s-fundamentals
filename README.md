# Kubernetes Fundamentals — 1-Hour Lecture Guide

Hands-on session using minikube. Phases 0–5 use only public images (`nginx`, `redis`, `busybox`) — no custom images to build. The capstone (Phase 6) builds and deploys our own: a small Flask API + a PostgreSQL StatefulSet. The rule for the session: create everything with `kubectl apply -f <file>.yaml`. We'll show `kubectl run` once and then leave it alone.

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
| 6 | Capstone: backend + database (Deployment + StatefulSet) | +15 min (optional) |

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
docker pull nginx && docker pull redis && docker pull busybox && docker pull postgres:16
minikube image load nginx
minikube image load redis
minikube image load busybox
minikube image load postgres:16
```

### Checklist

| Check | Command | Expected |
|-------|---------|----------|
| Docker running | `docker info` | No error |
| minikube up | `minikube status` | Running |
| kubectl connected | `kubectl get nodes` | 1 node, Ready |
| Images available | `minikube image ls` | nginx, redis, busybox, postgres listed |

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

## Phase 6 — Capstone: backend + database (+15 min, optional)

Everything so far was a single stateless component running a public image. Real applications look more like this: a stateless API you scale freely, and a stateful database that must keep its data *and* its identity. Same cluster, two different controllers.

```
browser
  │  NodePort 30085
  ▼
backend-service ──▶ backend-0     backend-1      Deployment — 2 replicas, stateless, interchangeable
                          │           │
                          └─────┬─────┘
                                │  DB_HOST=postgres-service
                                ▼
                     postgres-service (headless)   no VIP — DNS returns the pod IPs
                                │
                                ▼
                           postgres-0             StatefulSet — stable name, stable disk
                                │
                                ▼
                 PVC postgres-data-postgres-0      data survives pod restarts
```

Full-size version with the resource list, request flow and controller comparison: `07-backend-app/ARCHITECTURE.txt`.

### Two workloads, two controllers

| | Deployment (backend) | StatefulSet (database) |
|--|----------------------|------------------------|
| Pods | Identical, interchangeable | Identity matters — `postgres-0` is not `postgres-1` |
| Storage | None — stateless | One persistent disk per pod |
| Scaling / restart | Any order, any time | Ordered: `0` before `1`, teardown in reverse |
| Networking | One Service VIP, round-robin | Per-pod DNS names (`postgres-0.postgres-service`) |
| The question it answers | *"How many copies?"* | *"Which one am I?"* |

The rule of thumb: **ask whether the workload cares which pod it is.** A web server doesn't — a database does (client configs, replication, backups all reference a specific node).

### The application — `07-backend-app/`

A tiny Flask API that talks to PostgreSQL. Every piece of configuration comes from environment variables — injected by Kubernetes, exactly like the Secret/ConfigMap demos in Phase 5.

| Endpoint | Method | What it does |
|----------|--------|--------------|
| `/` | GET | Records a visit and replies with `served_by` — the pod that answered |
| `/health` | GET | `SELECT 1` against Postgres; `503` if the DB is down |
| `/visits` | GET | Last 50 rows from the `visits` table |
| `/visits` | POST | Insert a row (`{"path": "/whatever"}`) |

**`07-backend-app/app.py`** (trimmed — the file has the DB connection helpers too):

```python
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": os.environ.get("DB_PORT", "5432"),
    "dbname": os.environ.get("DB_NAME", "appdb"),
    "user": os.environ.get("DB_USER", "appuser"),
    "password": os.environ.get("DB_PASSWORD", "supersecret"),
}

@app.get("/")
def index():
    ensure_schema()
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO visits (hostname, path) VALUES (%s, %s)",
            (socket.gethostname(), "/"),
        )
    return jsonify(
        message="Hello from backend-k8s",
        served_by=socket.gethostname(),   # the pod name that handled the request
        database=DB_CONFIG["host"],
    )
```

`served_by` is what makes load balancing visible: hit the Service repeatedly and watch the pod name change.

**`07-backend-app/requirements.txt`**

```
flask==3.0.3
gunicorn==22.0.0
psycopg2-binary==2.9.9
```

### The Dockerfile — `07-backend-app/Dockerfile`

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
```

Line by line — this is the standard shape of any Python image:

| Instruction | Why |
|-------------|-----|
| `python:3.12-slim` | Small base image with `pip` — no OS cruft |
| `COPY requirements.txt` **before** `app.py` | Dependencies install in their own cached layer — editing code does not reinstall them |
| `gunicorn` | Production WSGI server — Flask's built-in server is for local development only |
| `EXPOSE 5000` | Documentation only; the real port mapping happens in the Service |

### Build and push to the registry

```bash
docker build -t afreydev/backend-k8s:latest ./07-backend-app
docker push afreydev/backend-k8s:latest
```

> Note: for a minikube-only demo you can skip the registry completely — `minikube image build -t afreydev/backend-k8s:latest ./07-backend-app` builds straight into minikube's Docker daemon. The Deployment sets `imagePullPolicy: IfNotPresent`, so the same manifest works with the registry image *and* a locally loaded one.

### Why a StatefulSet — the three guarantees

A Deployment throws away a pod's identity the moment it restarts. A StatefulSet promises the opposite:

| Guarantee | What it means in practice |
|-----------|---------------------------|
| **Stable identity** | Pod names are ordinals — `postgres-0`, `postgres-1` — never reused or shuffled |
| **Stable storage** | `volumeClaimTemplates` creates one PVC per pod; it is reattached after a restart or reschedule |
| **Ordered operations** | Pods are created and scaled up `0 → 1 → 2`, and torn down in reverse (`2 → 1 → 0`) |
| **Stable DNS** | Each pod resolves as `<pod-name>.<service-name>` — but only because of a headless Service |

### Headless Service — `07-backend-app/service-postgres.yaml`

A normal Service has a single virtual IP and round-robins across pods — you can never address one specific pod. A **headless** Service (`clusterIP: None`) skips the VIP: a DNS lookup returns *all* pod IPs, and `postgres-0.postgres-service` resolves to exactly that pod. This is what `serviceName: postgres-service` in the StatefulSet points at.

```yaml
apiVersion: v1
kind: Service
metadata:
  name: postgres-service
  labels:
    app: postgres
spec:
  clusterIP: None             # headless — no VIP, DNS returns the pod IPs directly
  selector:
    app: postgres             # matches the label on the StatefulSet pods
  ports:
    - protocol: TCP
      port: 5432              # cluster-internal port
```

### Persistent storage — `volumeClaimTemplates`

Instead of a `volumes:` section, the StatefulSet declares a **template**. For every pod it creates, Kubernetes spins up a matching PersistentVolumeClaim — named `postgres-data-postgres-0`, `postgres-data-postgres-1`, … — and reattaches the *same* claim if that pod is ever recreated. On minikube the default storage class provisions the disk automatically, so nothing else is needed.

Note what is **not** here: no `storageClassName`, no manual `PersistentVolume` manifest. Dynamic provisioning handles it. Also note `ReadWriteOnce` — the disk is attached to exactly one pod, which is correct for a database.

### The manifests

| File | Kind | Role |
|------|------|------|
| `07-backend-app/secret-backend-db.yaml` | Secret | DB credentials shared by both workloads |
| `07-backend-app/service-postgres.yaml` | Service (headless) | Per-pod DNS for the StatefulSet |
| `07-backend-app/statefulset-postgres.yaml` | StatefulSet | PostgreSQL + PVC template |
| `07-backend-app/deployment-backend.yaml` | Deployment | Flask API, 2 replicas |
| `07-backend-app/service-backend.yaml` | Service (NodePort) | Entry point for browser traffic |

**`07-backend-app/secret-backend-db.yaml`** — same pattern as Phase 5, consumed by *both* controllers:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: backend-db-secret
type: Opaque
stringData:                  # use stringData — kubectl encodes it for you
  DB_USER: appuser
  DB_PASSWORD: supersecret
```

**`07-backend-app/statefulset-postgres.yaml`** — the new piece of the puzzle:

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
  labels:
    app: postgres
spec:
  serviceName: postgres-service   # links each pod to its own DNS record
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
        - name: postgres
          image: postgres:16
          ports:
            - containerPort: 5432
          env:
            - name: POSTGRES_DB
              value: appdb
            - name: POSTGRES_USER
              valueFrom:
                secretKeyRef:
                  name: backend-db-secret
                  key: DB_USER
            - name: POSTGRES_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: backend-db-secret
                  key: DB_PASSWORD
            - name: PGDATA
              value: /var/lib/postgresql/data/pgdata   # subdirectory — the mount point must be empty
          volumeMounts:
            - name: postgres-data
              mountPath: /var/lib/postgresql/data
          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"
            limits:
              cpu: "250m"
              memory: "256Mi"
  volumeClaimTemplates:            # one PVC per pod: postgres-data-postgres-0
    - metadata:
        name: postgres-data
      spec:
        accessModes:
          - ReadWriteOnce
        resources:
          requests:
            storage: 1Gi
```

Two details worth calling out:

- **`serviceName`** must match the headless Service — without it, the per-pod DNS records don't exist.
- **`PGDATA`** points one level *inside* the mount. PostgreSQL refuses to initialize a non-empty data directory, and Kubernetes mounts are never empty.

**`07-backend-app/deployment-backend.yaml`** — a Deployment like Phase 3, but wired to the database:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend-deploy
  labels:
    app: backend
spec:
  replicas: 2
  selector:
    matchLabels:
      app: backend
  template:
    metadata:
      labels:
        app: backend
    spec:
      containers:
        - name: backend
          image: afreydev/backend-k8s:latest
          imagePullPolicy: IfNotPresent   # works with the registry AND with minikube image load
          ports:
            - containerPort: 5000
          env:
            - name: DB_HOST
              value: postgres-service      # Service DNS name — stable, unlike pod IPs
            - name: DB_PORT
              value: "5432"
            - name: DB_NAME
              value: appdb
            - name: DB_USER
              valueFrom:
                secretKeyRef:
                  name: backend-db-secret
                  key: DB_USER
            - name: DB_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: backend-db-secret
                  key: DB_PASSWORD
          resources:
            requests:
              cpu: "50m"
              memory: "64Mi"
            limits:
              cpu: "100m"
              memory: "128Mi"
```

`DB_HOST` is the **Service name**, never a pod IP — the whole point of Phase 4. The two backend pods are disposable; the database address never changes.

**`07-backend-app/service-backend.yaml`**

```yaml
apiVersion: v1
kind: Service
metadata:
  name: backend-service
spec:
  type: NodePort
  selector:
    app: backend                # matches the label on Deployment pods
  ports:
    - protocol: TCP
      port: 80                  # cluster-internal port
      targetPort: 5000          # container port
      nodePort: 30085           # external port (nginx uses 30080, echo uses 30090)
```

### Deploy — order matters

Credentials first, then the database, then the API (it would crash-loop while waiting for a database that doesn't exist yet):

```bash
kubectl apply -f 07-backend-app/secret-backend-db.yaml
kubectl apply -f 07-backend-app/service-postgres.yaml
kubectl apply -f 07-backend-app/statefulset-postgres.yaml

kubectl get statefulsets
kubectl get pods -w          # postgres-0 must be Running and Ready

kubectl apply -f 07-backend-app/deployment-backend.yaml
kubectl apply -f 07-backend-app/service-backend.yaml

kubectl get pods
kubectl get pvc              # one claim per StatefulSet pod
```

**Expected output:**

```
NAME       READY   AGE
postgres   1/1     45s

NAME                              READY   STATUS    RESTARTS   AGE
postgres-0                        1/1     Running   0          40s   ← StatefulSet first
backend-deploy-6c7d9f8b4-x2q9l   1/1     Running   0          8s
backend-deploy-6c7d9f8b4-m4k7p   1/1     Running   0          8s

NAME                                STATUS   VOLUME                                     CAPACITY
postgres-data-postgres-0            Bound    pvc-4b8f2e1c-...                           1Gi     ← created by volumeClaimTemplates
```

### Demo 1 — load balancing you can see

```bash
URL=$(minikube service backend-service --url)

for i in $(seq 1 6); do curl -s $URL/; echo; done
```

**Expected output** — the `served_by` field alternates between the two pod names:

```json
{"database":"postgres-service","message":"Hello from backend-k8s","served_by":"backend-deploy-6c7d9f8b4-x2q9l"}
{"database":"postgres-service","message":"Hello from backend-k8s","served_by":"backend-deploy-6c7d9f8b4-m4k7p"}
{"database":"postgres-service","message":"Hello from backend-k8s","served_by":"backend-deploy-6c7d9f8b4-x2q9l"}
...
```

### Demo 2 — the data survives (the whole point of the StatefulSet)

```bash
# Write a row, then kill the database pod
curl -s -X POST $URL/visits -H 'Content-Type: application/json' -d '{"path":"before-restart"}'

kubectl get pods -w                 # second terminal
kubectl delete pod postgres-0
# postgres-0 comes back with a NEW pod IP — but the SAME PVC

curl -s $URL/visits
```

**Expected output** — the row written before the restart is still there:

```json
[{"created_at":"2026-09-29T21:14:02.113742","hostname":"backend-deploy-6c7d9f8b4-x2q9l","id":4,"path":"before-restart"}, ...]
```

(The `hostname` column records which **backend** pod served the request — the row itself lives in Postgres, which is what survived the restart.)

Now do the same with the stateless tier and watch nothing interesting happen:

```bash
kubectl delete pod -l app=backend     # both backend pods, at once
curl -s $URL/visits                   # data untouched — the database never moved
```

> Key teaching point: a Deployment pod carries no identity and no disk — delete it and the replacement is indistinguishable. A StatefulSet pod carries both. That is the entire difference, and it is why one controller cannot substitute for the other.

### Scaling — ordered, not free-for-all

```bash
kubectl scale statefulset postgres --replicas=2
kubectl get pods -w                  # postgres-1 appears only after postgres-0 is Ready

kubectl scale statefulset postgres --replicas=1   # reverse order: postgres-1 is torn down first
```

 > Note: `replicas: 2` does **not** magically give you a working two-node Postgres cluster — replication has to be configured inside PostgreSQL itself. The StatefulSet provides the *plumbing* (stable names + storage), not the database logic. Worth saying out loud, because it's the most common misconception about StatefulSets.

### Clean up phase 6

```bash
kubectl delete -f 07-backend-app/service-backend.yaml
kubectl delete -f 07-backend-app/deployment-backend.yaml
kubectl delete -f 07-backend-app/statefulset-postgres.yaml
kubectl delete -f 07-backend-app/service-postgres.yaml
kubectl delete -f 07-backend-app/secret-backend-db.yaml

# PVCs are deliberately NOT deleted with the StatefulSet — data outlives the pod
kubectl get pvc
kubectl delete pvc postgres-data-postgres-0
```

---

## Quick reference — kubectl cheatsheet

```bash
# Apply / delete any resource
kubectl apply -f <file>.yaml
kubectl delete -f <file>.yaml

# Get resources
kubectl get pods / deployments / statefulsets / services / configmaps / secrets / namespaces / pvc

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
| `07-backend-app/secret-backend-db.yaml` | Secret | 6 |
| `07-backend-app/service-postgres.yaml` | Service (headless) | 6 |
| `07-backend-app/statefulset-postgres.yaml` | StatefulSet | 6 |
| `07-backend-app/deployment-backend.yaml` | Deployment | 6 |
| `07-backend-app/service-backend.yaml` | Service (NodePort) | 6 |

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
kubectl delete -f 07-backend-app/service-backend.yaml
kubectl delete -f 07-backend-app/deployment-backend.yaml
kubectl delete -f 07-backend-app/statefulset-postgres.yaml
kubectl delete -f 07-backend-app/service-postgres.yaml
kubectl delete -f 07-backend-app/secret-backend-db.yaml
kubectl delete pvc postgres-data-postgres-0        # PVCs outlive their StatefulSet

# Or wipe the cluster entirely
minikube stop
minikube delete
```

## Get info

```bash
# Get a single field
kubectl get pod <pod-name> -o jsonpath='{.status.podIP}'

# Multiple fields
kubectl get pod <pod-name> -o jsonpath='{.metadata.name} {.status.phase}'

# With a newline
kubectl get pod <pod-name> -o jsonpath='{.metadata.name}{"\n"}'

# Nested field (container image)
kubectl get pod <pod-name> -o jsonpath='{.spec.containers[0].image}'

# All container names in a pod
kubectl get pod <pod-name> -o jsonpath='{.spec.containers[*].name}'

# Loop over items (all pods)
kubectl get pods -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.podIP}{"\n"}{end}'
```

---

