# ABCD QC-Passed Image Downloader

## Required spreadsheets

To download images for ABCD you must have two spreadsheets:

1. `DAL_ABCD_merged_pcqcinfo.csv`

  - This is provided to us by the DAIC
  - Contains operator QC information for each scan. If the image fails operator QC (0) the image is not downloaded

1. `image03.txt`

  - This is downloaded from the NIMH Data Archive.
  - Contains paths to the tgz on s3 where the image is downloaded from
  - Login to the NIMH Data Archive (https://ndar.nih.gov/)
  - Go to "Data Dictionary" under Quick Navigation
  - Select all ABCD Releases under Source
  - Click 'Filter'
  - Select just Image/image03
  - Click 'Download'
  - In the upper right hand corner under 'Selected Filters' click 'Download/Add to Study'
    - Under Collections by Permission Group click 'Deselect All'
    - At the bottom re-select 'Adolescent Brain Cognitive Development (ABCD)'
    - Click 'Create Package'
      - Name the package Image03
      - Select only 'Include documentation'
      - Click 'Create Package'
  - Download the Package Manager and download

These two files are used in the `data_gatherer.m` to create the `ABCD_good_bad_series_table.csv` that is used to actually download the images.

`data_gatherer.m` also depends on a mapping file (`mapping.mat`), which maps among other things the SeriesDescriptions from each txt to known OHSU descriptors that classify each tgz into T1, T2, rfMRI, tfMRI_nBack, etc.

## Required software dependencies

From there, other necessary scripts are the `nda_aws_token_maker.py` to be called before each attempted DICOM series TGZ download.  Requires:

- https://github.com/NDAR/nda_aws_token_generator

You will also need to reach into the `nda_aws_token_maker.py` and update it with your NDA USERNAME and PASSWORD.  Make sure the file is locked down with `chmod 600 nda_aws_token_maker.py` so no one else can read your username and password in there.  We don't have a better solution right now.

# Usage

The actual download work is done by `good_bad_series_parser.py` which only requires the `ABCD_good_bad_series_table.csv` spreadsheet present under `./spreadsheets/`.


# ABCD TGZ to BIDS Input Setup

`unpack_and_setup.sh` does the work.  It takes three arguments:

```
SUB=$1 # Full BIDS formatted subject ID (sub-SUBJECTID)
VISIT=$2 # Full BIDS formatted session ID (ses-SESSIONID)
TGZDIR=$3 # Path to directory containing all .tgz for subject
```

**IMPORTANT**: update paths inside the script everywhere a `...` appears.
