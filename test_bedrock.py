import json
import logging
from doc_healing.llm.bedrock_client import BedrockLLMClient

logging.basicConfig(level=logging.INFO)

client = BedrockLLMClient()
print("Testing default client (us-east-1)...")
try:
    result = client.generate_correction("Fix this code: `print 'hello'`", "You are an AI code healer.")
    print("Result:", repr(result))
except Exception as e:
    print("Error:", e)

# Now test with explicit region mapping based on settings
from doc_healing.config import get_settings
print("Testing client with ap-south-1...")
client_aps1 = BedrockLLMClient(region_name="ap-south-1")
try:
    result2 = client_aps1.generate_correction("Fix this code: `print 'hello'`", "You are an AI code healer.")
    print("Result 2:", repr(result2))
except Exception as e:
    print("Error 2:", e)
