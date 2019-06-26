#! /usr/bin/env python3

"""
ABCD to BIDS CLI Wrapper
Greg Conan: conan@ohsu.edu
Created 2019-05-29
Last Updated 2019-06-26
"""

##################################
#
# Wrapper for ABCD DICOM to BIDS pipeline that can be run from the command line
#    1. Runs data_gatherer to create ABCD_good_and_bad_series_table.csv
#    2. Runs good_bad_series_parser to download ABCD data using that .csv table
#    3. Runs unpack_and_setup to unpack/setup the downloaded ABCD data
#    4. Runs correct_jsons to conform data to official BIDS standards
#    5. Runs BIDS validator on unpacked/setup data using Docker
#
##################################

import argparse
import configparser
from cryptography.fernet import Fernet
from getpass import getpass
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys

# Constants: Default paths to scripts to call from this wrapper, and default
# paths to folders in which to manipulate data
CONFIG_FILEPATH = os.path.expanduser("~/.abcd2bids/config.ini")
CORRECT_JSONS = "./src/correct_jsons.py"
DATA_GATHERER = "./src/bin/run_data_gatherer.sh"
DOWNLOAD_FOLDER = "./raw/"
GOOD_BAD_SERIES_PARSER = "./src/good_bad_series_parser.py"
NDA_AWS_TOKEN_MAKER = "./src/nda_aws_token_maker.py"
TEMP_FILES_DIR = "./temp"
UNPACK_AND_SETUP = "./src/unpack_and_setup.sh"
UNPACKED_FOLDER = "./data/"


def main():
    """
    Run entire process of downloading ABCD data from NDA website, transforming
    it to meet BIDS standards, and validating that it meets those standards.
    :return: N/A
    """
    cli_args = cli()
    print("\nRunning ABCD to BIDS wrapper. Started at: ")
    subprocess.check_call("date")

    # Set cleanup function to delete all temporary files if script crashes
    set_to_cleanup_on_crash(cli_args.temp)

    # Before running any different scripts, validate user's NDA credentials and
    # use them to make NDA token
    make_nda_token(cli_args)

    # Make list of functions, so that the wrapper can be run from any point in
    # the list and then sequentially run every function after that point.
    data_processing_steps = [

        # 1. Use compiled MATLAB script to create good_and_bad_series_table.csv
        create_good_and_bad_series_table,

        # 2. Parse good_and_bad_series_table.csv and download NDA data
        download_nda_data,

        # 3. Once NDA data is downloaded, unpack and set it up using .sh script
        unpack_and_setup,

        # 4. Correct ABCD BIDS input data to conform to official BIDS validator
        correct_jsons,

        # 5. Run the official BIDS validator on the corrected ABCD BIDS data
        run_bids_validator
    ]

    # Run the steps sequentially, starting at the one specified by the user
    for step in range(cli_args.start_at_step-1, len(data_processing_steps)):
        data_processing_steps[step](cli_args)

    # Finally, delete temporary files and end script with success exit code
    cleanup(cli_args.temp, 0)


def cli():
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

    # Optional: Get NDA username and password
    parser.add_argument(
        "-u",
        "--username",
        type=str,
        help=("Optional: NDA username. Adding this will create a new config "
              "file or overwrite an old one. Unless this is added or a config "
              "file exists with the user's NDA credentials, the user will be "
              "prompted for them. If this is added and --password is not, "
              "then the user will be prompted for their NDA password.")
    )
    parser.add_argument(
        "-p",
        "--password",
        type=str,
        help=("Optional: NDA password. Adding this will create a new config "
              "file or overwrite an old one. Unless this is added or a config "
              "file exists with the user's NDA credentials, the user will be "
              "prompted for them. If this is added and --username is not, "
              "then the user will be prompted for their NDA username.")
    )

    # Optional: Get path to already-existing config file with NDA credentials
    parser.add_argument(
        "-c",
        "--config",
        default=CONFIG_FILEPATH,
        help=("Optional: Path to config file with NDA credentials. If no "
              "config file exists at this path yet, then one will be created. "
              "Unless this option or --username and --password is added, the "
              "user will be prompted for their NDA username and password. "
              "By default, the config file will be located at "
              + os.path.abspath(CONFIG_FILEPATH))
    )

    # Optional: Get download folder path from user as CLI arg
    parser.add_argument(
        "-d",
        "--download",
        default=DOWNLOAD_FOLDER,
        help=("Optional: Path to folder which NDA data will be downloaded "
              "into. By default, data will be downloaded into the "
              + os.path.abspath(DOWNLOAD_FOLDER) + " folder.")
    )

    # Optional: Get folder to unpack NDA data into from download folder
    parser.add_argument(
        "-o",
        "--output",
        default=UNPACKED_FOLDER,
        help=("Optional: Folder path into which NDA data will be unpacked and "
              "setup once downloaded. By default, this script will put the "
              "data into the " + os.path.abspath(UNPACKED_FOLDER) + " folder.")
    )

    # Optional: Get folder to place temp data into during unpacking
    parser.add_argument(
        "-t",
        "--temp",
        default=TEMP_FILES_DIR,
        help=("Optional: Path to the directory to be created and filled with "
              "temporary files during unpacking and setup. By default, the "
              "folder will be created at " + os.path.abspath(TEMP_FILES_DIR)
              + " and deleted once the script finishes.")
    )

    # Optional: During unpack_and_setup, remove unprocessed data
    parser.add_argument(
        "-r",
        "--remove",
        action="store_true",
        help=("Optional: After each subject's data has finished processing, "
              "removed that subject's unprocessed data.")
    )

    # Optional: Pick a step to start at, ignore previous ones, and then run
    # that function and all subsequent ones sequentially
    parser.add_argument(
        "-s",
        "--start_at_step",
        type=int,
        choices=list(range(6)),
        default=1,
        help=("Optional: Give the number of the step in the wrapper to start "
              "at, then run that step and every step after it. Here are the "
              "numbers of all of the steps:"
              "\n1. create_good_and_bad_series_table\n2. download_nda_data"
              "\n3. unpack_and_setup\n4. correct_jsons\n5. run_bids_validator")
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
        Path(os.path.dirname(args.config)).mkdir(parents=True, exist_ok=True)
    except (OSError, TypeError):
        parser.error("Could not create folder to contain config file.")

    # Validate other dirs: check if they exist; if not, try to create them; and
    # move important files in the default dir(s) to the new dir(s)
    try_to_create_and_prep_directory_at(args.download, DOWNLOAD_FOLDER, parser)
    try_to_create_and_prep_directory_at(args.output, UNPACKED_FOLDER, parser)
    try_to_create_and_prep_directory_at(args.temp, TEMP_FILES_DIR, parser)

    # Ensure that the folder paths are formatted correctly: download and output
    # should have trailing slashes, but temp should not
    if args.download[-1] != "/":
        args.download += "/"
        print(args.download)
    if args.output[-1] != "/":
        args.output += "/"
        print(args.output)
    if args.temp[-1] == "/":
        args.temp = args.temp[:-1]
        print(args.temp)

    return args


def validate_dir_path(dir_path, parser):
    """
    Validate that a given path refers to an existing directory; if it doesn't,
    then raise an argparse error
    :param dir_path: Path to validate
    :param parser: argparse ArgumentParser to raise error if path is invalid
    :return: N/A
    """
    if not Path(dir_path).is_dir():
        parser.error(dir_path + " is not an existing directory.")


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
        Path(folder_path).mkdir(exist_ok=True, parents=True)
    except (OSError, TypeError):
        parser.error("Could not create folder at " + folder_path)

    # If user gave a different directory than the default, then copy the
    # required files into that directory and nothing else
    default = Path(default_path)
    if Path(folder_path).resolve() != default.resolve():
        for file in default.iterdir():
            if not file.is_dir():
                shutil.copy2(str(file), folder_path)


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
    for temp_dir_subdir in Path(temp_dir).iterdir():
        if temp_dir_subdir.is_dir():
            shutil.rmtree(str(temp_dir_subdir))

    # Inform user that temporary files were deleted, then terminate wrapper
    print("\nTemporary files in " + temp_dir + " deleted. ABCD to BIDS "
          "wrapper terminated.")
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
    if not args.username and not args.password and Path(args.config).exists():
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
        if args.password:
            password = args.password
        else:
            password = getpass("Enter your NIMH Data Archives password: ")

        make_config_file(args.config, username, password)

    # Try to make NDA token
    token_call_exit_code = subprocess.call([
        "python3",
        NDA_AWS_TOKEN_MAKER,
        username,
        password
    ])

    # If NDA credentials are invalid, tell user so without printing password.
    # Manually catch error instead of using try-except to avoid trying to
    # catch another file's exception.
    if token_call_exit_code is not 0:
        print("Failed to create NDA token using the username and decrypted "
              "password from " + str(Path(args.config).resolve()))
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
    encrypted_password = (
        Fernet(encryption_key).encrypt(password.encode("UTF-8"))
    )

    # Save the encryption key and encrypted password to a new config file
    config["NDA"] = {
        "username": username,
        "encrypted_password": encrypted_password.decode("UTF-8"),
        "key": encryption_key.decode("UTF-8")
    }
    with open(config_filepath, "w") as configfile:
        config.write(configfile)

    # Change permissions of the config file to prevent other users accessing it
    subprocess.check_call(["chmod", "700", config_filepath])


def create_good_and_bad_series_table(cli_args):
    """
    Create good_and_bad_series_table.csv using compiled MATLAB data_gatherer.
    :param cli_args: argparse namespace containing all CLI arguments. This function
    only uses the --mre_dir argument.
    :return: N/A
    """
    print("\ndata_gatherer to create good_and_bad_series_table started at:")
    subprocess.check_call("date")
    try:
        subprocess.check_call([DATA_GATHERER, cli_args.mre_dir])

    # If user does not have the right spreadsheets in the right location, then
    # inform the user instead of spitting out an unhelpful stack trace
    except subprocess.CalledProcessError:
        print("Error: data_gatherer failed. Please check that the "
              "./spreadsheets/ folder contains image03.txt and "
              "DAL_ABCD_QC_merged_pcqcinfo.csv, then run this script again.")
        sys.exit(1)

    print("\ndata_gatherer finished at:")
    subprocess.check_call('date')


def download_nda_data(cli_args):
    """
    Download NDA data by making NDA token and parsing the
    good_and_bad_series_table.csv spreadsheet.
    :param cli_args: argparse namespace containing all CLI arguments. This
    function only uses the --download argument, the path to the folder to fill
    with downloaded NDA data.
    :return: N/A
    """
    # Call Python script to parse good_and_bad_series_table and download data
    print("\nDownloading ABCD data from NDA. Download started at:")
    subprocess.check_call("date")
    subprocess.check_call([
        "python3",
        GOOD_BAD_SERIES_PARSER,
        cli_args.download
    ])
    print("\nABCD data download finished at:")
    subprocess.check_call("date")


def unpack_and_setup(args):
    """
    Run unpack_and_setup.sh script to unpack and setup the newly downloaded
    NDA data files.
    :param args: All arguments entered by the user from the command line. The
    specific arguments used by this function are fsl_dir, mre_dir, --output,
    --download, --temp, and --remove.
    :return: N/A
    """
    print("\nData unpacking and setup started at:")
    subprocess.check_call("date")

    # Get name of NDA data folder newly downloaded from download_nda_data
    download_folder = Path(args.download)

    # Unpack and setup every .tgz file descendant of the NDA data folder
    for subject in download_folder.iterdir():
        if subject.is_dir():
            for session_dir in subject.iterdir():
                if session_dir.is_dir():
                    for tgz in session_dir.iterdir():
                        if tgz:

                            # Get session ID from some (arbitrary) .tgz file in
                            # session folder
                            session_name = tgz.name.split("_")[1]

                            # Unpack/setup the data for this subject/session
                            subprocess.check_call([
                                UNPACK_AND_SETUP,
                                subject.name,
                                "ses-" + session_name,
                                str(session_dir.resolve()),
                                args.output,
                                args.temp,
                                args.fsl_dir,
                                args.mre_dir
                            ])

                            # If user said to, delete all the raw downloaded
                            # files for each subject after that subject's data
                            # has been processed and copied
                            if args.remove:
                                shutil.rmtree(args.download + subject.name)

                            break

    print("\nUnpacking and setup finished at:")
    subprocess.check_call("date")


def correct_jsons(cli_args):
    """
    Correct ABCD BIDS input data to conform to official BIDS Validator.
    :param cli_args: argparse namespace containing all CLI arguments. This
    function only uses the --output argument, the path to the folder containing
    corrected NDA data to validate.
    :return: N/A
    """
    print("\nJSON correction started at:")
    subprocess.check_call("date")
    subprocess.check_call([CORRECT_JSONS, cli_args.output])
    print("\nJSON correction finished at:")
    subprocess.check_call("date")


def run_bids_validator(cli_args):
    """
    Run the official BIDS validator on the corrected ABCD BIDS data.
    :param cli_args: argparse namespace containing all CLI arguments. This
    function only uses the --output argument, the path to the folder containing
    corrected NDA data to validate.
    :return: N/A
    """

    print("\nBIDS validation started at:")
    subprocess.check_call("date")
    try:
        subprocess.check_call(["docker", "run", "-ti", "--rm", "-v",
                               os.path.abspath(cli_args.output) + ":/data:ro",
                               "bids/validator", "/data"])

        # If BIDS validation is successful, then delete directory/ies holding
        # temporary files which were generated by unpack_and_setup
        print("\nBIDS validation finished at:")
        subprocess.check_call("date")

    except subprocess.CalledProcessError:
        print("Error: BIDS validation failed.")


if __name__ == '__main__':
    main()
