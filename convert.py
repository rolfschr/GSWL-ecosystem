#!/usr/bin/env python3
import logging
import os
import re
import sys
import tempfile

level = os.getenv('GSWL_ECOSYSTEM__LOG_LEVEL', 'INFO')
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=level)

try:
    import yaml
except ImportError:
    logging.critical("Missing yaml dependency. Please install PyYAML.")
    sys.exit(1)

CONFIG_FILE = './bankaccounts.yml'
LEDGER_FILE = './csv2journal.txt'
RE_LEDGER_FST_LINE_TRANSACTION = re.compile('^[0-9]+')


def usage():
    logging.debug("Begin usage()")
    s = f"""
Usage:
    {__file__} <account> <infile>
"""
    logging.critical(s)
    sys.exit(1)


def check_env():
    """
    Checks to ensure important files are present in the correct place.
    """
    logging.debug("Begin check_env()")
    files = [CONFIG_FILE, LEDGER_FILE]
    for f in files:
        logging.debug(f"Checking file {f}")
        if (not os.path.exists(f)):
            logging.critical(f"Cannot find expected file {f}")
            sys.exit(1)
        logging.debug(f"file {f} has been found")
    logging.debug("End check_env()")


def ignore_transactions(lines, patterns):
    """
    Returns a) a new list of lines exluding some of the original lines and b) a
    list of excluded lines.
    """
    logging.debug(f"Begin ignore_transactions() with \nlines:\n{str(lines)}\npatterns:\n{str(patterns)}\n")

    def match(line, patterns):
        logging.debug(f"Attempting to match patterns to line: {line}.")
        if (patterns is not None):
            for pattern in patterns:
                logging.debug(f"Trying pattern: {pattern}.")
                if re.search(pattern, line):
                    logging.debug(f"Pattern {pattern} matched for line {line}.")
                    return True
        logging.debug(f"No matches found for line: {line}")
        return False

    new_lines = []
    ignored_lines = []
    for line in lines:
        logging.debug(f"Looking for ignore transaction rule for line: {line}")
        if (not match(line, patterns)):
            logging.debug("No ignore rule present for this line, so adding it to 'new_lines' list.")
            new_lines.append(line)
        else:
            logging.debug("Ignore rule was present for this line, so adding it to 'ignore_lines' list.")
            ignored_lines.append(line)
    logging.debug(f"End ignore_transactions()\nIgnored lines are: \n{str(ignored_lines)}\nUsable lines are:\n{str(new_lines)}")
    return new_lines, ignored_lines


def modify_transactions(lines, mods):
    """
    Returns a) a new list of modified lines and b) a list of tuples of
    (original, modified) lines.
    """
    logging.debug(f"Begin modify_transactions() with lines \n{str(lines)}\nModifications are {str(mods)}")
    new_lines = []
    modified_lines = []
    for line in lines:
        logging.debug(f"Searching line for modifications: {line}.")
        raw = line
        if (mods is not None):
            for mod in mods:
                logging.debug(f"Trying modification {mod}.")
                line = re.sub(mod[0], mod[1], line)
                logging.debug(f"After modification, line is: {line}.")
        new_lines.append(line)
        modified_lines.append((raw, line))
    logging.debug(f"End modify_transactions() with\nnew_lines:\n{str(new_lines)}\nmodified_lines:\n{str(modified_lines)}")
    return new_lines, modified_lines


def main(argv=None):
    logging.debug("Begin main()")
    check_env()
    if (argv is None or len(argv) < 3 or argv[1] == '' or argv[2] == ''):
        usage()
    account = argv[1]
    account_colon = account.replace("___", ":")
    account_underscore = account_colon.replace(":", "___")
    csv_filename = argv[2]

    if not os.path.isfile(csv_filename):
        logging.critical(f"File does not exist: {csv_filename}.\nExiting.")
        sys.exit(1)
    logging.debug(f"Correct number of arguments passed.\naccount: {account}\ncsv_filename: {csv_filename}.")
    logging.debug(f"Opening config file {CONFIG_FILE}.")

    fh = open(CONFIG_FILE, 'r')
    cfg = yaml.load(fh, Loader=yaml.FullLoader)
    logging.debug(f"Loaded yaml objects from config file:\n{str(cfg)}")
    if account_underscore not in cfg:
        logging.critical(f"Cannot find account '{account_colon}' in config file ({CONFIG_FILE})\nDid you define the correct account?\nDid you use 3 underscores instead of each colon?")
        sys.exit(1)
    else:
        logging.debug("Account was found account in config file. Pulling out config information for this account.")
        # Get account config.
        acfg = cfg[account_underscore]
        logging.debug(f"Account configuration settings loaded as:\n{str(acfg)}")

        logging.debug("Creating temp csv file and populating its lines from old.")
        # Modify CSV file (delete/modify lines, add header, ...).
        _, tmp_csv_filename = tempfile.mkstemp()
        with open(csv_filename, errors='replace') as csv_fh:
            lines = csv_fh.readlines()
            logging.debug(f"File {csv_filename} opened to create the lines for the ledger call.")
            lines = [re.sub(r'[^\x00-\x7F]+', '_', l) for l in lines]
            lines = lines[int(acfg['ignored_header_lines']):]

            # Nothing is ignored by default.
            ignored_lines = []
            if ('ignore_transactions' in acfg):
                logging.debug("Processing transactions to be ignored.")
                lines, ignored_lines = \
                    ignore_transactions(lines, acfg['ignore_transactions'])
            logging.debug("Completed processing transactions to be ignored")
            logging.debug("Processing transactions to be modified")
            # Nothing is modfied by default.
            modified_lines = [(line, line) for line in lines]
            if ('modify_transactions' in acfg):
                logging.debug("Modification variables are present. Calling modify_transactions()")
                lines, modified_lines = \
                    modify_transactions(lines, acfg['modify_transactions'])
            logging.debug("Completed modifying csv lines. Creating temporary csv file with new lines.")

            with open(tmp_csv_filename, "w") as output_fh:
                logging.debug(f"created file {tmp_csv_filename} for temporary csv file.")
                logging.debug(f"Writing new header to tmp csv file: {acfg['convert_header']}.")
                output_fh.write(acfg['convert_header'] + '\n')
                for line in lines:
                    logging.debug(f"Adding to tmp csv file the line: {line}")
                    output_fh.write(line)

        logging.debug("Creating the ledger convert command.")
        # Use Ledger to convert the modified CSV file.
        cmd = f"ledger -f {LEDGER_FILE} convert {tmp_csv_filename}"
        cmd += f" --input-date-format {acfg['date_format']}"
        cmd += f" --account {account_colon}"
        cmd += f" --generated"  # pin automated transactions
        cmd += f" {acfg['ledger_args']}"
        cmd += f" | sed -e \"s/\(^\s\+.*\s\+\)\([-0-9\.]\+\)$/\\1{acfg['currency'].encode('utf8').decode()}\\2/g\""

        try:
            cmd += f" | sed -e \"s/Expenses:Unknown/{acfg['expenses_unknown']}/g\""
        except:
            logging.debug("Couldn't add 'expenses:unknown' part to cmd.")
            pass
        fd, tmp_journal_filename = tempfile.mkstemp()
        logging.debug(f"Creating temp journal file {tmp_journal_filename}")
        os.close(fd)
        cmd += f' > {tmp_journal_filename}'

        logging.debug(f"Completed creating the ledger convert command:\n{cmd}\n")
        logging.debug("Calling the ledger convert command to create the temp journal")
        os.system(cmd)

        # For every transaction, add the corresponding CSV file line to the
        # generated journal file.
        logging.debug("Adding the CSV lines to the generated transactions.")
        new_lines = []
        with open(tmp_journal_filename, 'r') as fh:
            i = 0
            for line in fh.readlines():
                logging.debug(f"Adding to the new lines the line: {line}")
                new_lines.append(line)
                if (RE_LEDGER_FST_LINE_TRANSACTION.match(line)):
                    logging.debug(f"Line just added was a first transaction line: {line}")
                    # Assuming that the transactions in the journal file have
                    # the same order as the transactions in the csv file, we
                    # can match modified csv lines to the journal's
                    # transactions:
                    new_lines.append(f'    ; CSV data:\n')
                    new_lines.append(f'    ; from : {modified_lines[i][1].strip()}\n')
                    new_lines.append(f'    ; (raw): {modified_lines[i][0].strip()}\n')
                    i += 1
        logging.debug("Completed adding CSV lines. Opening tmp journal for writing the lines.")
        with open(tmp_journal_filename, 'w') as fh:
            fh.write(''.join(new_lines))

        # Append the list of ignored transactions to the generated journal
        # file.
        if(len(ignored_lines) > 0):
            logging.debug("Adding ignored lines to the tmp journal.")
            with open(tmp_journal_filename, 'a+') as fh:
                fh.write('\n\n')
                fh.write(f'; Attention: The following lines from {csv_filename} were ignored:\n')
                for line in ignored_lines:
                    logging.debug(f"Adding ignored line: {line}")
                    fh.write(f"; {line.strip()}\n")

        # Print to stdout for later use.
        os.system(f'cat {tmp_journal_filename}')

        # Cleanup.
        logging.debug(f"Cleaning up by removing tmp files: {tmp_csv_filename}, {tmp_journal_filename}.")
        os.remove(tmp_csv_filename)
        os.remove(tmp_journal_filename)
        logging.debug("End main().")


if __name__ == '__main__':
    main(sys.argv)
