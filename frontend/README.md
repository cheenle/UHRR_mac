# Universal HamRadio Remote - Node.js Frontend

现代化Node.js + React前端，支持桌面端和移动端界面。

## 功能特性

### 桌面端界面
- 完整的电台控制面板
- 实时频谱显示
- 音频控制设置
- 多标签页布局

### 移动端界面
- 优化的触摸界面
- 紧凑的控制布局
- 实时频谱显示
- 底部导航栏

## 技术架构

- **框架**: Express.js (服务器) + React (UI)
- **实时通信**: Socket.io
- **音频处理**: Web Audio API + AudioWorklet
- **构建工具**: Webpack + Babel
- **样式**: CSS3 + 响应式设计

## 安装和运行

### 开发环境

```bash
# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build

# 启动生产服务器
npm start
```

### Docker部署

```bash
# 构建镜像
docker build -t uhrr-frontend .

# 运行容器
docker run -p 3000:3000 uhrr-frontend
```

## 项目结构

```
frontend/
├── public/                 # 静态资源
│   └── index.html         # HTML模板
├── src/
│   ├── components/        # React组件
│   │   ├── MobileInterface.jsx  # 移动端界面
│   │   ├── RadioControl.jsx     # 电台控制
│   │   ├── SpectrumDisplay.jsx  # 频谱显示
│   │   ├── AudioControl.jsx     # 音频控制
│   │   └── SpectrumMobile.jsx   # 移动端频谱
│   ├── services/         # 业务服务
│   │   ├── audioService.js     # 音频处理
│   │   ├── radioService.js     # 电台控制
│   │   └── websocketService.js # WebSocket通信
│   ├── utils/            # 工具函数
│   │   ├── constants.js       # 常量定义
│   │   └── audioUtils.js      # 音频工具
│   ├── types/            # 类型定义
│   ├── hooks/            # React Hooks
│   ├── App.jsx           # 主应用组件
│   ├── index.js          # 应用入口
│   ├── index.css         # 全局样式
│   └── server.js         # Express服务器
├── package.json          # 依赖配置
├── webpack.config.js     # 构建配置
├── Dockerfile           # Docker配置
└── .env                 # 环境变量
```

## 移动端界面特性

### 界面布局
- **顶部**: 时间显示 + 信号强度 + 断开连接按钮
- **主显示区**:
  - 频率显示（可点击编辑）
  - 模式选择按钮
  - 控制按钮组
  - 信号强度指示器
  - SWR和麦克风电平表
- **底部控制区**:
  - 日志按钮
  - PTT按钮（触摸操作）
  - 步进控制
- **频谱显示区**: 实时频谱瀑布图
- **底部导航**: VFO/Modes/Tools/IC-7610/Settings

### 交互特性
- **触摸优化**: 所有按钮和滑块都针对触摸操作优化
- **响应式设计**: 自适应不同屏幕尺寸
- **实时更新**: 所有状态实时同步
- **音频反馈**: PTT按钮有视觉和触觉反馈

## API接口

### WebSocket事件

#### 客户端到服务器
```javascript
// 加入电台会话
socket.emit('join-radio', { radioId: 'default' });

// 发送音频数据
socket.emit('audio-data', { type: 'tx', data: audioBuffer });

// 电台控制命令
socket.emit('radio-command', { command: 'setFrequency', value: 7050000 });
```

#### 服务器到客户端
```javascript
// 电台状态更新
socket.on('radio-status', (status) => {
  console.log('Radio status:', status);
});

// 接收音频数据
socket.on('audio-received', (audioData) => {
  // 处理音频播放
});

// 频谱数据
socket.on('spectrum-data', (spectrumData) => {
  // 更新频谱显示
});
```

## 环境变量

```bash
# 后端API URL
REACT_APP_BACKEND_URL=http://localhost:3000

# Socket.io配置
SOCKET_IO_PATH=/socket.io
SOCKET_IO_RECONNECT=true

# 音频设置
AUDIO_SAMPLE_RATE=24000
AUDIO_CHANNELS=1

# 默认电台设置
DEFAULT_FREQUENCY=7050000
DEFAULT_MODE=USB
```

## 开发指南

### 添加新组件
1. 在 `src/components/` 下创建组件文件
2. 导入并在适当的父组件中使用
3. 添加相应的CSS样式文件

### 添加新服务
1. 在 `src/services/` 下创建服务文件
2. 在主应用中初始化并传递给组件
3. 实现相应的API调用和事件处理

### 样式开发
- 使用CSS变量进行主题管理
- 遵循响应式设计原则
- 为移动端优化触摸目标尺寸（最小44px）

## 浏览器支持

- **桌面端**: Chrome 90+, Firefox 88+, Safari 14+, Edge 90+
- **移动端**: iOS Safari 14+, Android Chrome 90+

## 许可证

本项目遵循 GPL-3.0 许可证。

## 贡献

欢迎提交Issue和Pull Request。在提交代码前，请确保：
- 遵循项目的代码规范
- 添加适当的测试
- 更新相关文档
