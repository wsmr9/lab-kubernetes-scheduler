import argparse, math, time
from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException   # Compatible con kubernetes==2.0.0


# ============================================================
# Load Kubernetes API client
# ============================================================
def load_client(kubeconfig=None):
    if kubeconfig:
        config.load_kube_config(kubeconfig)
    else:
        config.load_incluster_config()
    return client.CoreV1Api()


# ============================================================
# Full taints/tolerations function
# ============================================================
def node_tolerates_taints(node, pod):
    taints = node.spec.taints or []
    tolerations = pod.spec.tolerations or []

    if not taints:
        return True

    for taint in taints:
        tolerated = any(
            tol.key == taint.key and
            (tol.effect == taint.effect or tol.effect is None) and
            (tol.operator == "Exists" or tol.value == taint.value)
            for tol in tolerations
        )

        if not tolerated:
            return False

    return True


# ============================================================
# Bind pod with exponential backoff
# ============================================================
def bind_pod(api, pod, node_name: str):
    target = client.V1ObjectReference(kind="Node", name=node_name)
    meta = client.V1ObjectMeta(name=pod.metadata.name)
    body = client.V1Binding(target=target, metadata=meta)

    delay = 0.5  # initial backoff delay

    for attempt in range(5):  # retry 5 times
        try:
            print(f"[bind] Attempt {attempt + 1} binding {pod.metadata.name} -> {node_name}")

            api.create_namespaced_binding(pod.metadata.namespace, body)

            print(f"[bind] SUCCESS {pod.metadata.name} -> {node_name}")
            return

        except ApiException as e:

            if e.status == 409:
                print(f"[bind] SKIP {pod.metadata.name}: already assigned (409)")
                return

            if e.status in (500, 503):
                print(f"[bind] RETRY {pod.metadata.name}: transient error {e.status}, waiting {delay}s...")
                time.sleep(delay)
                delay *= 2
                continue

            print(f"[bind] ERROR {pod.metadata.name}: {e}")
            raise

    print(f"[bind] FAILED after retries: {pod.metadata.name}")


# ============================================================
# Node selection (labels + taints/tolerations + spread)
# ============================================================
def choose_node(api: client.CoreV1Api, pod) -> str:

    # 1) Label filter env=prod
    all_nodes = api.list_node().items
    if not all_nodes:
        raise RuntimeError("No nodes available")

    nodes = [
        n for n in all_nodes
        if n.metadata.labels and n.metadata.labels.get("env") == "prod"
    ]

    if not nodes:
        raise RuntimeError("No nodes match label env=prod")

    # 2) Taints & tolerations
    nodes = [n for n in nodes if node_tolerates_taints(n, pod)]
    if not nodes:
        raise RuntimeError("No nodes pass taint/toleration check")

    # 3) Spread policy
    pods = api.list_pod_for_all_namespaces().items
    pod_label = pod.metadata.labels.get("app") if pod.metadata.labels else None

    best_node = None
    best_score = math.inf

    print(f"\n--- Evaluating nodes for pod: {pod.metadata.name} ---")

    for n in nodes:
        node_name = n.metadata.name

        total_pods = sum(1 for p in pods if p.spec.node_name == node_name)

        similar = 0
        if pod_label:
            similar = sum(
                1 for p in pods
                if p.spec.node_name == node_name and
                   p.metadata.labels and
                   p.metadata.labels.get("app") == pod_label
            )

        score = total_pods + (similar * 2)

        print(f"Node {node_name}: total={total_pods}, similar={similar}, score={score}")

        if score < best_score:
            best_score = score
            best_node = node_name

    print(f"Selecting {best_node} with score={best_score}\n")

    return best_node


# ============================================================
# Main watch-loop scheduler
# ============================================================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scheduler-name", default="my-scheduler")
    parser.add_argument("--kubeconfig", default=None)
    args = parser.parse_args()

    api = load_client(args.kubeconfig)

    print(f"[watch] scheduler starting… name={args.scheduler_name}")
    w = watch.Watch()

    for evt in w.stream(client.CoreV1Api().list_pod_for_all_namespaces,
                        _request_timeout=60):

        pod = evt["object"]
        if pod is None or not hasattr(pod, "spec"):
            continue

        if not pod.spec.node_name and pod.spec.scheduler_name == args.scheduler_name:

            try:
                node = choose_node(api, pod)
                bind_pod(api, pod, node)
                print(f"Bound {pod.metadata.namespace}/{pod.metadata.name} -> {node}")

            except ApiException as e:
                if e.status == 409:
                    print(f"[skip] Pod {pod.metadata.name} already assigned.")
                else:
                    print(f"[ERROR] Failed to bind {pod.metadata.name}: {e}")


if __name__ == "__main__":
    main()
