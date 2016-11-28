#!/usr/bin/python3
# -*- coding: utf-8 -*-
'''
Created on Fr Oct 16 17:12:50 2015

@author:    Sebastian Mey
            Institut für Kernphysik
            Forschungszentrum Jülich GmbH
            
            s.mey@fz-juelich.de
'''
import getopt, os, socket, sys, time
import paho.mqtt.client as mqtt


def usage():
    """
    Usage function
    """
    print("""Usage: %s -a [IP:Port] -t [Topic]

Connect to NMR device via TCP and publisch received measurement results via MQTT.

-h             Show this help message and exit
-a [IP:Port]   IP4 address of device, default "134.94.216.123:10001"
-t [Topic]     Optional MQTT topic, default "COSY/nmr"  
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
        print("Connected to Broker %s:%s" %(ip, str(port)))
    except:
        print("Broker %s not found" % ip)
        if client:
            client.disconnect()
        sys.exit(2)

        
def tcp(ip, port):
    """
    Connect to TCP device
    """
    global s
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((ip, port))
        print("Connected TCP Stream at %s:%s" %(ip, str(port)))
    except socket.error as err:
        if s:
            s.close()
        print("Cound not connect to %s:%s via TCP: %s" %(ip, str(port), err))
        sys.exit(2)


def color(line, keyw):
    """
    Color string for stdoutput according to list of keywords
    """
    color = {"L": r'\033[92m', "S": r'\033[93m', "N": r'\033[91m', "white": r'\033[0m'} # Green, yellow, red, white
    locked = color["white"]
    for lock in color.keys():
        if keyw == lock:
            locked = color[lock]
    return locked + line + color["white"]


def main(argv):
    # Default parameters
    devIP = "localhost" #"134.94.216.123"
    devPort = 20001 #20001 for ssh protforwaRdig via "ssh -f -L 20001:134.94.216.123:10001 mey.o@plisch.cc.kfa-juelich.de -N"
    brokerIP = "jedibroker.ikp.kfa-juelich.de"
    brokerPort = 1883
    topic="COSY/nmr"
    # Read CMD-arguments given
    try:
        opts, args = getopt.getopt(argv, "ha:t:")
    except getopt.GetoptError as err:
        print(str(err)+"\n")
        usage()
        sys.exit(2)
    for opt, arg in opts:
        if opt == "-h":
            usage()
            sys.exit()
        elif opt == "-a":
            devIP = arg.split(":")[0]
            devPort = int(arg.split(":")[1])
        elif opt == "-t":
            topic = str(arg)

    tcp(devIP, devPort)
    connect(brokerIP, brokerPort)
    try:
        while client.loop() == 0:
            #data = s.recv(4096)
            datafile = s.makefile()
            data = datafile.readline()
            try:
                state = data[0]
                field = float(data.rstrip()[1:-1])
            except ValueError as err:
                print(str(err))
                continue
            client.publish(topic, "%f:%s:%f" % (time.time(), state, field), retain = True)
            # debug
            print(color("%d:%s:%.7f" % (time.time(), state, field), state))
    # Quit publisher upon keyboard interrupt
    except (KeyboardInterrupt):
        print("Disconnecting...")
        client.disconnect()
        s.close()
                    
if __name__ == "__main__":
    main(sys.argv[1:])
