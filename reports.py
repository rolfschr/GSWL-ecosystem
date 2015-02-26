#!/usr/bin/python
"""
Usage:
    reports.py (<file>)

"""

import sys
import os

REPORT_FILE = 'reports.txt'


def show((expl, cmd)):
    os.system('clear')
    print(expl)
    print(cmd)


def main(argv=None):
    if (argv is not None and len(argv) > 1):
        filename = argv[1]
    else:
        filename = REPORT_FILE

    reports = []
    with open(filename, 'r') as fh:
        expl = ''
        cmd = ''
        for line in fh.readlines()[2:]:  # skip header lines
            if (line.startswith('#')):
                expl += line
            elif (not line.startswith('\n')):
                # consider everything else as the cmd
                cmd = line.strip()

            if (cmd):
                reports.append((expl.strip(), cmd))
                cmd = ''
                expl = ''

    i = 0
    while True:
        show(reports[i])
        action = raw_input('h = previous report, l = next report, q = quit [h/l/q] ? ')
        if (action == 'h'):
            i = i - 1 if i > 0 else len(reports) - 1
        elif (action == 'l'):
            i = i + 1 if i < len(reports) - 1 else 0
        elif (action == 'q'):
            break
    cmd = 'bash -c "source alias && led bal"'

if __name__ == '__main__':
    main(sys.argv)
