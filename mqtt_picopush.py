#!/usr/bin/python3
import getopt, os, sys, subprocess, time, paho.mqtt.publish as publish

def usage():
    """
    Usage function
    """
    print("""Usage: %s -b <Broker IP-address:Port> -t <topic> -l

-h    Show this help message and exit
-b    Specify different broker IP-address and port
-t    MQTT topic, default "COSY/RF-Devs", measurements are subtopics
-l    Enable logging to file .\picopush.log
""" % sys.argv[0])
                             
def picounit(string):
    """
    picoscopes give out measurement results in human readable units, postprocessing requires transformation back to floats
    """
    units = {
    "GV": [1E12, "V"], "MV": [1E6, "V"], "kV": [1E3, "V"], "mV": [1E-3, "V"], "µV": [1E-6, "V"], "nV": [1E-9, "V"], "pV": [1E-12, "V"],
    "GA": [1E12, "V"], "MA": [1E6, "A"], "kA": [1E3, "A"], "mA": [1E-3, "A"], "µV": [1E-6, "A"], "nV": [1E-9, "A"], "pA": [1E-12, "A"],
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
    read configured measurements from running picoscope and return a list of data points
    """
    try:
        csv = (str(subprocess.check_output("picoscope /a Measurements.CSV?"),"windows-1252").rstrip()).split("\r\n")[1:]
        timestamp = time.time()
    except:
        sys.exit(2)
    datastring = []
    for line in csv:
        channel = line.split(",")[0]
        quantity = line.split(",")[1]
        unit = picounit(line.split(",")[5].split()[1])
        average = float(line.split(",")[5].split()[0]) * unit[0]
        stddev = float(line.split(",")[6].split()[0]) * picounit(line.split(",")[6].split()[1])[0]
        datastring.append(channel+", "+quantity+" / "+unit[1]+":"+str(timestamp)+":"+str(average)+":"+str(stddev))
    return datastring
    
def main(argv):
    brokerIP = "jedibroker.ikp.kfa-juelich.de"#"134.94.220.203"
    brokerPort = 1883
    topic="COSY/RF-Devs"
    logfile = ''
    # read CMD-arguments given
    try:         
        opts, args = getopt.getopt(argv, "hb:t:l")
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
        elif opt == "-l":
            logfile = open("picopush.log", 'a')
        
    picodata = pico()
    uid = "picopush_"+str(os.getpid())
    payload = []
    for point in picodata:
        payload.append((topic+"/"+point.split(" / ")[0], point, 0, True))
    try:
        publish.multiple(payload, brokerIP, brokerPort, uid)
        if logfile:
            logfile.write(time.strftime("%Y-%m-%d %H:%M:%S")+":\n\t"+"\n\t".join(line for line in picodata)+"\nsent to broker "+brokerIP+":"+str(brokerPort)+"\n\n")
    except:     
        print("Broker %s:%s not found" % (brokerIP, brokerPort))
        if logfile:
            logfile.close() 
        sys.exit(2)
            
if __name__ == "__main__":
    main(sys.argv[1:])
