#! /usr/bin/env python3


import pandas as pd
import csv
import subprocess
import os
import sys

#######################################
# Read in ABCD_good_and_bad_series_table.csv that is continually updated
#   Create a log of all subjects that have been checked
#   If they are not able to be processed report what is wrong with them
#
#######################################


# Logging variables
num_sub_visits = 0
num_siemens = 0
num_ge = 0
num_philips = 0
num_rsfmri = 0
num_sst = 0
num_mid = 0
num_nback = 0
num_t2 = 0
num_invalid = 0
num_valid = 0
num_subjects_after_checks = 0

# Get download folder name. Use one entered from command line if it exists;
# otherwise use "./new_download". Added by Greg Conan 2019-06-06
if len(sys.argv) is 2:
    new_download_dir = sys.argv[1]
else:
    new_download_dir = './new_download/'


with open('abcd_download_log.csv','w') as f:
    writer = csv.writer(f)


    # Read csv as pandas dataframe, drop duplicate entries, sort, and group by subject/visit
    series_csv = "./spreadsheets/ABCD_good_and_bad_series_table.csv"
    series_df = pd.read_csv(series_csv)
    subject_dfs = series_df.drop_duplicates().sort_values(by='SeriesTime', ascending=True).groupby(["pGUID", "EventName"])

    for name, group in subject_dfs:

        ### Logging information
        # initialize logging variables
        has_t1 = 0
        has_t2 = 0
        has_sefm = 0
        has_rsfmri = 0
        has_mid = 0
        has_sst = 0
        has_nback = 0

        # TODO: Add pGUID and EventName (Subject ID and Visit) to csv for logging information
        num_sub_visits += 1

        scanner = group.iloc[0]['Manufacturer']
        if scanner == 'Philips Medical Systems':
            num_philips += 1
        elif scanner == 'GE MEDICAL SYSTEMS':
            num_ge += 1
        elif scanner == 'SIEMENS':
            num_siemens += 1
        else:
            print("Unexpected scanner type: %s" % scanner)

        # TODO: Create tgz directory if it doesn't already exist
        sub_id = name[0]
        visit = name[1]
        sub = "sub-" + sub_id.replace("_","")
        #print(sub_id, visit)
        tgz_dir = './download' + sub + '/' + visit
        new_tgz_dir = new_download_dir + sub + '/' + visit
        if os.path.exists(tgz_dir):
            print("{0} already exists from old download. Updating now.".format(name))
            #continue
        elif os.path.exists(new_tgz_dir):
            print("{0} already exists from the most recent download. Updating now.".format(name))
            tgz_dir = new_tgz_dir
        else:
            print("{0} downloading now.".format(name))
            tgz_dir = new_tgz_dir
            os.makedirs(tgz_dir)

        ### Get ready to download only good QC'd data that passes all of our criteria !

        passed_QC_group = group.loc[group['QC'] == 1.0]

        file_paths = []

        ### Identify valid scans
        # Download only T1, T2, fMRI_FM_PA, fMRI_FM_AP, fMRI_FM, rsfMRI, fMRI_MID_task, fMRI_SST_task, fMRI_nBack_task

        ## Check if T1_NORM exists and download that instead of just T1
        #   If there is a T1_NORM in the df of good T1s then use it. Else just use good T1
        T1_df = passed_QC_group.loc[passed_QC_group['image_description'] == 'ABCD-T1-NORM']
        if T1_df.empty:
            T1_df = passed_QC_group.loc[passed_QC_group['image_description'] == 'ABCD-T1']
            if T1_df.empty:
                has_t1 = 0 # No T1s. Invalid subject
            else:
                for file_path in T1_df['image_file']:
                    file_paths += [file_path]
                has_t1 = T1_df.shape[0]
        else:
            for file_path in T1_df['image_file']:
                file_paths += [file_path]
            has_t1 = T1_df.shape[0]

        T2_df = passed_QC_group.loc[passed_QC_group['image_description'] == 'ABCD-T2-NORM']
        if T2_df.empty:
            T2_df = passed_QC_group.loc[passed_QC_group['image_description'] == 'ABCD-T2']
            if T2_df.empty:
                has_t2 = 0 # No T2s
            else:
                for file_path in T2_df['image_file']:
                    file_paths += [file_path]
                has_t2 = T2_df.shape[0]
        else:
            for file_path in T2_df['image_file']:
                file_paths += [file_path]
            has_t2 = T2_df.shape[0]

        ## Pair SEFMs and only download if both pass QC
        #   Check first if just the FM exists
        FM_df = passed_QC_group.loc[passed_QC_group['image_description'] == 'ABCD-fMRI-FM']
        if FM_df.empty:
            FM_AP_df = group.loc[group['image_description'] == 'ABCD-fMRI-FM-AP']
            FM_PA_df = group.loc[group['image_description'] == 'ABCD-fMRI-FM-PA']
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

        ## List only download task iff their is a pair of scans for the task that passed QC
        MID_df = passed_QC_group.loc[passed_QC_group['image_description'] == 'ABCD-MID-fMRI']
        if MID_df.shape[0] != 2:
            has_mid = MID_df.shape[0]
        else:
            for file_path in MID_df['image_file']:
                file_paths += [file_path]
            has_mid = MID_df.shape[0]
        SST_df = passed_QC_group.loc[passed_QC_group['image_description'] == 'ABCD-SST-fMRI']
        if SST_df.shape[0] != 2:
            has_sst = SST_df.shape[0]
        else:
            for file_path in SST_df['image_file']:
                file_paths += [file_path]
            has_sst = SST_df.shape[0]
        nBack_df = passed_QC_group.loc[passed_QC_group['image_description'] == 'ABCD-nBack-fMRI']
        if nBack_df.shape[0] != 2:
            has_nback = nBack_df.shape[0]
        else:
            for file_path in nBack_df['image_file']:
                file_paths += [file_path]
            has_nback = nBack_df.shape[0]

        # TODO: log subject level information
        if has_t1 == 0:
            num_invalid += 1
            print('%s: t1=%s, t2=%s, sefm=%s, rsfmri=%s, mid=%s, sst=%s, nback=%s INVALID' % (sub, has_t1, has_t2, has_sefm, has_rsfmri, has_mid, has_sst, has_nback))
            writer.writerow([sub, has_t1, has_t2, has_sefm, has_rsfmri, has_mid, has_sst, has_nback])
        else:
            num_valid += 1
            print('%s: t1=%s, t2=%s, sefm=%s, rsfmri=%s, mid=%s, sst=%s, nback=%s' % (sub, has_t1, has_t2, has_sefm, has_rsfmri, has_mid, has_sst, has_nback))
            writer.writerow([sub, has_t1, has_t2, has_sefm, has_rsfmri, has_mid, has_sst, has_nback])
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
            # subprocess.call(["./nda_aws_token_maker.py", ">", "/dev/null"])
            for i in file_paths:
                tgz_name = os.path.basename(i)
                tgz_path = tgz_dir + '/' + tgz_name
                if os.path.exists(tgz_path):
                    continue
                else:
                    aws_cmd = ["aws", "s3", "cp", i, tgz_dir + "/", "--profile", "NDA"]
                    #print(aws_cmd)
                    subprocess.call(aws_cmd)


print("There are %s subject visits" % num_sub_visits)
print("%s are valid. %s are invalid" % (num_valid, num_invalid))
print("%s Siemens" % num_siemens)
print("%s Philips" % num_philips)
print("%s GE" % num_ge)
print("number of valid subjects with a T2 : %s" % num_t2)
print("number of valid subjects with rest : %s" % num_rsfmri)
print("number of valid subjects with mid  : %s" % num_mid)
print("number of valid subjects with sst  : %s" % num_sst)
print("number of valid subjects with nBack: %s" % num_nback)
