#!/bin/bash
TG_ARN=$(aws elbv2 describe-target-groups --names doc-healing-api-tg --query 'TargetGroups[0].TargetGroupArn' --region ap-south-1 --output text | tr -d '\r')
aws elbv2 describe-target-health --target-group-arn $TG_ARN --region ap-south-1 > health.json
