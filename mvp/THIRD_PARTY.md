# 开源组件与复用说明

MVP 复用成熟基础组件，避免重新编写终端模拟器、Windows PTY、SSH、串口和 Web 框架。教学页面、课程、自评流程、词法检索与工具绑定是本目录的应用实现。

| 组件 | 使用方式 | 上游 / 许可 |
|---|---|---|
| xterm.js 5.5.0 | 浏览器真实终端显示，JS/CSS 随包提供 | [xtermjs/xterm.js](https://github.com/xtermjs/xterm.js) · MIT |
| @xterm/addon-fit 0.10.0 | 终端尺寸同步，JS 随包提供 | [xterm.js addons](https://github.com/xtermjs/xterm.js/tree/master/addons) · MIT |
| pywinpty 2.0.11 | Windows 伪终端，不采用模拟命令输出 | [andfoy/pywinpty](https://github.com/andfoy/pywinpty) · MIT |
| FastAPI 0.141.1 | 本地 HTTP / WebSocket 接口 | [FastAPI](https://fastapi.tiangolo.com/) · MIT |
| Uvicorn 0.34.0 | 单进程 ASGI 服务 | [Uvicorn](https://www.uvicorn.org/) · BSD-3-Clause |
| Paramiko 5.0.0 | SSH 认证、主机密钥验证、交互通道 | [Paramiko](https://www.paramiko.org/) · LGPL-2.1 |
| pyserial 3.5 | 枚举和连接本地物理串口 | [pyserial](https://pyserial.readthedocs.io/) · BSD-3-Clause |
| Requests 2.31.0 | OpenAI 兼容接口、SSE 流读取 | [Requests](https://requests.readthedocs.io/) · Apache-2.0 |
| websockets 15.0.1 | WebSocket 服务支持及轻量验证客户端 | [websockets](https://websockets.readthedocs.io/) · BSD-3-Clause |

随包前端文件位于 `static/vendor/`。原始许可保存在同目录 `xterm-LICENSE.txt` 和 `addon-fit-LICENSE.txt`；不删除上游版权声明。Python 包通过依赖安装使用，许可随各包分发。

架构交互延续本仓库“终端 + 右侧教学栏”的设计，未整仓复制 Clide、Electerm 或其他桌面客户端代码。
