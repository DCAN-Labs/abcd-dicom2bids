# ABCD DICOM to BIDS

Written by the OHSU ABCD site for selectively downloading ABCD Study imaging DICOM data QC'ed as good by the ABCD DAIC site, converting it to BIDS standard input data, selecting the best pair of spin echo field maps, and correcting the sidecar JSON files to meet the BIDS Validator specification. 
For information on [Collection 3165, see here](https://github.com/ABCD-STUDY/nda-abcd-collection-3165).

## Installation

Clone this repository, install requirements listed in `src/requirements.txt` ***and*** the dependencies listed below.

## Dependencies

1. [Python 3.6.8](https://www.python.org/downloads/release/python-368/)+
1. [jq](https://stedolan.github.io/jq/download/) version 1.6 or higher
1. [MathWorks MATLAB Runtime Environment (MRE) version 9.1 (R2016b)](https://www.mathworks.com/products/compiler/matlab-runtime.html)
1. [cbedetti Dcm2Bids version X](https://github.com/cbedetti/Dcm2Bids) (`export` into your BASH `PATH` variable)
1. [Rorden Lab dcm2niix version X](https://github.com/rordenlab/dcm2niix) (`export` into your BASH `PATH` variable) version v1.0.20201102 (WARNING: older versions of dcm2niix have failed to properly convert DICOMs)
1. [dcmdump version 3.6.5 or higher](https://dicom.offis.de/dcmtk.php.en) (`export` into your BASH `PATH` variable)
1. [zlib's pigz-2.4](https://zlib.net/pigz) (`export` into your BASH `PATH` variable)
1. Singularity or Docker (see documentation for [Docker Community Edition for Ubuntu](https://docs.docker.com/install/linux/docker-ce/ubuntu/))
1. [FMRIB Software Library (FSL) v5.0](https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/FslInstallation)

We recommend creating a virtual environment for Python by running:

```
python3 -m venv env
source env/bin/activate
```

Then install the specified versions of all required python packages by running:

```
pip install -r src/requirements.txt
```

If encountering errors during the package download process, try running `pip install --upgrade setuptools`. Then check to see if this fixed any download errors by rerunning `pip install -r src/requirements.txt`

## Downloading Data Packages

There are two methods of downloading data packages from the NDA. They can be downloaded through a GUI found [here](https://nda.nih.gov/nda/nda-tools.html#download-manager-beta) or from the command line using `downloadcmd`, which can be installed with `pip install nda-tools==0.2.22`. Follow instructions provided by the NDA depending on your preferred method to download the ABCD Fasttrack QC. Run `downloadcmd -h` for usage information. 

If using `downloadcmd` option, the "Updating Stored Passwords with keyring" step on the [nda-tools](https://github.com/NDAR/nda-tools) ReadMe will still be necessary because if you want to download a specific subject from the package you will need to use both nda-tools and keyring. If downloading every subject all at once, then just using the download manager will suffice. The default is to now download all tasks regardless of run number where as before it would only download if and only if there were two runs (Version # HERE).

The contents of `~/.config/python_keyring/keyringrc.cfg` should be:
```
[backend]
 default-keyring=keyrings.alt.file.PlaintextKeyring
 keyring-path=/tmp/work
```
After the contents of `keyringrc.cfg` have been properly edited, run these commands to see if your password for nda-tools is up to date. Be aware that this will display your password in the terminal:
```
python3
import keyring
keyring.get_password("nda-tools", "USERNAME")
```
If the correct password is not returned, then running `keyring.set_password("nda-tools", "username", "password")` should fix the issue. 

If you are experiencing the following error `ModuleNotFoundError: No module named 'keyrings'`, it is most likely due to an outdated version of `keyrings.alt`. Running the command `pip list | grep keyring` will result in the current versions for `keyring` and `keyrings.alt` on your system. To avoid the error, `keyring` and `keyrings.alt` should be updated to versions `23.13.1` and `3.1` respectively. If `keyrings.alt` is outdated, then run `pip install keyrings.alt`.

Important Note: your NDA password and keyring password cannot differ. It's also important to be careful when using exclamation marks or other special characters in the password that can trigger keyring issues/errors.

## Data Packages

Skip this section if you already have the necessary packages downloaded. You will just need the Package ID info when running `abcd2bids.py`.

### NDA QC Spreadsheet (not included)

To download images for ABCD you must have the `abcd_fastqc01.csv` spreadsheet downloaded to this repository's `spreadsheets` folder. It can be downloaded from the [NIMH Data Archive (NDA)](https://nda.nih.gov/) with an ABCD Study Data Use Certification in place. `abcd_fastqc01.csv` contains operator QC information for each MRI series. If the image fails operator QC (a score of 0), then the image will not be downloaded.

#### How to Download `abcd_fastqc01.csv`

1. Login to the [NIMH Data Archive](https://nda.nih.gov/).
2. From the homepage, click `Get Data`
3. Under the `Data Dictionary` heading in the sidebar, click `Data Structures`.
4. Enter `ABCD Fasttrack QC Instrument` into the `Text Search` box then select `ABCD Fasttrack QC Instrument`
5. At the bottom of the page, click the `Add to Workspace` button.
6. Your `Filter Cart` should appear at the top-right corner of the page (it will take a minute to load). Click on `Create Data Package/Add Data to Study` once it has finished loading.
7. Make sure that the ABCD Dataset and ABCD Fasttrack QC Instrument checkboxes are selected (they should be by default)
8. Click `Create Data Package`
    - Name the package something informative like **abcdQC** (note: special characters are not allowed).
    - Select Only **Include documentation**.
    - Click **Create Data Package**.
9. Navigate to your NDA dashboard and from your NDA dashboard, click `DataPackages`. You should see the data package that you just created with a status of "Creating Package". It takes roughly 10 minutes for the NDA to create this package.
10. When the Data package is ready to download the status will change to "Ready to Download"

Make note of the Package ID number (found in the `Data Packages` table). You will need to input this in the run command as `downloadcmd -dp <PackageID>`. If you dont specify an ouput directory the package will be downloaded here: `~/NDA/nda-tools/downloadcmd/packages/<PackageID>/`.

The contents of the data package after it has been downloaded should look like this:

```
.
├── abcd_fastqc01.txt
├── dataset_collection.txt
├── guid_pseudoguid.txt
├── package_info.txt
└── README.pdf
```

#### How to Create an NDA Image Data Package

1. Follow steps 1-3 from "How to Download `abcd_fastqc01.csv`"
1. In the `Text Search` window enter `image03` and click `Apply`.
    - You should see a single result with the heading `Image`.
1. Click on the `Image` heading.
1. At the bottom of the page click `Add to Filter Cart`.
1. Wait until the `Filter Cart` window at the top-right no longer says `Updating Filter Cart`. 
1. Once the Filter Cart is updated, click `Create Data Package/Add to Study` in the `Filter Cart` window.
1. In the left hand box titled `Collections by Permission Group` click `Deselect All`.
1. Search for `fasttrack` using find (e.g. Ctrl-F or Cmd-F)
1. Select the box next to `[2573] Adolescent Brain Cognitive Development Study (ABCD)`
1. Scroll to the bottom of the page and click `Create Data Package`
1. Name the Package something informative and make sure to check the box that says `Include Associated Data Files`
1. Finally click `Create Data Package`

This data package is roughly 71TB in size and may take up to a day to be created. You can check the status of this package by navigating to the `Data Packages` tab within your profile. You should see your newly created package at the top of the table with a status of `Creating Package`. Wait until the status changes to `Ready to Download` before proceeding with next steps.

Make note of the Package ID number (found in the `Data Packages` table). You will need to input this in the run command as `downloadcmd -dp <PackageID>`. If you dont specify an ouput directory the package will be downloaded here: `~/NDA/nda-tools/downloadcmd/packages/<PackageID>/`

## Usage
```
usage: abcd2bids.py [-h] [-c CONFIG] [-d DOWNLOAD] [-o OUTPUT] [-q QC] 
                    -p PACKAGE_ID [--downloadcmd DOWNLOADCMD] -l SUBJECT_LIST
                    [-y {baseline_year_1_arm_1,2_year_follow_up_y_arm_1} [{baseline_year_1_arm_1,2_year_follow_up_y_arm_1} ...]] 
                    [-m {anat,func,dwi} [{anat,func,dwi} ...]] [-r]
                    [-s {reformat_fastqc_spreadsheet,download_nda_data,unpack_and_setup,correct_jsons,validate_bids}] 
                    [-t TEMP] [-u USERNAME] [-z DOCKER_CMD] [-x SIF_PATH]
                    fsl_dir mre_dir

Wrapper to download, parse, and validate QC'd ABCD data.

positional (and required) arguments:
  fsl_dir               Required: Path to FSL directory. This positional
                        argument must be a valid path to an existing folder.
  mre_dir               Required: Path to directory containing MATLAB Runtime
                        Environment (MRE) version 9.1 or newer. This is used
                        to run a compiled MATLAB script. This positional
                        argument must be a valid path to an existing folder. 
                        Note: MRE will ouput cached files into INSERT PATH in 
                        your home directory. This will need to be cleared out 
                        regularly in order to avoid filling up the system you 
                        are running abcd2bids.py on.
  -q QC, --qc QC        Path to Quality Control (QC) spreadsheet file
                        downloaded from the NDA.
  -l SUBJECT_LIST, --subject-list SUBJECT_LIST
                        Path to a .txt file containing a list of subjects to
                        download. Subjects should appear as 'sub-NDAID' without
                        quotations.
  -p PACKAGE_ID, --package_id PACKAGE_ID
                        Package ID number of relevant NDA data package.
  --downloadcmd DOWNLOADCMD
                        Path to wherever the downloadcmd has been installed
optional arguments:
  -h, --help            show this help message and exit
  -c CONFIG, --config CONFIG
                        Path to config file with NDA credentials. If no config
                        file exists at this path yet, then one will be
                        created. Unless this option or --username and
                        --password is added, the user will be prompted for
                        their NDA username and password. By default, the
                        config file will be located at
                        ~/.abcd2bids/config.ini
  -d DOWNLOAD, --download DOWNLOAD
                        Path to folder which NDA data will be downloaded into.
                        By default, data will be downloaded into the
                        ~/abcd-dicom2bids/raw folder. A folder will be created 
                        at the given path if one does not already exist.
  -o OUTPUT, --output OUTPUT
                        Folder path into which NDA data will be unpacked and
                        setup once downloaded. By default, this script will
                        put the data into the ~/abcd-dicom2bids/data folder. 
                        A folder will be created at the given path if one does 
                        not already exist.
  --password PASSWORD
                        NDA password. Adding this will create a new config
                        file or overwrite an old one. Unless this is added or
                        a config file exists with the user's NDA credentials,
                        the user will be prompted for them. If this is added
                        and --username is not, then the user will be prompted
                        for their NDA username.
  -y {baseline_year_1_arm_1,2_year_follow_up_y_arm_1} [{baseline_year_1_arm_1,2_year_follow_up_y_arm_1} ...], --sessions {baseline_year_1_arm_1,2_year_follow_up_y_arm_1} [{baseline_year_1_arm_1,2_year_follow_up_y_arm_1} ...]
                        List of sessions for each subject to download. The
                        default is to download all sessions for each subject.
                        The possible selections are ['baseline_year_1_arm_1',
                        '2_year_follow_up_y_arm_1']
  -m {anat,func,dwi} [{anat,func,dwi} ...], --modalities {anat,func,dwi} [{anat,func,dwi} ...]
                        List of the imaging modalities that should be
                        downloaded for each subject. The default is to
                        download all modalities. The possible selections are
                        ['anat', 'func', 'dwi']
  -r, --remove          After each subject's data has finished conversion,
                        removed that subject's unprocessed data.
  -s {reformat_fastqc_spreadsheet,download_nda_data,unpack_and_setup,correct_jsons,validate_bids}, --start_at {reformat_fastqc_spreadsheet,download_nda_data,unpack_and_setup,correct_jsons,validate_bids}
                        Give the name of the step in the wrapper to start at,
                        then run that step and every step after it. Here are
                        the names of all of the steps, in order from first to
                        last: reformat_fastqc_spreadsheet, download_nda_data,
                        unpack_and_setup, correct_jsons, validate_bids
  -t TEMP, --temp TEMP  Path to the directory to be created and filled with
                        temporary files during unpacking and setup. By
                        default, the folder will be created at
                        ~/abcd-dicom2bids/temp and deleted once the script finishes.
                        A folder will be created at the given path if one
                        doesn't already exist.
  -u USERNAME, --username USERNAME
                        NDA username. Adding this will create a new config
                        file or overwrite an old one. Unless this is added or
                        a config file exists with the user's NDA credentials,
                        the user will be prompted for them. If this is added
                        and --password is not, then the user will be prompted
                        for their NDA password.
  -z DOCKER_CMD, --docker-cmd DOCKER_CMD
                        A necessary docker command replacement on HPCs like
                        the one at OHSU, which has it's own special wrapper
                        fordocker for security reasons. Example:
                        '/opt/acc/sbin/exadocker'
  -x SIF_PATH, --singularity SIF_PATH
                        Use singularity and path the .sif file
```


The DICOM to BIDS process can be done by running the `abcd2bids.py` wrapper from within the directory cloned from this repo. `abcd2bids.py` requires four positional arguments and can take several optional arguments. Those positional arguments are file paths to the FSL directory, the MATLAB Runtime Environment, the QC spreadsheet, and the list of subjects to download. Here is an example of a valid call of this wrapper:
```
python3 abcd2bids.py <FSL directory> <Matlab2016bRuntime v9.1 compiler runtime directory> <Path to QC spreadsheet file downloaded from the NDA> <Path to a .txt file containing a list of subjects to download> <Package_ID> <Path to downloadcmd>
```
Example contents of SUBJECT_LIST file (not using any ABCC subject IDs):
```
sub-01
sub-02
```
The first time that a user uses this wrapper, the user will have to enter their NDA credentials. If the user does not include them as command-line arguments, then the wrapper will prompt the user to enter them. The wrapper will then create a `config.ini` file with the user's username and (encrypted) password, so the user will not have to enter their NDA credentials any subsequent times running this wrapper.

If the user already has a `config.ini` file, then the wrapper can use that, so the user does not need to enter their NDA credentials again. However, to make another `config.ini` file or overwrite the old one, the user can enter their NDA credentials as command-line args.

### Disk Space Usage Warnings

This wrapper will download NDA data (into the `raw/` subdirectory by default) and then copy it (into the `data/` subdirectory by default) to convert it, without deleting the downloaded data unless the `--remove` flag is added. The downloaded and converted data will take up a large amount of space on the user's filesystem, especially for converting many subjects. About 3 to 7 GB of data or more will be produced by downloading and converting one subject session, not counting the temporary files in the `temp/` subdirectory.

This wrapper will create a temporary folder (`temp/` by default) with hundreds of thousands of files (about 7 GB or more) per subject session. These files are used in the process of preparing the BIDS data. The wrapper will delete that temporary folder once it finishes running, even if it crashes. Still, it is probably a good idea to double-check that the temporary folder has no subdirectories before and after running this wrapper. Otherwise, this wrapper might leave an extremely large set of unneeded files on the user's filesystem.

### Optional Arguments

`--start-at`: By default, this wrapper will run every step listed below in that order. Use this flag to start at one step and skip all of the previous ones. To do so, enter the name of the step. E.g. `--start-at correct_jsons` will skip every step before JSON correction.

1. create_good_and_bad_series_table
2. download_nda_data
3. unpack_and_setup
4. correct_jsons
5. validate_bids

`--username` and `--password`: Include one of these to pass the user's NDA credentials from the command line into a `config.ini` file. This will create a new config file if one does not already exist, or overwrite the existing file. If only one of these flags is included, the user will be prompted for the other. They can be passed into the wrapper from the command line like so: `--username <NDA username> --password <NDA password>`.

`--config`: By default, the wrapper will look for a `config.ini` file in a hidden subdirectory of the user's home directory (`~/.abcd2bids/`). Use `--config` to enter a different (non-default) path to the config file, e.g. `--config ~/Documents/config.ini`.

`--temp`: By default, the temporary files will be created in the `temp/` subdirectory of the clone of this repo. If the user wants to place the temporary files anywhere else, then they can do so using the optional `--temp` flag followed by the path at which to create the directory containing temp files, e.g. `--temp /usr/home/abcd2bids-temporary-folder`. A folder will be created at the given path if one does not already exist.

`--sessions`: By default, the wrapper will download all sessions from each subject. This is equivalent to `--sessions ['baseline_year_1_arm_1', '2_year_follow_up_y_arm_1']`. If only a specific year should be download for a subject then specify the year within list format, e.g. `--sessions ['baseline_year_1_arm_1']` for just "year 1" data.

`--modalities`: By default, the wrapper will download all modalities from each subject. This is equivalent to `--modalities ['anat', 'func', 'dwi']`. If only certain modalities should be downloaded for a subject then provide a list, e.g. `--modalities ['anat', 'func']`

`--download`: By default, the wrapper will download the ABCD data to the `raw/` subdirectory of the cloned folder. If the user wants to download the ABCD data to a different directory, they can use the `--download` flag, e.g. `--download ~/abcd-dicom2bids/ABCD-Data-Download`. A folder will be created at the given path if one does not already exist.

`--remove`: By default, the wrapper will download the ABCD data to the `raw/` subdirectory of the cloned folder. If the user wants to delete the raw downloaded data for each subject after that subject's data is finished converting, the user can use the `--remove` flag without any additional parameters.

`--output`: By default, the wrapper will place the finished/converted data into the `data/` subdirectory of the cloned folder. If the user wants to put the finished data anywhere else, they can do so using the optional `--output` flag followed by the path at which to create the directory, e.g. `--output ~/abcd-dicom2bids/Finished-Data`. A folder will be created at the given path if one does not already exist.

`--stop-before`: To run every step until a specific step, and skip every step after it, use this flag with the name of the first step to skip. E.g. `--stop-before unpack_and_setup` will only run the first two steps.

For more information including the shorthand flags of each option, use the `--help` command: `python3 abcd2bids.py --help`.

Here is the format for a call to the wrapper with more options added:

```
python3 abcd2bids.py <FSL directory> <Matlab2016bRuntime v9.1 compiler runtime directory> <Path to QC spreadsheet file downloaded from the NDA> <Path to a .txt file containing a list of subjects to download> <Package_ID> <Path to downloadcmd> --username <NDA username> --download <Folder to place raw data in> --output <Folder to place converted data in> --temp <Directory to hold temporary files> --remove
```

*Note: DWI has been added to the list of modalities that can be downloaded. This has resulted in a couple important changes to the scripts included here and the output BIDS data. Most notably, fieldmaps now include an acquisition field in their filenames to differentiate those used for functional images and those used for DWI (e.g. ..._acq-func_... or ..._acq-dwi_...). Data uploaded to [Collection 3165](https://github.com/ABCD-STUDY/nda-abcd-collection-3165), which was created using this repository, does not contain this identifier.*

## Explanation of Process

`abcd2bids.py` is a wrapper for 4 distinct scripts, which previously needed to be run on their own in sequential order:

1. (Python) `good_bad_series_parser.py`
2. (BASH) `unpack_and_setup.sh`
3. (Python) `correct_jsons.py`
4. (Docker) Official BIDS validator

The DICOM 2 BIDS conversion process can be done by running `python3 abcd2bids.py <FSL directory> <MRE directory>` without any other options. First, the wrapper will try to create an NDA token with the user's NDA credentials. It does this by calling `src/nda_aws_token_maker.py`, which calls `src/nda_aws_token_generator` ([taken from the NDA](https://github.com/NDAR/nda_aws_token_generator)). If the wrapper cannot find a `config.ini` file with those credentials, and they are not entered as command line args, then the user will be prompted to enter them.

### Preliminary Steps

**NOTE:** This step can take over two hours to complete, and is completely handled by `abcd2bids.py`

As its first step, the wrapper will call `nda_aws_token_maker.py`. If successful, `nda_aws_token_maker.py` will create a `credentials` file in the `.aws/` subdirectory of the user's `home` directory. 

Next, the wrapper will produce a download list for the Python & BASH portion to download, convert, select, and prepare. The two spreadsheets referenced above are used to create the `ABCD_good_and_bad_series_table.csv` which gets used to actually download the images. If successful, this script will create the file `ABCD_good_and_bad_series_table.csv` in the `spreadsheets/` subdirectory. This step was previously done by a compiled MATLAB script called `data_gatherer`, but now the wrapper has its own functionality to replace that script.

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

Next, the wrapper runs `correct_jsons.py` on the whole BIDS directory (`data/` by default) to correct/prepare all BIDS sidecar JSON files to comply with the BIDS specification standard version 1.2.0. `correct_jsons.py` will derive fields that are important for the abcd-hcp-pipeline that are hardcoded in scanner specific details.

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

The resulting ABCD Study dataset here is made up of all the ABCD Study participants' BIDS imaging data that passed initial acquisition quality control (MRI QC) for the subjects and sessions originally provide in the SUBJECT_LIST. 


## Attributions

This wrapper relies on the following other projects:
- [cbedetti Dcm2Bids](https://github.com/cbedetti/Dcm2Bids)
- [Rorden Lab dcm2niix](https://github.com/rordenlab/dcm2niix)
- [zlib's pigz-2.4](https://zlib.net/pigz)
- [Official BIDS validator](https://github.com/bids-standard/bids-validator) 
- [NDA AWS token generator](https://github.com/NDAR/nda_aws_token_generator)
- [dcmdump](https://dicom.offis.de/dcmtk.php.en)


## Meta

Documentation last updated by Jacob Lundquist on 2023-01-05.
