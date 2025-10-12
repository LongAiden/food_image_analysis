import os
import base64
import logfire
from typing import Optional
from PIL import Image
from io import BytesIO
import google.generativeai as genai
from pydantic_ai import Agent
from pydantic_ai.models.gemini import GoogleModel

from backend.models.models import NutritionAnalysis, SYSTEM_PROMPT


class GeminiAnalyzer: # Add key
    """Service for analyzing food images using Gemini with Pydantic AI"""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize Gemini analyzer

        Args:
            api_key: Google API key for Gemini. If None, reads from GEMINI_API_KEY env var
        """
        self.api_key = api_key

        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")

        # Configure Gemini
        genai.configure(api_key=self.api_key)

        # Initialize Pydantic AI Agent with Gemini model
        self.model = GoogleModel(
            model_name='gemini-2.5-flash',
            api_key=self.api_key
        )

        # Create Pydantic AI agent with structured output
        self.agent = Agent(
            model=self.model,
            result_type=NutritionAnalysis,
            system_prompt=SYSTEM_PROMPT
        )

        logfire.info("✓ Gemini Analyzer initialized successfully")

    async def analyze_image(self, image_data: bytes, filename: str = "image.jpg") -> NutritionAnalysis:
        """Analyze food image and return nutrition information

        Args:
            image_data: Raw image bytes
            filename: Original filename for logging

        Returns:
            NutritionAnalysis object with structured nutrition data
        """
        try:
            logfire.info(f"Starting analysis for image: {filename}")

            # Validate image
            image = Image.open(BytesIO(image_data))
            logfire.info(f"Image loaded: {image.format} {image.size}")

            # Encode image to base64 for Gemini
            buffered = BytesIO()
            image.save(buffered, format=image.format or "JPEG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode()

            # Run Pydantic AI agent with image
            # Note: We pass the image data as part of the prompt
            result = await self.agent.run(
                f"Analyze this food image and provide nutritional information.",
                message_history=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Analyze this food image"},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}}
                    ]
                }]
            )

            nutrition_data = result.data

            logfire.info(
                f"Analysis completed for {filename}",
                calories=nutrition_data.calories,
                protein=nutrition_data.protein,
                sugar=nutrition_data.sugar
            )

            return nutrition_data

        except Exception as e:
            logfire.error(f"Error analyzing image {filename}: {str(e)}")
            raise ValueError(f"Error analyzing image {filename}: {str(e)}")

    async def analyze_from_base64(self, base64_string: str, filename: str = "image.jpg") -> NutritionAnalysis:
        """Analyze food image from base64 string

        Args:
            base64_string: Base64 encoded image data
            filename: Original filename for logging

        Returns:
            NutritionAnalysis object with structured nutrition data
        """
        try:
            # Remove data URL prefix if present
            if "," in base64_string:
                base64_string = base64_string.split(",")[1]

            # Decode base64 to bytes
            image_data = base64.b64decode(base64_string)

            return await self.analyze_image(image_data, filename)

        except Exception as e:
            logfire.error(f"Invalid base64 image data: {str(e)}")
            raise ValueError(f"Invalid base64 image data: {str(e)}")

    def validate_image(self, image_data: bytes, max_size_mb: int = 10) -> bool:
        """Validate image data

        Args:
            image_data: Raw image bytes
            max_size_mb: Maximum allowed file size in MB

        Returns:
            True if valid, raises ValueError otherwise
        """
        # Check file size
        size_mb = len(image_data) / (1024 * 1024)
        if size_mb > max_size_mb:
            logfire.error(f"Image too large: {size_mb:.2f}MB (max: {max_size_mb}MB)")
            raise ValueError(f"Image too large: {size_mb:.2f}MB (max: {max_size_mb}MB)")

        # Check if valid image
        try:
            image = Image.open(BytesIO(image_data))
            image.verify()

            # Check format
            if image.format not in ['JPEG', 'PNG', 'JPG', 'WEBP', 'GIF']:
                logfire.error(f"Unsupported image format: {image.format}")
                raise ValueError(f"Unsupported image format: {image.format}")

            return True

        except Exception as e:
            logfire.error(f"Invalid image file: {str(e)}")
            raise ValueError(f"Invalid image file: {str(e)}")
