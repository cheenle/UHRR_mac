# ATU集成使用指南

## 概述

UHRR系统已成功集成了ATU（自动天线调谐器）实时监控功能，可以在Web界面上显示实时的功率和驻波比信息。

## 功能特性

- ✅ **实时功率显示**: 显示ATU输出的实际功率（W）
- ✅ **实时驻波比显示**: 显示天线系统的驻波比（SWR）
- ✅ **连接状态指示**: 可视化显示ATU连接状态
- ✅ **自动更新**: 每秒更新一次数据
- ✅ **错误处理**: 自动处理连接失败和数据异常

## 配置步骤

### 1. 配置文件设置

在 `UHRR.conf` 中添加ATU配置：

```ini
[ATU]
host = 192.168.1.12
port = 80
enabled = True
update_interval = 1.0
```

### 2. 启动系统

启动UHRR主程序：

```bash
python UHRR
```

系统会自动：
- 连接到ATU设备（192.168.1.12:80）
- 启动后台监控线程
- 通过WebSocket广播数据到前端

## Web界面使用

### 显示位置

ATU数据显示位于主界面的右侧面板：

- **功率仪表**: 显示当前输出功率（0-100W）
- **驻波比仪表**: 显示当前驻波比（1.0-3.0）
- **状态指示器**: 显示ATU连接状态
  - 🟢 绿色: 已连接并接收数据
  - 🔴 红色: 未连接或连接失败
  - 🟡 黄色: 数据异常

### 数据更新频率

- 每秒更新一次实时数据
- 发射（PTT）时优先显示最新数据
- 接收时显示平均功率和驻波比

## ATU设备要求

### 支持的API格式

ATU设备需要提供HTTP API，支持以下响应格式之一：

1. **标准格式**:
```json
{
  "power": 45.5,
  "swr": 1.23
}
```

2. **扩展格式**:
```json
{
  "forward_power": 45.5,
  "swr": 1.23
}
```

3. **数组格式**:
```json
[
  {
    "watt": 45.5,
    "standing_wave_ratio": 1.23
  }
]
```

## 测试和调试

### 使用模拟服务器测试

如果没有实际ATU设备，可以使用提供的模拟服务器：

```bash
python atu_mock_server.py
```

模拟服务器将运行在 `http://localhost:80`，提供随机的功率和驻波比数据。

### 运行集成测试

```bash
python test_atu_integration.py
```

测试脚本会验证：
- ATU客户端连接功能
- 数据获取和解析
- Web界面组件集成

### 日志监控

查看 `uhrr_debug.log` 文件，监控ATU相关日志：

```
INFO - ATU client initialized successfully
INFO - ATU monitoring started successfully
DEBUG - ATU Data: Power=45.5W, SWR=1.23
ERROR - Failed to connect to ATU: Connection refused
```

## 故障排除

### 连接问题

1. **检查网络连接**:
   - 确认ATU设备IP地址正确
   - 检查防火墙设置
   - 验证端口可访问性

2. **测试API可用性**:
   ```bash
   curl http://192.168.1.12:80/status
   ```

3. **查看日志**:
   ```bash
   tail -f uhrr_debug.log | grep ATU
   ```

### 数据显示问题

1. **检查WebSocket连接**:
   - 确认WebSocket连接正常
   - 检查浏览器控制台错误

2. **验证数据格式**:
   - 确认ATU API返回正确的JSON格式
   - 检查数据字段名称是否匹配

### 性能问题

如果ATU监控影响系统性能：

1. **调整更新频率**:
   ```ini
   [ATU]
   update_interval = 2.0  # 降低到每2秒更新一次
   ```

2. **禁用监控**:
   ```ini
   [ATU]
   enabled = False
   ```

## 技术细节

### 架构设计

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   ATU设备       │    │   UHRR后端       │    │   Web前端       │
│  192.168.1.12   │◄──►│  atu_client.py   │◄──►│  controls.js    │
│                 │    │                  │    │                 │
│ HTTP API        │    │ WebSocket广播    │    │ 实时显示        │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### 数据流

1. **后端轮询**: ATU客户端每秒查询一次ATU状态
2. **数据缓存**: 在内存中缓存最新数据
3. **实时广播**: 通过WebSocket将数据广播给所有连接的客户端
4. **前端更新**: JavaScript接收数据并更新显示元素

### 错误处理

- **连接失败**: 自动重试连接，失败时显示错误状态
- **数据异常**: 验证数据有效性，无效数据时显示警告状态
- **网络超时**: 设置合理的超时时间，避免长时间阻塞

## 扩展开发

### 添加新的ATU设备

1. 修改 `atu_client.py` 中的 `_parse_status_data()` 方法
2. 根据设备的API格式添加新的解析逻辑
3. 更新配置文件中的设备类型选项

### 自定义显示样式

修改 `www/style.css` 中的ATU样式定义：

```css
/* 自定义功率仪表颜色 */
#atuPowerMeter::-webkit-meter-optimum-value {
    background: linear-gradient(to right, #00ff00 0%, #ffff00 70%, #ff0000 100%);
}
```

### 添加历史数据

可以在后端添加数据历史记录功能：

```python
# 在atu_client.py中添加历史记录
self._history = []
# 在获取数据时保存历史
self._history.append(status)
if len(self._history) > 100:  # 保留最近100条记录
    self._history.pop(0)
```

## 支持和反馈

如有问题或建议，请：

1. 查看日志文件 `uhrr_debug.log`
2. 运行测试脚本 `test_atu_integration.py`
3. 检查ATU设备文档和网络配置

---

*最后更新: 2025年10月*
*版本: v1.0.0*

