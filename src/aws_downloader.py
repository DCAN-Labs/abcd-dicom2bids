#! /usr/bin/env python3


import pandas as pd
import csv
import subprocess
import os
import sys
import argparse

#######################################
# Read in ABCD_good_and_bad_series_table.csv (renamed to ABCD_operator_QC.csv) that is continually updated
#   Create a log of all subjects that have been checked
#   If they are not able to be processed report what is wrong with them
#
#######################################

prog_descrip='AWS downloader'

QC_CSV = os.path.join(os.path.dirname(os.path.dirname(
                    os.path.abspath(__file__))), "spreadsheets",
                    "abcd_fastqc01_reformatted.csv") 
YEARS = ['baseline_year_1_arm_1', '2_year_follow_up_y_arm_1']
MODALITIES = ['anat', 'func', 'dwi']

def generate_parser(parser=None):

    if not parser:
        parser = argparse.ArgumentParser(
            description=prog_descrip
        )
    parser.add_argument(
        '-q', 
        '--qc-csv', 
        dest='qc_csv',
        default=QC_CSV,
        help='Path to the csv file containing aws paths and operator QC info'
)
    parser.add_argument(
        '-d',
        '--download-dir',
        dest='download_dir',
        default='./new_download',
        help='Path to where the subjects should be downloaded to.'
)
    parser.add_argument(
        '-s', 
        '--subject-list', 
        dest='subject_list',
        required=True,
        help='Path to a text file containing a list of subject IDs'
)
    parser.add_argument(
        '-y', 
        '--sessions', 
        dest='year_list',
        default=YEARS,
        help='List the years that images should be downloaded from'
)
    parser.add_argument(
        '-m', 
        '--modalities',
#        choices=MODALITIES,
#        nargs='+',
        dest='modalities',
        default=MODALITIES,
        help="List the modalities that should be downloaded. Default: ['anat', 'func', 'dwi']"
)
    parser.add_argument(
        '-c',
        '--config-dir',
        default=os.path.expanduser('~'),
        help="Directory containing a .s3cfg-ndar for the NDA. Default: home directory (~)"
)

    return parser

def main(argv=sys.argv):
    parser = generate_parser()
    args = parser.parse_args()

    # Logging variables
    num_sub_visits = 0
    num_t1 = 0
    num_rsfmri = 0
    num_sst = 0
    num_mid = 0
    num_nback = 0
    num_t2 = 0
    num_dti = 0


    series_csv = args.qc_csv
    if args.subject_list:
        f = open(args.subject_list, 'r')
        x = f.readlines()
        f.close
        subject_list = [sub.strip() for sub in x]
        log = os.path.join(os.path.dirname(args.subject_list), os.path.splitext(os.path.basename(args.subject_list))[0] + "_download_log.csv")
    year_list = args.year_list
    if isinstance(year_list, str):
        year_list = year_list.split(',')
    modalities = args.modalities
    if isinstance(modalities, str):
        modalities = modalities.split(',')
    download_dir = args.download_dir

    print("aws_downloader.py command line arguments:")    
    print("     QC spreadsheet      : {}".format(series_csv))
    print("     Number of Subjects  : {}".format(len(subject_list)))
    print("     Year                : {}".format(year_list))
    print("     Modalities          : {}".format(modalities))

    with open(log, 'w') as f:
        writer = csv.writer(f)

        # Read csv as pandas dataframe, drop duplicate entries, sort, and group by subject/visit
        series_df = pd.read_csv(series_csv)

        # If subject list is provided
        #subject_list = ['sub-NDARINV019DXLU4', 'NDAR_INV353XG4XH']
        # Get list of all unique subjects if not provided
        # subject_list = series_df.pGUID.unique()
        #year_list = ['baseline_year_1_arm_1']
        # Get list of all years if not provided
        # year_list = series_df.EventName.unique()

        uid_start = "INV"
        for sub in subject_list:
            uid = sub.split(uid_start, 1)[1]
            pguid = 'NDAR_INV' + ''.join(uid)
            bids_id = 'sub-NDARINV' + ''.join(uid)
            subject_df = series_df[series_df['pGUID'] == pguid]
            for year in year_list:
                sub_ses_df = subject_df[subject_df['EventName'] == year]
                sub_pass_QC_df = sub_ses_df # changed to include all data, not just data with QC == 1.0
                file_paths = []
                ### Logging information
                # initialize logging variables
                has_t1 = 0
                has_t2 = 0
                has_sefm = 0
                has_rsfmri = 0
                has_mid = 0
                has_sst = 0
                has_nback = 0
                has_dti = 0

                num_sub_visits += 1
                tgz_dir = os.path.join(download_dir, bids_id, year)
                print("Checking QC data for valid images for {} {}.".format(bids_id, year))
                os.makedirs(tgz_dir, exist_ok=True)
                                
                if 'anat' in modalities:
                    (file_paths, has_t1, has_t2) = add_anat_paths(sub_pass_QC_df, file_paths)
                if 'func' in modalities:
                    (file_paths, has_sefm, has_rsfmri, has_mid, has_sst, has_nback) = add_func_paths(sub_pass_QC_df, file_paths)
                if 'dwi' in modalities:
                    (file_paths, has_dti) = add_dwi_paths(sub_pass_QC_df, file_paths)
                    
            
        
                # TODO: log subject level information
                print(' t1=%s, t2=%s, sefm=%s, rsfmri=%s, mid=%s, sst=%s, nback=%s, has_dti=%s' % (has_t1, has_t2, has_sefm, has_rsfmri, has_mid, has_sst, has_nback, has_dti))
                writer.writerow([bids_id, year, has_t1, has_t2, has_sefm, has_rsfmri, has_mid, has_sst, has_nback, has_dti])
                
                if has_t1 != 0:
                    num_t1 += 1
                if has_t2 != 0:
                    num_t2 += 1
                if has_rsfmri != 0:
                    num_rsfmri += 1
                if has_mid != 0:
                    num_mid += 1
                if has_sst != 0:
                    num_sst += 1
                if has_nback != 0:
                    num_nback += 1
                if has_dti != 0:
                    num_dti += 1
                for i in file_paths:
                    tgz_name = os.path.basename(i)
                    tgz_path = tgz_dir + '/' + tgz_name
                    if os.path.exists(tgz_path):
                        print("{} already exists".format(tgz_path))
                        continue
                    else:
                        aws_cmd = ["s3cmd", "--config", os.path.join(args.config_dir, ".s3cfg-ndar"), "get", i, tgz_dir + "/"]
                        print("Downloading {} to {}".format(i, tgz_dir))
                        subprocess.run(aws_cmd)


    print("There are %s subject visits" % num_sub_visits)
    print("number of subjects with a T1 : %s" % num_t1)
    print("number of subjects with a T2 : %s" % num_t2)
    print("number of subjects with rest : %s" % num_rsfmri)
    print("number of subjects with mid  : %s" % num_mid)
    print("number of subjects with sst  : %s" % num_sst)
    print("number of subjects with nBack: %s" % num_nback)
    print("number of subjects with dti  : %s" % num_dti)



def add_anat_paths(passed_QC_group, file_paths):
    ##  Download both T1_NORM and T1
    T1_df = passed_QC_group[passed_QC_group['image_description'] == 'ABCD-T1']
    if T1_df.empty:
        has_t1 = 0 # No T1s. Invalid subject
    else:
        for file_path in T1_df['image_file']:
            file_paths += [file_path]
        has_t1 = T1_df.shape[0]

    T1_df_norm = passed_QC_group[passed_QC_group['image_description'] == 'ABCD-T1-NORM']
    if not T1_df_norm.empty:
        for file_path in T1_df_norm['image_file']:
            file_paths += [file_path]
        has_t1 += T1_df_norm.shape[0]

    T2_df = passed_QC_group[passed_QC_group['image_description'] == 'ABCD-T2']
    if T2_df.empty:
        has_t2 = 0 # No T2s
    else:
        for file_path in T2_df['image_file']:
            file_paths += [file_path]
        has_t2 = T2_df.shape[0]

    T2_df_norm = passed_QC_group[passed_QC_group['image_description'] == 'ABCD-T2-NORM']
    if not T2_df_norm.empty:
        for file_path in T2_df_norm['image_file']:
            file_paths += [file_path]
        has_t2 += T2_df_norm.shape[0]

    return (file_paths, has_t1, has_t2)

def add_func_paths(passed_QC_group, file_paths):
    ## Pair SEFMs and only download if both pass QC
    #   Check first if just the FM exists
    FM_df = passed_QC_group[passed_QC_group['image_description'] == 'ABCD-fMRI-FM']
    if FM_df.empty:
        FM_AP_df = passed_QC_group[passed_QC_group['image_description'] == 'ABCD-fMRI-FM-AP']
        FM_PA_df = passed_QC_group[passed_QC_group['image_description'] == 'ABCD-fMRI-FM-PA']
        if FM_AP_df.shape[0] != FM_PA_df.shape[0] or FM_AP_df.empty:
            has_sefm = 0 # No SEFMs. Invalid subject
        else:
            for i in range(0, FM_AP_df.shape[0]):
                if FM_AP_df.iloc[i]['QC'] == 1.0 and FM_PA_df.iloc[i]['QC'] == 1.0:
                    FM_df = FM_df.append(FM_AP_df.iloc[i])
                    FM_df = FM_df.append(FM_PA_df.iloc[i])
    if FM_df.empty:
        has_sefm = 0 # No SEFMs. Invalid subject
    else:
        for file_path in FM_df['image_file']:
            file_paths += [file_path]
        has_sefm = FM_df.shape[0]


    ## List all rsfMRI scans that pass QC
    RS_df = passed_QC_group.loc[passed_QC_group['image_description'] == 'ABCD-rsfMRI']
    if RS_df.empty:
        has_rsfmri = 0
    else:
        for file_path in RS_df['image_file']:
            file_paths += [file_path]
        has_rsfmri = RS_df.shape[0]

    ## List only download task if and only if there is a pair of scans for the task that passed QC
    MID_df = passed_QC_group.loc[passed_QC_group['image_description'] == 'ABCD-MID-fMRI']

    for file_path in MID_df['image_file']:
        file_paths += [file_path]
    has_mid = MID_df.shape[0]
    SST_df = passed_QC_group.loc[passed_QC_group['image_description'] == 'ABCD-SST-fMRI']

    for file_path in SST_df['image_file']:
        file_paths += [file_path]
    has_sst = SST_df.shape[0]
    nBack_df = passed_QC_group.loc[passed_QC_group['image_description'] == 'ABCD-nBack-fMRI']

    for file_path in nBack_df['image_file']:
        file_paths += [file_path]
    has_nback = nBack_df.shape[0]

    return (file_paths, has_sefm, has_rsfmri, has_mid, has_sst, has_nback)


def add_dwi_paths(passed_QC_group, file_paths):
    DTI_df = passed_QC_group.loc[passed_QC_group['image_description'] == 'ABCD-DTI']
    if DTI_df.shape[0] >= 1:
        # If a DTI exists then download all passing DTI fieldmaps
        DTI_FM_df = passed_QC_group.loc[passed_QC_group['image_description'] == 'ABCD-Diffusion-FM']
        if DTI_FM_df.empty:
            DTI_FM_AP_df = passed_QC_group.loc[passed_QC_group['image_description'] == 'ABCD-Diffusion-FM-AP']
            if DTI_FM_AP_df.empty:
                return (file_paths, 0)
            DTI_FM_PA_df = passed_QC_group.loc[passed_QC_group['image_description'] == 'ABCD-Diffusion-FM-PA']
            DTI_FM_df = DTI_FM_AP_df.tail(1)
            DTI_FM_df = DTI_FM_df.append(DTI_FM_PA_df.tail(1))
        if not DTI_FM_df.empty:
            for file_path in DTI_df['image_file']:
                file_paths += [file_path]
            for file_path in DTI_FM_df['image_file']:
                file_paths += [file_path]
        has_dti = DTI_df.shape[0]
    else:
        has_dti = DTI_df.shape[0]

    return (file_paths, has_dti)

if __name__ == "__main__":
    main()
