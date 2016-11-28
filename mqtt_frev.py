#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Created on Mi Okt 21 16:14:50 2015

@author:    Sebastian Mey
            Institut für Kernphysik
            Forschungszentrum Jülich GmbH
            
            s.mey@fz-juelich.de
"""
import getpass, getopt, os, sys, time
import paramiko
from scp import SCPClient
import paho.mqtt.client as mqtt


def usage():
    """
    Usage function
    """
    print("""Usage: %s -i [user@host:path] -t [Topic] -s [sleeptime]

Read in spectrum analyzer File (/mnt/cc-x/smb/fsv/update) and transmit measured spectra via MQTT in fixed time intervals.

-h                    Show this help message and exit
-i [user@host:path]   Input file, default "cosy@snoopy.cc.kfa-juelich.de:/mnt/cc-x/smb/fsv/update"
-s [sleeptime]        Poll interval in s, should match COSY cycle length, default "60"
-t [Topic]            Optional MQTT topic, default "COSY/frev"
""" % sys.argv[0])


def connect(ip, port):
    """
    Generate unique client name and connect to mqtt broker
    """
    try:
        pid = os.getpid()
        uid = "visa_"+str(pid)
        global client
        client = mqtt.Client(uid, False)
        client.connect(ip, port, 300)
    except:
        print("Broker %s not found" % ip)
        if client:
            client.disconnect()
        sys.exit(2)

        
def sshtransport(server, user, passwd):
    """
    Try to connect to server via ssh and open transport for file transfer
    """
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    ssh.load_host_keys(os.path.expanduser("~/.ssh/known_hosts"))
    #ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    if not passwd:
        passwd = getpass.getpass("%s@%s's password: " %(user, server))
    try:
        ssh.connect(hostname = server, username = user, password = passwd, look_for_keys=False, allow_agent = False)
        print("Connected to %s@%s via SSH." %(user, server))
    except (paramiko.AuthenticationException, paramiko.SSHException) as err:
        print("Could not connect to %s@%s: %s" %(user, server, err))
        sys.exit(2)
    scp = SCPClient(ssh.get_transport())
    return (ssh, scp)

                
def getspectrum(file):
    """
    format file content into spectrum list 
    """
    f = open(file, 'r')
    spectra = [[],[]]
    try:
        for line in f:
            entries = line.split(";")
            if entries[0] == "Start":
                fstart = float(entries[1])
            elif entries[0] == "Stop":
                fend = float(entries[1])
            elif entries[0] == "Values":
                n = int(entries[1])
            try:
                freq = float(line.split(";")[0])
                re = float(line.split(";")[1])
                im = float(line.split(";")[2])
            except ValueError:
                continue
            spectra[0].append(re)
            spectra[1].append(im)
    finally:
        f.close()
    spectra[0] = [time.time(), fstart, fend, n] + spectra[0]
    spectra[1] = [time.time(), fstart, fend, n] + spectra[1]
    return spectra
    

def main(argv):
    # Default parameters
    sshIP = "snoopy.cc.kfa-juelich.de"
    sshUser = "cosy"
    sshPWD = ""
    ifile =  "/mnt/cc-x/smb/fsv/update"
    brokerIP = "jedibroker.ikp.kfa-juelich.de"
    brokerPort = 1883
    topic="COSY/frev"
    wait = 10
    # Read CMD-arguments given
    try:
        opts, args = getopt.getopt(argv, "hi:s:t:")
    except getopt.GetoptError as err:
        print(str(err)+"\n")
        usage()
        sys.exit(2)
    for opt, arg in opts:
        if opt == "-h":
            usage()
            sys.exit()
        elif opt == "-i":
            address= arg.split(":")
            sshuser = adress[0].split("@")[0]
            sshIP = address[0].split("@")[1]
            ifile = address[1]
        elif opt == "-s":
            wait = int(arg)
        elif opt == "-t":
            topic = str(arg)

    #connect(brokerIP, brokerPort)
    ssh, scp = sshtransport(sshIP, sshUser, sshPWD)
    # test
    try:
        scp.get(ifile)
        ssh.close()
    except:
        print("Could not find %s." % ifile)
        ssh.close()
        sys.exit(2)
    syncspectrum = syncspectrum(ifile.split("/")[-1])
    # debug
    print(":".join(map(str, fspectrum[0])))
    
    try:
        while client.loop() == 0:
            try:
                scp.get(ifile)
                ssh.close()
            except:
                print("Could not find %s." % ifile)
                ssh.close()
                sys.exit(2)
            syncspectrum = getspectrum(ifile.split("/")[-1])
            syncspectrum = ":".join(map(str, syncspectrum[0]))
            # debug
            #print(syncspectrum)
            client.publish(topic, syncspectrum, retain=True)
            print(time.strftime("%Y-%m-%d %H:%M:%S")+": "+"Longitudnal beam spectrum sent")
            time.sleep(wait) 
    # Quit publisher upon keyboard interrupt
    except (KeyboardInterrupt):
        print("Disconnecting...")
        client.disconnect()

                    
if __name__ == "__main__":
    main(sys.argv[1:])
