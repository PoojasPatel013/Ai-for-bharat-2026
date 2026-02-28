#!/bin/bash
set -x
TG_ARN=$(aws elbv2 describe-target-groups --names doc-healing-api-tg --query 'TargetGroups[0].TargetGroupArn' --region ap-south-1 --output text | tr -d '\r')
aws ecs create-service \
    --cluster doc-healing-cluster \
    --service-name doc-healing-api-service \
    --task-definition arn:aws:ecs:ap-south-1:122610498241:task-definition/doc-healing-api:9 \
    --desired-count 1 \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[subnet-01026b3046fafc6f1,subnet-03f527b3f57d450b7],securityGroups=[sg-0ed4656c2242bc381],assignPublicIp=ENABLED}" \
    --load-balancers "targetGroupArn=$TG_ARN,containerName=doc-healing-app,containerPort=8000" \
    --region ap-south-1
