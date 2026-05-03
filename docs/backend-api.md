# 拍照饮食分析后端 API 说明

## 基础信息

- Base URL: `http://localhost:8000`
- 当前 MVP 默认使用 mock 模型，填入 Key 后可切换真实千问、DeepSeek 和高德。
- 图片存储在服务端本地磁盘，不存储在用户手机本地。

## 鉴权与限流

除 `/health` 外，业务接口都需要带客户端 Key：

```text
X-Client-Key: dev-client-key
```

生产环境在 `backend/config/app.yml` 里修改：

```yaml
security:
  client_keys:
    - your-long-random-client-key
  rate_limit_per_minute: 30
  analysis_limit_per_day: 200
```

错误响应：

```json
{"detail": "missing api key"}
```

```json
{"detail": "invalid api key"}
```

```json
{"detail": "rate limit exceeded"}
```

```json
{"detail": "daily analysis limit exceeded"}
```

## GET /health

检查服务状态。

响应示例：

```json
{
  "status": "ok",
  "dependencies": {
    "mysql": "ok",
    "redis": "ok"
  }
}
```

## POST /api/v1/images

上传饭菜图片。

请求：

```bash
curl -X POST http://localhost:8000/api/v1/images \
  -H "X-Client-Key: dev-client-key" \
  -F "file=@food.jpg;type=image/jpeg"
```

响应：

```json
{
  "image_id": "img_xxx",
  "relative_path": "2026/05/03/img_xxx.jpg",
  "content_type": "image/jpeg",
  "size_bytes": 12345
}
```

限制：

- 支持 `image/jpeg`、`image/png`、`image/webp`
- 默认最大 10MB
- 文件名由后端随机生成，不使用用户原始文件名

## POST /api/v1/analyses

分析图片中的菜品、热量、成本、菜系/餐型和健康建议。

请求头：

```text
X-Client-Key: dev-client-key
```

请求示例：

```json
{
  "image_id": "img_xxx",
  "image_path": "storage/uploads/2026/05/03/img_xxx.jpg",
  "user_profile": {
    "conditions": ["diabetes"],
    "goals": ["控糖"],
    "avoid_foods": [],
    "note": ""
  },
  "location_choice": {
    "kind": "home"
  }
}
```

响应核心字段：

```json
{
  "image_id": "img_xxx",
  "foods": [
    {
      "id": "food_1",
      "name": "番茄炒蛋",
      "bbox": {
        "x": 0.12,
        "y": 0.18,
        "width": 0.36,
        "height": 0.28,
        "coordinate_space": "normalized"
      },
      "confidence": 0.86,
      "calories_range": "220-320 kcal",
      "cost_range": "5-9 元"
    }
  ],
  "cuisine": {
    "primary_type": "家常菜",
    "secondary_type": "中式家常",
    "confidence": 0.78,
    "evidence": ["识别到番茄炒蛋和米饭"]
  },
  "total_calories_range": "400-580 kcal",
  "total_cost_range": "6-12 元",
  "health_advice": {
    "summary": "建议按估算结果控制主食和油脂摄入。",
    "disclaimer": "仅作为饮食参考，不替代医生或营养师建议。"
  },
  "restaurant_summary": null
}
```

坐标说明：

- `bbox` 默认是归一化坐标。
- 前端需要基于图片当前缩放和平移状态同步映射坐标框、标签和点击热区。

## POST /api/v1/locations/nearby

查询附近 3-5 家餐饮 POI。

请求头：

```text
X-Client-Key: dev-client-key
```

请求：

```json
{
  "latitude": 31.2304,
  "longitude": 121.4737,
  "radius_m": 500
}
```

响应：

```json
[
  {
    "id": "mock_poi_1",
    "name": "附近家常菜馆",
    "address": "模拟地址 1",
    "distance_m": 80,
    "rating": "4.3",
    "cost": "45",
    "tags": ["家常菜"]
  }
]
```

没有高德 Key 时返回 mock 数据；配置 `providers.amap_key` 后调用高德周边搜索。

## POST /api/v1/storage/cleanup

按配置清理过期图片。

请求头：

```text
X-Client-Key: dev-client-key
```

响应：

```json
{
  "removed": 3,
  "keep_days": 7
}
```
