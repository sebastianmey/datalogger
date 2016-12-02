#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Changelog:  2015-06-06: improved exception handling in case of non-converging fits.
            2015-06-12: reworked fit routine to use the transmitted historgrams' maximum as start value
            2015-06-13: replaced error output in the plot by FWHM
            2015-09-16: more command line parameters for tune calculation (harmonics)
            2015-10-30: added possibility to read out additional spectrum via ssh from the scope program on paxls1.kfa-juelich.de.cc (via snoopy in the same cc subnet)
            2015-11-06: Defined connected network shares on 134.94.224.106 as default save options
"""
import getpass, getopt, math, os, sys, time
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
import visa
import paramiko
from scp import SCPClient


def usage():
    """
    Usage function
    """
    print("""Usage: %s -g [GPIB] -i [user@host:file] -l  -o [oPath] -s [Sleeptime]-F [frev harmonic] -H [Tune harmonic]

-h    Show this help message and exit
-g [GPIB]              GPIB address of NWA with tune spectra, default "TCPIP0::ikp060.ikp.kfa-juelich.de::gpib0,7::INSTR"
-i [user@host:file]    Input file of sync. osz. spectrum accessable via ssh, e.g. "cosy@snoopy.cc.kfa-juelich.de:/mnt/cc-x/smb/fsv/update", dafault is input via smb from "//134.94.224.106/fsv/update"
-l                     Enable logging of spectra to file and saving of screenshots
-o [oPath]             Optional logfile path, default is "//134.94.224.106/spectra/"
-s [Sleeptime]         Poll interval in s, should match COSY cycle length, default "30."
-F [frev Harmonic]     Harmonic F of the revolution frequency the Spectrum Analyzer set up for, as in df= F*frev, default "1"
-H [Tune harmonic]     Harmonic H of the revolution frequency the NWA is set up for, as in f=(H+q)*frev, default "1"
""" % sys.argv[0])


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
        print("Connected to " + instr.ask('*IDN?')) # SCPI poll for self idenfication
    except:
        print("No device at "+addr)
        sys.exit(2)
    return lib, instr

    
def gettune(instr):
    """
    Poll network analyzer for data, add timestamp and give out spectrum as histogram#
    """
    flist = instr.ask('OUTPSWPRM?')[:-1].split(",") # SCPI poll for sweep parameters
    amplist = instr.ask('OUTPDTRC?')[:-1].split(",") # SCPI poll for data trace
    spectrum = [time.time(), len(flist), float(flist[0]), float(flist[-1])]
    for amp in amplist[::2]: # every 2nd entry, cuts imaginary part
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
    return (ssh, scp)


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
    
        
def gauss(x, amp, xpeak, sigma):
    """
    Gaussian as fit function
    """
    return amp*np.exp(-(x-xpeak)**2/(2.*sigma**2))



def lorentz(x, amp, xpeak, fwhm):
    """
    Lorentzian as fit function
    """
    return amp / (1 + ((x - xpeak) / fwhm)**2)
    

def lorentz_offset(x, amp, xpeak, fwhm, offset):
    """
    Lorantzian with offset as Fit function
    """
    return amp / (1 + ((x - xpeak) / fwhm)**2) + offset
    
    
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
    #fitpar, fitcovar = curve_fit(lorentz, xdata, ydata, startvalues)
    #fitpar, fitcovar = curve_fit(lorentz_offset, xdata, ydata, (fitpar[0], fitpar[1], fitpar[2], ymin))
    fitparerr = np.sqrt(np.diag(fitcovar))
    #chisq = 0.
    #for x, y in zip(xdata, ydata):
    #    chisq += (lorentz_offset(x, fitpar[0], fitpar[1], fitpar[2], fitpar[3]) - y)**2
    #redchisq = chisq / (len(xdata)-len(fitpar))
    #print("f(x) = A / (1+((x-xpeak)/fwhm)^2) + O \n A = %.3f +- %.3f; xpeak = %.3f +- %.3f; fwhm = %.3f +- %.3f; O = %.3f +- %.3f \n ChiSq/dof = %.3f" %(fitpar[0], fitparerr[0], fitpar[1], fitparerr[1], fitpar[2], fitparerr[2], fitpar[3], fitparerr[3], redchisq))
    return fitpar, fitparerr, fitcovar#, redchisq


def createplot(ntraces, npoints, f0, fmax):
    """
    Create empty plot with all the traces used later on#
    """
    global direction, f, axarr, x, y, l, lfit
    direction = ["synch. osz.", r"$q_x$", r"$q_y$"]
    color = ['g', 'r', 'b']
    f, axarr = plt.subplots(3, 1)
    #plt.rcParams['text.usetex'] = True
    plt.rcParams['font.size'] = 14
    plt.rcParams['savefig.format'] = 'pdf'
    plt.rcParams['mathtext.default'] = 'regular'
    plt.xlabel("f / Hz" )
    plt.ion()
    f.suptitle("Beam Spectra")
    x = [[f0 + n * (fmax - f0) / npoints for n in range(2*npoints)], [f0 + n * (fmax - f0) / npoints for n in range(npoints)], [f0 + n * (fmax - f0) / npoints for n in range(npoints)]] # Fill x-data
    y = [[[0] * 2*npoints], [[0] * npoints], [[0] * npoints]] # Fill y-data for both plots with zeros
    l = [[0] * (ntraces + 1), [0] * (ntraces + 1), [0] * (ntraces + 1)]
    lfit = [[0], [0], [0]]
    for j, ax in enumerate(axarr):
        for i in range(ntraces):
            y[j].append([0] * len(x[j]))#npoints)
            l[j][i], = ax.plot(x[j], y[j][i], c = str( 0.1 + 0.1 * float(i)), ls = '-') # Empty history spectra
        l[j][ntraces], = ax.plot(x[j], [0] * len(x[j]), '%s-' %color[j], lw = 2, label = "current %s tune" % direction[j]) # Empty current sprectrum
        lfit[j], = ax.plot(x[j], [0] * len(x[j]), 'k--', lw = 2, label = "Lorentzian") # Empty fit function
        ax.legend(fancybox=True, framealpha=0.5)
        ax.set_ylabel("Amp. %s" % direction[j])
        ax.ticklabel_format(style='sci', axis='x', scilimits=(-3, 3))
        ax.ticklabel_format(style='sci', axis='y', scilimits=(-3, 3))
    plt.show()
    #plt.tight_layout()
    return
    

def updateplot(spectrumlist, intervall):
    """
    Fill plot with measured data and perform fit
    """
    peaks = [0., 0., 0.]
    peakerrs = [0., 0., 0.]
    fwhms = [0., 0., 0.]
    fwhmerrs = [0., 0., 0.]
    conv = 1
    for j, ax in enumerate(axarr):
        npoints = spectrumlist[j][1]
        fmin = spectrumlist[j][2]
        fmax = spectrumlist[j][3]
        data = spectrumlist[j][4:]
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
        ax.legend((l[j][-1], lfit[j]), result, fancybox=True, framealpha=0.5, fontsize='10')
        ax.relim() # Autoscale axes
        ax.autoscale_view(tight = True)
    plt.draw()
    plt.pause(intervall - 1.)
    return peaks, fwhms
    

def main(argv):
    # Default parameters
    sshIP = "" #"snoopy.cc.kfa-juelich.de"
    sshUser = "" #"cosy"
    sshPWD = ""
    ifile = "z:" + os.sep + "update" #"/mnt/cc-x/smb/fsv/update"
    opath = "y:" + os.sep + "spectra" + os.sep
    gpibAddress = 'TCPIP0::ikp060.ikp.kfa-juelich.de::gpib0,7::INSTR'
    global revh, tuneh, intervall
    tuneh = 1
    revh = 1
    wait = 10.
    history = 7
    spectra = [0, 0, 0]
    l = 1
    # Read CMD-arguments given
    try:
        opts, args = getopt.getopt(argv, "hg:i:ls:F:H:")
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
        elif opt == "-l":
            l = 1
        elif opt == "-o":
            ofile = arg
        elif opt == "-s":
            wait = float(arg)
        elif opt == "-H":
            tuneh = float(arg)          
        elif opt == "-F":
            revh = float(arg)
    
    # read in startparameters from stdin
    th = input("Harmonic the Network Analyzer for tune measurements is set to, ENTER for H = 1 as in f=(H+q)*frev: ")
    if th:
        tuneh = int(th)
    fh = input("Harmonic the Spectrum Analyzer for shottky measurements is set to, ENTER for F = 1 as in df= F*frev: ")
    if fh:
        revh = int(fh)
    i = input("Poll intervall for spectrum readouts, ENTER for i = 30.: ")
    if i:
        wait = float(i)        
    
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
        spectra[0] = getfrev(ifile.split("/")[-1])
    except FileNotFoundError as err:
        print(err)
        print(r"\\134.94.224.106\fsv mounted as network drive Z:\?")
        sys.exit(2)
    # debug
    #print(":".join(map(str, spectrum[0])))
    n = [spectra[0][1], 0., 0.]
    fmin = [spectra[0][2], 0., 0.]
    fmax = [spectra[0][3], 0., 0.]
    data = [spectra[0][4:], 0., 0.]
    createplot(history, n[0], fmin[0], fmax[0])
    try:
        while True:
            try:
                spectra[0] = getfrev(ifile.split("/")[-1])
            except FileNotFoundError as err:
                print(err)
                continue
            nwa.write('CHAN1')
            spectra[1] = gettune(nwa)
            # debug
            #print(spectra[1])
            nwa.write('CHAN2')
            spectra[2] = gettune(nwa)
            # debug
            #print(spectra[2])
            lib.gpib_control_ren(nwa.session, 6)
            spectra[0] = getfrev(ifile.split("/")[-1])
            nwa.write('CHAN1')
            spectra[1] = gettune(nwa)
            # debug
            #print(spectra[1])
            nwa.write('CHAN2')
            spectra[2] = gettune(nwa)
            # debug
            #print(spectra[2])
            lib.gpib_control_ren(nwa.session, 6) # Raw command to switch back to local                  
            tune, width = updateplot(spectra, wait)
            #print(time.strftime("%Y-%m-%d %H:%M:%S") + r"frev ")
            if l:
                t = time.strftime("%Y-%m-%d_%H-%M-%S")
                try:
                    plt.savefig(opath + t + "_tunespectra.pdf", dpi = 300, orientation = 'landscape', papertype = 'a4', transparent = True)
                    logfile = open(opath + t + "_tunespectra.log", 'w')
                    logfile.write("sync. osz. spectrum: \n" + ":".join(map(str, spectra[0])) + "\n beta_x spectrum: \n" + ":".join(map(str, spectra[1])) + "\n beta_Y spectrum: \n" + ":".join(map(str, spectra[2])))
                    logfile.close()
                except FileNotFoundError as err:
                    print(err)
                    print("\\134.94.224.106\beamdynamics mounted as network drive Y:\ ?")
                    continue                   
            time.sleep(wait)
    # Quit upon keyboard interrupt
    except (KeyboardInterrupt):
        print("Disconnecting...")
        if sshIP and sshuser:
            ssh.close()
                    
if __name__ == "__main__":
    main(sys.argv[1:])
