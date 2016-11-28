#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Created on Mon Aug 3 14:08:50 2015
@author:    Sebastian Mey, Institut für Kernphysik, Forschungszentrum Jülich GmbH
            s.mey@fz-juelich.de
"""


import getopt, math, os, sys, datetime, time
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
import paho.mqtt.client as mqtt


def usage():
    """
    Usage function
    """
    print("""Usage: %s -f [frev] - H [Harmonic] -l -t [Topic]

-h                   Show this help message and exit
-f [frev]            Revolution frequency in kHz, default is JEDI setting of "750.603"
-H [Harmonic]        Harmonic of the revolution frequency the NWA is set up for, as in df=(H+dq)*frev, default "1"
-l                   Enable logging to file .\\tunes.log
-t [Topic]           Optional MQTT topic, default "COSY\\tune"
""" % sys.argv[0])


def lorentz_offset(x, amp, xpeak, fwhm_half, offset):
    """
    Lorentzian with offset as fit function
    """
    return amp / (1 + ((x - xpeak) / fwhm_half)**2) + offset

        
def peakfit(xdata, ydata):
    """
    A simple peakfinder
    """
    ymax = max(ydata)
    ymin = min(ydata)
    imax = ydata.index(ymax)
    xmax = xdata[imax]
    startvalues = (math.fabs(ymax - ymin), xmax, 1., ymin)
    # see http://docs.scipy.org/doc/scipy-0.15.1/reference/generated/scipy.optimize.curve_fit.html#
    fitpar, fitcovar = curve_fit(lorentz_offset, xdata, ydata, startvalues)
    fitparerr = np.sqrt(np.diag(fitcovar))
    #chisq = 0.
    #for x, y in zip(xdata, ydata):
    #    chisq += (lorentz_offset(x, fitpar[0], fitpar[1], fitpar[2], fitpar[3]) - y)**2
    #redchisq = chisq / (len(xdata)-len(fitpar))
    #print("f(x) = A / (1+((x-xpeak)/fwhm)^2) + O \n A = %.3f +- %.3f; xpeak = %.3f +- %.3f; fwhm = %.3f +- %.3f; O = %.3f +- %.3f \n ChiSq/dof = %.3f" %(fitpar[0], fitparerr[0], fitpar[1], fitparerr[1], fitpar[2], fitparerr[2], fitpar[3], fitparerr[3], redchisq))
    return fitpar, fitparerr, fitcovar#, redchisq

    
def createplot(ntraces, npoints, fmin, fmax):
    """
    Create empty plot with all the traces used later on
    """
    global direction, f, axarr, x, y, l, lfit
    direction = ["synch. osz.", r"$q_x$", r"$q_y$"]
    color = ['g', 'r', 'b']
    f, axarr = plt.subplots(3, 1)#, sharex='col') # 2 plots in one
    plt.rcParams['font.size'] = 14
    plt.rcParams['savefig.format'] = 'pdf'
    plt.rcParams['mathtext.default'] = 'regular'
    plt.xlabel("f / kHz" )
    plt.ion() 
    f.suptitle("Beam Spectra")
    x = [[fmin + n * (fmax - fmin) / npoints for n in range(2*npoints)], [fmin + n * (fmax - fmin) / npoints for n in range(npoints)], [fmin + n * (fmax - fmin) / npoints for n in range(npoints)]] # Fill x-data
    y = [[[0] * 2*npoints], [[0] * npoints], [[0] * npoints]] # Fill y-data for plots with zeros
    l = [[0] * (ntraces + 1), [0] * (ntraces + 1), [0] * (ntraces + 1)]
    lfit = [[0], [0], [0]]
    for j, ax in enumerate(axarr):
        for i in range(ntraces):
            y[j].append([0] * len(x[j]))
            l[j][i], = ax.plot(x[j], y[j][i], c = str( 0.1 + 0.1 * float(i)), ls = '-') # Append empty history spectra
        l[j][ntraces], = ax.plot(x[j], [0] * len(x[j]), '%s-' %color[j], lw = 2, label = "current %s tune" % direction[j]) # Last trace for empty, current sprectrum
        lfit[j], = ax.plot(x[j], [0] * len(x[j]), 'k--', lw = 2, label = "Lorentzian") # Add empty fit function 
        ax.legend(fancybox=True, framealpha=0.5)
        ax.set_ylabel("Amplitude %s" % direction[j])
        ax.ticklabel_format(style='sci', axis='x', scilimits=(-3, 3))
        ax.ticklabel_format(style='sci', axis='y', scilimits=(-3, 3))
    plt.show()
    #plt.tight_layout()
    return


def updateplot(spectrumlist):
    """
    Fill plot with measured data and perform fit
    """
    peaks = [0., 0., 0.]
    peakerrs = [0., 0., 0.]
    fwhms = [0., 0., 0.]
    fwhmerrs = [0., 0., 0.]
    conv = 1
    for j, ax in enumerate(axarr):
        npoints = int(spectrumlist[j][1])
        fmin = float(spectrumlist[j][2])
        fmax = float(spectrumlist[j][3])
        data = [float(x) for x in spectrumlist[j][4:]]
        x[j] = [fmin + n * (fmax - fmin) / (npoints-1) for n in range(npoints)]
        ymax = max(data)
        imax = data.index(ymax)
        xmax = x[j][imax]
        ymin = min(data)
        imin = data.index(ymin)
        xmin = x[j][imin]
        # Peakfit
        try:
            pars, parerrs, covariance = peakfit(x[j], data)#, redchisq
            if pars[1] < x[j][0] or pars[1] > x[j][-1]:
                raise UserWarning
            if j == 0:
                peaks[0] = pars[1] / revh / 1000. # Revolution frequency / kHz
                peakerrs[0] = parerrs[1] / revh / 1000.
                fwhms[0] = pars[2] / revh / 1000. # Actually FWHM/2 / kHz
                fwhmerrs[0] = parerrs[2] / revh / 1000.
                result = (time.strftime("%Y-%m-%d %H:%M:%S") + r": %s spectrum" % direction[j], r"$f_{max} \pm FWHM/2 = (%.2f \pm %.2f) Hz \Rightarrow f_{rev} = (%.5f \pm %.5f) kHz$" % (pars[1], pars[2], peaks[0], fwhms[0]))
            else:
                peaks[j] = pars[1] / peaks[0] / 1000. - tuneh # Fractional betatron tune / kHz
                peakerrs[j] = math.sqrt((parerrs[1] /1000. / peaks[0])**2 +(pars[1] / 1000. / peaks[0]**2 * peakerrs[0])**2) # Tune error
                fwhms[j] = pars[2] / peaks[0] / 1000.
                fwhmerrs[j] = parerrs[2] / peaks[0] / 1000.
                result = (time.strftime("%Y-%m-%d %H:%M:%S") + r": %s spectrum" % direction[j], r"$f_{max} \pm FWHM/2 = (%.0f \pm %.0f) Hz \Rightarrow q = %.4f \pm %.4f$" % (pars[1], pars[2], peaks[j], fwhms[j]))
            print(time.strftime("%Y-%m-%d %H:%M:%S") + r": %s f_max = (%.2f +- %.2f) Hz, FWHM/2 = (%.2f +- %.2f) Hz" % (direction[j], pars[1], parerrs[1], pars[2], parerrs[2]))
            conv = 1
        # Catch faulty/ non-converged fits
        except (RuntimeError, UserWarning):
            print(time.strftime("%Y-%m-%d %H:%M:%S") + ": fit to %s did not converge, max. amp at %.3f kHz" % (direction[j], xmax/1000.))
            if j == 0:
                peaks[0] = xmax / revh / 1000.
                peakerrs[0] = 0.01
            result = (time.strftime("%Y-%m-%d %H:%M:%S") + r": %s spectrum" % direction[j], "Fit did not converge, max. amp. at $%.3f kHz$" % (xmax/1000.))
            conv = 0
        # Plot
        y[j].append(data) # Append latest measurement
        del y[j][0] # Delete oldest measurement
        for i, line in enumerate(l[j]): # Update plot data
            if len(y[j][i]) != len(x[j]):
                y[j][i] = [0] * len(x[j])
            line.set_data(x[j], y[j][i])
        if conv == 1:
            lfit[j].set_data(x[j], [lorentz_offset(xdata, pars[0], pars[1], pars[2], pars[3]) for xdata in x[j]])
        elif conv == 0:
            #lfit[j].set_data(x[j], [lorentz_offset(xdata, math.fabs(ymax-ymin), xmax, 5000., ymin) for xdata in x[j]])
            lfit[j].set_data(x[j], [0] * len(x[j]))
        ax.legend((l[j][-1], lfit[j]), result, fancybox=True, framealpha=0.5)
        ax.relim() # Autoscale axes
        ax.autoscale_view(tight = True)
    #plt.draw()
    #plt.pause(intervall - 1.)
    return peaks, fwhms


def connect(ip, port):
    """
    Generate unique client name and connect to mqtt broker
    """
    pid = os.getpid()
    uid = "mqtt_tunesuscriber_"+str(pid)
    global client
    client = mqtt.Client(uid, False)
    client.connect(ip, port)
    

def on_connect(client, userdata, flags, rc):
    """
    Callback for when the client receives a CONNACK response from the server
    """
    print("Connected with result code "+str(rc))
    # debug
    #print(topic)
    client.subscribe(topic)


def updatetime(t):
    """
    Dirty hack needed to keep window from freezing between updates
    """
    global lasttime
    lasttime = t

    
def on_message(client, userdata, msg):
    """
    callback for when a PUBLISH message is received from the server
    """
    t = msg.topic
    p = msg.payload.decode('utf-8')
    plist = p.split(":")
    frev = plist[1:int(plist[2])+5]
    del plist[:int(plist[2])+5]
    channel1 = plist[1:int(plist[2])+5]
    del plist[:int(plist[2])+5]
    channel2 = plist[1:]
    t = [float(frev[0]), float(channel1[0]), float(channel2[0])]
    strft = [datetime.datetime.fromtimestamp(time).strftime("%Y-%m-%d %H:%M:%S") for time in t]
    n = [int(frev[1]), int(channel1[1]), int(channel2[1])]
    fmin = [float(frev[2])/1000, float(channel1[2])/1000, float(channel2[2])/1000]
    fmax = [float(frev[3])/1000, float(channel1[3])/1000, float(channel2[3])/1000]
    print("%s: sync. osz. spectrum with %d entries received, fmin = %.0f Hz, fmax = %.0f Hz" % (strft[0], n[0], fmin[0], fmax[0]))    
    print("%s: x tunespectrum with %d entries received, fmin = %.0f Hz, fmax = %.0f Hz" % (strft[1], n[1], fmin[1], fmax[1]))
    print("%s: y tunespectrum with %d entries received, fmin = %.0f Hz, fmax = %.0f Hz" % (strft[2], n[2], fmin[2], fmax[2]))
    if logfile:
        logfile.write(p+"\n\n")
    updateplot([frev, channel1, channel2])
    # Apply hack
    if lasttime:
        print("waiting %f s" % (t[0] - lasttime))
        plt.pause(t[0] - lasttime)
    else:
        print("waiting %f s" % (time.time() - t[0]))
        plt.pause(time.time()-t[0])
    updatetime(t[0])


def main(argv):
    # Default parameters
    global topic, logfile, plot, frev, harm
    brokerIP = "jedibroker.ikp.kfa-juelich.de"
    brokerPort = 1883
    topic = "COSY/tune"
    logfile = ''
    global revh, tuneh, lasttime
    tuneh = 1.
    revh = 1.
    lasttime = ''
    history = 7
    
    # Read CMD-arguments given
    try:         
        opts, args = getopt.getopt(argv, "hf:H:lpt:")
    except getopt.GetoptError as err:
        print(str(err)+"\n")
        usage()
        sys.exit(2)
    for opt, arg in opts:
        if opt == "-h":
            usage()
            sys.exit()
        elif opt == "-f":
            frev = float(arg)
        elif opt == "-H":
            harm = float(arg)
        elif opt == "-l":
            logfile = open("tunes.log", 'a')
        elif opt == "-t":
            topic = str(arg)
                        
    th = input("Harmonic the Network Analyzer for tune measurements is set to, ENTER for H = 1 as in fq=(H+q)*frev: ")
    if th:
        tuneh = int(th)
    fh = input("Harmonic the Spectrum Analyzer for shottky measurements is set to, ENTER for F = 1 as in f= F*frev: ")
    if fh:
        revh = int(fh)
        
    connect(brokerIP, brokerPort)
    createplot(history, 401, 0.5*750.603, 0.7*750.603)
    try:
        client.on_connect = on_connect
        client.on_message = on_message
        # blocking call that processes network traffic, dispatches callbacks and handles reconnecting.
        client.loop_forever()
    except (KeyboardInterrupt):
        if logfile:
            logfile.close()
        print("Disconnecting...")        
        client.disconnect()

if __name__ == "__main__":
    main(sys.argv[1:])
