#!/usr/bin/env python3

import os
import sys
import argparse
from subprocess import Popen, PIPE



def check_for_RawDataStorage(dcm_dir):
    # Check if the first dicom is raw storage
    dcm1 = sorted(os.listdir(dcm_dir))[0]
    dump_cmd = ["dcmdump", "--search", "0002,0002", os.path.join(dcm_dir, dcm1)]
    p = Popen(dump_cmd, stdout=PIPE, stderr=PIPE)
    output, err = p.communicate()
    output = output.decode()
    if output.split(" ")[2] == '=RawDataStorage':
        print("%s contains DICOMs with non-imaging data that need to be removed prior to dcm2niix" % os.path.join(dcm_dir, dcm1))
        rm_RawData_dcms(dcm_dir, dcm1)
    elif output.split(" ")[2] == '=MRImageStorage':
        print("%s valid" % os.path.join(dcm_dir, dcm1))
        return
    else:
        print("ERROR: dcmdump output not recognized from cmd: %s" % " ".join(dump_cmd))

    return

def rm_RawData_dcms(dcm_dir, dcm1):
    # Identify number of temporal positions (0020,0105) and number of slices per time point (should be 60)
    dump_cmd = ["dcmdump", "--search", "2001,1081", os.path.join(dcm_dir, dcm1)]
    p = Popen(dump_cmd, stdout=PIPE, stderr=PIPE)
    output, err = p.communicate()
    output = output.decode()
    num_vols = int(output.split(" ")[2].strip("[]"))
    print("Number of Temporal Positions (Field 2001,1081): {}".format(num_vols))
    # Confirm that there are 60 slices per time point
    assert(num_vols * 60 == len(os.listdir(dcm_dir)))

    # Remove the entire first corrupt volume (every 60th DICOM)
    for i in range(0,60):
        series_num = str((i*num_vols) + 1).zfill(6)
        dcm_fn = dcm1.replace('000001', series_num)
        os.remove(os.path.join(dcm_dir, dcm_fn))

    return
    

def get_cli_args():
    parser = argparse.ArgumentParser(
        description="Check for RawDataStorage DICOMs in functional imaging DICOM directories and remove them."
    )

    parser.add_argument(
        "dcm_dir",
        type=str,
        help=("DICOM directory")
    )
    
    return(parser.parse_args())

def main():
    cli_args = get_cli_args()

    func_dcm_dirs = [x[0] for x in os.walk(cli_args.dcm_dir)][1:]

    for func_dcm_dir in func_dcm_dirs:
        check_for_RawDataStorage(func_dcm_dir)


if __name__ == "__main__":
    sys.exit(main())



