# ABCD DICOM to BIDS

Written by the OHSU ABCD site for selectively downloading ABCD Study imaging DICOM data QC'ed as good by the ABCD DAIC site, converting it to BIDS standard input data, selecting the best pair of spin echo field maps, and correcting the sidecar JSON files to meet the BIDS Validator specification.

*Note: DWI has been added to the list of modalities that can be downloaded. This has resulted in a couple important changes to the scripts included here and the output BIDS data. Most notably, fieldmaps now include an acquisition field in their filenames to differentiate those used for functional images and those used for DWI (e.g. ..._acq-func_... or ..._acq-dwi_...). Data uploaded to [Collection 3165](https://github.com/ABCD-STUDY/nda-abcd-collection-3165), which was created using this repository, does not contain this identifier.*

## Installation

Clone this repository and save it somewhere on the Linux system you want to do ABCD DICOM downloads and conversions to BIDS on.

## Dependencies

1. [Python 3.5.2](https://www.python.org/downloads/release/python-352/)
1. [jq](https://stedolan.github.io/jq/download/) version 1.6 or higher
1. [MathWorks MATLAB Runtime Environment (MRE) version 9.1 (R2016b)](https://www.mathworks.com/products/compiler/matlab-runtime.html)
1. [cbedetti Dcm2Bids](https://github.com/cbedetti/Dcm2Bids) (`export` into your BASH `PATH` variable)
1. [Rorden Lab dcm2niix](https://github.com/rordenlab/dcm2niix) (`export` into your BASH `PATH` variable)
1. [dcmdump](https://dicom.offis.de/dcmtk.php.en) (`export` into your BASH `PATH` variable)
1. [zlib's pigz-2.4](https://zlib.net/pigz) (`export` into your BASH `PATH` variable)
1. Docker (see documentation for [Docker Community Edition for Ubuntu](https://docs.docker.com/install/linux/docker-ce/ubuntu/))
1. [FMRIB Software Library (FSL) v5.0](https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/FslInstallation)
1. Python [`cryptography` package](https://cryptography.io/en/latest/)
1. Python [`pandas` package](https://pandas.pydata.org)
1. [AWS CLI (Amazon Web Services Command Line Interface) v19.0.0](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-install.html)

## Spreadsheet (not included)

To download images for ABCD you must have the `abcd_fastqc01.csv` spreadsheet downloaded to this repository's `spreadsheets` folder. It can be downloaded from the [NIMH Data Archive (NDA)](https://nda.nih.gov/) with an ABCD Study Data Use Certification in place. `abcd_fastqc01.csv` contains operator QC information for each MRI series. If the image fails operator QC (a score of 0), then the image will not be downloaded.

### How to Download `abcd_fastqc01.csv`

1. Login to the [NIMH Data Archive](https://nda.nih.gov/).
1. From the homepage, click the button labeled `GET DATA` to go to `Featured Datasets`.
1. Under the `Data Dictionary` heading in the sidebar, click `Data Structures`.
1. Add `abcd_fastqc01.csv` to the Filter Cart.
    1. Enter the spreadsheet file name into the `Text Search` box to find `ABCD Fasttrack QC Instrument`, then click its checkbox to select it.
    1. At the bottom of the page, click the `Add to Workspace` button.
1. At the top-right corner of the page under `logout` is a small icon. Click on it to open the `Selected Filters Workspace`.
1. Click `Submit to Filter Cart` at the bottom of the workspace.
1. Wait until the `Filter Cart` window at the top-right no longer says `Updating Filter Cart`. 
1. Once the Filter Cart is updated, click `Package/Add to Study` in the `Filter Cart` window.
1. Click one of the buttons that says `Create Package`
    - Name each package something like **abcdQC**.
    - Select Only **Include documentation**.
    - Click **Create Package**.
1. From your NDA dashboard, click `Packages`.
1. Click the `Download Manager` button to download an executable `.jnlp` file. Once it downloads, run it to install the NDA Download Manager on your local machine.
1. Enter your NDA username and password in the window that pops up.
1. Accept the terms and conditions.
1. Click the checkbox at the left side of the window next to the file that you downloaded (e.g. `abcdQC`).
    - If you want to save the file to a different location than your home directory, click the `Browse` button at the top of the window.
1. Once the `Status` column of your package says `Ready to Download`, click `Start Downloads` at the bottom of the page to begin the download.
    - To track your download's progress at any given point, click the `Refresh Queue` button at the top of the window.  
1. Once the `Status` column of your file says `Download Complete`, your file is ready.

## Usage

The DICOM to BIDS process can be done by running the `abcd2bids.py` wrapper from within the directory cloned from this repo. `abcd2bids.py` requires two positional arguments and can take several optional arguments. Those positional arguments are file paths to the FSL directory and the MATLAB Runtime Environment. Here is an example of a valid call of this wrapper:

```sh
python3 abcd2bids.py <FSL directory> <Matlab2016bRuntime v9.1 compiler runtime directory>
```

The first time that a user uses this wrapper, the user will have to enter their NDA credentials. If the user does not include them as command-line arguments, then the wrapper will prompt the user to enter them. The wrapper will then create a `config.ini` file with the user's username and (encrypted) password, so the user will not have to enter their NDA credentials any subsequent times running this wrapper.

If the user already has a `config.ini` file, then the wrapper can use that, so the user does not need to enter their NDA credentials again. However, to make another `config.ini` file or overwrite the old one, the user can enter their NDA credentials as command-line args.

### Disk Space Usage Warnings

This wrapper will download NDA data (into the `raw/` subdirectory by default) and then copy it (into the `data/` subdirectory by default) to convert it, without deleting the downloaded data unless the `--remove` flag is added. The downloaded and converted data will take up a large amount of space on the user's filesystem, especially for converting many subjects. About 3 to 7 GB of data or more will be produced by downloading and converting one subject session, not counting the temporary files in the `temp/` subdirectory.

This wrapper will create a temporary folder (`temp/` by default) with hundreds of thousands of files (about 7 GB or more) per subject session. These files are used in the process of preparing the BIDS data. The wrapper will delete that temporary folder once it finishes running, even if it crashes. Still, it is probably a good idea to double-check that the temporary folder has no subdirectories before and after running this wrapper. Otherwise, this wrapper might leave an extremely large set of unneeded files on the user's filesystem.

### Optional Arguments

`--username` and `--password`: Include one of these to pass the user's NDA credentials from the command line into a `config.ini` file. This will create a new config file if one does not already exist, or overwrite the existing file. If only one of these flags is included, the user will be prompted for the other. They can be passed into the wrapper from the command line like so: `--username <NDA username> --password <NDA password>`.

`--config`: By default, the wrapper will look for a `config.ini` file in a hidden subdirectory of the user's home directory (`~/.abcd2bids/`). Use `--config` to enter a different (non-default) path to the config file, e.g. `--config ~/Documents/config.ini`.

`--temp`: By default, the temporary files will be created in the `temp/` subdirectory of the clone of this repo. If the user wants to place the temporary files anywhere else, then they can do so using the optional `--temp` flag followed by the path at which to create the directory containing temp files, e.g. `--temp /usr/home/abcd2bids-temporary-folder`. A folder will be created at the given path if one does not already exist.

`--subject-list`: By default, all subjects will be downloaded and converted. If only a subset of subjects are desired then specify a path to a .txt file containing a list of subjects (each on their own line) to download. If none is provided this script will attempt to download and convert every subject, which may take weeks to complete. It is recommended to run in parallel on batches of subjects.

`--modalities`: By default, the wrapper will download all modalities from each subject. This is equivalent to `--modalities ['anat', 'func', 'dwi']`. If only certain modalities should be downloaded for a subject then provide a list, e.g. `--modalities ['anat', 'func']`

`--download`: By default, the wrapper will download the ABCD data to the `raw/` subdirectory of the cloned folder. If the user wants to download the ABCD data to a different directory, they can use the `--download` flag, e.g. `--download ~/abcd-dicom2bids/ABCD-Data-Download`. A folder will be created at the given path if one does not already exist.

`--qc`: Path to the Quality Control (QC) spreadsheet file downloaded from the NDA. By default, the wrapper will use the `abcd_fastqc01.txt` file in the `spreadsheets` directory.

`--remove`: By default, the wrapper will download the ABCD data to the `raw/` subdirectory of the cloned folder. If the user wants to delete the raw downloaded data for each subject after that subject's data is finished converting, the user can use the `--remove` flag without any additional parameters.

`--output`: By default, the wrapper will place the finished/converted data into the `data/` subdirectory of the cloned folder. If the user wants to put the finished data anywhere else, they can do so using the optional `--output` flag followed by the path at which to create the directory, e.g. `--output ~/abcd-dicom2bids/Finished-Data`. A folder will be created at the given path if one does not already exist.

`--start-at`: By default, this wrapper will run every step listed below in that order. Use this flag to start at one step and skip all of the previous ones. To do so, enter the name of the step. E.g. `--start-at correct_jsons` will skip every step before JSON correction.

1. create_good_and_bad_series_table
2. download_nda_data
3. unpack_and_setup
4. correct_jsons
5. validate_bids

`--stop-before`: To run every step until a specific step, and skip every step after it, use this flag with the name of the first step to skip. E.g. `--stop-before unpack_and_setup` will only run the first two steps.

For more information including the shorthand flags of each option, use the `--help` command: `python3 abcd2bids.py --help`.

Here is the format for a call to the wrapper with more options added:

```sh
python3 abcd2bids.py <FSL directory> <Matlab2016bRuntime v9.1 compiler runtime directory> --username <NDA username> --download <Folder to place raw data in> --output <Folder to place converted data in> --temp <Directory to hold temporary files> --remove
```

## Explanation of Process

`abcd2bids.py` is a wrapper for 4 distinct scripts, which previously needed to be run on their own in sequential order:

1. (Python) `good_bad_series_parser.py`
2. (BASH) `unpack_and_setup.sh`
3. (Python) `correct_jsons.py`
4. (Docker) Official BIDS validator

The DICOM 2 BIDS conversion process can be done by running `python3 abcd2bids.py <FSL directory> <MRE directory>` without any other options. First, the wrapper will try to create an NDA token with the user's NDA credentials. It does this by calling `src/nda_aws_token_maker.py`, which calls `src/nda_aws_token_generator` ([taken from the NDA](https://github.com/NDAR/nda_aws_token_generator)). If the wrapper cannot find a `config.ini` file with those credentials, and they are not entered as command line args, then the user will be prompted to enter them.

### Preliminary Steps

As its first step, the wrapper will call `nda_aws_token_maker.py`. If successful, `nda_aws_token_maker.py` will create a `credentials` file in the `.aws/` subdirectory of the user's `home` directory. 

Next, the wrapper will produce a download list for the Python & BASH portion to download, convert, select, and prepare. The two spreadsheets referenced above are used to create the `ABCD_good_and_bad_series_table.csv` which gets used to actually download the images. If successful, this script will create the file `ABCD_good_and_bad_series_table.csv` in the `spreadsheets/` subdirectory. This step was previously done by a compiled MATLAB script called `data_gatherer`, but now the wrapper has its own functionality to replace that script.

**NOTE:** This step can take over two hours to complete.

### 1. (Python) `aws_downloader.py`

Once `ABCD_good_and_bad_series_table.csv` is successfully created, the wrapper will run `src/aws_downloader.py` with this repository's cloned folder as the present working directory to download the ABCD data from the NDA website. It requires the `ABCD_good_and_bad_series_table.csv` spreadsheet under a `spreadsheets` subdirectory of this repository's cloned folder.

`src/aws_downloader.py` also requires a valid NDA token in the `.aws/` folder in the user's `home/` directory. If successful, this will download the ABCD data from the NDA site into the `raw/` subdirectory of the clone of this repo. If the download crashes and shows errors about `awscli`, try making sure you have the [latest AWS CLI installed](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-install.html), and that the [`aws` executable is in your BASH `PATH` variable](https://docs.aws.amazon.com/cli/latest/userguide/install-linux.html#install-linux-path).

### 2. (BASH) `unpack_and_setup.sh`

The wrapper will call `unpack_and_setup.sh` in a loop to do the DICOM to BIDS conversion and spin echo field map selection, taking seven arguments:

```sh
SUB=$1 # Full BIDS formatted subject ID (sub-SUBJECTID)
VISIT=$2 # Full BIDS formatted session ID (ses-SESSIONID)
TGZDIR=$3 # Path to directory containing all TGZ files for SUB/VISIT
ROOTBIDSINPUT=$4 Path to output folder which will be created to store unpacked/setup files
ScratchSpaceDir=$5 Path to folder which will be created to store temporary files that will be deleted once the wrapper finishes
FSL_DIR=$6 # Path to FSL directory
MRE_DIR=$7 # Path to MATLAB Runtime Environment (MRE) directory
```

By default, the wrapper will put the unpacked/setup data in the `data/` subdirectory of this repository's cloned folder. This step will also create and fill the `temp/` subdirectory of the user's home directory containing temporary files used for the download. If the user enters other locations for the temp directory or output data directory as optional command line args, then those will be used instead.

### 3. (Python) `correct_jsons.py`

Next, the wrapper runs `correct_jsons.py` on the whole BIDS directory (`data/` by default) to correct/prepare all BIDS sidecar JSON files to comply with the BIDS specification standard version 1.2.0.

### 4. (Docker) Run Official BIDS Validator

Finally, the wrapper will run the [official BIDS validator](https://github.com/bids-standard/bids-validator) using Docker to validate the final dataset created by this process in the `data/` subdirectory.

## Inside the `data` subdirectory

The following files belong in the `data` subdirectory to run `abcd2bids.py`:

1. `CHANGES`
2. `dataset_description.json`
3. `task-MID_bold.json`
4. `task-nback_bold.json`
5. `task-rest_bold.json`
6. `task-SST_bold.json`

Without these files, the output of `abcd2bids.py` will fail BIDS validation. They should be downloaded from the GitHub repo by cloning it.

`data` is where the output of `abcd2bids.py` will be placed by default. So, after running `abcd2bids.py`, this folder will have subdirectories for each subject session. Those subdirectories will be correctly formatted according to the [official BIDS specification standard v1.2.0](https://github.com/bids-standard/bids-specification/releases/tag/v1.2.0).

The resulting ABCD Study dataset here is made up of all the ABCD Study participants' imaging data that passed initial acquisition quality control (MRI QC).

## Attributions

This wrapper relies on the following other projects:
- [cbedetti Dcm2Bids](https://github.com/cbedetti/Dcm2Bids)
- [Rorden Lab dcm2niix](https://github.com/rordenlab/dcm2niix)
- [zlib's pigz-2.4](https://zlib.net/pigz)
- [Official BIDS validator](https://github.com/bids-standard/bids-validator) 
- [NDA AWS token generator](https://github.com/NDAR/nda_aws_token_generator)
- [dcmdump](https://dicom.offis.de/dcmtk.php.en)

## Meta

Documentation last updated by Greg Conan on 2020-06-29.
