#! /usr/bin/env bash
# compiles all 

function usage() {
   echo "usage: `basename $0` <Matlab Compiler>"
}

echo STARTED:
date

if [ $# -eq 1 ]; then
  MCC_FILE="$1"
fi

if [ ! -e $MCC_FILE ]; then
  echo "unable to locate matlab compiler"
  usage
  exit 1
fi

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"

# set paths
CODE="${DIR}"
BIN="${DIR}/bin"

fmr="rm -f ${DIR}/bin/run_data_gatherer.sh ; ${MCC_FILE} -v -m -R -singleCompThread -R -nodisplay -o data_gatherer ${CODE}/data_gatherer.m"

echo $fmr
eval $fmr

mv "run_data_gatherer.sh" "./bin/"
mv "data_gatherer" "./bin/"

#add MCR_CACHE_ROOT to all run scripts for Exahead processing
sed -i '/  shift 1/a \  RANDHASH=`cat /dev/urandom | tr -cd "a-f0-9" | head -c 8`\n  export MCR_CACHE_ROOT=$TMPDIR/$USER/$RANDHASH\n  mkdir -p $MCR_CACHE_ROOT' ${BIN}/run_*.sh

echo ENDED:
date
