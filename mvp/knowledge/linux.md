# Linux 与 SSH 基础讲义

## 确认环境
SSH 连接建立的是远程会话，whoami、hostname、pwd 分别查看用户、主机与当前位置。远端不需要安装 AI Agent。独立 SSH exec 通道不会继承交互 Shell 的 cd、alias、虚拟环境或导出变量；本 MVP 不在独立通道猜测这些状态。

## 目录与文本
ls -la 查看详细目录与隐藏文件。cd 切换目录。cat 读取较小的文本文件，grep -n 'keyword' example.txt 按行搜索。路径区分大小写。Permission denied 可能来自目录权限、用户权限或挂载选项，先看 ls -l，不要直接 chmod 777。No such file or directory 首先核对 pwd 与路径拼写。

## SSH 连接失败
Connection refused 先检查地址、端口与 sshd；Connection timed out 检查网络和防火墙；Authentication failed 核对用户名和认证方式。主机指纹用于防止连接错误目标，首次连接需与管理员核对 SHA256 指纹。私钥、密码不要粘贴进教学对话。
