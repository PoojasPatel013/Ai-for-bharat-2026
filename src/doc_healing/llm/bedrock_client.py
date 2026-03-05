import json
import logging
import re
from typing import Optional
import boto3
from botocore.exceptions import ClientError
from doc_healing.config import get_settings

logger = logging.getLogger(__name__)


class BedrockLLMClient:
    def __init__(self, region_name: str = "ap-south-1"):
        """Initialize the Bedrock client with boto3/IAM credentials."""
        settings = get_settings()

        self.client = boto3.client(service_name='bedrock-runtime', region_name=region_name)
        self.default_model_id = settings.bedrock_model_id
        self.fallback_model_id = settings.bedrock_fallback_model_id

    def generate_correction(self, prompt: str, system_prompt: str, use_fallback: bool = False) -> Optional[str]:
        """Send a prompt to the configured Bedrock model to get a code correction.

        Uses the Converse API which works with both Amazon Nova and Anthropic Claude models.
        Primary model: Amazon Nova Pro (no Marketplace subscription needed).
        Fallback model: Claude 4 Sonnet via APAC cross-region inference.
        """
        model_id = self.fallback_model_id if use_fallback else self.default_model_id

        try:
            logger.info(f"Invoking Bedrock model: {model_id}")
            response = self.client.converse(
                modelId=model_id,
                system=[{"text": system_prompt}],
                messages=[
                    {
                        "role": "user",
                        "content": [{"text": prompt}],
                    }
                ],
                inferenceConfig={
                    "maxTokens": 4096,
                    "temperature": 0.1,
                },
            )

            output_message = response.get("output", {}).get("message", {})
            content_blocks = output_message.get("content", [])
            if content_blocks and len(content_blocks) > 0:
                raw_text = content_blocks[0].get("text", "")
                return self._strip_code_fences(raw_text)

            return None

        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            error_message = e.response.get('Error', {}).get('Message')
            logger.error(f"Bedrock API error: {e} (Code: {error_code}, Message: {error_message})")

            if not use_fallback and error_code in [
                'ThrottlingException', 'ModelStreamErrorException',
                'InternalServerException', 'AccessDeniedException',
            ]:
                logger.info(f"Falling back to {self.fallback_model_id}...")
                return self.generate_correction(prompt, system_prompt, use_fallback=True)
            return None
        except Exception as e:
            logger.error(f"Unexpected error calling Bedrock: {e}")
            return None

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        """Remove markdown code fences from AI response."""
        text = text.strip()
        match = re.match(r'^```\w*\s*\n(.*?)```\s*$', text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text
