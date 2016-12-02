#!/usr/bin/python3
# -*- coding: utf-8 -*-
import getopt, math, os, sys, time, datetime as dt
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as dates
import matplotlib.lines as lines
import paho.mqtt.client as mqtt


def usage():
    """
    Usage function
    """
    print("""Usage: %s -l -n [# of points] -t [topic]

Connect to NMR device via TCP and publisch received measurement results via MQTT.

-h                 Show this help message and exit
-l                 Enable logging to file .\\nmr.log
-n [# of points]   Width of time interval to show in plot in seconds, default "100"
-t [Topic]         Optional MQTT topic, default "COSY\\nmr"
""" % sys.argv[0])


def connect(ip, port):
# Generate unique client name and connect to mqtt broker
    pid = os.getpid()
    uid = "visa_"+str(pid)
    global client
    client = mqtt.Client(uid, False)
    client.connect(ip, port, 300)


def color(string):
    colors = {"L": 'g', "S": 'y', "N": 'r', "none": 'k'} # Green, yellow, red, black
    c = colors["none"]
    for key in colors.keys():
        if key == string:
            c = colors[string]
    return c


def createplot(npoints = 180, updinterv = 1.):
    global f, ax, x, y, c, coll
    plt.rcParams['font.size'] = 14
    plt.rcParams['savefig.format'] = 'pdf'
    plt.rcParams['mathtext.default'] = 'regular'
    plt.ion()
    f, ax  = plt.subplots(1, 1)
    f.suptitle("Main Field MDBE25 as Sampled by NMR Probe")
    start = time.time()
    timestamps = [start - updinterv * (npoints - i) for i in range(npoints)] # generate list of n timestamps backwards from start
    x = [dates.date2num(dt.datetime.fromtimestamp(t)) for t in timestamps] # reformat to python.datetime and from there to matplotlib.dates floats and use as x-data
    y = [0.] * npoints
    c = ['w'] * npoints
    coll = ax.scatter(x, y, s = 20, color = c, marker = 'o')
    f.autofmt_xdate()
    ax.xaxis.set_major_formatter(dates.DateFormatter('%H:%M:%S'))
    ax.set_xlabel("t / s")
    ax.set_ylabel("B / T")
    lock = lines.Line2D([], [], color='g', marker='o', markeredgecolor = 'g', markersize=10, linestyle = 'NONE', label='Locked')
    search = lines.Line2D([], [], color='y', marker='o', markeredgecolor = 'y', markersize=10, linestyle = 'NONE', label='Searching')
    nolock = lines.Line2D([], [], color='r', marker='o', markeredgecolor = 'r', markersize=10, linestyle = 'NONE', label='No Lock')
    ax.legend([lock, search, nolock], ["Locked", "Searching", "No Lock"], fancybox=True, framealpha=0.5) # manual legend
    plt.show()


def updateplot(time, lock, field):
    x.append(dates.date2num(dt.datetime.fromtimestamp(time))) # add timestamp from x data to x
    del x[0] # loose oldest x data
    y.append(field) # same for y data
    del y[0]
    c.append(color(lock)) #same for color data
    del c[0]
    coll = ax.scatter(x, y, s = 30, color = c, marker = 'o')
    lbl = "Locked"
    if c[-1] == 'g':
        lbl = dt.datetime.fromtimestamp(time).strftime("%H:%M:%S") + ": B = %.7f T" % field
    lock = lines.Line2D([], [], color='g', marker='o', markeredgecolor = 'g', markersize=10, linestyle = 'NONE', label = lbl)
    search = lines.Line2D([], [], color='y', marker='o', markeredgecolor = 'y', markersize=10, linestyle = 'NONE', label = 'Searching')
    nolock = lines.Line2D([], [], color='r', marker='o', markeredgecolor = 'r', markersize=10, linestyle = 'NONE', label = 'No Lock')
    ax.legend([lock, search, nolock], [lbl, "Searching", "No Lock"], fancybox=True, framealpha=0.5) # manual legend 
    ax.relim() # new axes limits from data    
    #ax.autoscale_view() #autoscale axes to new limits, breaks matplotlib.dates.Dateformatter???
    #plt.draw()
    plt.pause(0.001)


def on_connect(client, userdata, flags, rc):
    """
    Callback for when the client receives a CONNACK response from the server
    """
    print("Connected with result code "+str(rc))
    client.subscribe(topic)

        
def on_message(client, userdata, msg):
    """
    Callback for when a PUBLISH message is received from the server
    """
    t = msg.topic
    p = msg.payload.decode('utf-8').split(":")
    print(p)
    updateplot(float(p[0]), p[1], float(p[2]))
    if logfile:
        logfile.write(":".join(p))
        logfile.flush()


def main(argv):
    # Default parameters
    brokerIP = "jedibroker.ikp.kfa-juelich.de"
    brokerPort = 1883
    global logfile, npoints, topic
    logfile = ''
    npoints = 100
    topic = "COSY/nmr"
    # Read CMD-arguments given
    try:
        opts, args = getopt.getopt(argv, "hln:t:")
    except getopt.GetoptError as err:
        print(str(err)+"\n")
        usage()
        sys.exit(2)
    for opt, arg in opts:
        if opt == "-h":
            usage()
            sys.exit()
        elif opt == "-l":
            logfile = open("nmr.log", 'a')
        elif opt == "-n":
            npoints = int(arg)
        elif opt == "-t":
            topic = str(arg)
            
    connect(brokerIP, brokerPort)
    createplot(npoints) #create empty plot in right dimensions
    try:
        client.on_connect = on_connect
        client.on_message = on_message
        # blocking call that processes network traffic, dispatches callbacks and handles reconnecting.    
        client.loop_forever()
    except (KeyboardInterrupt):
        print("Disconnecting...")     
        client.disconnect()
        if logfile:
            logfile.close()

                    
if __name__ == "__main__":
    main(sys.argv[1:])
