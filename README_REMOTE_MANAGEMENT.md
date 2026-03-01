# UHRR 远程管理指南

本文档介绍如何通过 SSH 远程管理和监控 UHRR 服务。

## 问题背景

在 macOS 下，通过 SSH 远程启动 UHRR 程序时，音频功能会完全失效，因为：
- SSH 会话无法访问 Core Audio 系统
- PyAudio 在无头环境中初始化失败
- 音频硬件无法被访问

## 解决方案

使用 launchd 服务在本地 GUI 会话中自动启动 UHRR，然后通过 SSH 进行远程管理。

## 快速开始

### 1. 首次安装

```bash
# 在本地 Terminal 中执行完整安装
./uhrr_setup.sh install
```

### 2. 快速安装（如果依赖已安装）

```bash
# 仅安装服务
./uhrr_setup.sh quick
```

### 3. 启动服务

```bash
# 启动服务
./uhrr_control.sh start

# 检查状态
./uhrr_control.sh status
```

## 远程管理命令

### 服务控制

```bash
# 检查服务状态
./uhrr_control.sh status

# 启动服务
./uhrr_control.sh start

# 停止服务
./uhrr_control.sh stop

# 重启服务
./uhrr_control.sh restart
```

### 监控和诊断

```bash
# 完整健康报告
./uhrr_monitor.sh status

# 实时监控
./uhrr_monitor.sh realtime

# 快速状态检查
./uhrr_monitor.sh basic

# 查看实时日志
./uhrr_control.sh logs
```

### 服务管理

```bash
# 启用开机自启动
./uhrr_control.sh enable

# 禁用开机自启动
./uhrr_control.sh disable

# 卸载服务
./uhrr_setup.sh uninstall
```

## 典型使用场景

### 场景 1：首次设置

```bash
# 1. 本地 Terminal 中安装
./uhrr_setup.sh install

# 2. 通过 SSH 远程检查
ssh user@host "cd /Users/cheenle/UHRR/UHRR_mac && ./uhrr_control.sh status"

# 3. 远程重启服务
ssh user@host "cd /Users/cheenle/UHRR/UHRR_mac && ./uhrr_control.sh restart"
```

### 场景 2：日常远程管理

```bash
# 检查服务状态
ssh user@host "cd /Users/cheenle/UHRR/UHRR_mac && ./uhrr_control.sh status"

# 查看实时日志
ssh user@host "cd /Users/cheenle/UHRR/UHRR_mac && ./uhrr_control.sh logs"

# 重启服务
ssh user@host "cd /Users/cheenle/UHRR/UHRR_mac && ./uhrr_control.sh restart"
```

### 场景 3：故障排查

```bash
# 完整健康检查
ssh user@host "cd /Users/cheenle/UHRR/UHRR_mac && ./uhrr_monitor.sh status"

# 检查错误日志
ssh user@host "cd /Users/cheenle/UHRR/UHRR_mac && ./uhrr_monitor.sh errors"

# 检查系统资源
ssh user@host "cd /Users/cheenle/UHRR/UHRR_mac && ./uhrr_monitor.sh system"
```

## 脚本说明

### uhrr_setup.sh
- **完整安装**: 检查依赖、安装 Python 包、配置服务
- **快速安装**: 仅安装服务（依赖已安装时使用）
- **卸载**: 完全移除服务

### uhrr_control.sh
- **服务控制**: 启动、停止、重启服务
- **状态检查**: 检查进程、端口、日志状态
- **日志管理**: 查看实时日志

### uhrr_monitor.sh
- **健康报告**: 完整的系统和服务状态报告
- **实时监控**: 实时显示服务状态
- **专项检查**: 网络、音频、错误等专项检查

## 文件位置

- **服务配置**: `~/Library/LaunchAgents/com.user.uhrr.plist`
- **服务日志**: `/Users/cheenle/UHRR/UHRR_mac/uhrr_service.log`
- **错误日志**: `/Users/cheenle/UHRR/UHRR_mac/uhrr_service_error.log`
- **调试日志**: `/Users/cheenle/UHRR/UHRR_mac/uhrr_debug.log`

## 故障排除

### 服务无法启动
```bash
# 检查依赖
./uhrr_setup.sh deps

# 查看错误日志
tail -f uhrr_service_error.log

# 重新安装服务
./uhrr_setup.sh uninstall
./uhrr_setup.sh quick
```

### 音频功能异常
- 确保服务在本地 GUI 会话中运行
- 检查音频设备配置
- 验证 PyAudio 安装

### Web 界面无法访问
```bash
# 检查端口
./uhrr_monitor.sh network

# 检查进程
./uhrr_control.sh status
```

## 注意事项

1. **必须在本地 GUI 会话中安装服务**，SSH 会话无法正确配置音频
2. **服务启动后**，可以通过 SSH 进行所有管理操作
3. **开机自启动**需要用户登录后才能生效
4. **SSL 证书**需要正确配置才能使用 HTTPS

## 高级用法

### 创建 SSH 别名
在 `~/.ssh/config` 中添加：
```
Host uhrr-host
    HostName your-server-ip
    User your-username
    IdentityFile ~/.ssh/your-key
```

然后使用：
```bash
ssh uhrr-host "cd /Users/cheenle/UHRR/UHRR_mac && ./uhrr_control.sh status"
```

### 定时监控
使用 crontab 定时检查服务状态：
```bash
# 每5分钟检查一次
*/5 * * * * cd /Users/cheenle/UHRR/UHRR_mac && ./uhrr_control.sh status > /dev/null 2>&1
```

这个远程管理系统确保了 UHRR 服务始终在正确的环境中运行，同时提供了完整的远程管理能力。