# Docker 镜像源说明

如果构建时报错：

```text
failed to fetch oauth token
connectex: A connection attempt failed
```

通常是当前机器访问 Docker Hub 超时。可以用下面两种方式处理。

## 方式一：构建时临时指定 Python 镜像源

在 `backend` 目录执行：

```powershell
docker build `
  --build-arg PYTHON_IMAGE=docker.m.daocloud.io/library/python:3.13-slim `
  -t food-analysis-api:latest .
```

也可以尝试：

```powershell
docker build `
  --build-arg PYTHON_IMAGE=docker.1ms.run/library/python:3.13-slim `
  -t food-analysis-api:latest .
```

构建成功后再启动：

```powershell
docker compose -f docker-compose.yaml up -d
```

## 方式二：配置 Docker Desktop 镜像加速

打开 Docker Desktop：

```text
Settings
  -> Docker Engine
```

把配置改成类似：

```json
{
  "registry-mirrors": [
    "https://docker.m.daocloud.io",
    "https://docker.1ms.run"
  ]
}
```

然后点击 `Apply & Restart`。

如果你有阿里云个人镜像加速地址，优先使用阿里云给你的专属地址。

## 推荐构建命令

```powershell
cd E:\Godot_v4.5-stable_win64.exe\Projects\ui\backend

docker build `
  --build-arg PYTHON_IMAGE=docker.m.daocloud.io/library/python:3.13-slim `
  -t food-analysis-api:latest .

docker compose -f docker-compose.yaml up -d
```
