# MRRC Website

MRRC项目官方网站源码，用于向HAM Radio社区介绍本项目。

## 文件结构

```
website/
├── index.html          # 首页（中英文双语）
├── installation.html   # 安装指南
├── features.html       # 功能特性
├── documentation.html  # 文档
├── css/
│   ├── style.css      # 主样式
│   └── docs.css       # 文档页面样式
├── js/
│   ├── main.js        # 主脚本
│   └── i18n.js        # 国际化
└── deploy.sh          # 部署脚本
```

## 部署到 www.vlsc.net

### 方法1: 使用部署脚本

```bash
cd website
./deploy.sh
```

### 方法2: 手动复制

```bash
# 打包网站
cd website
tar -czf /tmp/mrrc_website.tar.gz .

# 上传到服务器
scp /tmp/mrrc_website.tar.gz vlsc@www.vlsc.net:/tmp/

# SSH到服务器解压
ssh vlsc@www.vlsc.net
sudo mkdir -p /var/www/vlsc.net/mrrc
cd /var/www/vlsc.net/mrrc
sudo tar -xzf /tmp/mrrc_website.tar.gz
sudo chown -R www-data:www-data /var/www/vlsc.net/mrrc
sudo chmod -R 755 /var/www/vlsc.net/mrrc
sudo systemctl reload apache2
```

### 方法3: rsync同步

```bash
rsync -avz --delete \
  ./website/ \
  vlsc@www.vlsc.net:/var/www/vlsc.net/mrrc/
```

> **注意**：部署目标为 `/var/www/vlsc.net/mrrc/`（不是 `/var/www/html/mrrc/`）。
> 若 rsync 因权限失败，先 `ssh cheenle@www.vlsc.net "sudo chown -R cheenle /var/www/vlsc.net/mrrc"`
> 再部署，完成后恢复 `sudo chown -R www-data:www-data /var/www/vlsc.net/mrrc`。

## Apache配置

确保Apache配置允许.htaccess或添加以下配置：

```apache
<Directory /var/www/vlsc.net/mrrc>
    Options -Indexes +FollowSymLinks
    AllowOverride All
    Require all granted
</Directory>
```

## 特点

- 响应式设计，支持移动端
- 中英文双语切换
- 现代暗色主题设计
- SEO优化
- PWA Ready

## 访问地址

部署后访问：
- https://www.vlsc.net/mrrc/
