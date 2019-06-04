# ABCD DICOM to BIDS

Written by the OHSU ABCD site for selectively downloading ABCD Study imaging DICOM data QC'ed as good by the ABCD DAIC site, converting it to BIDS standard input data, selecting the best pair of spin echo field maps, and correcting the sidecar JSON files to meet the BIDS Validator specification.

## Installation

Clone this repository and save it somewhere on the Linux system you want to do ABCD DICOM downloads and conversions to BIDS.

## Dependencies

1. [MathWorks MATLAB (R2016b and newer)](https://www.mathworks.com/products/matlab.html)
1. [Python 2.7](https://www.python.org/download/releases/2.7/)
1. [NIMH Data Archive (NDA) `nda_aws_token_generator`](https://github.com/NDAR/nda_aws_token_generator)
1. [cbedetti Dcm2Bids](https://github.com/cbedetti/Dcm2Bids) (`export` into your BASH `PATH` variable)
1. [Rorden Lab dcm2niix](https://github.com/rordenlab/dcm2niix) (`export` into your BASH `PATH` variable)
1. [zlib's pigz-2.4](https://zlib.net/pigz) (`export` into your BASH `PATH` variable)

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

## Setup

You will also need to reach into the `nda_aws_token_maker.py` in this repository and update it with your NDA USERNAME and PASSWORD.  Make sure the file is locked down to only your own read and write privileges so no one else can read your username and password in there:

```
chmod 600 nda_aws_token_maker.py
```

We don't have a better solution for securing your credentials while automating downloads right now.

## Usage

This repo's usage is broken out into four distinct scripting sections.  You will need to run them in order, each independently of the next waiting for the first to complete.

1. (MATLAB) `data_gatherer.m`
2. (Python) `good_bad_series_parser.py`
3. (BASH) `unpack_and_setup.sh`
4. (Python) `correct_jsons.py`

The MATLAB portion is for producing a download list for the Python & BASH portion to download, convert, select, and prepare.

## 1. (MATLAB) `data_gatherer.m`

The two spreadsheets referenced above are used in the `data_gatherer.m` to create the `ABCD_good_and_bad_series_table.csv` which gets used to actually download the images.

`data_gatherer.m` depends on a mapping file (`mapping.mat`), which maps the SeriesDescriptions to known OHSU descriptors that classify each TGZ file into T1, T2, task-rest, task-nback, etc.

Run `data_gatherer.m` with this repository's cloned folder as the pwd. If successful, it will create the file `ABCD_good_and_bad_series_table.csv` in the `spreadsheets` folder.

## 2. (Python) `good_bad_series_parser.py`

The download is done like this:

```
./good_bad_series_parser.py
```

This must also be run with this repository's cloned folder as the pwd. It requires the `ABCD_good_and_bad_series_table.csv` spreadsheet present under a `spreadsheets` folder inside this repository's cloned folder. It also requires a `.aws` folder in the user's `home` directory.

**Note:** The `nda_aws_token_maker.py` is called before each attempted DICOM series TGZ download. If successful, `nda_aws_token_maker` will create a `credentials` file in `.aws`.

If successful, this will download the ABCD data from the NDA site into a `new_download` subdirectory of the pwd.

## 3. (BASH) `unpack_and_setup.sh`

`unpack_and_setup.sh` should be called in a loop to do the DICOM to BIDS conversion and spin echo field map selection.  It takes three arguments:

```
SUB=$1 # Full BIDS formatted subject ID (sub-SUBJECTID)
VISIT=$2 # Full BIDS formatted session ID (ses-SESSIONID)
TGZDIR=$3 # Path to directory containing all TGZ files for SUB/VISIT
```

Here is an example:

```
./unpack_and_setup.sh sub-NDARINVABCD1234 ses-baselineYear1Arm1 ./new_download/sub-NDARINVABCD1234/ses-baseline_year_1_arm_1
```

This will create a `abcd-dicom2bids_unpack_temp` subdirectory of the user's home directory containing temporary files used for the download, and a `ABCD-HCP` subdirectory of this repository's cloned folder.

## 4. (Python) `correct_jsons.py`

Finally at the end `correct_jsons.py` is run on the whole BIDS input directory to correct/prepare all BIDS sidecar JSON files to comply with the BIDS specification standard version 1.2.0.

```
./correct_jsons.py ./ABCD-HCP
```
