"""
Claude AI service module for receipt analysis.
Handles communication with Anthropic Claude API for receipt image processing.
"""

import anthropic
import base64
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class ClaudeService:
    """Service for analyzing receipt images using Claude AI."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5-20250929",
                 prompt_template_path: str = "prompt-combined.txt"):
        """
        Initialize Claude service.

        Args:
            api_key: Anthropic API key
            model: Claude model name to use
            prompt_template_path: Path to prompt template file
        """
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.prompt_template_path = prompt_template_path

    def analyze_receipt(
        self,
        image_path: str,
        categories: List[str]
    ) -> tuple[Dict[str, Any], int, int]:
        """
        Analyze receipt image using Claude vision API.

        Args:
            image_path: Path to the receipt image file
            categories: List of category names from database

        Returns:
            Tuple of (receipt_data, input_tokens, output_tokens)
            - receipt_data: Parsed JSON response from Claude containing receipt data
            - input_tokens: Number of input tokens used
            - output_tokens: Number of output tokens used

        Raises:
            FileNotFoundError: If image or prompt file not found
            anthropic.APIError: If Claude API call fails
            json.JSONDecodeError: If response is not valid JSON
        """
        # Load and prepare prompt
        prompt = self._prepare_prompt(self.prompt_template_path, categories)

        # Load and encode image
        image_data = self._load_image(image_path)

        # Determine media type from file extension
        media_type = self._get_media_type(image_path)

        logger.info(f"Analyzing receipt image: {image_path}")

        try:
            # Call Claude API with vision
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": image_data,
                                },
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ],
                    }
                ],
            )

            # Extract text response
            if not response.content or len(response.content) == 0:
                logger.warning(f"Claude returned no content blocks. Stop reason: {response.stop_reason}")
                logger.debug(f"Full response: {response}")

                # Handle refusal specifically
                if response.stop_reason == 'refusal':
                    raise ValueError(
                        "Claude refused to process this image. This may happen if the image contains "
                        "sensitive information (credit card numbers, personal IDs) or triggers content filters. "
                        "Please try a different image or ensure no sensitive data is visible."
                    )
                else:
                    raise ValueError(f"Claude returned no content. Stop reason: {response.stop_reason}")

            response_text = response.content[0].text
            logger.debug(f"Claude raw response: {response_text}")

            # Check if response is empty
            if not response_text or not response_text.strip():
                logger.error(f"Claude returned empty response. Full response object: {response}")
                raise ValueError("Claude returned an empty response")

            # Strip markdown code blocks if present
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]  # Remove ```json
            elif response_text.startswith("```"):
                response_text = response_text[3:]  # Remove ```
            if response_text.endswith("```"):
                response_text = response_text[:-3]  # Remove trailing ```
            response_text = response_text.strip()

            logger.debug(f"Claude cleaned response: {response_text[:200]}...")

            # Parse JSON response
            receipt_data = json.loads(response_text)

            # Extract token usage
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens

            logger.info(f"Receipt analysis successful, status: {receipt_data.get('extraction_status', 'unknown')}, "
                       f"tokens: {input_tokens} in / {output_tokens} out")
            return receipt_data, input_tokens, output_tokens

        except anthropic.APIError as e:
            logger.error(f"Claude API error: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response as JSON: {e}")
            logger.error(f"Response text (first 500 chars): {response_text[:500]}")
            raise
        except ValueError as e:
            logger.error(f"Response validation error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during receipt analysis: {e}")
            raise

    def _prepare_prompt(self, template_path: str, categories: List[str]) -> str:
        """
        Load prompt template and inject categories list.

        Args:
            template_path: Path to prompt template file
            categories: List of category names

        Returns:
            Complete prompt text with categories injected
        """
        template_file = Path(template_path)
        if not template_file.exists():
            raise FileNotFoundError(f"Prompt template not found: {template_path}")

        with open(template_file, 'r', encoding='utf-8') as f:
            template = f.read()

        # Format categories as bullet list
        categories_text = "\n".join(f"- {cat}" for cat in categories)

        # Replace placeholder with actual categories
        prompt = template.replace(">> list of categories <<", categories_text)

        logger.debug(f"Prompt prepared with {len(categories)} categories")
        return prompt

    def _load_image(self, image_path: str) -> str:
        """
        Load image file and encode as base64.

        Args:
            image_path: Path to image file

        Returns:
            Base64-encoded image data
        """
        image_file = Path(image_path)
        if not image_file.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")

        with open(image_file, 'rb') as f:
            image_bytes = f.read()

        return base64.standard_b64encode(image_bytes).decode('utf-8')

    def _get_media_type(self, image_path: str) -> str:
        """
        Determine media type from file extension.

        Args:
            image_path: Path to image file

        Returns:
            MIME type string (e.g., 'image/jpeg', 'image/png')
        """
        extension = Path(image_path).suffix.lower()
        media_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp'
        }

        return media_types.get(extension, 'image/jpeg')  # Default to JPEG
