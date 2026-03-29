#!/bin/bash
# acme.sh 代理配置
# 添加到 ~/.bashrc 或 ~/.zshrc

# 代理设置 (根据你的网络环境调整)
export HTTPS_PROXY="socks5://127.0.0.1:3328"
export ACME_USE_WGET=1

# acme.sh 路径
export PATH="$HOME/.acme.sh:$PATH"

# 可选: Cloudflare DNS API Token (如果使用 Cloudflare DNS 验证)
# export CF_Token="your-cloudflare-api-token"
# export CF_Account_ID="your-cloudflare-account-id"

echo "acme.sh 代理配置已加载"
echo "代理: $HTTPS_PROXY"
