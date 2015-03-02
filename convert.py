#!/usr/bin/python
"""
Usage:
    preconvert.py <account> <infile>

"""

import re
import sys
import os
try:
    import yaml
except ImportError:
    print('Missing yaml dependency. Please install with:')
    print('pip install pyyaml')
    sys.exit(1)

CONFIG_FILE = 'bankaccounts.yml'
OUTFILE = '/tmp/out.csv'


def ignore_transactions(lines, patterns):
    def match(line, patterns):
        for pattern in patterns:
            if re.match(pattern, line):
                return True
        return False

    ret = []
    for line in lines:
        if (not match(line, patterns)):
            ret.append(line)
    return ret


def modify_transactions(lines, mods):
    ret = []
    for line in lines:
        for mod in mods:
            line = re.sub(mod[0], mod[1], line)
        ret.append(line)
    return ret


def main(argv=None):
    if (argv is None or len(argv) < 4):
        print __name__
        sys.exit(1)
    account = argv[1]
    csv_filename = argv[2]
    f = file(CONFIG_FILE, 'r')
    cfg = yaml.load(f)
    if account not in cfg:
        print("Cannot find accout {} in config file.".format(account))
        sys.exit(1)
    else:
        acfg = cfg[account]
        with open(csv_filename) as csv_fh:
            lines = csv_fh.readlines()
            lines = lines[int(acfg['ignored_lines']):]
            lines = ignore_transactions(lines, acfg['ignored_transactions'])
            lines = modify_transactions(lines, acfg['modify_transactions'])
            with open(OUTFILE, "w") as output_fh:
                output_fh.write(acfg['convert_header'] + '\n')
                for line in lines:
                    output_fh.write(line)

        cmd = 'ledger -f main.txt convert {}'.format(OUTFILE)
        cmd += ' --input-date-format "{}"'.format(acfg['date_format'])
        cmd += ' --account {}'.format(account)
        cmd += ' {}'.format(acfg['ledger_args'])
        cmd += ' ' # expenses:unkown
        cmd += ' ' # add currcency
        #| sed -e "s/\(^\s\+.*[0-9]\)$/\1  $CURRENCY/g" -e "s/Expenses:Unknown/Ausgaben:Unbekannt/g"
        # cmd += ' | grep H'
        print(cmd)

        # directly call in subshell
        os.system(cmd)
        #os.remove(OUTFILE)

if __name__ == '__main__':
    main(sys.argv)
