from app.providers import normalize_reasoning_summary, normalize_vision_foods


def test_normalizes_qwen_foods_missing_id_list_bbox_and_string_ingredients():
    foods = normalize_vision_foods(
        [
            {
                "name": "红色椭圆物体",
                "bbox": [97, 135, 415, 408],
                "confidence": 0.72,
                "ingredients_guess": "番茄, 火腿, 红椒",
                "cooking_method_guess": "未知",
                "portion_guess": "1份",
            }
        ]
    )

    assert foods[0].id == "food_1"
    assert foods[0].bbox.x == 97
    assert foods[0].bbox.y == 135
    assert foods[0].bbox.width == 318
    assert foods[0].bbox.height == 273
    assert foods[0].bbox.coordinate_space == "original"
    assert foods[0].ingredients_guess == ["番茄", "火腿", "红椒"]


def test_normalizes_nested_foods_key():
    foods = normalize_vision_foods(
        {
            "foods": [
                {
                    "name": "米饭",
                    "bbox": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4},
                    "confidence": 0.88,
                    "ingredients_guess": ["大米"],
                }
            ]
        }
    )

    assert foods[0].id == "food_1"
    assert foods[0].bbox.coordinate_space == "normalized"


def test_normalizes_deepseek_natural_analysis_shape():
    payload = {
        "foods": [
            {
                "id": "food_1",
                "name": "番茄炒蛋",
                "bbox": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4},
                "confidence": 0.88,
                "ingredients_guess": ["番茄", "鸡蛋"],
                "cooking_method_guess": "炒",
                "portion_guess": "中份",
            }
        ],
        "location_choice": {"kind": "home"},
    }
    raw = {
        "overall_analysis": "这是一顿家常菜。",
        "food_analyses": [
            {
                "food_id": "food_1",
                "nutrition_info": {"calories": "150-200千卡"},
                "risks": [{"description": "油脂可能偏高"}],
            }
        ],
        "health_recommendations": [{"description": "米饭减半。"}],
        "general_advice": "建议控制主食。仅供参考。",
    }

    normalized = normalize_reasoning_summary(raw, payload)

    assert normalized["foods"][0]["calories_range"] == "150-200千卡"
    assert normalized["foods"][0]["nutrition_risks"] == ["油脂可能偏高"]
    assert normalized["cuisine"]["primary_type"]
    assert normalized["total_calories_range"]
    assert normalized["total_cost_range"]
    assert normalized["health_advice"]["summary"] == "建议控制主食。仅供参考。"
    assert normalized["restaurant_summary"] is None
