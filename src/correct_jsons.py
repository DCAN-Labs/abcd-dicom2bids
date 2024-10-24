#! /usr/bin/env python3

import json,os,sys,argparse,re

__doc__ = \
"""
This scripts is meant to correct ABCD BIDS input data to
conform to the Official BIDS Validator.
"""
__version__ = "1.0.0"

def read_json_field(json_path, json_field):

    with open(json_path, 'r') as f:
        data = json.load(f)

    if json_field in data:
        return data[json_field]
    else:
        return None

def remove_json_field(json_path, json_field):

    with open(json_path, 'r+') as f:
        data = json.load(f)
        
        if json_field in data:
            del data[json_field]
            f.seek(0)
            json.dump(data, f, indent=4)
            f.truncate()
            flag = True
        else:
            flag = False

    return flag

def update_json_field(json_path, json_field, value):

    with open(json_path, 'r+') as f:
        data = json.load(f)

        if json_field in data:
            flag = True
        else:
            flag = False

        data[json_field] = value
        f.seek(0)
        json.dump(data, f, indent=4)
        f.truncate()

    return flag

def main(argv=sys.argv):
    parser = argparse.ArgumentParser(
        prog='correct_jsons.py',
        description=__doc__,
        usage='%(prog)s BIDS_DIR'
    )
    parser.add_argument(
        'BIDS_DIR',
        help='Path to the input BIDS dataset root directory.  Read more '
             'about the BIDS standard in the link in the description.  It is '
             'recommended to use Dcm2Bids to convert from participant dicoms '
             'into BIDS format.'
    )
    parser.add_argument(
        '--version', '-v', action='version', version='%(prog)s ' + __version__
    )

    args = parser.parse_args()

    for root, dirs, files in os.walk(args.BIDS_DIR):
        for filename in files:
            fn, ext = os.path.splitext(filename)

            if ext == '.json':
                json_path = os.path.join(root, filename)
                # print(json_path)

                with open(json_path, 'r') as f:
                    try:
                        data = json.load(f)
                    except ValueError:
                        print('Decoding JSON has failed: {}'.format(json_path))

                # If TotalReadoutTime is missing from fmap JSON
                if ('fmap' in root or 'func' in root) and 'TotalReadoutTime' not in data:
                    # Then check for EffectiveEchoSpacing and ReconMatrixPE
                    if 'EffectiveEchoSpacing' in data and 'ReconMatrixPE' in data:
                        # If both are present then update the JSON with a calculated TotalReadoutTime
                        EffectiveEchoSpacing = data['EffectiveEchoSpacing']
                        ReconMatrixPE = data['ReconMatrixPE']
                        # Calculated TotalReadoutTime = EffectiveEchoSpacing * (ReconMatrixPE - 1)
                        TotalReadoutTime = EffectiveEchoSpacing * (ReconMatrixPE - 1)
                        update_json_field(json_path, 'TotalReadoutTime', TotalReadoutTime)

                    # If EffectiveEchoSpacing is missing print error
                    if 'EffectiveEchoSpacing' not in data:
                        print(json_path + ': No EffectiveEchoSpacing')

                    # If ReconMatrixPE is missing print error
                    if 'ReconMatrixPE' not in data:
                        print(json_path + ': No ReconMatrixPE')

                # Find the IntendedFor field that is a non-empty list
                if 'fmap' in root and 'IntendedFor' in data and len(data['IntendedFor']) > 0:
                    # Regular expression replace all paths in that list with a relative path to ses-SESSION
                    intended_list = data['IntendedFor']
                    if not isinstance(intended_list, list):
                        intended_list = [intended_list]
                    corrected_intended_list = [re.sub(r'.*(ses-.*_ses-.+)','\g<1>',entry) for entry in intended_list]
                    print("Updating",json_path,"IntendedFor", corrected_intended_list)
                    update_json_field(json_path, 'IntendedFor', corrected_intended_list)

                # Remove SliceTiming field from func JSONs
                if 'func' in root and 'SliceTiming' in data:
                    remove_json_field(json_path, 'SliceTiming')

if __name__ == "__main__":
    sys.exit(main())
