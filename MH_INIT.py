import ctypes as ct
from ctypes import byref
import numpy as np
import os
import sys
import matplotlib
matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
import time


if sys.version_info[0] < 3:
    print("[Warning] Python 2 is not fully supported. It might work, but "
          "use Python 3 if you encounter errors.\n")
    raw_input("press RETURN to continue"); print

# From mhdefin.h
LIB_VERSION = "3.1"
MAXDEVNUM = 8
MODE_T2 = 2
MODE_T3 = 3
MAXLENCODE = 6
MAXINPCHAN = 64
TTREADMAX = 1048576
FLAG_OVERFLOW = 0x0001
FLAG_FIFOFULL = 0x0002

# Measurement parameters, these are hardcoded since this is just a demo
mode = MODE_T2 # set T2 or T3 here, observe suitable Syncdivider and Range!
binning = 4 # you can change this, meaningful only in T3 mode
offset = 0 # you can change this, meaningful only in T3 mode
tacq = 40000 # Measurement time in millisec, you can change this
syncDivider = 1 # you can change this, observe mode! READ MANUAL!

syncTriggerEdge = 0 # you can change this, can be set to 0 or 1 
syncTriggerLevel = -50 # you can change this (in mV) 
syncChannelOffset = 0 # you can change this (in ps, like a cable delay)
inputTriggerEdge = 0 # you can change this, can be set to 0 or 1  
inputTriggerLevel = -50 # you can change this (in mV)
inputChannelOffset = 5000 # you can change this (in ps, like a cable delay)

# Variables to store information read from DLLs
buffer = (ct.c_uint * TTREADMAX)()
dev = []
libVersion = ct.create_string_buffer(b"", 8)
hwSerial = ct.create_string_buffer(b"", 8)
hwPartno = ct.create_string_buffer(b"", 8)
hwVersion = ct.create_string_buffer(b"", 8)
hwModel = ct.create_string_buffer(b"", 24)
errorString = ct.create_string_buffer(b"", 40)
numChannels = ct.c_int()
resolution = ct.c_double()
syncRate = ct.c_int()
Syncperiod = ct.c_double()
countRate = ct.c_int()
flags = ct.c_int()
recNum = ct.c_int()
nRecords = ct.c_int()
ctcstatus = ct.c_int()
warnings = ct.c_int()
warningstext = ct.create_string_buffer(b"", 16384)
TimeTag = ct.c_int()
Channel = ct.c_int()
Markers = ct.c_int()
DTime = ct.c_int()
Special = ct.c_int()
oflcorrection = ct.c_int()
progress = ct.c_int()

# Got PhotonT2
# TimeTag: Overflow-corrected arrival time in units of the device's base resolution 
# Channel: Channel the photon arrived (0 = Sync channel, 1..N = regular timing channel)
def GotPhotonT2(TimeTag, Channel):
    global outputfile, resolution
    return [Channel, TimeTag * resolution.value]

# ProcessT2
# HydraHarpV2 or TimeHarp260 or MultiHarp T2 record data
def ProcessT2(TTTRRecord, g2):
    global outputfile, recNum, nRecords, oflcorrection, Markers, Channel, Special
    ch = 0
    truetime = 0
    T2WRAPAROUND_V2 = 33554432    
    try:   
        # The data handed out to this function is transformed to an up to 32 digits long binary number
        # and this binary is filled by zeros from the left up to 32 bit
        recordDatabinary = '{0:0{1}b}'.format(TTTRRecord,32)
    except:
        print("\nThe file ended earlier than expected, at record %d/%d."\
          % (recNum.value, nRecords.value))
        sys.exit(0)

    # Then the different parts of this 32 bit are splitted and handed over to the Variables       
    Special = int(recordDatabinary[0:1], base=2) # 1 bit for Special    
    Channel = int(recordDatabinary[1:7], base=2) # 6 bit for Channel
    TimeTag = int(recordDatabinary[7:32], base=2) # 25 bit for TimeTag


    if Special==1:
        if Channel == 0x3F: # Special record, including Overflow as well as Markers and Sync

            # number of overflows is stored in timetag
            if TimeTag == 0: # if it is zero it is an old style single overflow 
                oflcorrection += T2WRAPAROUND_V2
            else:
                oflcorrection += T2WRAPAROUND_V2 * TimeTag
        if Channel>=1 and Channel<=15: # Markers
            truetime = oflcorrection + T2WRAPAROUND_V2 * TimeTag

        if Channel==0: # Sync
            truetime = oflcorrection + TimeTag
            ch = 0 # we encode the sync channel as 0
            g2.append(GotPhotonT2(truetime, ch))
    else: # regular input channel
        truetime = oflcorrection + TimeTag
        ch = Channel + 1 # we encode the regular channels as 1..N        
        g2.append(GotPhotonT2(truetime, ch))     
def Time_Differences(data, lim):
    td = []
    l = len(data)
    ch1 = 0
    ch2 = 0
    for i in range(l):
        store = data[i][1]
        store_ch = data[i][0]
        if store_ch == 1:
            ch1+=1
        else:
            ch2+=1
        j = i+1
        while j<l:
            if (abs(data[j][1] - store)/1000) > lim:
                break
            else:
                if data[j][0] != store_ch:
                    if data[j][0] == 1:
                        td.append(-(abs(data[j][1] - store)/1000)) 
                    else:
                        td.append((abs(data[j][1] - store)/1000))
            j+=1
    return td, ch1, ch2

if os.name == "nt":
    mhlib = ct.WinDLL("mhlib64.dll") 
else:
    mhlib = ct.CDLL("libmh150.so")


def closeDevices():
    for i in range(0, MAXDEVNUM):
        mhlib.MH_CloseDevice(ct.c_int(i))
    sys.exit(0)

def stoptttr():
    retcode = mhlib.MH_StopMeas(ct.c_int(dev[0]))
    if retcode < 0:
        print("MH_StopMeas error %1d. Aborted." % retcode)
    closeDevices()

def tryfunc(retcode, funcName, measRunning=False):
    if retcode < 0:
        mhlib.MH_GetErrorString(errorString, ct.c_int(retcode))
        print("MH_%s error %d (%s). Aborted." % (funcName, retcode,
              errorString.value.decode("utf-8")))
        if measRunning:
            stoptttr()
        else:
            closeDevices()

print("\nMultiHarp MHLib for Live g2 acquisition and plotting")
print("\n~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
mhlib.MH_GetLibraryVersion(libVersion)
print("Library version is %s" % libVersion.value.decode("utf-8"))
if libVersion.value.decode("utf-8") != LIB_VERSION:
    print("Warning: The application was built for version %s" % LIB_VERSION)


print("\n");

print("Mode              : %d" % mode)
print("Binning           : %d" % binning)
print("Offset            : %d" % offset)
print("SyncDivider       : %d" % syncDivider)
print("syncTriggerEdge   : %d" % syncTriggerEdge)
print("SyncTriggerLevel  : %d" % syncTriggerLevel)
print("SyncChannelOffset : %d" % syncChannelOffset)
print("InputTriggerEdge  : %d" % inputTriggerEdge)
print("InputTriggerLevel : %d" % inputTriggerLevel)
print("InputChannelOffset: %d" % inputChannelOffset)

print("\nSearching for MultiHarp devices...")
print("Devidx     Status")


retcode = mhlib.MH_OpenDevice(ct.c_int(0), hwSerial)
if retcode == 0:
    print("  %1d        S/N %s" % (0, hwSerial.value.decode("utf-8")))
    dev.append(0)
else:
    if retcode == -1: # MH_ERROR_DEVICE_OPEN_FAIL
        print("  %1d        no device" % 0)
    else:
        mhlib.MH_GetErrorString(errorString, ct.c_int(retcode))
        print("  %1d        %s" % (0, errorString.value.decode("utf8")))

# In this demo we will use the first MultiHarp device we find, i.e. dev[0].
# You can also use multiple devices in parallel.
# You can also check for specific serial numbers, so that you always know 
# which physical device you are talking to.

if len(dev) < 1:
    print("\nNo device available.")
    closeDevices()
print("\nUsing device #%1d" % dev[0])
print("\nInitializing the device...\n")

# with internal clock
tryfunc(mhlib.MH_Initialize(ct.c_int(dev[0]), ct.c_int(mode), ct.c_int(0)),
        "Initialize")

# Only for information
tryfunc(mhlib.MH_GetHardwareInfo(dev[0], hwModel, hwPartno, hwVersion),
        "GetHardwareInfo")
print("Found Model %s Part no %s Version %s" % (hwModel.value.decode("utf-8"),
      hwPartno.value.decode("utf-8"), hwVersion.value.decode("utf-8")))

tryfunc(mhlib.MH_GetNumOfInputChannels(ct.c_int(dev[0]), byref(numChannels)),
        "GetNumOfInputChannels")
print("Device has %i input channels." % numChannels.value)

tryfunc(mhlib.MH_SetSyncDiv(ct.c_int(dev[0]), ct.c_int(syncDivider)), "SetSyncDiv")

tryfunc(
    mhlib.MH_SetSyncEdgeTrg(ct.c_int(dev[0]), ct.c_int(syncTriggerLevel),
                            ct.c_int(syncTriggerEdge)),
    "SetSyncEdgeTrg"
    )

tryfunc(mhlib.MH_SetSyncChannelOffset(ct.c_int(dev[0]), ct.c_int(syncChannelOffset)),
        "SetSyncChannelOffset") # in ps, emulate a cable delay

# we use the same input settings for all channels, you can change this
for i in range(0, numChannels.value):
    tryfunc(
        mhlib.MH_SetInputEdgeTrg(ct.c_int(dev[0]), ct.c_int(i), ct.c_int(inputTriggerLevel),
                                 ct.c_int(inputTriggerEdge)),
        "SetInputEdgeTrg"
    )

    tryfunc(
        mhlib.MH_SetInputChannelOffset(ct.c_int(dev[0]), ct.c_int(i),
                                       ct.c_int(inputChannelOffset)),
        "SetInputChannelOffset"
    )# in ps, emulate a cable delay


tryfunc(mhlib.MH_GetResolution(ct.c_int(dev[0]), byref(resolution)), "GetResolution")
print("Resolution is %1.1lfps" % resolution.value)

# Note: after Init or SetSyncDiv you must allow >100 ms for valid  count rate readings
time.sleep(0.15)# in s

tryfunc(mhlib.MH_GetSyncRate(ct.c_int(dev[0]), byref(syncRate)), "GetSyncRate")
print("\nSyncrate=%1d/s" % syncRate.value)

for i in range(0, numChannels.value):
    tryfunc(mhlib.MH_GetCountRate(ct.c_int(dev[0]), ct.c_int(i), byref(countRate)),
            "GetCountRate")
    print("Countrate[%1d]=%1d/s" % (i, countRate.value))
# after getting the count rates you can check for warnings
oflcorrection = 0    


def giveRawTags():
    tryfunc(mhlib.MH_ReadFiFo(ct.c_int(dev[0]), byref(buffer), byref(nRecords)), "ReadFiFo", measRunning=True)
    data = []
    for i in range(nRecords.value):
        ProcessT2(buffer[i],data)
    return nRecords.value,data

# @tf.function
def t_diff(data, n, buffer, Q):
    # data = []
    # for i in range(n):
    #     ProcessT2(buffer[i],data)
    N1, N2, c_t, histogram = Q.get()
    
    # N1 = N1
    # N2 = N2
    # c_t = c_t
    lim = 500
    binwidth = 1
    t_ax = np.linspace(-lim, lim, int((2*lim/binwidth)+1))
    
    c_t += (data[-1][1] - data[0][1])/1e12 #s
    td, n1, n2 = Time_Differences(data, lim)   
    N1 += n1
    N2 += n2
    hist, bii = np.histogram(td, bins=t_ax)
        
    histogram = np.add(histogram, hist)

    norm_hist = (c_t*1e9/(N1*N2))*histogram
    
    Q.put([N1, N2, c_t, histogram])
    return norm_hist
