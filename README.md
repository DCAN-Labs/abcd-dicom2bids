# ABCD DICOM to BIDS

Written by the OHSU ABCD site for selectively downloading ABCD Study imaging DICOM data QC'ed as good by the ABCD DAIC site, converting it to BIDS standard input data, selecting the best pair of spin echo field maps, and correcting the sidecar JSON files to meet the BIDS Validator specification.

## Installation

Clone this repository and save it somewhere on the Linux system you want to do ABCD DICOM downloads and conversions to BIDS on.

## Dependencies

1. [Python 3.5.2](https://www.python.org/downloads/release/python-352/)
1. [MathWorks MATLAB Runtime Environment (MRE) version 9.1 (R2016b)](https://www.mathworks.com/products/compiler/matlab-runtime.html)
1. [cbedetti Dcm2Bids](https://github.com/cbedetti/Dcm2Bids) (`export` into your BASH `PATH` variable)
1. [Rorden Lab dcm2niix](https://github.com/rordenlab/dcm2niix) (`export` into your BASH `PATH` variable)
1. [zlib's pigz-2.4](https://zlib.net/pigz) (`export` into your BASH `PATH` variable)
1. Docker (see documentation for [Docker Community Edition for Ubuntu](https://docs.docker.com/install/linux/docker-ce/ubuntu/))
1. [FMRIB Software Library (FSL) v5.0](https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/FslInstallation)
1. [Python `cryptography` package](https://cryptography.io/en/latest/)
1. [AWS CLI (Amazon Web Services Command Line Interface) v19.0.0](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-install.html)

## Spreadsheets (not included)

To download images for ABCD you must have two spreadsheets downloaded to this repository's `spreadsheets` folder:

1. `DAL_ABCD_merged_pcqcinfo.csv`
1. `image03.txt`

`DAL_ABCD_merged_pcqcinfo.csv` was provided to OHSU by the ABCD DAIC.  A future version of this code will utilize the [NIMH Data Archive (NDA)](https://ndar.nih.gov/) version of this QC information.  The spreadsheet contains operator QC information for each MRI series.  If the image fails operator QC (a score of 0) the image is not downloaded.

`image03.txt` can be downloaded from [the NDA](https://ndar.nih.gov/) with an ABCD Study Data Use Certification in place.  It contains paths to the TGZ files on the NDA's Amazon AWS S3 buckets where the images can be downloaded from per series.  The following are explicit steps to download just this file:

1. Login to the [NIMH Data Archive](https://ndar.nih.gov/)
1. Go to **Data Dictionary** under **Tools**
1. Select **ABCD Release 2.0 (or whatever release is out)** under **Source Dropdown Menu**
1. Click **Filter**
1. Click the box under **Select** for just **Image/image03**
1. Click **Add to Filter Cart** at the bottom left of the page. 
1. Wait for your cart filter to update.
1. In the upper right hand corner in the **Filter Cart Menu** click **Package/Add to Study**
    - Under **Collections** by **Permission Group** click **Deselect All**
    - Collapse any other studies you have access to and re-select **Adolescent Brain Cognitive Development**
1. Click **Create Package**
    - Name the package something like **Image03**
    - Select Only **Include documentation**
    - Click **Create Package**
1. Download and use the **Package Manager** to download your package

## Usage

The DICOM to BIDS process can be done by running the `abcd2bids.py` wrapper from within the directory cloned from this repo. `abcd2bids.py` requires two positional arguments and can take several optional arguments. Those positional arguments are file paths to the FSL directory and the MATLAB Runtime Environment. Here is an example of a valid call of this wrapper:

```
python3 abcd2bids.py <FSL directory> <Matlab2016bRuntime v9.1 compiler runtime directory>
```

The first time that a user uses this wrapper, the user will have to enter their NDA credentials. If the user does not include them as command-line arguments, then the wrapper will prompt the user to enter them. The wrapper will then create a `config.ini` file with the user's username and (encrypted) password, so the user will not have to enter their NDA credentials any subsequent times running this wrapper.

If the user already has a `config.ini` file, then the wrapper can use that, so the user does not need to enter their NDA credentials again. However, to make another `config.ini` file or overwrite the old one, the user can enter their NDA credentials as command-line args.

### Disk Space Usage Warnings

This wrapper will download NDA data (into the `raw/` subdirectory by default) and then copy it (into the `data/` subdirectory by default) to convert it without deleting the downloaded data, unless the `--remove` flag is added. The downloaded and converted data will take up a large amount of space on the user's filesystem, especially for converting many subjects. About 3 to 7 GB of data or more will be produced by downloading and converting one subject session, not counting the temporary files in the `temp/` subdirectory.

This wrapper will create a temporary folder (`temp/` by default) with hundreds of thousands of files (about 7 GB or more) per subject session. These files are used in the process of preparing the BIDS data. The wrapper will delete that temporary folder once it finishes running, even if it crashes. Still, it is probably a good idea to double-check that the temporary folder has no subdirectories before and after running this wrapper. Otherwise, this wrapper might leave an extremely large set of unneeded files on the user's filesystem.

### Optional arguments

`--username` and `--password`: Include one of these to pass the user's NDA credentials from the command line into a `config.ini` file. This will create a new config file if one does not already exist, or overwrite the existing file. If only one of these flags is included, the user will be prompted for the other. They can be passed into the wrapper from the command line like so: `--username my_nda_username --password my_nda_password`.

`--config`: By default, the wrapper will look for a `config.ini` file in a hidden subdirectory of the user's home directory (`~/.abcd2bids/`). Use `--config` to enter a different (non-default) path to the config file, e.g. `--config ~/Documents/config.ini`.

`--temp`: By default, the temporary files will be created in the `temp/` subdirectory of the clone of this repo. If the user wants to place the temporary files anywhere else, then they can do so using the optional `--temp` flag followed by the path at which to create the directory containing temp files, e.g. `--temp /usr/home/abcd2bids-temporary-folder`. A folder will be created at the given path if one does not already exist.

`--download`: By default, the wrapper will download the ABCD data to the `raw/` subdirectory of the cloned folder. If the user wants to download the ABCD data to a different directory, they can use the `--download` flag, e.g. `--download ~/abcd-dicom2bids/ABCD-Data-Download`. A folder will be created at the given path if one does not already exist.

`--remove`: By default, the wrapper will download the ABCD data to the `raw/` subdirectory of the cloned folder. If the user wants to delete the raw downloaded data for each subject after that subject's data is finished converting, the user can use the `--remove` flag without any additional parameters.

`--output`: By default, the wrapper will place the finished/converted data into the `data/` subdirectory of the cloned folder. If the user wants to put the finished data anywhere else, they can do so using the optional `--output` flag followed by the path at which to create the directory, e.g. `--output ~/abcd-dicom2bids/Finished-Data`. A folder will be created at the given path if one does not already exist.

`--start_at`: By default, this wrapper will run every step listed under "Explanation of Process" below. Use this flag to start at one step and skip all of the previous ones. To do so, enter the name of the step, e.g. `--start_at correct_jsons` to skip every step before JSON correction.

For more information including the shorthand flags of each option, use the `--help` command: `python3 abcd2bids.py --help`.

Here is the format for a call to the wrapper with more options added:

```
python3 abcd2bids.py <FSL directory> <Matlab2016bRuntime v9.1 compiler runtime directory> --username <NDA username> --download <Folder to place raw data in> --output <Folder to place converted data in> --temp <Directory to hold temporary files> --remove 
```

## Explanation of Process

`abcd2bids.py` is a wrapper for five distinct scripts, which previously needed to be run on their own in sequential order:

1. (MATLAB) `data_gatherer.m`
2. (Python) `good_bad_series_parser.py`
3. (BASH) `unpack_and_setup.sh`
4. (Python) `correct_jsons.py`
5. (Docker) Official BIDS validator

The DICOM 2 BIDS conversion process can be done by running `python3 abcd2bids.py <FSL directory> <MRE directory>` without any other options. First, the wrapper will try to create an NDA token with the user's NDA credentials. It does this by calling `src/nda_aws_token_maker.py`, which calls `src/nda_aws_token_generator` ([taken from the NDA](https://github.com/NDAR/nda_aws_token_generator)). If the wrapper cannot find a `config.ini` file with those credentials, and they are not entered as command line args, then the user will be prompted to enter them.

### 1. (MATLAB) `data_gatherer`

The MATLAB portion is for producing a download list for the Python & BASH portion to download, convert, select, and prepare. The two spreadsheets referenced above are used in the `data_gatherer` compiled MATLAB script to create the `ABCD_good_and_bad_series_table.csv` which gets used to actually download the images. `data_gatherer` depends on a mapping file (`mapping.mat`), which maps the SeriesDescriptions to known OHSU descriptors that classify each TGZ file into T1, T2, task-rest, task-nback, etc.

As its first step, the wrapper will run `data_gatherer` with this repository's cloned folder as the clone of this repo. If successful, it will create the file `ABCD_good_and_bad_series_table.csv` in the `spreadsheets/` subdirectory.

**NOTE:** This step can take over two hours to complete.

### 2. (Python) `good_bad_series_parser.py`

Once `ABCD_good_and_bad_series_table.csv` is successfully created, the wrapper will run `src/good_bad_series_parser.py` with this repository's cloned folder as the present working directory to download the ABCD data from the NDA website. It requires the `ABCD_good_and_bad_series_table.csv` spreadsheet under a `spreadsheets` subdirectory of this repository's cloned folder.

`src/good_bad_series_parser.py` also requires a `.aws` folder in the user's `home` directory, which will contain the NDA token. The `nda_aws_token_maker.py` is called before running the wrapper. If successful, `nda_aws_token_maker` will create a `credentials` file in `.aws`. If the download crashes and shows errors about `awscli`, try making sure you have the [latest AWS CLI installed](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-install.html), and that the [`aws` executable is in your BASH `PATH` variable](https://docs.aws.amazon.com/cli/latest/userguide/install-linux.html#install-linux-path).

If successful, this will download the ABCD data from the NDA site into the `raw/` subdirectory of the clone of this repo.

### 3. (BASH) `unpack_and_setup.sh`

The wrapper will call `unpack_and_setup.sh` in a loop to do the DICOM to BIDS conversion and spin echo field map selection, taking seven arguments:

```
SUB=$1 # Full BIDS formatted subject ID (sub-SUBJECTID)
VISIT=$2 # Full BIDS formatted session ID (ses-SESSIONID)
TGZDIR=$3 # Path to directory containing all TGZ files for SUB/VISIT
ROOTBIDSINPUT=$4 Path to output folder which will be created to store unpacked/setup files
ScratchSpaceDir=$5 Path to folder which will be created to store temporary files that will be deleted once the wrapper finishes
FSL_DIR=$6 Path to FSL directory
MRE_DIR=$7 Path to MATLAB Runtime Environment (MRE) directory
```

By default, the wrapper will put the unpacked/setup data in the `data/` subdirectory of this repository's cloned folder. This step will also create and fill the `temp/` subdirectory of the user's home directory containing temporary files used for the download. If the user enters other locations for the temp directory or output data directory as optional command line args, then those will be used instead.

### 4. (Python) `correct_jsons.py`

Next, the wrapper runs `correct_jsons.py` on the whole BIDS directory (`data/` by default) to correct/prepare all BIDS sidecar JSON files to comply with the BIDS specification standard version 1.2.0.

### 5. (Docker) Run official BIDS validator

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

This folder is where the output of `abcd2bids.py` will be placed by default. So, after running `abcd2bids.py`, this folder will have subdirectories for each subject session. Those subdirectories will be correctly formatted according to the [official BIDS specification standard v1.2.0](https://github.com/bids-standard/bids-specification/releases/tag/v1.2.0).

The resulting ABCD Study dataset here is made up of all the ABCD Study participants' imaging data that passed initial acquisition quality control (MRI QC).

## Attributions

This wrapper relies on the following other projects:
- [cbedetti Dcm2Bids](https://github.com/cbedetti/Dcm2Bids)
- [Rorden Lab dcm2niix](https://github.com/rordenlab/dcm2niix)
- [zlib's pigz-2.4](https://zlib.net/pigz)
- [Official BIDS validator](https://github.com/bids-standard/bids-validator) 
- [NDA AWS token generator](https://github.com/NDAR/nda_aws_token_generator)
