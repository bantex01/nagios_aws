#!/usr/bin/python

# Adding in comment

import sys
import os
import subprocess
from subprocess import call
import json
import boto3
import time
import re
import collections

def tree():
    return collections.defaultdict(tree)


def process_cfg():

	# Let's set some defaults
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
		sys.exit(2)

	# Certain config items are needed, bomb out if we haven't got them

	for cfg_item in ("sqs_queue","region_name","send_nrdp_path","nrdp_token","nrdp_http_path"):
		if cfg_item not in SQS_CONFIG['config']:
			print "item not found "+str(cfg_item)
			sys.exit(2)

	for key in SQS_CONFIG:
		print "key "+str(key) + "- " +str(SQS_CONFIG[key]) + "\n"


def run():

	while True:
		process_messages()
		time.sleep(int(SQS_CONFIG['config']['cycle_time']))


def process_messages():

	sqs = boto3.resource('sqs', region_name=SQS_CONFIG['config']['region_name'])
	# Get the queue
	queue = sqs.get_queue_by_name(QueueName='nagios_alert_q')
	messages=queue.receive_messages()
	if (len(messages)> 0) :
		print "Messages found "+str(len(messages))

		# We have messages, let's get the output file ready

		output_file = open(SQS_CONFIG['config']['nrdp_output_file'],'w')
		output_file.write("<?xml version='1.0'?>\n")
		output_file.write("<checkresults>\n")

		while len(messages)>0:

			for msg in messages:
        			#print(msg.body)
        			body_json = json.loads(msg.body)
        			#msg_id = body_json['MessageId']
        			#print str(msg_id)

        			# The Message is a json payload too, let's bring it in, as we need the detail

        			for key in body_json:
                			print str(key) + " - " + str(body_json[key])

        			print "\n\n\n"

        			msg_json = json.loads(body_json['Message'])


        			for key in msg_json:
                			print str(key) + " - " + str(msg_json[key])

        			instance_id = str(msg_json['Trigger']['Dimensions'][0]['value'])
        			alarm_name = str(msg_json['AlarmName'])
        			metric_name = str(msg_json['Trigger']['MetricName'])
        			region = str(msg_json['Region'])
        			aws_namespace = str(msg_json['Trigger']['Namespace'])
        			state_value = str(msg_json['NewStateValue'])

        			# Need to gather alarm sev from cfg file

        			if (state_value == "ALARM"):
                			state_value = "1"
        			else:
                			state_value = "0"

        			print "\n\n"

        			print state_value + " Namespace: " +aws_namespace + " Region: " +region + " Alarm fired for "+ instance_id + " alarm name " +alarm_name + " metric name is " +metric_name

        			# Need to add these details to the file we will pass to nrdp scripts

				output_file.write("<checkresult type=\"service\" checktype=\"1\">\n")
				output_file.write("<hostname>"+instance_id+"</hostname>\n")
				output_file.write("<servicename>"+metric_name+"</servicename>\n")
				output_file.write("<state>"+state_value+"</state>\n")
				output_file.write("<output>Namespace: "+aws_namespace+" Region: "+region+ " Instance ID: "+instance_id+" Alarm: "+alarm_name+ " Metric: "+metric_name+"</output>\n")
				output_file.write("</checkresult>\n")

				msg.delete()

			messages=queue.receive_messages()

		# Let's write the final line and close off
		output_file.write("</checkresults>")
		output_file.close()

		print "****************************************"

		#call(["/usr/local/nrdp/clients/send_nrdp.py","-u","http://localhost/nrdp/","-t","my_token","-f","nrdp.out"])
		call([SQS_CONFIG['config']['send_nrdp_path']+"/send_nrdp.py","-u",SQS_CONFIG['config']['nrdp_http_path'],"-t",SQS_CONFIG['config']['nrdp_token'],"-f",SQS_CONFIG['config']['nrdp_output_file']])
		os.remove(SQS_CONFIG['config']['nrdp_output_file'])

	else:
		print "No messages found"

###############################################################################
#
# Main
#
###############################################################################

RUN_DIR = os.path.dirname(os.path.join(os.getcwd(), __file__))
SQS_CONFIG = tree()
process_cfg()

if __name__ == "__main__":
	run()
