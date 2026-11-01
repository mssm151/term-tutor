# PowerShell 基础讲义

## 当前位置和路径
Get-Location 显示 PowerShell 当前目录。Get-ChildItem 列出目录内容。Set-Location（别名 cd）切换目录。相对路径基于当前目录解析，.. 表示父目录。Windows 路径含空格时应加引号，例如 Set-Location 'C:\Program Files'。查看目录命令不会创建文件。

## 创建与读取文件
New-Item -ItemType Directory -Path practice 创建练习目录。Set-Content -Path hello.txt -Value 'hello terminal' 写入文件，会覆盖已有内容；Add-Content 追加内容。Get-Content hello.txt 读取内容。Test-Path 检查路径是否存在。操作前确认当前路径，练习只在自己的工作目录进行。

## PowerShell 管道
PowerShell 管道传递对象而非单纯文本。Get-ChildItem -File -Filter *.txt | Select-Object Name,Length 可以筛选文本文件并选择属性。Where-Object 用于按条件筛选；Get-Member 查看类型与成员。Linux grep 的文本思路与 PowerShell 对象管道不同。

## 命令报错
CommandNotFoundException 或“无法将…识别为…”通常与拼写、未安装、PATH 或当前 Shell 不匹配有关。先用 Get-Command 命令名 检查是否存在。PathNotFound 或 Cannot find path 通常先检查 Get-Location、Test-Path 与路径引号。Access denied 需核实文件权限和目标目录，避免一律以管理员运行。Ctrl+C 中断前台任务。
