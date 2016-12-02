#!/usr/bin/python3
# -*- coding: utf-8 -*-
import array, getopt, os, sys, time, xdrlib, paho.mqtt.client as mqtt


def usage():
# Usage function
    print("""%s -b [BrokerIP:Port]

Connects to the COSY MQTT broker and receives the Timing Table from the setup files.

-h                     Show this help message and exit
-b [IP-address:Port]   Specify broker IP-address and port, default "jedibroker.ikp.kfa-juelich.de"
""" % sys.argv[0])


def decode(setup):
# decodes and checks binary data as used by Peter Wüstner for the COSY setup files:
# the message format is (XDR, RFC 4506):
# int    size;       number of remaining words of the message
# int    version;    version of this protocol, currently 0
# string filename<>; canonical (absolute) path of the file
# int    sec;        time of last modification
# int    usec;
# string file<>;     this is the content of the actual file
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
# generate unique client name and connect to mqtt broker
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

        
def on_message_payload(client, userdata, msg):
    t = msg.topic
    p = msg.payload
    # debug
    #print(t, p)
    t_s, t_ms, fname, data = decode(p)
    print(fname)
    print("Submitted " + time.ctime(t_s))
    experiments = [block.split("`")[:-1] for block in data.split("/")]
    for i, experiment in enumerate(experiments):
        print("Experiment %s:" % i)
        #events = [line.split(",") for line in experiment]
        #print(events)
        for event in experiment:
            n = int(event.split(",")[0])
            t = int(event.split(",")[1])
            t1 = int(hex(int(event.split(",")[2], 16))[3:], 16)
            t1 = -1 if t1 == 4095 else t1
            t2 =  int(hex(int(event.split(",")[3], 16))[3:], 16)
            t2 = -1 if t2 == 4095 else t2
            state = int(hex(int(event.split(",")[4], 16))[3:], 16)
            state = -1 if state == 4095 else state
            if int(event.split(",")[5]) == 1:
                active = True
            else:
                active = False
            name = event.split(",")[6]
            event = [n, name, t, t1, t2, state, active]
            print(event)


def main(argv):
    global topic, subtopic
    brokerIP = "jedibroker.ikp.kfa-juelich.de"#"134.94.220.203"
    brokerPort = 1883
    topic = "COSY/SetupFiles/TimingSender/Triggertabelle"

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

    try:
        connect(brokerIP, brokerPort)
        client.on_connect = on_connect
        client.message_callback_add(topic, on_message_payload)
        client.loop_forever()
    except (KeyboardInterrupt):
        print("Disconnecting...")
        client.disconnect()

if __name__ == "__main__":
    main(sys.argv[1:])
