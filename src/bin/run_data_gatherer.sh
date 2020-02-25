#!/bin/sh
# script for execution of deployed applications
#
# Sets up the MATLAB Runtime environment for the current $ARCH and executes 
# the specified command.
#
exe_name=$0
exe_dir=`dirname "$0"`

# Added 2020-01-29 to ensure that $TMPDIR is nonempty and points to a real path
if [ "x$TMPDIR" = "x" ]; then
    export TMPDIR=/tmp
fi
if [ ! -d $TMPDIR ]; then
    mkdir -p $TMPDIR;
fi
 
if [ ! -d $TMPDIR/$USER ]; then
    mkdir $TMPDIR/$USER
fi

echo "------------------------------------------"
if [ "x$1" = "x" ]; then
  echo Usage:
  echo    $0 \<deployedMCRroot\> args
else
  echo Setting up environment variables
  MCRROOT="$1"
  echo ---
  LD_LIBRARY_PATH=.:${MCRROOT}/runtime/glnxa64 ;
  LD_LIBRARY_PATH=${LD_LIBRARY_PATH}:${MCRROOT}/bin/glnxa64 ;
  LD_LIBRARY_PATH=${LD_LIBRARY_PATH}:${MCRROOT}/sys/os/glnxa64;
  LD_LIBRARY_PATH=${LD_LIBRARY_PATH}:${MCRROOT}/sys/opengl/lib/glnxa64;
  export LD_LIBRARY_PATH;
  echo LD_LIBRARY_PATH is ${LD_LIBRARY_PATH};
  shift 1
  RANDHASH=`cat /dev/urandom | tr -cd "a-f0-9" | head -c 8`
  export MCR_CACHE_ROOT=$TMPDIR/$USER/$RANDHASH
  mkdir -p $MCR_CACHE_ROOT
  args=
  while [ $# -gt 0 ]; do
      token=$1
      args="${args} \"${token}\"" 
      shift
  done
  eval "\"${exe_dir}/data_gatherer\"" $args
fi
exit

