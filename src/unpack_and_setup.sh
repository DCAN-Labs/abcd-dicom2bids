#! /bin/bash

# Given a subject ID, session, and tgz directory:
#   1) Copy all tgzs to compute node's disk
#   2) Unpack tgzs
#   3) Convert dcms to niftis in BIDS
#   4) Select the best SEFM
#   5) Rename and move Eprime files
#   6) Copy back to Lustre

## Necessary dependencies
# dcm2bids (https://github.com/DCAN-Labs/Dcm2Bids)
# microgl_lx (https://github.com/rordenlab/dcm2niix)
# pigz-2.4 (https://zlib.net/pigz)
# run_order_fix.py (in this repo)
# sefm_eval_and_json_editor.py (in this repo)

# modified by Greg 2020-02-21
SRC_DIR="$(dirname ${0})"
if [ "$(basename ${SRC_DIR})" = "src" ]; then
    ABCD2BIDS_DIR="$(dirname $SRC_DIR)"
else
    echo "Error: $(basename ${0}) must be kept in the 'src' directory."
    exit
fi

 
# If output folder is given as a command line arg, get it; otherwise use
# ./data as the default. Added by Greg 2019-06-06
if [ "x$4" = "x" ]; then
    ROOT_BIDSINPUT=${ABCD2BIDS_DIR}/data
else
    ROOT_BIDSINPUT=$4
fi

# If temp files folder is given as a command line arg, get it; otherwise use
# ./temp as the default. Added by Greg 2019-06-07
if [ "x$5" = "x" ]; then
    ScratchSpaceDir=${ABCD2BIDS_DIR}/temp
else
    ScratchSpaceDir=$5
fi

# Get FSL and MRE directory paths from command line; added by Greg Conan on
# 2019-06-10
if [[ ! "x$6" = "x" && ! "x$7" = "x" ]]; then
    FSL_DIR=$6
    MRE_DIR=$7
fi

SUB=$1 # Full BIDS formatted subject ID (sub-SUBJECTID)
VISIT=$2 # Full BIDS formatted session ID (ses-SESSIONID)
TGZDIR=$3 # Path to directory containing all .tgz for this subject's session

participant=`echo ${SUB} | sed 's|sub-||'`
session=`echo ${VISIT} | sed 's|ses-||'`

date
hostname
echo ${SLURM_JOB_ID}

# Setup scratch space directory
if [ ! -d ${ScratchSpaceDir} ]; then
    mkdir -p ${ScratchSpaceDir}
    # chown :fnl_lab ${ScratchSpaceDir} || true 
    chmod 770 ${ScratchSpaceDir} || true
fi
RandomHash=`cat /dev/urandom | tr -cd 'a-f0-9' | head -c 16`
TempSubjectDir=${ScratchSpaceDir}/${RandomHash}
mkdir -p ${TempSubjectDir}
# chown :fnl_lab ${TempSubjectDir} || true

# copy all tgz to the scratch space dir
echo `date`" :COPYING TGZs TO SCRATCH: ${TempSubjectDir}"
cp ${TGZDIR}/* ${TempSubjectDir}

# unpack tgz to ABCD_DCMs directory
mkdir ${TempSubjectDir}/DCMs
echo `date`" :UNPACKING DCMs: ${TempSubjectDir}/DCMs"
for tgz in ${TempSubjectDir}/*.tgz; do
    echo $tgz
    tar -xzf ${tgz} -C ${TempSubjectDir}/DCMs
done


# # IMPORTANT PATH DEPENDENCY VARIABLES AT OHSU IN SLURM CLUSTER
# export PATH=.../anaconda2/bin:${PATH} # relevant Python path with dcm2bids
# export PATH=.../mricrogl_lx/:${PATH} # relevant dcm2niix path
# export PATH=.../pigz-2.4/:${PATH} # relevant pigz path for improved (de)compression


# convert DCM to BIDS and move to ABCD directory
mkdir ${TempSubjectDir}/BIDS_unprocessed
echo ${participant}
echo `date`" :RUNNING dcm2bids"
echo "ABCD2BIDS_DIR is ${ABCD2BIDS_DIR}"
dcm2bids -d ${TempSubjectDir}/DCMs/${SUB} -p ${participant} -s ${session} -c ${ABCD2BIDS_DIR}/abcd_dcm2bids.conf -o ${TempSubjectDir}/BIDS_unprocessed --forceDcm2niix --clobber

echo `date`" :CHECKING BIDS ORDERING OF EPIs"
if [[ -e ${TempSubjectDir}/BIDS_unprocessed/${SUB}/${VISIT}/func ]]; then
    if [[ `${ABCD2BIDS_DIR}/src/run_order_fix.py ${TempSubjectDir}/BIDS_unprocessed ${TempSubjectDir}/bids_order_error.json ${TempSubjectDir}/bids_order_map.json --all --subject ${SUB}` == ${SUB} ]]; then
        echo BIDS correctly ordered
    else
        echo ERROR: BIDS incorrectly ordered even after running run_order_fix.py
        exit
    fi
else
    echo "No functional images found for subject ${SUB}. Skipping sefm_eval_and_json_editor to copy and rename source data."
    exit
fi

# select best fieldmap and update sidecar jsons
echo `date`" :RUNNING SEFM SELECTION AND EDITING SIDECAR JSONS"
if [ -d ${TempSubjectDir}/BIDS_unprocessed/${SUB}/${VISIT}/fmap ]; then
    cp ${ROOT_BIDSINPUT}/dataset_description.json ${TempSubjectDir}/BIDS_unprocessed
    ${ABCD2BIDS_DIR}/src/sefm_eval_and_json_editor.py ${TempSubjectDir}/BIDS_unprocessed/ ${FSL_DIR} ${MRE_DIR} --participant-label=${participant} --output_dir $ROOT_BIDSINPUT
fi

rm ${TempSubjectDir}/BIDS_unprocessed/${SUB}/ses-baselineYear1Arm1/fmap/*dir-both* 2> /dev/null || true

# rename EventRelatedInformation
echo `date`" :COPY AND RENAME SOURCE DATA"
srcdata_dir=${TempSubjectDir}/BIDS_unprocessed/sourcedata/${SUB}/ses-baselineYear1Arm1/func
echo $srcdata_dir
ls ${TempSubjectDir}/DCMs/${SUB}/ses-baselineYear1Arm1/func/*EventRelatedInformation.txt
if ls ${TempSubjectDir}/DCMs/${SUB}/ses-baselineYear1Arm1/func/*EventRelatedInformation.txt > /dev/null 2>&1; then
    mkdir -p ${srcdata_dir}
    echo "Made srcdata_dir"
fi
MID_evs=`ls ${TempSubjectDir}/DCMs/${SUB}/ses-baselineYear1Arm1/func/*MID*EventRelatedInformation.txt 2>/dev/null`
SST_evs=`ls ${TempSubjectDir}/DCMs/${SUB}/ses-baselineYear1Arm1/func/*SST*EventRelatedInformation.txt 2>/dev/null`
nBack_evs=`ls ${TempSubjectDir}/DCMs/${SUB}/ses-baselineYear1Arm1/func/*nBack*EventRelatedInformation.txt 2>/dev/null`
echo ${MID_evs}
echo ${SST_evs}
echo ${nBack_evs}
if [ `echo ${MID_evs} | wc -w` -eq 2 ]; then
    i=1
    for ev in ${MID_evs}; do
        cp ${ev} ${srcdata_dir}/${SUB}_ses-baselineYear1Arm1_task-MID_run-0${i}_bold_EventRelatedInformation.txt
        ((i++))
    done
fi
if [ `echo ${SST_evs} | wc -w` -eq 2 ]; then
    i=1
    for ev in ${SST_evs}; do
        cp ${ev} ${srcdata_dir}/${SUB}_ses-baselineYear1Arm1_task-SST_run-0${i}_bold_EventRelatedInformation.txt
        ((i++))
    done
fi
if [ `echo ${nBack_evs} | wc -w` -eq 2 ]; then
    i=1
    for ev in ${nBack_evs}; do
        cp ${ev} ${srcdata_dir}/${SUB}_ses-baselineYear1Arm1_task-nback_run-0${i}_bold_EventRelatedInformation.txt
        ((i++))
    done
fi

echo `date`" :COPYING SOURCE AND SORTED DATA BACK: ${ROOT_BIDSINPUT}"

TEMPBIDSINPUT=${TempSubjectDir}/BIDS_unprocessed/${SUB}
if [ -d ${TEMPBIDSINPUT} ] ; then
    echo `date`" :CHMOD BIDS INPUT"
    chmod g+rw -R ${TEMPBIDSINPUT} || true
    echo `date`" :COPY BIDS INPUT"
    mkdir -p ${ROOT_BIDSINPUT}
    cp -r ${TEMPBIDSINPUT} ${ROOT_BIDSINPUT}/
fi

ROOT_SRCDATA=${ROOT_BIDSINPUT}/sourcedata
TEMPSRCDATA=${TempSubjectDir}/BIDS_unprocessed/sourcedata/${SUB}
if [ -d ${TEMPSRCDATA} ] ; then
    echo `date`" :CHMOD SOURCEDATA"
    chmod g+rw -R ${TEMPSRCDATA} || true
    echo `date`" :COPY SOURCEDATA"
    mkdir -p ${ROOT_SRCDATA}
    cp -r ${TEMPSRCDATA} ${ROOT_SRCDATA}/
fi

echo `date`" :UNPACKING AND SETUP COMPLETE: ${SUB}/${VISIT}"
