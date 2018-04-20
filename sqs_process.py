#!/usr/bin/python

import logging
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
import sys
import os
import subprocess
from subprocess import call
import json
import boto3
import time
import re
import collections
import datetime

#################################################################################################
# Functions
#################################################################################################


def setup_logger(name, log_file, level):

    	handler = logging.FileHandler(log_file)        
    	handler.setFormatter(formatter)

    	logger = logging.getLogger(name)
    	logger.setLevel(level)
    	logger.addHandler(handler)

	return logger


def tree():
	return collections.defaultdict(tree)


def process_cfg():

	cfg_logger = setup_logger('cfg_logger','sqs_process.err','INFO') 

	# Let's set some defaults
	SQS_CONFIG['config']['log_file'] = "sqs_process.log"
	SQS_CONFIG['config']['num_messages'] = 5
	SQS_CONFIG['config']['cycle_time'] = 60
	SQS_CONFIG['config']['nrdp_output_file'] = "/tmp/nrdp.out"

	conf_file = RUN_DIR + "/" + "sqs_process.cfg"
	if (os.path.exists(conf_file)):
		conf_file = open(conf_file,'r')
		for conf_line in conf_file:
			if (re.match(r'^#',conf_line)):
				continue
			if (re.match(r'^\[.*\]',conf_line)):
				config_attr = re.search(r'^\[(.*)\]',conf_line)
				continue
			
			if (re.match(r'^\w+|\W+\s?=\s?.*',conf_line)):
				cfg_items=re.search(r'^(\w+|\W+)\s?=\s?(.*)',conf_line)
				SQS_CONFIG[config_attr.group(1)][cfg_items.group(1)] = cfg_items.group(2)
	else:
		print "Conf file does not exist, aborting"
		cfg_logger.info("Cfg file "+conf_file + " does not exist, aborting")
		sys.exit(2)

	# Certain config items are needed, bomb out if we haven't got them

	for cfg_item in ("sqs_queue","region_name","send_nrdp_path","nrdp_token","nrdp_http_path","output_method"):
		if cfg_item not in SQS_CONFIG['config']:
			print "item not found "+str(cfg_item)
			cfg_logger.info("Needed cfg item not found - " +str(cfg_item))
			sys.exit(2)

	for key in SQS_CONFIG:
		print "key "+str(key) + "- " +str(SQS_CONFIG[key]) + "\n"	

	# If we're here we can assume all config needed is present so let's set up the output method

	output_methods = str(SQS_CONFIG['config']['output_method']).split(",")
	for method in output_methods:
		if (method == "nrdp"):
			for nrdp_options in ("send_nrdp_path","nrdp_token","nrdp_http_path"):
				if nrdp_options not in SQS_CONFIG['config']:
					print "nrdp options not found, aborting "+str(nrdp_options)
					cfg_logger.info("NRDP set but needed NRDP options not found - "+str(nrdp_options) +", aborting") 
					sys.exit(2)

			global SEND_NRDP
			SEND_NRDP = "1"
			#cfg_logger.info("Send to NRDP detected")
			print "in cfg, send nrdp is "+str(SEND_NRDP)

		elif (method == "log"):
			if "output_log" not in SQS_CONFIG['config']:
				print "log options not found, aborting : output_log"
				cfg_logger.info("Log method found, but no output log specified, aborting")	
				sys.exit(2)

			else:
				global OUTPUT_LOG
				OUTPUT_LOG = "1"
				#cfg_logger.info("Send to log detected")
				print "in cfg, output log is "+str(OUTPUT_LOG)

		else:
			print "output method unknown, aborting"
			cfg_logger.info("Unknown output method specified, specify log or nrdp or both, aborting")
			sys.exit(2)	


def run():

	while True:
		main_logger.info("Connecting to queue and processing messages") 
		process_messages()
		time.sleep(int(SQS_CONFIG['config']['cycle_time']))


def process_messages():

	#print "OUPUT_LOG is "+str(OUTPUT_LOG)
	#print "SEND_NRDP is "+str(SEND_NRDP)

	sqs = boto3.resource('sqs',region_name=SQS_CONFIG['config']['region_name'])
	# Get the queue
	queue = sqs.get_queue_by_name(QueueName=SQS_CONFIG['config']['sqs_queue'])
	messages=queue.receive_messages()
	if (len(messages)> 0) :
		print "Messages found "+str(len(messages))
		main_logger.info("Message found, processing...")

		if (SEND_NRDP == "1"):

			output_file = open(SQS_CONFIG['config']['nrdp_output_file'],'w')
			output_file.write("<?xml version='1.0'?>\n")
			output_file.write("<checkresults>\n")	

		while len(messages)>0:

			if (OUTPUT_LOG == "1"):
				output_log = open(SQS_CONFIG['config']['output_log'],'a')

			for msg in messages:
        			#print(msg.body)
        			body_json = json.loads(msg.body)
        			#msg_id = body_json['MessageId']
        			#print str(msg_id)

        			# The Message is a json payload too, let's bring it in, as we need the detail

        			for key in body_json:
					main_logger.debug(str(key) + " - " + str(body_json[key]))
                			print str(key) + " - " + str(body_json[key])

        			print "\n\n\n"

        			msg_json = json.loads(body_json['Message'])


        			for key in msg_json:
					main_logger.debug(str(key) + " - " + str(msg_json[key]))
                			print str(key) + " - " + str(msg_json[key])

        			instance_id = str(msg_json['Trigger']['Dimensions'][0]['value'])
        			alarm_name = str(msg_json['AlarmName'])
        			metric_name = str(msg_json['Trigger']['MetricName'])
        			region = str(msg_json['Region'])
        			aws_namespace = str(msg_json['Trigger']['Namespace'])
        			state_value = str(msg_json['NewStateValue'])
				old_state_value = str(msg_json['OldStateValue'])
				new_state_reason = str(msg_json['NewStateReason'])

				if (metric_name not in SQS_CONFIG[aws_namespace]):
					print "metric "+metric_name +" not in Namespace "+aws_namespace + " not in cfg file, deleting message"
					main_logger.debug("metric "+metric_name +" not in Namespace "+aws_namespace + " not in cfg file, deleting message")
					# Namespace there 
					msg.delete()

				else:
					main_logger.debug("metric "+metric_name + " is in cfg file, gathering needed details")
					print "metric "+metric_name + " IS in cfg, woohoo"

        				# Need to gather alarm sev from cfg file

        				if (state_value == "ALARM"):
                				#nagios_state_value = "1"
						main_logger.debug("State of message is ALARM, setting nagios severity")
						nagios_state_value = SQS_CONFIG[aws_namespace][metric_name]
						main_logger.debug("Nagios severity set to "+str(nagios_state_value))
						print "nag sev from cfg fiel is "+str(nagios_state_value)
        				else:
						print "not an ALARM message so nag state set to 0"
						main_logger.debug("State of message is OK, setting nagios severity to 0")
                				nagios_state_value = "0"

        				print "\n\n"

        				print "State: "+state_value + " - Previous State: "+old_state_value +" - Namespace: " +aws_namespace + " - Region: " +region + " - Summary: Alarm fired for "+ instance_id + " alarm name " +alarm_name + " metric name is " +metric_name + " - State Reason: "+new_state_reason
					
					main_logger.info("State: "+state_value + " - Previous State: "+old_state_value +" - Namespace: " +aws_namespace + " - Region: " +region + " - Summary: Alarm fired for "+ instance_id + " alarm name " +alarm_name + " metric name is " +metric_name + " - State Reason: "+new_state_reason)

        				# Need to add these details to the file we will pass to nrdp scripts

					if (SEND_NRDP == "1"):

						output_file.write("<checkresult type=\"service\" checktype=\"1\">\n")
						output_file.write("<hostname>"+instance_id+"</hostname>\n")
						output_file.write("<servicename>"+metric_name+"</servicename>\n")
						output_file.write("<state>"+nagios_state_value+"</state>\n")
						output_file.write("<output>State : "+state_value + " - Previous State: "+old_state_value +" - Namespace: "+aws_namespace+" - Region: "+region+ " - Instance ID: "+instance_id+" - Alarm: "+alarm_name+ " - Metric: "+metric_name+ " - State Reason: "+new_state_reason+"</output>\n")
						output_file.write("</checkresult>\n")

					if (OUTPUT_LOG == "1"):
						output_log.write(str(datetime.datetime.now()) + " State: "+state_value + " - Previous State: "+old_state_value +" - Namespace: "+aws_namespace+" - Region: "+region+ " - Instance ID: "+instance_id+" - Alarm: "+alarm_name+ " - Metric: "+metric_name + " - State Reason: "+new_state_reason +"\n")
						output_log.close()	

					msg.delete()

			messages=queue.receive_messages()

		if (SEND_NRDP == "1"):
			print "send_nrdp is "+str(SEND_NRDP)
			# Let's write the final line and close off
			output_file.write("</checkresults>")
			output_file.close()

			call([SQS_CONFIG['config']['send_nrdp_path']+"/send_nrdp.py","-u",SQS_CONFIG['config']['nrdp_http_path'],"-t",SQS_CONFIG['config']['nrdp_token'],"-f",SQS_CONFIG['config']['nrdp_output_file']])
			os.remove(SQS_CONFIG['config']['nrdp_output_file'])

		print "****************************************"

	else:
		main_logger.info("No messages found, sleeping")

###############################################################################
# Main
###############################################################################

OUTPUT_LOG = "0"
SEND_NRDP = "0"
RUN_DIR = os.path.dirname(os.path.join(os.getcwd(), __file__))
SQS_CONFIG = tree()

process_cfg()
#setup_logging()
#global main_logger
main_logger = setup_logger('main_logger',SQS_CONFIG['config']['log_file'],SQS_CONFIG['config']['log_level'])

if __name__ == "__main__":
	main_logger.info("Entering daemon mode, messages will be checked on a "+str(SQS_CONFIG['config']['cycle_time']) + " cycle time")
	run()

