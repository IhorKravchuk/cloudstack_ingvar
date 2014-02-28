#!/usr/bin/env python

# Author: Ihor Kravchuk Ihor.Kravchuk@radialpoint.com
# based on Python CloudStack wrapper from Will Stevens - wstevens@cloudops.com
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import urllib
import urllib2
import hmac
import hashlib
import base64
import json
import pprint
import random
import string
import time
import datetime
import commands


class CloudstackAPI(object):
    """
    Login and run queries against the Cloudstack API.
    Example Usage: 
    cs_api = CloudstackAPI(api_key='api_key', secret_key='secret_key'))
    accounts = cs_api.request(dict({'command':'listAccounts'}))
    
    """
    
    def __init__(self, protocol='http', host='127.0.0.1:8080', uri='/client/api', api_key=None, secret_key=None, logging=True, async_poll_interval=5):        
        self.protocol = protocol
        self.host = host
        self.uri = uri
        self.api_key = api_key
        self.secret_key = secret_key
        self.errors = []
        self.logging = logging
        self.async_poll_interval = async_poll_interval
        
    def request(self, params):
        """Builds a query from params and return a json object of the result or None"""
        if self.api_key and self.secret_key:
            # add the default and dynamic params
            params['response'] = 'json'
            params['apiKey'] = self.api_key

            # build the query string
            query_params = map(lambda (k,v):k+"="+urllib.quote(str(v)).replace('/', '%2F'), params.items())
            query_string = "&".join(query_params)
            
            # build signature
            query_params.sort()
            signature_string = "&".join(query_params).lower()
            signature = urllib.quote(base64.b64encode(hmac.new(self.secret_key, signature_string, hashlib.sha1).digest()))

            # final query string...
            url = self.protocol+"://"+self.host+self.uri+"?"+query_string+"&signature="+signature

            output = None
            try:
                output = json.loads(urllib2.urlopen(url).read())
            except urllib2.HTTPError, e:
                self.errors.append("HTTPError: "+str(e.code))
            except urllib2.URLError, e:
                self.errors.append("URLError: "+str(e.reason))
                
            if output:
                output = output[(params['command']).lower()+'response']
            
            if self.logging:
                with open('request.log', 'a') as f:
                    f.write('request:\n')
                    f.write(url)
                    f.write('\n\n')
                    f.write('response:\n')
                    if output:
                        pprint.pprint(output, f, 2)
                    else:
                        f.write(repr(self.errors))
                    f.write('\n\n\n\n')
            
            # if the request was an async call, then poll for the result...
            if output and 'jobid' in output.keys() and \
                    ('jobstatus' not in output.keys() or ('jobstatus' in output.keys() and output['jobstatus'] == 0)):
                print 'polling...'
                time.sleep(self.async_poll_interval)
                output = self.request(dict({'command':'queryAsyncJobResult', 'jobId':output['jobid']}))

            return output
        else:
            self.errors.append("missing api_key and secret_key in the constructor")
            return None
            
            
def get_dns():
    # comment out the following line to keep a history of the requests over multiple runs (request.log will get big).
    open('request.log', 'w').close() # cleans the 'request.log' before execution so it only includes this run.

    host = 'CLOUDTSACK_MANAGEMENT_SERVER_IP:PORT'
    api_key = 'PUT_YOUR_API_KEY_HERE'
    secret_key = 'PUT_YOUR_SECRET_KEY_HERE'

    cs_api = CloudstackAPI(protocol='https', host=host, api_key=api_key, secret_key=secret_key)
    output = ""
    default_net = "cloud"
    net_dict = {}
# Get list of networks, defined inside the Cloudstack 
    nets = cs_api.request(dict({'command':'listNetworks',
                                        'domainid':'366668fc-eb33-11e2-baef-005056a36bde',
                                        'isrecursive':'true'}))
# Build a small dict network_name:domain out of this information
    if 'network' in nets:
        for net in nets['network']:
            net_dict[net['name']]= net.get('networkdomain', default_net)[:-6]
    else:
        output += "\nNo Acounts on this CloudStack install...\n"
  

    vms = cs_api.request(dict({'command':'listVirtualMachines',
 					'domainid':'366668fc-eb33-11e2-baef-005056a36bde',
 					'isrecursive':'true'}))
    if 'virtualmachine' in vms:
        for vm in vms['virtualmachine']:
            output+= vm['name'] + "." + net_dict[vm['nic'][0]['networkname']] + "\t\t\t300\tIN\tA\t" + vm['nic'][0]['ipaddress'] +" \n"
    else:
        output += "\nNo VMs on this CloudStack install...\n"

    return output

def dnsprint(dns):
    soa = "$TTL 3600\t; 1 hour\n"
    soa += "$ORIGIN cloud.\n"
    soa += "@\t\t\tIN\tSOA\tns1.cloud. hostmaster.cloud. (\n"
    serial_d =  datetime.datetime.now().strftime('%y%j%H%M%S')
    serial = int(serial_d) - 14000000000
    soa += "\t\t\t\t\t" + str(serial) + "\t; serial\n"
    soa += "\t\t\t\t\t1800\t; refresh (30 minutes)\n"
    soa += "\t\t\t\t\t1800\t; retry (30 minutes)\n"
    soa += "\t\t\t\t\t864000\t; expire (1 week 3 days)\n"
    soa += "\t\t\t\t\t1800\t; minimum (30 minutes)\n\t\t\t\t\t)\n"
    soa += "\t\t\t\tNS\tns1.cloud.\n"
    soa += "\t\t\t\tNS\tns2.cloud.\n"
    soa += "ns1\t\t\tIN\tA\t10.150.100.15\n"
    soa += "ns2\t\t\tIN\tA\t10.150.100.15\n"
    soa += "@\t\t\tIN\tA\t10.150.100.15\n"
    zone_file = open ('/var/named/chroot/var/named/internal/cloud.zone', 'w')
    zone_file.write(soa+dns)
    zone_file.close()
    named_reload = commands.getoutput("rndc reload")
#    print (soa + dns)
#    print named_reload

if __name__ == "__main__":
    log_file = '/var/log/cloudstack/management/catalina.out'
    words = 'DhcpEntryCommand'
    fp = open(log_file, 'r')
    fp.seek(-3,2)
# Create DNS table on startup
    time.sleep(60)
    dns_table = get_dns()
    dnsprint(dns_table)
    while True:
          new = fp.readline()
          # Once all lines are read this just returns ''
          # until the file changes and a new line appears
          if new:
             if words in new:
                dns_table = get_dns()
                dnsprint(dns_table)

          else:
             time.sleep(0.5)
    print "Done!"

