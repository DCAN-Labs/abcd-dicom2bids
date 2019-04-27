#! /usr/bin/env python

from nda_aws_token_generator import *
import getpass

web_service_url = 'https://ndar.nih.gov/DataManager/dataManager'
#username  = raw_input('Enter your NIMH Data Archives username:')
#password  = getpass.getpass('Enter your NIMH Data Archives password:')
username = "FILL_IN_YOUR_NDA_USERNAME"
password = "FILL_IN_YOUR_NDA_PASSWORD"

generator = NDATokenGenerator(web_service_url)

token = generator.generate_token(username,password)

print('aws_access_key_id=%s\n'
      'aws_secret_access_key=%s\n'
      'security_token=%s\n'
      'expiration=%s\n'
      %(token.access_key,
        token.secret_key,
        token.session,
        token.expiration)
      )

import os
from configparser import ConfigParser
parser = ConfigParser()
parser.read(os.path.expanduser('~/.aws/credentials'))

if not parser.has_section('NDA'):
    parser.add_section('NDA')

parser.set('NDA', 'aws_access_key_id', token.access_key)
parser.set('NDA', 'aws_secret_access_key', token.secret_key)
parser.set('NDA', 'aws_session_token', token.session)

with open (os.path.expanduser('~/.aws/credentials'), 'w') as configfile:
    parser.write(configfile)
