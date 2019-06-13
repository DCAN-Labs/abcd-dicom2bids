#! /usr/bin/env python3

"""
ABCD 2 BIDS CLI Wrapper
Greg Conan: conan@ohsu.edu
Created 2019-05-29
Last Updated 2019-06-13
"""

##################################
#
# Wrapper for ABCD DICOM to BIDS pipeline that can be run from the command line
#    1. Runs data_gatherer to create ABCD_good_and_bad_series_table.csv
#    2. Runs good_bad_series_parser to download ABCD data using that .csv table
#    3. Runs unpack_and_setup to unpack/setup the downloaded ABCD data
#    4. Runs correct_jsons to conform to official BIDS validator
#    5. Runs BIDS validator on unpacked/setup data using Docker
#
##################################

import argparse
import configparser
from cryptography.fernet import Fernet
from getpass import getpass
import os
import pathlib
import subprocess

# Constants: Default paths to scripts to call from this wrapper
DATA_GATHERER = "./src/bin/run_data_gatherer.sh"
NDA_AWS_TOKEN_MAKER = "./src/nda_aws_token_maker.py"
GOOD_BAD_SERIES_PARSER = "./src/good_bad_series_parser.py"
UNPACK_AND_SETUP = "./src/unpack_and_setup.sh"
DOWNLOAD_FOLDER = "./raw/"
UNPACKED_FOLDER = "./data/"
TEMP_FILES_DIR = "./temp"
CORRECT_JSONS = "./src/correct_jsons.py"
CONFIG_FILEPATH = "./src/config.ini"


def main():
    """
    Run entire process of downloading ABCD data from NDA data and validating
    that it meets BIDS standards.
    :return: N/A
    """
    cli_args = cli()

    # 1. Use compiled MATLAB script to create good_and_bad_series_table
    create_good_and_bad_series_table(cli_args.mre_dir)

    # 2. Make NDA token and parse good_and_bad_series_table to get NDA data
    make_nda_token(cli_args)
    download_nda_data(cli_args.download)

    # 3. Once NDA data is downloaded, unpack it & set it up using .sh script
    unpack_and_setup(cli_args)

    # 4. Correct ABCD BIDS input data to conform to official BIDS Validator
    correct_jsons(cli_args.output)

    # 5. Run the official BIDS validator on the corrected ABCD BIDS data
    run_bids_validator(cli_args.output, cli_args.temp)


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
              "be a valid path to an existing folder, ending with /fsl/5.0")
    )

    # Required: Get path to MRE / MCR root to run compiled MATLAB script
    parser.add_argument(
        "mre_dir",
        type=str,
        help=("Required: Path to directory containing MATLAB Runtime "
              "Environment (MRE) version 9.1 or newer. This is used to run "
              "a compiled MATLAB script. This positional argument must be a "
              "valid path to an existing folder, ending with "
              "/Matlab2016bRuntime/v91")
    )

    # Optional: Get NDA username and password
    parser.add_argument(
        "-u",
        "--username",
        type=str,
        help=("Optional: NDA username. Unless this is added or a config file "
              "exists with the user's NDA credentials, the user will be "
              "prompted for them. If this is added, --password must be too.")
    )
    parser.add_argument(
        "-p",
        "--password",
        type=str,
        help=("Optional: NDA password. Unless this is added or a config file "
              "exists with the user's NDA credentials, the user will be "
              "prompted for them. If this is added, --username must be too.")
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
              "By default, the config file will be at " + CONFIG_FILEPATH
              + " as a subdirectory of the pwd.")
    )

    # Optional: Get download folder path from user as CLI arg
    parser.add_argument(
        "-d",
        "--download",
        default=DOWNLOAD_FOLDER,
        help=("Optional: Folder path to which NDA data will be downloaded. "
              "By default, this script will place the data into a folder "
              "called " + DOWNLOAD_FOLDER + " as a subdirectory of the pwd.")
    )

    # Optional: Get folder to unpack NDA data into from download folder
    parser.add_argument(
        "-o",
        "--output",
        default=UNPACKED_FOLDER,
        help=("Optional: Folder path into which NDA data will be unpacked and "
              "setup after it is downloaded. By default, this script will "
              "place the data into a folder called " + UNPACKED_FOLDER
              + " as a subdirectory of the pwd.")
    )

    # Optional: Get folder to place temp data into during unpacking
    parser.add_argument(
        "-t",
        "--temp",
        default=TEMP_FILES_DIR,
        help=("Optional: File path at which to create the directory which "
              "will be filled with temporary files during unpacking and setup."
              " By default, the temp folder will be created at "
              + TEMP_FILES_DIR + " and deleted once the script is finished.")
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

    # Validate that if username is present, so is password; and vice versa
    if bool(args.password is None) is not bool(args.username is None):
        parser.error("Username and password must both be included.")

    # Validate FSL and MRE directories
    validate_dir_path(args.fsl_dir, parser)
    validate_dir_path(args.mre_dir, parser)

    # Validate other dirs: check if they exist, and if not, try to create them
    try_to_create_directory_at(args.download, parser)
    try_to_create_directory_at(args.output, parser)

    return args


def validate_dir_path(dir_path, parser):
    """
    Validate that a given path refers to an existing directory; if it doesn't,
    then raise an argparse error
    :param dir_path: Path to validate
    :param parser: argparse ArgumentParser to raise error if path is invalid
    :return: N/A
    """
    if not pathlib.Path(dir_path).is_dir():
        parser.error(dir_path + " is not an existing directory.")


def try_to_create_directory_at(folder_path, parser):
    """
    Validate file path of folder; if it doesn't exist, create it
    :param folder_path: Path of folder that either exists or should be created
    :param parser: argparse ArgumentParser to raise error if path is invalid
    :return: N/A
    """
    try:
        pathlib.Path(folder_path).mkdir(exist_ok=True, parents=True)
    except (OSError, TypeError):
        parser.error("Could not create folder at " + folder_path)


def create_good_and_bad_series_table(mre_dir):
    """
    Create good_and_bad_series_table.csv using compiled MATLAB script.
    :return: N/A
    """
    print("\nRunning ABCD to BIDS wrapper. data_gatherer started at:")
    subprocess.check_call("date")
    subprocess.check_call([DATA_GATHERER, mre_dir])
    print("\ndata_gatherer finished at:")
    subprocess.check_call('date')


def make_nda_token(args):
    """
    Create NDA token by getting credentials from config file. If no config file
    exists yet, then create one to store NDA credentials.
    :param args: argparse namespace containing all CLI arguments. The specific
    arguments used by this function are --username, --password, and --config.
    :return: N/A
    """

    # If config file with NDA credentials exists, then get its credentials
    if pathlib.Path(args.config).exists():
        username, password = get_nda_credentials_from(args.config)

    # Otherwise, get NDA credentials and save them in a new config file
    else:

        # If user gave NDA credentials as CLI args, use those
        if args.username:
            username = args.username
            password = args.password

        # Otherwise, prompt user for NDA credentials
        else:
            username = input('Enter your NIMH Data Archives username: ')
            password = getpass('Enter your NIMH Data Archives password: ')

        make_config_file(args.config, username, password)

    # Try to make NDA token
    try:
        subprocess.check_call([
            "python3",
            NDA_AWS_TOKEN_MAKER,
            username,
            password
        ])

    # If NDA credentials are invalid, tell user so without printing password
    except subprocess.CalledProcessError:
        print("Failed to create NDA token using the username and decrypted "
              "password from " + str(pathlib.Path(args.config).absolute()))


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
    If there isn't a config file, create one to save user's NDA credentials.
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


def download_nda_data(download):
    """
    Download NDA data by making NDA token and parsing the
    good_and_bad_series_table.csv spreadsheet.
    :param download: Path of folder to fill with downloaded NDA data.
    :return: N/A
    """

    # Call Python script to parse good_and_bad_series_table and download data
    print("\nDownloading ABCD data from NDA. Download started at:")
    subprocess.check_call("date")
    subprocess.check_call([
        "python3",
        GOOD_BAD_SERIES_PARSER,
        download
    ])
    print("\nABCD data download finished at:")
    subprocess.check_call("date")


def unpack_and_setup(args):
    """
    Run unpack_and_setup.sh script to unpack and setup the newly downloaded
    NDA data files.
    :param args: All arguments entered by the user from the command line. The
    specific arguments used by this function are fsl_dir, mre_dir, --output,
    --download, and --temp.
    :return: N/A
    """
    print("\nData unpacking and setup started at:")
    subprocess.check_call("date")

    # Get name of NDA data folder newly downloaded from download_nda_data
    download_folder = pathlib.Path(args.download)

    # Unpack and setup every .tgz file descendant of the NDA data folder
    for subject in download_folder.iterdir():
        for session_dir in subject.iterdir():

            # Get session ID from some (arbitrary) .tgz file in session folder
            session_name = next(session_dir.iterdir()).name.split("_", 2)[1]

            # Unpack and setup the data for this subject and session
            subprocess.check_call([
                UNPACK_AND_SETUP,
                subject.name,
                "ses-" + session_name,
                str(session_dir),
                args.output,
                args.temp,
                args.fsl_dir,
                args.mre_dir
            ])
    print("\nUnpacking and setup finished at:")
    subprocess.check_call("date")


def correct_jsons(output):
    """
    Correct ABCD BIDS input data to conform to official BIDS Validator.
    :param output: Path to folder containing unpacked NDA data to correct.
    :return: N/A
    """
    print("\nJSON correction started at:")
    subprocess.check_call("date")
    subprocess.check_call([CORRECT_JSONS, output])
    print("\nJSON correction finished at:")
    subprocess.check_call("date")


def run_bids_validator(output, temp_dir):
    """
    Run the official BIDS validator on the corrected ABCD BIDS data.
    :param output: Path to folder containing corrected NDA data to validate.
    :param temp_dir: Path to folder containing temporary files (created while
    running unpack_and_setup function) to delete if BIDS validation succeeds.
    :return: N/A
    """
    print("\nBIDS validation started at:")
    subprocess.check_call("date")
    try:
        subprocess.check_call(["docker", "run", "-ti", "--rm", "-v",
                               os.path.abspath(output) + ":/data:ro",
                               "bids/validator", "/data"])

        # If BIDS validation is successful, then delete temporary files which
        # were generated by unpack_and_setup
        subprocess.check_call(["rm", "-rf", temp_dir + "/*"])
        print("\nBIDS validation subprocess finished. Temporary files at "
              + temp_dir + " deleted. ABCD to BIDS wrapper completed at:")
        subprocess.check_call("date")

    except subprocess.CalledProcessError:
        print("Error: BIDS validation failed.")


if __name__ == '__main__':
    main()
