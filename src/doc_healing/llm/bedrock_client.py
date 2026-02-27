import json
import logging
from typing import Optional
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

class BedrockLLMClient:
    def __init__(self, region_name: str = "us-east-1"):
        """Initialize the Bedrock client."""
        # In production this will pick up credentials from the environment or EC2/ECS role.
        self.client = boto3.client(service_name='bedrock-runtime', region_name=region_name)
        # Default to Claude 3.5 Sonnet for complex code tasks
        self.default_model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"
        # Fallback to Claude 3 Haiku for faster/cheaper queries or if Sonnet fails
        self.fallback_model_id = "anthropic.claude-3-haiku-20240307-v1:0"

    def generate_correction(self, prompt: str, system_prompt: str, use_fallback: bool = False) -> Optional[str]:
        """
        Send a prompt to Anthropic Claude via Bedrock to get a code correction.
        """
        model_id = self.fallback_model_id if use_fallback else self.default_model_id
        
        # Format for Claude 3 Messages API
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.1, # Low temperature for more deterministic code generation
        }

        try:
            logger.info(f"Invoking Bedrock model: {model_id}")
            response = self.client.invoke_model(
                modelId=model_id,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            )
            
            response_body = json.loads(response.get('body').read())
            
            # The response from Claude 3 Messages API has content as an array of blocks
            content_blocks = response_body.get('content', [])
            if content_blocks and len(content_blocks) > 0:
                return content_blocks[0].get('text', '')
                
            return None
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            logger.error(f"Bedrock API error: {e} (Code: {error_code})")
            
            # Try fallback if not already using it and it's a transient or capacity error (e.g. ThrottlingException)
            if not use_fallback and error_code in ['ThrottlingException', 'ModelStreamErrorException', 'InternalServerException']:
                logger.info(f"Falling back to {self.fallback_model_id}...")
                return self.generate_correction(prompt, system_prompt, use_fallback=True)
            return None
        except Exception as e:
            logger.error(f"Unexpected error calling Bedrock: {e}")
            return None
