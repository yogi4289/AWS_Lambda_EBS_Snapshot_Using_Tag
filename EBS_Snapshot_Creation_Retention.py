import boto3
import json
import time
import sys
import string
import re
from datetime import datetime
import smtplib
import os
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText

ec2 = boto3.client('ec2')     
ec2Resource = boto3.resource('ec2')

retention_value = 40  # constant value for number of snapshots to retain of each block devices

#client = boto3.client('events')


data = {}
json.dumps(data)
ec2Resource = boto3.resource('ec2')  # object to access ec2 resources
vpc = ec2Resource.Vpc("vpc-xxxxxxx")   #created vpc connection using vpcID 


#bubble sorting alogrithm to sort indices on the basic of their start time    
def swap( snapshot, x, y ):
    tmp = snapshot[x]
    snapshot[x] = snapshot[y]
    snapshot[y] = tmp   

###HTML MAIL START############
header = '<!doctyle html><html><head><title>My Title</title></head><body>'
body = '<h3>Following are the list of snapshots created :-</h3><table style = "border-collapse: collapse;"><thead><tr><th style="text-align:left;border:1px solid black; padding: 10px">SnapshotName</th><th style="text-align:left;border:1px solid black; padding: 10px">DeviceName</th><th style="text-align:left;border:1px solid black; padding: 10px">IpAddress(ClusterName)</th></tr>'
footer = '</table></body></html>'
###HTML MAIL END################

#Lambda main function
def lambda_handler(event, context):
   
    html =  header + body
    fromaddr = "admin@abc.com"
    toaddr = "admin@abc.com"
    msg = MIMEMultipart()
    msg['From'] = fromaddr
    msg['To'] = toaddr
    msg['Subject'] = "Snapshot creation script has been completed"
    # SMTP Configuration Block End 
    
    try:
            total_snapshot = 0
            #Capture all the snapshots in allsnapshots dictionary#
            allSnapshots = ec2.describe_snapshots(
                        Filters=[
                        {
                            'Name': 'status',
                            'Values': [
                                'completed'
                            ],
                        }
                    ],
                    OwnerIds=[
                        '0000000800'
                    ]
                    )
        
            instance_count = 0
            total_instances = []  #dictionary initialisation to store all instances
            
            #check all the instances available in vpc having "daily" tag#
            for i in vpc.instances.all():
                if i.tags:
                    for tag in i.tags: 
            
                        if ((tag['Value'] == 'daily') and (tag['Key'] == 'snapshot_schedule')):
        
                            total_instances.append(i)
                            instance_count = instance_count + 1
        
            print (instance_count) # total number of instances having daily tag
            
            counter = 0
            
            #while loop to check for block devices attached to every instances#    
            while (counter < instance_count):
            
                total_blockDevice = []  # dictonary initialisation to store snapshot of each block devices
                response = ec2.describe_instance_attribute(
                    InstanceId= total_instances[counter].id,
                    Attribute='blockDeviceMapping'
                )
                                
                print total_instances[counter].id
                i = 0
                blockDevice_count = 0
                #check for total number of block devices attached to the instances
                for blockdevice in response['BlockDeviceMappings']:
                    
                    total_blockDevice.append(response['BlockDeviceMappings'][i]['Ebs']) 
                    blockDevice_count = blockDevice_count + 1
                    i = i + 1
            
                print blockDevice_count  # total number of block devices attached to the instance
                index  = 0   # initialisation to check each block device
                
                #check for total number of snapshots created from each blockdevices
                while (index < blockDevice_count):
                
                    volume_snapshot = []   # dictionary to store total number of snapshot of index blockdevice
                    print "check for blockdevices"
                    blockDeviceId = total_blockDevice[index]['VolumeId']
                    print blockDeviceId
                    #print total_blockDevice[index]
                    volume = ec2Resource.Volume(blockDeviceId)  #volume object to access volume attributes
                    count = 0 # initializing to count snapshots created from volume object
                    
                    # For loop to count total number of snapshots created from volume and add them to volume_snapshot dictionary
                    for snapshot in allSnapshots['Snapshots']:
                        
                        if (snapshot['VolumeId'] == blockDeviceId):
                            
                            volume_snapshot.append(snapshot)
                            count = count + 1
                    
                    print count   # total number of snapshot of blockdevice
                    print  type(volume_snapshot)
                    #Apply sort to sort snapshots on the basic of thier start time
                    volume_snapshot.sort(key=lambda x:x['StartTime'])
                    volume_snapshot.reverse()
                    print len(volume_snapshot)
                    
                    #creating new snapshot of block device                    
                    newsnapshot = volume.create_snapshot()  # Api to create new snapshsot of volume 
                    #volume_snapshot.append(newsnapshot) # Adding newly created snapshot to volume_snapshot dictionary
                    #print str(InstanceId)
                    DeviceName = total_instances[counter].block_device_mappings[index]["DeviceName"]
                    current_date = datetime.now().strftime("%Y%m%d%H%M")
                    snapshotName = "Snapshot("+total_instances[counter].id+")"+DeviceName+"-"+current_date
                    print (snapshotName)
                    #Find instance name start
                    for j in total_instances[counter].tags:
                        
                        if (j['Key'] == 'Name'):
                            
                            instance_name = j['Value']
                            break
                        else:
                            instance_name = "NOT AVAILABLE"
                            
                    #Find Instance Name End
                    # Email Body Start
                    
                    block_deviceDetails = str(blockDeviceId)+"("+str(DeviceName)+")"
                    Instance_details = str(total_instances[counter].private_ip_address)+"("+ instance_name +")"
                    html += '<tr><td style = "border:1px solid black">{}</td><td style = "border:1px solid black">{}</td><td style = "border:1px solid black">{}</td></tr>\n'.format(str(snapshotName),str(block_deviceDetails),str(Instance_details))
               
                  
                    #######create Name,BlockDevice,InstanceID tags of snapshot created#############
                    
                    newsnapshot.create_tags(
                           Tags=[
                          {
                               'Key': 'Name',
                               'Value': snapshotName
                          },
                            {
                               'Key': 'BlockDevice',
                               'Value': DeviceName
                          },
                            {
                               'Key': 'InstanceID',
                               'Value': total_instances[counter].id
                         }
                          ]
                           )
                    
                    #checking condition if total snapshot count with  Retention value
                    if len(volume_snapshot) > retention_value :
                        print ("deletion")
                        for snap in volume_snapshot[retention_value:] :
                            snapshot = ec2Resource.Snapshot(snap['SnapshotId'])
                            if "Created by CreateImage" not in snap['Description']:
                                snapshot.delete()
                                print (snapshot)
                            
                    index = index  + 1  # incrementing index value for next block device
                counter = counter + 1   # incrementing counter value for next instances
            entry = {"Total Instances with daily tag" : instance_count}
            data.update(entry)
                          
           
            html = html + footer
 
            print html
            ###Convert TEXT TO END###############
                                       
            # SMTP block start to send mail
            msg.attach(MIMEText(html, 'html'))
            server = smtplib.SMTP(host)
            server.starttls()
            #server.login(fromaddr)
            text = msg.as_string()
            print (text)
            server.sendmail(fromaddr, toaddr, text)
            server.quit()
            # SMTP block end to send mail
            print ("Successfully Completed All Snapshots")
            return data
            
    except Exception, e:
            msg['Subject'] = "Snapshot creation script has been Failed"
            
            # SMTP block start to send mail
            msg.attach(MIMEText(html, 'html'))
            server = smtplib.SMTP(host)
            server.starttls()
            #server.login(fromaddr)
            text = msg.as_string()
            print (text)
            server.sendmail(fromaddr, toaddr, text)
            server.quit()
            # SMTP block end to send mail
            print ("Snapshots have been failed")
            raise e
