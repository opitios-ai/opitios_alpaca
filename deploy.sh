#!/bin/bash

# 拉取最新代码
echo "正在拉取最新代码..."
git pull

# 检查 git pull 是否成功
if [ $? -ne 0 ]; then
    echo "git pull 执行失败，停止部署"
    exit 1
fi

# 重启服务
echo "正在重启 opitios_alpaca 服务..."
sudo systemctl restart opitios_alpaca.service

# 检查服务是否重启成功
if [ $? -ne 0 ]; then
    echo "服务重启失败"
    exit 1
fi

# 显示服务日志
echo "正在显示 opitios_alpaca 服务日志..."
sudo journalctl -u opitios_alpaca.service -f
    