#! /usr/bin/env python3

"""
ABCD 2 BIDS CLI Wrapper
Greg Conan
Created 2019-05-29
Last Updated 2019-06-06
"""

##################################
#
# Wrapper for ABCD DICOM to BIDS pipeline that can be run from the command line
#    1. Runs data_gatherer to create ABCD_good_and_bad_series_table.csv
#    2. Runs good_bad_series_parser to download ABCD data using that .csv table
#    3. Runs unpack_and_setup.sh to unpack/setup the downloaded ABCD data
#    4. Runs correct_jsons
#
##################################

import argparse
import getpass
import pathlib
import subprocess


# Constants: Paths to scripts to call from this wrapper
DATA_GATHERER = "./bin/run_data_gatherer.sh"
NDA_AWS_TOKEN_MAKER = "./nda_aws_token_maker.py"
GOOD_BAD_SERIES_PARSER = "./good_bad_series_parser.py"
UNPACK_AND_SETUP = "./unpack_and_setup.sh"
DOWNLOAD_FOLDER = "./new_download/"
UNPACKED_FOLDER = "./ABCD-HCP/"
CORRECT_JSONS = "./correct_jsons.py"


def main():

    # Get CLI args
    cli_args = cli()

    # 1. Use MATLAB script to create good_and_bad_series_table.csv
    create_good_and_bad_series_table()

    # 2. Parse good_and_bad_series_table.csv to get NDA data
    download_nda_data(cli_args)

    # 3. Once NDA data is downloaded, unpack it & set it up using .sh script
    unpack_and_setup(cli_args.download, cli_args.output)

    # 4. Correct ABCD BIDS input data to conform to official BIDS Validator
    correct_jsons(cli_args.output)

    # 5. Run the official BIDS validator on the corrected ABCD BIDS data
    run_bids_validator(cli_args.output)


def cli():
    """
    Get and validate all args from command line using argparse.
    :return: Namespace containing all validated inputted command line arguments
    """

    # Create arg parser
    parser = argparse.ArgumentParser(
        description="Wrapper to download and parse QC'd ABCD data."
    )

    # Optional: Get NDA username and password
    parser.add_argument(
        "-u",
        "--username",
        type=str,
        help="Optional: NDA username. Unless this or --token is added, "
             + "the user will be prompted for their NDA username and password."
             + " If this is added, --password must also be added."
    )
    parser.add_argument(
        "-p",
        "--password",
        type=str,
        help="Optional: NDA password. Unless this or --token is added, "
             + "the user will be prompted for their NDA username and password."
             + " If this is added, --username must also be added."
    )

    # Optional: Get path to already-existing NDA token
    parser.add_argument(
        "-t",
        "--token",
        type=argparse.FileType('r'),
        help="Optional: Path to already-existing NDA token credentials file. "
             + "Unless this option or --username and --password is added, the "
             + "user will be prompted for their NDA username and password."
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
        help="Optional: Folder path into which NDA data will be unpacked and "
             + "setup after it is downloaded. By default, this script will "
             + "place the data into a folder called " + UNPACKED_FOLDER
             + " as a subdirectory of the pwd."
    )

    args = parser.parse_args()

    # Validate that if username is present, so is password; and vice versa
    if bool(args.password is None) is not bool(args.username is None):
        parser.error("Error: Username and password must both be included.")

    # Validate download folder file path; if it doesn't exist, create it
    try:
        pathlib.Path(args.download).mkdir(exist_ok=True, parents=True)
    except (OSError, TypeError):
        parser.error("Error: Invalid download folder path.")

    return args


def create_good_and_bad_series_table():
    """
    Create good_and_bad_series_table .csv using compiled MATLAB script
    :return: N/A
    """
    subprocess.check_call([DATA_GATHERER])
    print("MATLAB subprocess finished.")


def download_nda_data(cli_args):
    """
    Download NDA data by parsing good_and_bad_series_table.csv, making NDA
    token if needed.
    :param cli_args: argparse namespace containing all CLI arguments.
    :return: N/A
    """

    # If NDA token does not already exist, then make one
    if not cli_args.token:

        # If user did not already enter NDA credentials, get them
        if not cli_args.username:
            username = input('Enter your NIMH Data Archives username: ')
            password = getpass.getpass(
                'Enter your NIMH Data Archives password: '
            )

        # If user entered NDA credentials as CLI args, use those
        else:
            username = cli_args.username
            password = cli_args.password

        # Call Python script to make NDA token
        subprocess.check_call([
            "python3",
            NDA_AWS_TOKEN_MAKER,
            username,
            password
        ])
        print("NDA token maker subprocess finished.")

    # Call Python script to parse good_and_bad_series_table.csv
    subprocess.check_call([
        "python3",
        GOOD_BAD_SERIES_PARSER,
        cli_args.download
    ])
    print("Good/bad series parser subprocess finished.")


def unpack_and_setup(download, output):
    """
    Run unpack_and_setup.sh script to unpack and setup the newly downloaded
    NDA data files.
    :param download: Path to folder of newly downloaded NDA data.
    :param output: Path to folder where unpacked data will be put.
    :return: N/A
    """

    # Get name of NDA data folder newly downloaded from download_nda_data
    download_folder = pathlib.Path(download)

    # Throw exception if the NDA data folder cannot be found at given path
    assert download_folder.is_dir(), "Could not find download folder"

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
                output
            ])
    print("Unpack and setup subprocess finished.")


def correct_jsons(output):
    """
    Correct ABCD BIDS input data to conform to official BIDS Validator.
    :param output: Path to folder containing unpacked NDA data to correct.
    :return: N/A
    """
    subprocess.check_call([
        CORRECT_JSONS,
        output
    ])
    print("JSON correction subprocess complete.")


def run_bids_validator(output):
    """
    Run the official BIDS validator on the corrected ABCD BIDS data.
    :param output: Path to folder containing corrected NDA data to validate.
    :return: N/A
    """
    subprocess.check_call(["docker", "run", "-ti", "--rm", "-v", output
                          + ":/data:ro", "bids/validator", "/data"])
    # Error: Got permission denied while trying to connect to the Docker daemon socket

    print("BIDS validation subprocess complete. ABCD 2 BIDS complete.")


if __name__ == '__main__':
    main()