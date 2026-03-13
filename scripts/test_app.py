#!/usr/bin/env python3
"""Deploy a test app to the cluster and verify it's reachable via the LB IP.

Usage:
    python scripts/test_app.py            # deploy, test, then prompt to cleanup
    python scripts/test_app.py --cleanup  # remove test app resources
    python scripts/test_app.py --keep     # deploy and test without cleanup prompt

Requires KUBECONFIG to be set or k3s_kubeconfig.yaml to exist in the repo root.
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
MANIFESTS = REPO_ROOT / "test-app" / "manifests.yaml"
HOST_HEADER = "hello.test"
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
    ips = [ip for ip in out.split() if "." in ip]  # prefer IPv4
    if not ips:
        print("Error: could not find LB external IP")
        sys.exit(1)
    return ips[0]


def deploy():
    print("Applying test-app manifests...")
    kubectl("apply", "-f", str(MANIFESTS), capture=False)
    print("Waiting for deployment to be ready...")
    kubectl("wait", "deployment/hello", "--for=condition=Available", "--timeout=120s", capture=False)


def test(lb_ip):
    url = f"http://{lb_ip}"
    print(f"\nTesting: GET {url} (Host: {HOST_HEADER})")
    req = urllib.request.Request(url, headers={"Host": HOST_HEADER})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = resp.read().decode()
                print(f"HTTP {resp.status} OK")
                if "hello" in body.lower() or "nginx" in body.lower():
                    print("Response looks good.")
                else:
                    print(f"Response body (first 200 chars): {body[:200]}")
                return True
        except urllib.error.URLError as e:
            print(f"Attempt {attempt + 1}/5 failed: {e.reason} — retrying in 5s...")
            time.sleep(5)
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

    deploy()
    lb_ip = get_lb_ip()
    print(f"LB IP: {lb_ip}")
    success = test(lb_ip)

    if not args.keep:
        answer = input("\nClean up test resources? [Y/n] ").strip().lower()
        if answer != "n":
            cleanup()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
