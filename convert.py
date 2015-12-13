#!/usr/bin/python

import re
import sys
import os
import tempfile
try:
    import yaml
except ImportError:
    print('Missing yaml dependency. Please install with:')
    print('pip install pyyaml')
    sys.exit(1)

CONFIG_FILE = './bankaccounts.yml'
LEDGER_FILE = './csv2journal.txt'
RE_LEDGER_FST_LINE_TRANSACTION = re.compile('^[0-9]+')
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
    """
    Returns a) a new list of lines exluding some of the original lines and b) a
    list of excluded lines.
    """
    def match(line, patterns):
        if (patterns is not None):
            for pattern in patterns:
                if re.search(pattern, line):
                    return True
        return False

    new_lines = []
    ignored_lines = []
    for line in lines:
        if (not match(line, patterns)):
            new_lines.append(line)
        else:
            ignored_lines.append(line)
    return new_lines, ignored_lines


def modify_transactions(lines, mods):
    """
    Returns a) a new list of modified lines and b) a list of tuples of
    (original, modified) lines.
    """
    new_lines = []
    modified_lines = []
    for line in lines:
        raw = line
        if (mods is not None):
            for mod in mods:
                line = re.sub(mod[0], mod[1], line)
        new_lines.append(line)
        modified_lines.append((raw, line))
    return new_lines, modified_lines


def main(argv=None):
    check_env()
    if (argv is None or len(argv) < 3):
        usage()
    account = argv[1]
    account_colon = account.replace("___", ":")
    account_underscore = account_colon.replace(":", "___")
    csv_filename = argv[2]
    f = file(CONFIG_FILE, 'r')
    cfg = yaml.load(f)
    if account_underscore not in cfg:
        print("Cannot find accout {} in config file ({}).".
              format(account_colon, CONFIG_FILE))
        print("Did you define the correct account?")
        print("Did you use 3 underscores instead of each colon?")
        sys.exit(1)
    else:
        # Get account config.
        acfg = cfg[account_underscore]

        # Modify CSV file (delete/modify lines, add header, ...).
        _, tmp_csv_filename = tempfile.mkstemp()
        with open(csv_filename) as csv_fh:
            lines = csv_fh.readlines()
            lines = [re.sub(r'[^\x00-\x7F]+', '_', l) for l in lines]
            lines = lines[int(acfg['ignored_header_lines']):]

            # Nothing is ignored by default.
            ignored_lines = []
            if ('ignore_transactions' in acfg):
                lines, ignored_lines = \
                    ignore_transactions(lines, acfg['ignore_transactions'])

            # Nothing is modfied by default.
            modified_lines = [(line, line) for line in lines]
            if ('modify_transactions' in acfg):
                lines, modified_lines = \
                    modify_transactions(lines, acfg['modify_transactions'])

            with open(tmp_csv_filename, "w") as output_fh:
                output_fh.write(acfg['convert_header'] + '\n')
                for line in lines:
                    # print(line)
                    output_fh.write(line)

        # Use Ledger to convert the modified CSV file.
        cmd = 'ledger -f {} convert {}'.format(LEDGER_FILE, tmp_csv_filename)
        cmd += ' --input-date-format "{}"'.format(acfg['date_format'])
        cmd += ' --account {}'.format(account_colon)
        cmd += ' --generated'  # pin automated transactions
        cmd += ' {}'.format(acfg['ledger_args'])
        cmd += ' | sed -e "s/\(^\s\+.*\s\+\)\([-0-9\.]\+\)$/\\1{}\\2/g"'.\
            format(acfg['currency'])
        try:
            cmd += ' | sed -e "s/Expenses:Unknown/{}/g"'.\
                format(acfg['expenses_unknown'])
        except:
            pass
        fd, tmp_journal_filename = tempfile.mkstemp()
        os.close(fd)
        cmd += ' > {}'.format(tmp_journal_filename)
        os.system(cmd)

        # For every trannsaction, add the correspinding CSV file line to the
        # generated journal file.
        new_lines = []
        with open(tmp_journal_filename, 'a+') as fh:
            i = 0
            for line in fh.readlines():
                new_lines.append(line)
                if (RE_LEDGER_FST_LINE_TRANSACTION.match(line)):
                    # Assuming that the transactions in the journal file have
                    # the same order as the transactions in the csv file, we
                    # can match modified csv lines to the journal's
                    # transactions:
                    new_lines.append('    ; CSV data:\n')
                    new_lines.append('    ; from : {}'.
                                     format(modified_lines[i][1]))
                    new_lines.append('    ; (raw): {}'.
                                     format(modified_lines[i][0]))
                    i += 1
        with open(tmp_journal_filename, 'w') as fh:
            fh.write(''.join(new_lines))

        # Append the list of ignored transactions to the generated journal
        # file.
        if(len(ignored_lines) > 0):
            with open(tmp_journal_filename, 'a+') as fh:
                fh.write('\n\n')
                fh.write('; Attention: The following lines from ')
                fh.write('{} were ignored:\n'.format(csv_filename))
                for line in ignored_lines:
                    fh.write('; {}\n'.format(line.strip()))

        # Print to stdout for later use.
        os.system('cat {}'.format(tmp_journal_filename))

        # Cleanup.
        os.remove(tmp_csv_filename)
        os.remove(tmp_journal_filename)

if __name__ == '__main__':
    main(sys.argv)
