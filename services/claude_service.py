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
from services.toon_parser import parse_toon

logger = logging.getLogger(__name__)


class ClaudeService:
    """Service for analyzing receipt images using Claude AI."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5-20250929",
                 prompt_template_path: str = "prompt-combined.txt",
                 prompt_format: str = "json",
                 enable_prompt_caching: bool = False):
        """
        Initialize Claude service.

        Args:
            api_key: Anthropic API key
            model: Claude model name to use
            prompt_template_path: Path to prompt template file (legacy, not used with multi-part messages)
            prompt_format: Output format - "json" or "toon" (default: "json")
            enable_prompt_caching: Enable prompt caching to reduce API costs
        """
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.prompt_template_path = prompt_template_path
        self.prompt_format = prompt_format
        self.enable_prompt_caching = enable_prompt_caching

    def analyze_receipt(
        self,
        image_path: str,
        categories: List[tuple[int, str]],
        category_notes: Optional[List[tuple[int, str, str]]] = None,
        merchant_notes: Optional[List[tuple[str, str, str, str]]] = None,
        user_notes: Optional[str] = None
    ) -> tuple[Dict[str, Any], int, int, str]:
        """
        Analyze receipt image using Claude vision API.

        Args:
            image_path: Path to the receipt image file
            categories: List of (category_id, category_name) tuples from database
            category_notes: Optional list of (category_id, category_name, ai_notes) tuples
            merchant_notes: Optional list of (name, address, city, ai_notes) tuples
            user_notes: Optional user-provided notes from image caption

        Returns:
            Tuple of (receipt_data, input_tokens, output_tokens, raw_response)
            - receipt_data: Parsed dict (from JSON or TOON)
            - input_tokens: Number of input tokens used
            - output_tokens: Number of output tokens used
            - raw_response: Raw string response from Claude (JSON or TOON)

        Raises:
            FileNotFoundError: If image or prompt file not found
            anthropic.APIError: If Claude API call fails
            json.JSONDecodeError: If response is not valid JSON (when format is "json")
            ValueError: If response is not valid TOON (when format is "toon")
        """
        # Build multi-part system messages
        system_messages = self._build_system_messages(categories, category_notes, merchant_notes)

        # Load and encode image
        image_data = self._load_image(image_path)

        # Determine media type from file extension
        media_type = self._get_media_type(image_path)

        logger.info(f"Analyzing receipt image: {image_path} (caching: {self.enable_prompt_caching})")

        try:
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
                    system=system_messages,
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
            if response_text.startswith("```toon"):
                response_text = response_text[7:]  # Remove ```toon
            elif response_text.startswith("```json"):
                response_text = response_text[7:]  # Remove ```json
            elif response_text.startswith("```"):
                response_text = response_text[3:]  # Remove ```
            if response_text.endswith("```"):
                response_text = response_text[:-3]  # Remove trailing ```
            response_text = response_text.strip()

            logger.debug(f"Claude cleaned response: {response_text[:200]}...")

            # Save raw response before parsing
            raw_response = response_text

            # Parse based on format
            if self.prompt_format == "toon":
                receipt_data = parse_toon(response_text)
                logger.debug(f"Parsed TOON response into dict with {len(receipt_data)} top-level keys")
            else:
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
            return receipt_data, input_tokens, output_tokens, raw_response

        except anthropic.APIError as e:
            logger.error(f"Claude API error: {e}")
            raise
        except json.JSONDecodeError as e:
            # Only if format is JSON
            if self.prompt_format == "json":
                logger.error(f"Failed to parse Claude response as JSON: {e}")
                logger.error(f"Response text (first 500 chars): {response_text[:500]}")
                raise
            else:
                # Should not happen for TOON
                logger.error(f"Unexpected JSON decode error with TOON format: {e}")
                raise
        except ValueError as e:
            # TOON parsing errors or other validation errors
            logger.error(f"Failed to parse Claude response: {e}")
            if 'response_text' in locals():
                logger.error(f"Response text (first 500 chars): {response_text[:500]}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during receipt analysis: {e}")
            raise

    def _prepare_prompt(
        self,
        template_path: str,
        categories: List[tuple[int, str]],
        category_notes: Optional[List[tuple[int, str, str]]] = None,
        merchant_notes: Optional[List[tuple[str, str, str, str]]] = None
    ) -> str:
        """
        Load prompt template and inject categories list, category notes, and merchant notes.

        Args:
            template_path: Path to prompt template file
            categories: List of (category_id, category_name) tuples
            category_notes: Optional list of (category_id, category_name, ai_notes) tuples
            merchant_notes: Optional list of (name, address, city, ai_notes) tuples

        Returns:
            Complete prompt text with categories and notes injected
        """
        template_file = Path(template_path)
        if not template_file.exists():
            raise FileNotFoundError(f"Prompt template not found: {template_path}")

        with open(template_file, 'r', encoding='utf-8') as f:
            template = f.read()

        # Format categories as bullet list with IDs
        categories_text = "\n".join(f"- [{cat_id}] {cat_name}" for cat_id, cat_name in categories)

        # Replace placeholder with actual categories
        prompt = template.replace(">> list of categories <<", categories_text)

        # Format category notes
        if category_notes and len(category_notes) > 0:
            notes_text = "The following category-specific guidelines, prefer these rules over default assignment logic:\n"
            for category_id, category_name, ai_note in category_notes:
                notes_text += f"- [{category_id}] {category_name} - Note: {ai_note}\n"
            logger.debug(f"Added {len(category_notes)} category notes to prompt")
        else:
            notes_text = ""
            logger.debug("No category notes to add to prompt")

        # Replace placeholder with category notes
        prompt = prompt.replace(">> category notes <<", notes_text)

        # Format merchant notes
        if merchant_notes and len(merchant_notes) > 0:
            merchant_text = "The following merchants have special recognition or categorization rules:\n"
            for name, address, city, ai_note in merchant_notes:
                merchant_text += f"- {name}"
                if city:
                    merchant_text += f", {city}"
                merchant_text += f" - Note: {ai_note}\n\n"
            logger.debug(f"Added {len(merchant_notes)} merchant notes to prompt")
        else:
            merchant_text = "No special merchant recognition rules defined."
            logger.debug("No merchant notes to add to prompt")

        # Replace placeholder with merchant notes
        prompt = prompt.replace(">> merchant notes <<", merchant_text)

        logger.debug(f"Prompt prepared with {len(categories)} categories")
        return prompt

    def _build_system_messages(
        self,
        categories: List[tuple[int, str]],
        category_notes: Optional[List[tuple[int, str, str]]] = None,
        merchant_notes: Optional[List[tuple[str, str, str, str]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Build multi-part system messages for Claude API.

        All messages are cacheable for maximum token savings.

        Args:
            categories: List of (category_id, category_name) tuples
            category_notes: List of (category_id, category_name, ai_notes) tuples
            merchant_notes: List of (name, address, city, ai_notes) tuples

        Returns:
            List of system message dicts for Claude API
        """
        system_messages = []

        # Message 1: Main prompt (static, cacheable)
        main_prompt_path = Path("prompt_main.txt")
        if not main_prompt_path.exists():
            raise FileNotFoundError(f"Main prompt not found: {main_prompt_path}")

        with open(main_prompt_path, 'r', encoding='utf-8') as f:
            main_prompt = f.read()

        main_message = {
            "type": "text",
            "text": main_prompt
        }
        if self.enable_prompt_caching:
            main_message["cache_control"] = {"type": "ephemeral"}

        system_messages.append(main_message)

        # Message 2: Output format specification (static, cacheable)
        format_prompt_path = Path("prompt_output_format_specification.txt")
        if not format_prompt_path.exists():
            raise FileNotFoundError(f"Format spec not found: {format_prompt_path}")

        with open(format_prompt_path, 'r', encoding='utf-8') as f:
            format_spec = f.read()

        format_message = {
            "type": "text",
            "text": format_spec
        }
        if self.enable_prompt_caching:
            format_message["cache_control"] = {"type": "ephemeral"}

        system_messages.append(format_message)

        # Message 3: Categories (semi-static, cacheable)
        # Changes infrequently (only when categories/notes are added/modified)
        categories_text = self._format_categories_message(categories, category_notes)
        categories_message = {
            "type": "text",
            "text": categories_text
        }
        if self.enable_prompt_caching:
            categories_message["cache_control"] = {"type": "ephemeral"}

        system_messages.append(categories_message)

        # Message 4: Merchant-specific guidelines (semi-static, cacheable, optional)
        # Changes infrequently (only when merchant notes are added/modified)
        if merchant_notes and len(merchant_notes) > 0:
            merchant_text = self._format_merchant_message(merchant_notes)
            merchant_message = {
                "type": "text",
                "text": merchant_text
            }
            if self.enable_prompt_caching:
                merchant_message["cache_control"] = {"type": "ephemeral"}

            system_messages.append(merchant_message)

        logger.debug(f"Built {len(system_messages)} system messages")
        return system_messages

    def _format_categories_message(
        self,
        categories: List[tuple[int, str]],
        category_notes: Optional[List[tuple[int, str, str]]] = None
    ) -> str:
        """
        Format categories message matching .prompt_ng_v2/categories.txt structure.

        Integrates category notes inline with pipe separator.

        Args:
            categories: List of (category_id, category_name) tuples
            category_notes: Optional list of (category_id, category_name, ai_notes) tuples

        Returns:
            Formatted categories message

        Example:
            [44] Child: Food | Assign Haribo bears here instead of [35] Food: Sweets
        """
        # Build dict of category_id -> ai_notes for quick lookup
        notes_map = {}
        if category_notes:
            for cat_id, cat_name, ai_note in category_notes:
                notes_map[cat_id] = ai_note

        # Build category lines
        lines = [
            "CATEGORIZE",
            "",
            "Use the following table to assign categories to the items. Each category has an ID (in square brackets) and a name. Use the category ID in your response. Some categories have additional notes after the \"|\" sign. Respect them.",
            ""
        ]

        for cat_id, cat_name in sorted(categories, key=lambda x: x[1]):
            line = f"[{cat_id}] {cat_name}"
            if cat_id in notes_map:
                line += f" | {notes_map[cat_id]}"
            lines.append(line)

        return "\n".join(lines)

    def _format_merchant_message(
        self,
        merchant_notes: List[tuple[str, str, str, str]]
    ) -> str:
        """
        Format merchant-specific guidelines message.

        Args:
            merchant_notes: List of (name, address, city, ai_notes) tuples

        Returns:
            Formatted message matching .prompt_ng_v2/specifics.txt structure

        Example:
            MERCHANT-SPECIFIC guidelines:
            The following merchants have special recognition or categorization rules:
            - ALDI, Werl - Note: Quantity line ABOVE item line
        """
        lines = [
            "MERCHANT-SPECIFIC guidelines:",
            "The following merchants have special recognition or categorization rules:"
        ]

        for name, address, city, ai_note in merchant_notes:
            merchant_label = name
            if city:
                merchant_label += f", {city}"
            lines.append(f"- {merchant_label} - Note: {ai_note}")

        return "\n".join(lines)

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
