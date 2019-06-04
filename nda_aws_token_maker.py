#! /usr/bin/env python

from nda_aws_token_generator import *
import getpass
import os

if sys.version_info[0] < 3:
    # Python 2 specific imports
    input = raw_input
    from ConfigParser import ConfigParser
else:
    # Python 3 specific imports
    from configparser import ConfigParser


web_service_url = 'https://nda.nih.gov/DataManager/dataManager'
username  = input('Enter your NIMH Data Archives username: ') # Replace with empty string and instructions to put username here
password  = getpass.getpass('Enter your NIMH Data Archives password: ') # Replace with empty string and instructions to put password here

generator = NDATokenGenerator(web_service_url)

token = generator.generate_token(username, password)

# Read .aws/credentials from the user's HOME directory, add a NDA profile, and update with credentials
parser = ConfigParser()
parser.read(os.path.expanduser('~/.aws/credentials'))

if not parser.has_section('NDA'):
    parser.add_section('NDA')
parser.set('NDA', 'aws_access_key_id', token.access_key)
parser.set('NDA', 'aws_secret_access_key', token.secret_key)
parser.set('NDA', 'aws_session_token', token.session)

with open (os.path.expanduser('~/.aws/credentials'), 'w') as configfile:
    parser.write(configfile)

print('aws_access_key_id=%s\n'
      'aws_secret_access_key=%s\n'
      'security_token=%s\n'
      'expiration=%s\n'
      %(token.access_key,
        token.secret_key,
        token.session,
        token.expiration)
      )
