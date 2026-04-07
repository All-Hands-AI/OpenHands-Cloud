# Migration Guide: Bitnami PostgreSQL to CloudNative-PG (CNPG)

This guide covers migrating the embedded PostgreSQL from the Bitnami subchart to CloudNative-PG (CNPG) with zero data loss. This applies to deployments using the embedded PostgreSQL (`postgresql.enabled: true` in the old chart).

> **Downtime**: The dump (Step 1) runs while the application is live. Downtime begins when you scale down workloads (Step 3) and ends when the final helm upgrade brings everything back up (Step 6).

## Prerequisites

- `kubectl` access to the cluster
- `helm` v3
- Current chart version: openhands `0.3.x` (Bitnami PostgreSQL)
- Target chart version: openhands `0.4.0` (CNPG)

## Step 1: Dump All Databases

### 1a. Set variables

```bash
NAMESPACE=openhands  # adjust if different
```

### 1b. Create a PVC for the dump

Size this larger than your database. Check current usage with:

```bash
kubectl exec -n $NAMESPACE \
  $(kubectl get pods -n $NAMESPACE -l app.kubernetes.io/name=postgresql -o jsonpath='{.items[0].metadata.name}') \
  -- psql -U postgres -c "SELECT pg_size_pretty(sum(pg_database_size(datname))) FROM pg_database;"
```

```bash
kubectl apply -n $NAMESPACE -f - <<'EOF'
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: pg-migration-dump
spec:
  accessModes: [ReadWriteOnce]
  resources:
    requests:
      storage: 50Gi   # adjust based on database size
EOF
```

### 1c. Run the dump

```bash
kubectl apply -n $NAMESPACE -f - <<'EOF'
apiVersion: batch/v1
kind: Job
metadata:
  name: pg-migration-dump
spec:
  backoffLimit: 0
  template:
    spec:
      restartPolicy: Never
      volumes:
        - name: dump
          persistentVolumeClaim:
            claimName: pg-migration-dump
      containers:
        - name: dump
          image: postgres:17
          volumeMounts:
            - name: dump
              mountPath: /dump
          env:
            - name: PGHOST
              value: oh-main-postgresql
            - name: PGUSER
              value: postgres
            - name: PGPASSWORD
              valueFrom:
                secretKeyRef:
                  name: postgres-password
                  key: password
          command: ["sh", "-c"]
          args:
            - pg_dumpall --clean --if-exists > /dump/all.sql && ls -lh /dump/all.sql
EOF
```

### 1d. Verify

```bash
kubectl wait --for=condition=Complete job/pg-migration-dump -n $NAMESPACE --timeout=3600s
kubectl logs job/pg-migration-dump -n $NAMESPACE
```

The logs should show the dump file size. Once confirmed, clean up the job:

```bash
kubectl delete job pg-migration-dump -n $NAMESPACE
```

## Step 2: Install the CNPG Operator

```bash
helm repo add cnpg https://cloudnative-pg.github.io/charts
helm repo update

helm install cnpg-operator cnpg/cloudnative-pg \
  -n cnpg-system --create-namespace

kubectl wait --for=condition=Available deployment/cnpg-operator-cloudnative-pg \
  -n cnpg-system --timeout=120s
```

## Step 3: Scale Down All Workloads

Scale everything to zero so nothing writes to the database during the migration.

```bash
kubectl scale deployment -n $NAMESPACE --all --replicas=0
kubectl scale statefulset -n $NAMESPACE --all --replicas=0
kubectl patch cronjob -n $NAMESPACE --type=merge -p '{"spec":{"suspend":true}}' --all
```

Wait until no pods remain:

```bash
kubectl get pods -n $NAMESPACE
```

## Step 4: Upgrade the OpenHands Chart (replicas=0)

### 4a. Update your values file

**Remove** these sections:

```yaml
postgresql:
  enabled: true
  auth:
    username: postgres
    existingSecret: postgres-password
  # ...

externalDatabase:
  enabled: false
  existingSecret: postgres-password

databaseMigrations:
  waitForDatabase: true
  createDatabases: false
  migrate: true
```

**Add** these sections:

```yaml
database:
  host: "oh-main-postgresql-rw"
  port: "5432"
  user: "postgres"
  name: "openhands"
  secretName: "postgres-password"
  secretKey: "password"
  waitForDatabase: true
  createDatabases: true
  migrate: true

cnpg:
  enabled: true
  imageName: "ghcr.io/cloudnative-pg/postgresql:17"
  instances: 1
  storage:
    size: 10Gi
    # storageClass: ""  # set if you need a specific storage class
```

**Update `runtime-api`**: Remove the old `databaseMigrations`, `postgresql`, and `externalDatabase` keys. Also remove `DB_HOST` from `runtime-api.env` if present. Add:

```yaml
runtime-api:
  database:
    waitForDatabase: true
    createDatabases: false
    migrate: true
```

**Update hostname references** from `oh-main-postgresql` to `oh-main-postgresql-rw`:

```yaml
keycloak:
  externalDatabase:
    host: oh-main-postgresql-rw

litellm-helm:
  db:
    endpoint: oh-main-postgresql-rw
```

### 4b. Run the helm upgrade with replicas held at zero

```bash
helm upgrade openhands oci://ghcr.io/all-hands-ai/helm-charts/openhands --version <VERSION> \
  -n $NAMESPACE \
  -f your-values.yaml \
  --set deployment.replicas=0 \
  --set runtime-api.replicaCount=0 \
  --set automation.deployment.replicas=0 \
  --set keycloak.replicaCount=0 \
  --timeout 600s
```

Scale down anything the `--set` overrides didn't cover (e.g. LiteLLM):

```bash
kubectl scale deployment -n $NAMESPACE --all --replicas=0
kubectl scale statefulset -n $NAMESPACE --all --replicas=0
```

### 4c. Wait for the CNPG cluster

```bash
kubectl wait --for=condition=Ready cluster/oh-main-postgresql \
  -n $NAMESPACE --timeout=300s
```

## Step 5: Restore the Database Dump

```bash
kubectl apply -n $NAMESPACE -f - <<'EOF'
apiVersion: batch/v1
kind: Job
metadata:
  name: pg-migration-restore
spec:
  backoffLimit: 0
  template:
    spec:
      restartPolicy: Never
      volumes:
        - name: dump
          persistentVolumeClaim:
            claimName: pg-migration-dump
      containers:
        - name: restore
          image: postgres:17
          volumeMounts:
            - name: dump
              mountPath: /dump
          env:
            - name: PGHOST
              value: oh-main-postgresql-rw
            - name: PGUSER
              value: postgres
            - name: PGPASSWORD
              valueFrom:
                secretKeyRef:
                  name: postgres-password
                  key: password
          command: ["sh", "-c"]
          args:
            - psql -f /dump/all.sql
EOF
```

```bash
kubectl wait --for=condition=Complete job/pg-migration-restore -n $NAMESPACE --timeout=7200s
kubectl logs job/pg-migration-restore -n $NAMESPACE
```

You will see some harmless errors like `role "postgres" already exists`. This is expected.

Clean up:

```bash
kubectl delete job pg-migration-restore -n $NAMESPACE
kubectl delete pvc pg-migration-dump -n $NAMESPACE
```

## Step 6: Bring the Application Back Up

Run the upgrade again **without** the `--set *.replicas=0` overrides:

```bash
helm upgrade openhands oci://ghcr.io/all-hands-ai/helm-charts/openhands --version <VERSION> \
  -n $NAMESPACE \
  -f your-values.yaml \
  --wait --timeout 600s
```

Database migrations run automatically on startup.

## Verification

1. **CNPG cluster health**:
   ```bash
   kubectl get cluster oh-main-postgresql -n $NAMESPACE
   ```
   Status should show `Cluster in healthy state`.

2. **Databases present**:
   ```bash
   kubectl exec -n $NAMESPACE oh-main-postgresql-1 -- psql -U postgres -c '\l'
   ```

3. **Application access**: Log in to the OpenHands UI and verify authentication works and existing conversations are visible.

## Rollback

The old Bitnami PostgreSQL PVC is preserved during migration.

1. `helm rollback openhands` to the previous revision
2. Uninstall the CNPG operator

## Cleanup

Once you've verified the migration is successful and no longer need the rollback option:

```bash
kubectl delete pvc data-oh-main-postgresql-0 -n $NAMESPACE
```
