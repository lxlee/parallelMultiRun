#!/usr/bin/env python3

import os
import yaml
import paramiko
import scp
import logging
import threading
import time
import socket
from multiprocessing.pool import ThreadPool
import click


def catchException(func):
    def innerCaller(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except Exception as e:
            logging.critical(e)
            raise(e)
    return innerCaller

class Host:
    def __init__(self, host, username, password, port=22, env=None) -> None:
        self._host = host
        self._username = username
        self._password = password
        self._port = port
        self._env = env

        self._ssh = paramiko.SSHClient()
        self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._ssh.connect(host, username=username, port=port, password=password, timeout=10)
        self._scp = scp.SCPClient(self._ssh.get_transport());

        self.__setup_env()
        self._sourceCMD = 'source /tmp/.env_paramiko'

    def name(self):
        return f"{self._username}@{self._host}:{self._port}"

    @property
    def host(self):
        return self._host

    @property
    def port(self):
        return self._port

    def __setup_env(self):
        self._ssh.exec_command('rm -f /tmp/.env_paramiko')
        for k, v in self._env.items():
            self._ssh.exec_command(f'echo "{k}={v}" >> /tmp/.env_paramiko')
        self._ssh.exec_command('echo "export PATH=/home/wision/.local/bin:$PATH" >> /tmp/.env_paramiko')
        self._ssh.exec_command('echo "export PYTHONPATH=/home/wision/work/myPylibs:$PYTHONPATH" >> /tmp/.env_paramiko')
        # self._ssh.exec_command('source /tmp/.env_paramiko') # not working ...

    @catchException
    def scpto(self, source, target):
        logging.info(f"[TASK][{self._host}] scpto {source} {target}")
        if os.path.isfile(source):
            self._scp.put(source, target)
        else:
            self._scp.put(source, target, recursive=True)

    @catchException
    def scpfrom(self, source, target):
        logging.info(f"[TASK][{self._host}] scpfrom {source} {target}")
        self._scp.get(source, target, recursive=True)

    @catchException
    def execCmd(self, cmdline):
        logging.info(f"[TASK][{self._host}] cmd {cmdline}")
        if cmdline.startswith("sudo"):
            cmdline = cmdline.replace("sudo", "sudo -S -p ''")
            stdin_, stdout_, stderr_ = self._ssh.exec_command(self._sourceCMD + ";" + cmdline, get_pty=True)
            stdin_.write(self._password + "\n")
            stdin_.flush()
        else:
            stdin_, stdout_, stderr_ = self._ssh.exec_command(self._sourceCMD + ";" + cmdline)
        status = stdout_.channel.recv_exit_status()
        if 0 != status:
            logging.warning(f"[TASK][{self._host}] status {status}")
            logging.warning(f"[TASK][{self._host}] error : {stderr_.read().decode('utf-8')}")
        else:
            logging.info(f"[TASK][{self._host}] cmd finished")

class HostManager:
    def __init__(self, hostcfgs):
        self._hosts = []
        try:
            for hc in hostcfgs:
                self._hosts.append(Host(hc['ip'], hc['username'], hc['password'], hc['port'], hc['env']))
                logging.info(f"Connected to {hc['username']}@{hc['ip']}:{hc['port']}")

            self._monitor = threading.Thread(target=self.monitor)
            self._monitor.setDaemon(True)
            self._monitor.start()
        except Exception as e:
            logging.critical(f"Failed to connect to {hc['username']}@{hc['ip']}:{hc['port']} with pass({type(hc['password'])})")
            logging.critical(e)
            return
    
    def __len__(self):
        return len(self._hosts)

    def runTasks(self, taskArray:list):
        for task in taskArray:
            prog = list(task.keys())[0]
            if "ScpTo" == prog:
                with ThreadPool(len(self)) as pool:
                    for host in self._hosts:
                        pool.apply_async(host.scpto, (task[prog]['source'], task[prog]['target']))
                    pool.close()
                    pool.join()
            elif "ScpFrom" == prog:
                with ThreadPool(len(self)) as pool:
                    for host in self._hosts:
                        pool.apply_async(host.scpfrom, (task[prog]['source'], task[prog]['target']))
                    pool.close()
                    pool.join()
            elif "LocalCmd" == prog:
                logging.info(f"[RUN][localhost] cmd {task[prog]}")
                os.system(task[prog])
            elif "RemoteCmd" == prog:
                with ThreadPool(len(self)) as pool:
                    for host in self._hosts:
                        pool.apply_async(host.execCmd, (task[prog],))
                    pool.close()
                    pool.join()
            else:
                logging.critical(f"Unsupport cmd \"{prog}\"")

    def monitor(self):
        def online(ip, port):
            try:
                socket.create_connection((ip, port), timeout=5)
                return True
            except socket.error:
                return False

        while True:
            for host in self._hosts:
                if not online(host.host, host.port):
                    logging.critical(f"\"{host.name()}\" offline.")

            time.sleep(10)

def printHelp():
        print('''config.yml format:
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
'''
              )
        
@click.command("")
@click.option("-c", default="config.yml", help="config file")
@click.option("-v", is_flag=True, default=False, help="logging verbose")
@click.option("-h", is_flag=True, default=False, help="show config format help")
def _main(c, v, h):
    if h:
        printHelp()
        return
    
    if v:
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')
    else:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')

    if not os.path.exists(c):
        logging.critical(f"[MAIN][localhost] {c} not exists")
        return
    
    logging.info(f"Running with config '{c}'")
    try:
        with open(c, "r") as f:
            config = yaml.safe_load(f)
    except Exception:
        logging.critical(f"[MAIN][localhost] format error in '{c}'")
        return


    if not "hosts" in config:
        logging.warning("[MAIN][localhost] no hosts config found...")
        return

    hostManager = HostManager(config['hosts'])
    if len(hostManager) != len(config['hosts']):
        logging.warning("[MAIN][localhost] Some host connect error ...")
        return

    logging.info(f"[MAIN][localhost] Will run on {len(hostManager)} hosts")
    if "tasks" in config:
        # export some environment params.
        os.environ['config_file'] = c;
        os.environ['remote_host_num'] = str(len(hostManager))
        hostManager.runTasks(config["tasks"])

    logging.info("[MAIN][localhost] Work Finished")

if __name__ == "__main__":
    _main()
