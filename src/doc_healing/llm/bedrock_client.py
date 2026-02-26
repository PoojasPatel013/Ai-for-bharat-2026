"""AWS Bedrock client for documentation healing."""

import json
import logging
from typing import Optional, Dict, Any

from botocore.exceptions import ClientError
from doc_healing.config import get_settings

logger = logging.getLogger(__name__)

class BedrockClient:
    """Client for interacting with AWS Bedrock."""
    
    def __init__(self):
        """Initialize the Bedrock client."""
        # defer boto3 import so it doesn't crash if optional dependency missing
        import boto3
        self.settings = get_settings()
        self.client = boto3.client('bedrock-runtime', region_name=getattr(self.settings, 'aws_region', 'us-east-1'))
        
    def _invoke_model(self, model_id: str, prompt: str, max_tokens: int = 2000) -> Optional[str]:
        """Invoke a Bedrock model with the given prompt.
        
        Args:
            model_id: The ID of the primary model.
            prompt: The formatted prompt to send to the model.
            max_tokens: Maximum number of tokens to generate.
            
        Returns:
            The generated code, or None if the request failed.
        """
        try:
            # We use Anthropic Claude 3 Messages API format
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "system": "You are a documentation auto-fixer. Given this broken code snippet and this error log, output only the corrected code snippet.",
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            })
            
            response = self.client.invoke_model(
                modelId=model_id,
                body=body,
                contentType="application/json",
                accept="application/json",
            )
            
            response_body = json.loads(response.get('body').read())
            
            content = response_body.get('content', [])
            if content and len(content) > 0:
                text = content[0].get('text', '')
                return self._extract_code(text)
            return None
            
        except ClientError as e:
            logger.error(f"Bedrock invocation failed: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error calling Bedrock: {str(e)}")
            return None
            
    def heal_code(self, code: str, language: str, errors: list[str]) -> Optional[str]:
        """Attempt to heal broken code using Claude.
        
        Args:
            code: The original broken code snippet.
            language: The programming language of the snippet.
            errors: A list of errors encountered when validating the code.
            
        Returns:
            The healed code snippet, or None if healing failed.
        """
        from doc_healing.llm.prompts import generate_healing_prompt
        
        prompt = generate_healing_prompt(code, language, errors)
        
        # Try primary model first
        logger.info(f"Attempting to heal code using primary model: {self.settings.bedrock_model_id}")
        result = self._invoke_model(self.settings.bedrock_model_id, prompt)
        
        if result:
            return result
            
        # Try fallback model if configured and primary failed
        if self.settings.bedrock_fallback_model_id:
            logger.warning(f"Primary model failed. Attempting fallback model: {self.settings.bedrock_fallback_model_id}")
            result = self._invoke_model(self.settings.bedrock_fallback_model_id, prompt)
            if result:
                return result
                
        logger.error("All models failed to heal the code.")
        return None
        
    def _extract_code(self, text: str) -> str:
        """Extract just the code from the LLM's response.
        
        Finds the first markdown code block and returns its contents.
        If no code block is found, returns the raw text (assuming the LLM followed instructions).
        """
        lines = text.split('\n')
        in_code_block = False
        code_lines = []
        
        for line in lines:
            if line.strip().startswith('```'):
                if in_code_block:
                    # End of block
                    break
                else:
                    # Start of block
                    in_code_block = True
            elif in_code_block:
                code_lines.append(line)
                
        if code_lines:
            return '\n'.join(code_lines)
            
        return text.strip()
