#!/usr/bin/env python3
"""
Module for converting csv files into ledger transactions.
"""

import os
import re
import subprocess
import sys
import tempfile
from typing import Dict, List, Tuple

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
    """Function to inform the user how to use this module"""
    s = """
Usage:
    {} <account> <infile>
""".format(__file__)
    print(s)
    sys.exit(1)


def check_env():
    """Function to check for the necessary files in the environment"""
    files = [CONFIG_FILE, LEDGER_FILE]
    for f in files:
        if not os.path.exists(f):
            print('Cannot find expected file {}'.format(f))
            sys.exit(1)


def ignore_transactions(lines, patterns):
    """
    Returns a) a new list of lines exluding some of the original lines and b) a
    list of excluded lines.
    """
    def match(line, patterns):
        if patterns is not None:
            for pattern in patterns:
                if re.search(pattern, line):
                    return True
        return False

    new_lines = []
    ignored_lines = []
    for line in lines:
        if not match(line, patterns):
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
        if mods is not None:
            for mod in mods:
                line = re.sub(mod[0], mod[1], line)
        new_lines.append(line)
        modified_lines.append((raw, line))
    return new_lines, modified_lines


# TODO This should really use dependency injection to get the accounts dictionary... Ie pass in an object or function that can return the config
# That way you could change it from a yaml file to any other type of file (or data source) by simply passing in a different function.
def get_Accounts_Config_Dict(accounts_config_filename: str = CONFIG_FILE) -> Dict:
    """
    Gets the contents of the yaml config file as a dictionary
    """
    with open(accounts_config_filename, 'r') as f:
        accounts_config = yaml.load(f, Loader=yaml.FullLoader)
    return accounts_config


def get_Account_Config(account_name: str, accounts_config: Dict) -> Dict:
    """
    Finds and returns the account config from the accounts config dictionary.
    """
    # TODO: in future it may be beneficial to have an 'accounts config' object that can give a list of accounts, auto detect accounts in
    # the config file, and perhaps provide a list of known settings to users.... Probably too much effort though.
    account_underscore = account_name.replace(":", "___")
    if account_underscore not in accounts_config:
        print("Cannot find account {} in config file.".
              format(account_name))
        print("Did you define the correct account?")
        print("Did you use 3 underscores instead of each colon?")
        sys.exit(1)
    else:
        # Get account config.
        account_config = accounts_config[account_underscore]
    return account_config


def get_Lines_From_File(file_name: str) -> List[str]:
    """
    Function to get the lines from a file in a List
    """
    with open(file_name, errors='replace') as f:
        file_lines = f.readlines()

    return file_lines


def process_csv_lines(lines: List[str], account_config: Dict) -> Tuple[List[str], List[str], List[str]]:
    """
    Function to process the csv lines before they are used for the conversion.
    In future I will be looking to make this into calling a chain of functions that are defined in config files (ie customisable)
    Returns a tuple containing three lists: (original_lines, modified_lines, ignored_lines)
    """

    # pre-processing of csv_lines
    lines = [re.sub(r'[^\x00-\x7F]+', '_', line) for line in lines]
    lines = lines[int(account_config['ignored_header_lines']):]
    lines.insert(0, account_config['convert_header'])

    # Nothing is ignored by default.
    ignored_lines: List[str] = []
    if 'ignore_transactions' in account_config:
        lines, ignored_lines = \
            ignore_transactions(lines, account_config['ignore_transactions'])

    # Nothing is modfied by default.
    if 'modify_transactions' in account_config:
        _, (lines, modified_lines) = \
            modify_transactions(lines, account_config['modify_transactions'])

    return lines, modified_lines, ignored_lines


def get_Processed_Csv_Lines(csv_filename: str,
                            account_config: Dict) -> Tuple[List[str], List[str], List[str]]:
    """
    Gets csv lines from a file and then performs pre-processing.
    Returns a tuple that is (original lines, modified lines, ignored lines).
    """
    original_lines = get_Lines_From_File(csv_filename)

    # NOTE: Modified lines variable contains the raw lines, doesn't it? So you probably don't need to save and return raw lines separately
    original_lines, modified_lines, ignored_lines = process_csv_lines(original_lines, account_config)

    return original_lines, modified_lines, ignored_lines


def create_Ledger_Convert_Command(csv_filename: str,
                                  tmp_journal_filename: str,
                                  account_name: str,
                                  additional_ledger_args: str = '',
                                  input_date_format: str = '%Y/%m/%d',
                                  expenses_unknown: str = "Expenses:Unknown",
                                  conversion_ledger_file: str = LEDGER_FILE,
                                  currency: str = "$") -> str:
    """
    Creates a string that is the ledger command needed to perform the conversion
    """
    # TODO In Future you would probably be best defining a 'ledger_command' class that uses a "ledger_settings" class object.
    # That way, you would be able to define default ledger settings to be brought in by the ledger settings object, and then
    # you could create multiple different ledger commands using the same settings (or slightly different settings for each one).
    # Eg multiple calls to 'csvconvert' with only the csv file and account name changed each time.
    # NOTE to self: This code looks messy... the subprocess module (just like 'system' module) can take a list of strings
    # that represent the command to be called. It may be easier/neater to put all these string components into a list rather than
    # building the string yourself.
    cmd = 'ledger -f "{}" convert "{}"'.format(conversion_ledger_file, csv_filename)
    cmd += ' --input-date-format "{}"'.format(input_date_format)
    cmd += ' --account "{}"'.format(account_name)
    cmd += ' --generated'  # pin automated transactions
    cmd += ' {}'.format(additional_ledger_args)

    # TODO: Now that I'm using python so much, I should change these sed calls to be python regex substitutions...
    cmd += ' | sed -e "s/\(^\s\+.*\s\+\)\([-0-9\.]\+\)$/\\1{}\\2/g"'.\
        format(currency.encode('utf8').decode())  # noqa: W605
    try:
        cmd += ' | sed -e "s/Expenses:Unknown/{}/g"'.\
            format(expenses_unknown)
    except KeyError:
        pass

    cmd += ' > {}'.format(tmp_journal_filename)
    return cmd


def create_Ledger_Convert_Command_From_Config(csv_filename: str,  # pylint: disable=unused-argument
                                              tmp_journal_filename: str,  # pylint: disable=unused-argument
                                              account_name: str,  # pylint: disable=unused-argument
                                              account_config: Dict,
                                              conversion_ledger_file: str) -> str:  # pylint: disable=unused-argument
    """
    Function to pull the necessary variables out of the config dictionary and create the ledger convert command
    """

    variables_required = ['account_name',
                          'csv_filename',
                          'conversion_ledger_file',
                          'tmp_journal_filename',
                          'currency',
                          'additional_ledger_args',
                          'input_date_format',
                          'expenses_unknown']

    # use variables passed into this function first (locals), but variables from the account config otherwise.
    # If neither has the value, it shouldn't be in the dictionary so that the default of the function being called is preserved
    local_vars = locals()
    convert_dictionary = {key: local_vars.get(key, account_config.get(key, None))
                          for key in variables_required
                          if key in local_vars or key in account_config}

    return create_Ledger_Convert_Command(**convert_dictionary)


def process_Converted_Transactions(transaction_lines: List[str],
                                   original_lines: List[str],
                                   modified_lines: List[str],
                                   ignored_lines: List[str]) -> List[str]:
    """
    Performs post-processing on the generated ledger format transactions.
    Returns the final journal lines from the conversion as a list of strings.
    """
    # For every trannsaction, add the corresponding CSV file line to the
    # generated journal file.
    new_lines = []
    i = 0
    for line in transaction_lines:
        new_lines.append(line)
        if RE_LEDGER_FST_LINE_TRANSACTION.match(line):
            # Assuming that the transactions in the journal file have
            # the same order as the transactions in the csv file, we
            # can match modified csv lines to the journal's
            # transactions:
            new_lines.append('    ; CSV data:\n')
            new_lines.append('    ; from : {}\n'.
                             format(modified_lines[i].strip()))
            new_lines.append('    ; (raw): {}\n'.
                             format(original_lines[i].strip()))
            i += 1

    # Append the list of ignored transactions to the converted transaction lines
    if len(ignored_lines) > 0:
        new_lines.append('')
        new_lines.append('; Attention: The following lines were ignored:')
        new_lines.extend(ignored_lines)

    # TODO Add in the possibility to sort by date (now that meta data has been correctly (and fully)added.
    # TODO We can even limit by date rather than using regex to ignore old transactions.

    return new_lines


def main(argv=None):
    """Main function of the module"""
    check_env()
    if (argv is None or len(argv) < 3):
        usage()

    account_name = argv[1]
    csv_filename = argv[2]

    accounts_config = get_Accounts_Config_Dict(CONFIG_FILE)

    account_config = get_Account_Config(account_name, accounts_config)

    original_lines, modified_lines, ignored_lines = get_Processed_Csv_Lines(csv_filename, account_config)

    _, tmp_csv_filename = tempfile.mkstemp()

    _, tmp_journal_filename = tempfile.mkstemp()

    # TODO Would like to save this to the tmp folder in due course to make it easier for people to see what the processed csv becomes
    with open(tmp_csv_filename, 'w') as f:
        f.write('\n'.join([line for _, line in modified_lines]))

    # Use ledger to convert the lines to ledger format
    cmd = create_Ledger_Convert_Command_From_Config(tmp_csv_filename, tmp_journal_filename, account_name, account_config, LEDGER_FILE)

    # Run the ledger command
    try:
        process_result = subprocess.run(cmd, capture_output=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Calling the ledger command {cmd} resulted in an error:\n{e}.\nThe stderr pipe text is:\n{process_result.stderr}")

    converted_lines = process_result.stdout.split('\n')
    converted_lines = process_Converted_Transactions(converted_lines, original_lines, modified_lines, ignored_lines)

    # Print to stdout for later use.
    print('\n'.join(converted_lines))

    # TODO This script should really save the final converted output to a file, rather than relying on redirect from standard out.

    # Cleanup.
    os.remove(tmp_csv_filename)
    os.remove(tmp_journal_filename)


if __name__ == '__main__':
    main(sys.argv)
