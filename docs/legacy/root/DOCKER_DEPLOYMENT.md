# MRRC Docker 部署指南

## 概述

本文档介绍如何使用 Docker 部署 MRRC 业余电台远程控制系统。Docker 部署提供以下优势：

- **环境一致性**：容器化确保开发、测试、生产环境一致
- **快速部署**：一键启动所有服务
- **易于维护**：服务隔离，升级方便
- **跨平台支持**：支持 Linux、macOS（有限支持）、Windows（WSL2）

## 系统要求

### 硬件要求
- CPU: 1核+
- 内存: 512MB+
- 存储: 1GB+
- USB 串口设备访问权限（电台连接）
- 音频设备访问权限（USB 声卡）

### 软件要求
- Docker 20.10+
- Docker Compose 2.0+
- Linux 内核 5.0+（推荐）

## 快速开始

### 1. 克隆代码仓库

```bash
git clone https://github.com/cheenle/UHRR_mac.git
cd UHRR_mac
```

### 2. 配置环境

复制配置文件模板：

```bash
cp MRRC.conf.example MRRC.conf
```

编辑 `MRRC.conf` 配置：

```ini
[SERVER]
port = 8877
certfile = /uhrh/certs/radio.vlsc.net.pem
keyfile = /uhrh/certs/radio.vlsc.net.key
auth = FILE
db_users_file = /uhrh/MRRC_users.db
debug = False

[AUDIO]
outputdevice = USB Audio CODEC
inputdevice = USB Audio CODEC

[HAMLIB]
rig_pathname = /dev/ttyUSB0
rig_model = 30003
rig_rate = 4800
stop_bits = 2
```

### 3. 准备证书（可选但推荐）

将 TLS 证书放入 `certs/` 目录：

```bash
mkdir -p certs
cp /path/to/your/cert.pem certs/radio.vlsc.net.pem
cp /path/to/your/key.key certs/radio.vlsc.net.key
```

### 4. 构建并启动

```bash
docker-compose up -d --build
```

### 5. 查看日志

```bash
docker-compose logs -f
```

### 6. 访问系统

浏览器访问：`https://your-server-ip:8877`

## 详细配置

### 单实例部署

默认 `docker-compose.yml` 配置单电台实例：

```yaml
version: '3.8'

services:
  mrrc:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: mrrc
    restart: unless-stopped
    privileged: true  # 需要特权模式访问 USB 设备
    volumes:
      - ./MRRC.conf:/uhrh/MRRC.conf:ro
      - ./certs:/uhrh/certs:ro
      - ./atr1000_tuner.json:/uhrh/atr1000_tuner.json
      - /dev:/dev
    ports:
      - "8877:8877"
    environment:
      - PYTHONUNBUFFERED=1
    devices:
      - /dev/snd:/dev/snd  # 音频设备
    networks:
      - mrrc-network

networks:
  mrrc-network:
    driver: bridge
```

### 多实例部署

使用 Docker Compose 部署多个电台实例：

```yaml
version: '3.8'

services:
  # 电台1实例
  mrrc-radio1:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: mrrc-radio1
    restart: unless-stopped
    privileged: true
    volumes:
      - ./MRRC.radio1.conf:/uhrh/MRRC.conf:ro
      - ./certs:/uhrh/certs:ro
      - ./atr1000_radio1.json:/uhrh/atr1000_tuner.json
      - /dev:/dev
    ports:
      - "8891:8891"
    environment:
      - INSTANCE_NAME=radio1
    networks:
      - mrrc-network

  # 电台2实例
  mrrc-radio2:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: mrrc-radio2
    restart: unless-stopped
    privileged: true
    volumes:
      - ./MRRC.radio2.conf:/uhrh/MRRC.conf:ro
      - ./certs:/uhrh/certs:ro
      - ./atr1000_radio2.json:/uhrh/atr1000_tuner.json
      - /dev:/dev
    ports:
      - "8892:8892"
    environment:
      - INSTANCE_NAME=radio2
    networks:
      - mrrc-network

networks:
  mrrc-network:
    driver: bridge
```

### ATR-1000 天调集成

ATR-1000 代理在容器内自动启动，无需额外配置。但需要确保：

1. 网络可以访问 ATR-1000 设备（默认 IP: 192.168.1.63）
2. 在配置文件中启用 ATR-1000：

```ini
[ATR1000]
enabled = True
device_ip = 192.168.1.63
device_port = 60001
```

### 反向代理配置（Nginx）

使用 Nginx 作为反向代理，统一入口：

```yaml
version: '3.8'

services:
  nginx:
    image: nginx:alpine
    container_name: mrrc-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certs:/etc/nginx/certs:ro
    networks:
      - mrrc-network
    depends_on:
      - mrrc-radio1
      - mrrc-radio2

  mrrc-radio1:
    # ... 配置同上

  mrrc-radio2:
    # ... 配置同上

networks:
  mrrc-network:
    driver: bridge
```

nginx.conf 示例：

```nginx
events {
    worker_connections 1024;
}

http {
    map $http_upgrade $connection_upgrade {
        default upgrade;
        '' close;
    }

    # 电台1 - radio.vlsc.net/radio1
    server {
        listen 443 ssl;
        server_name radio.vlsc.net;

        ssl_certificate /etc/nginx/certs/radio.vlsc.net.pem;
        ssl_certificate_key /etc/nginx/certs/radio.vlsc.net.key;

        location /radio1/ {
            proxy_pass https://mrrc-radio1:8891/;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection $connection_upgrade;
            proxy_set_header Host $host;
        }
    }

    # 电台2 - radio2.vlsc.net
    server {
        listen 443 ssl;
        server_name radio2.vlsc.net;

        ssl_certificate /etc/nginx/certs/radio2.vlsc.net.pem;
        ssl_certificate_key /etc/nginx/certs/radio2.vlsc.net.key;

        location / {
            proxy_pass https://mrrc-radio2:8892/;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection $connection_upgrade;
        }
    }
}
```

## 高级配置

### 自动启动 rigctld

创建启动脚本 `docker-entrypoint.sh`：

```bash
#!/bin/sh
set -e

# 启动 rigctld
rigctld -m ${RIG_MODEL:-30003} \
        -r ${RIG_DEVICE:-/dev/ttyUSB0} \
        -s ${RIG_SPEED:-4800} \
        -t ${RIG_PORT:-4531} \
        -C stop_bits=${RIG_STOP_BITS:-2} &

echo "Waiting for rigctld to start..."
sleep 2

# 启动 ATR-1000 代理（如果启用）
if [ "${ATR1000_ENABLED:-False}" = "True" ]; then
    python3 /uhrh/atr1000_proxy.py &
    echo "ATR-1000 proxy started"
fi

# 启动 MRRC
echo "Starting MRRC..."
exec python3 /uhrh/MRRC
```

修改 Dockerfile：

```dockerfile
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["docker-entrypoint.sh"]
```

### 持久化数据

使用 Docker volumes 持久化重要数据：

```yaml
volumes:
  mrrc-data:
    driver: local

services:
  mrrc:
    # ...
    volumes:
      - mrrc-data:/uhrh/data
      - ./MRRC.conf:/uhrh/MRRC.conf:ro
```

### 日志管理

配置日志轮转：

```yaml
services:
  mrrc:
    # ...
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

## 故障排查

### 1. USB 设备无法访问

**问题**：容器内无法访问电台串口设备

**解决方案**：
```bash
# 1. 检查设备权限
ls -l /dev/ttyUSB*

# 2. 添加用户到 dialout 组
sudo usermod -a -G dialout $USER

# 3. 使用特权模式（docker-compose.yml）
privileged: true

# 4. 或者使用设备映射
device_cgroup_rules:
  - 'c 188:* rmw'  # USB 串口设备
```

### 2. 音频设备问题

**问题**：音频设备在容器内无法识别

**解决方案**：
```bash
# 1. 检查宿主机音频设备
aplay -l
cat /proc/asound/cards

# 2. 安装 ALSA 工具
docker exec -it mrrc apk add alsa-utils

# 3. 映射音频设备
devices:
  - /dev/snd:/dev/snd
```

### 3. 网络连接问题

**问题**：无法访问 ATR-1000 设备

**解决方案**：
```bash
# 1. 检查网络连通性
docker exec -it mrrc ping 192.168.1.63

# 2. 使用 host 网络模式（仅 Linux）
network_mode: host

# 3. 或者配置容器网络
networks:
  mrrc-network:
    driver: bridge
    ipam:
      config:
        - subnet: 192.168.1.0/24
```

### 4. 权限问题

**问题**：容器内无法写入文件

**解决方案**：
```bash
# 1. 检查挂载目录权限
chown -R 1000:1000 ./certs
chown -R 1000:1000 ./atr1000_tuner.json

# 2. 在 Dockerfile 中设置用户
RUN adduser -D -u 1000 mrrc
USER mrrc
```

## 维护操作

### 更新镜像

```bash
# 拉取最新代码
git pull

# 重建镜像
docker-compose down
docker-compose up -d --build
```

### 备份数据

```bash
# 备份配置和数据
tar czvf mrrc-backup-$(date +%Y%m%d).tar.gz \
    MRRC*.conf \
    atr1000_tuner*.json \
    certs/ \
    MRRC_users.db
```

### 查看容器状态

```bash
# 容器状态
docker-compose ps

# 资源使用
docker stats mrrc

# 进入容器调试
docker exec -it mrrc sh
```

## 性能优化

### 1. 限制资源使用

```yaml
services:
  mrrc:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 512M
        reservations:
          cpus: '0.5'
          memory: 256M
```

### 2. 使用多阶段构建

优化 Dockerfile 减少镜像大小：

```dockerfile
# 构建阶段
FROM alpine:latest AS builder
# ... 编译依赖

# 运行阶段
FROM alpine:latest
COPY --from=builder /hamlib-prefix /usr/local
# ... 只复制必要的文件
```

### 3. 启用健康检查

```yaml
services:
  mrrc:
    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "https://localhost:8877/"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

## 安全建议

1. **使用非 root 用户运行容器**
2. **限制容器网络访问**
3. **使用 TLS 加密通信**
4. **定期更新基础镜像**
5. **启用 Docker 安全选项**

```yaml
services:
  mrrc:
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    cap_add:
      - SYS_ADMIN  # 需要用于音频设备
```

## 参考文档

- [MRRC 安装指南](INSTALLATION.md)
- [MRRC 多实例配置](docs/Multi_Instance_Setup.md)
- [Docker 官方文档](https://docs.docker.com/)
- [Docker Compose 文档](https://docs.docker.com/compose/)

## 贡献

欢迎提交 Issue 和 PR 改进 Docker 部署方案。

## 许可证

本项目遵循 GPL-3.0 许可证。