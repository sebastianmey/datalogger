#!/usr/bin/python
# -*- coding: utf-8 -*-
import getopt, os, sys, time
import visa
import paho.mqtt.client as mqtt


def usage():
    """
    Usage function
    """
    print("""Usage: %s -g [GPIB] -i [user@host:file] -s [Sleeptime] -t [Topic]

Connect to network analyzer via NI-libraries and transmit measured spectra via MQTT in fixed time intervals.

-h                    Show this help message and exit
-g [GPIB]             GPIB address, default "TCPIP0::ikp060.ikp.kfa-juelich.de::gpib0,7::INSTR"
-i [user@host:file]   Input file of sync. osz. spectrum accessable via ssh, e.g. "cosy@snoopy.cc.kfa-juelich.de:/mnt/cc-x/smb/fsv/update", dafault is now input via samba network disk "//134.94.224.106/fsv/update"
-s [Sleeptime]        Poll interval in s, default "30"
-t [Topic]            Optional MQTT topic, default "COSY/tune"
""" % sys.argv[0])


def connect(ip, port):
    """
    Generate unique client name and connect to mqtt broker
    """
    pid = os.getpid()
    uid = "mqtt_tune_"+str(pid)
    client = mqtt.Client(uid, False)
    client.connect(ip, port, 300)
    return client

        
def gpib(addr):
    """
    Try to connect to gpib networkanalyzer
    """
    try:
        rm = visa.ResourceManager()
        lib = rm.visalib
        # debug
        #print("Device list: ", rm.list_resources())
    except:
        print("NI-VISA Library not found")
        sys.exit(2)
    try:
        instr = rm.get_instrument(addr)
        print("Connected to "+instr.ask('*IDN?')) # SCPI poll for self idenfication
    except:
        print("No device at "+addr)
        sys.exit(2)
    return lib, instr
    
    
def gettune(instr):
    """
    Poll network analyzer for data, add timestamp and give out spectrum as histograms
    """
    flist = instr.ask('OUTPSWPRM?')[:-1].split(",") # SCPI poll for sweep parameters
    amplist = instr.ask('OUTPDTRC?')[:-1].split(",") # SCPI poll for data trace
    spectrum = [time.time(), len(flist), float(flist[0]), float(flist[-1])]
    for amp in amplist[::2]: # every 2nd entry, cuts imaginary part (which is not set up anyway)
       spectrum.append(float(amp))
    return spectrum


def sshtransport(server, user, passwd):
    """
    Try to connect to server via ssh and open transport for file transfer
    """
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    #ssh.load_host_keys(os.path.expanduser("~" + os.sep() + ".ssh" + os.sep() + "known_hosts"))
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    if not passwd:
        passwd = getpass.getpass("%s@%s's password: " %(user, server))
    try:
        ssh.connect(hostname = server, username = user, password = passwd, look_for_keys=False, allow_agent = False)
        print("Connected to %s@%s via SSH" %(user, server))
    except (paramiko.AuthenticationException, paramiko.SSHException) as err:
        print("Could not connect to %s@%s: %s" %(user, server, err))
        sys.exit(2)
    scp = SCPClient(ssh.get_transport())
    return ssh, scp
    
    
def getfrev(file):
    """
    Read spectrum from file, add timestamp and return as histogram
    """
    f = open(file, 'r')
    spectrum = []
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
                amp = float(line.split(";")[1])
            except ValueError as err:
                #print(err)
                continue
            spectrum.append(amp)
    finally:
        f.close()
    spectrum = [time.time(), n, fstart, fend] + spectrum
    return spectrum

    
def main(argv):
    # Default parameters
    sshIP = "snoopy.cc.kfa-juelich.de"
    sshUser = "cosy"
    sshPWD = ""
    ifile = "/mnt/cc-x/smb/fsv/update" #"z:" + os.sep + "update" 
    gpibAddress = 'TCPIP0::ikp060.ikp.kfa-juelich.de::gpib0,7::INSTR'
    brokerIP = "jedibroker.ikp.kfa-juelich.de"
    brokerPort = 1883
    topic="COSY/tune"   
    wait = 30
    spectra = [0, 0, 0]
    # Read CMD-arguments given
    try:
        opts, args = getopt.getopt(argv, "hg:i:s:t:")
    except getopt.GetoptError as err:
        print(str(err)+"\n")
        usage()
        sys.exit(2)
    for opt, arg in opts:
        if opt == "-h":
            usage()
            sys.exit()
        elif opt == "-g":
            gpibAddress = arg
        elif opt == "-i":
            address= arg.split(":")
            sshuser = adress[0].split("@")[0]
            sshIP = address[0].split("@")[1]
            ifile = address[1]
        elif opt == "-s":
            wait = int(arg)
        elif opt == "-t":
            topic = str(arg)
                
    client = connect(brokerIP, brokerPort)
    lib, nwa = gpib(gpibAddress)
    if sshIP and sshuser:
        ssh, scp = sshtransport(sshIP, sshUser, sshPWD)
        try:
            scp.get(ifile)
        except:
            print("Could not find %s." % ifile)
            ssh.close()
            sys.exit(2)

    try:
        while client.loop() == 0:
            try:
                spectra[0] = getfrev(ifile)#ifile.split("/")[-1])#ifile
                # debug
                #print(spectra[0])
            except FileNotFoundError as err:
                print(err)
                continue
            nwa.write('CHAN1') # Switch network analyzer to channel 1
            spectra[1] = gettune(nwa)
            # debug
            #print(spectra[1])
            nwa.write('CHAN2') # Switch network analyzer to channel 1
            spectra[2] = gettune(nwa)
            # debug
            #print(spectra[2])
            lib.gpib_control_ren(nwa.session, 6) # Raw command to switch network analyzer back to local

            client.publish(topic, "frev:"+":".join(map(str,spectra[0]))+":channel1:"+":".join(map(str,spectra[1]))+":channel2:"+":".join(map(str,spectra[2])), retain = True)
            print(time.strftime("%Y-%m-%d %H:%M:%S")+": "+"Beam spectra sent")
            # debug
            #print("frev:"+":".join(map(str,spectra[0]))+"\nchannel1:"+":".join(map(str,spectra[1]))+"\nchannel2:"+":".join(map(str,spectra[2])))
            time.sleep(wait) 
    # Quit publisher upon keyboard interrupt
    except (KeyboardInterrupt):
        print("Disconnecting...")
        client.disconnect()
        if sshIP and sshuser:
            ssh.close()
            
if __name__ == "__main__":
    main(sys.argv[1:])
