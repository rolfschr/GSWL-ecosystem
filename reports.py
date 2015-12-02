#!/usr/bin/python
"""
Usage:
    reports.py [<file> [<report-num>]]

"""

import sys
import os
import tty
import termios
import subprocess

REPORT_FILE = 'reports.txt'
TEMP_SCRIPT_FILE = '/tmp/.ledgerscript.sh'
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
COLOR_BLUE = '\\e[36m'
COLOR_RESET = '\\e[0m'
CMD_EXPL_COLOR = COLOR_BLUE


def getchar():
    """
    Get a single character from stdin.
    """
    # from http://code.activestate.com/recipes/134892/
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch


def colorize(msg):
    return '{}{}{}'.format(CMD_EXPL_COLOR, msg, COLOR_RESET)


def escape(s):
    return s.replace('"', '\\"').replace('`', '\\`').replace('$', '\\$')


def makescript(expl, cmds):
    """
    Make a helper script which eases usage of the ecosystem.
    """
    out = ""
    out += '#!/bin/bash\n'
    out += 'shopt -s expand_aliases\n'
    out += '. {}/alias\n'.format(THIS_DIR)
    expl = escape(expl)
    out += 'echo -e "{}{}{}"\n'.format(CMD_EXPL_COLOR, expl, COLOR_RESET)
    out += 'echo ""\n'
    for cmd in cmds:
        s = escape(cmd)
        if (cmd.startswith('echo')):  # prevent "double echo"
            out += 'echo -e -n "{} "\n'.format(colorize('\$ echo'))
        else:
            out += 'echo -e "{}"\n'.format(colorize('\$ ' + s))
        out += '{}\n'.format(cmd)
    with open(TEMP_SCRIPT_FILE, 'w') as fh:
        fh.write(out)
    os.chmod(TEMP_SCRIPT_FILE, 0o777)


def show((expl, cmds)):
    """
    Show one report from the report file.
    """
    makescript(expl, cmds)
    os.system('clear')
    subprocess.call(TEMP_SCRIPT_FILE, shell=True)


def main(argv=None):
    try:
        filename = argv[1]
    except:
        filename = REPORT_FILE
    try:
        reportnum = int(argv[2]) - 1
    except:
        reportnum = 0

    reports = []
    with open(filename, 'r') as fh:
        expl = ''
        cmds = []
        lines = fh.readlines()[2:]  # skip header lines
        for i, line in enumerate(lines):
            if (line.startswith('#')):
                expl += line
            elif (not line.startswith('\n')):
                # consider everything else till a blank line as commands
                cmds.append(line.strip())

            ipp = i + 1
            if (cmds and (ipp == len(lines) or lines[ipp].startswith('\n'))):
                reports.append((expl.strip(), cmds))
                cmds = []
                expl = ''

    i = reportnum
    while True:
        show(reports[i])
        print('')
        print('[#{}] h = previous report, l = next report, q = quit [h/l/q] ?'.
              format(i + 1))
        action = getchar()
        # TODO: get char of cursor left/up/right/down
        if (action == 'h'):
            i = i - 1 if i > 0 else len(reports) - 1
        elif (action == 'l'):
            i = i + 1 if i < len(reports) - 1 else 0
        elif (action == 'q'):
            break

if __name__ == '__main__':
    main(sys.argv)
