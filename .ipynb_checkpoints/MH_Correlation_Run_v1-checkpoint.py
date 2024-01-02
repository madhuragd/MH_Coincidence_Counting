from MH_INIT import *
import time
import numpy as np

def correlation(acqTime, binwidth, lim):
    
    tacq = acqTime*1000

    tryfunc(mhlib.MH_StartMeas(ct.c_int(dev[0]), ct.c_int(tacq)), "StartMeas")
    start_time = time.time()
    c_t = 0
    binw = binwidth # in ns
    t_ax = np.linspace(-lim, lim, int((2*lim/binwidth)+1))
    histogram = np.zeros(len(t_ax)-1)
    N1 = 0
    N2 = 0
    plt.ion()

    tryfunc(mhlib.MH_CTCStatus(ct.c_int(dev[0]), byref(ctcstatus)),
                    "CTCStatus")
    while ctcstatus.value == 0:
        tryfunc(mhlib.MH_GetFlags(ct.c_int(dev[0]), byref(flags)), "GetFlags")

        if flags.value & FLAG_FIFOFULL > 0:
            print("\nFiFo Overrun!")
            stoptttr()
        
        tryfunc(
            mhlib.MH_ReadFiFo(ct.c_int(dev[0]), byref(buffer), byref(nRecords)),
            "ReadFiFo", measRunning=True
        )
        
        if nRecords.value > 0: 
            
            data = []
            
            for i in range(0,nRecords.value): 
                ProcessT2(buffer[i], data)
            
            c_t += (data[-1][1] - data[0][1])/1e12 #s
            td, n1, n2 = Time_Differences(data, lim)   
            N1 += n1
            N2 += n2
            
            hist, bii = np.histogram(td, bins=t_ax)
        
            histogram = np.add(histogram, hist)
           
            norm_hist = (c_t*1e9/(N1*N2))*histogram
            plt.cla()
            plt.plot(t_ax[:-1], norm_hist)
            plt.show()
            plt.pause(0.05)
            
        else:
            tryfunc(mhlib.MH_CTCStatus(ct.c_int(dev[0]), byref(ctcstatus)),
                    "CTCStatus")
            if ctcstatus.value > 0: 
                print("\nDone")
                print("--- %s seconds ---" % (time.time() - start_time))

        # within this loop you can also read the count rates if needed.

    return t_ax, norm_hist


t_acq = int(input("Enter acquisition time in seconds: "))
t_ax, MH_code = correlation(t_acq, 1, 500)
import os
import pandas as pd

save = input("Do you want to save the data (y or n): ")
if save == 'y':
    name = input("Input filename: ")
    filename = os.getcwd() + "\\" + str(name) + ".csv"
    df = pd.DataFrame([t_ax, MH_code]).T
    df.columns = ['t axis (ns)','Normalized g2 values']
    df.to_csv(filename, index=False)
    print('Your file is saved as:',filename)    
closeDevices()