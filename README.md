# nagios_aws

This script will read from an SQS queue and send to the Nagios NRDP process or a log file or both.

# Setup

## Python

The following python modules are imported:

logging
sys
os
subprocess
from subprocess import call
json
boto3
time
re
collections
datetime

## boto/AWS

boto3 documentation can be found here:

https://boto3.readthedocs.io/en/latest/

The script assumes AWS credentials have been configured.

## Nagios NRDP

In order to send events to Nagios NRDP you will need a local installation of NRDP. Details on source loction and install instructions can be found here:

https://support.nagios.com/kb/article/nrdp-installing-nrdp-from-source-602.html#CentOS

Further information on NRDP can be found here:

https://support.nagios.com/kb/article/nrdp-send_nrdp-client-599.html

## sqs_process.cfg

The following configuration is accepted by the script:

[config] 
sqs_queue = The name of the SQS queue you want to read from
num_messages = The number of messages to retrieve in once call
region_name = The AWS region you want to connect to
cycle_time = The length of time (in seconds) between polling the queue
nrdp_ouput_file = The temporary output file which is used to send event data to NRDP
send_nrdp_path = The path to the nrdp client (include the full path including the final slash. i.e. /opt/nrdp/)
nrdp_token = The NRDP token
nrdp_http_path = The HTTP path to NRDP (i.e. //localhost/nrdp/)
log_file = The path to the log file for the sqs_process.py 
log_level = The logging level
output_method = The output method - either nrdp, log or both
output_log = If log method has been selected this is the path to that log
