from app.dependencies import (
    get_k8s_client,
    get_logs_service,
    get_metrics_service,
    get_shell_service,
    get_topology_service,
)
from tools import logs, metrics

def main():
    print("=== topology ===")
    topo = get_topology_service()
    print(topo.get_cluster_overview())

    print("=== shell policy ===")
    shell = get_shell_service()
    print(shell.get_shell_policy())

    print("=== kubectl ===")
    print(shell.exec_kubectl("kubectl get pods"))

    print("=== pods ===")
    print(get_shell_service().exec_kubectl("kubectl get pods -A"))

    print("=== get svc ===")
    print(get_shell_service().exec_kubectl("kubectl get svc -A"))

    print("=== topology ===")
    topo = get_topology_service()
    print(topo.get_cluster_overview(namespace="kube-system"))
    print(topo.get_cluster_overview(namespace="local-path-storage"))


    print("=== logs ===")
    logs = get_logs_service()

    print(logs.get_pod_logs(
        "coredns-7d764666f9-q5rkz",
        namespace="kube-system",
        important_only=False,
    ))

    print(logs.summarize_service_logs(
        "kube-dns",
        namespace="kube-system",
    ))


    print("URL URL URL")
    from app.config import get_settings
    print(get_settings().prometheus_url)

    print("=== metrics ===")
    metrics = get_metrics_service()

    print(metrics.get_pod_metrics(
        "coredns-7d764666f9-q5rkz",
        namespace="kube-system",
    ))

    print(metrics.get_service_metrics(
        "kube-dns",
        namespace="kube-system",
    ))

    print("=== topology ===")
    topo = get_topology_service()
    print(topo.get_pods_from_service("kube-dns", namespace="kube-system"))
    print(topo.get_services_from_pod("coredns-7d764666f9-q5rkz", namespace="kube-system"))



if __name__ == "__main__":
    main()