from app.config import ProviderConfig
from app.providers import (
    DeepSeekReasoningProvider,
    MockReasoningProvider,
    MockVisionProvider,
    QwenVisionProvider,
    ReasoningProvider,
    VisionProvider,
)
from app.schemas import AnalysisRequest, AnalysisResult


class AnalysisService:
    def __init__(self, vision: VisionProvider, reasoning: ReasoningProvider) -> None:
        self.vision = vision
        self.reasoning = reasoning

    @classmethod
    def from_config(cls, config: ProviderConfig) -> "AnalysisService":
        if config.use_mock_models:
            return cls(MockVisionProvider(), MockReasoningProvider())
        return cls(QwenVisionProvider(config), DeepSeekReasoningProvider(config))

    @classmethod
    def mocked(cls) -> "AnalysisService":
        return cls(MockVisionProvider(), MockReasoningProvider())

    async def analyze(self, request: AnalysisRequest, image_path: str) -> AnalysisResult:
        foods = await self.vision.detect_foods(image_path)
        reasoning_payload = {
            "image_id": request.image_id,
            "foods": [food.model_dump() for food in foods],
            "user_profile": request.user_profile.model_dump(),
            "location_choice": request.location_choice.model_dump(),
        }
        summary = await self.reasoning.summarize_analysis(reasoning_payload)
        return AnalysisResult.model_validate({"image_id": request.image_id, **summary})
