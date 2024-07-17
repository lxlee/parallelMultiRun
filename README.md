## 多机器并行执行

### 程序
主要流程文件parallelRun.py, 主要配置分为三个：hosts, tasks
```bash
>localhost$ ./parallelRun.py -h
config.yml format:
hosts:
    -
        ip:
        post:
        username:
        password:
tasks:
    -   
        [ScpTo|ScpFrom]:
            source:
            target:
    -
        [LocalCmd|RemoteCmd]:
```
* hosts, 配置远程机器ssh相关参数
* tasks, 多机器运行程序，依赖ssh登录到各台机器上执行相同的task程序，可以通过配置文件等方式实现不用机器的差异化执行.  
    * ScpTo, 拷贝本机文件到远程位置
    * ScpFrom, 拷贝远程文件到本机
    * LocalCmd, 本机运行的命令
    * RemoteCmd, 远程机分别运行的命令

### 配置
config.yml 主要的配置文件 
