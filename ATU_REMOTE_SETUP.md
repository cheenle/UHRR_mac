# ATU远程连接配置指南

## 问题描述
ATU服务器默认连接到 `192.168.1.12:60001`，但这个IP地址在远程网络中可能无法访问。

## 解决方案

### 方法1：通过环境变量配置

在启动ATU服务器之前，设置环境变量：

```bash
# 设置ATU设备的实际IP地址和端口
export ATU_DEVICE_IP="实际ATU设备的IP地址"
export ATU_DEVICE_PORT="实际ATU设备的端口"
export ATU_SERVER_PORT="8889"  # 可选，默认8889

# 启动ATU服务器
./ATU_SERVER
```

### 方法2：修改ATU_SERVER文件

直接编辑 `ATU_SERVER` 文件中的默认值：

```python
# 全局变量
# 从环境变量或默认值获取ATU设备配置
ATU_DEVICE_IP = os.environ.get('ATU_DEVICE_IP', '实际ATU设备的IP地址')
ATU_DEVICE_PORT = int(os.environ.get('ATU_DEVICE_PORT', '60001'))
ATU_SERVER_PORT = int(os.environ.get('ATU_SERVER_PORT', '8889'))
```

### 方法3：使用启动脚本

创建一个启动脚本 `start_atu_server.sh`：

```bash
#!/bin/bash

# 设置ATU设备连接参数
export ATU_DEVICE_IP="实际ATU设备的IP地址"
export ATU_DEVICE_PORT="60001"

# 启动ATU服务器
./ATU_SERVER
```

然后运行：
```bash
chmod +x start_atu_server.sh
./start_atu_server.sh
```

## 获取ATU设备IP地址的方法

1. **在ATU设备所在的局域网内**：
   - 登录路由器管理界面查看已连接设备
   - 使用网络扫描工具（如 `nmap`）扫描网络
   - 查看ATU设备的网络设置

2. **通过VPN连接**：
   - 如果ATU设备在VPN网络中，使用VPN分配的IP地址

3. **端口转发**：
   - 如果ATU设备在NAT后面，需要在路由器上设置端口转发

## 验证连接

启动ATU服务器后，检查日志确认连接状态：

```bash
tail -f atu_server_debug.log
```

应该看到类似这样的输出：
```
ATU设备配置: 实际IP地址:60001
✓ ATU设备连接成功
```

## 注意事项

- 确保ATU设备的防火墙允许来自ATU服务器的连接
- 如果使用VPN，确保VPN连接稳定
- 如果连接失败，检查网络连通性：
  ```bash
  telnet ATU设备IP 60001
  ```