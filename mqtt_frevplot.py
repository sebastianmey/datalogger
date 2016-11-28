#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Created on Mi Okt 21 16:14:50 2015

@author:    Sebastian Mey
            Institut für Kernphysik
            Forschungszentrum Jülich GmbH
            
            s.mey@fz-juelich.de
"""
import getpass, getopt, os, sys, time
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
import paramiko
from scp import SCPClient
import paho.mqtt.client as mqtt


def usage():
    """
    Usage function
    """
    print("""Usage: %s -i [user@host:path] -t [Topic] -s [Sleeptime]

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
    Try to connect to server via ssh and open transport for file tranfer
    """
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    #ssh.load_host_keys(os.path.expanduser("~" + os.sep() + ".ssh" + os.sep() + "known_hosts"))
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
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
    spectra = []#,[]]
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
                #im = float(line.split(";")[2])
            except ValueError as err:
                #print(err)
                continue
            spectra.append(amp)
            #spectra[1].append(im)
    finally:
        f.close()
    spectra = [time.time(), n, fstart, fend] + spectra
    #spectra[1] = [time.time(), n, fstart, fend] + spectra[1]
    return spectra


def lorentz(x, amp, xpeak, fwhm):
    """
    Lorentzian as fit function
    """
    return amp / (1 + ((x - xpeak) / fwhm)**2)
    

def lorentz_offset(x, amp, xpeak, fwhm, offset):
    """
    lorentzian with offset as fit function
    """
    return amp / (1 + ((x - xpeak) / fwhm)**2) + offset

    
def peakfit(xdata, ydata):
    """
    A simple peakfinder
    """
    ymax = max(ydata)
    imax = ydata.index(ymax)
    xmax = xdata[imax]
    startvalues = (ymax, xmax, 10.)
    # see http://docs.scipy.org/doc/scipy-0.15.1/reference/generated/scipy.optimize.curve_fit.html
    fitpar, fitcovar = curve_fit(lorentz, xdata, ydata, startvalues)
    fitpar, fitcovar = curve_fit(lorentz_offset, xdata, ydata, (fitpar[0], fitpar[1], fitpar[2], -100.))
    fitparerr = np.sqrt(np.diag(fitcovar))
    return (fitpar, fitparerr, fitcovar)
     

def createplot(ntraces, npoints, fmin, fmax):
    """
    Create empty plot with all the traces used later on
    """
    global f, ax, x, y, l, lfit
    f, ax = plt.subplots(1, 1, sharex = 'col') # 2 plots sharing one x-axis
    #plt.rcParams['text.usetex'] = True
    plt.rcParams['font.size'] = 14
    plt.rcParams['savefig.format'] = 'pdf'
    plt.rcParams['mathtext.default'] = 'regular'
    plt.xlabel("f / Hz" )
    #plt.ion() 
    f.suptitle("Sychrotron Oscilaltion Spectra")
    x = [fmin + n * (fmax - fmin) / (npoints-1) for n in range(npoints)] # Fill x-data
    y = [[0] * npoints] # Fill y-data for both plots with zeors
    l = [0] * (ntraces + 1)
    lfit = [0]
    for i in range(ntraces):
        y.append([0] * npoints)
        l[i], = ax.plot(x, y[i], c = str( 0.1 + 0.2 * float(i)), ls = '-') # Empty history spectra
    l[ntraces], = ax.plot(x, [0] * npoints, 'g-', lw = 2, label = "Spectrum") # Last trace , empty current sprectrum
    lfit, = ax.plot(x, [0] * npoints, 'k--', lw = 2, label = "Lorentzian") # Empty fit function 
    ax.legend()
    ax.set_ylabel("Amp. / dBm")
    plt.draw()
    return


def updateplot(npoints, fmin, fmax, data):
    """
    Fill plot with measured data and perform fit
    """
    frev = 0.
    freverr = 0.
    fwhm = 0.
    fwhmerr = 0.
    conv = 1
    x = [fmin + n * (fmax - fmin) / npoints for n in range(npoints)]
    # Peakfit
    try:
        pars, parerrs, covariance = peakfit(x, data)
        if pars[1] < fmin or pars[1] > fmax:
            raise UserWarning
        frev = pars[1] / harm / 1000 # harmonic of revolution frequency / kHz
        freverr = parerrs[1] / harm / 1000 # Error of peak mean value of frev / kHz
        fwhm = pars[2] / harm / 1000 # actually FWHM/2 / kHz
        fwhmerr = parerrs[2] / harm / 1000
        print("frev = (%.3f +- %.3f) kHz, FWHM = (%.3f +- %.3f) kHz" % (frev, freverr, fwhm, fwhmerr))
        result = "Current Amp.: $f_{peak} \pm FWHM/2= (%.2f \pm %.2f)$ kHz" % (pars[1], pars[2])
        conv = 1
    except (RuntimeError, UserWarning): # Catch faulty/ non-converged fits
        ymax = max(data)
        imax = data.index(ymax)
        xmax = x[imax]
        print("Fit did not converge, max. amp at %.2f Hz" % xmax)
        result = "Fit did not converge, max. Amp. at $%.2f$ Hz" % xmax
        conv = 0

    y.append(data) # Append latest measurement
    del y[0] # Delete oldest measurement
    for i, line in enumerate(l):
        line.set_ydata(y[i]) # Update plot data
    if conv == 1:
        lfit.set_ydata([lorentz_offset(xdata, pars[0], pars[1], pars[2], pars[3]) for xdata in x]) 
    elif conv ==0:
        lfit.set_ydata([0] * len(x))
    ax.legend((l[-1], lfit), ("Current spectrum", result))
    ax.relim() # Autoscale axes
    ax.autoscale_view(tight = True)
    plt.draw()
    plt.pause(1)
    plt.savefig("frev.pdf", bbox_inches='tight')
    return (frev, fwhm)
    

def main(argv):
    # Default parameters
    sshIP = "snoopy.cc.kfa-juelich.de"
    sshUser = "cosy"
    sshPWD = ""
    ifile =  "/mnt/cc-x/smb/fsv/update"
    brokerIP = "jedibroker.ikp.kfa-juelich.de"
    brokerPort = 1883
    topic = "COSY/frev"
    global harm
    harm = 1.
    history = 1

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

    connect(brokerIP, brokerPort)
    ssh, scp = sshtransport(sshIP, sshUser, sshPWD)
    # test
    try:
        scp.get(ifile)
        ssh.close()
    except:
        print("Could not find %s." % ifile)
        ssh.close()
        sys.exit(2)
    syncspectrum = getspectrum(ifile.split("/")[-1])
    # debug
    #print(":".join(map(str, syncspectrum[0])))
    n = syncspectrum[1]
    fmin = syncspectrum[2]
    fmax = syncspectrum[3]
    data = syncspectrum[4:]
    createplot(history, n, fmin, fmax)
    updateplot(n, fmin, fmax, data)
    input("ENTER to continue")
    
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
