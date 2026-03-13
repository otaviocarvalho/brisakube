#!/usr/bin/env python3
"""Install Chatwoot on brisakube with PostgreSQL + Redis via Helm."""

import argparse
import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SECRETS_FILE = REPO_ROOT / "chatwoot" / ".secrets"
KUBECONFIG = REPO_ROOT / "k3s_kubeconfig.yaml"
HOSTNAME = "chat.46-225-43-58.sslip.io"

POSTGRES_RELEASE = "chatwoot-postgres"
REDIS_RELEASE = "chatwoot-redis"
CHATWOOT_RELEASE = "chatwoot"
NAMESPACE = "default"


def run(cmd: list[str], check: bool = True, **kwargs) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["KUBECONFIG"] = str(KUBECONFIG)
    print(f"+ {' '.join(cmd)}")
    return subprocess.run(cmd, check=check, env=env, **kwargs)


def load_or_generate_secrets() -> dict:
    if SECRETS_FILE.exists():
        with open(SECRETS_FILE) as f:
            data = json.load(f)
        print("Loaded existing secrets from chatwoot/.secrets")
    else:
        data = {
            "postgres_password": secrets.token_urlsafe(32),
            "redis_password": secrets.token_urlsafe(32),
            "secret_key_base": secrets.token_hex(64),
        }
        SECRETS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SECRETS_FILE, "w") as f:
            json.dump(data, f, indent=2)
        os.chmod(SECRETS_FILE, 0o600)
        print("Generated new secrets → chatwoot/.secrets")
    return data


def setup_helm_repos():
    run(["helm", "repo", "add", "bitnami", "https://charts.bitnami.com/bitnami"])
    run(["helm", "repo", "add", "chatwoot", "https://chatwoot.github.io/charts"])
    run(["helm", "repo", "update"])


def wait_for_deployment(name: str, namespace: str = NAMESPACE, timeout: int = 300):
    print(f"Waiting for deployment {name} to be ready (timeout {timeout}s)…")
    run([
        "kubectl", "rollout", "status", f"deployment/{name}",
        "-n", namespace,
        f"--timeout={timeout}s",
    ])


def wait_for_statefulset(name: str, namespace: str = NAMESPACE, timeout: int = 300):
    print(f"Waiting for statefulset {name} to be ready (timeout {timeout}s)…")
    run([
        "kubectl", "rollout", "status", f"statefulset/{name}",
        "-n", namespace,
        f"--timeout={timeout}s",
    ])


def install(s: dict):
    setup_helm_repos()

    # --- PostgreSQL ---
    run([
        "helm", "upgrade", "--install", POSTGRES_RELEASE, "bitnami/postgresql",
        "-n", NAMESPACE, "--create-namespace",
        "-f", str(REPO_ROOT / "chatwoot" / "postgres-values.yaml"),
        "--set", f"auth.password={s['postgres_password']}",
    ])

    # --- Redis ---
    run([
        "helm", "upgrade", "--install", REDIS_RELEASE, "bitnami/redis",
        "-n", NAMESPACE,
        "-f", str(REPO_ROOT / "chatwoot" / "redis-values.yaml"),
        "--set", f"auth.password={s['redis_password']}",
    ])

    # Wait for backing services before deploying Chatwoot
    wait_for_statefulset(f"{POSTGRES_RELEASE}-postgresql")
    wait_for_statefulset(f"{REDIS_RELEASE}-master")

    postgres_url = (
        f"postgresql://chatwoot:{s['postgres_password']}"
        f"@{POSTGRES_RELEASE}-postgresql.{NAMESPACE}.svc.cluster.local:5432/chatwoot_production"
    )
    redis_url = (
        f"redis://:{s['redis_password']}"
        f"@{REDIS_RELEASE}-master.{NAMESPACE}.svc.cluster.local:6379"
    )

    # --- Chatwoot ---
    run([
        "helm", "upgrade", "--install", CHATWOOT_RELEASE, "chatwoot/chatwoot",
        "-n", NAMESPACE,
        "-f", str(REPO_ROOT / "chatwoot" / "chatwoot-values.yaml"),
        "--set", f"postgresql.url={postgres_url}",
        "--set", f"redis.url={redis_url}",
        "--set", f"rails.secretKeyBase={s['secret_key_base']}",
    ])

    wait_for_deployment(f"{CHATWOOT_RELEASE}-web")

    print()
    print("=" * 60)
    print(f"Chatwoot is available at:  https://{HOSTNAME}")
    print("=" * 60)


def uninstall():
    for release in [CHATWOOT_RELEASE, REDIS_RELEASE, POSTGRES_RELEASE]:
        run(["helm", "uninstall", release, "-n", NAMESPACE], check=False)
    print("All releases uninstalled.")
    print("PersistentVolumeClaims are NOT deleted automatically.")
    print("Run: kubectl delete pvc --all -n default   (if you want a clean slate)")


def main():
    parser = argparse.ArgumentParser(description="Install or uninstall Chatwoot on brisakube")
    parser.add_argument("--uninstall", action="store_true", help="Tear down all three Helm releases")
    args = parser.parse_args()

    if not KUBECONFIG.exists():
        print(f"ERROR: kubeconfig not found at {KUBECONFIG}", file=sys.stderr)
        sys.exit(1)

    if args.uninstall:
        uninstall()
    else:
        s = load_or_generate_secrets()
        install(s)


if __name__ == "__main__":
    main()
