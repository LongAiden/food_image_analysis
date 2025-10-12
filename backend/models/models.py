from pydantic import BaseModel, Field

# Pydantic Model for Structured Output


class NutritionAnalysis(BaseModel):
    """Structured nutrition analysis from food image"""
    calories: float = Field(description="Total estimated calories in kcal for the food shown in the image")
    sugar: float = Field(description="Total estimated sugar content in grams")
    protein: float = Field(description="Total estimated protein content in grams")
    others: str = Field(
        description="Additional nutritional information including fats, carbohydrates, fiber, vitamins, minerals, and any other relevant dietary notes")