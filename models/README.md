# CW 解码器模型

## 模型文件

本目录需要放置 `cw_decoder.onnx` 模型文件才能使用AI解码功能。

## 获取模型

### 方法一：从 GitHub 下载 (推荐)

```bash
cd /Users/cheenle/UHRR/MRRC/models
curl -L -o cw_decoder.onnx "https://github.com/e04/web-deep-cw-decoder/raw/refs/heads/master/model/cw_decoder.onnx"
```

### 方法二：手动下载

1. 访问 https://github.com/e04/web-deep-cw-decoder
2. 进入 `model` 目录
3. 下载 `cw_decoder.onnx` 文件
4. 将文件放置到本目录

## 模型信息

- **来源**: web-deep-cw-decoder 项目
- **作者**: e04
- **大小**: 约 2MB
- **格式**: ONNX
- **用途**: CW (摩尔斯码) 实时解码

## 验证模型

下载后可以使用以下命令验证模型完整性：

```bash
# 检查文件类型
file cw_decoder.onnx
# 应该显示: "data" 或 "ONNX model"

# 检查文件大小
ls -lh cw_decoder.onnx
# 应该约为 2MB
```

## 不使用模型

如果没有模型文件，CW解码器将自动使用传统的自适应阈值DSP算法进行解码。
虽然准确率可能略低于AI模型，但也能正常工作。
