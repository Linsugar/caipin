# Docker Compose 部署说明

## 镜像构建

进入后端目录：

```bash
cd /data/CaiPin
```

在服务器或构建机上先构建后端镜像：

```bash
docker build -t food-analysis-api:latest .
```

然后用后端目录的 `docker-compose.yaml` 启动：

```bash
docker compose -f docker-compose.yaml up -d
```

## 容器

| 服务 | 镜像 | 容器名 | 端口 |
|---|---|---|---|
| 后端 API | `food-analysis-api:latest` | `food-analysis-api` | `8000:8000` |
| MySQL | `mysql:8.4` | `food-analysis-mysql` | `3306:3306` |
| Redis | `redis:7-alpine` | `food-analysis-redis` | `6379:6379` |

## 数据挂载

| 容器 | 容器路径 | 宿主机/卷 |
|---|---|---|
| API | `/app/config/app.yml` | `./config/app.yml` |
| API | `/app/storage` | `./storage` |
| MySQL | `/var/lib/mysql` | `mysql_data` |
| Redis | `/data` | `redis_data` |

图片会保存在服务器本地：

```text
./storage/uploads/YYYY/MM/DD/img_xxx.jpg
```

## 配置

后端配置在：

```text
backend/config/app.yml
```

上线前至少修改：

```yaml
providers:
  use_mock_models: false
  deepseek_api_key: "你的 DeepSeek Key"
  qwen_api_key: "你的千问百炼 Key"
  amap_key: "你的高德 Key"

security:
  client_keys:
    - "换成你自己的长随机字符串"
  rate_limit_per_minute: 30
  analysis_limit_per_day: 200
```

小程序请求后端时带：

```text
X-Client-Key: 你的长随机字符串
```

DeepSeek、千问、高德 Key 不要放到小程序前端。

## 常用命令

启动：

```bash
docker compose -f docker-compose.yaml up -d
```

查看状态：

```bash
docker compose -f docker-compose.yaml ps
```

查看日志：

```bash
docker compose -f docker-compose.yaml logs -f api
```

停止：

```bash
docker compose -f docker-compose.yaml down
```
