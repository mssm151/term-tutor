# 桌面客户端框架目录

此目录仅保留模块划分，不提供可运行 Electron 应用，也不启动 Pi CLI。

- `src/main/`：窗口、连接与本地凭据。
- `src/preload/`：受限 IPC。
- `src/renderer/`：连接列表、学生终端、右侧 Agent 侧栏。
- `src/agent/`：未来嵌入 Pi SDK，管理客户端 Agent 循环。
- `src/tools/`：环境上下文、受控探索、课程检索接口。
- `src/sessions/`：本地 PTY、SSH、SFTP、串口 SerialTransport。
- `src/contracts/`：会话标识、上下文版本和事件契约。

Electron/Pi 由未来 npm 清单管理，目前无需安装。设计见 [架构文档](../docs/架构设计.md)。Django 后端不代替客户端执行终端命令。
