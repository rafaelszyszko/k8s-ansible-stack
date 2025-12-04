# k8s-ansible-stack

This repository contains a complete stack for deploying a multi-component application on a local Kubernetes cluster (using Minikube) and provisioning AWS infrastructure via Ansible. The application is a calculator API that integrates PostgreSQL (persistence), Redis (cache with 30s TTL), and NGINX (proxy), exposed via Ingress. The goal is to demonstrate Kubernetes and Ansible skills for production environments.

## Repository structure
- app-src/: Application source code (Python API with Dockerfile, requirements.txt, init_db.sql).
- k8s/: Kubernetes files organized by component. Includes deployments, services, ingress, secrets, PVCs, and StatefulSets.
- ansible/: Ansible role for provisioning AWS resources such as ECR, EKS, RDS, Elasticache, SQS and CloudFront. Standard structure with tasks, vars, etc.
- docs/: Additional documentation, including infrastructure diagram.

## Requirements

### Local Kubernetes:

- Minikube installed (`minikube start` to start).
- kubectl configured (`kubectl cluster-info` to verify).
- Ingress Controller enabled: `minikube addons enable ingress`.
- Docker running (for building the app image).

### Ansible:

- Ansible installed (`ansible --version`).
- AWS credentials configured (via `aws configure` or environment variables: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`).
- Ansible collections: `ansible-galaxy collection install community.aws amazon.aws`.

### Others:

- Git for cloning this repo.
- curl for testing the API.

## Deploying the Kubernetes environment (Minikube)

Follow these steps to deploy the stack locally. Assume the repo is cloned and you are in the root.

1. Prepare the API Image

   - Navigate to `app-src/`.
   - Build the image: `docker build -t calculator:latest .`
   - Load into Minikube: `minikube image load calculator:latest`
   - (Alternative: Run `eval $(minikube docker-env)` before the build to use Minikube's Docker).

2. Apply Kubernetes manifests

   Recommended order to avoid dependencies:

   - PSQL: `kubectl apply -f k8s/psql/`
     - Verify: `kubectl get pods -l app=postgresql` (wait until Running).

   - Redis: `kubectl apply -f k8s/redis/`
     - Verify: `kubectl get pods -l app=redis` (wait until Running).

   - App (including NGINX and Ingress): `kubectl apply -f k8s/app/`
     - Verify: `kubectl get pods -l app=calculator` and `kubectl get ingress`.

   To access externally: Run `minikube tunnel` in a separate terminal. The Ingress will be accessible via `http://localhost` or the defined host (e.g., `calculator.local`).

3. Post-deployment verifications

   - Pods: `kubectl get pods --all-namespaces` (all should be Running).
   - Services: `kubectl get svc` (check internal IPs).
   - Ingress: `kubectl describe ingress` (confirm routing rules).
   - Logs: `kubectl logs -l app=calculator` for API debugging.

## Testing the API

The API responds to HTTP requests like `http://localhost:5000/calculator/sum/3/3`. Returns JSON with result and status (calculated, cache, added).

### API usage

- First request: `curl http://localhost:5000/calculator/sum/3/3` → Should return `{"result": 6, "status": "calculated"}` (result calculated and persisted in both Redis and PSQL).
- Cached request (less than 30s): Repeat the curl → Should return `{"result": 6, "status": "cache"}` (consulted from Redis).
- After TTL (more than 30s): Wait and repeat → Should return `{"result": 6, "status": "added"}` (persisted in PSQL).
- Other operations: Test subtraction, multiplication, etc. (assume similar endpoints).

## Troubleshooting

- Image error: Make sure the image was loaded correctly.
- Ingress not accessible: Check if `minikube tunnel` is running and the host/IP is correct.
- PVC issues: `kubectl get pvc` and check storageClass (`kubectl get storageclass`).

--

## Ansible

The `aws-localstack` role provisions AWS resources for a production environment equivalent to the local one. For local development and testing, we use LocalStack to simulate AWS services without incurring real costs or requiring an actual AWS account.

#### Setting up LocalStack:
- Install LocalStack via Docker: `docker run --rm -d --name localstack -p 4566:4566 -p 4571:4571 localstack/localstack`.
- Ensure Docker is running and ports 4566 (main LocalStack port) and 4571 (for some services) are available.
- Configure your Ansible variables to point to LocalStack endpoints (e.g., set `aws_endpoint_url` to `http://localhost:4566` in your group vars).

### Requirements

- AWS credentials with permissions for ECR, EKS, RDS, etc. (using IAM roles for production and/or localstack for local tests).
- Variables: Edit `ansible/group_vars/all.yml` with values like `aws_region: us-east-1`, `cluster_name: eks-cluster`.
- For LocalStack: Docker installed and LocalStack running locally.

### Steps to execute

- Navigate to `ansible/`.
- Run the playbook: `ansible-playbook playbooks/deploy-aws.yml -i inventory/hosts.ini`
- The role will create:
  - ECR: Repository for Docker images.
  - EKS: Kubernetes cluster with nodes.
  - RDS: PostgreSQL instance.
  - Elasticache: Redis cluster.
  - SQS: Message queue.
  - CloudFront: CDN distribution for the app.