# Chatwoot on brisakube

Chatwoot deployed via Helm with external PostgreSQL and Redis on Hetzner volumes.

- **URL**: https://chat.46-225-43-58.sslip.io
- **Namespace**: `default`
- **Helm releases**: `chatwoot-postgres`, `chatwoot-redis`, `chatwoot`

## Install / Uninstall

```bash
export KUBECONFIG=./k3s_kubeconfig.yaml

# Install
python scripts/install_chatwoot.py

# Tear down (PVCs not deleted automatically)
python scripts/install_chatwoot.py --uninstall
```

Secrets (passwords, secret key base) are auto-generated on first run and saved to
`chatwoot/.secrets` (gitignored). Re-runs reuse them.

---

## Get passwords

```bash
export KUBECONFIG=./k3s_kubeconfig.yaml

# PostgreSQL
export POSTGRES_PASSWORD=$(kubectl get secret --namespace default chatwoot-postgres-postgresql \
  -o jsonpath="{.data.password}" | base64 -d)

# Redis
export REDIS_PASSWORD=$(kubectl get secret --namespace default chatwoot-redis \
  -o jsonpath="{.data.redis-password}" | base64 -d)
```

Or just read `chatwoot/.secrets` directly (JSON).

---

## Port-forward for local access

### PostgreSQL (port 5432)

```bash
kubectl port-forward --namespace default svc/chatwoot-postgres-postgresql 5432:5432 &

# Connect with psql
PGPASSWORD=$POSTGRES_PASSWORD psql -h 127.0.0.1 -U chatwoot -d chatwoot_production
```

### Redis (port 6379)

```bash
kubectl port-forward --namespace default svc/chatwoot-redis-master 6379:6379 &

# Connect with redis-cli
REDISCLI_AUTH=$REDIS_PASSWORD redis-cli -h 127.0.0.1 -p 6379
```

---

## Resource limits (production note)

The Bitnami charts warn when `resources` sections are not set. For production, add explicit
requests and limits to each values file. Example:

```yaml
# postgres-values.yaml or redis-values.yaml
primary:
  resources:
    requests:
      cpu: 250m
      memory: 256Mi
    limits:
      cpu: 1000m
      memory: 512Mi
```

**Why this matters** ([Kubernetes docs](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/)):

- **Requests** tell the scheduler which node can fit the pod. Always set them.
- **Limits** cap CPU (via throttling) and memory (OOM kill if exceeded). Set them to
  prevent one workload starving others.
- Omitting both means the pod runs with `BestEffort` QoS and is the first evicted under
  node pressure.

Right-size values based on actual usage — use `kubectl top pods` to observe real
consumption before committing to limits.

---

## Check status

```bash
export KUBECONFIG=./k3s_kubeconfig.yaml

kubectl get pods
kubectl get pvc
kubectl get certificate          # chatwoot-tls should be Ready
kubectl get ingress
```
