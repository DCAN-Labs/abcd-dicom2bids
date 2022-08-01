#!/usr/bin/python

"""
This program is designed to run on an Amazon Web Services EC2 instance, running linux.
As a pre-requisite, Python 2.6 or higher will be needed for the script to run, which comes
pre-packaged on the standard Linux Amazon Machine Image (AMI).

This program will:
- Download the NDAR Download Manager (http://ndar.nih.gov)
- Download + configure s3cmd (s3tools.org)
- Configure the aws-cli tools pre-packaged with standard AWS Linux AMIs (http://aws.amazon.com/documentation/cli/)
- Generate a set of access credentials for NDAR data stored as S3 objects.

Configuration:
- Set your ndar_username and ndar_password inside this file
  OR
- Set the enviornment variables ndar_username and ndar_password:
  example: export ndar_username="John Doe"
           export ndar_password="sup3r S3cret"

NOTES: 
- Data access is monitoried.
- Access to data requires an NDAR account.
- A Data Use Certification must be signed and agreed to.
- Downloading and persisting data, as well as any kind of redistribution is strictly prohibited.
- Please read the NDAR Omics policy as it applies to Data Download https://ndar.nih.gov/faq.html#faq64
"""  
from os.path import expanduser 
import sys
import argparse
import stat
import fileinput
import getpass
from subprocess import call
try:
    from nda_aws_token_generator import *
except ImportError:
    from src.nda_aws_token_generator import *
try:
    import ConfigParser
except ImportError:
    import configparser as ConfigParser
import os
try:
    import urllib2
except ImportError:
    from urllib import request
import zipfile
import tarfile

# Default config_dir directory, set this to the config_dir folder for the user you plan to use, (i.e., ec2-uesr, ubuntu, etc.)
#config_dir = '/config_dir/ec2-user'
#config_dir = '/config_dir/ubuntu'
#config_dir = '/config_dir/elisonj/perr0372/Projects'
#config_dir = os.path.expanduser('~')
src_path = os.path.abspath(os.path.dirname(__file__))


#config_dir = expanduser("~")
#print ('Home is %s' %config_dir) 
def download_file( url, dest ):
    print('Downloading {} to {}'.format(url, dest))
    if sys.version_info[0] < 3:    
        f = urllib2.urlopen( url )
    else:
        f = request.urlopen( url )
    data = f.read()
    with open( dest, "wb") as local_file:
        local_file.write(data)
        local_file.close()

def unzip_file( filename ):
    z = zipfile.ZipFile(filename)
    for name in z.namelist():
        outpath = os.path.normpath(src_path + "/ndar_toolkit")
        z.extract( name, outpath )
    z.close()
    os.remove( filename )

def shell_source(script, config_dir):
   f = open (os.path.normpath( config_dir + '/ndar_toolkit/ndar_update_keys.sh'), 'r')
   line = f.readline()
   ndar_username = line.split("=",1)[1]
   line = f.readline()
   ndar_password = line.split("=",1)[1]
   return ndar_username.strip(), ndar_password.strip()  

def create_default_config(config_dir, config_file):
    f = open (os.path.normpath(config_dir + config_file), 'wt')
    f.write('[NDAR]\n')
    f.close()

def make_aws_tokens(username, password):
    web_service_url = 'https://nda.nih.gov/DataManager/dataManager'
    generator = NDATokenGenerator(web_service_url)
    try:
        token = generator.generate_token(username, password)
    except Exception as e:
        print("Failed to create NDAR token.")
        sys.exit(1)
    return token

def write_aws_config(config_dir, config_file, profile):
    config_aws_cli = ConfigParser.ConfigParser()
    # If a config file already exists read profiles from there and update
    if (os.path.isfile(os.path.normpath(config_dir + config_file))):
        config_aws_cli.read(os.path.normpath(config_dir + config_file))
    # if the profile doesn't exist create it
    if not config_aws_cli.has_section(profile):
        config_aws_cli.add_section(profile)
    config_aws_cli.set(profile, 'aws_access_key_id', myvars["accessKey"])
    config_aws_cli.set(profile, 'aws_secret_access_key', myvars["secretKey"])
    config_aws_cli.set(profile, 'aws_session_token', myvars["sessionToken"])
    config_aws_cli.set(profile, 'region', 'us-east-1')

    with open(os.path.normpath(config_dir + config_file), 'wt') as configfile:
        config_aws_cli.write(configfile)

def write_s3cmd_config(config_dir, config_file):
    config_s3cmd = ConfigParser.ConfigParser()

    if (os.path.isfile( os.path.normpath(config_dir + config_file ))):
        config_s3cmd.read(os.path.normpath(config_dir + config_file))
    if not config_s3cmd.has_section('default'):
        config_s3cmd.add_section('default')
    print('Updating access keys and token for {} profile in {}'.format('default', os.path.normpath(config_dir + config_file)))

    s3cmd_info = {
        'access_key': myvars["accessKey"],
        'secret_key': myvars["secretKey"],
        'access_token': myvars["sessionToken"],
        'bucket_location': "US",
        'cloudfront_host': 'cloudfront.amazonaws.com',
        'default_mime_type': 'binary/octet-stream',
        'delete_removed': 'False',
        'dry_run': 'False',
        'enable_multipart': 'True',
        'encoding': 'UTF-8',
        'encrypt': 'False',
        'follow_symlinks': 'False',
        'force': 'False',
        'get_continue': 'False',
        'gpg_command': '/usr/bin/gpg',
        'gpg_decrypt': '%(gpg_command)s -d --verbose --no-use-agent --batch --yes --passphrase-fd %(passphrase_fd)s -o %(output_file)s %(input_file)s',
        'gpg_encrypt': '%(gpg_command)s -c --verbose --no-use-agent --batch --yes --passphrase-fd %(passphrase_fd)s -o %(output_file)s %(input_file)s',
        'gpg_passphrase': '',
        'guess_mime_type': 'True',
        'host_base': 's3.amazonaws.com',
        'host_bucket': '%(bucket)s.s3.amazonaws.com',
        'human_readable_sizes': 'False',
        'invalidate_on_cf': 'False',
        'list_md5': 'False',
        'log_target_prefix': '',
        'mime_type': '',
        'multipart_chunk_size_mb': '15',
        'multipart_copy_size': '15728640',
        'preserve_attrs': 'True',
        'progress_meter': 'True',
        'proxy_host': '',
        'proxy_port': '0',
        'recursive': 'False',
        'recv_chunk': '4096',
        'reduced_redundancy': 'False',
        'send_chunk': '4096',
        'simpledb_host': 'sdb.amazonaws.com',
        'skip_existing': 'False',
        'socket_timeout': '300',
        'urlencoding_mode': 'normal',
        'use_https': 'False',
        'verbosity': 'WARNING',
        'website_endpoint': 'http://%(bucket)s.s3-website-%(location)s.amazonaws.com/',
        'website_error': '',
        'website_index': 'index.html'
    }
    #config_s3cmd.add_section('default')
    for key in s3cmd_info.keys():
        config_s3cmd.set('default', key, s3cmd_info[key])
    with open( os.path.normpath(config_dir + config_file), 'wt') as configfile:
        config_s3cmd.write(configfile)


def generate_parser(parser=None):
    """
    generates argument parser for this prgoram.
    """
    parser = argparse.ArgumentParser(
        prog='ndar_update_keys',
        description='   1) Downloads and installs NDA downloadmanager.jar and s3cmd. ' \
                    '   2) Generates an aws credentials file and an s3cmd config for the ABCD NDA bucket. ' \
                    '   3) Generates a temporary NDA token for downloading.'
    )
    parser.add_argument(
        '-u', '--username', required=False, default=None, help='NDA username'
    )
    parser.add_argument(
        '-p', '--password', required=False, default=None, help='NDA encrypted password'
    )
    parser.add_argument(
        '-c', '--config-dir', required=False, default=os.path.expanduser('~'), help='Temporary directory to for the s3 config file. Default: config_dir directory (~)'
    )

    return parser
    

if __name__ == '__main__':


    if not os.path.exists (os.path.normpath(src_path + "/ndar_toolkit")):
        os.makedirs (os.path.normpath(src_path + "/ndar_toolkit"))


    # Try to get NDA credentials from command line args passed in; if there are no
    # args, then prompt user for credentials
    parser = generate_parser()
    args = parser.parse_args()
    
    if args.username is not None and args.password is not None:
        ndar_username = args.username
        ndar_password = args.password
    else:
        ndar_username = input('Enter your NIMH Data Archives username: ')
        ndar_password = getpass.getpass('Enter your NIMH Data Archives password: ')

    config_dir = args.config_dir
    
    
    # Creates location for aws credentials files
    if not os.path.exists ( os.path.normpath(config_dir + '/.aws/')):
        os.makedirs ( os.path.normpath(config_dir + '/.aws/'))
        #os.makedirs ( '/root/.aws/' )

    
    if not (os.path.isfile( os.path.normpath(src_path + '/ndar_toolkit/s3cmd-master/s3cmd' ))):
        download_file("https://github.com/s3tools/s3cmd/archive/master.zip", src_path + '/s3cmd-master.zip')
        unzip_file( os.path.normpath(src_path + '/s3cmd-master.zip'))
        for i, line in enumerate(fileinput.input( os.path.normpath(src_path + '/ndar_toolkit/s3cmd-master/S3/S3.py'), inplace=1)):
            sys.stdout.write(line.replace('self.s3.config.role_refresh()', 
                                          '# Role refresh is with NDAR Download Manager\n# self.s3.config.role_refresh()')) 
        st = os.stat(os.path.normpath(src_path + '/ndar_toolkit/s3cmd-master/s3cmd'))
        os.chmod(os.path.normpath(src_path + '/ndar_toolkit/s3cmd-master/s3cmd'), st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        
        if not os.path.exists ( os.path.normpath(src_path + '/bin/' )):
            os.makedirs ( os.path.normpath(src_path + '/bin/' ))
    
        if os.path.lexists( os.path.normpath(src_path + '/bin/s3cmd')):
            os.remove( os.path.normpath(src_path + '/bin/s3cmd'))
        try:
            os.symlink(os.path.normpath(src_path + '/ndar_toolkit/s3cmd-master/s3cmd'), src_path + '/bin/s3cmd')
        except:
            pass

    print ("Generating new keys and updating config files")
    token = make_aws_tokens(ndar_username, ndar_password)

    myvars={}
    myvars["accessKey"] = token.access_key
    myvars["secretKey"] = token.secret_key
    myvars["sessionToken"] = token.session
    
    os.environ["AWS_ACCESS_KEY_ID"] = myvars["accessKey"]
    os.environ["AWS_SECRET_ACCESS_KEY"] = myvars["secretKey"]
    os.environ["AWS_SESSION_TOKEN"] = myvars["sessionToken"]

    #Additional entries may be necessary depending on environment, to write configuration file to config_dir directory
    write_aws_config( config_dir, '/.aws/credentials', 'NDAR')
    write_aws_config( config_dir, '/.aws/config', 'profile NDAR')
    write_s3cmd_config( config_dir, '/.s3cfg-ndar')
