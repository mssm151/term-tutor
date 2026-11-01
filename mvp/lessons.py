"""Small, bundled curriculum. Completion is explicitly self-reported."""
LESSONS = [
    {
        'id': 'powershell', 'title': 'PowerShell 入门', 'tag': '本地实验',
        'description': '从当前位置出发，认识目录、文件和管道。建议在新建的本地会话中练习。',
        'steps': [
            {'title': '认识当前位置', 'goal': '查看当前目录和目录中的文件，理解相对路径从哪里开始。',
             'hint': '先试试 Get-Location，再用 Get-ChildItem。观察输出中的 Path、Mode 和 Name。',
             'commands': ['Get-Location', 'Get-ChildItem']},
            {'title': '创建练习目录', 'goal': '创建名为 practice 的目录并进入它，再确认当前位置。',
             'hint': 'New-Item -ItemType Directory 用于创建目录，Set-Location 用于切换目录。目录已存在时不必重复创建。',
             'commands': ['New-Item -ItemType Directory -Path practice', 'Set-Location practice', 'Get-Location']},
            {'title': '写入并读取文件', 'goal': '把 hello terminal 写入 hello.txt，然后读取并核对内容。',
             'hint': 'Set-Content 会覆盖目标文件；请只操作练习文件。Get-Content 用于查看文件内容。',
             'commands': ["Set-Content -Path hello.txt -Value 'hello terminal'", 'Get-Content hello.txt']},
            {'title': '用管道筛选', 'goal': '找到当前目录下所有 .txt 文件，并只显示文件名和长度。',
             'hint': 'PowerShell 管道传递对象。先筛选文件，再使用 Select-Object 选择属性。',
             'commands': ['Get-ChildItem -File -Filter *.txt | Select-Object Name,Length']},
        ],
    },
    {
        'id': 'linux', 'title': 'Linux / SSH 基础', 'tag': '远程实验',
        'description': '连接你已有的 Linux SSH 主机后练习。目标主机无需安装 AI Agent。',
        'steps': [
            {'title': '确认目标主机', 'goal': '确认当前用户、主机和目录，避免在错误的机器上操作。',
             'hint': '不要把本地 PowerShell 环境当成 SSH 目标环境。', 'commands': ['whoami', 'hostname', 'pwd']},
            {'title': '查看目录', 'goal': '查看目录内容和隐藏文件，理解权限列与文件大小。',
             'hint': 'ls -la 会显示隐藏文件。文件名开头的点通常表示隐藏。', 'commands': ['ls -la']},
            {'title': '查找文本', 'goal': '在已有文本文件中搜索关键词，解释 grep 的输出。',
             'hint': '先确认文件存在，再替换示例中的文件名与关键词。', 'commands': ["grep -n 'keyword' example.txt"]},
        ],
    },
    {
        'id': 'docker', 'title': 'Docker 状态排查', 'tag': '进阶实验',
        'description': '需要已安装且可连接的 Docker 引擎。先确认 context，再分析容器状态。',
        'steps': [
            {'title': '确认 Docker 目标', 'goal': '查看 Docker 版本和当前 context，区分客户端与服务端。',
             'hint': 'docker version 只有 Client 不代表引擎可用；context 可能指向另一台机器。',
             'commands': ['docker version', 'docker context show']},
            {'title': '观察容器状态', 'goal': '列出包含已退出容器的清单，识别容器名称、状态和退出码。',
             'hint': 'docker ps 默认只列运行中的容器，加 -a 查看全部。', 'commands': ['docker ps -a']},
            {'title': '分析日志', 'goal': '为一个已有容器查看最近日志，结合退出状态提出原因假设。',
             'hint': '把 CONTAINER 替换为实际容器名；分享日志前留意其中的密钥和业务数据。',
             'commands': ['docker logs --tail 30 CONTAINER']},
        ],
    },
    {
        'id': 'kubernetes', 'title': 'Kubernetes 观察', 'tag': '进阶实验',
        'description': '需要已有 kubectl 和集群权限。本课仅观察已有资源。',
        'steps': [
            {'title': '确认集群上下文', 'goal': '识别当前 context 和 namespace，确认工具操作目标。',
             'hint': '本机安装 kubectl 不代表已接入集群；不要上传 kubeconfig 原文。',
             'commands': ['kubectl config current-context', 'kubectl config view --minify -o jsonpath={..namespace}']},
            {'title': '查看 Pod', 'goal': '查看当前 namespace 中的 Pod，理解 READY、STATUS 和 RESTARTS。',
             'hint': '权限不足或网络不通应标为未知，不能据此判断集群不存在。', 'commands': ['kubectl get pods']},
            {'title': '查看事件', 'goal': '观察一个已有 Pod 的事件并分析 Pending 或重启的可能原因。',
             'hint': '将 POD 替换为实际名称，先看 Events 部分。', 'commands': ['kubectl describe pod POD']},
        ],
    },
]


def lesson_by_id(lesson_id):
    return next((item for item in LESSONS if item['id'] == lesson_id), None)
