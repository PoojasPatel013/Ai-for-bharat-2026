#!/bin/bash
# deploy/aws/setup_infrastructure.sh
# 
# This script contains the AWS CLI commands required to provision the backend
# infrastructure for the Doc Healing Engine. Please populate the placeholders
# (VPC_ID, SUBNET_IDS, SECURITY_GROUP) before running.

set -e

AWS_REGION="ap-south-1"
ACCOUNT_ID="122610498241"

# --- PLACEHOLDERS ---
VPC_ID="vpc-xxxxxx" # Replace with your VPC ID
SUBNET_IDS="subnet-xxxxxx subnet-yyyyyy" # Replace with your subnet IDs (space separated)
SECURITY_GROUP="sg-xxxxxx" # Replace with your SG ID

echo "Starting deployment setup for Doc Healing Engine in $AWS_REGION..."

# 1. Container Registry Setup (AWS ECR) [Task 16.1]
echo "Creating ECR Repository..."
aws ecr create-repository \
    --repository-name doc-healing-engine \
    --region $AWS_REGION || echo "Repository may already exist."

echo "Authenticating Docker with ECR..."
aws ecr get-login-password --region $AWS_REGION | \
    docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# 2. Database Setup (Amazon RDS PostgreSQL) [Task 16.2]
echo "Creating RDS PostgreSQL Instance..."
aws rds create-db-instance \
    --db-instance-identifier doc-healing-db \
    --db-instance-class db.t4g.micro \
    --engine postgres \
    --master-username postgres \
    --master-user-password "YourSecurePassword123!" \
    --allocated-storage 20 \
    --vpc-security-group-ids $SECURITY_GROUP || echo "DB is launching or already exists."

# 3. Queue Setup (Amazon ElastiCache Redis) [Task 16.2]
echo "Creating ElastiCache Redis Instance..."
aws elasticache create-cache-cluster \
    --cache-cluster-id doc-healing-redis \
    --engine redis \
    --cache-node-type cache.t4g.micro \
    --num-cache-nodes 1 \
    --security-group-ids $SECURITY_GROUP || echo "Redis is launching or already exists."

# 4. Compute Setup (ECS Cluster) [Task 16.3]
echo "Creating ECS Cluster..."
aws ecs create-cluster --cluster-name doc-healing-cluster

# 5. Network Exposure (Application Load Balancer) [Task 16.4]
echo "Creating Application Load Balancer..."
ALB_ARN=$(aws elbv2 create-load-balancer \
    --name doc-healing-alb \
    --subnets $SUBNET_IDS \
    --security-groups $SECURITY_GROUP \
    --query 'LoadBalancers[0].LoadBalancerArn' \
    --output text)

echo "Creating Target Group for API on port 8000..."
TG_ARN=$(aws elbv2 create-target-group \
    --name doc-healing-api-tg \
    --protocol HTTP \
    --port 8000 \
    --vpc-id $VPC_ID \
    --target-type ip \
    --query 'TargetGroups[0].TargetGroupArn' \
    --output text)

echo "Creating Listener for ALB..."
aws elbv2 create-listener \
    --load-balancer-arn $ALB_ARN \
    --protocol HTTP \
    --port 80 \
    --default-actions Type=forward,TargetGroupArn=$TG_ARN

echo ""
echo "=== IMPORTANT NEXT STEPS ==="
echo "1. Wait for RDS and ElastiCache to completely provision."
echo "2. Note their endpoints."
echo "3. Create a secrets.json file locally:"
echo '   {
        "DATABASE_URL": "postgresql://postgres:YourSecurePassword123!@doc-healing-db...rds.amazonaws.com:5432/postgres",
        "REDIS_HOST": "doc-healing-redis...cache.amazonaws.com",
        "REDIS_PORT": "6379"
      }'
echo "4. Push credentials to AWS Secrets Manager [Task 17.1]:"
echo "   aws secretsmanager create-secret --name doc-healing/production/secrets --secret-string file://secrets.json"
echo "5. Push your code to GitHub to trigger '.github/workflows/deploy.yml' to build the Docker image and deploy your ECS Task Definitions."
echo "============================"
