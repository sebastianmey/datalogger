#!/usr/bin/python3
# -*- coding: utf-8 -*-
import getopt, math, os, socket, sys, time, datetime as dt
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as dates
import matplotlib.lines as lines
from matplotlib.animation import FuncAnimation
import paho.mqtt.client as mqtt


def usage():
    """
    Usage function
    """
    print("""Usage: %s -i [IP:Port] -l -t [Topic] -w [Width]

Connect to NMR device via TCP and publisch received measurement results via MQTT.

-h             Show this help message and exit
-i [IP:Port]   IP4 address of device, default "134.94.216.123:10001"
-l             Enable logging to local file
-t [Topic]     Optional MQTT topic, default "COSY/nmr"
-w [Width]     Width of time interval to show in plot in seconds, default "200"
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

        
def tcp(ip, port):
    """
    Connect to TCP device
    """
    global s
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((ip, port))
        print("Connected to %s:%s" %(ip, str(port)))
    except socket.error as err:
        if s:
            s.close()
        print("Cound not connect to %s:%s via TCP: %s" %(ip, str(port), err))
        sys.exit(2)       


def stdoutcolor(line, keyw):
    """
    Color line for stdoutput according to keywords
    """
    colors = {"L": '\033[92m', "S": '\033[93m', "N": '\033[91m', "white": '\033[0m'} # Green, yellow, red, white
    locked = colors["white"]
    for lock in colors.keys():
        if keyw == lock:
            locked = colors[lock]
    return locked + line + colors["white"]


def color(string):
    colors = {"L": 'g', "S": 'y', "N": 'r', "none": 'k'} # Green, yellow, red, black
    c = colors["none"]
    for key in colors.keys():
        if key == string:
            c = colors[string]
    return c


def getdata(file):
    data = file.readline()
    if data:
        try:
            state = data[0]
            field = float(data.rstrip()[1:-1])
            return [time.time(), state, field]
        except ValueError as err:
            print(str(err))


def createplot(npoints = 120, updinterv = 1.):
    global f, ax, x, y, c, coll
    #plt.rcParams['text.usetex'] = True
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
    return coll,


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


def main(argv):
    # Default parameters
    devIP = "localhost" #134.94.216.123"
    devPort = 20001 #10001 for ssh protforwaRdig via "ssh -f -L 30001:134.94.216.123:10001 mey.o@plisch.cc.kfa-juelich.de -N"
    brokerIP = "jedibroker.ikp.kfa-juelich.de"
    brokerPort = 1883
    topic = "COSY/nmr"
    opath = "y:" + os.sep + "nmr" + os.sep #os.sep + "134.94.224.106"
    logfile = ""#open(opath + "nmr.log", 'a')#""
    width = 200
    # Read CMD-arguments given
    try:
        opts, args = getopt.getopt(argv, "hi:lt:w:")
    except getopt.GetoptError as err:
        print(str(err)+"\n")
        usage()
        sys.exit(2)
    for opt, arg in opts:
        if opt == "-h":
            usage()
            sys.exit()
        elif opt == "-i":
            devIP = arg.split(":")[0]
            devPort = int(arg.split(":")[1])
        elif opt == "-l":
            logfile = open(opath + "nmr.log", 'a')
        elif opt == "-t":
            topic = str(arg)
        elif opt == "-w":
            width = int(arg)
            
    tcp(devIP, devPort)   
    #connect(brokerIP, brokerPort)
    global datafile
    datafile = s.makefile()
    createplot(width, 1.)
    try:
        while True:
            data = getdata(datafile)
            if data:
                time = float(data[0])
                lock = str(data[1]) 
                field = float(data[2])
                print(stdoutcolor("%s:%s:%.7fT" % (dt.datetime.fromtimestamp(time).strftime("%Y-%m-%d_%H-%M-%S"), lock, field), lock))
                global lbl
                nmr = updateplot(time, lock, field)
                if logfile:
                    logfile.write(":".join(map(str, data))+"\n")
                    logfile.flush()
    # Quit publisher upon keyboard interrupt
    except (KeyboardInterrupt):
        print("Disconnecting...")
        #client.disconnect()
        s.close()
        sys.exit(0)
    """
    try:
        while True:#client.loop() == 0:
            #data = s.recv(4096)
            data = datafile.readline()
            try:
                state = data[0]
                field = float(data.rstrip()[1:-1])
            except ValueError as err:
                print(str(err))
                continue
            #client.publish(topic, "%f:%s:%f" % (time.time(), state, field), retain = True)
            # debug
            print(color("%d:%s:%.7f" % (time.time(), state, field), state))
            updateplot(state, time.time(), field)"""
                    
if __name__ == "__main__":
    main(sys.argv[1:])
