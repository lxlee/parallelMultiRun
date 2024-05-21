## 多机器并行执行

### 程序
主要流程文件parallelRun.py, 流程主要分为三个：prepares, tasks, posts
* prepares, 为task执行做准备，目前主要是在主机器上执行，可以用来准备tasks执行需要的配置文件、环境等.  
* tasks, 多机器运行程序，依赖ssh登录到各台机器上执行相同的task程序，可以通过配置文件等方式实现不用机器的差异化执行.
* posts, tasks执行完后，可对数据进行处理等进一步操作

### 配置
config.yml 主要的配置文件 
