import sys
from rq.cli import worker as rq_worker_cli

sys.argv = ["rq", "worker", "webhooks", "validation", "healing", "--url", "redis://foo:6379/1"]
try:
    rq_worker_cli()
except Exception as e:
    print("Caught:", type(e), e)
