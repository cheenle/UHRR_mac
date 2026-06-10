# V3.0 Fuchs ATU — 验证清单

> 覆盖：固件烧录、硬件装配、MRRC联调、现场验收

---

## 1. 固件编译与烧录

- [ ] **ESP-IDF 环境**: `idf.py --version` 确认 v5.0+
- [ ] **目标芯片**: `idf.py set-target esp32s3`
- [ ] **cJSON 组件**: `components/cJSON/cJSON.c` 存在 (3143行)
- [ ] **编译通过**: `idf.py build` 无错误无警告
- [ ] **分区表**: `idf.py partition_table` 显示 `nvs_tune` (0xDF0000, 24KB)
- [ ] **Flash 大小**: 16MB (CONFIG_ESPTOOLPY_FLASHSIZE_16MB=y)
- [ ] **烧录**: `idf.py flash` 成功
- [ ] **串口监控**: `idf.py monitor` 显示 `=== Fuchs ATU V3.0 (ESP32-S3) ===`
- [ ] **启动蜂鸣**: 上电后蜂鸣器响 1 声
- [ ] **LED 状态**: 
  - [ ] WiFi 断连 → LED 快闪 (200ms 周期 ×3, 每 5s)
  - [ ] WiFi 已连+WS 已连 → LED 常亮

---

## 2. WiFi 连接

- [ ] **sdkconfig 中 SSID/密码**: `CONFIG_ESP_WIFI_SSID` 和 `CONFIG_ESP_WIFI_PASSWORD` 已设置为实际路由器
- [ ] **连接成功**: 串口日志显示 `WiFi connected, IP: xxx.xxx.xxx.xxx`
- [ ] **断连重连**: 关闭路由器 → LED 快闪 → 重启路由器 → 30s 内自动恢复
- [ ] **信号强度**: 安装位置 (室外 IP66 壳体内) 串口 `esp_wifi_get_rssi()` ≥ -75 dBm

---

## 3. WebSocket 连接 (MRRC)

- [ ] **MRRC 服务器**: `MRRC_WS_URL_DEFAULT` 指向正确 IP:端口 (如 `ws://192.168.1.100:8877/atu`)
- [ ] **atu_fuchs_handler.py 已部署**: MRRC 启动日志显示 `Fuchs ATU WebSocket endpoint registered at /atu`
- [ ] **WebSocket 连接成功**: 串口日志显示 `WebSocket connected to MRRC`
- [ ] **get_status**: 串口发送 `{"cmd":"get_status"}` → 返回 `{"evt":"status_report",...}`
- [ ] **断连重连**: 停止 MRRC → WS disconnect → 重启 MRRC → 3s 内自动重连

---

## 4. 伺服测试 (无RF)

- [ ] **伺服供电**: 上电后万用表测量 HDR_SERVO Pin2 (VCC_SERVO) = 0V (空闲时断电)
- [ ] **set_bypass**: 发送 `{"cmd":"set_bypass"}` → 伺服转到 0° (电容最小值), 然后断电
- [ ] **手动位置**: 发送自定义位置测试 0°, 90°, 180° 三个角度, 确认机械行程无障碍
- [ ] **MOSFET 开关**: 
  - [ ] 调谐期间: VCC_SERVO = 6V (MOSFET 导通)
  - [ ] 调谐结束: VCC_SERVO = 0V (MOSFET 关断)
- [ ] **齿轮耦合**: 伺服 0°↔180° 完整行程对应电容轴 0°↔180°, 无空回/跳齿
- [ ] **堵转风险确认**: 当前硬件无真实堵转检测; 只做低压短时卡阻试验, 确认不会长时间上电, 并记录“SWR不变化/超时”作为间接症状

---

## 5. 伺服测试 (有RF — 台架)

- [ ] **功放设置**: 5W CW 载波 (≤15W)
- [ ] **ATR1000 在线**: MRRC 能读到 SWR 读数
- [ ] **手动调谐**: 通过 MRRC 发送不同 servo 位置, 观察 SWR 变化趋势
- [ ] **全扫描调谐**: 发送 `tune_start` → 
  - [ ] 粗扫 37 个采样点: 0°→180° @5° (每步 ~80ms 伺服 + ~100ms SWR 往返)
  - [ ] 总时间 < 10s
  - [ ] 最终 SWR < 2.0 (首次, 新频段)
- [ ] **缓存命中**: 同频段再次 tune_start → < 1s 直接定位 (NVS 命中)
- [ ] **缓存持久**: 断电 → 重新上电 → 同频段 tune_start → 缓存命中 < 1s
- [ ] **过功率保护**: 发射 100W → 发送 tune_start → 预期 `tune_error(overpower)`
- [ ] **RF 丢失**: 停止发射 → 发送 tune_start → 预期 `tune_error(no_rf)`

---

## 6. 调谐精度

- [ ] **40m (7.1MHz)**: 全扫描后 SWR < 1.5:1
- [ ] **30m (10.1MHz)**: 全扫描后 SWR < 1.5:1
- [ ] **20m (14.2MHz)**: 全扫描后 SWR < 1.2:1
- [ ] **17m (18.1MHz)**: 全扫描后 SWR < 1.5:1
- [ ] **15m (21.2MHz)**: 全扫描后 SWR < 1.5:1
- [ ] **12m (24.9MHz)**: 全扫描后 SWR < 1.5:1
- [ ] **10m (28.5MHz)**: 全扫描后 SWR < 1.5:1
- [ ] **缓存召回**: 每频段调谐 3 次 → 每次缓存命中 SWR < 2.0

---

## 7. 健康监控

- [ ] **Bias-T 电压**: 串口日志 Bias-V ≈ 12.0V (正常范围 10.0-15.0V)
- [ ] **欠压告警**: Bias-T 电源调至 9V → 预期 `health_alert(DC_RAIL, 9.0V)`
- [ ] **过压告警**: Bias-T 电源调至 16V → 预期 `health_alert(DC_RAIL, 16.0V)`
- [ ] **核心温度**: 串口日志温度 < 60°C (空闲), < 80°C (持续调谐后)
- [ ] **看门狗**: `esp_task_wdt` 已注册 — 故意死循环某 task → 5s 后自动复位

---

## 8. NVS 缓存

- [ ] **写入**: 调谐完成 → 串口日志 `Saved: 14200kHz → pos=67`
- [ ] **查找**: 同频段再次 tune_start → `Cache hit: 14200000Hz → pos=67`
- [ ] **模糊匹配**: 14.205MHz 调谐 (与 14.200MHz 差 50kHz 以内) → 缓存命中
- [ ] **擦除**: `nvs_cache_erase_all()` → 之后 tune_start → `Cache miss`

---

## 9. OTA 固件更新

- [ ] **分区布局**: `idf.py partition_table` 显示 `ota_0` 和 `ota_1` 各 7MB
- [ ] **初始启动**: 从 `ota_0` 启动
- [ ] **OTA 推送**: MRRC → ESP32-S3 HTTPS 下载新固件 → 写入 `ota_1`
- [ ] **切换**: 设置 `ota_1` 为启动分区 → 重启
- [ ] **回滚**: 如果新固件启动失败 → bootloader 自动回滚到 `ota_0`

---

## 10. 现场安装

- [ ] **天线架设**: EFHW ~20m 线, 高度 > 5m
- [ ] **ATU 安装**: 距天线馈电点 < 1m (减少高 SWR 段的传输线损耗)
- [ ] **防水**: IP66 壳体密封圈完好, 底部呼吸孔 PTFE 膜无堵塞
- [ ] **接地**: Counterpoise 2m 自由垂放
- [ ] **Bias-T**: 室内端 13.8V 注入正常, 同轴无短路
- [ ] **WiFi 信号**: 安装位置测 RSSI ≥ -75 dBm
- [ ] **温度范围**: 当地历史最低/最高温在 -20°C ~ +60°C 内
- [ ] **初次全频段扫描**: 逐频段执行 tune_start, 建立缓存 (~8s/频段)

---

## 11. 回归测试 (每次固件更新后)

- [ ] 编译通过零警告
- [ ] 上电 LED+蜂鸣器正常
- [ ] WiFi 连接 + WS 连接
- [ ] set_bypass → 伺服正常
- [ ] 单一频段全扫描调谐 → SWR < 2.0
- [ ] 缓存命中 < 1s
- [ ] 断电重启 → 缓存保留
- [ ] 健康监控无告警
