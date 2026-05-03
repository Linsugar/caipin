# Food Analysis Backend

微信小程序 MVP 后端，包含图片上传、服务端本地图片存储、拍照饮食分析、附近餐饮 POI 查询、MySQL 记录和 Redis 连接检查。

## 启动

在项目根目录运行：

```powershell
docker compose up --build
```

启动后访问：

- API: `http://localhost:8000`
- OpenAPI: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

## 配置

编辑 `backend/config/app.yml`：

```yaml
providers:
  use_mock_models: true
  deepseek_api_key: ""
  qwen_api_key: ""
  amap_key: ""

security:
  client_keys:
    - dev-client-key
  rate_limit_per_minute: 30
  analysis_limit_per_day: 200

logging:
  print_request_response: true
  max_body_chars: 4000
```

默认 `use_mock_models: true`，没有 Key 也能跑通接口。真实接入时改成 `false`，再填 DeepSeek、千问百炼、高德 Key。

## 安全策略

除 `/health` 外，所有业务接口都需要请求头：

```text
X-Client-Key: dev-client-key
```

生产环境请把 `dev-client-key` 改成你自己的长随机字符串。后端会做：

- API Key 鉴权，未带 key 返回 `401`
- 错误 key 返回 `403`
- 分钟级限流，默认每个客户端每分钟 30 次
- 分析接口每日限流，默认每个客户端每天 200 次
- Redis 可用时用 Redis 计数，测试环境用内存计数

小程序前端只能调用你的后端；DeepSeek、千问、高德 Key 不要放到小程序里。

## 请求和模型日志

默认会打印：

- `HTTP_REQUEST`：接口请求方法、路径、请求头、请求体
- `HTTP_RESPONSE`：接口状态码、响应头、响应体
- `QWEN_REQUEST` / `QWEN_RESPONSE`：千问视觉请求和响应
- `DEEPSEEK_REQUEST` / `DEEPSEEK_RESPONSE`：DeepSeek 请求和响应

日志会自动脱敏：

- `Authorization`
- `api_key`
- `deepseek_api_key`
- `qwen_api_key`
- `X-Client-Key`
- 图片 base64 内容

如果日志太多，可以在 `backend/config/app.yml` 里关闭 HTTP 请求/响应日志：

```yaml
logging:
  print_request_response: false
  max_body_chars: 4000
```

查看容器日志：

```bash
docker logs -f --tail 200 food-analysis-api
```

## 图片存储

MVP 阶段图片存到你的服务器本地磁盘：

```text
backend/storage/uploads/YYYY/MM/DD/img_xxx.jpg
```

Docker 中挂载到：

```text
/app/storage/uploads
```

接口 `/api/v1/storage/cleanup` 会按 `storage.keep_days` 清理过期图片。

## 本地测试

```powershell
python -m pip install -r backend\requirements.txt
python -m pytest backend\tests -q
```
