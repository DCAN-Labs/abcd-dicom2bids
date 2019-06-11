#! /usr/bin/env python3

"""
ABCD 2 BIDS CLI Wrapper
Greg Conan
Created 2019-05-29
Last Updated 2019-06-11
"""

##################################
#
# Wrapper for ABCD DICOM to BIDS pipeline that can be run from the command line
#    1. Runs data_gatherer to create ABCD_good_and_bad_series_table.csv
#    2. Runs good_bad_series_parser to download ABCD data using that .csv table
#    3. Runs unpack_and_setup to unpack/setup the downloaded ABCD data
#    4. Runs correct_jsons to conform to official BIDS Validator
#    5. Runs BIDS validator on unpacked/setup data using Docker
#
##################################

import argparse
import os
import pathlib
import subprocess

# Constants: Default paths to scripts to call from this wrapper
DATA_GATHERER = "./bin/run_data_gatherer.sh"
NDA_AWS_TOKEN_MAKER = "./nda_aws_token_maker.py"
GOOD_BAD_SERIES_PARSER = "./good_bad_series_parser.py"
UNPACK_AND_SETUP = "./unpack_and_setup.sh"
DOWNLOAD_FOLDER = "./new_download/"
UNPACKED_FOLDER = "./ABCD-HCP/"
TEMP_FILES_DIR = "~/abcd-dicom2bids_unpack_tmp"
CORRECT_JSONS = "./correct_jsons.py"


def main():
    """
    Run entire process of downloading ABCD data from NDA data and validating
    that it meets BIDS standards.
    :return: N/A
    """
    cli_args = cli()

    # 1. Use MATLAB script to create good_and_bad_series_table.csv
    create_good_and_bad_series_table(cli_args.mre_dir)

    # 2. Parse good_and_bad_series_table.csv to get NDA data
    download_nda_data(cli_args)

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
              "Environment (MRE) version 9.1 or newer. This is used to run"
              "a compiled MATLAB script. This positional argument must be a"
              "valid path to an existing folder, ending with "
              "/Matlab2016bRuntime/v91")
    )

    # Optional: Get NDA username and password
    parser.add_argument(
        "-u",
        "--username",
        type=str,
        help=("Optional: NDA username. Unless this or --nda_token is added, "
              "the user will be prompted for their NDA username and password."
              " If this is added, --password must also be added.")
    )
    parser.add_argument(
        "-p",
        "--password",
        type=str,
        help=("Optional: NDA password. Unless this or --nda_token is added, "
              "the user will be prompted for their NDA username and password."
              " If this is added, --username must also be added.")
    )

    # Optional: Get path to already-existing NDA token
    parser.add_argument(
        "-n",
        "--nda_token",
        type=argparse.FileType('r'),
        help=("Optional: Path to already-existing NDA token credentials file. "
              "Unless this option or --username and --password is added, the "
              "user will be prompted for their NDA username and password.")
    )

    # Optional: Get download folder path from user as CLI arg
    parser.add_argument(
        "-d",
        "--download",
        default=DOWNLOAD_FOLDER,
        help="Optional: Folder path to which NDA data will be downloaded. "
             + "By default, this script will place the data into a folder "
             + "called " + DOWNLOAD_FOLDER + " as a subdirectory of the pwd."
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
    Create good_and_bad_series_table .csv using compiled MATLAB script, and
    display how long it takes to the user.
    :return: N/A
    """
    print("Running ABCD to BIDS wrapper. data_gatherer subprocess started at:")
    subprocess.check_call("date")
    subprocess.check_call([DATA_GATHERER, mre_dir])
    print("data_gatherer subprocess finished at:")
    subprocess.check_call('date')


def download_nda_data(args):
    """
    Download NDA data by parsing good_and_bad_series_table.csv, making NDA
    token if needed.
    :param args: argparse namespace containing all CLI arguments. The
    specific arguments used by this function are --username, --password,
    --download, and --nda_token.
    :return: N/A
    """

    # If NDA token does not already exist, then make one
    if not args.nda_token:

        # If user gave NDA credentials as CLI args, use those to make NDA token
        if args.username:
            subprocess.check_call([
                "python3",
                NDA_AWS_TOKEN_MAKER,
                args.username,
                args.password
            ])

        # Otherwise, let nda_aws_token_maker handle credentials and make token
        else:
            subprocess.check_call([
                "python3",
                NDA_AWS_TOKEN_MAKER,
            ])
        print("NDA token maker subprocess finished.")

    # Call Python script to parse good_and_bad_series_table and download data
    print("Downloading ABCD data from NDA. Download subprocess started at:")
    subprocess.check_call("date")
    subprocess.check_call([
        "python3",
        GOOD_BAD_SERIES_PARSER,
        args.download
    ])
    print("ABCD data download subprocess finished at:")
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
    print("Data unpacking and setup subprocess started at:")
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
    print("Unpack and setup subprocess finished at:")
    subprocess.check_call("date")


def correct_jsons(output):
    """
    Correct ABCD BIDS input data to conform to official BIDS Validator.
    :param output: Path to folder containing unpacked NDA data to correct.
    :return: N/A
    """
    print("JSON correction subprocess started at:")
    subprocess.check_call("date")
    subprocess.check_call([CORRECT_JSONS, output])
    print("JSON correction subprocess finished at:")
    subprocess.check_call("date")


def run_bids_validator(output, temp_dir):
    """
    Run the official BIDS validator on the corrected ABCD BIDS data.
    :param output: Path to folder containing corrected NDA data to validate.
    :param temp_dir: Path to folder containing temporary files (created while
    running unpack_and_setup function) to delete if BIDS validation succeeds.
    :return: N/A
    """
    print("BIDS validation subprocess started at:")
    subprocess.check_call("date")
    try:
        subprocess.check_call(["docker", "run", "-ti", "--rm", "-v",
                               os.path.abspath(output) + ":/data:ro",
                               "bids/validator", "/data"])

        # If BIDS validation is successful, then delete temporary files which
        # were generated by unpack_and_setup
        subprocess.check_call(["rm", "-rf", temp_dir])
        print("BIDS validation subprocess finished. Temporary files at "
              + temp_dir + " deleted. ABCD 2 BIDS completed at:")
        subprocess.check_call("date")

    except subprocess.CalledProcessError:
        print("Error: BIDS validation failed.")


if __name__ == '__main__':
    main()