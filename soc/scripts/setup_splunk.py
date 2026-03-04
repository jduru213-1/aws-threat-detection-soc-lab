# Purpose: This script is used to setup the Splunk environment for the Lab by creating the indexes and validating the indexes are created
# Author: Justin Duru
# Date: 2026-03-03
# Version: 1.0.0
# Run: python ./scripts/setup_splunk.py from the soc folder and follow the prompt to enter the Splunk password

# Import the necessary libraries
from turtle import update
import argparse # Enables the use of command line arguments
import getpass # Provides a secure way to enter a password interactively
import os # Provides a way to interact with the operating system

import splunklib.client as client # Provides a way to interact with the Splunk API

# Indexes you must for the Lab
DEFAULT_INDEXES = [ # List of indexes you must create for the Lab
    "aws_cloudtrail",
    "aws_config",
    "aws_guardduty",
    "aws_vpcflow",
]

def connect_splunk(host, port, username, password): # Connects to the Splunk API
    # Note: verify=False skips certificate verification for the self-signed certificate
    service = client.connect( 
        host=host, # Hostname of the Splunk server
        port=port, # Port of the Splunk server
        username=username, # Username for the Splunk server
        password=password, # Password for the Splunk server
        scheme="https", # Scheme for the Splunk server
        verify=False, # Verify the certificate of the Splunk server
    )
    return service # Returns the service object

def ensure_indexes(service, index_names): # Ensures the indexes exist
    for name in index_names: # Iterates through the list of indexes
        if name in service.indexes: 
             print(f"[indexes] {name} already exists") # 
        else:
            service.indexes.create(name) # Create the index
            print(f"[indexes] {name} does not exist...creating index") # Print the index that does not exist

def main(): # Main function
    parser = argparse.ArgumentParser(description="Setup Splunk for the Lab") # Creates a parser for the command line arguments
    parser.add_argument("--host", default="localhost", help="Splunk host") # Adds the host argument to the parser
    parser.add_argument("--port", default=8089, help="Splunk port") # Adds the port argument to the parser
    parser.add_argument("--username", default="admin", help="Splunk username") # Adds the username argument to the parser
    parser.add_argument("--password", default="ChangeMe123!", help="Splunk password") # Adds the password argument to the parser

    args = parser.parse_args() # Parses the command line arguments

    password = getpass.getpass(prompt="Enter your Splunk password: ") # Gets the password from the user

    service = connect_splunk( # Connects to the Splunk API
        host=args.host,
        port=args.port,
        username=args.username,
        password=password,
    )

    ensure_indexes(service, DEFAULT_INDEXES) # Ensures the indexes exist

    print("[setup] Splunk setup complete") # Prints the setup complete message

if __name__ == "__main__": # Runs the main function
    main()
