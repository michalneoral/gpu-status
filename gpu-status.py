#!/usr/bin/python
import subprocess as sp
import xml.etree.ElementTree
import os
import pwd
import argparse
import psutil
import socket

red_c = '\x1b[0;31m'
blue_c = '\x1b[0;34m'
cyan_c = '\x1b[0;36m'
green_c = '\x1b[0;32m'
yellow_c = '\x1b[0;33m'
magenta_c = '\x1b[0;35m'
red_cb = '\x1b[1;31m'
blue_cb = '\x1b[1;34m'
cyan_cb = '\x1b[1;36m'
green_cb = '\x1b[1;32m'
yellow_cb = '\x1b[1;33m'
magenta_cb = '\x1b[1;35m'

def owner(pid):
    try:
        # the /proc/PID is owned by process creator
        proc_stat_file = os.stat("/proc/{}".format(pid))
        # get UID via stat call
        uid = proc_stat_file.st_uid
        # look up the username from uid
        username = pwd.getpwuid(uid)[0]
    except:
        username = 'unknown'
    return username


def get_status():
    status = {}

    smi_cmd = ['nvidia-smi', '-q', '-x']  # get XML output
    proc = sp.Popen(smi_cmd, stdout=sp.PIPE, stderr=sp.PIPE)
    stdout, stderr = proc.communicate()

    gpu_info_cmd = ['nvidia-smi',
                    '--query-gpu=index,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu',
                    '--format=csv,noheader']

    proc = sp.Popen(gpu_info_cmd, stdout=sp.PIPE, stderr=sp.PIPE)
    gpu_stdout, gpu_stderr = proc.communicate()
    gpu_infos = gpu_stdout.strip().split('\n')
    gpu_infos = map(lambda x: x.split(', '), gpu_infos)
    gpu_infos = [{'index': x[0],
                  'mem_total': x[1],
                  'mem_used': x[2],
                  'mem_free': x[3],
                  'gpu_util': x[4],
                  'gpu_temp': x[5]}
                 for x in gpu_infos]

    e = xml.etree.ElementTree.fromstring(stdout)
    for id, gpu in enumerate(e.findall('gpu')):
        gpu_stat = {}

        index = int(gpu_infos[id]['index'])
        utilization = gpu.find('utilization')
        gpu_util = utilization.find('gpu_util').text
        gpu_temp = gpu_infos[id]['gpu_temp'].split()[0]
        mem_free = gpu_infos[id]['mem_free'].split()[0]
        mem_total = gpu_infos[id]['mem_total'].split()[0]

        gpu_stat['gpu_util'] = float(gpu_util.split()[0]) / 100
        gpu_stat['mem_free'] = int(mem_free)
        gpu_stat['mem_total'] = int(mem_total)
        gpu_stat['gpu_temp'] = int(gpu_temp)

        gpu_procs = []
        procs = gpu.find('processes')
        for procinfo in procs.iter('process_info'):
            pid = int(procinfo.find('pid').text)
            mem = procinfo.find('used_memory').text
            mem_num = int(mem.split()[0])
            user = owner(pid)

            tmp = {'user': user,
                   'mem': mem_num}
            command = ""
            try:
                p = psutil.Process(pid)
                command = ' '.join(p.cmdline())
                tmp['command'] = command
            except:
                pass
            gpu_procs.append(tmp)
        gpu_stat['proc'] = gpu_procs
        status[index] = gpu_stat

    return status

def get_color_memory(value, max_value=1.0):
    perc = 100 * (float(value) / max_value)
    if perc > 95:
        return green_cb
    elif perc > 80:
        return blue_cb
    elif perc > 40:
        return yellow_cb
    else:
        return red_cb

def pretty_print(status, verbose=False):
    line_separator = '+-----+------+--------------------+----------+'
    print(line_separator)
    print('| GPU | TEMP |    Memory-Usage    | GPU-Util |')
    print('|=====+======+====================+==========|')
    for id, stats in status.iteritems():
        color_out = '\x1b[0m'

        # GPU Memory
        mem_free = stats['mem_free']
        mem_total = stats['mem_total']
        mem_color = get_color_memory(mem_free, mem_total)

        # GPU Proc
        gpu_util = stats['gpu_util']
        gpu_color = get_color_memory(1.0 - gpu_util)

        # GPU Temp
        temp = stats['gpu_temp']

        header = '| {:2d}  | {:3d}C | {}{:6d}{} /{:6d} MiB | {}{:7d}{}% |'.format(id,
                                                             temp,
                                                             mem_color,
                                                             mem_free,
                                                             color_out,
                                                             mem_total,
                                                             gpu_color,
                                                             int(100*gpu_util),
                                                             color_out)
        print header
        print(line_separator)

    line_separator = '+-----+---------------------+----------------+'
    print('')
    print(line_separator)
    print('| GPU |    PROCESS OWNER    |     MEMORY     |')
    print('|=====+=====================+================|')
    for id, stats in status.iteritems():
        if len(stats['proc']) == 0:
            continue
        for proc in stats['proc']:
            line = '| {:2d}  | {:19s} | {:10} MiB |'.format(id, proc['user'], proc['mem'])
            print(line)
            if verbose:
                print(proc['command'])
                print('')
    print(line_separator)



if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', action='store_true', help='show commands')
    args = vars(parser.parse_args())

    verbose = args['v']

    hostname = socket.gethostname()
    if hostname == 'halmos':
        print('!!! Halmos has GPU 0 and GPU 3 switched !!!\n')

    pretty_print(get_status(), verbose)
