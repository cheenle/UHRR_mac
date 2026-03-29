FROM alpine:latest
MAINTAINER MRRC Team

# 安装系统依赖
RUN apk add --no-cache \
    python3 \
    py3-pip \
    py3-tornado \
    py3-pyaudio \
    py3-numpy \
    py3-serial \
    py3-hamlib \
    py3-websocket-client \
    alsa-lib \
    alsa-utils \
    libusb \
    git \
    build-base \
    swig \
    linux-headers \
    && rm -rf /var/cache/apk/*

# 安装 Python 依赖
RUN pip3 install --no-cache-dir --break-system-packages \
    pyrtlsdr \
    tornado \
    pyaudio \
    numpy \
    pyserial

# 创建工作目录
RUN mkdir -p /uhrh/www /uhrh/certs
WORKDIR /uhrh

# 复制项目文件
COPY MRRC /uhrh/MRRC
COPY atr1000_proxy.py /uhrh/atr1000_proxy.py
COPY atr1000_tuner.py /uhrh/atr1000_tuner.py
COPY audio_interface.py /uhrh/audio_interface.py
COPY hamlib_wrapper.py /uhrh/hamlib_wrapper.py
COPY wdsp_wrapper.py /uhrh/wdsp_wrapper.py
COPY tci_client.py /uhrh/tci_client.py
COPY www/ /uhrh/www/

# 确保脚本可执行
RUN chmod +x /uhrh/MRRC

# 创建启动脚本
RUN cat > /uhrh/docker-entrypoint.sh << 'EOF'
#!/bin/sh
set -e

echo "================================"
echo "MRRC Docker Container Starting"
echo "================================"

# 检查配置文件
if [ ! -f /uhrh/MRRC.conf ]; then
    echo "ERROR: MRRC.conf not found!"
    echo "Please mount your configuration file."
    exit 1
fi

# 列出可用设备（用于调试）
echo "Available audio devices:"
aplay -l 2>/dev/null || echo "No ALSA devices found"

echo "Available serial devices:"
ls -la /dev/tty* 2>/dev/null || echo "No serial devices found"

# 启动 MRRC
echo ""
echo "Starting MRRC server..."
exec python3 /uhrh/MRRC
EOF

RUN chmod +x /uhrh/docker-entrypoint.sh

# 暴露端口
EXPOSE 8877

# 设置入口点
ENTRYPOINT ["/uhrh/docker-entrypoint.sh"]