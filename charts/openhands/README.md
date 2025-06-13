# Openhands-all Helm Chart

This Helm chart deploys the complete OpenHands stack, including all required dependencies. It's designed to be a one-stop solution for deploying OpenHands in a Kubernetes environment.

## Prerequisites

- Kubernetes 1.19+
- Helm 3.2.0+
- Ingress controller (recommended: Traefik)
- A TLS solution for certificates (recommended: cert-manager)


## Installation
### Initial setup
1. Clone the repository and navigate to the chart directory:
   ```bash
   git clone https://github.com/All-Hands-AI/openhands-cloud
   cd openhands-cloud/charts/openhands
   ```

2. Create the openhands namespace:
   ```bash
   # Create namespace (if you want to use a different namespace, you will need to change it in all the commands that follow)
   kubectl create namespace openhands
   ```

3. Create a secret for your LLM
  ```bash
  kubectl create secret generic litellm-env-secrets -n openhands \
     --from-literal=ANTHROPIC_API_KEY=<your-anthropic-api-key>
  ```

4. Create required secrets:
   ```bash

   # For a basic installation, we'll reuse this secret for several components. You can create a different secret for each component if you prefer.
   export GLOBAL_SECRET=`head /dev/urandom | tr -dc A-Za-z0-9 | head -c 32`

   # Create JWT secret for sessions
   kubectl create secret generic jwt-secret -n openhands --from-literal=jwt-secret=$GLOBAL_SECRET

   # Create Keycloak realm secret
   kubectl create secret generic keycloak-realm -n openhands \
     --from-literal=realm-name=openhands \
     --from-literal=provider-name=email \
     --from-literal=server-url=http://keycloak \
     --from-literal=client-id=openhands \
     --from-literal=client-secret=$GLOBAL_SECRET

   kubectl create secret generic keycloak-admin -n openhands \
     --from-literal=admin-password=$GLOBAL_SECRET

   # Create PostgreSQL password secret
   kubectl create secret generic postgres-password -n openhands \
     --from-literal=username=postgres \
     --from-literal=password=$GLOBAL_SECRET \
     --from-literal=postgres-password=$GLOBAL_SECRET

   # Create Redis password secret
   kubectl create secret generic redis -n openhands \
     --from-literal=redis-password=$GLOBAL_SECRET

   # Create LiteLLM API key secret
   kubectl create secret generic lite-llm-api-key -n openhands \
     --from-literal=lite-llm-api-key=$GLOBAL_SECRET

   # Create langfuse salt secret
   kubectl create secret generic langfuse-salt -n openhands \
     --from-literal=salt=$GLOBAL_SECRET

   # Create langfuse nextauth secret (for signing JWTs)
   kubectl create secret generic langfuse-nextauth -n openhands \
     --from-literal=nextauth-secret=$GLOBAL_SECRET

   # Create clickhouse password secret
   kubectl create secret generic clickhouse-password -n openhands \
     --from-literal=password=$GLOBAL_SECRET

   # Create two secrets, one that configures runtime-api with a default api key, and another that configures openhands to utilize that api key.
   # There are two secrets because these two workloads can also run in different clusters/namespaces
   kubectl create secret generic default-api-key -n openhands \
     --from-literal=default-api-key=$GLOBAL_SECRET

   kubectl create secret generic sandbox-api-key -n openhands \
     --from-literal=sandbox-api-key=$GLOBAL_SECRET
   ```

You should now have these secrets in the openhands namespace:
```bash
kubectl get secret -n openhands

NAME                  TYPE     DATA   AGE
clickhouse-password   Opaque   1      13s
default-api-key       Opaque   1      7s
jwt-secret            Opaque   1      44s
langfuse-nextauth     Opaque   1      18s
langfuse-salt         Opaque   1      23s
lite-llm-api-key      Opaque   1      28s
litellm-env-secrets   Opaque   1      2m8s
postgres-password     Opaque   3      39s
redis                 Opaque   1      35s
sandbox-api-key       Opaque   1      3s
```

### Install and Set Up OpenHands
Now we can install the helm chart.

```bash
helm dependency update
helm upgrade --install openhands --namespace openhands .
```

This installation won't complete successfully the first time because we need to set up LiteLLM.

After installing the chart initially you will need a manual step to set up
LiteLLM.

> [!NOTE]
> This process will be automated in the near future.

First, port-forward to litellm:

```bash
kubectl port-forward svc/openhands-litellm 4000:4000
```

Next, create a new Team in LiteLLM:
* Navigate to http://localhost:4000/ui in your browser
* login using the username `admin` password $GLOBAL_SECRET (set above)
* go to Teams -> Create New Team
* Name it whatever you want
* Get the team id (e.g. `e0a62105-9c6c-4167-b5be-16674a99d502`), and add it to my-values.yaml:

```yaml
litellm:
  teamId: "<TEAM_ID>"
```

Finally, upgrade the release:
```bash
helm upgrade --install openhands --namespace openhands . -f my-values.yaml
```

You should now be able to see OpenHands running with
```bash
kubectl port-forward svc/openhands-service 3000:3000
```

## Setting up DNS and Ingress
We recommend traefik as an ingress controller. If you're not using traefik,
you can set ingress.class in the objects below.

You'll also need to point your DNS records to the ingress controller's IP address.
In this example, we'll use `openhands.example.com` as the main domain.

First, set up a CNAME record pointing *.openhands.example.com to your ingress
controller's IP address.

Next, enable ingress in your values.yaml:
```yaml
ingress:
  enabled: true
  host: openhands.example.com
keycloak:
  url: https://auth.openhands.example.com
  ingress:
    enabled: true
    hostname: auth.openhands.example.com
runtime-api:
  ingress:
    enabled: true
    hostname: runtimes.openhands.example.com
litellm-helm:
  ingress:
    enabled: true
    hosts:
    - host: llm-proxy.example.com
      paths:
      - path: /
        pathType: Prefix
```

## Enabling GitHub Authentication

The chart includes Keycloak for authentication and supports GitHub OAuth integration. To configure GitHub OAuth:

Similar instructions apply to GitLab authentication.

1. Create a GitHub OAuth App:
   - Go to your GitHub organization settings or personal settings
   - Navigate to "Developer settings" > "OAuth Apps" > "New OAuth App"
   - Set the "Authorization callback URL" to `https://<your-keycloak-hostname>/realms/<realm-name>/broker/github/endpoint`
   - Note the Client ID and Client Secret provided by GitHub

1. Create a Kubernetes secret for Keycloak realm configuration:
   ```bash
   kubectl create secret generic keycloak-realm -n openhands \
     --from-literal=client-id=allhands \
     --from-literal=client-secret=<your-keycloak-client-secret> \
     --from-literal=provider-name=github \
     --from-literal=realm-name=allhands \
     --from-literal=server-url=http://keycloak
   ```

   The secret must contain the following keys:
   - `client-id`: The Keycloak client ID (not the GitHub OAuth App client ID), set to "allhands"
   - `client-secret`: The Keycloak client secret (not the GitHub OAuth App client secret)
   - `provider-name`: Set to "github" for GitHub OAuth integration
   - `realm-name`: The name of your Keycloak realm, set to "allhands"
   - `server-url`: The internal Keycloak service URL (typically "http://keycloak")

1. Create a GitHub App secret with the following structure:
   This secret contains the GitHub App configuration information from your GitHub account.
   You can create it using kubectl:
   ```bash
   kubectl create secret generic github-app -n openhands \
     --from-literal=app-id=<your-github-app-id> \
     --from-literal=webhook-secret=<your-github-webhook-secret> \
     --from-literal=client-id=<your-github-client-id> \
     --from-literal=client-secret=<your-github-client-secret> \
     --from-file=private-key=<path-to-your-private-key-file>
   ```

When the chart is deployed, a job will run to configure the Keycloak realm with GitHub as an identity provider using the credentials you provided.

## Configuration

See the [values.yaml](values.yaml) file for the full list of configurable parameters. Make sure to update all values marked with "REQUIRED" comments.

An [example-values.yaml](example-values.yaml) file is also provided as a starting point for your own configuration. This example file contains the minimum set of values you need to override when deploying the chart with the default included services (without using external data stores). Remember to update the domain names and other environment-specific values in the example file before using it.

## Using External Services

### Bring Your Own PostgreSQL

To use an external PostgreSQL database instead of deploying one with the chart:

1. Disable the included PostgreSQL:
   ```yaml
   postgresql:
     enabled: false
   ```

2. Configure the external database connection:
   ```yaml
   externalDatabase:
     host: your-postgresql-host
     port: 5432
     database: openhands
     existingSecret: postgres-password

   # Make sure the secret exists with the correct credentials
   # kubectl create secret generic postgres-password \
   #   --from-literal=username=<your-db-username> \
   #   --from-literal=password=<your-db-password>
   ```

3. Update the Keycloak, LiteLLM, and runtime-api configurations to use the external database:
   ```yaml
   keycloak:
     externalDatabase:
       host: your-postgresql-host
       port: 5432
       existingSecret: postgres-password

   litellm-helm:
     db:
       deployStandalone: false
       useExisting: true
       database: litellm
       endpoint: your-postgresql-host
       secret:
         name: postgres-password

   runtime-api:
     postgresql:
       auth:
         existingSecret: postgres-password
     env:
       DB_HOST: your-postgresql-host
       DB_USER: your-db-username
       DB_NAME: runtime_api_db
   ```

### Bring Your Own Redis

To use an external Redis instance:

1. Disable the included Redis:
   ```yaml
   redis:
     enabled: false
   ```

2. Configure the external Redis connection:
   ```yaml
   externalRedis:
     host: your-redis-host
     port: 6379
     existingSecret: redis

   # Make sure the secret exists with the correct credentials
   # kubectl create secret generic redis \
   #   --from-literal=redis-password=<your-redis-password>
   ```

### Bring Your Own S3-Compatible Storage

To use an external S3-compatible storage instead of MinIO:

1. Disable the ephemeral filestore:
   ```yaml
   filestore:
     ephemeral: false
   ```

2. Configure the S3 connection:
   ```yaml
   filestore:
     ephemeral: false
     bucket: your-bucket-name
     endpoint: https://your-s3-endpoint
     region: your-s3-region
     existingSecret: s3-credentials

   # Make sure the secret exists with the correct credentials
   # kubectl create secret generic s3-credentials \
   #   --from-literal=access-key=<your-access-key> \
   #   --from-literal=secret-key=<your-secret-key>
   ```

### Storage Class Configuration

By default, the chart expects a storage class named `standard-rwo`. If you're using EKS, which typically has a `gp2` storage class, you can configure the chart to use it instead:

```yaml
runtime-api:
  env:
    STORAGE_CLASS: "gp2"  # Replace with your cluster's storage class name
```

Alternatively, you can create a storage class named `standard-rwo` that uses your cloud provider's block storage:

```bash
# For AWS EKS
kubectl apply -f - <<EOF
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: standard-rwo
provisioner: kubernetes.io/aws-ebs
parameters:
  type: gp2
volumeBindingMode: WaitForFirstConsumer
EOF

# For GKE
kubectl apply -f - <<EOF
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: standard-rwo
provisioner: pd.csi.storage.gke.io
parameters:
  type: pd-standard
volumeBindingMode: WaitForFirstConsumer
EOF
```

## Upgrading

To upgrade the chart:

```bash
helm upgrade openhands . -f my-values.yaml -n openhands
```

## Uninstallation

To uninstall the chart:

```bash
helm uninstall openhands -n openhands
```

Note: This will not delete any PVCs or secrets created. You'll need to delete those manually if desired.
