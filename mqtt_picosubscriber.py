#!/usr/bin/python3
import getopt, os, sys, math, time, datetime as dt
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import paho.mqtt.client as mqtt


def usage():
    """
    Usage function
    """
    print("""Usage: %s -b <Broker IP-address:Port> -t <topic> -n <# of points>

-h    Show this help message and exit
-b    Specify different broker IP-address and port
-t    MQTT topic, default "COSY/RF-Devs/A, Peak To Peak"
-n    Number of Points to show in plot, default 101 points
""" % sys.argv[0])

    
def createplot(name, npoints, updinterv=1):
    """
    Create empty plot
    """
    global x, xerr, y, yerr, l, c, b
    start = time.time()
    timestamps = [start - updinterv * (npoints - i) for i in range(npoints)] # generate list of npoints timestamps backwards from start
    x = [mdates.date2num(dt.datetime.fromtimestamp(t)) for t in timestamps] # reformat to python.datetime and from there to matplotlib floats and use as x-data
    xerr = [0.] * npoints # assuming error free timestams
    y = [0.] * npoints
    yerr = [0.] * npoints
    
    plt.ion() # interactive plotting
    plt.xticks(rotation=25 )
    plt.xlabel("t / s")
    plt.subplots_adjust(bottom=0.15, left=0.15) 
    l, c, b = plt.errorbar(x, y, yerr = yerr, xerr = xerr, fmt='r+', label = name)
    plt.gca().legend()
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    plt.draw()
    return


def set_errdata(line, caplines, barlinecols, x, xerr, y, yerr):
    """
    Matplotlibs default set_data() routine only updates the plotlines with x- and y-data, not the errorbars, this does that
    """
    x = np.array(x)
    xerr = np.array(xerr)
    y = np.array(y)
    yerr = np.array(yerr)
    line.set_data(x, y)
    errpos = (x-xerr,y), (x+xerr,y), (x, y - yerr), (x, y + yerr)
    for i, pos in enumerate(errpos): # set caplines to ednpoints of errorbars
        caplines[i].set_data(pos)
    barlinecols[0].set_segments(zip(zip(x-xerr,y), zip(x+xerr,y))) # set xerror line between the endpoints
    barlinecols[1].set_segments(zip(zip(x,y-yerr), zip(x,y+yerr))) # set yerror line between the endpoints
    return

    
def updateplot(picodata):
    x.append(mdates.date2num(dt.datetime.fromtimestamp(float(picodata[1])))) # add timestamp from data to xdata
    del x[0] # loose oldest x-data
    y.append(float(picodata[2])) #same for y data
    del y[0]
    yerr.append(float(picodata[3])) #same for y errors
    del yerr[0]
    #plt.ion() #interactive plotting
    set_errdata(l, c, b, x, xerr ,y, yerr) # update data
    plt.gca().set_ylabel(picodata[0].split(", ")[1]) # get axis label from data
    plt.gca().relim() # autoscale axis if neccesary
    plt.gca().autoscale_view()
    #plt.draw() # update plot
    plt.pause(0.001)
    #plt.ioff()
    return


def connect(ip, port):
    """
    Generate unique client name and connect to mqtt broker
    """
    try:
        pid = os.getpid()
        uid = "mqtt_picosuscriber_"+str(pid)
        global client
        client = mqtt.Client(uid, False)
        client.connect(ip, port)
    except:
        print("Broker %s:%s not found" % (ip, port))
        sys.exit(2)

        
def on_connect(client, userdata, flags, rc):
    """
    Callback for when the client receives a CONNACK response from the server
    """
    print("Connected with result code "+str(rc))
    # subscribing in on_connect() means that if we lose the connection and reconnect then subscriptions will be renewed.
    client.subscribe(topic)
    createplot(topic, npoints) #create empty plot in right dimensions with MQTT topic as name

        
def on_message(client, userdata, msg):
    """
    Callback for when a PUBLISH message is received from the server
    """
    t = msg.topic
    p = msg.payload.decode('utf-8').split(":")
    print(p)
    updateplot(p)


def main(argv):
    global topic, npoints
    brokerIP = "jedibroker.ikp.kfa-juelich.de"#"134.94.220.203"
    brokerPort = 1883
    topic="COSY/RF-Devs/D, Peak To Peak"
    npoints = 101

    # read CMD-arguments given
    try:         
        opts, args = getopt.getopt(argv, "hb:t:n:")
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
        elif opt == "-n":
            npoints = int(arg)

    connect(brokerIP, brokerPort)
    try:
        client.on_connect = on_connect
        client.on_message = on_message
        # blocking call that processes network traffic, dispatches callbacks and handles reconnecting.    
        client.loop_forever()
    except (KeyboardInterrupt):
        print("Disconnecting...")        
        client.disconnect()

if __name__ == "__main__":
    main(sys.argv[1:])
