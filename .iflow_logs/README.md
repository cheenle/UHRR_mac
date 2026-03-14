# iFlow CLI 对话记录目录

本目录用于保存与 iFlow CLI 在本项目中的对话记录。

## 🚀 完全自动记录方案（推荐）

### 方案1：一键启动（最简单）

```bash
cd /Users/cheenle/UHRR/MRRC/.iflow_logs
./start_iflow.sh
```

这会启动一个自动记录的新 shell，所有输入输出都会保存到 `.iflow_logs/2026-03-12_时间戳_iflow_session.log`。

退出时按 `Ctrl+D` 或输入 `exit`，日志自动保存。

### 方案2：Shell 函数（最灵活）

将自动记录功能添加到 shell：

```bash
# 临时启用（当前终端有效）
source /Users/cheenle/UHRR/MRRC/.iflow_logs/iflow_auto_log.sh

# 永久启用（添加到 ~/.zshrc 或 ~/.bashrc）
echo 'source /Users/cheenle/UHRR/MRRC/.iflow_logs/iflow_auto_log.sh' >> ~/.zshrc
```

然后使用以下命令：

```bash
iflow          # 启动带自动记录的 iFlow CLI 会话
iflow-logs     # 查看最近的会话记录列表
iflow-today    # 查看今日的所有会话
```

---

## 其他记录方式

### 方法1：手动复制（推荐）

1. 对话结束后，点击 iFlow CLI 界面的复制按钮
2. 创建一个新文件：`YYYY-MM-DD_简短描述.md`
3. 粘贴内容保存

### 方法2：使用终端日志

在启动 iFlow CLI 之前，先开启终端日志记录：

```bash
# 进入项目目录
cd /Users/cheenle/UHRR/MRRC

# 启动日志记录（macOS/Linux）
script -r .iflow_logs/terminal_$(date +%Y%m%d_%H%M%S).log

# 然后启动你的 iFlow CLI...

# 退出时输入
exit
```

### 方法3：iFlow 记忆功能

对于重要的项目信息，可以直接告诉我：

> "记住：我的电台型号是 IC-R9000，串口设备是 /dev/cu.usbserial-120"

这样我会使用 `save_memory` 工具保存到长期记忆。

## 文件命名规范

建议使用以下格式：

```
YYYY-MM-DD_简短描述.md
```

例如：
- `2026-03-12_修复PTT延迟问题.md`
- `2026-03-15_添加新功能讨论.md`

## 内容格式建议

```markdown
# 对话记录 - YYYY-MM-DD

## 主题
简要描述本次对话的主要内容

## 背景
相关的上下文信息

## 讨论内容
1. 问题/需求描述
2. 解决方案
3. 实现细节

## 关键决策
- 决策1
- 决策2

## 后续行动
- [ ] 任务1
- [ ] 任务2

## 相关文件
- `/path/to/file1`
- `/path/to/file2`
```

## 注意事项

1. **隐私**：请勿保存敏感信息（密码、密钥等）
2. **大小**：定期清理过大的日志文件
3. **备份**：重要记录建议同步到云盘或版本控制
