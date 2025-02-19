# `src` folder

This folder contains all of the scripts used by the `abcd2bids.py` wrapper. There should be 13 files in this folder, as well as a `bin` subdirectory.

## Files belonging in this folder

#### Metadata:
1. `__init__.py`
1. `README.md`

#### Scripts used to create NDA token to download NDA data:
1. `nda_aws_token_generator.py`
1. `nda_aws_token_maker.py`

#### Scripts used to download NDA data:
1. `FSL_identity_transformation_matrix.mat`
1. `aws_downloader.py`
1. `mapping.mat`

#### Scripts used to unpack and setup NDA data:
1. `eta_squared`
1. `run_eta_squared.sh`
1. `run_order_fix.py`
1. `sefm_eval_and_json_editor.py`
1. `unpack_and_setup.sh`
2. `remove_RawDataStorage_dcms.py`

#### Scripts used to make NDA data meet BIDS standards:
1. `correct_jsons.py`
