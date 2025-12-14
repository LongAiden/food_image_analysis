import json
import re
import logfire
from typing import Optional

import google.generativeai as genai

from backend.models.models import NutritionAnalysis, SYSTEM_PROMPT
from backend.services.image_utils import PreparedImage


class GeminiAnalyzer:
    """Service for analyzing food images using Google Generative AI directly."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.5-flash"):
        if not api_key:
            raise ValueError("GOOGLE_API_KEY must be set")

        self.model_name = model
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(self.model_name)

        logfire.info("Gemini Analyzer initialized", model=self.model_name)

    @staticmethod
    def _parse_model_output(text: str) -> dict:
        """Extract JSON payload from model response text."""
        if not text or not text.strip():
            raise ValueError("Model returned an empty response")

        cleaned = text.strip()

        # Strip fenced code blocks like ```json ... ```
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if "\n" in cleaned:
                cleaned = cleaned.split("\n", 1)[1]
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].lstrip()

        try:
            return json.loads(cleaned)
        except Exception:
            # Try to extract the first JSON object in the string
            match = re.search(r"\{[\s\S]*\}", cleaned)
            if match:
                return json.loads(match.group(0))
            raise

    async def analyze_image(
        self, prepared: PreparedImage, filename: str = "image.jpg"
    ) -> NutritionAnalysis:
        """Analyze a prepared image and return nutrition information."""
        try:
            prompt = (
                SYSTEM_PROMPT
                + "\nReturn ONLY valid JSON with fields: food_name, calories, sugar, protein, carbs, fat, fiber, others, health_score."
            )

            response = await self.model.generate_content_async(
                [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": prepared.content_type,
                            "data": prepared.image_bytes,
                        }
                    },
                ],
            )

            text = (response.text or "").strip()
            data = self._parse_model_output(text)
            nutrition = NutritionAnalysis.model_validate(data)

            logfire.info(
                "Analysis completed",
                format=prepared.image_format,
            )
            return nutrition

        except Exception as exc:
            logfire.error(f"Error analyzing image {filename}: {exc}")
            raise ValueError(f"Error analyzing image {filename}: {exc}")
