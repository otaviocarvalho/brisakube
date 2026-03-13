# brisakube

Kubernetes cluster on Hetzner Cloud using [kube-hetzner](https://github.com/kube-hetzner/terraform-hcloud-kube-hetzner).

## Infrastructure

All resources in region **Nuremberg (nbg1)**.

### Nodes

| Role | Count | Type | vCPU | RAM | Disk | Private IP |
|------|-------|------|------|-----|------|------------|
| Control plane | 1 | cx23 | 2 | 4 GB | 40 GB | 10.255.0.101 |
| Worker | 2 | cx33 | 4 | 8 GB | 80 GB | 10.0.0.101–102 |

### Networking

- Private network: `10.0.0.0/8`
  - Control plane subnet: `10.255.0.0/16`
  - Agent subnet: `10.0.0.0/16`
- Firewall: SSH (22), Kube API (6443), ICMP inbound; HTTP/S, DNS, NTP outbound

### Load Balancer

- Type: `lb11` (Hetzner), targets agent nodes only
- Used for nginx ingress — public traffic hits the LB, which routes to worker nodes
- LB private IP: `10.0.255.254`

### k3s / Kubernetes

- Module: [kube-hetzner](https://registry.terraform.io/modules/kube-hetzner/kube-hetzner/hcloud) v2.19.2
- CNI: Flannel (default)
- Ingress: nginx
- Cloud controller: Hetzner CCM (manages LB and node IPs)
- Storage: Hetzner CSI
- OS: MicroOS (auto-updated, immutable)
- Kubeconfig saved locally as `k3s_kubeconfig.yaml` after apply

## Setup

1. Copy the example config and fill in your credentials:
   ```bash
   cp kube.tf.brisa.example kube.tf
   # Edit kube.tf and set hcloud_token
   ```

2. Initialize and apply:
   ```bash
   terraform init
   terraform apply
   ```

3. Use the cluster:
   ```bash
   export KUBECONFIG=./k3s_kubeconfig.yaml
   kubectl get nodes
   ```

## Scripts

### `scripts/test_app.py`

Deploys a test app (`test-app/manifests.yaml`) to the cluster, waits for it to be ready, hits it via the LB IP, and optionally cleans up.

```bash
python scripts/test_app.py           # deploy, test, prompt for cleanup
python scripts/test_app.py --keep    # deploy and test, leave resources
python scripts/test_app.py --cleanup # remove test app resources
```

Reads kubeconfig from `$KUBECONFIG` or `k3s_kubeconfig.yaml` in the repo root.

### `scripts/list_server_types.py`

Lists all available Hetzner server types with specs and monthly prices, sorted by cost. Useful for choosing or comparing instance types.

```bash
HCLOUD_TOKEN=xxx python scripts/list_server_types.py
```
