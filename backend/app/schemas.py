from typing import Literal

from pydantic import BaseModel, Field


LocationKind = Literal["restaurant", "home", "takeaway", "canteen", "manual", "skip"]


class BoundingBox(BaseModel):
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    coordinate_space: Literal["normalized", "original"] = "normalized"


class UserProfile(BaseModel):
    conditions: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    avoid_foods: list[str] = Field(default_factory=list)
    note: str = ""


class LocationChoice(BaseModel):
    kind: LocationKind = "skip"
    poi_id: str | None = None
    restaurant_name: str | None = None
    city: str | None = None
    address: str | None = None
    platform: str | None = None


class FoodItem(BaseModel):
    id: str
    name: str
    bbox: BoundingBox
    confidence: float = Field(ge=0, le=1)
    ingredients_guess: list[str] = Field(default_factory=list)
    cooking_method_guess: str = ""
    portion_guess: str = ""
    calories_range: str = ""
    cost_range: str = ""
    nutrition_risks: list[str] = Field(default_factory=list)


class CuisineAnalysis(BaseModel):
    primary_type: str
    secondary_type: str | None = None
    confidence: float = Field(ge=0, le=1)
    evidence: list[str] = Field(default_factory=list)


class HealthAdvice(BaseModel):
    summary: str
    suggestions: list[str] = Field(default_factory=list)
    disclaimer: str = "仅作为饮食参考，不替代医生或营养师建议。"


class RestaurantSummary(BaseModel):
    source_type: str
    positive: list[str] = Field(default_factory=list)
    negative: list[str] = Field(default_factory=list)
    hygiene_risk: str = ""
    disclaimer: str = "仅基于公开摘要和地图信息，无法通过照片确认食品安全。"


class AnalysisRequest(BaseModel):
    image_id: str
    user_profile: UserProfile = Field(default_factory=UserProfile)
    location_choice: LocationChoice = Field(default_factory=LocationChoice)


class AnalysisResult(BaseModel):
    image_id: str
    foods: list[FoodItem]
    cuisine: CuisineAnalysis
    total_calories_range: str
    total_cost_range: str
    cost_confidence: float = Field(ge=0, le=1)
    health_advice: HealthAdvice
    restaurant_summary: RestaurantSummary | None = None
    uncertainty_notes: list[str] = Field(default_factory=list)


class ImageUploadResponse(BaseModel):
    image_id: str
    relative_path: str
    content_type: str
    size_bytes: int


class NearbyPoiRequest(BaseModel):
    latitude: float
    longitude: float
    radius_m: int = 500


class PoiCandidate(BaseModel):
    id: str
    name: str
    address: str = ""
    distance_m: int | None = None
    rating: str | None = None
    cost: str | None = None
    tags: list[str] = Field(default_factory=list)
