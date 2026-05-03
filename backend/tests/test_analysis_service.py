from pathlib import Path

import pytest

from app.analysis_service import AnalysisService
from app.schemas import AnalysisRequest, LocationChoice, UserProfile


@pytest.mark.asyncio
async def test_analysis_returns_food_boxes_cuisine_cost_and_health_advice(tmp_path: Path):
    service = AnalysisService.mocked()
    request = AnalysisRequest(
        image_id="img_1",
        image_path=str(tmp_path / "food.jpg"),
        user_profile=UserProfile(conditions=["diabetes"], goals=["控糖"]),
        location_choice=LocationChoice(kind="home"),
    )

    result = await service.analyze(request)

    assert result.image_id == "img_1"
    assert result.total_calories_range.endswith("kcal")
    assert result.total_cost_range.endswith("元")
    assert result.cuisine.primary_type in {"家常菜", "火锅", "混合餐型"}
    assert result.foods
    assert result.foods[0].bbox.x >= 0
    assert "建议" in result.health_advice.summary
    assert result.restaurant_summary is None


@pytest.mark.asyncio
async def test_analysis_includes_restaurant_summary_when_restaurant_selected(tmp_path: Path):
    service = AnalysisService.mocked()
    request = AnalysisRequest(
        image_id="img_2",
        image_path=str(tmp_path / "food.jpg"),
        user_profile=UserProfile(conditions=[]),
        location_choice=LocationChoice(
            kind="restaurant",
            restaurant_name="老街家常菜",
            poi_id="poi_1",
        ),
    )

    result = await service.analyze(request)

    assert result.restaurant_summary is not None
    assert result.restaurant_summary.source_type == "poi_and_public_snippets"
    assert "无法通过照片确认" in result.restaurant_summary.disclaimer


@pytest.mark.asyncio
async def test_location_choices_without_restaurant_do_not_fabricate_review_summary(tmp_path: Path):
    service = AnalysisService.mocked()

    for kind in ["home", "canteen", "skip"]:
        result = await service.analyze(
            AnalysisRequest(
                image_id=f"img_{kind}",
                image_path=str(tmp_path / f"{kind}.jpg"),
                user_profile=UserProfile(),
                location_choice=LocationChoice(kind=kind),
            )
        )
        assert result.restaurant_summary is None
