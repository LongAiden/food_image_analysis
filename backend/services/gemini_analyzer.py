import os
import base64
import logfire
from typing import Optional
from PIL import Image
from io import BytesIO
from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

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

        provider = GoogleProvider(api_key=self.api_key)
        # Initialize Pydantic AI Agent with Gemini model
        self.model = GoogleModel('gemini-2.5-flash', provider=provider)

        # Create Pydantic AI agent with structured output
        self.agent = Agent(
            model=self.model,
            output_type=NutritionAnalysis,
            system_prompt=SYSTEM_PROMPT
        )

        logfire.info("✓ Gemini Analyzer initialized successfully")
    
    async def analyze_image_from_path(self, image_path: str):
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image file not found at path: {image_path}")

        # 1. Read the raw image data (bytes) from the local file path
        with open(image_path, "rb") as f:
            image_data = f.read() # Read data into 'image_data' (bytes object)

        # 2. Convert the byte data into a PIL Image object
        #    This is the crucial step that was missing/misplaced.
        img_object = Image.open(BytesIO(image_data))
        
        # logfire.info is a placeholder, uncomment if you are using it
        # logfire.info(f"Image loaded: {img_object.format} {img_object.size}")

        # FIX: Convert RGBA to RGB before proceeding, as JPEG does not support the Alpha channel.
        if img_object.mode == 'RGBA':
            # Create a white background
            background = Image.new('RGB', img_object.size, (255, 255, 255))
            # Paste the RGBA image onto the background, effectively removing transparency
            background.paste(img_object, mask=img_object.split()[3]) # Use the alpha channel as the mask
            img_object = background # Update img_object to the new RGB image
        
        # Encode image to base64 for Gemini (Existing code logic)
        buffered = BytesIO()
        
        # Determine the format to save as. We can now safely set this to 'JPEG' 
        # since we've handled the RGBA conversion.
        save_format = "JPEG"
        
        # Save the processed PIL Image object to the buffer
        img_object.save(buffered, format=save_format)
        
        img_base64 = base64.b64encode(buffered.getvalue()).decode()

        # Run Pydantic AI agent with image (Existing code logic)
        # Note: We pass the image data as part of the prompt
        result = await self.agent.run(
            f"Analyze this food image and provide nutritional information.",
            message_history=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Analyze this food image"},
                    # Ensure the data URI header matches the save_format
                    {"type": "image_url", "image_url": {"url": f"data:image/{save_format.lower()};base64,{img_base64}"}}
                ]
            }]
        )
        return result

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
            img_object = Image.open(BytesIO(image_data))

            # FIX: Convert RGBA to RGB before proceeding, as JPEG does not support the Alpha channel.
            if img_object.mode == 'RGBA':
                # Create a white background
                background = Image.new('RGB', img_object.size, (255, 255, 255))
                # Paste the RGBA image onto the background, effectively removing transparency
                background.paste(img_object, mask=img_object.split()[3]) # Use the alpha channel as the mask
                img_object = background # Update img_object to the new RGB image

            logfire.info(f"Image loaded: {img_object.format} {img_object.size}")

            # Encode image to base64 for Gemini
            buffered = BytesIO()
            img_object.save(buffered, format=img_object.format or "JPEG")
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

            nutrition_data = result.output

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
