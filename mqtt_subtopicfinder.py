#!/usr/bin/python3
# -*- coding: utf-8 -*-

'''
Created on Mon Feb  2 21:14:05 2015
@author:    Sebastian Mey, Institut für Kernphysik, Forschungszentrum Jülich GmbH      
            s.mey@fz-juelich.de
'''

import getopt, os, sys, time, xdrlib, paho.mqtt.client as mqtt


def usage():
    """
    Usage function
    """
    print("""Usage: %s -b <Broker IP-address:Port> -t <topic> -s <subtopic>)

-h    Show this help message and exit
-b    Specify broker IP-address and port, default "jedibroker.ikp.kfa-juelich.de:1883"
-t    MQTT topic for which to write all subtopics to the command line, default "COSY"
-s    optional MQTT subtopic for which the payload is written in the command line
""" % sys.argv[0])


def decode(setup):
    """
    decodes and checks binary data as used by Peter Wüstner for the COSY setup files:
    the message format is (XDR, RFC 4506):
    int    size;       number of remaining words of the message
    int    version;    version of this protocol, currently 0
    string filename<>; canonical (absolute) path of the file
    int    sec;        time of last modification
    int    usec;
    string file<>;     this is the content of the actual file
    """
    try:
        u = xdrlib.Unpacker(setup)
        l_words = u.unpack_uint()
        mqttv = u.unpack_uint()
        l_fname = u.unpack_uint()
        fname = u.unpack_fstring(l_fname).decode('utf_8', 'ignore')
        time_s = u.unpack_uint()
        time_ms = u.unpack_uint()
        l_data = u.unpack_uint()
        data = u.unpack_fstring(l_data).decode('utf_8','ignore')
        u.done
        # debug
        #print(l_words, mqttv, l_fname, fname, time_s, time_ms, l_data, data)
        if l_fname != len(fname) or l_data != len(data):
            raise UserWarning
    except (xdrlib.ConversionError, UnicodeDecodeError, UserWarning):
        print(str(err)+"/n")
        sys.exit(2)
    return (time_s, time_ms, fname, data)
    
    
def connect(ip, port):
    """
    generate unique client name and connect to mqtt broker
    """
    try:
        pid = os.getpid()
        uid = "subtopicfinder_"+str(pid)
        global client
        client = mqtt.Client(uid, False)
        client.connect(ip, port)
    except:
        print("Broker %s:%s not found" % (ip, port))
        sys.exit(2)

        
def on_connect(client, userdata, rc):
    print("Connected with result code "+str(rc))
    client.subscribe(topic+"/#") # suscribe to all topics below specified


def on_message_topics(client, userdata, msg):
    print(msg.topic) #print all topics

    
def on_message_payload(client, userdata, msg):
    t = msg.topic
    p = msg.payload
    # debug
    #print(t, p)
    try:
        if t.startswith("COSY/SetupFiles/"):
            t_s, t_ms, fname, data = decode(p)
            print(fname)
            print("Submitted " + time.ctime(t_s))
            print(data)
        else:
            p = p.decode('utf_8','ignore')
            print(p)
    except (UnicodeDecodeError):
        print(str(err)+"/n")
        sys.exit(2)


def main(argv):
    global topic, subtopic
    brokerIP = "jedibroker.ikp.kfa-juelich.de"#"134.94.220.203"
    brokerPort = 1883
    topic = "COSY"
    subtopic = ""  

    # read CMD-arguments given
    try:         
        opts, args = getopt.getopt(argv, "hb:t:s:")
    except getopt.GetoptError as err:
        print(str(err)+"\n")
        usage()
        sys.exit(2)
    for opt, arg in opts:
        if opt == "-h":
            usage()
            sys.exit()
        elif opt == "-b":
            brokerIP= arg.split(":")[0]
            brokerPort = float(arg.split(":")[1])
        elif opt == "-t":
            topic = str(arg)
        elif opt == "-s":
            subtopic = str(arg)
            
    try:
        connect(brokerIP, brokerPort)
        client.on_connect = on_connect
        if subtopic:
            client.message_callback_add(subtopic, on_message_payload)
        else:
            client.on_message = on_message_topics
        client.loop_forever()
    except (KeyboardInterrupt):
        print("Disconnecting...")
        client.disconnect()

if __name__ == "__main__":
    main(sys.argv[1:])
