#! /usr/bin/env python3

"""
ABCD to BIDS CLI Wrapper
Greg Conan: conan@ohsu.edu
Created 2019-05-29
Updated 2020-01-15
"""

##################################
#
# Wrapper for ABCD DICOM to BIDS pipeline that can be run from the command line
#    1. Imports data, QC's it, and exports abcd_fastqc01_reformatted.csv
#    2. Runs aws_downloader.py to download ABCD data using .csv table
#    3. Runs unpack_and_setup.sh to unpack/setup the downloaded ABCD data
#    4. Runs correct_jsons.py to conform data to official BIDS standards
#    5. Runs BIDS validator on unpacked/setup data using Docker
#
##################################

import argparse
import configparser
from cryptography.fernet import Fernet
import datetime
from getpass import getpass
import glob
import os
import pandas as pd
import shutil
import signal
import subprocess
import sys

# Constant: List of function names of steps 1-5 in the list above
STEP_NAMES = ["reformat_fastqc_spreadsheet", "download_nda_data",
              "unpack_and_setup", "correct_jsons", "validate_bids"]

# Get path to directory containing abcd2bids.py
try:
    PWD = os.path.dirname(os.path.abspath(__file__))
    assert os.access(os.path.join(PWD, "abcd2bids.py"), os.R_OK)
except (OSError, AssertionError):
    PWD = os.getcwd()

# Constants: Default paths to scripts to call from this wrapper, and default
# paths to folders in which to manipulate data
CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".abcd2bids", "config.ini")
CORRECT_JSONS = os.path.join(PWD, "src", "correct_jsons.py")
DOWNLOAD_FOLDER = os.path.join(PWD, "raw")
#NDA_AWS_TOKEN_MAKER = os.path.join(PWD, "src", "nda_aws_token_maker.py")
NDA_AWS_TOKEN_MAKER = os.path.join(PWD, "src", "ndar_update_keys.py")
DOWNLOAD_CMD_PATH = os.path.join(os.path.expanduser("~"), ".local", "bin", "downloadcmd")

SERIES_TABLE_PARSER = os.path.join(PWD, "src", "aws_downloader.py")
SPREADSHEET_DOWNLOAD = os.path.join(PWD, "temp", "abcd_fastqc01_reformatted.csv")
SPREADSHEET_QC = os.path.join(PWD, "spreadsheets", "abcd_fastqc01.txt")
TEMP_FILES_DIR = os.path.join(PWD, "temp")
UNPACK_AND_SETUP = os.path.join(PWD, "src", "unpack_and_setup.sh")
UNPACKED_FOLDER = os.path.join(PWD, "data")
MODALITIES = ['anat', 'func', 'dwi']
SESSIONS = ['baseline_year_1_arm_1', '2_year_follow_up_y_arm_1']


def main():
    """
    Run entire process of downloading ABCD data from NDA website, transforming
    it to meet BIDS standards, and validating that it meets those standards.
    :return: N/A
    """
    cli_args = get_cli_args()
    starting_timestamp = get_and_print_timestamp_when(sys.argv[0], "started")

    # Set cleanup function to delete all temporary files if script crashes
    if cli_args.remove:
        set_to_cleanup_on_crash(cli_args.temp)

    # Before running any different scripts, validate user's NDA credentials and
    # use them to make NDA token
    #make_nda_token(cli_args)

    # Run all steps sequentially, starting at the one specified by the user
    started = False
    for step in STEP_NAMES:
        if step == cli_args.start_at:
            started = True
        if started:
            get_and_print_timestamp_when("The {} step".format(step),
                                         "started")
            globals()[step](cli_args)
            get_and_print_timestamp_when("The {} step".format(step),
                                         "finished")
    print(starting_timestamp)
    get_and_print_timestamp_when(sys.argv[0], "finished")

    # Finally, delete temporary files and end script with success exit code
    cleanup(cli_args.temp, 0)


def get_and_print_timestamp_when(script, did_what):
    """
    Print and return a string showing the exact date and time when a script
    reached a certain part of its process
    :param script: String naming the script that started/finished
    :param did_what: String which is a past tense verb describing what the
                     script did at the timestamp, like "started" or "finished"
    :return: String with a human-readable message showing when script did_what
    """
    timestamp = "\n{} {} at {}".format(
        script, did_what,
        datetime.datetime.now().strftime("%H:%M:%S on %b %d, %Y")
    )
    print(timestamp)
    return timestamp


def get_cli_args():
    """
    Get and validate all args from command line using argparse.
    :return: Namespace containing all validated inputted command line arguments
    """
    # Create arg parser
    parser = argparse.ArgumentParser(
        description="Wrapper to download, parse, and validate QC'd ABCD data."
    )

    # Required: Get path to FSL directory
    parser.add_argument(
        "fsl_dir",
        type=str,
        help=("Required: Path to FSL directory. This positional argument must "
              "be a valid path to an existing folder.")
    )

    # Required: Get path to MRE / MCR root to run compiled MATLAB script
    parser.add_argument(
        "mre_dir",
        type=str,
        help=("Required: Path to directory containing MATLAB Runtime "
              "Environment (MRE) version 9.1 or newer. This is used to run "
              "a compiled MATLAB script. This positional argument must be a "
              "valid path to an existing folder.")
    )

    # Optional: Get path to already-existing config file with NDA credentials
    parser.add_argument(
        "-c",
        "--config",
        default=CONFIG_FILE,
        help=("Path to config file with NDA credentials. If no "
              "config file exists at this path yet, then one will be created. "
              "Unless this option or --username and --password is added, the "
              "user will be prompted for their NDA username and password. "
              "By default, the config file will be located at " + CONFIG_FILE)
    )

    # Optional: Get download folder path from user as CLI arg
    parser.add_argument(
        "-d",
        "--download",
        default=DOWNLOAD_FOLDER,
        help=("Path to folder which NDA data will be downloaded "
              "into. By default, data will be downloaded into the {} folder. "
              "A folder will be created at the given path if one does not "
              "already exist.".format(DOWNLOAD_FOLDER))
    )

    # Optional: Get folder to unpack NDA data into from download folder
    parser.add_argument(
        "-o",
        "--output",
        default=UNPACKED_FOLDER,
        help=("Folder path into which NDA data will be unpacked and "
              "setup once downloaded. By default, this script will put the "
              "data into the {} folder. A folder will be created at the given "
              "path if one does not already exist.".format(UNPACKED_FOLDER))
    )

    # Optional: Get QC spreadsheet
    parser.add_argument(
        "-q",
        "--qc",
        type=validate_readable_file,
        default=SPREADSHEET_QC,
        help=("Path to Quality Control (QC) spreadsheet file downloaded from "
              "the NDA. By default, this script will use {} as the QC "
              "spreadsheet.".format(SPREADSHEET_QC))
    )
    parser.add_argument(
        "-p",
        "--package_id",
        required=True,
        help=("ID of the data package that is created via the NDA")
    )
    parser.add_argument(
        "--downloadcmd",
        default=DOWNLOAD_CMD_PATH,
        help=("Path to downloadcmd executable")
    )

    # Optional: Subject list
    parser.add_argument(
        "-l",
        "--subject-list",
        dest="subject_list",
        type=validate_readable_file,
        required=True,
        help=("Path to a .txt file containing a list of subjects to download. "
              "The default is to download all available subjects.")
    )

    # Optional: Sessions
    parser.add_argument(
        "-y",
        "--sessions",
        choices=SESSIONS,
        nargs="+",
        dest="sessions",
        default=SESSIONS,
        help=("List of sessions for each subject to download. The default is "
             "to download all sessions for each subject. "
             "The possible selections are {}".format(SESSIONS))
)    

    # Optional: Modalities
    parser.add_argument(
        "-m",
        "--modalities",
        choices=MODALITIES,
        nargs="+",
        dest="modalities",
        default=MODALITIES,
        help=("List of the imaging modalities that should be downloaded for "
             "each subject. The default is to download all modalities. "
             "The possible selections are {}".format(MODALITIES))
)    

    # Optional: During unpack_and_setup, remove unprocessed data
    parser.add_argument(
        "-r",
        "--remove",
        action="store_true",
        help=("After each subject's data has finished conversion, "
              "removed that subject's unprocessed data.")
    )

    # Optional: Pick a step to start at, ignore previous ones, and then run
    # that function and all subsequent ones sequentially
    parser.add_argument(
        "-s",
        "--start_at",
        choices=STEP_NAMES,
        default=STEP_NAMES[0],
        help=("Give the name of the step in the wrapper to start "
              "at, then run that step and every step after it. Here are the "
              "names of all of the steps, in order from first to last: "
              + ", ".join(STEP_NAMES))
    )

    # Optional: Get folder to place temp data into during unpacking
    parser.add_argument(
        "-t",
        "--temp",
        default=TEMP_FILES_DIR,
        help=("Path to the directory to be created and filled with "
              "temporary files during unpacking and setup. By default, the "
              "folder will be created at {} and deleted once the script "
              "finishes. A folder will be created at the given path if one "
              "doesn't already exist.".format(TEMP_FILES_DIR))
    )

    # Optional: Get NDA username and password
    parser.add_argument(
        "-u",
        "--username",
        type=str,
        help=("NDA username. Adding this will create a new config "
              "file or overwrite an old one. Unless this is added or a config "
              "file exists with the user's NDA credentials, the user will be "
              "prompted for them. If this is added and --password is not, "
              "then the user will be prompted for their NDA password.")
    )

    parser.add_argument(
        "-z",
        "--docker-cmd",
        type=str,
        dest="docker_cmd",
        default=None,
        help=("A necessary docker command replacement on HPCs like "
              "the one at OHSU, which has it's own special wrapper for"
              "docker for security reasons. Example: '/opt/acc/sbin/exadocker'")
    )
    parser.add_argument(
        "-x",
        "--singularity",
        type=str,
        dest="sif_path",
        default=None,
        help=("Use singularity and path the .sif file")
    )

    # Parse, validate, and return all CLI args
    return validate_cli_args(parser.parse_args(), parser)


def validate_cli_args(args, parser):
    """
    Check that all command line arguments will allow this script to work.
    :param args: argparse namespace with all command-line arguments
    :param parser: argparse ArgumentParser to raise error if anything's invalid
    :return: Validated command-line arguments argparse namespace
    """
    # Validate FSL and MRE directories
    validate_dir_path(args.fsl_dir, parser)
    validate_dir_path(args.mre_dir, parser)

    # Validate and create config file's parent directory
    try:
        os.makedirs(os.path.dirname(args.config), exist_ok=True)
    except (OSError, TypeError):
        parser.error("Could not create folder to contain config file.")

    # Validate other dirs: check if they exist; if not, try to create them; and
    # move important files in the default dir(s) to the new dir(s)
    try:
        for cli_arg in ("download", "output", "temp"):
            setattr(args, cli_arg, os.path.abspath(getattr(args, cli_arg)))
    except OSError:
        parser.error("Failed to convert {} to absolute path.".format(cli_arg))
    try_to_create_and_prep_directory_at(args.download, DOWNLOAD_FOLDER, parser)
    try_to_create_and_prep_directory_at(args.output, UNPACKED_FOLDER, parser)
    try_to_create_and_prep_directory_at(args.temp, TEMP_FILES_DIR, parser)

    # Ensure that the output folder path is formatted correctly:
    if args.output[-1] != "/":
        args.output += "/"

    return args


def validate_dir_path(dir_path, parser):
    """
    Validate that a given path refers to an existing directory; if it doesn't,
    then raise an argparse error
    :param dir_path: Path to validate
    :param parser: argparse ArgumentParser to raise error if path is invalid
    :return: N/A
    """
    if not os.path.isdir(dir_path):
        parser.error(dir_path + " is not an existing directory.")


def validate_readable_file(param):
    """
    Throw exception unless parameter is a valid readable filename string. This
    is used instead of argparse.FileType("r") because the latter leaves an open
    file handle, which has caused problems.
    :param param: Parameter to check if it represents a valid filename
    :return: A valid filename as a string
    """
    if not os.access(param, os.R_OK):
        raise argparse.ArgumentTypeError("Could not read file at " + param)
    return os.path.abspath(param)


def try_to_create_and_prep_directory_at(folder_path, default_path, parser):
    """
    Validate file path of folder, and if it doesn't exist, create it. If a
    non-default path is given, then move the file(s) in the default folder(s)
    to the new folder(s) without copying any subdirectories (which have data).
    :param folder_path: Path of folder that either exists or should be created
    :param default_path: The default value of folder_path. The folder here
    has some files which will be copied to the new directory at folder_path.
    :param parser: argparse ArgumentParser to raise error if path is invalid
    :return: N/A
    """
    try:
        os.makedirs(folder_path, exist_ok=True)
    except (OSError, TypeError):
        parser.error("Could not create folder at " + folder_path)

    # If user gave a different directory than the default, then copy the
    # required files into that directory and nothing else
    default = os.path.abspath(default_path)
    if os.path.abspath(folder_path) != default:
        for each_file in os.scandir(default):
            if not each_file.is_dir():
                #shutil.copy2(each_file.path, folder_path)
                try:
                    shutil.copyfile(each_file.path, os.path.join(folder_path, each_file.name))
                # If source and destination are same
                except shutil.SameFileError:
                    print("Source and destination represents the same file.")
                 
                # If destination is a directory.
                except IsADirectoryError:
                    print("Destination is a directory.")
                 
                # If there is any permission issue
                except PermissionError:
                    print("Permission denied.")
                 
                # For other errors
                except:
                    print("Error occurred while copying file.")


def set_to_cleanup_on_crash(temp_dir):
    """
    Make it so that if the script crashes, all of the temporary files that it
    generated are deleted. signal.signal() checks if the script has crashed,
    and cleanup() deletes all of the temporary files.
    :return: N/A
    """
    # Use local function as an intermediate because the signal module does
    # not allow the signal handler (the second parameter of signal.signal) to
    # take the parameter (temp_dir) needed by the cleanup function. Run cleanup
    # function and exit with exit code 1 (failure)
    def call_cleanup_function(_signum, _frame):
        cleanup(temp_dir, 1)

    # If this wrapper crashes, delete all temporary files
    signal.signal(signal.SIGINT, call_cleanup_function)
    signal.signal(signal.SIGTERM, call_cleanup_function)


def cleanup(temp_dir, exit_code):
    """
    Function to delete all temp files created while running this script. This
    function will always run right before the wrapper terminates, whether or
    not the wrapper ran successfully.
    :param temp_dir: Path to folder containing temporary files to delete.
    :param exit_code: Code for this wrapper to return on exit. If cleanup() is
    called when wrapper finishes successfully, then 0; otherwise 1.
    :return: N/A
    """
    # Delete all temp folder subdirectories, but not the README in temp folder
    for temp_dir_subdir in os.scandir(temp_dir):
        if temp_dir_subdir.is_dir():
            shutil.rmtree(temp_dir_subdir.path)

    # Inform user that temporary files were deleted, then terminate wrapper
    print("\nTemporary files in {} deleted. ABCD to BIDS wrapper "
          "terminated.".format(temp_dir))
    sys.exit(exit_code)


def make_nda_token(args):
    """
    Create NDA token by getting credentials from config file. If no config file
    exists yet, or user specified to make a new one by entering their NDA
    credentials as CLI args, then create one to store NDA credentials.
    :param args: argparse namespace containing all CLI arguments. The specific
    arguments used by this function are --username, --password, and --config.
    :return: N/A
    """
    # If config file with NDA credentials exists, then get credentials from it,
    # unless user entered other credentials to make a new config file
    if not args.username and os.path.exists(args.config):
        username, password = get_nda_credentials_from(args.config)

    # Otherwise get NDA credentials from user & save them in a new config file,
    # overwriting the existing config file if user gave credentials as cli args
    else:

        # If NDA username was a CLI arg, use it; otherwise prompt user for it
        if args.username:
            username = args.username
        else:
            username = input("\nEnter your NIMH Data Archives username: ")

        # If NDA password was a CLI arg, use it; otherwise prompt user for it
        password = getpass("Enter your NIMH Data Archives password: ")
            
        make_config_file(args.config, username, password)

    # Try to make NDA token
    token_call_exit_code = subprocess.call((
        "python3",
        NDA_AWS_TOKEN_MAKER,
        "--username", username,
        "--password", password,
        "--config-dir", args.temp
    ))

    # If NDA credentials are invalid, tell user so without printing password.
    # Manually catch error instead of using try-except to avoid trying to
    # catch another file's exception.
    if token_call_exit_code != 0:
        print("Failed to create NDA token using the username and decrypted "
              "password from {}.".format(os.path.abspath(args.config)))
        sys.exit(1)


def get_nda_credentials_from(config_file_path):
    """
    Given the path to a config file, returns user's NDA credentials.
    :param config_file_path: Path to file containing user's NDA username,
    encrypted form of user's NDA password, and key to that encryption.
    :return: Two variables: user's NDA username and password.
    """
    # Object to read/write config file containing NDA credentials
    config = configparser.ConfigParser()
    config.read(config_file_path)

    # Get encrypted password and encryption key from config file
    encryption_key = config["NDA"]["key"]
    encrypted_password = config["NDA"]["encrypted_password"]

    # Decrypt password to get user's NDA credentials
    username = config["NDA"]["username"]
    password = (
        Fernet(encryption_key.encode("UTF-8"))
        .decrypt(token=encrypted_password.encode("UTF-8"))
        .decode("UTF-8")
    )

    return username, password


def make_config_file(config_filepath, username, password):
    """
    Create a config file to save user's NDA credentials.
    :param config_filepath: Name and path of config file to create.
    :param username: User's NDA username to save in config file.
    :param password: User's NDA password to encrypt then save in config file.
    :return: N/A
    """
    # Object to read/write config file containing NDA credentials
    config = configparser.ConfigParser()

    # Encrypt user's NDA password by making an encryption key
    encryption_key = Fernet.generate_key()
    encrypted_pass = Fernet(encryption_key).encrypt(password.encode("UTF-8"))

    # Save the encryption key and encrypted password to a new config file
    config["NDA"] = {
        "username": username,
        "encrypted_password": encrypted_pass.decode("UTF-8"),
        "key": encryption_key.decode("UTF-8")
    }
    with open(config_filepath, "w") as configfile:
        config.write(configfile)

    # Change permissions of the config file to prevent other users accessing it
    subprocess.check_call(("chmod", "700", config_filepath))


def reformat_fastqc_spreadsheet(cli_args):
    """
    Create abcd_fastqc01_reformatted.csv by reformatting the original fastqc01.txt spreadsheet.
    :param cli_args: argparse namespace containing all CLI arguments.
    :return: N/A
    """   
    # Import QC data from .csv file
    with open(cli_args.qc) as qc_file:
        all_qc_data = pd.read_csv(
            qc_file, encoding="utf-8-sig", sep=",|\t", engine="python",
            index_col=False, header=0, skiprows=[1] # Skip row 2 (description)
        )
    
    # Remove quotes from values and convert int-strings to ints
    all_qc_data = all_qc_data.applymap(lambda x: x.strip('"')).apply(
        lambda x: x.apply(lambda y: int(y) if y.isnumeric() else y)
    )
    
    # Remove quotes from headers
    new_headers = []
    for header in all_qc_data.columns: # data.columns is your list of headers
        header = header.strip('"') # Remove the quotes off each header
        new_headers.append(header) # Save the new strings without the quotes
    all_qc_data.columns = new_headers # Replace the old headers with the new list
    print(all_qc_data.columns)

    # select all QC data, not just those with ftq_usable == 1
    qc_data = fix_split_col(all_qc_data)

    def get_img_desc(row):
        """
        :param row: pandas.Series with a column called "ftq_series_id"
        :return: String with the image_description of that row
        """
        return row.ftq_series_id.split("_")[2]

    # Add extra column by splitting data from other column
    image_desc_col = qc_data.apply(get_img_desc, axis=1)
    qc_data = qc_data.assign(**{'image_description': image_desc_col.values})

    def get_img_timestamp(row):
        """
        :param row: pandas.Series with a column called "ftq_series_id"
        :return: String with the image_description of that row
        """
        return row.ftq_series_id.split("_")[3]

    # Add extra column by splitting data from other column
    image_timestamp_col = qc_data.apply(get_img_timestamp, axis=1)
    qc_data = qc_data.assign(**{'image_timestamp': image_timestamp_col.values})

    # remove "Replaced" rows from download list
    qc_data = qc_data[qc_data['ftq_recall_reason'] != 'Replaced']

    # Change column names for good_bad_series_parser to use; then save to .csv
    qc_data.rename({
        "ftq_usable": "QC", "subjectkey": "pGUID", "visit": "EventName",
        "abcd_compliant": "ABCD_Compliant", "interview_age": "SeriesTime",
        "comments_misc": "SeriesDescription", "file_source": "image_file"
    }, axis="columns").sort_values([
        'pGUID',
        'EventName',
        'image_description',
        'image_timestamp'
    ]).to_csv(SPREADSHEET_DOWNLOAD, index=False)


def fix_split_col(qc_df):
    """
    Because qc_df's ftq_notes column contains values with commas, it is split
    into multiple columns on import. This function puts them back together.
    :param qc_df: pandas.DataFrame with all QC data
    :return: pandas.DataFrame which is qc_df, but with the last column(s) fixed
    """
    def trim_end_columns(row):
        """
        Local function to check for extra columns in a row, and fix them
        :param row: pandas.Series which is one row in the QC DataFrame
        :param columns: List of strings where each is the name of a column in
        the QC DataFrame, in order
        :return: N/A
        """
        ix = int(row.name)
        if not pd.isna(qc_df.at[ix, columns[-1]]):
            qc_df.at[ix, columns[-3]] += " " + qc_df.at[ix, columns[-2]]
            qc_df.at[ix, columns[-2]] = qc_df.at[ix, columns[-1]]

    # Keep checking and dropping the last column of qc_df until it's valid
    columns = qc_df.columns.values.tolist()
    last_col = columns[-1]
    while any(qc_df[last_col].isna()):
        qc_df.apply(trim_end_columns, axis="columns")
        print("Dropping '{}' column because it has NaNs".format(last_col))
        qc_df = qc_df.drop(last_col, axis="columns")
        columns = qc_df.columns.values.tolist()
        last_col = columns[-1]
    return qc_df


def download_nda_data(cli_args):
    """
    Call Python script to download NDA data by making NDA token and parsing the
    good_and_bad_series_table.csv spreadsheet.
    :param cli_args: argparse namespace containing all CLI arguments. This
    function only uses the --download argument, the path to the folder to fill
    with downloaded NDA data.
    :return: N/A
    """
    subprocess.check_call(("python3", "--version"))
    print(cli_args.modalities)
    subprocess.check_call(("python3", 
                            SERIES_TABLE_PARSER,
                            "--qc-csv", os.path.join(cli_args.temp, os.path.basename(SPREADSHEET_DOWNLOAD)),
                            "--download-dir", cli_args.download, 
                            "--subject-list", cli_args.subject_list,
                            "--sessions", ','.join(cli_args.sessions),
                            "--modalities", ','.join(cli_args.modalities),
                            "--downloadcmd", cli_args.downloadcmd,
                            "--package-id", cli_args.package_id))


def unpack_and_setup(args):
    """
    Run unpack_and_setup.sh script repeatedly to unpack and setup the newly
    downloaded NDA data files (every .tgz file descendant of the NDA data dir)
    :param args: All arguments entered by the user from the command line. The
    specific arguments used by this function are fsl_dir, mre_dir, --output,
    --download, --temp, and --remove.
    :return: N/A
    """

    # Create list of all subject directories for setup
    subject_dir_paths = {}
    if args.subject_list:
        f = open(args.subject_list, 'r')
        x = f.readlines()
        f.close
        subject_list = [sub.strip() for sub in x]
        for subject in subject_list:
            uid_start = "INV"
            uid = subject.split(uid_start, 1)[1]
            bids_pid = 'sub-NDARINV' + ''.join(uid)
            subject_dir = os.path.join(args.download, bids_pid)
            if os.path.isdir(subject_dir):
                subject_dir_paths[bids_pid] = subject_dir
    else:
        for subject in os.scandir(args.download):
            if subject.is_dir():
                subject_dir_paths[subject.name] = subject.path

    # Loop through each subject and setup all sessions for that subject
    for subject, subject_dir in subject_dir_paths.items():
        for session_dir in os.scandir(subject_dir):
            if session_dir.is_dir():
                tgz_dir = os.path.join(session_dir.path, 'image03')
                for tgz in os.scandir(tgz_dir):
                    if tgz:
                        # Get session ID from some (arbitrary) .tgz file in
                        # session folder
                        session_name = tgz.name.split("_")[1]
                        print('Unpacking and setting up tgzs for {} {} located here: {}'.format(subject, session_name, tgz_dir))
                        print("Running: ", UNPACK_AND_SETUP, subject, "ses-" + session_name, session_dir.path, args.output, args.temp, args.fsl_dir, args.mre_dir)

                        # Unpack/setup the data for this subject/session
                        subprocess.check_call((
                            UNPACK_AND_SETUP,
                            subject,
                            "ses-" + session_name,
                            session_dir.path,
                            args.output,
                            args.temp,
                            args.fsl_dir,
                            args.mre_dir
                        ))

                        # If user said to, delete all the raw downloaded
                        # files for each subject after that subject's data
                        # has been converted and copied
                        if args.remove:
                            shutil.rmtree(os.path.join(args.download,
                                                       subject))
                        break


def correct_jsons(cli_args):
    """
    Correct ABCD BIDS input data to conform to official BIDS Validator.
    :param cli_args: argparse namespace containing all CLI arguments. This
    function only uses the --output argument, the path to the folder containing
    corrected NDA data to validate.
    :return: N/A
    """
    subprocess.check_call((CORRECT_JSONS, cli_args.output))

    # Remove the .json files added to each subject's output directory by
    # sefm_eval_and_json_editor.py, and the vol*.nii.gz files
    sub_dirs = os.path.join(cli_args.output, "sub*")
    for json_path in glob.iglob(os.path.join(sub_dirs, "*.json")):
        print("Removing .JSON file: {}".format(json_path))
        os.remove(json_path)
    for vol_file in glob.iglob(os.path.join(sub_dirs, "ses*", 
                          "fmap", "vol*.nii.gz")):
        print("Removing 'vol' file: {}".format(vol_file))
        os.remove(vol_file)


def validate_bids(cli_args):
    """
    Run the official BIDS validator on the corrected ABCD BIDS data.
    :param cli_args: argparse namespace containing all CLI arguments. This
    function only uses the --output argument, the path to the folder containing
    corrected NDA data to validate.
    :return: N/A
    """
    try:
        if cli_args.sif_path:
            subprocess.check_call(("singularity", "run", "-B", cli_args.output + ":/data", 
                                   cli_args.sif_path, "/data"))
        else:
            if cli_args.docker_cmd:
                subprocess.check_call(('sudo', cli_args.docker_cmd, "run", "-ti", "--rm", "-v",
                                       cli_args.output + ":/data:ro", "bids/validator",
                                       "/data"))
            else:    
                subprocess.check_call(("docker", "run", "-ti", "--rm", "-v",
                                       cli_args.output + ":/data:ro", "bids/validator",
                                       "/data"))
    except subprocess.CalledProcessError:
        print("Error: BIDS validation failed.")

if __name__ == '__main__':
    main()

