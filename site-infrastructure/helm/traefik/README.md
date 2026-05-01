# Traefik Configuration

This directory contains Helm values for Traefik, the ingress controller used by OpenHands staging environments. Two routing strategies are supported:

1. **Path-based routing**: All services on a single domain with different URL paths
2. **Subdomain-based routing**: Each service on its own subdomain

## Installation

```bash
# Add Traefik Helm repository
helm repo add traefik https://traefik.github.io/charts
helm repo update

# For path-based routing
helm install traefik traefik/traefik \
  --namespace traefik \
  --create-namespace \
  -f values.yaml \
  -f values-path-routing.yaml

# For subdomain-based routing
helm install traefik traefik/traefik \
  --namespace traefik \
  --create-namespace \
  -f values.yaml \
  -f values-subdomain-routing.yaml
```

## Routing Strategies

### Path-Based Routing

All traffic goes to a single domain, with services differentiated by URL path:

```
domain.com/           → openhands-service (UI)
domain.com/api/       → openhands-service (API)
domain.com/runtime/   → runtime-api
domain.com/auth/      → keycloak
domain.com/llm/       → litellm
```

**Pros:**
- Single TLS certificate needed
- Simpler DNS setup (one A record)
- Works with HTTP-01 ACME challenges

**Cons:**
- Requires path stripping middlewares
- Some applications may have path conflicts
- Less isolation between services

After installing Traefik, apply the middlewares:

```bash
kubectl create namespace openhands
kubectl apply -f middlewares-path-routing.yaml
```

### Subdomain-Based Routing

Each service gets its own subdomain:

```
app.domain.com        → openhands-service (UI)
api.domain.com        → openhands-service (API)
runtime.domain.com    → runtime-api
auth.domain.com       → keycloak
llm.domain.com        → litellm
branch.domain.com     → branch deployment
```

**Pros:**
- Clean separation between services
- No path rewriting needed
- Easier to configure per-service settings
- Better for branch-based deployments

**Cons:**
- Requires wildcard TLS certificate (DNS-01 challenge)
- More complex DNS setup (wildcard record)

## Static IP Configuration

For GKE with a static IP from Terraform:

```yaml
service:
  spec:
    loadBalancerIP: "YOUR_STATIC_IP"
  annotations:
    networking.gke.io/load-balancer-type: "External"
```

## OpenHands Ingress Examples

### Path-Based Routing Ingress

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: openhands-ingress
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-production
    traefik.ingress.kubernetes.io/router.middlewares: openhands-security-headers@kubernetescrd
spec:
  ingressClassName: traefik
  tls:
    - hosts:
        - domain.com
      secretName: openhands-tls
  rules:
    - host: domain.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: openhands-service
                port:
                  number: 3000
          - path: /runtime
            pathType: Prefix
            backend:
              service:
                name: runtime-api
                port:
                  number: 8000
```

### Subdomain-Based Routing Ingress

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: openhands-app-ingress
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-dns
spec:
  ingressClassName: traefik
  tls:
    - hosts:
        - "*.domain.com"
      secretName: openhands-wildcard-tls
  rules:
    - host: app.domain.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: openhands-service
                port:
                  number: 3000
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: openhands-runtime-ingress
spec:
  ingressClassName: traefik
  tls:
    - hosts:
        - "*.domain.com"
      secretName: openhands-wildcard-tls
  rules:
    - host: runtime.domain.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: runtime-api
                port:
                  number: 8000
```

## Troubleshooting

```bash
# Check Traefik logs
kubectl logs -n traefik -l app.kubernetes.io/name=traefik

# Access Traefik dashboard (port-forward)
kubectl port-forward -n traefik svc/traefik 9000:9000
# Then open http://localhost:9000/dashboard/

# List IngressRoutes
kubectl get ingressroute -A

# List Middlewares
kubectl get middleware -A
```
