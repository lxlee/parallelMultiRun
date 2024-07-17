#!/usr/bin/env python3

import os
import yaml
import paramiko
import scp
import logging
import threading
from multiprocessing.pool import ThreadPool
import click

class Host:
    def __init__(self, host, username, password, port=22) -> None:
        self._host = host
        self._username = username
        self._password = password
        self._port = port

        self._ssh = paramiko.SSHClient()
        self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._ssh.connect(host, username=username, port=port, password=password, timeout=10)
        self._scp = scp.SCPClient(self._ssh.get_transport());

    def name(self):
        return f"{self._username}@{self._host}:{self._port}"

    def scpto(self, source, target):
        logging.info(f"[TASK][{self._host}] scpto {source} {target}")
        if os.path.isfile(source):
            self._scp.put(source, target)
        else:
            self._scp.put(source, target, recursive=True)

    def scpfrom(self, source, target):
        logging.info(f"[TASK][{self._host}] scpfrom {source} {target}")
        self._scp.get(source, target, recursive=True)

    def execCmd(self, cmdline):
        logging.info(f"[TASK][self._host] cmd {cmdline}")
        _, stdout_, stderr_ = self._ssh.exec_command(cmdline)
        status = stdout_.channel.recv_exit_status()
        if 0 != status:
            logging.warning(f"[TASK][{self._host}] status {status}")
            logging.warning(f"[TASK][{self._host}] error : {stderr_.read().decode('utf-8')}")

class HostManager:
    def __init__(self, hostcfgs):
        self._hosts = []
        try:
            for hc in hostcfgs:
                self._hosts.append(Host(hc['ip'], hc['username'], hc['password'], hc['port']))
                logging.info(f"Connected to {hc['username']}@{hc['ip']}:{hc['port']}")

        except Exception as e:
            logging.critical(f"Failed to connect to {hc['username']}@{hc['ip']}:{hc['port']}")
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
    except Exception as e:
        logging.critical(f"[MAIN][localhost] format error in '{c}'")
        return


    if not "hosts" in config:
        logging.warning(f"[MAIN][localhost] no hosts config found...")
        return

    hostManager = HostManager(config['hosts'])

    logging.info(f"[MAIN][localhost] Will run on {len(hostManager)} hosts")
    if "tasks" in config:
        # export some environment params.
        os.environ['config_file'] = c;
        os.environ['remote_host_num'] = str(len(hostManager))
        hostManager.runTasks(config["tasks"])

    logging.info("[MAIN][localhost] Work Finished")

if __name__ == "__main__":
    _main()
