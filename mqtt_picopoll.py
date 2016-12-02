#!/usr/bin/python3
import getopt, os, sys, subprocess, math, time, datetime as dt
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import paho.mqtt.client as mqtt

def usage():
    """
    Usage function
    """
    print("""Usage: %s -b <Broker IP-address:Port> -t <topic> -u <updateintervall> -l -p -n <# of points>

-h    Show this help message and exit
-b    Specify different broker IP-address and port
-t    MQTT topic, default "COSY/RF-Devs", measurements are subtopics
-u    How long to wait beween data updates, default 10 s
-p    Enable plotting on local machine
-l    Enable logging of measurements to file .\picopoll.log
-n    Number of Points to show in plot, default 101 points
""" % sys.argv[0])

def connect(ip, port):
    """
    Generate unique client name and connect to mqtt broker
    """
    try:
        pid = os.getpid()
        uid = "picopoll_"+str(pid)
        global client
        client = mqtt.Client(uid, False)
        client.connect(ip, port, 300)
    except:
        print("Broker %s:%s not found" % (ip, port))
        sys.exit(2)
                             
def picounit(string):
    """
    Picoscopes give out measurement results in human readable units, postprocessing requires transformation back to floats
    """
    units = {
    "GV": [1E12, "V"], "MV": [1E6, "V"], "kV": [1E3, "V"], "mV": [1E-3, "V"], "µV": [1E-6, "V"], "nV": [1E-9, "V"], "pV": [1E-12, "V"],
    "GA": [1E12, "V"], "MA": [1E6, "A"], "kA": [1E3, "A"], "mA": [1E-3, "A"], "µA": [1E-6, "A"], "nV": [1E-9, "A"], "pA": [1E-12, "A"],
    "GW": [1E12, "V"], "MW": [1E6, "W"], "kW": [1E3, "W"], "mW": [1E-3, "W"], "µV": [1E-6, "W"], "nV": [1E-9, "W"], "pW": [1E-12, "W"],
    "Gs": [1E12, "s"], "Ms": [1E6, "s"], "ks": [1E3, "s"], "ms": [1E-3, "s"], "µs": [1E-6, "s"], "ns": [1E-9, "s"], "ps": [1E-12, "s"],
    "G°": [1E12, "°"], "M°": [1E6, "°"], "k°": [1E3, "°"], "m°": [1E-3, "°"], "µ°": [1E-6, "°"], "n°": [1E-9, "°"], "p°": [1E-12, "°"],
    "GdB": [1E12, "dB"], "MdB": [1E6, "dB"], "kdB": [1E3, "dB"], "mdB": [1E-3, "dB"], "µdB": [1E-6, "dB"], "ndB": [1E-9, "dB"], "pdB": [1E-12, "dB"],
    "GHz": [1E12, "Hz"], "MHz": [1E6, "Hz"], "kHz": [1E3, "Hz"], "mHz": [1E-3, "Hz"], "µHz": [1E-6, "Hz"], "nHz": [1E-9, "Hz"], "pHz": [1E-12, "Hz"]}  
    for key in units.keys():
        if key == string:
            return units[key]
            break
    else:
        return [1, string]

def pico():
    """
    Read configured measurements from running picoscope and return a list of data points
    """
    try:
        csv = (str(subprocess.check_output("picoscope /a Measurements.CSV?"),"windows-1252").rstrip()).split("\r\n")[1:]
        timestamp = time.time()
    except:
        sys.exit(2)
    datapoint = []
    for line in csv:
        try:
            #print(line)
            channel = line.split(",")[0]
            quantity = line.split(",")[1]
            unit = picounit(line.split(",")[5].split()[1])
            average = float(line.split(",")[5].split()[0]) * unit[0]
            stddev = float(line.split(",")[6].split()[0]) * picounit(line.split(",")[6].split()[1])[0]
            datapoint.append([channel+", "+quantity+" / "+unit[1], timestamp, average, stddev])
        except IndexError:
            print("No measurements set up in picoscope?")
            sys.exit(1)
    return datapoint
  
def createplot(picodata, n, u):
    """
    Create empty plot with right dimensions for plottig the picoscope measurements
    """
    global x, xerr, y, yerr, f, axarr, l, c, b
    dim = len(picodata)
    start = picodata[0][1]
    timestamps = [start - u * (n - i) for i in range(n)] # generate list of npoints timestamps backwards from start
    x = [mdates.date2num(dt.datetime.fromtimestamp(t)) for t in timestamps] # reformat to python.datetime and from there to matplotlib floats and use as x-data
    xerr = [0.] * n # assuming error free timestams
    y = []
    yerr = []  
    l = [0] * dim
    c = [0] * dim
    b = [0] * dim
    plt.rcParams['font.size'] = 14
    plt.rcParams['savefig.format'] = 'pdf'
    plt.ion() # interactive plotting
    f, axarr = plt.subplots(dim, 1, sharex='col') # create a subplot for each measurement in data, all sharing the time axis
    if dim == 1: #catch error when axarr is not iterable
        axarr = [axarr]
    f.suptitle("Picoscope Measurements")
    plt.xticks(rotation=25 )
    plt.xlabel("t / s")
    plt.subplots_adjust(bottom=0.15, left=0.15) 
    picocolors = ['b', 'r', 'g', 'y', 'm', '0.75', 'c']
    for i, ax in enumerate(axarr):
        y.append([0.] * n)
        yerr.append([0.] * n)
        l[i], c[i], b[i] = ax.errorbar(x, y[i], yerr = yerr[i], xerr = xerr, marker='+',ls = 'None', color=picocolors[i], label = "%s" % picodata[i][0]) # draw each subplot
        ax.legend()
        ax.set_ylabel("%s" %picodata[i][0].split(", ")[1])
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    plt.draw()
    return
    
def set_errdata(line, caplines, barlinecols, x, xerr, y, yerr):
    """
    Matplotlibs default set_data() routine only updates the plotlines with x- and y-data, not the errorbars
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

def updateplot(picodata, updinterv):
    x.append(mdates.date2num(dt.datetime.fromtimestamp(picodata[0][1]))) # add timestamp from data to xdata
    del x[0] # loose oldest x-data
    for i, ax in enumerate(axarr):
        y[i].append(picodata[i][2]) #same for y data
        del y[i][0]
        yerr[i].append(picodata[i][3])
        del yerr[i][0]
        set_errdata(l[i], c[i], b[i], x, xerr ,y[i], yerr[i])
        ax.legend([l[i]], ["%s = %.3f $\pm$ %.3f" %((picodata[i][0]), y[i][-1], yerr[i][-1])])
        ax.relim()
        ax.autoscale_view()
        #print(i, mdates.num2date(x[0]), mdates.num2date(x[-1]), y[i][0], y[i][-1], yerr[i][-1])
    #plt.draw() # update plot
    plt.pause(updinterv)
    return
    
def main(argv):
    brokerIP = "jedibroker.ikp.kfa-juelich.de"#"134.94.220.203"
    brokerPort = 1883
    topic="COSY/RF-Devs"
    updinterv = 10
    plot = 0
    npoints = 21
    logfile = ''
    
    # read CMD-arguments given
    try:         
        opts, args = getopt.getopt(argv, "hb:t:u:lpn:")
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
        elif opt == "-u":
            updinterv = float(arg)
        elif opt == "-l":
            logfile = open("picopoll.log", 'a')
        elif opt == "-p":
            plot = 1
        elif opt == "-n":
            npoints = int(arg)
    
    connect(brokerIP, brokerPort)
    if plot == 1:
        createplot(pico(), npoints, updinterv)
    try:
        while client.loop() == 0:
            picodata = pico()
            for point in picodata:
                datastring = point[0]+":"+str(point[1])+":"+str(point[2])+":"+str(point[3])
                client.publish(topic+"/"+point[0].split(" / ")[0], datastring, retain = True)
                print(time.strftime("%Y-%m-%d %H:%M:%S")+": "+datastring+" sent")
                if logfile:
                    logfile.write(time.strftime("%Y-%m-%d %H:%M:%S")+": "+datastring+"/n/t")
            if (plot == 1 and len(picodata) == len(axarr)): #ommit empty points to cath dimension errors when plotting
                updateplot(picodata, updinterv)
            if plot == 0:
                time.sleep(updinterv)
                
    #quit publisher upon keyboard interrupt
    except (KeyboardInterrupt):
        if logfile:
            logfile.close()
        print("Disconnecting...")
        client.disconnect()
            
if __name__ == "__main__":
    main(sys.argv[1:])
