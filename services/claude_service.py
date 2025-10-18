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
from services.metrics_service import MetricsService

logger = logging.getLogger(__name__)


class ClaudeService:
    """Service for analyzing receipt images using Claude AI."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5-20250929",
                 prompt_template_path: str = "prompt-combined.txt",
                 enable_prompt_caching: bool = False):
        """
        Initialize Claude service.

        Args:
            api_key: Anthropic API key
            model: Claude model name to use
            prompt_template_path: Path to prompt template file
            enable_prompt_caching: Enable prompt caching to reduce API costs
        """
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.prompt_template_path = prompt_template_path
        self.enable_prompt_caching = enable_prompt_caching

    def analyze_receipt(
        self,
        image_path: str,
        categories: List[str],
        category_notes: Optional[List[tuple[str, str]]] = None,
        merchant_notes: Optional[List[tuple[str, str, str, str]]] = None,
        user_notes: Optional[str] = None
    ) -> tuple[Dict[str, Any], int, int]:
        """
        Analyze receipt image using Claude vision API.

        Args:
            image_path: Path to the receipt image file
            categories: List of category names from database
            category_notes: Optional list of (category_name, ai_notes) tuples
            merchant_notes: Optional list of (name, address, city, ai_notes) tuples
            user_notes: Optional user-provided notes from image caption

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
        prompt = self._prepare_prompt(self.prompt_template_path, categories, category_notes, merchant_notes)

        # Load and encode image
        image_data = self._load_image(image_path)

        # Determine media type from file extension
        media_type = self._get_media_type(image_path)

        logger.info(f"Analyzing receipt image: {image_path} (caching: {self.enable_prompt_caching})")

        try:
            # Prepare system message with optional cache_control
            system_message = {
                "type": "text",
                "text": prompt
            }
            if self.enable_prompt_caching:
                system_message["cache_control"] = {"type": "ephemeral"}

            # Prepare messages list - start with image
            messages_content = [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_data,
                    },
                }
            ]

            # Add user notes if provided
            if user_notes:
                messages_content.append({
                    "type": "text",
                    "text": f"USER NOTE: {user_notes}"
                })
                logger.info(f"Added user notes to prompt: {user_notes[:50]}...")

            # Call Claude API with vision (track timing)
            with MetricsService.claude_api_duration.time():
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    system=[system_message],
                    messages=[
                        {
                            "role": "user",
                            "content": messages_content,
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
            cache_creation = getattr(response.usage, 'cache_creation_input_tokens', 0)
            cache_read = getattr(response.usage, 'cache_read_input_tokens', 0)

            # Record metrics
            MetricsService.record_tokens(
                model=self.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read_tokens=cache_read,
                cache_creation_tokens=cache_creation
            )

            # Log cache statistics if caching is enabled
            cache_info = ""
            if self.enable_prompt_caching and (cache_creation > 0 or cache_read > 0):
                cache_info = f", cache: {cache_creation} created / {cache_read} read"

            logger.info(f"Receipt analysis successful, status: {receipt_data.get('extraction_status', 'unknown')}, "
                       f"tokens: {input_tokens} in / {output_tokens} out{cache_info}")
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

    def _prepare_prompt(
        self,
        template_path: str,
        categories: List[str],
        category_notes: Optional[List[tuple[str, str]]] = None,
        merchant_notes: Optional[List[tuple[str, str, str, str]]] = None
    ) -> str:
        """
        Load prompt template and inject categories list, category notes, and merchant notes.

        Args:
            template_path: Path to prompt template file
            categories: List of category names
            category_notes: Optional list of (category_name, ai_notes) tuples
            merchant_notes: Optional list of (name, address, city, ai_notes) tuples

        Returns:
            Complete prompt text with categories and notes injected
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

        # Format category notes
        if category_notes and len(category_notes) > 0:
            notes_text = "The following categories have special assignment rules. When you encounter items matching these descriptions, prioritize these notes over general categorization logic:\n\n"
            for category_name, ai_note in category_notes:
                notes_text += f"- {category_name}\n  Note: {ai_note}\n\n"
            logger.debug(f"Added {len(category_notes)} category notes to prompt")
        else:
            notes_text = "No special category assignment rules defined."
            logger.debug("No category notes to add to prompt")

        # Replace placeholder with category notes
        prompt = prompt.replace(">> category notes <<", notes_text)

        # Format merchant notes
        if merchant_notes and len(merchant_notes) > 0:
            merchant_text = "The following merchants have special recognition or categorization rules:\n\n"
            for name, address, city, ai_note in merchant_notes:
                merchant_text += f"- {name}"
                if city:
                    merchant_text += f", {city}"
                if address:
                    merchant_text += f"\n  Address: {address}"
                merchant_text += f"\n  Note: {ai_note}\n\n"
            logger.debug(f"Added {len(merchant_notes)} merchant notes to prompt")
        else:
            merchant_text = "No special merchant recognition rules defined."
            logger.debug("No merchant notes to add to prompt")

        # Replace placeholder with merchant notes
        prompt = prompt.replace(">> merchant notes <<", merchant_text)

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
