from MH_INIT import *
import time
import numpy as np
import matplotlib.pyplot as plt
import concurrent.futures
import time
import os
import pandas as pd
from queue import Queue

def main():
    start_time = time.time()
    
    t_acq = int(input("Enter acquisition time in seconds: "))
    acqTime = t_acq #sec
    lim = 500
    binwidth = 1
    t_ax = np.linspace(-lim, lim, int((2*lim/binwidth)+1))
    histogram = np.zeros(len(t_ax)-1)
    tacq = acqTime*1000
    plt.ion()
    fig = plt.figure()
    tryfunc(mhlib.MH_StartMeas(ct.c_int(dev[0]), ct.c_int(tacq)), "StartMeas")
    start_time = time.time()
    Q = Queue()
    Q.put([0, 0, 0, histogram])
    
    tryfunc(mhlib.MH_CTCStatus(ct.c_int(dev[0]), byref(ctcstatus)), "CTCStatus")
    while ctcstatus.value == 0:
        tryfunc(mhlib.MH_GetFlags(ct.c_int(dev[0]), byref(flags)), "GetFlags")

        if flags.value & FLAG_FIFOFULL > 0:
            print("\nFiFo Overrun!")
            stoptttr()
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_data = executor.submit(giveRawTags)
            n,data = future_data.result()
            if n > 0:
                result_t_diff = 0
                norm_hist = executor.submit(t_diff, data, n, buffer, Q)
                 
                plt.cla()
                plt.plot(t_ax[:-1], norm_hist.result())
                plt.show()
                plt.pause(0.05)

            else:
                tryfunc(mhlib.MH_CTCStatus(ct.c_int(dev[0]), byref(ctcstatus)),"CTCStatus")
                if ctcstatus.value > 0: 
                    print("\nDone")
                    print("--- %s seconds ---" % (time.time() - start_time))

    save = input("Do you want to save the data (y or n): ")
    if save == 'y':
        name = input("Input filename: ")
        filename = os.getcwd() + "\\" + str(name) + ".csv"
        df = pd.DataFrame([t_ax, norm_hist.result()]).T
        df.columns = ['t axis (ns)','Normalized g2 values']
        df.to_csv(filename, index=False)
        print('Your file is saved as:',filename)  
if __name__ == "__main__":
    main()


closeDevices()

