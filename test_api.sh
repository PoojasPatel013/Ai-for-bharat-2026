#!/bin/bash
curl -X POST http://doc-healing-alb-1100630618.ap-south-1.elb.amazonaws.com/heal/snippet \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "docs/example.md",
    "snippet_id": "test-snippet-01",
    "language": "python",
    "code": "def add(a, b)\n    return a + b",
    "errors": ["SyntaxError: expected \":\""]
  }'
