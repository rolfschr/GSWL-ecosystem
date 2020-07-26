#!/usr/bin/env python3
import re
import sys
import os
from pathlib import Path
import tempfile
import logging

ECOSYSTEM_CONFIG_FILE='./eco_config.yml'

#Set up logger to run until logging settings can be loaded from the config file.

logger = logging.getLogger('Convert.py Logger')
logger.setLevel(logging.DEBUG) #Pass all message levels to the handlers

logFormatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

streamHandler = logging.StreamHandler()
streamHandler.setLevel(logging.DEBUG)
streamHandler.setFormatter(logFormatter)

logger.addHandler(streamHandler)

try:
    import yaml
except ImportError:
    logger.critical('Missing yaml dependency. Please install with:\npip3 install yaml')
    sys.exit(1)

f = open(ECOSYSTEM_CONFIG_FILE, 'r')

logger.debug("Loading yaml objects from ecosystem config file")
ecocfg = yaml.load(f, Loader=yaml.FullLoader)

if "logging" not in ecocfg:
    logger.warning(f"Cannot find logging settings in config file: {ECOSYSTEM_CONFIG_FILE}. Using Defaults.")
else:
    # Get config for convert
    logcfg = ecocfg["logging"]
    logger.debug(f"Logging configuration settings loaded as:\n{str(logcfg)}")
    
    #Define the variable to ensure it has correct scope
    logfile = None

    if 'log_file' in logcfg:
        logfile = Path.cwd() / Path(logcfg['log_file'])
        logger.debug(f"The logfile has been set to path: {logfile}")
        if not logfile.exists():
            os.system(f"touch {logfile}")
        logger.debug(f"Logfile {logfile} exists and is ready for logs")
    else:
        logger.debug("No log file found in ecosystem config")
        logfile = None

    if 'log_level' in logcfg:
        config_loglevel = logcfg['log_level']
        valid_loglevels = ("CRIT", "ERR", "WARN", "INFO", "DEBUG")
        if config_loglevel not in valid_loglevels:
            logger.error(f"Invalid log level, {config_loglevel}, provided in ecosystem config file {ECOSYSTEM_CONFIG_FILE}. Ignoring the specified log level.")
            config_loglevel = logging.INFO
        else:
            logger.debug(f"As per {ECOSYSTEM_CONFIG_FILE}, setting log level to {config_loglevel}")
            config_loglevel = getattr(logging, f"{config_loglevel}");
        
    logger.debug(f"Create logfile (if log file has been specified)") 
    # use try and except since most of the time the log_file is not defined
    try:
        logger.debug(f"The logfile ({logfile}) is now being tested to ensure it exists and is valid") 
        if (not logfile is None) and (logfile != ''):
            writemode = "w"
            if "write_mode" in logcfg:
                valid_writemodes = ('a', 'w')
                if logcfg["write_mode"] in valid_writemodes:
                    writemode = logcfg["write_mode"]
                else:
                    writemode = "w" #Write over old log by default
            logger.debug(f"Creating file handler for logging with mode '{writemode}' in file {logfile}")
            fileHandler = logging.FileHandler(logfile,mode=f'{writemode}')
            fileHandler.setLevel(config_loglevel)
            fileHandler.setFormatter(logFormatter)
            logger.addHandler(fileHandler)
            logger.debug(f"Completed creating the file handler for logging using file {logfile} and mode '{writemode}'")
        
    except NameError as e:
        logger.debug(f"Whilst defining log file had the exception: \n{e}")
        logger.debug("Log file not defined. Continuing without a log file.")

    logger.debug("Setting the log level for the stream handler")
    streamHandler.setLevel(config_loglevel)
logger.debug("Completed setting up logging for convert.py")

ACCOUNTS_CONFIG_FILE = './bankaccounts.yml'
LEDGER_FILE = './csv2journal.txt'

RE_LEDGER_FST_LINE_TRANSACTION = re.compile('^[0-9]+')
SHOW_DIFF = False


def usage():
    logger.debug("Starting function 'usage', that will print usage and quit.")
    s = f"""
Usage:
    {__file__} <account> <infile>
"""
    logger.critical(s)
    sys.exit(1)


def check_env():
    """
    Checks to ensure important files are present in the correct place.
    """
    logger.debug("Commenced function 'check_env'")
    files = [ACCOUNTS_CONFIG_FILE, LEDGER_FILE]
    for f in files:
        logger.debug(f"Checking file {f}")
        if (not os.path.exists(f)):
            logger.critical(f'Cannot find expected file {f}')
            sys.exit(1)
        logger.debug(f"file {f} has been found")
    logger.debug("Completed function 'check_env'")

def ignore_transactions(lines, patterns):
    """
    Returns a) a new list of lines exluding some of the original lines and b) a
    list of excluded lines.
    """
    logger.debug(f"Starting function 'ignore_transactions' with \nlines:\n{str(lines)}\npatterns:\n{str(patterns)}\n")

    def match(line, patterns):
        logger.debug(f"Attempting to match patterns to line: {line}")
        if (patterns is not None):
            for pattern in patterns:
                logger.debug(f"Trying pattern: {pattern}")
                if re.search(pattern, line):
                    logger.debug(f"Pattern {pattern} matched for line {line}")
                    return True
        logger.debug(f"No matches found for line: {line}")
        return False

    new_lines = []
    ignored_lines = []
    for line in lines:
        logger.debug(f"Looking for ignore transaction rule for line: {line}")
        if (not match(line, patterns)):
            logger.debug("No ignore rule present for this line, so adding it to 'new_lines' list")
            new_lines.append(line)
        else:
            logger.debug("Ignore rule was present for this line, so adding it to 'ignore_lines' list")
            ignored_lines.append(line)
    logger.debug(f"Completed 'ignore_transactions' function.\nIgnored lines are: \n{str(ignored_lines)}\nUsable lines are:\n{str(new_lines)}\n")
    return new_lines, ignored_lines


def modify_transactions(lines, mods):
    """
    Returns a) a new list of modified lines and b) a list of tuples of
    (original, modified) lines.
    """
    logger.debug(f"Starting 'modify_transactions' function with lines \n{str(lines)}\nModifications are {str(mods)}")
    new_lines = []
    modified_lines = []
    for line in lines:
        logger.debug(f"Searching line for modifications: {line}")
        raw = line
        if (mods is not None):
            for mod in mods:
                logger.debug(f"Trying modification {mod}")
                line = re.sub(mod[0], mod[1], line)
                logger.debug(f"After modification, line is: {line}")
        new_lines.append(line)
        modified_lines.append((raw, line))
    logger.debug(f"Completed 'modify_transactions' function with\nnew_lines:\n{str(new_lines)}\nmodified_lines:\n{str(modified_lines)}\n")
    return new_lines, modified_lines


def main(argv=None):
    logger.debug("Commencing main function and calling 'check_env' function")
    check_env()
    if (argv is None or len(argv) < 3 or argv[1] == '' or argv[2] == ''):
        usage()
    account = argv[1]
    account_colon = account.replace("___", ":")
    account_underscore = account_colon.replace(":", "___")
    csv_filename = argv[2]

    if not os.path.isfile(csv_filename):
        logger.critical(f"File does not exist: {csv_filename}.\nExiting.")
        sys.exit(1)
    logger.debug(f"Correct number of arguments passed.\naccount: {account}\ncsv_filename: {csv_filename}\n")
    logger.debug(f"Opening config file {ACCOUNTS_CONFIG_FILE}")

    f = open(ACCOUNTS_CONFIG_FILE, 'r')
    cfg = yaml.load(f, Loader=yaml.FullLoader)
    logger.debug(f"Loaded yaml objects from config file:\n{str(cfg)}")
    if account_underscore not in cfg:
        logger.critical(f"Cannot find account '{account_colon}' in config file ({ACCOUNTS_CONFIG_FILE})\nDid you define the correct account?\nDid you use 3 underscores instead of each colon?")
        sys.exit(1)
    else:
        logger.debug("Account was found account in config file. Pulling out config information for this account")
        # Get account config.
        acfg = cfg[account_underscore]
        logger.debug(f"Account configuration settings loaded as:\n{str(acfg)}")

        logger.debug("Creating temp csv file and populating its lines from old")
        # Modify CSV file (delete/modify lines, add header, ...).
        _, tmp_csv_filename = tempfile.mkstemp()
        with open(csv_filename, errors='replace') as csv_fh:
            lines = csv_fh.readlines()
            logger.debug(f"File {csv_filename} opened to create the lines for the ledger call.")
            lines = [re.sub(r'[^\x00-\x7F]+', '_', l) for l in lines]
            lines = lines[int(acfg['ignored_header_lines']):]

            # Nothing is ignored by default.
            ignored_lines = []
            if ('ignore_transactions' in acfg):
                logger.debug("Processing transactions to be ignored")
                lines, ignored_lines = \
                    ignore_transactions(lines, acfg['ignore_transactions'])
            logger.debug("Completed processing transactions to be ignored")
            logger.debug("Processing transactions to be modified")
            # Nothing is modfied by default.
            modified_lines = [(line, line) for line in lines]
            if ('modify_transactions' in acfg):
                logger.debug("Modification variables are present. Calling 'modify_transactions' function")
                lines, modified_lines = \
                    modify_transactions(lines, acfg['modify_transactions'])
            logger.debug("Completed modifying csv lines. Creating temporary csv file with new lines")

            with open(tmp_csv_filename, "w") as output_fh:
                logger.debug(f"created file {tmp_csv_filename} for temporary csv file")
                logger.debug(f"Writing new header to tmp csv file: {acfg['convert_header']}")
                output_fh.write(acfg['convert_header'] + '\n')
                for line in lines:
                    logger.debug(f"Adding to tmp csv file the line: {line}")
                    output_fh.write(line)

        logger.debug("Creating the ledger convert command")
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
            logger.debug("Couldn't add 'expenses:unknown' part to cmd")
            pass
        fd, tmp_journal_filename = tempfile.mkstemp()
        logger.debug(f"Creating temp journal file {tmp_journal_filename}")
        os.close(fd)
        cmd += f' > {tmp_journal_filename}'

        logger.debug(f"Completed creating the ledger convert command:\n{cmd}\n")
        logger.debug("Calling the ledger convert command to create the temp journal")
        os.system(cmd)
        
        # For every transaction, add the corresponding CSV file line to the
        # generated journal file.
        logger.debug("Adding the CSV lines to the generated transactions")
        new_lines = []
        with open(tmp_journal_filename, 'r') as fh:
            i = 0
            for line in fh.readlines():
                logger.debug(f"Adding to the new lines the line: {line}")
                new_lines.append(line)
                if (RE_LEDGER_FST_LINE_TRANSACTION.match(line)):
                    logger.debug(f"Line just added was a first transaction line: {line}")
                    # Assuming that the transactions in the journal file have
                    # the same order as the transactions in the csv file, we
                    # can match modified csv lines to the journal's
                    # transactions:
                    new_lines.append('    ; CSV data:\n')
                    new_lines.append(f'    ; from : {modified_lines[i][1].strip()}\n')
                    new_lines.append(f'    ; (raw): {modified_lines[i][0]}\n')
                    i += 1
        logger.debug("Completed adding CSV lines. Opening tmp journal for writing the lines")
        with open(tmp_journal_filename, 'w') as fh:
            fh.write(''.join(new_lines))

        # Append the list of ignored transactions to the generated journal
        # file.
        if(len(ignored_lines) > 0):
            logger.debug("Adding ignored lines to the tmp journal")
            with open(tmp_journal_filename, 'a+') as fh:
                fh.write('\n\n')
                fh.write(f'; Attention: The following lines from {csv_filename} were ignored:\n')
                for line in ignored_lines:
                    logger.debug(f"Adding ignored line: {line}")
                    fh.write(f"; {line.strip()}\n")
        
        # Print to stdout for later use.
        os.system(f'cat {tmp_journal_filename}')

        # Cleanup.
        logger.debug(f"Cleaning up by removing tmp files: {tmp_csv_filename}, {tmp_journal_filename}")
        os.remove(tmp_csv_filename)
        os.remove(tmp_journal_filename)

if __name__ == '__main__':
    logger.debug("Calling main function")
    main(sys.argv)
    logger.debug("Script completed")
