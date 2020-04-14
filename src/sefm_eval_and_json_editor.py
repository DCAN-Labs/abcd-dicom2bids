#! /usr/bin/env python3

import os, sys, glob, argparse, subprocess, socket, operator, shutil, json
from bids.layout import BIDSLayout
from itertools import product
import nibabel as nib
import numpy as np

os.environ['FSLOUTPUTTYPE'] = 'NIFTI_GZ'

# Last modified
last_modified = "Created by Anders Perrone 3/21/2017. Last modified by Greg Conan 2/24/2020"

# Program description
prog_descrip =  """%(prog)s: sefm_eval pairs each of the pos/neg sefm and returns the pair that is most representative
                   of the average by calculating the eta squared value for each sefm pair to the average sefm.""" + last_modified

# Path to abcd2bids/src, which contains compiled MATLAB ETA squared function; added
# by Greg 2019-06-10 & updated 2019-11-07
ETA_DIR = os.path.dirname(os.path.abspath(__file__))

def read_bids_layout(layout, subject_list=None, collect_on_subject=False):
    """
    :param bids_input: path to input bids folder
    :param subject_list: a list of subject ids to filter on
    :param collect_on_subject: collapses all sessions, for cases with
    non-longitudinal data spread across scan sessions.
    """

    subjects = layout.get_subjects()

    # filter subject list
    if isinstance(subject_list, list):
        subjects = [s for s in subjects if s in subject_list]
    elif isinstance(subject_list, dict):
        subjects = [s for s in subjects if s in subject_list.keys()]

    subsess = []
    # filter session list
    for s in subjects:
        sessions = layout.get_sessions(subject=s)
        if not sessions:
            subsess += [(s, 'session')]
        elif collect_on_subject:
            subsess += [(s, sessions)]
        else:
            subsess += list(product([s], sessions))

    assert len(subsess), 'bids data not found for participants. If labels ' \
            'were provided, check the participant labels for errors.  ' \
            'Otherwise check that the bids folder provided is correct.'

    return subsess


def eta_squared(inputIm, refIm):
    # replace the matlab code - could be done
    # with either fslstats, simpleitk, or nibabel
    # nibabel is already in use, so stick with that
    # Note that this gives a slightly different
    # answer to eta_squared.m, at least on my
    # matlab version. Difference is due to matlab
    # using int16 arithmetic some of the time.
    # comes out the same when forced to double.
    im1 = nib.load(refIm)
    im2 = nib.load(inputIm)
    imdat1 = im1.get_fdata()
    imdat2 = im2.get_fdata()

    mn1 = imdat1.mean()
    mn2 = imdat2.mean()
    grandmean = (mn1 + mn2)/2
    MWithin = (imdat1 + imdat2)/2
    ssWithin = np.sum(np.square(imdat1 - MWithin)) + np.sum(np.square(imdat2 - MWithin))
    ssTot =  np.sum(np.square(imdat1 - grandmean)) + np.sum(np.square(imdat2 - grandmean))
    return 1-ssWithin/ssTot

    
def sefm_select(layout, subject, sessions, base_temp_dir, fsl_dir, mre_dir,
                debug=False):
    pos = 'PA'
    neg = 'AP'

    # Add trailing slash to fsl_dir variable if it's not present
    if fsl_dir[-1] is not "/":
        fsl_dir += "/"

    # Make a temporary working directory
    temp_dir = os.path.join(base_temp_dir, subject + '_eta_temp')
    try:
        os.mkdir(temp_dir)
    except:
        print(temp_dir + " already exists")
        pass

    print("Pairing for subject " + subject + ": " + subject + ", " + sessions)
    fmap = layout.get(subject=subject, session=sessions, datatype='fmap', extension='nii.gz')
    if len(fmap):
        list_pos = [x.path for i, x in enumerate(fmap) if 'dir-PA' in x.filename]
        list_neg = [x.path for i, x in enumerate(fmap) if 'dir-AP' in x.filename]
    
    try:
        len(list_pos) == len(list_neg)
    except:
        print("Error: There are a mismatched number of SEFMs. This should never happen!")
    
    pairs = []
    for pair in zip(list_pos, list_neg):
        pairs.append(pair)
    
    pos_ref = pairs[0][0]
    neg_ref = pairs[0][1]
    
    print("Aligning SEFMs and creating template")
    for i, pair in enumerate(pairs):
        pos_input = pair[0]
        neg_input = pair[1]
        for pedir,ref,flirt_in in [(pos,pos_ref,pos_input),(neg,neg_ref,neg_input)]:
            out = os.path.join(temp_dir,'init_' + pedir + '_reg_' + str(i) + '.nii.gz')
            cmd = [fsl_dir + 'flirt', '-in', flirt_in, '-ref', ref, '-dof', str(6), '-out', out]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, env=os.environ)

    # Average the pos/neg SEFMs after alignment
    
    # First sum all of the images together
    for pedir in [pos,neg]:
        sum_cmd = [os.path.join(fsl_dir,'fslmaths'), os.path.join(temp_dir,'init_' + pedir + '_reg_0.nii.gz')]
        for i in range(1,len(pairs)):
            sum_cmd += ['-add', os.path.join(temp_dir,'init_' + pedir + '_reg_' + str(i) + '.nii.gz')]
        sum_cmd += [os.path.join(temp_dir, pedir + '_sum.nii.gz')]
        subprocess.run(sum_cmd, env=os.environ)

    # Divide the sum by the number of pos/neg SEFMs to get the average
    num_sefm = len(pairs)
    for pedir in [pos,neg]:
        avg_cmd = [os.path.join(fsl_dir, 'fslmaths'), os.path.join(temp_dir, pedir + '_sum.nii.gz'), '-div', str(num_sefm), os.path.join(temp_dir,pedir + '_mean.nii.gz')]
        subprocess.run(avg_cmd, env=os.environ)
    
    print("Computing ETA squared value for each image to the template")
    
    # Calculate the eta squared value of each aligned image to the average and return the pair with the highest average
    #avg_eta_dict = {}
    min_eta_dict = {}
    for i, pair in enumerate(pairs):
        eta_list = []
        for pedir,image in [(pos,pair[0]),(neg,pair[1])]:
            eta = eta_squared(os.path.join(temp_dir,'init_' + pedir + '_reg_' + str(i) + '.nii.gz'), os.path.join(temp_dir,pedir + '_mean.nii.gz'))
            print(image + " eta value = " + str(eta))
            eta_list.append(eta)
        # instead of finding the average between eta values between pairs. Take the pair with the highest lowest eta value.
        min_eta = min(eta_list)
        min_eta_dict[pair] = min_eta
    best_pos, best_neg = max(min_eta_dict, key=min_eta_dict.get)
    print(best_pos)
    print(best_neg)

    # Add metadata
    func_list = [x.path for x in layout.get(subject=subject, session=sessions, datatype='func', extension='nii.gz')]
    anat_list = [x.path for x in layout.get(subject=subject, session=sessions, datatype='anat', extension='nii.gz')]
    for pair in pairs:
        pos_nifti = pair[0]
        neg_nifti = pair[1]
        pos_json = pos_nifti.replace(".nii.gz", ".json")
        neg_json = neg_nifti.replace(".nii.gz", ".json")
        insert_edit_json(pos_json, "PhaseEncodingDirection", "j")
        insert_edit_json(neg_json, "PhaseEncodingDirection", "j-")
        
        if pair == (best_pos, best_neg):
            insert_edit_json(pos_json, "IntendedFor", anat_list + func_list)
            insert_edit_json(neg_json, "IntendedFor", anat_list + func_list)
        else:
            insert_edit_json(pos_json, "IntendedFor", [])
            insert_edit_json(neg_json, "IntendedFor", [])
        
            
    # Delete the temp directory containing all the intermediate images
    if not debug:
        rm_cmd = ['rm', '-rf', temp_dir]
        subprocess.run(rm_cmd, env=os.environ)
    
    print("Success! Best SEFM pair has been chosen and linked in " + subject + "'s nifti directory.")
    
    return best_pos, best_neg


def seperate_concatenated_fm(bids_layout, subject, session, fsl_dir):
    print("actually running")
    fmap = bids_layout.get(subject=subject, session=session, datatype='fmap', extension='nii.gz')
    # use the first functional image as the reference for the nifti header after fslswapdim
    func_ref = bids_layout.get(subject=subject, session=session, datatype='func', extension='nii.gz')[0].path
    print("functional reference: {}".format(func_ref))

    for FM in [x.path for x in fmap]:
        subject_dir = os.path.dirname(FM)
        if "-both_" in FM:
            print("Splitting up {}".format(FM))
            AP_filename = FM.replace("-both_", "-AP_")
            PA_filename = FM.replace("-both_", "-PA_")
            split = [fsl_dir + "/fslsplit", FM, subject_dir + "/vol" ,"-t"]
            print(split)
            subprocess.run(split, env=os.environ)
            swap_dim = [fsl_dir + "/fslswapdim", subject_dir + "/vol0000.nii.gz" ,"x", "-y", "z", subject_dir + "/vol0000.nii.gz"]
            subprocess.run(swap_dim, env=os.environ)
            os.rename(subject_dir + "/vol0000.nii.gz",AP_filename)
            os.rename(subject_dir + "/vol0001.nii.gz",PA_filename)

            # Change by Greg 2019-06-10: Replaced hardcoded Exacloud path to
            # FSL_identity_transformation_matrix with relative path to that
            # file in the pwd
            AP_flirt = [fsl_dir + "/flirt", "-out", AP_filename, "-in", AP_filename, "-ref", func_ref, "-applyxfm", "-init", os.path.join(ETA_DIR, "FSL_identity_transformation_matrix.mat"), "-interp", "spline"]
            PA_flirt = [fsl_dir + "/flirt", "-out", PA_filename, "-in", PA_filename, "-ref", func_ref, "-applyxfm", "-init", os.path.join(ETA_DIR, "FSL_identity_transformation_matrix.mat"), "-interp", "spline"]

            subprocess.run(AP_flirt, env=os.environ)
            subprocess.run(PA_flirt, env=os.environ)
            
            # create the side car jsons for the new pair
            orig_json = FM.replace(".nii.gz", ".json")
            AP_json = AP_filename.replace(".nii.gz", ".json")
            PA_json = PA_filename.replace(".nii.gz", ".json")
            shutil.copyfile(orig_json, AP_json)
            shutil.copyfile(orig_json, PA_json)
            insert_edit_json(orig_json, 'PhaseEncodingDirection', 'NA')
            insert_edit_json(AP_json, 'PhaseEncodingDirection', 'j-')
            insert_edit_json(PA_json, 'PhaseEncodingDirection', 'j')
            # add required fields to the orig json as well
            insert_edit_json(orig_json, 'IntendedFor', [])
    return

def insert_edit_json(json_path, json_field, value):
    with open(json_path, 'r+') as f:
        data = json.load(f)
        data[json_field] = value
        f.seek(0)
        json.dump(data, f, indent=4)
        f.truncate
    return
        

def generate_parser(parser=None):
    """
    Generates the command line parser for this program.
    :param parser: optional subparser for wrapping this program as a submodule.
    :return: ArgumentParser for this script/module
    """
    if not parser:
        parser = argparse.ArgumentParser(
            description=prog_descrip
        )
    parser.add_argument(
        'bids_dir',
        help='path to the input bids dataset root directory.  It is recommended to use '
             'the dcan bids gui or Dcm2Bids to convert from participant dicoms.'
    )
    parser.add_argument(
        'fsl_dir',
        help="Required: Path to FSL directory."
    )
    parser.add_argument(
        'mre_dir',
        help="Required: Path to MATLAB Runtime Environment (MRE) directory."
    )
    parser.add_argument(
        '--participant-label', dest='subject_list', metavar='ID', nargs='+',
        help='optional list of participant ids to run. Default is all ids '
             'found under the bids input directory.  A participant label '
             'does not include "sub-"'
    )
    parser.add_argument(
        '-a','--all-sessions', dest='collect', action='store_true',
        help='collapses all sessions into one when running a subject.'
    )
    parser.add_argument(
        '-d', '--debug', dest='debug', action='store_true', default=False,
        help='debug mode, leaves behind the "eta_temp" directory.'
    )
    parser.add_argument(
        '-v', '--version', action='version', version=last_modified,
        help="Return script's last modified date."
    )

    # Added by Greg Conan 2019-11-04
    parser.add_argument(
        '-o', '--output-dir', default='./data/',
        help=('Directory where necessary .json files live, including '
              'dataset_description.json')
    )
    
    return parser


def main(argv=sys.argv):
    parser = generate_parser()
    args = parser.parse_args()

    # Set environment variables for FSL dir based on CLI
    os.environ['FSL_DIR'] = args.fsl_dir
    os.environ['FSLDIR'] = args.fsl_dir
    # for this script's usage of FSL_DIR...
    fsl_dir = args.fsl_dir + '/bin'

    # Load the bids layout
    layout = BIDSLayout(args.bids_dir)
    subsess = read_bids_layout(layout, subject_list=args.subject_list, collect_on_subject=args.collect)

    for subject,sessions in subsess:
        # fmap directory = base dir
        fmap = layout.get(subject=subject, session=sessions, datatype='fmap', extension='nii.gz')
        if fmap:  # "if" added by Greg 2020-02-24 to prevent crashing if fmap is empty list

            # Check if fieldmaps are concatenated
            base_temp_dir = os.path.dirname(fmap[0].path)
            print(fmap[0].path)
            print("-both_" in fmap[0].path)
            if "-both_" in fmap[0].path:
                print("Running seperate_concatenate_fm")
                seperate_concatenated_fm(layout, subject, sessions, fsl_dir)
                # recreate layout with the additional SEFMS
                layout = BIDSLayout(args.bids_dir)
                
            # Return a list of each SEFM pos/neg pair
            bes_pos, best_neg = sefm_select(layout, subject, sessions,
                                            base_temp_dir, fsl_dir,
                                            args.mre_dir, args.debug)

        # Additional edits to the anat json sidecar
        anat = layout.get(subject=subject, session=sessions, datatype='anat', extension='nii.gz')
        for TX in [x.path for x in anat]:
            TX_json = TX.replace('.nii.gz', '.json') 
            TX_metadata = layout.get_metadata(TX)
                #if 'T1' in TX_metadata['SeriesDescription']:

            if 'Philips' in TX_metadata['Manufacturer']:
                insert_edit_json(TX_json, 'DwellTime', 0.00062771)
            if 'GE' in TX_metadata['Manufacturer']:
                insert_edit_json(TX_json, 'DwellTime', 0.000536)
            if 'Siemens' in TX_metadata['Manufacturer']:
                insert_edit_json(TX_json, 'DwellTime', 0.00051001152626)
        
        # add EffectiveEchoSpacing if it doesn't already exist
        fmap = layout.get(subject=subject, session=sessions, datatype='fmap', extension='nii.gz')
        for sefm in [x.path for x in fmap]:
            sefm_json = sefm.replace('.nii.gz', '.json')
            sefm_metadata = layout.get_metadata(sefm)

            if 'Philips' in sefm_metadata['Manufacturer']:
                insert_edit_json(sefm_json, 'EffectiveEchoSpacing', 0.00062771)
            if 'GE' in sefm_metadata['Manufacturer']:
                insert_edit_json(sefm_json, 'EffectiveEchoSpacing', 0.000536)
            if 'Siemens' in sefm_metadata['Manufacturer']:
                insert_edit_json(sefm_json, 'EffectiveEchoSpacing', 0.00051001152626)

        # PE direction vs axis
        func = layout.get(subject=subject, session=sessions, datatype='func', extension='nii.gz')
        for task in [x.path for x in func]:
            task_json = task.replace('.nii.gz', '.json')
            task_metadata = layout.get_metadata(task)
            print('Inserting PE into func')
            if "PhaseEncodingAxis" in task_metadata:
                print('Adding PEDirection')
                print(task_json)
                print('PhaseEncodingDirection')
                print(task_metadata['PhaseEncodingAxis'])
                insert_edit_json(task_json, 'PhaseEncodingDirection', task_metadata['PhaseEncodingAxis'])
            elif "PhaseEncodingDirection" in task_metadata:
                insert_edit_json(task_json, 'PhaseEncodingAxis', task_metadata['PhaseEncodingDirection'])
 

if __name__ == "__main__":
    sys.exit(main())