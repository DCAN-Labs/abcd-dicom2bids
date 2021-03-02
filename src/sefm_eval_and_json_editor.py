#! /usr/bin/env python3

import os, sys, glob, argparse, subprocess, socket, operator, shutil, json
from bids import BIDSLayout
from itertools import product

os.environ['FSLOUTPUTTYPE'] = 'NIFTI_GZ'

# Last modified
last_modified = "Created by Anders Perrone 3/21/2017. Last modified 13/01/2019"

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


def sefm_select(layout, subject, sessions, base_temp_dir, fsl_dir, mre_dir,
                debug=False):
    pos = 'PA'
    neg = 'AP'

    # Add trailing slash to fsl_dir variable if it's not present
    if fsl_dir[-1] != "/":
        fsl_dir += "/"

    # Make a temporary working directory
    temp_dir = os.path.join(base_temp_dir, subject + '_eta_temp')
    try:
        os.mkdir(temp_dir)
    except:
        print(temp_dir + " already exists")
        pass

    print("Pairing for subject " + subject + ": " + subject + ", " + sessions)
    pos_func_fmaps = layout.get(subject=subject, session=sessions, datatype='fmap', acquisition='func', direction=pos, extension='.nii.gz')
    neg_func_fmaps = layout.get(subject=subject, session=sessions, datatype='fmap', acquisition='func', direction=neg, extension='.nii.gz')
    list_pos = [os.path.join(x.dirname, x.filename) for x in pos_func_fmaps]
    list_neg = [os.path.join(y.dirname, y.filename) for y in neg_func_fmaps]

#    fmap = layout.get(subject=subject, session=sessions, datatype='fmap', acquisitionuisition='func', extension='.nii.gz')
#    if len(fmap):
#        list_pos = [x.filename for i, x in enumerate(fmap) if 'dir-PA' in x.filename]
#        list_neg = [x.filename for i, x in enumerate(fmap) if 'dir-AP' in x.filename]
    
    try:
        len(list_pos) == len(list_neg)
    except:
        print("ERROR in SEFM select: There are a mismatched number of SEFMs. This should never happen!")
    
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
            mat_cmd = [os.path.join(ETA_DIR,'run_eta_squared.sh'), mre_dir, os.path.join(temp_dir,'init_' + pedir + '_reg_' + str(i) + '.nii.gz'), os.path.join(temp_dir,pedir + '_mean.nii.gz')]
            mat_stdout = subprocess.check_output(mat_cmd)
            eta = float(mat_stdout.split()[-1])
            print(image + " eta value = " + str(eta))
            eta_list.append(eta)
        # instead of finding the average between eta values between pairs. Take the pair with the highest lowest eta value.
        min_eta = min(eta_list)
        min_eta_dict[pair] = min_eta
    best_pos, best_neg = max(min_eta_dict, key=min_eta_dict.get)
    print(best_pos)
    print(best_neg)

    # Add metadata
    func_list = [os.path.join(x.dirname, x.filename) for x in layout.get(subject=subject, session=sessions, datatype='func', extension='.nii.gz')]
    anat_list = [os.path.join(x.dirname, x.filename) for x in layout.get(subject=subject, session=sessions, datatype='anat', extension='.nii.gz')]
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


def seperate_concatenated_fm(bids_layout, subject, session, fsl_dir, debug=False):
    fmap = bids_layout.get(subject=subject, session=session, datatype='fmap', acquisition='func', direction='both', extension='.nii.gz')
    # use the first functional image as the reference for the nifti header after fslswapdim
    func_ref_fn = bids_layout.get(subject=subject, session=session, datatype='func', extension='.nii.gz')[0].filename
    func_ref_dir = bids_layout.get(subject=subject, session=session, datatype='func', extension='.nii.gz')[0].dirname
    func_ref = os.path.join(func_ref_dir, func_ref_fn)
    print("functional reference: {}".format(func_ref))
    for FM in fmap:
        FM_dir = FM.dirname
        FM_fn = FM.filename
        FM_concatenated = os.path.join(FM_dir, FM_fn)
        print("Splitting up {}".format(FM_concatenated))
        AP_fn = FM_concatenated.replace("-both_", "-AP_")
        PA_fn = FM_concatenated.replace("-both_", "-PA_")
        split = [fsl_dir + "/fslsplit", FM_concatenated, os.path.join(FM_dir,"vol"), "-t"]
        subprocess.run(split, env=os.environ)
        swap_dim = [fsl_dir + "/fslswapdim", os.path.join(FM_dir, "vol0000.nii.gz"), "x", "-y", "z", os.path.join(FM_dir, "vol0000.nii.gz")]
        subprocess.run(swap_dim, env=os.environ)
        os.rename(os.path.join(FM_dir, "vol0000.nii.gz"), AP_fn)
        os.rename(os.path.join(FM_dir, "vol0001.nii.gz"), PA_fn)

        # Change by Greg 2019-06-10: Replaced hardcoded Exacloud path to
        # FSL_identity_transformation_matrix with relative path to that
        # file in the pwd
        AP_flirt = [fsl_dir + "/flirt", "-out", AP_fn, "-in", AP_fn, "-ref", func_ref, "-applyxfm", "-init", os.path.join(ETA_DIR, "FSL_identity_transformation_matrix.mat"), "-interp", "spline"]
        PA_flirt = [fsl_dir + "/flirt", "-out", PA_fn, "-in", PA_fn, "-ref", func_ref, "-applyxfm", "-init", os.path.join(ETA_DIR, "FSL_identity_transformation_matrix.mat"), "-interp", "spline"]

        subprocess.run(AP_flirt, env=os.environ)
        subprocess.run(PA_flirt, env=os.environ)
        
        # create the side car jsons for the new pair
        orig_json = FM_concatenated.replace(".nii.gz", ".json")
        AP_json = AP_fn.replace(".nii.gz", ".json")
        PA_json = PA_fn.replace(".nii.gz", ".json")
        shutil.copyfile(orig_json, AP_json)
        shutil.copyfile(orig_json, PA_json)
        insert_edit_json(orig_json, 'PhaseEncodingDirection', 'NA')
        insert_edit_json(AP_json, 'PhaseEncodingDirection', 'j-')
        insert_edit_json(PA_json, 'PhaseEncodingDirection', 'j')
        # add required fields to the orig json as well
        insert_edit_json(orig_json, 'IntendedFor', [])

    #if not debug:
    #    rm_cmd = ['rm', '-rf', os.path.join(FM_dir, "vol*")]
    #    subprocess.run(rm_cmd, env=os.environ)
    #    rm_cmd = ['rm', '-rf', os.path.join()]
    #    subprocess.run(rm_cmd, env=os.environ)
   
    return

def edit_dwi_jsons(layout, subject, sessions):
    print('Editing DWI sidecar jsons')
    all_json_paths = []
    # Get rel path of all dwi images
    rel_dwi_paths = []
    for dwi in layout.get(subject=subject, session=sessions, datatype='dwi', suffix='dwi', extension='.nii.gz'):
        dwi_fn = dwi.filename
        dwi_dir = dwi.dirname
        dwi_json = dwi_fn.replace('.nii.gz', '.json')
        all_json_paths += [os.path.join(dwi_dir, dwi_json)]
        rel_path = "/".join(dwi_dir.split("/")[-3:] + [dwi_fn])
        rel_dwi_paths += [rel_path]

    # There should currently only be a single dwi fmap TODO: allow for multiple fmaps
    AP = layout.get(subject=subject, session=sessions, datatype='fmap', acquisition='dwi', direction='AP', extension='.nii.gz')
    AP_json = layout.get(subject=subject, session=sessions, datatype='fmap', acquisition='dwi', direction='AP', extension='.json')
    assert(len(AP_json) == 1)
    AP_json_path = "/".join([AP_json[0].dirname, AP_json[0].filename])
    all_json_paths += [AP_json_path]

    insert_edit_json(AP_json_path, 'IntendedFor', rel_dwi_paths)
    insert_edit_json(AP_json_path, 'PhaseEncodingDirection', 'j-')
    
    # We are not using the PA even if one is included
    PA_json = layout.get(subject=subject, session=sessions, datatype='fmap', acquisition='dwi', direction='PA', extension='.json')
    if PA_json:
        PA_json_path = "/".join([PA_json[0].dirname, PA_json[0].filename])
        all_json_paths += [PA_json_path]
        insert_edit_json(PA_json_path, 'IntendedFor',[])
        insert_edit_json(PA_json_path, 'PhaseEncodingDirection', 'j')

        insert_edit_json(PA_json_path, 'PhaseEncodingDirection', 'j')

    
    for json_path in all_json_paths:
        nii_path = json_path.replace('.json', '.nii.gz')
        dwi_metadata = layout.get_metadata(nii_path)
        if 'GE' in dwi_metadata['Manufacturer']:
            if 'DV26' in dwi_metadata['SoftwareVersions']:
                insert_edit_json(json_path, 'EffectiveEchoSpacing', 0.000768)
                insert_edit_json(json_path, 'TotalReadoutTime', 0.106752)
            if 'DV25' in dwi_metadata['SoftwareVersions']:
                insert_edit_json(json_path, 'EffectiveEchoSpacing', 0.000752)
                insert_edit_json(json_path, 'TotalReadoutTime', 0.104528)
        elif 'Philips' in dwi_metadata['Manufacturer']:
            insert_edit_json(json_path, 'EffectiveEchoSpacing', 0.00062771)
            insert_edit_json(json_path, 'TotalReadoutTime', 0.08976)
            insert_edit_json(json_path, 'PhaseEncodingDirection', 'j')
        elif 'Siemens' in dwi_metadata['Manufacturer']:
            insert_edit_json(json_path, 'EffectiveEchoSpacing', 0.000689998)
            insert_edit_json(json_path, 'TotalReadoutTime', 0.0959097)
        else:
            print("ERROR: DWI manufacturer not recognized")

    print('Done editing DWI sidecar jsons')

    return
    

def insert_edit_json(json_path, json_field, value):
    with open(json_path, 'r') as f:
        data = json.load(f)
    if json_field in data and data[json_field] != value:
        print('WARNING: Replacing {}: {} with {} in {}'.format(json_field, data[json_field], value, json_path))
    else:
        print('Inserting {}: {} in {}'.format(json_field, value, json_path))
        
    data[json_field] = value
    with open(json_path, 'w') as f:    
        json.dump(data, f, indent=4)

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
        '-o', '--output_dir', default='./data/',
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
 
        # Check if fieldmaps are concatenated
        if layout.get(subject=subject, session=sessions, datatype='fmap', extension='.nii.gz', acquisition='func', direction='both'):
            print("Func fieldmaps are concatenated. Running seperate_concatenate_fm")
            seperate_concatenated_fm(layout, subject, sessions, fsl_dir)
            # recreate layout with the additional SEFMS
            layout = BIDSLayout(args.bids_dir)
        

        fmap = layout.get(subject=subject, session=sessions, datatype='fmap', extension='.nii.gz', acquisition='func')        
        # Check if there are func fieldmaps and return a list of each SEFM pos/neg pair
        if fmap:
            print("Running SEFM select")
            base_temp_dir = fmap[0].dirname
            bes_pos, best_neg = sefm_select(layout, subject, sessions,
                                            base_temp_dir, fsl_dir, args.mre_dir,
                                            args.debug)
            for sefm in [os.path.join(x.dirname, x.filename) for x in fmap]:
                sefm_json = sefm.replace('.nii.gz', '.json')
                sefm_metadata = layout.get_metadata(sefm)

                if 'Philips' in sefm_metadata['Manufacturer']:
                    insert_edit_json(sefm_json, 'EffectiveEchoSpacing', 0.00062771)
                if 'GE' in sefm_metadata['Manufacturer']:
                    insert_edit_json(sefm_json, 'EffectiveEchoSpacing', 0.000536)
                if 'Siemens' in sefm_metadata['Manufacturer']:
                    insert_edit_json(sefm_json, 'EffectiveEchoSpacing', 0.000510012)

        # Check if there are dwi fieldmaps and insert IntendedFor field accordingly
        if layout.get(subject=subject, session=sessions, datatype='fmap', extension='.nii.gz', acquisition='dwi'):
            print("Editing DWI jsons")
            edit_dwi_jsons(layout, subject, sessions)
                    


        # Additional edits to the anat json sidecar
        anat = layout.get(subject=subject, session=sessions, datatype='anat', extension='.nii.gz')
        if anat:
            for TX in [os.path.join(x.dirname, x.filename) for x in anat]:
                TX_json = TX.replace('.nii.gz', '.json') 
                TX_metadata = layout.get_metadata(TX)
                    #if 'T1' in TX_metadata['SeriesDescription']:

                if 'Philips' in TX_metadata['Manufacturer']:
                    insert_edit_json(TX_json, 'DwellTime', 0.00062771)
                if 'GE' in TX_metadata['Manufacturer']:
                    insert_edit_json(TX_json, 'DwellTime', 0.000536)
                if 'Siemens' in TX_metadata['Manufacturer']:
                    insert_edit_json(TX_json, 'DwellTime', 0.000510012)
        
        # add EffectiveEchoSpacing if it doesn't already exist

        # PE direction vs axis
        func = layout.get(subject=subject, session=sessions, datatype='func', extension='.nii.gz')
        if func:
            for task in [os.path.join(x.dirname, x.filename) for x in func]:
                task_json = task.replace('.nii.gz', '.json')
                task_metadata = layout.get_metadata(task)
                if 'Philips' in task_metadata['Manufacturer']:
                    insert_edit_json(task_json, 'EffectiveEchoSpacing', 0.00062771)
                if 'GE' in task_metadata['Manufacturer']:
                    if 'DV26' in task_metadata['SoftwareVersions']:
                        insert_edit_json(task_json, 'EffectiveEchoSpacing', 0.000556)
                if 'Siemens' in task_metadata['Manufacturer']:
                    insert_edit_json(task_json, 'EffectiveEchoSpacing', 0.000510012)                
                if "PhaseEncodingAxis" in task_metadata:
                    insert_edit_json(task_json, 'PhaseEncodingDirection', task_metadata['PhaseEncodingAxis'])
                elif "PhaseEncodingDirection" in task_metadata:
                    insert_edit_json(task_json, 'PhaseEncodingAxis', task_metadata['PhaseEncodingDirection'].strip('-'))
     

if __name__ == "__main__":
    sys.exit(main())

