# Kubernetes Cluster Sizing Guide for OpenHands Enterprise

This document provides comprehensive guidance for sizing Kubernetes clusters to run OpenHands Enterprise effectively. The sizing recommendations are based on the OpenHands architecture, which consists of core applications and runtime pods that handle user workloads.

## Architecture Overview

OpenHands Enterprise can be deployed in two configurations:

1. **Single-Cluster Deployment**: Core applications and runtime pods in the same cluster with namespace isolation
2. **Multi-Cluster Deployment**: Core applications in one cluster, runtime pods in a dedicated cluster (recommended for production)

## Core Application Sizing

The core applications provide the main OpenHands functionality and have predictable resource requirements.

### Core Application Components

| Component | CPU Request | Memory Request | CPU Limit | Memory Limit | Replicas | Notes |
|-----------|-------------|----------------|-----------|--------------|----------|-------|
| OpenHands Enterprise Server | 1000m | 3Gi | - | 3Gi | 1-5 (HPA) | Main application server |
| Runtime API | 500m | 1.5Gi | - | 1.5Gi | 3-6 (HPA) | Manages runtime pods |
| Integration Events | 1000m | 1.5Gi | 1000m | 1.5Gi | 2 | Handles integrations |
| MCP Events | - | - | - | - | 2 | Model Context Protocol |
| PostgreSQL | 2000m | 8Gi | - | - | 1 | Primary database |
| Redis | 100m | 512Mi | 100m | 512Mi | 1 | Caching and sessions |
| MinIO (Optional) | 100m | 512Mi | 100m | 512Mi | 1 | Object storage (dev only) |
| Keycloak | - | - | - | - | 1 | Authentication |
| ClickHouse (Optional) | - | - | - | - | 1 | Analytics database |

### Core Application Cluster Sizing

**Minimum Production Configuration:**
- **Node Specs**: 8 vCPU, 16 GiB RAM per node (e.g., AWS `c5.2xlarge`, GCP `c2-standard-8`, Azure `Standard_F8s_v2`)
- **Node Count**: 3-6 nodes (across 3 availability zones)
- **Total Resources**: 24-48 vCPU, 48-96 GiB RAM

**Recommended Production Configuration:**
- **Node Specs**: 16 vCPU, 32 GiB RAM per node (e.g., AWS `c5.4xlarge`, GCP `c2-standard-16`, Azure `Standard_F16s_v2`)
- **Node Count**: 3-9 nodes (across 3 availability zones)
- **Total Resources**: 48-144 vCPU, 96-288 GiB RAM

**High-Memory Workloads** (Optional - Analytics, ClickHouse):
- **Additional Node Pool**: 8 vCPU, 64 GiB RAM per node (e.g., AWS `r5.2xlarge`, GCP `n2-highmem-8`, Azure `Standard_E8s_v4`)
- **Node Count**: 0-3 nodes (scale from zero)
- **Taints**: `workload-type=memory-intensive:NoSchedule`
- **Note**: Only required if deploying optional analytics components like ClickHouse

## Runtime Pod Sizing

Runtime pods are the execution environments where AI agents perform tasks. Their resource consumption varies based on workload complexity.

### Default Runtime Pod Resources

| Resource | Default Value | Configurable Via | Notes |
|----------|---------------|------------------|-------|
| Memory Request | 2048Mi (2 GiB) | `MEMORY_REQUEST` | Always allocated |
| Memory Limit | 3072Mi (3 GiB) | `MEMORY_LIMIT` | Maximum allowed |
| CPU Request | 1000m (1 vCPU) | `CPU_REQUEST` | Always allocated |
| CPU Limit | Unlimited | `CPU_LIMIT` | Can burst if available |
| Ephemeral Storage | 25Gi | `EPHEMERAL_STORAGE_SIZE` | Temporary files |
| Persistent Storage | 10Gi | `PERSISTENT_STORAGE_SIZE` | User workspace |

### Runtime Pod Lifecycle

1. **Creation**: Pod starts when user begins a session
2. **Active**: Pod consumes full resources during agent execution
3. **Idle**: Pod remains allocated but with minimal CPU usage after 30 minutes of inactivity
4. **Paused**: Pod is scaled to zero, PVC retained (default behavior)
5. **Stopped**: Pod and PVC are deleted after 24 hours (configurable)

### Resource Consumption Patterns

**Active Runtime Pod:**
- **CPU**: 50-100% of allocated CPU during agent execution
- **Memory**: 70-90% of allocated memory for large codebases
- **Storage**: Grows with workspace size and temporary files

**Idle Runtime Pod:**
- **CPU**: 5-10% of allocated CPU for background processes
- **Memory**: 40-60% of allocated memory (cached data)
- **Storage**: Unchanged

**Paused Runtime Pod:**
- **CPU**: 0 (pod scaled to zero)
- **Memory**: 0 (pod scaled to zero)
- **Storage**: PVC retained for quick resume

## Per-User Scaling Calculations

### Basic Per-User Resource Requirements

**Single Active User:**
- **CPU**: 1 vCPU (runtime) + 0.1 vCPU (overhead) = 1.1 vCPU
- **Memory**: 3 GiB (runtime) + 0.2 GiB (overhead) = 3.2 GiB
- **Storage**: 35 GiB (25 GiB ephemeral + 10 GiB persistent)

**User with Multiple Runtimes** (if `max_runtimes_per_user` > 1):
- **CPU**: `max_runtimes_per_user` × 1.1 vCPU
- **Memory**: `max_runtimes_per_user` × 3.2 GiB
- **Storage**: `max_runtimes_per_user` × 35 GiB

### Concurrent User Scaling

**Formula for Runtime Cluster Sizing:**
```
Total CPU = (Concurrent Users × Max Runtimes per User × 1.1 vCPU) + (Warm Runtime Count × 1.1 vCPU)
Total Memory = (Concurrent Users × Max Runtimes per User × 3.2 GiB) + (Warm Runtime Count × 3.2 GiB)
Total Storage = (Total Users × Max Runtimes per User × 35 GiB)
```

**Example Calculations:**

*Small Deployment (50 concurrent users):*
- Max runtimes per user: 2
- Warm runtimes: 5
- **CPU**: (50 × 2 × 1.1) + (5 × 1.1) = 115.5 vCPU
- **Memory**: (50 × 2 × 3.2) + (5 × 3.2) = 336 GiB
- **Recommended Nodes**: 15 × 4 vCPU, 8 GiB nodes (e.g., AWS `c5.xlarge`, GCP `c2-standard-4`, Azure `Standard_F4s_v2`) across 3 AZs

*Medium Deployment (200 concurrent users):*
- Max runtimes per user: 3
- Warm runtimes: 10
- **CPU**: (200 × 3 × 1.1) + (10 × 1.1) = 671 vCPU
- **Memory**: (200 × 3 × 3.2) + (10 × 3.2) = 1952 GiB
- **Recommended Nodes**: 45 × 8 vCPU, 16 GiB nodes (e.g., AWS `c5.2xlarge`, GCP `c2-standard-8`, Azure `Standard_F8s_v2`) across 3 AZs

*Large Deployment (1000 concurrent users):*
- Max runtimes per user: 2
- Warm runtimes: 20
- **CPU**: (1000 × 2 × 1.1) + (20 × 1.1) = 2222 vCPU
- **Memory**: (1000 × 2 × 3.2) + (20 × 3.2) = 6464 GiB
- **Recommended Nodes**: 140 × 8 vCPU, 16 GiB nodes (e.g., AWS `c5.2xlarge`, GCP `c2-standard-8`, Azure `Standard_F8s_v2`) across 3 AZs

## Warm Runtime Configuration Impact

Warm runtimes are pre-started pods that provide instant availability for users but consume resources continuously.

### Warm Runtime Benefits
- **Instant Start**: Users get immediate access without waiting for pod startup
- **Better UX**: Eliminates 30-60 second cold start delays
- **Consistent Performance**: Avoids resource contention during pod creation

### Warm Runtime Costs
- **Continuous Resource Usage**: Each warm runtime consumes 1.1 vCPU and 3.2 GiB continuously
- **Increased Base Cost**: Higher minimum cluster size regardless of active users

### Warm Runtime Sizing Recommendations

| User Base | Recommended Warm Runtimes | Reasoning |
|-----------|---------------------------|-----------|
| < 50 users | 2-5 | Cover peak concurrent sessions |
| 50-200 users | 5-15 | 5-10% of user base |
| 200-500 users | 15-25 | 3-5% of user base |
| 500+ users | 25-50 | 2-5% of user base |

**Configuration Example:**
```yaml
runtime-api:
  warmRuntimes:
    enabled: true
    count: 10
    configs:
      - name: default
        image: "ghcr.io/all-hands-ai/runtime:latest-nikolaik"
        # ... other config
```

## Max Runtimes Per User Impact

The `max_runtimes_per_user` setting controls how many concurrent runtime pods a single user can have.

### Setting Considerations

**max_runtimes_per_user = 1:**
- **Pros**: Predictable resource usage, lower costs, simpler management
- **Cons**: Users can't work on multiple projects simultaneously
- **Use Case**: Cost-conscious deployments, simple workflows

**max_runtimes_per_user = 2-3:**
- **Pros**: Allows multi-project work, good balance of flexibility and cost
- **Cons**: 2-3x resource requirements per user
- **Use Case**: Most production deployments

**max_runtimes_per_user > 3:**
- **Pros**: Maximum flexibility for power users
- **Cons**: High resource requirements, potential for resource waste
- **Use Case**: Research environments, unlimited resource scenarios

### Resource Impact Examples

**100 concurrent users with different max_runtimes_per_user:**

| Max Runtimes | Total CPU | Total Memory | Node Count (8 vCPU, 16 GiB) |
|--------------|-----------|--------------|--------------------------|
| 1 | 110 vCPU | 320 GiB | 14 nodes |
| 2 | 220 vCPU | 640 GiB | 28 nodes |
| 3 | 330 vCPU | 960 GiB | 42 nodes |
| 5 | 550 vCPU | 1600 GiB | 70 nodes |

## Node Pool Recommendations

### Runtime Cluster Node Pools

**Primary Runtime Pool:**
- **Node Specs**: 8-16 vCPU, 16-32 GiB RAM per node
  - AWS: `c5.2xlarge` (8 vCPU, 16 GiB) or `c5.4xlarge` (16 vCPU, 32 GiB)
  - GCP: `c2-standard-8` (8 vCPU, 32 GiB) or `c2-standard-16` (16 vCPU, 64 GiB)
  - Azure: `Standard_F8s_v2` (8 vCPU, 16 GiB) or `Standard_F16s_v2` (16 vCPU, 32 GiB)
- **Scaling**: Auto-scaling with 1-150 nodes per availability zone
- **Storage**: 300-500 GiB SSD per node
- **Runtime Class**: `sysbox-runc` (for container security)

**High-Performance Pool** (optional):
- **Node Specs**: 36 vCPU, 72 GiB RAM per node
  - AWS: `c5.9xlarge`, GCP: `c2-standard-30`, Azure: `Standard_F32s_v2`
- **Use Case**: CPU-intensive workloads, large codebases
- **Scaling**: 0-10 nodes per availability zone (scale from zero)
- **Taints**: `workload-type=high-performance:NoSchedule`

**GPU Pool** (optional):
- **Node Specs**: 8+ vCPU, 60+ GiB RAM, 1+ GPU per node
  - AWS: `p3.2xlarge` (8 vCPU, 61 GiB, 1 V100), GCP: `n1-standard-8` + GPU, Azure: `Standard_NC6s_v3`
- **Use Case**: ML/AI workloads requiring GPU acceleration
- **Scaling**: 0-5 nodes per availability zone (scale from zero)
- **Taints**: `nvidia.com/gpu=true:NoSchedule`

### Core Application Cluster Node Pools

**Primary Application Pool:**
- **Node Specs**: 8 vCPU, 16 GiB RAM per node
  - AWS: `c5.2xlarge`, GCP: `c2-standard-8`, Azure: `Standard_F8s_v2`
- **Scaling**: 3-25 nodes per availability zone
- **Storage**: 50-100 GiB SSD per node

**Memory-Intensive Pool** (Optional):
- **Node Specs**: 8 vCPU, 64 GiB RAM per node
  - AWS: `r5.2xlarge`, GCP: `n2-highmem-8`, Azure: `Standard_E8s_v4`
- **Use Case**: Analytics, ClickHouse, large databases
- **Scaling**: 0-3 nodes per availability zone (scale from zero)
- **Taints**: `workload-type=memory-intensive:NoSchedule`
- **Note**: Only required if deploying optional analytics components

## Monitoring and Alerting

### Key Metrics to Monitor

**Cluster-Level Metrics:**
- CPU utilization (target: 60-80%)
- Memory utilization (target: 70-85%)
- Node count and scaling events
- Pod pending time (should be < 60 seconds)

**Runtime-Specific Metrics:**
- Active runtime count
- Idle runtime count
- Warm runtime count
- Runtime creation/deletion rate
- Average runtime lifetime

**User Experience Metrics:**
- Time to first runtime (cold start)
- Runtime availability (uptime)
- Resource contention events

### Recommended Alerts

1. **High Resource Utilization**: CPU > 85% or Memory > 90% for 5 minutes
2. **Pod Pending**: Pods pending for > 2 minutes
3. **Runtime Creation Failures**: Failed runtime creation rate > 5%
4. **Warm Runtime Shortage**: Available warm runtimes < 2
5. **Node Scaling Issues**: Node scaling events failing

## Cost Optimization Strategies

### Right-Sizing Strategies

1. **Start Conservative**: Begin with lower `max_runtimes_per_user` and fewer warm runtimes
2. **Monitor Usage Patterns**: Track actual vs. allocated resources
3. **Implement Spot Instances**: Use spot instances for non-critical runtime workloads
4. **Optimize Idle Timeouts**: Reduce idle timeout from 30 minutes to 15 minutes if appropriate

### Advanced Optimizations

1. **Mixed Instance Types**: Use different instance types for different workload patterns
2. **Scheduled Scaling**: Scale down during off-hours if usage patterns are predictable
3. **Resource Quotas**: Implement namespace-level resource quotas to prevent resource hogging
4. **Pod Disruption Budgets**: Ensure availability during node maintenance

## Troubleshooting Common Issues

### Resource Exhaustion

**Symptoms**: Pods stuck in Pending state, slow runtime creation
**Solutions**:
- Increase node pool maximum size
- Add additional node pools with different instance types
- Review resource requests and limits

### Poor Performance

**Symptoms**: Slow agent execution, timeouts
**Solutions**:
- Increase runtime pod CPU/memory limits
- Use higher-performance instance types
- Check for resource contention

### High Costs

**Symptoms**: Unexpected AWS bills, high resource utilization
**Solutions**:
- Reduce warm runtime count
- Lower `max_runtimes_per_user`
- Implement more aggressive cleanup policies
- Use spot instances where appropriate

## Example Configurations

### Small Organization (< 100 users)

```yaml
# Core Application Cluster
Node Pool: 3 × 8 vCPU, 16 GiB nodes
Total: 24 vCPU, 48 GiB

# Runtime Cluster  
Node Pool: 6 × 8 vCPU, 16 GiB nodes
Total: 48 vCPU, 96 GiB

# Configuration
max_runtimes_per_user: 2
warm_runtime_count: 5
idle_timeout: 1800 # 30 minutes
```

### Medium Organization (100-500 users)

```yaml
# Core Application Cluster
Primary Pool: 6 × 8 vCPU, 16 GiB nodes
Memory Pool: 2 × 8 vCPU, 64 GiB nodes (optional - for analytics)
Total: 64 vCPU, 224 GiB

# Runtime Cluster
Primary Pool: 30 × 8 vCPU, 16 GiB nodes
Total: 240 vCPU, 480 GiB

# Configuration
max_runtimes_per_user: 2
warm_runtime_count: 15
idle_timeout: 1800 # 30 minutes
```

### Large Organization (500+ users)

```yaml
# Core Application Cluster
Primary Pool: 12 × 16 vCPU, 32 GiB nodes
Memory Pool: 6 × 16 vCPU, 128 GiB nodes (optional - for analytics)
Total: 288 vCPU, 1152 GiB

# Runtime Cluster
Primary Pool: 100 × 8 vCPU, 16 GiB nodes
High-Perf Pool: 10 × 36 vCPU, 72 GiB nodes
Total: 1160 vCPU, 2320 GiB

# Configuration
max_runtimes_per_user: 3
warm_runtime_count: 25
idle_timeout: 1200 # 20 minutes
```

## Related Configuration Files

This sizing guide references the following configuration files in this repository:

- [`charts/openhands/values.yaml`](../charts/openhands/values.yaml) - Core application resource defaults
- [`charts/runtime-api/values.yaml`](../charts/runtime-api/values.yaml) - Runtime API configuration
- [`charts/openhands/example-values.yaml`](../charts/openhands/example-values.yaml) - Example deployment configuration
- [`charts/openhands/values.runtime-example.yaml`](../charts/openhands/values.runtime-example.yaml) - Runtime-specific example

## Conclusion

Proper Kubernetes cluster sizing for OpenHands Enterprise requires careful consideration of both core application needs and runtime pod scaling patterns. Start with conservative estimates based on your expected user load, implement comprehensive monitoring, and adjust based on actual usage patterns.

Key takeaways:
- Core applications have predictable resource requirements
- Runtime pods scale with user activity and configuration settings
- Warm runtimes improve user experience but increase base costs
- Monitor actual usage to optimize resource allocation and costs
- Plan for growth with auto-scaling node pools and appropriate instance types

For additional support with sizing your OpenHands Enterprise deployment, consult with the OpenHands team or your cloud provider's solutions architect.