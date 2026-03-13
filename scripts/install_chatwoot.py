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


SMTP_HOST = "smtp.resend.com"
SMTP_PORT = "587"
SMTP_USERNAME = "resend"
MAILER_SENDER_EMAIL = "chatwoot@meliegturo.resend.app"

REQUIRED_SECRETS = {
    "postgres_password":           lambda: secrets.token_urlsafe(32),
    "postgres_superuser_password": lambda: secrets.token_urlsafe(32),
    "redis_password":              lambda: secrets.token_urlsafe(32),
    "secret_key_base":             lambda: secrets.token_hex(64),
    "resend_api_key":              lambda: (_ for _ in ()).throw(RuntimeError(
        "resend_api_key not set — add it manually to chatwoot/.secrets"
    )),
}


def load_or_generate_secrets() -> dict:
    data = {}
    if SECRETS_FILE.exists():
        with open(SECRETS_FILE) as f:
            data = json.load(f)

    missing = [k for k in REQUIRED_SECRETS if k not in data]
    if missing:
        for k in missing:
            data[k] = REQUIRED_SECRETS[k]()
        SECRETS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SECRETS_FILE, "w") as f:
            json.dump(data, f, indent=2)
        os.chmod(SECRETS_FILE, 0o600)
        action = "Generated" if len(missing) == len(REQUIRED_SECRETS) else "Updated"
        print(f"{action} chatwoot/.secrets")
    else:
        print("Loaded existing secrets from chatwoot/.secrets")
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
        "--set", f"auth.postgresPassword={s['postgres_superuser_password']}",
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

    postgres_host = f"{POSTGRES_RELEASE}-postgresql.{NAMESPACE}.svc.cluster.local"
    redis_host = f"{REDIS_RELEASE}-master.{NAMESPACE}.svc.cluster.local"
    redis_url = f"redis://:{s['redis_password']}@{redis_host}:6379"

    # --- Chatwoot ---
    run([
        "helm", "upgrade", "--install", CHATWOOT_RELEASE, "chatwoot/chatwoot",
        "-n", NAMESPACE,
        "-f", str(REPO_ROOT / "chatwoot" / "chatwoot-values.yaml"),
        "--set", f"postgresql.postgresqlHost={postgres_host}",
        "--set", f"postgresql.postgresqlPort=5432",
        "--set", f"postgresql.auth.username=chatwoot",
        "--set", f"postgresql.auth.postgresPassword={s['postgres_password']}",
        "--set", f"postgresql.auth.database=chatwoot_production",
        "--set", f"redis.host={redis_host}",
        "--set", f"redis.port=6379",
        "--set", f"redis.password={s['redis_password']}",
        # Override REDIS_URL explicitly: the chart template uses $(REDIS_PASSWORD) which
        # is not substituted inside a Kubernetes Secret (only works in pod env[] entries).
        "--set", f"env.REDIS_URL={redis_url}",
        "--set", f"env.SECRET_KEY_BASE={s['secret_key_base']}",
        "--set", f"env.SMTP_ADDRESS={SMTP_HOST}",
        "--set", f"env.SMTP_PORT={SMTP_PORT}",
        "--set", f"env.SMTP_USERNAME={SMTP_USERNAME}",
        "--set", f"env.SMTP_PASSWORD={s['resend_api_key']}",
        "--set", f"env.SMTP_AUTHENTICATION=plain",
        "--set", f"env.SMTP_ENABLE_STARTTLS_AUTO=true",
        "--set", f"env.MAILER_SENDER_EMAIL={MAILER_SENDER_EMAIL}",
    ])

    wait_for_deployment(f"{CHATWOOT_RELEASE}-web")

    print()
    print("=" * 60)
    print(f"Chatwoot is available at:  https://{HOSTNAME}")
    print("=" * 60)


def uninstall():
    for release in [CHATWOOT_RELEASE, REDIS_RELEASE, POSTGRES_RELEASE]:
        run(["helm", "uninstall", release, "-n", NAMESPACE], check=False)
    run(["kubectl", "delete", "job", "-l", f"release={CHATWOOT_RELEASE}", "-n", NAMESPACE], check=False)
    run(["kubectl", "delete", "pvc", "--all", "-n", NAMESPACE], check=False)
    print("All releases, jobs, and PVCs deleted.")


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
