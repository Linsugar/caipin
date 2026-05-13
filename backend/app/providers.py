import json
from pathlib import Path
from typing import Any

import httpx

from app.config import ProviderConfig
from app.logging_utils import log_json
from app.schemas import BoundingBox, FoodItem


class ProviderError(RuntimeError):
    pass


class ProviderTimeoutError(ProviderError):
    pass


class ProviderHTTPError(ProviderError):
    pass


def _parse_json_content(content: object) -> Any:
    if isinstance(content, dict):
        return content
    if not isinstance(content, str):
        raise ValueError("model response content is not JSON")
    # 清理 markdown 代码块包裹
    text = content.strip()
    if text.startswith("```"):
        text = text.removeprefix("```json").removeprefix("```").strip()
        if text.endswith("```"):
            text = text[:-3].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 尝试提取第一个 JSON 对象
        import re as _re
        m = _re.search(r'\{.*\}', text, _re.DOTALL)
        if m:
            return json.loads(m.group())
        raise


def _split_guess(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.replace("，", ",").split(",") if item.strip()]
    return []


def _normalize_bbox(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return {
            "x": value.get("x", value.get("left", 0)),
            "y": value.get("y", value.get("top", 0)),
            "width": value.get("width", value.get("w", 1)),
            "height": value.get("height", value.get("h", 1)),
            "coordinate_space": value.get("coordinate_space", "normalized"),
        }
    if isinstance(value, list) and len(value) == 4:
        x1, y1, x2, y2 = [float(item) for item in value]
        width = x2 - x1 if x2 > x1 else x2
        height = y2 - y1 if y2 > y1 else y2
        return {
            "x": x1,
            "y": y1,
            "width": max(width, 1),
            "height": max(height, 1),
            "coordinate_space": "original",
        }
    return {"x": 0, "y": 0, "width": 1, "height": 1, "coordinate_space": "normalized"}


def normalize_vision_foods(raw: object) -> list[FoodItem]:
    all_items: list[dict] = []

    def _collect(obj: object, category: str = "") -> None:
        if isinstance(obj, list):
            for elem in obj:
                _collect(elem, category)
        elif isinstance(obj, dict):
            if "name" in obj:
                all_items.append({"category": category, **obj})
            for key, value in obj.items():
                if isinstance(value, (list, dict)):
                    _collect(value, key.rstrip("s") if isinstance(value, list) else category)

    _collect(raw)
    if not all_items:
        return []

    if not all_items:
        return []

    normalized: list[FoodItem] = []
    for index, item in enumerate(all_items, start=1):
        normalized.append(
            FoodItem.model_validate(
                {
                    "id": item.get("id") or f"food_{index}",
                    "name": item.get("name") or item.get("food_name") or "未知菜品",
                    "bbox": _normalize_bbox(item.get("bbox") or item.get("box")),
                    "confidence": float(item.get("confidence", 0.5)),
                    "ingredients_guess": _split_guess(item.get("ingredients_guess", [])),
                    "cooking_method_guess": item.get("cooking_method_guess") or item.get("cooking_method") or "",
                    "portion_guess": item.get("portion_guess") or item.get("portion") or "",
                }
            )
        )
    return normalized


def _risk_to_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return str(value.get("description") or value.get("risk") or value.get("type") or "").strip()
    return ""


def _guess_cuisine(food_names: list[str]) -> dict[str, object]:
    joined = "、".join(food_names)
    if any(word in joined for word in ["火锅", "锅底", "肥牛"]):
        return {"primary_type": "火锅", "secondary_type": None, "confidence": 0.65, "evidence": ["菜名或画面线索包含火锅相关内容"]}
    if any(word in joined for word in ["干锅"]):
        return {"primary_type": "干锅", "secondary_type": None, "confidence": 0.65, "evidence": ["菜名包含干锅相关内容"]}
    return {"primary_type": "家常菜", "secondary_type": "中式家常", "confidence": 0.55, "evidence": ["根据菜品组合做保守归类"]}


def normalize_reasoning_summary(raw: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    # Build lookup from DeepSeek's foods array (keyed by id or index)
    reasoning_foods = raw.get("foods") or raw.get("food_analyses") or []
    reasoning_by_id: dict[str, dict] = {}
    for i, item in enumerate(reasoning_foods):
        if isinstance(item, dict):
            key = item.get("id") or f"food_{i + 1}"
            reasoning_by_id[key] = item

    foods: list[dict[str, Any]] = []
    calories_parts: list[str] = []
    for food in payload.get("foods", []):
        fid = food.get("id", "")
        analysis = reasoning_by_id.get(fid, {})
        nutrition = analysis.get("nutrition_info", {}) if isinstance(analysis, dict) else {}
        calories = (
            nutrition.get("calories")
            or analysis.get("calories")
            or analysis.get("calories_range")
            or food.get("calories_range")
            or "热量不确定"
        )
        cost = (
            nutrition.get("cost")
            or analysis.get("cost")
            or analysis.get("cost_range")
            or food.get("cost_range")
            or "成本不确定"
        )
        calories_parts.append(str(calories))
        risks = [_risk_to_text(risk) for risk in (analysis.get("nutrition_risks") or analysis.get("risks") or [])] if isinstance(analysis, dict) else []
        foods.append(
            {
                **food,
                "calories_range": str(calories),
                "cost_range": str(cost),
                "nutrition_risks": [risk for risk in risks if risk],
            }
        )

    food_names = [str(food.get("name", "")) for food in foods]
    health_recommendations = raw.get("health_recommendations", [])
    suggestions = [
        str(item.get("description") or item.get("suggestion") or item)
        for item in health_recommendations
        if item
    ]
    location_kind = payload.get("location_choice", {}).get("kind", "skip")
    restaurant_summary = raw.get("restaurant_summary")
    if location_kind not in {"restaurant", "manual", "takeaway"}:
        restaurant_summary = None

    return {
        "foods": foods,
        "cuisine": raw.get("cuisine") or _guess_cuisine(food_names),
        "total_calories_range": raw.get("total_calories_range") or " + ".join(calories_parts) or "热量不确定",
        "total_cost_range": raw.get("total_cost_range") or "成本不确定",
        "cost_confidence": float(raw.get("cost_confidence", 0.35)),
        "health_advice": raw.get("health_advice")
        or {
            "summary": raw.get("general_advice") or raw.get("overall_analysis") or "建议结合个人健康情况适量食用。",
            "suggestions": suggestions,
            "disclaimer": "仅作为饮食参考，不替代医生或营养师建议。",
        },
        "restaurant_summary": restaurant_summary,
        "uncertainty_notes": raw.get("uncertainty_notes") or ["模型输出已归一化，热量和成本为估算值"],
    }


class VisionProvider:
    async def detect_foods(self, image_path: str) -> list[FoodItem]:
        raise NotImplementedError


class ReasoningProvider:
    async def summarize_analysis(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class MockVisionProvider(VisionProvider):
    async def detect_foods(self, image_path: str) -> list[FoodItem]:
        return [
            FoodItem(
                id="food_1",
                name="番茄炒蛋",
                bbox=BoundingBox(x=0.12, y=0.18, width=0.36, height=0.28),
                confidence=0.86,
                ingredients_guess=["鸡蛋", "番茄", "食用油"],
                cooking_method_guess="炒",
                portion_guess="中份",
            ),
            FoodItem(
                id="food_2",
                name="米饭",
                bbox=BoundingBox(x=0.56, y=0.22, width=0.24, height=0.22),
                confidence=0.9,
                ingredients_guess=["大米"],
                cooking_method_guess="蒸",
                portion_guess="一碗",
            ),
        ]


class MockReasoningProvider(ReasoningProvider):
    async def summarize_analysis(self, payload: dict[str, Any]) -> dict[str, Any]:
        location_kind = payload.get("location_choice", {}).get("kind", "skip")
        restaurant_selected = location_kind in {"restaurant", "manual", "takeaway"}
        has_diabetes = "diabetes" in payload.get("user_profile", {}).get("conditions", [])
        return {
            "foods": [
                {
                    **food,
                    "calories_range": "220-320 kcal" if food["name"] != "米饭" else "180-260 kcal",
                    "cost_range": "5-9 元" if food["name"] != "米饭" else "1-3 元",
                    "nutrition_risks": ["油脂可能偏高"] if food["name"] != "米饭" else ["碳水偏高"],
                }
                for food in payload["foods"]
            ],
            "cuisine": {
                "primary_type": "家常菜",
                "secondary_type": "中式家常",
                "confidence": 0.78,
                "evidence": ["识别到番茄炒蛋和米饭", "烹饪方式以炒、蒸为主"],
            },
            "total_calories_range": "400-580 kcal",
            "total_cost_range": "6-12 元",
            "cost_confidence": 0.68,
            "health_advice": {
                "summary": "建议按估算结果控制主食和油脂摄入。",
                "suggestions": ["米饭可减量三分之一"] if has_diabetes else ["注意蔬菜搭配"],
            },
            "restaurant_summary": {
                "source_type": "poi_and_public_snippets",
                "positive": ["口味评价以家常、下饭为主"],
                "negative": ["未发现集中负面线索"],
                "hygiene_risk": "未发现集中卫生负面线索",
            }
            if restaurant_selected
            else None,
            "uncertainty_notes": ["份量由图片估算，成本仅供参考"],
        }


class QwenVisionProvider(VisionProvider):
    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

    async def detect_foods(self, image_path: str) -> list[FoodItem]:
        if not self.config.qwen_api_key:
            return await MockVisionProvider().detect_foods(image_path)

        image_bytes = Path(image_path).read_bytes()
        # MVP 先保留真实接入位置；不同百炼视觉模型的图片格式细节可按开通模型再微调。
        try:
            request_payload = {
                "model": self.config.qwen_vision_model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": (
    "识别图片中所有可见的物品，按类别分组返回 JSON。类别可包括 foods（菜品）、fruits（水果）、drinks（饮品）等。"
    "每个物品返回 name、bbox（[x1,y1,x2,y2] 像素坐标）、confidence、ingredients_guess、cooking_method_guess、portion_guess。"
    "示例：{\"foods\":[{\"name\":\"红烧肉\",\"bbox\":[292,224,574,450],\"confidence\":0.9,\"ingredients_guess\":[\"猪肉\"],\"cooking_method_guess\":\"炖\",\"portion_guess\":\"中份\"}],\"fruits\":[{\"name\":\"苹果\",\"bbox\":[100,50,200,150],\"confidence\":0.85,\"ingredients_guess\":[\"苹果\"],\"cooking_method_guess\":\"生食\",\"portion_guess\":\"一个\"}]}"
)},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": "data:image/jpeg;base64,"
                                    + __import__("base64").b64encode(image_bytes).decode("ascii")
                                },
                            },
                        ],
                    }
                ],
                "response_format": {"type": "json_object"},
            }
            log_json("QWEN_REQUEST", request_payload)
            async with httpx.AsyncClient(timeout=self.config.request_timeout_seconds, trust_env=False) as client:
                response = await client.post(
                    f"{self.config.qwen_base_url.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {self.config.qwen_api_key}"},
                    json=request_payload,
                )
                response.raise_for_status()
                log_json("QWEN_RESPONSE", {"status_code": response.status_code, "body": response.text})
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError("qwen vision request timed out") from exc
        except httpx.HTTPStatusError as exc:
            raise ProviderHTTPError(f"qwen vision request failed: {exc.response.text[:500]}") from exc
        content = response.json()["choices"][0]["message"]["content"]
        try:
            parsed = _parse_json_content(content)
        except (json.JSONDecodeError, ValueError) as exc:
            log_json("QWEN_PARSE_ERROR", {"error": str(exc), "content": content[:500]})
            return await MockVisionProvider().detect_foods(image_path)
        foods = normalize_vision_foods(parsed)
        if not foods:
            return await MockVisionProvider().detect_foods(image_path)
        return foods


class DeepSeekReasoningProvider(ReasoningProvider):
    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

    async def summarize_analysis(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.config.deepseek_api_key:
            return await MockReasoningProvider().summarize_analysis(payload)

        import json as _json

        system_prompt = (
            "你是饮食分析后端。输入是图片中识别到的菜品列表（含菜名、坐标、置信度、食材、做法、份量）。"
            "请为每道菜估算热量和成本，并输出以下 JSON 格式：\n"
            '{"foods":[{"id":"food_1","name":"番茄炒蛋","calories_range":"220-320 kcal","cost_range":"5-9 元","nutrition_risks":["油脂偏高"]}],'
            '"cuisine":{"primary_type":"家常菜","secondary_type":null,"confidence":0.8,"evidence":["根据菜品判断"]},'
            '"total_calories_range":"400-580 kcal","total_cost_range":"6-12 元","cost_confidence":0.7,'
            '"health_advice":{"summary":"整体建议","suggestions":["建议1"]},'
            '"uncertainty_notes":["热量和成本为估算值"]}\n'
            "只输出 JSON，不要任何额外文字。"
        )

        try:
            request_payload = {
                "model": self.config.deepseek_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": _json.dumps(payload, ensure_ascii=False)},
                ],
                "response_format": {"type": "json_object"},
            }
            log_json("DEEPSEEK_REQUEST", request_payload)
            async with httpx.AsyncClient(timeout=self.config.request_timeout_seconds, trust_env=False) as client:
                response = await client.post(
                    f"{self.config.deepseek_base_url.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {self.config.deepseek_api_key}"},
                    json=request_payload,
                )
                response.raise_for_status()
                log_json("DEEPSEEK_RESPONSE", {"status_code": response.status_code, "body": response.text})
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError("deepseek reasoning request timed out") from exc
        except httpx.HTTPStatusError as exc:
            raise ProviderHTTPError(f"deepseek reasoning request failed: {exc.response.text[:500]}") from exc
        content = response.json()["choices"][0]["message"]["content"]
        try:
            parsed = _parse_json_content(content)
            return normalize_reasoning_summary(parsed, payload)
        except (json.JSONDecodeError, ValueError) as exc:
            log_json("DEEPSEEK_PARSE_ERROR", {"error": str(exc), "content": content[:500]})
            return await MockReasoningProvider().summarize_analysis(payload)
