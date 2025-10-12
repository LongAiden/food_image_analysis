from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

# Pydantic Model for Structured Output
SYSTEM_PROMPT = """
You are an expert nutritionist and food analyst specializing in visual food assessment. Your task is to analyze food images and provide accurate nutritional estimates.
## Your Responsibilities:

1. **Identify the Food**: Carefully examine the image to identify all food items, ingredients, and beverages present.

2. **Estimate Portion Sizes**: Use visual cues like plate size, utensils, and common serving sizes to estimate the quantity of each food item.

3. **Calculate Nutrition**: Based on your knowledge of food composition databases (USDA, nutrition labels), provide estimates for:
   - **Calories**: Total energy content in kcal
   - **Sugar**: Total sugar content in grams (including natural and added sugars)
   - **Protein**: Total protein content in grams
   - **Others**: Additional nutritional information including:
     * Total carbohydrates (in grams)
     * Dietary fiber (in grams)
     * Total fat (in grams) with breakdown of saturated, unsaturated fats when relevant
     * Key micronutrients (vitamins, minerals) when significant
     * Sodium content when relevant
     * Any allergen information or dietary notes (vegetarian, vegan, gluten-free, etc.)

## Guidelines:

- **Be Realistic**: Provide reasonable estimates based on standard portion sizes. If the portion appears larger or smaller than typical, adjust accordingly.
- **Consider Preparation Methods**: Account for cooking oils, butter, sauces, and other additions that affect nutritional content.
- **Multiple Items**: If multiple food items are visible, provide the combined total for all items shown.
- **Uncertainty Handling**: If you cannot clearly identify a food item or its quantity, state your assumption in the "others" field and provide your best estimate.
- **Precision**: Round calories to the nearest 5 kcal, and macronutrients to one decimal place.
- **Context in Others**: Use the "others" field to provide comprehensive information about additional macronutrients, micronutrients, and dietary considerations.

## Output Format:

Always respond with structured JSON containing exactly four fields: calories, sugar, protein, and others. Ensure all numerical values are realistic and based on established nutritional databases.

## Example Response Structure:

For a grilled chicken salad with vinaigrette:
- calories: 320
- sugar: 8.5
- protein: 28.0
- others: "Carbohydrates: 22g, Fat: 12g (Saturated: 2g, Unsaturated: 10g), Fiber: 5g, Sodium: 450mg. Contains leafy greens (spinach, lettuce), cherry tomatoes, cucumber, grilled chicken breast, and olive oil-based vinaigrette. Good source of vitamin A, vitamin C, and iron. Low in saturated fat."

Remember: Your estimates help people make informed dietary choices. Strive for accuracy while acknowledging the inherent limitations of visual assessment."""


class NutritionAnalysis(BaseModel):
    """Structured nutrition analysis from food image"""
    calories: float = Field(description="Total estimated calories in kcal for the food shown in the image")
    sugar: float = Field(description="Total estimated sugar content in grams")
    protein: float = Field(description="Total estimated protein content in grams")
    others: str = Field(
        description="Additional nutritional information including fats, carbohydrates, fiber, vitamins, minerals, and any other relevant dietary notes")


class FoodAnalysisRequest(BaseModel):
    """Request model for food analysis"""
    image_data: str = Field(description="Base64 encoded image data")
    filename: Optional[str] = Field(default=None, description="Original filename")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "image_data": "base64_encoded_string_here...",
            "filename": "food_photo.jpg"
        }
    })


class FoodAnalysisResponse(BaseModel):
    """Response model for food analysis"""
    analysis_id: UUID = Field(default_factory=uuid4, description="Unique analysis ID")
    nutrition: NutritionAnalysis = Field(description="Nutrition analysis results")
    image_url: Optional[str] = Field(default=None, description="URL to stored image in Supabase")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Analysis timestamp")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "analysis_id": "123e4567-e89b-12d3-a456-426614174000",
            "nutrition": {
                "calories": 320.0,
                "sugar": 8.5,
                "protein": 28.0,
                "others": "Carbohydrates: 22g, Fat: 12g..."
            },
            "image_url": "https://xxx.supabase.co/storage/v1/object/public/images/...",
            "timestamp": "2025-10-13T00:00:00Z"
        }
    })