# brisakube

Kubernetes cluster on Hetzner Cloud using [kube-hetzner](https://github.com/kube-hetzner/terraform-hcloud-kube-hetzner).

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

## Cluster

- 1 control plane node (`cpx11`, `nbg1`)
- 2 worker nodes (`cpx21`, `nbg1`)
- Ingress: nginx with Hetzner Load Balancer
