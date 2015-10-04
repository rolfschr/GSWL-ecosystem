#!/usr/bin/python

import re
import sys
import os
try:
    import yaml
except ImportError:
    print('Missing yaml dependency. Please install with:')
    print('pip install pyyaml')
    sys.exit(1)

CONFIG_FILE = './bankaccounts.yml'
OUTFILE = '/tmp/out.csv'
LEDGER_FILE = './csv2journal.txt'
SHOW_DIFF = False


def usage():
    s = """
Usage:
    {} <account> <infile>
""".format(__file__)
    print(s)
    sys.exit(1)


def check_env():
    files = [CONFIG_FILE, LEDGER_FILE]
    for f in files:
        if (not os.path.exists(f)):
            print('Cannot find expected file {}'.format(f))
            sys.exit(1)


def ignore_transactions(lines, patterns):
    def match(line, patterns):
        if (patterns is not None):
            for pattern in patterns:
                if re.search(pattern, line):
                    return True
        return False

    ret = []
    ignored = []
    for line in lines:
        if (not match(line, patterns)):
            ret.append(line)
        else:
            ignored.append(line)
    return ret, ignored


def modify_transactions(lines, mods):
    ret = []
    for line in lines:
        if (mods is not None):
            for mod in mods:
                line = re.sub(mod[0], mod[1], line)
        ret.append(line)
    return ret


def main(argv=None):
    check_env()
    if (argv is None or len(argv) < 3):
        usage()
    account = argv[1]
    csv_filename = argv[2]
    f = file(CONFIG_FILE, 'r')
    cfg = yaml.load(f)
    if account not in cfg:
        print("Cannot find accout {} in config file ({}).".
              format(account, CONFIG_FILE))
        sys.exit(1)
    else:
        acfg = cfg[account]
        with open(csv_filename) as csv_fh:
            lines = csv_fh.readlines()
            lines = [re.sub(r'[^\x00-\x7F]+', '_', l) for l in lines]
            lines = lines[int(acfg['ignored_lines']):]
            lines, ignored = \
                ignore_transactions(lines, acfg['ignored_transactions'])
            lines = modify_transactions(lines, acfg['modify_transactions'])
            with open(OUTFILE, "w") as output_fh:
                output_fh.write(acfg['convert_header'] + '\n')
                for line in lines:
                    # print(line)
                    output_fh.write(line)
        if (SHOW_DIFF is True):
            cmd = ''
            cmd += '`which wdiff > /dev/null`'
            cmd += ' && `which colordiff > /dev/null`'
            cmd += ' && echo "; Temporarily converted CSV:"'
            cmd += ' && '
            cmd += ' wdiff -n --no-deleted'
            cmd += ' {} {}'.format(csv_filename, OUTFILE)
            cmd += ' | colordiff 1>&2'
            cmd += '; echo -n "\n\n"'
            # print(cmd)
            os.system(cmd)

        if(len(ignored) > 0):
            print('')
            print('')
            print('; Attention: The following lines were ignored:')
            for line in ignored:
                print('; {}'.format(line.strip()))

        cmd = 'ledger -f {} convert {}'.format(LEDGER_FILE, OUTFILE)
        cmd += ' --input-date-format "{}"'.format(acfg['date_format'])
        cmd += ' --account {}'.format(account)
        cmd += ' --generated'  # pin automated transactions
        cmd += ' {}'.format(acfg['ledger_args'])
        cmd += ' | sed -e "s/\(^\s\+.*\s\+\)\([-0-9\.]\+\)$/\\1{}\\2/g"'.\
            format(acfg['currency'])
        try:
            cmd += ' | sed -e "s/Expenses:Unknown/{}/g"'.\
                format(acfg['expenses_unknown'])
        except:
            pass
        # cmd += ' | grep H'

        # directly call in subshell
        os.system(cmd)
        os.remove(OUTFILE)

if __name__ == '__main__':
    main(sys.argv)
