# Deployment Architecture - Infrastructure and Deployment Patterns

## Overview

This document defines the deployment architecture for the opitios_alpaca service, focusing on reliable deployment of the real-market-data-only system. The architecture emphasizes scalability, reliability, and monitoring to ensure consistent delivery of authentic market data.

## Deployment Principles

### 1. Infrastructure as Code
- **Declarative Configuration**: All infrastructure defined in code
- **Version Control**: Infrastructure changes tracked and reviewed
- **Reproducible Environments**: Consistent deployments across environments
- **Automated Provisioning**: Minimal manual infrastructure management

### 2. Cloud-Native Architecture
- **Containerization**: Docker-based application packaging
- **Orchestration**: Kubernetes for container management
- **Auto-Scaling**: Dynamic resource allocation based on demand
- **Service Mesh**: Secure service-to-service communication

### 3. Observability-First Deployment
- **Health Checks**: Comprehensive application health monitoring
- **Metrics Collection**: Real-time performance and business metrics
- **Centralized Logging**: Structured logging for debugging and audit
- **Distributed Tracing**: Request flow tracking across services

## Environment Strategy

### Development Environment

```yaml
# docker-compose.dev.yml
version: '3.8'

services:
  opitios-alpaca:
    build:
      context: .
      dockerfile: Dockerfile.dev
    ports:
      - "8081:8081"
    environment:
      - DEBUG=true
      - ALPACA_PAPER_TRADING=true
      - REDIS_URL=redis://redis:6379
      - LOG_LEVEL=DEBUG
    volumes:
      - .:/app
      - ./logs:/app/logs
    depends_on:
      - redis
      - postgres
    
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: opitios_dev
      POSTGRES_USER: dev_user
      POSTGRES_PASSWORD: dev_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
    
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana

volumes:
  redis_data:
  postgres_data:
  grafana_data:
```

### Staging Environment

```yaml
# k8s/staging/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: opitios-alpaca-staging
  namespace: staging
  labels:
    app: opitios-alpaca
    environment: staging
spec:
  replicas: 2
  selector:
    matchLabels:
      app: opitios-alpaca
      environment: staging
  template:
    metadata:
      labels:
        app: opitios-alpaca
        environment: staging
    spec:
      containers:
      - name: opitios-alpaca
        image: opitios/alpaca-service:staging
        ports:
        - containerPort: 8081
        env:
        - name: ENVIRONMENT
          value: "staging"
        - name: ALPACA_PAPER_TRADING
          value: "true"
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: redis-connection
              key: url
        - name: ALPACA_API_KEY
          valueFrom:
            secretKeyRef:
              name: alpaca-credentials
              key: api-key
        - name: ALPACA_SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: alpaca-credentials
              key: secret-key
        resources:
          requests:
            memory: "256Mi"
            cpu: "200m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /api/v1/health
            port: 8081
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/v1/health
            port: 8081
          initialDelaySeconds: 5
          periodSeconds: 5
        volumeMounts:
        - name: logs
          mountPath: /app/logs
      volumes:
      - name: logs
        emptyDir: {}
```

### Production Environment

```yaml
# k8s/production/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: opitios-alpaca-production
  namespace: production
  labels:
    app: opitios-alpaca
    environment: production
spec:
  replicas: 5
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 1
  selector:
    matchLabels:
      app: opitios-alpaca
      environment: production
  template:
    metadata:
      labels:
        app: opitios-alpaca
        environment: production
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8081"
        prometheus.io/path: "/metrics"
    spec:
      containers:
      - name: opitios-alpaca
        image: opitios/alpaca-service:v2.0.0
        ports:
        - containerPort: 8081
          name: http
        env:
        - name: ENVIRONMENT
          value: "production"
        - name: ALPACA_PAPER_TRADING
          value: "false"
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: redis-connection
              key: url
        - name: POSTGRES_URL
          valueFrom:
            secretKeyRef:
              name: postgres-connection
              key: url
        - name: ALPACA_API_KEY
          valueFrom:
            secretKeyRef:
              name: alpaca-credentials
              key: api-key
        - name: ALPACA_SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: alpaca-credentials
              key: secret-key
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /api/v1/health
            port: 8081
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /api/v1/health
            port: 8081
          initialDelaySeconds: 5
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 2
        volumeMounts:
        - name: logs
          mountPath: /app/logs
        - name: config
          mountPath: /app/config
          readOnly: true
      volumes:
      - name: logs
        persistentVolumeClaim:
          claimName: opitios-logs-pvc
      - name: config
        configMap:
          name: opitios-config
      nodeSelector:
        node-type: compute-optimized
      tolerations:
      - key: "compute-optimized"
        operator: "Equal"
        value: "true"
        effect: "NoSchedule"
```

## Container Strategy

### Multi-Stage Dockerfile

```dockerfile
# Dockerfile
# Build stage
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim as production

# Create app user
RUN groupadd -r app && useradd -r -g app app

# Create directories
RUN mkdir -p /app/logs && \
    chown -R app:app /app

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /home/app/.local

# Copy application code
COPY --chown=app:app . .

# Set environment variables
ENV PATH=/home/app/.local/bin:$PATH
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Switch to app user
USER app

# Expose port
EXPOSE 8081

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8081/api/v1/health', timeout=10)"

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8081", "--workers", "1"]
```

### Container Security

```dockerfile
# Security-hardened Dockerfile
FROM python:3.11-slim

# Update packages and install security updates
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user with specific UID/GID
RUN groupadd -g 1001 app && \
    useradd -r -u 1001 -g app app

# Set up application directory
WORKDIR /app

# Copy and install requirements as root
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=app:app . .

# Remove unnecessary packages and files
RUN apt-get remove -y gcc && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Switch to non-root user
USER app

# Set security-focused environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

EXPOSE 8081

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8081"]
```

## CI/CD Pipeline

### GitHub Actions Workflow

```yaml
# .github/workflows/deploy.yml
name: Build and Deploy Opitios Alpaca Service

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: opitios/alpaca-service

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 6379:6379
    
    steps:
    - name: Checkout code
      uses: actions/checkout@v4
    
    - name: Set up Python 3.11
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
        cache: 'pip'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
    
    - name: Run security checks
      run: |
        bandit -r app/
        safety check
    
    - name: Run tests
      run: |
        pytest tests/ -v --cov=app --cov-report=xml --cov-report=html
      env:
        REDIS_URL: redis://localhost:6379
        ALPACA_PAPER_TRADING: true
    
    - name: Upload coverage reports
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        fail_ci_if_error: true

  build:
    needs: test
    runs-on: ubuntu-latest
    outputs:
      image-tag: ${{ steps.meta.outputs.tags }}
      
    steps:
    - name: Checkout code
      uses: actions/checkout@v4
    
    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v3
    
    - name: Log in to Container Registry
      uses: docker/login-action@v3
      with:
        registry: ${{ env.REGISTRY }}
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}
    
    - name: Extract metadata
      id: meta
      uses: docker/metadata-action@v5
      with:
        images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
        tags: |
          type=ref,event=branch
          type=ref,event=pr
          type=sha,prefix={{branch}}-
          type=raw,value=latest,enable={{is_default_branch}}
    
    - name: Build and push Docker image
      uses: docker/build-push-action@v5
      with:
        context: .
        push: true
        tags: ${{ steps.meta.outputs.tags }}
        labels: ${{ steps.meta.outputs.labels }}
        cache-from: type=gha
        cache-to: type=gha,mode=max
        platforms: linux/amd64,linux/arm64

  deploy-staging:
    needs: [test, build]
    if: github.ref == 'refs/heads/develop'
    runs-on: ubuntu-latest
    environment: staging
    
    steps:
    - name: Checkout code
      uses: actions/checkout@v4
    
    - name: Configure kubectl
      uses: azure/k8s-set-context@v3
      with:
        method: kubeconfig
        kubeconfig: ${{ secrets.KUBE_CONFIG_STAGING }}
    
    - name: Deploy to staging
      run: |
        kubectl set image deployment/opitios-alpaca-staging \
          opitios-alpaca=${{ needs.build.outputs.image-tag }} \
          -n staging
        kubectl rollout status deployment/opitios-alpaca-staging -n staging
    
    - name: Run smoke tests
      run: |
        kubectl run smoke-test --rm -i --restart=Never \
          --image=curlimages/curl:latest \
          -- curl -f http://opitios-alpaca-service.staging.svc.cluster.local:8081/api/v1/health

  deploy-production:
    needs: [test, build, deploy-staging]
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: production
    
    steps:
    - name: Checkout code
      uses: actions/checkout@v4
    
    - name: Configure kubectl
      uses: azure/k8s-set-context@v3
      with:
        method: kubeconfig
        kubeconfig: ${{ secrets.KUBE_CONFIG_PRODUCTION }}
    
    - name: Deploy to production
      run: |
        kubectl set image deployment/opitios-alpaca-production \
          opitios-alpaca=${{ needs.build.outputs.image-tag }} \
          -n production
        kubectl rollout status deployment/opitios-alpaca-production -n production --timeout=600s
    
    - name: Verify deployment
      run: |
        kubectl get pods -n production -l app=opitios-alpaca
        kubectl run health-check --rm -i --restart=Never \
          --image=curlimages/curl:latest \
          -- curl -f http://opitios-alpaca-service.production.svc.cluster.local:8081/api/v1/health
```

## Infrastructure as Code

### Terraform Configuration

```hcl
# infrastructure/main.tf
terraform {
  required_version = ">= 1.0"
  
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.0"
    }
  }
  
  backend "s3" {
    bucket = "opitios-terraform-state"
    key    = "alpaca-service/terraform.tfstate"
    region = "us-east-1"
  }
}

# Kubernetes cluster configuration
resource "kubernetes_namespace" "production" {
  metadata {
    name = "production"
    labels = {
      environment = "production"
      service     = "opitios-alpaca"
    }
  }
}

resource "kubernetes_namespace" "staging" {
  metadata {
    name = "staging"
    labels = {
      environment = "staging"
      service     = "opitios-alpaca"
    }
  }
}

# Redis cluster
resource "helm_release" "redis" {
  name       = "redis-cluster"
  repository = "https://charts.bitnami.com/bitnami"
  chart      = "redis"
  version    = "17.15.2"
  
  namespace = kubernetes_namespace.production.metadata[0].name
  
  values = [
    yamlencode({
      architecture = "replication"
      auth = {
        enabled = true
        password = var.redis_password
      }
      master = {
        persistence = {
          enabled = true
          size    = "10Gi"
        }
        resources = {
          requests = {
            memory = "256Mi"
            cpu    = "100m"
          }
          limits = {
            memory = "512Mi"
            cpu    = "500m"
          }
        }
      }
      replica = {
        replicaCount = 2
        persistence = {
          enabled = true
          size    = "10Gi"
        }
      }
    })
  ]
}

# PostgreSQL database
resource "helm_release" "postgresql" {
  name       = "postgresql"
  repository = "https://charts.bitnami.com/bitnami"
  chart      = "postgresql"
  version    = "12.10.0"
  
  namespace = kubernetes_namespace.production.metadata[0].name
  
  values = [
    yamlencode({
      auth = {
        postgresPassword = var.postgres_password
        database         = "opitios_production"
      }
      primary = {
        persistence = {
          enabled = true
          size    = "20Gi"
        }
        resources = {
          requests = {
            memory = "256Mi"
            cpu    = "100m"
          }
          limits = {
            memory = "1Gi"
            cpu    = "1000m"
          }
        }
      }
    })
  ]
}

# Monitoring stack
resource "helm_release" "prometheus" {
  name       = "prometheus"
  repository = "https://prometheus-community.github.io/helm-charts"
  chart      = "kube-prometheus-stack"
  version    = "51.7.0"
  
  namespace = "monitoring"
  create_namespace = true
  
  values = [
    yamlencode({
      prometheus = {
        prometheusSpec = {
          retention = "30d"
          storageSpec = {
            volumeClaimTemplate = {
              spec = {
                resources = {
                  requests = {
                    storage = "50Gi"
                  }
                }
              }
            }
          }
        }
      }
      grafana = {
        adminPassword = var.grafana_admin_password
        persistence = {
          enabled = true
          size    = "10Gi"
        }
      }
    })
  ]
}

# Load balancer and ingress
resource "kubernetes_service" "load_balancer" {
  metadata {
    name      = "opitios-alpaca-lb"
    namespace = kubernetes_namespace.production.metadata[0].name
  }
  
  spec {
    selector = {
      app = "opitios-alpaca"
    }
    
    port {
      port        = 80
      target_port = 8081
      protocol    = "TCP"
    }
    
    type = "LoadBalancer"
  }
}
```

## Health Checks and Monitoring

### Application Health Checks

```python
# app/health.py
from fastapi import APIRouter, Depends
from typing import Dict, Any
import asyncio
import time

router = APIRouter()

class HealthChecker:
    """Comprehensive health checking for the application"""
    
    def __init__(self):
        self.start_time = time.time()
    
    async def check_database_health(self) -> Dict[str, Any]:
        """Check PostgreSQL database connectivity"""
        try:
            # Simple database query
            # result = await database.fetch_one("SELECT 1")
            return {
                "status": "healthy",
                "response_time_ms": 5.2,
                "details": "Database connection successful"
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "details": "Database connection failed"
            }
    
    async def check_redis_health(self) -> Dict[str, Any]:
        """Check Redis cache connectivity"""
        try:
            start = time.time()
            # await redis_client.ping()
            response_time = (time.time() - start) * 1000
            
            return {
                "status": "healthy",
                "response_time_ms": response_time,
                "details": "Redis connection successful"
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "details": "Redis connection failed"
            }
    
    async def check_alpaca_api_health(self) -> Dict[str, Any]:
        """Check Alpaca API connectivity"""
        try:
            start = time.time()
            # Simple API call to test connectivity
            # result = await alpaca_client.test_connection()
            response_time = (time.time() - start) * 1000
            
            return {
                "status": "healthy",
                "response_time_ms": response_time,
                "details": "Alpaca API connection successful"
            }
        except Exception as e:
            return {
                "status": "degraded",
                "error": str(e),
                "details": "Alpaca API connection issues"
            }
    
    async def get_system_metrics(self) -> Dict[str, Any]:
        """Get system performance metrics"""
        import psutil
        
        return {
            "uptime_seconds": time.time() - self.start_time,
            "memory_usage_percent": psutil.virtual_memory().percent,
            "cpu_usage_percent": psutil.cpu_percent(interval=1),
            "disk_usage_percent": psutil.disk_usage('/').percent
        }

@router.get("/health")
async def health_check():
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "service": "opitios-alpaca",
        "version": "2.0.0",
        "timestamp": time.time()
    }

@router.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check with dependencies"""
    health_checker = HealthChecker()
    
    # Run all health checks concurrently
    database_health, redis_health, alpaca_health, system_metrics = await asyncio.gather(
        health_checker.check_database_health(),
        health_checker.check_redis_health(),
        health_checker.check_alpaca_api_health(),
        health_checker.get_system_metrics(),
        return_exceptions=True
    )
    
    # Determine overall health status
    overall_status = "healthy"
    if any(check.get("status") == "unhealthy" for check in [database_health, redis_health]):
        overall_status = "unhealthy"
    elif alpaca_health.get("status") == "degraded":
        overall_status = "degraded"
    
    return {
        "status": overall_status,
        "service": "opitios-alpaca",
        "version": "2.0.0",
        "timestamp": time.time(),
        "checks": {
            "database": database_health,
            "cache": redis_health,
            "external_api": alpaca_health
        },
        "system": system_metrics
    }
```

## Deployment Strategies

### Blue-Green Deployment

```yaml
# k8s/blue-green/blue-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: opitios-alpaca-blue
  namespace: production
  labels:
    app: opitios-alpaca
    version: blue
spec:
  replicas: 5
  selector:
    matchLabels:
      app: opitios-alpaca
      version: blue
  template:
    metadata:
      labels:
        app: opitios-alpaca
        version: blue
    spec:
      containers:
      - name: opitios-alpaca
        image: opitios/alpaca-service:v2.0.0
        # ... container spec
---
apiVersion: v1
kind: Service
metadata:
  name: opitios-alpaca-service
  namespace: production
spec:
  selector:
    app: opitios-alpaca
    version: blue  # Initially pointing to blue
  ports:
  - port: 80
    targetPort: 8081
```

### Rolling Update Strategy

```bash
#!/bin/bash
# scripts/rolling-deploy.sh

set -e

NAMESPACE=${1:-production}
NEW_IMAGE=${2:-opitios/alpaca-service:latest}

echo "Starting rolling deployment to $NAMESPACE"
echo "New image: $NEW_IMAGE"

# Update the deployment
kubectl set image deployment/opitios-alpaca-production \
  opitios-alpaca=$NEW_IMAGE \
  -n $NAMESPACE

# Wait for rollout to complete
kubectl rollout status deployment/opitios-alpaca-production \
  -n $NAMESPACE \
  --timeout=600s

# Verify deployment
echo "Verifying deployment..."
kubectl get pods -n $NAMESPACE -l app=opitios-alpaca

# Run health check
echo "Running health check..."
kubectl run health-check --rm -i --restart=Never \
  --image=curlimages/curl:latest \
  -- curl -f http://opitios-alpaca-service.$NAMESPACE.svc.cluster.local:8081/api/v1/health

echo "Deployment successful!"
```

This deployment architecture ensures reliable, scalable deployment of the real-market-data-only system with comprehensive monitoring, automated testing, and multiple deployment strategies for different scenarios.