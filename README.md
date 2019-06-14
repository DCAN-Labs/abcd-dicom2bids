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
1. Go to **Data Dictionary** under **Quick Navigation**
1. Select **All ABCD Releases** under **Source**
1. Click **Filter**
1. Select just **Image/image03**
1. Click **Download**
1. In the upper right hand corner under **Selected Filters** click **Download/Add to Study**
    - Under **Collections** by **Permission Group** click **Deselect All**
    - At the bottom re-select **Adolescent Brain Cognitive Development (ABCD)**
1. Click **Create Package**
    - Name the package something like **Image03**
    - Select Only **Include documentation**
    - Click **Create Package**
1. Download and use the **Package Manager** to download your package

## Usage

The DICOM to BIDS process can be done by running the `abcd2bids.py` wrapper from within the directory cloned from this repo. `abcd2bids.py` requires two positional arguments and can take several optional arguments. Those positional arguments are file paths to the FSL directory and the MATLAB Runtime Environment. Here is an example of a valid call of this wrapper:

```
python3 abcd2bids.py /usr/share/fsl/5.0 /mnt/max/shared/code/external/utilities/Matlab2016bRuntime/v91
```

The first time that a user uses this wrapper, the user will have to enter their NDA credentials. If the user does not include them as command-line arguments, then the wrapper will prompt the user to enter them. The wrapper will then create a `config.ini` file with the user's username and (encrypted) password, so the user will not have to enter their NDA credentials any subsequent times running this wrapper.

If the user already has a `config.ini` file, then the wrapper can use that, so the user does not need to enter their NDA credentials again. However, to make another `config.ini` file or overwrite the old one, the user can enter their NDA credentials as command-line args.

**WARNING:** This wrapper will create a temporary folder with hundreds of thousands of files (about 7 GB or more) per subject session. These files are used in the process of preparing the BIDS data. The wrapper will delete that temporary folder once it finishes running, even if it crashes. Still, it is probably a good idea to double-check that the `./temp/` folder has no subdirectories before and after running this wrapper. Otherwise, it may be possible for this wrapper to leave an extremely large set of unneeded files on the user's filesystem.

### Optional arguments

`--username` and `--password`: Lets the user enter their NDA credentials to make a new `config.ini` file. If one flag is included, the other must be too. They can be passed into the wrapper from the command line like so: `--username my_nda_username --password my_nda_password`.

`--config`: By default, the wrapper will look for a `config.ini` file in a hidden subdirectory of the user's home directory (`~/.abcd2bids/`). The wrapper will create a new config file if one does not already exist, or overwrite the existing one if NDA credentials are given as command-line arguments. Use `--config` to enter a different (non-default) path to the config file, e.g. `--config ~/Documents/config.ini`.

`--temp`: By default, the temporary folder will be created in the `temp/` subdirectory of the clone of this repo. If the user wants to place the temporary folder anywhere else, then they can do so using the optional `--temp` flag followed by the path at which to create the directory, e.g. `--temp /usr/home/abcd2bids-temporary-folder`.

`--download`: By default, the wrapper will download the ABCD data to the `raw/` subdirectory of the cloned folder. If the user wants to download the ABCD data to a different directory, they can use the `--download` flag, e.g. `--download ~/abcd-dicom2bids/ABCD-Data-Download`.

`--output`: By default, the wrapper will place the finished/processed data into the `data/` subdirectory of the cloned folder. If the user wants to put the finished data anywhere else, they can do so using the optional `--output` flag followed by the path at which to create the directory, e.g. `--output ~/abcd-dicom2bids/Finished-Data`.

For more information including the shorthand flags of each option, use the `--help` command: `python3 abcd2bids.py --help`.

## Explanation of Process

`abcd2bids.py` is a wrapper for five distinct scripts, which previously needed to be run on their own in sequential order:

1. (MATLAB) `data_gatherer.m`
2. (Python) `good_bad_series_parser.py`
3. (BASH) `unpack_and_setup.sh`
4. (Python) `correct_jsons.py`
5. (Docker) Official BIDS validator

The DICOM 2 BIDS conversion process can be done by running `python3 abcd2bids.py <FSL directory> <MRE directory>` without any other options. If the wrapper cannot find a `config.ini` file, and the NDA username and password are not entered as command line args, then the user will be prompted to enter both of them.

The MATLAB portion is for producing a download list for the Python & BASH portion to download, convert, select, and prepare.

### 1. (MATLAB) `data_gatherer`

The two spreadsheets referenced above are used in the `data_gatherer` compiled MATLAB script to create the `ABCD_good_and_bad_series_table.csv` which gets used to actually download the images. `data_gatherer` depends on a mapping file (`mapping.mat`), which maps the SeriesDescriptions to known OHSU descriptors that classify each TGZ file into T1, T2, task-rest, task-nback, etc.

As its first step, the wrapper will run `data_gatherer` with this repository's cloned folder as the clone of this repo. If successful, it will create the file `ABCD_good_and_bad_series_table.csv` in the `spreadsheets` folder.

**NOTE:** This step can take over two hours to complete.

### 2. (Python) `good_bad_series_parser.py`

First, the wrapper will try to create an NDA token with the user's NDA credentials. It does this by calling `src/nda_aws_token_maker.py`, which calls `src/nda_aws_token_generator` ([taken from the NDA](https://github.com/NDAR/nda_aws_token_generator)).

Once an NDA token is successfully created, the wrapper will run `src/good_bad_series_parser.py` with this repository's cloned folder as the clone of this repo to download the ABCD data from the NDA website. It requires the `ABCD_good_and_bad_series_table.csv` spreadsheet under a `spreadsheets` subdirectory of this repository's cloned folder.

`src/good_bad_series_parser.py` also requires a `.aws` folder in the user's `home` directory, which will contain the NDA token. The `nda_aws_token_maker.py` is called before each attempted DICOM series TGZ download. If successful, `nda_aws_token_maker` will create a `credentials` file in `.aws`. If the download crashes and shows errors about `awscli`, try making sure you have the [latest AWS CLI installed](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-install.html), and that the [`aws` executable is in your BASH `PATH` variable](https://docs.aws.amazon.com/cli/latest/userguide/install-linux.html#install-linux-path).

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

Next, the wrapper runs `correct_jsons.py` on the whole BIDS directory (`data/` ) to correct/prepare all BIDS sidecar JSON files to comply with the BIDS specification standard version 1.2.0.

### 5. (Docker) Run official BIDS validator

Finally, the wrapper will run the [official BIDS validator](https://github.com/bids-standard/bids-validator) using Docker to validate the dataset in the `data/` folder created by this process.

## Attributions

This wrapper relies on the following other projects:
- [cbedetti Dcm2Bids](https://github.com/cbedetti/Dcm2Bids)
- [Rorden Lab dcm2niix](https://github.com/rordenlab/dcm2niix)
- [zlib's pigz-2.4](https://zlib.net/pigz)
- [BIDS validator](https://github.com/bids-standard/bids-validator) 
- [NDA AWS token generator](https://github.com/NDAR/nda_aws_token_generator)
