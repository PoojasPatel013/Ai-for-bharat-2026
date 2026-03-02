from doc_healing.llm.bedrock_client import BedrockLLMClient
client = BedrockLLMClient()
result = client.generate_correction("Fix: print(add(2)) where def add(a,b): return a+b", "You are a code fixer. Output only the corrected code.")
print("SUCCESS:", repr(result[:100]) if result else "FAILED: None")
