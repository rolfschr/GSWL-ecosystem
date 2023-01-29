#!/usr/bin/env python3

import re
import sys
from typing import Dict, List, Tuple, Union
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

def get_Account_Config(account_name: str, accounts_config_filename = CONFIG_FILE) -> Dict:
    """
    Finds and returns the account config from the accounts config file (default is bankaccounts.yml)
    """
    account_colon = account_name.replace("___", ":")
    account_underscore = account_colon.replace(":", "___")
    
    with open(CONFIG_FILE, 'r') as f:
        cfg = yaml.load(f, Loader=yaml.FullLoader)
        if account_underscore not in cfg:
            print("Cannot find accout {} in config file ({}).".
                  format(account_colon, CONFIG_FILE))
            print("Did you define the correct account?")
            print("Did you use 3 underscores instead of each colon?")
            sys.exit(1)
        else:
            # Get account config.
            acfg = cfg[account_underscore]
    return acfg

def get_csv_file_lines(csv_filename: str, acfg: str) -> Tuple[List[str], List[Tuple[str, str]], List[str]]:
    """
    Gets csv lines from a file and then performs pre-processing.
    Returns a tuple that is (raw lines, modified lines, ignored lines).
    modified lines is itself a list of tuples, with each entry being (original, modified)
    """

    with open(csv_filename, errors='replace') as csv_fh:
        raw_lines = csv_fh.readlines()

    # pre-processing of csv_lines
    raw_lines = [re.sub(r'[^\x00-\x7F]+', '_', line) for line in raw_lines]
    raw_lines = raw_lines[int(acfg['ignored_header_lines']):]
    raw_lines.insert(0, acfg['convert_header'])
    
    # Nothing is ignored by default.
    ignored_lines: List[str] = []
    if ('ignore_transactions' in acfg):
        raw_lines, ignored_lines = \
        ignore_transactions(raw_lines, acfg['ignore_transactions'])

    # Nothing is modfied by default.
    modified_lines = [(line, line) for line in raw_lines]
    if ('modify_transactions' in acfg):
        raw_lines, modified_lines = \
        modify_transactions(raw_lines, acfg['modify_transactions'])
        
    return raw_lines, modified_lines, ignored_lines

def create_Ledger_Command(tmp_csv_filename: str, tmp_journal_filename: str, acfg: str, account_name: str, ledger_file: str = LEDGER_FILE):
    """
    Creates a string that is the ledger command needed to perform the conversion
    """
    # TODO In Future you would probably be best defining a 'ledger_command' class that uses a "ledger_settings" class object.
    # That way, you would be able to define default ledger settings to be brought in by the ledger settings object, and then
    # you could create multiple ledger commands using the same settings (or slightly different settings for each one).
    cmd = 'ledger -f {} convert {}'.format(ledger_file, tmp_csv_filename)
    cmd += ' --input-date-format "{}"'.format(acfg['date_format'])
    cmd += ' --account "{}"'.format(account_name)
    cmd += ' --generated'  # pin automated transactions
    cmd += ' {}'.format(acfg['ledger_args'])
    cmd += ' | sed -e "s/\(^\s\+.*\s\+\)\([-0-9\.]\+\)$/\\1{}\\2/g"'.\
    format(acfg['currency'].encode('utf8').decode())
    try:
        cmd += ' | sed -e "s/Expenses:Unknown/{}/g"'.\
            format(acfg['expenses_unknown'])
    except:
        pass

    cmd += ' > {}'.format(tmp_journal_filename)
    return cmd

def process_converted_transactions(tmp_journal_filename: str, modified_lines: Tuple[List[str], List[str]]) -> List[str]:
    """
    Performs post-processing on the generated ledger format transactions.
    """
    # For every trannsaction, add the corresponding CSV file line to the
    # generated journal file.
    new_lines = []
    with open(tmp_journal_filename, 'r') as fh:
        i = 0
        for line in fh.readlines():
            new_lines.append(line)
            if (RE_LEDGER_FST_LINE_TRANSACTION.match(line)):
                # Assuming that the transactions in the journal file have
                # the same order as the transactions in the csv file, we
                # can match modified csv lines to the journal's
                # transactions:
                new_lines.append('    ; CSV data:\n')
                new_lines.append('    ; from : {}\n'.
                                 format(modified_lines[i][1].strip()))
                new_lines.append('    ; (raw): {}\n'.
                                 format(modified_lines[i][0].strip()))
                i += 1

    # TODO Add in the possibility to sort by date (now that meta data has been correctly added. Can even limit by date rather than using regex to ignore old transactions.
    return new_lines

def main(argv=None):

    check_env()
    if (argv is None or len(argv) < 3):
        usage()

    account_name = argv[1]
    csv_filename = argv[2]

    acfg = get_Account_Config(account_name, CONFIG_FILE)

    raw_lines, modified_lines, ignored_lines = get_csv_file_lines(csv_filename, acfg)

    # Have kept these from previous - demonstrates the problem of not being modular. We are creating tmp files for no real reason.
    _, tmp_csv_filename = tempfile.mkstemp()

    _, tmp_journal_filename = tempfile.mkstemp()


    # Use ledger to convert the lines to ledger format
    cmd = create_Ledger_Command(tmp_csv_filename, tmp_journal_filename, acfg, account_name, LEDGER_FILE)
    
    # TODO: You should use 'subprocess' command rather than system, and you can then capture stdout rather than saving to a file with the shell
    # Come to think of it, I think ledger has a "-o" option for outputting directly to a file, so that is an option too - but subprocess
    # is better: You can then trigger a stop to the conversion when ledger raises an error - something that isn't trivial with the current setup 
    os.system(cmd)

    new_lines = process_converted_transactions(tmp_journal_filename, modified_lines)


    with open(tmp_journal_filename, 'w') as fh:
        fh.write(''.join(new_lines))

    # Append the list of ignored transactions to the generated journal
    # file. (this can be better done by simply calling 'new_lines.extend(ignored_lines)'
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
