#!/usr/bin/env python3

import os
import yaml
import paramiko
import scp
import logging
import threading
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

    def exec(self, taskArray:list):
        for task in taskArray:
            prog = list(task.keys())[0]
            if "scp" == prog:
                fromFile = task[prog]['from']
                toFile = task[prog]['to']
                self._scp.put(fromFile, toFile)
            elif "cmd" == prog:
                self._ssh.exec_command(task[prog])

def local_exec(paralist:list):
    for paras in paralist:
        if 'cmd' in paras:
            os.system(paras['cmd'])


@click.command("")
@click.option("-c", default="config.yml", help="config file")
@click.option("-v", is_flag=True, default=False, help="logging verbose")
@click.option("-vv", is_flag=True, default=False, help="logging more verbose")
def _main(c, v, vv):
    if vv:
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')
    elif v:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')
    else:
        logging.basicConfig(level=logging.WARN, format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')

    if not os.path.exists(c):
        logging.critical(f"{c} not exists")
        return
    
    logging.info(f"Running with config '{c}'")
    try:
        with open(c, "r") as f:
            config = yaml.safe_load(f)
    except Exception as e:
        logging.critical(f"format error in '{c}'")
        return

    hosts = []
    try:
        if not "hosts" in config:
            logging.warning(f"no hosts config found...")    
            return
        
        for hc in config['hosts']:
            hosts.append(Host(hc['ip'], hc['username'], hc['password'], hc['port']))
            logging.info(f"Connected to {hc['username']}@{hc['ip']}:{hc['port']}")

    except Exception as e:
        logging.critical(f"Failed to connect to {hc['username']}@{hc['ip']}:{hc['port']}")
        return

    logging.info(f"Will run on {len(hosts)} hosts")
    if "prepares" in config:
        logging.info("Running prepare commands")

        # export some environment params.
        os.environ['config_file'] = c;
        os.environ['remote_host_num'] = str(len(hosts))
        local_exec(config["prepares"])

    logging.info("Running tasks")
    threads = []
    for host in hosts:
        threads.append(threading.Thread(target=host.exec, name=host.name(), args=(config['tasks'], )))
        threads[-1].start()
    
    for t in threads:
        t.join()
    
    if "posts" in config:
        logging.info("Running post commands")
        
        # export some environment params.
        os.environ['config_file'] = c;
        os.environ['remote_host_num'] = str(len(hosts))
        local_exec(config["posts"])

if __name__ == "__main__":
    _main()
