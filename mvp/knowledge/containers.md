# Docker 与 Kubernetes 排查讲义

## Docker 引擎与 context
docker version 区分 Client 和 Server。docker context show 查看默认目标；DOCKER_HOST、DOCKER_CONTEXT 及显式参数也可能改变目标。Cannot connect to the Docker daemon 只表示当前目标连接失败，不能说明本机未安装 Docker。不要盲目启动、删除或重建容器。

## 容器状态与日志
docker ps -a 展示包含退出容器在内的清单。docker logs --tail 30 CONTAINER 查看近期日志。Exited 说明主进程已结束，可能是正常完成或异常退出；需要结合退出码与日志判断。端口绑定失败需观察冲突端口。容器内的系统信息不代表完整宿主机。

## Kubernetes 环境与排查
kubectl config current-context 查看本地选定上下文；kubectl get pods 查看当前 namespace 的 Pod。kubectl describe pod POD 的 Events 可帮助分析调度失败、拉取镜像失败等情况。Pending、CrashLoopBackOff、ImagePullBackOff 的原因不同，先收集状态与事件再判断。连接失败或 Forbidden 不能推断集群不存在。不要上传 kubeconfig、Secret 或令牌。
