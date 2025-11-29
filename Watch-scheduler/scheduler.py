import argparse, math
from kubernetes import client, config, watch
from kubernetes.client.models import V1Taint, V1Toleration

def load_client(kubeconfig=None):
    if kubeconfig:
        config.load_kube_config(kubeconfig)
    else:
        config.load_incluster_config()
    return client.CoreV1Api()

def bind_pod(api: client.CoreV1Api, pod, node_name: str):
    target = client.V1ObjectReference(kind="Node", name=node_name)
    meta = client.V1ObjectMeta(name=pod.metadata.name)
    body = client.V1Binding(target=target, metadata=meta)
    api.create_namespaced_binding(pod.metadata.namespace, body)

def choose_node(api: client.CoreV1Api, pod) -> str:
    nodes = api.list_node().items
    pods = api.list_pod_for_all_namespaces().items

    nodes = [ n for n in api.list_node().items if "env" in (n.metadata.labels or {}) and
        n.metadata.labels["env"] == "prod"]

    eligible_nodes = [n for n in nodes if node_tolerates_taints(n, pod)]
    if not eligible_nodes:
        raise RuntimeError("No nodes available")
    min_cnt = math.inf
    pick = nodes[0].metadata.name
    for n in eligible_nodes:
        cnt = sum(1 for p in pods if p.spec.node_name == n.metadata.name)
        if cnt < min_cnt:
            min_cnt = cnt
            pick = n.metadata.name
    return pick

def check_toleration(taint: V1Taint, tol: V1Toleration) -> bool:
    if tol.operator == "Exists" and (tol.key is None or tol.key == ""):
        return True
    if tol.key != taint.key:
        return False
    if tol.effect is not None and tol.effect != taint.effect:
        return False
    if tol.operator == "Exists":
        return True
    if tol.operator is None or tol.operator == "Equal":
        return tol.value == taint.value
    return False

def node_tolerates_taints(node, pod):
    taints = node.spec.taints or []
    tolerations = pod.spec.tolerations or []
    if not taints:
        return True
    for taint in taints:
        tolerated = any(check_toleration(taint, tol) for tol in tolerations)
        if not tolerated:
            return False
    return True

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scheduler-name", default="my-scheduler")
    parser.add_argument("--kubeconfig", default=None)
    args = parser.parse_args()

    api = load_client(args.kubeconfig)

    print(f"[watch] scheduler starting… name={args.scheduler_name}")
    w = watch.Watch()
    # Stream Pod events and bind unscheduled Pods, also with request_timeout to avoid hanging indefinitely (polling interval).
    for evt in w.stream(api.list_pod_for_all_namespaces, _request_timeout=60):
        obj = evt['object']
        if obj is None or not hasattr(obj, 'spec'):
            continue
        if obj.spec.node_name is None and obj.spec.scheduler_name == args.scheduler_name:
            node = choose_node(api, obj)
            bind_pod(api, obj, node)
            print(f"Bound by watch {obj.metadata.namespace}/{obj.metadata.name} -> {node}")

if __name__ == "__main__":
    main()
 