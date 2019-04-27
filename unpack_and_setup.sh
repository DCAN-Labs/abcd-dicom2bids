#! /bin/bash

set -e

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



SUB=$1 # Full BIDS formatted subject ID (sub-SUBJECTID)
VISIT=$2 # Full BIDS formatted session ID (ses-SESSIONID)
TGZDIR=$3 # Path to directory containing all .tgz for subject

participant=`echo ${SUB} | sed 's|sub-||'`
session=`echo ${VISIT} | sed 's|ses-||'`


date
hostname
echo ${SLURM_JOB_ID}

# Setup scratch space directory
ScratchSpaceDir=/mnt/scratch/fnl_lab
if [ ! -d ${ScratchSpaceDir} ]; then
    mkdir -p ${ScratchSpaceDir}
    chown :fnl_lab ${ScratchSpaceDir} || true
    chmod 770 ${ScratchSpaceDir} || true
fi
RandomHash=`cat /dev/urandom | tr -cd 'a-f0-9' | head -c 16`
TempSubjectDir=${ScratchSpaceDir}/${RandomHash}
mkdir -p ${TempSubjectDir}
chown :fnl_lab ${TempSubjectDir} || true
echo "TempSubjectDir = ${TempSubjectDir}"

# copy all tgz to the scratch space dir
echo `date`" :COPYING TGZs TO SCRATCH"
cp ${TGZDIR}/* ${TempSubjectDir}

# unpack tgz to ABCD_DCMs directory
mkdir ${TempSubjectDir}/DCMs
echo `date`" :UNPACKING DCMs"
for tgz in ${TempSubjectDir}/*.tgz; do
    echo $tgz
    tar -xzf ${tgz} -C ${TempSubjectDir}/DCMs
done


# IMPORTANT PATH DEPENDENCY VARIABLES
export PATH=.../anaconda2/bin:${PATH} # relevant Python path with dcm2bids
export PATH=.../mricrogl_lx/:${PATH} # relevant dcm2niix path
export PATH=.../pigz-2.4/:${PATH} # relevant pigz path for improved (de)compression



# convert DCM to BIDS and move to ABCD directory
mkdir ${TempSubjectDir}/BIDS_unprocessed
echo ${participant}
echo `date`" :RUNNING dcm2bids"
dcm2bids -d ${TempSubjectDir}/DCMs/${SUB} -p ${participant} -s ${session} -c `dirname $0`/abcd_dcm2bids.conf -o ${TempSubjectDir}/BIDS_unprocessed --forceDcm2niix --clobber

echo `date`" :CHECKING BIDS ORDERING OF EPIs"
if [ -e ${TempSubjectDir}/BIDS_unprocessed/${SUB}/${VISIT}/func ]; then
    if [ `.../run_order_fix.py ${TempSubjectDir}/BIDS_unprocessed ${TempSubjectDir}/bids_order_error.json ${TempSubjectDir}/bids_order_map.json --all --subject ${SUB}` == ${SUB} ]; then
        echo BIDS correctly ordered
    else
        echo ERROR: BIDS incorrectly ordered even after running run_order_fix.py
        exit
    fi
else
    echo ERROR: No functional images found T1 only processing not yet enabeled
    exit
fi

# select best fieldmap and update sidecar jsons
echo `date`" :RUNNING SEFM SELECTION AND EDITING SIDECAR JSONS"
`dirname $0`/sefm_eval_and_json_editor.py ${TempSubjectDir}/BIDS_unprocessed/${SUB} --participant-label=${participant}

rm ${TempSubjectDir}/BIDS_unprocessed/${SUB}/ses-baselineYear1Arm1/fmap/*dir-both* 2> /dev/null || true

# rename EventRelatedInformation
echo `date`" :COPY AND RENAME SOURCE DATA"
srcdata_dir=${TempSubjectDir}/BIDS_unprocessed/sourcedata/${SUB}/ses-baselineYear1Arm1/func
if ls ${TempSubjectDir}/DCMs/${SUB}/ses-baselineYear1Arm1/func/*EventRelatedInformation.txt > /dev/null 2>&1; then
    mkdir -p ${srcdata_dir}
fi
MID_evs=`ls ${TempSubjectDir}/DCMs/${SUB}/ses-baselineYear1Arm1/func/*MID*EventRelatedInformation.txt 2>/dev/null`
SST_evs=`ls ${TempSubjectDir}/DCMs/${SUB}/ses-baselineYear1Arm1/func/*SST*EventRelatedInformation.txt 2>/dev/null`
nBack_evs=`ls ${TempSubjectDir}/DCMs/${SUB}/ses-baselineYear1Arm1/func/*nBack*EventRelatedInformation.txt 2>/dev/null`
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
        cp ${ev} ${srcdata_dir}/${SUB}_ses-baselineYear1Arm1_task-nBack_run-0${i}_bold_EventRelatedInformation.txt
        ((i++))
    done
fi

echo `date`" :COPYING SOURCE AND SORTED DATA BACK TO RDS"

ROOT_BIDSINPUT=.../ABCD
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

echo `date`" :UNPACKING AND SETUP COMPLETE"
