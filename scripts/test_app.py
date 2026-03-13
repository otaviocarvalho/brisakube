#!/usr/bin/env python3
"""Deploy a test app to the cluster and verify it's reachable via HTTPS (sslip.io + Let's Encrypt).

Usage:
    python scripts/test_app.py            # deploy, test, then prompt to cleanup
    python scripts/test_app.py --cleanup  # remove test app resources
    python scripts/test_app.py --keep     # deploy and test without cleanup prompt

Requires KUBECONFIG to be set or k3s_kubeconfig.yaml to exist in the repo root.
"""

import argparse
import os
import subprocess
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
MANIFESTS = REPO_ROOT / "test-app" / "manifests.yaml"
CLUSTER_ISSUER = REPO_ROOT / "cert-manager" / "cluster-issuer.yaml"
KUBECONFIG = os.environ.get("KUBECONFIG", str(REPO_ROOT / "k3s_kubeconfig.yaml"))


def kubectl(*args, capture=True):
    cmd = ["kubectl", "--kubeconfig", KUBECONFIG, *args]
    result = subprocess.run(cmd, capture_output=capture, text=True)
    if result.returncode != 0:
        if capture:
            print(f"Error: {result.stderr.strip()}")
        sys.exit(1)
    return result.stdout.strip() if capture else ""


def get_lb_ip():
    out = kubectl("get", "svc", "-n", "nginx",
                  "nginx-ingress-nginx-controller",
                  "-o", "jsonpath={.status.loadBalancer.ingress[*].ip}")
    ips = [ip for ip in out.split() if "." in ip]
    if not ips:
        print("Error: could not find LB external IP")
        sys.exit(1)
    return ips[0]


def sslip_domain(ip):
    return ip.replace(".", "-") + ".sslip.io"


def setup_cert_manager():
    print("Applying ClusterIssuer...")
    kubectl("apply", "-f", str(CLUSTER_ISSUER), capture=False)


def deploy():
    print("Applying test-app manifests...")
    kubectl("apply", "-f", str(MANIFESTS), capture=False)
    print("Waiting for deployment to be ready...")
    kubectl("wait", "deployment/hello", "--for=condition=Available", "--timeout=120s", capture=False)


def wait_for_cert(domain, timeout=120):
    print(f"Waiting for TLS certificate for {domain}...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        out = kubectl("get", "certificate", "hello-tls",
                      "-o", "jsonpath={.status.conditions[?(@.type=='Ready')].status}")
        if out == "True":
            print("Certificate is ready.")
            return True
        time.sleep(5)
    print("Warning: certificate not ready yet (may still be provisioning).")
    return False


def test_https(domain):
    url = f"https://{domain}"
    print(f"\nTesting: GET {url}")
    for attempt in range(6):
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                body = resp.read().decode()
                print(f"HTTP {resp.status} OK — HTTPS is working.")
                return True
        except urllib.error.URLError as e:
            reason = getattr(e, "reason", str(e))
            print(f"Attempt {attempt + 1}/6 failed: {reason} — retrying in 10s...")
            time.sleep(10)
    print("All attempts failed.")
    return False


def cleanup():
    print("\nCleaning up test-app resources...")
    kubectl("delete", "-f", str(MANIFESTS), "--ignore-not-found", capture=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cleanup", action="store_true", help="Remove test app resources and exit")
    parser.add_argument("--keep", action="store_true", help="Skip cleanup prompt after test")
    args = parser.parse_args()

    if args.cleanup:
        cleanup()
        return

    lb_ip = get_lb_ip()
    domain = sslip_domain(lb_ip)
    print(f"LB IP: {lb_ip}")
    print(f"Domain: {domain}")

    setup_cert_manager()
    deploy()
    wait_for_cert(domain)
    success = test_https(domain)

    if success:
        print(f"\nOpen in browser: https://{domain}")

    if not args.keep:
        answer = input("\nClean up test resources? [Y/n] ").strip().lower()
        if answer != "n":
            cleanup()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
