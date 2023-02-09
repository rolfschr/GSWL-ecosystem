#!/usr/bin/env python3
"""
Module for converting csv files into ledger transactions.
"""

import os
import re
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Tuple

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


def save_Lines_To_File(file_name: str, lines: List[str]) -> None:
    """
    Simple function to write lines to a file
    """
    with open(file_name, 'w') as f:
        f.write('\n'.join(lines))


def get_Lines_From_File(file_name: str) -> List[str]:
    """
    Function to get the lines from a file in a List
    """
    with open(file_name, errors='replace') as f:
        file_lines = f.readlines()

    return file_lines


# TODO For pre and post processing (and perhaps the conversion itself), we want to have the definitions of which functions to call (and in
# what order) listed in a file. So the class/function would need to read the file, call the function names with the appropriate input
# variables. We can examine python functions to see which variables are present, or you can unpack a dictionary into every function
# and have each function only use (and update) the variables it needs. Don't really like either option - a bit messy
# Another messyish idea would be the file that stores the function names also includes the variables that function needs and returns.

def replace_non_ascii_chars(lines: List[str]) -> List[str]:
    """
    Preprocessing function to replace non-ascii characters with an underscore
    """
    # NOTE Which is more efficient, list compresssion like this or using 'map' function
    return [re.sub(r'[^\x00-\x7F]+', '_', line) for line in lines]


def fix_csv_header(lines: List[str], ignore_header_lines: int = 0, replacement_header: str = None) -> List[str]:
    """
    Function to remove a number of header lines from csv lines then add a new header
    """
    lines = lines[ignore_header_lines:]

    if replacement_header:
        lines.insert(0, replacement_header)

    return lines


def process_csv_lines(lines: List[str], account_config: Dict) -> Tuple[List[str], List[str], List[str]]:
    """
    Function to process the csv lines before they are used for the conversion.
    In future I will be looking to make this into calling a chain of functions that are defined in config files (ie customisable)
    Hence why I am refactoring everything in this function so that it can be done with a single function call.
    Returns a tuple containing three lists: (original_lines, modified_lines, ignored_lines)
    """

    # pre-processing of csv_lines
    new_lines = replace_non_ascii_chars(lines)
    new_lines = fix_csv_header(new_lines, int(account_config.get('ignored_header_lines', 0)), account_config.get('convert_header', None))

    # Nothing is ignored by default.

    # TODO Commented this code out to confirm that single liner operates correctly. Remove old code once you have tested this thoroughly
    # ignored_lines: List[str] = []
    # if 'ignore_transactions' in account_config:
    #   lines, ignored_lines = \
    #        ignore_transactions(lines, account_config['ignore_transactions'])

    # if there is no 'ignore_transactions' in the dict, the ignore transaction functions should just return (lines, [])
    new_lines, ignored_lines = ignore_transactions(new_lines, account_config.get('ignore_transactions', None))

    # Again, remove this when you have confirmed the one liner operate correctly.
    # Nothing is modfied by default.
    # if 'modify_transactions' in account_config:
    #    _, (lines, modified_lines) = \
    #        modify_transactions(lines, account_config['modify_transactions'])

    # With no modifications, then it doesn't matter what is returned for 'modified_lines' variable, and the new_lines are just the old lines
    new_lines, _ = modify_transactions(new_lines, account_config.get('modify_transactions', None))

    return lines, new_lines, ignored_lines


def get_Processed_Csv_Lines(csv_filename: str,
                            account_config: Dict) -> Tuple[List[str], List[str], List[str]]:
    """
    Gets csv lines from a file and then performs pre-processing.
    Returns a tuple that is (original lines, modified lines, ignored lines).
    """
    original_lines = get_Lines_From_File(csv_filename)

    original_lines, modified_lines, ignored_lines = process_csv_lines(original_lines, account_config)

    return original_lines, modified_lines, ignored_lines


def create_Ledger_Convert_Command(csv_filename: str,
                                  account_name: str,
                                  additional_ledger_args: str = '',
                                  input_date_format: str = '%Y/%m/%d',
                                  conversion_ledger_file: str = LEDGER_FILE) -> str:
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

    return cmd


# TODO Add in a **kwargs to this command so that people can pass in any additional items to add to the ledger command
def create_Ledger_Convert_Command_From_Config(csv_filename: str,  # pylint: disable=unused-argument
                                              account_name: str,  # pylint: disable=unused-argument
                                              account_config: Dict,
                                              conversion_ledger_file: str) -> str:  # pylint: disable=unused-argument
    """
    Function to pull the necessary variables out of the config dictionary and create the ledger convert command
    """

    variables_required = ['account_name',
                          'csv_filename',
                          'conversion_ledger_file',
                          'additional_ledger_args',
                          'input_date_format']

    # use variables passed into this function first (locals), but variables from the account config otherwise.
    # If neither has the value, it shouldn't be in the dictionary so that the default of the function being called is preserved
    local_vars = locals()
    convert_dictionary = {key: local_vars.get(key, account_config.get(key, None))
                          for key in variables_required
                          if key in local_vars or key in account_config}

    return create_Ledger_Convert_Command(**convert_dictionary)


def post_process_regex_replacements(journal_lines: List[str], terms_to_search_and_replace: List[Tuple[str, str, str]], account_config: Dict[str, Any]) -> List[str]:
    """
    Performs multiple regex replacements to correct aspects of the converted journal.
    """
    new_lines = journal_lines.copy()

    for key, pattern, replacement in terms_to_search_and_replace:
        if key in account_config:
            new_lines, _ = modify_transactions(new_lines, (pattern, replacement))

    return new_lines


def insert_Csv_Lines_into_Transactions(transaction_lines: List[str], original_csv_lines: List[str], modified_csv_lines: List[str]) -> List[str]:
    """
    Inserts the CSV lines (original and modified) into the journal formatted transaction lines and returns the processed lines.
    Needs the original csv lines and the modified csv lines to be in the same transaction order as the converted transaction lines.
    """

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
                             format(modified_csv_lines[i].strip()))
            new_lines.append('    ; (raw): {}\n'.
                             format(original_csv_lines[i].strip()))
            i += 1

    return new_lines


def add_ignored_csv_lines(transaction_lines: List[str], ignored_csv_lines: List[str]) -> List[str]:
    """
    Appends the ignored csv lines (transactions) to the end of the converted transaction lines
    This is part of the generic post-processing done to the journal format transaction lines.
    """

    if len(ignored_csv_lines) > 0:
        transaction_lines.append('\n\n; Attention: The following lines were ignored:\n')
        transaction_lines.extend(ignored_csv_lines)

    return transaction_lines


def process_Converted_Transactions(transaction_lines: List[str],
                                   original_lines: List[str],
                                   modified_lines: List[str],
                                   ignored_lines: List[str],
                                   account_config: Dict[str, Any]) -> List[str]:
    """
    Performs post-processing on the generated ledger format transactions.
    Returns the final journal lines from the conversion as a list of strings.
    """
    new_lines = insert_Csv_Lines_into_Transactions(transaction_lines, original_lines, modified_lines)

    new_lines = add_ignored_csv_lines(new_lines, ignored_lines)

    # Setting up some regex replacements. TODO In due course, I want to move these into the config file similar to how 'modify_transactions' is
    terms_to_search_and_replace = [('currency', r"\(^\s\+.*\s\+\)\([-0-9\.]\+\)$", f"\\1{str(account_config.get('currency')).encode('utf').decode()}\\2/g"),
                                   ('expenses_unknown', 'Expenses:Unknown', "{account_config.get('expenses_unknown', None)}")]

    new_lines = post_process_regex_replacements(new_lines, terms_to_search_and_replace, account_config)

    # TODO Add in the possibility to sort by date (now that meta data has been correctly (and fully) added.
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

    # TODO Would like to save this to the private tmp folder in due course to make it easier for people to see what the processed csv becomes
    # to be honest, need to write some code so that csv filenames and journalfile names can be identified easily based on the account
    # config parameters and the current date. So you could define a template file and a periodicity (eg monthly) and then you would
    # know what the previous period's csvfilename and tmp-journal filename would be based on that template and the previous month number
    with open(tmp_csv_filename, 'w') as f:
        f.write('\n'.join(modified_lines))

    # Use ledger to convert the lines to ledger format
    cmd = create_Ledger_Convert_Command_From_Config(tmp_csv_filename, account_name, account_config, LEDGER_FILE)

    # Run the ledger command
    try:
        process_result = subprocess.run(cmd, capture_output=True, check=True, shell=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"Calling the ledger command {cmd} resulted in an error:\n{e}.\nThe stderr pipe text is:\n{e.stderr}")

    converted_lines = process_result.stdout.split('\n')

    # Post processing
    converted_lines = process_Converted_Transactions(converted_lines, original_lines, modified_lines, ignored_lines, account_config)

    save_Lines_To_File(tmp_journal_filename, converted_lines)

    # Print to stdout for later use.
    print(''.join(converted_lines))

    # TODO This script should really save the final converted output to a file in a good location, rather than relying on
    # redirect from standard out. The line above that saves it to a tmp file gets undone by cleanup below where the file is
    # deleted

    # Cleanup.
    os.remove(tmp_csv_filename)
    os.remove(tmp_journal_filename)


if __name__ == '__main__':
    main(sys.argv)
