#ICA
import cv2
import numpy as np
import math
import matplotlib.pyplot as plt
from scipy import signal
from scipy import sparse
from scipy import linalg
from scipy import io as scio
from skimage.util import img_as_float
from sklearn.metrics import mean_squared_error
#utils
from signal_methods import utils

def ICA_POH(VideoFile,ECGFile, PPGFile, PlotTF):
    # paras:cut off frequency
    LPF = 0.7
    HPF = 2.5
    if PlotTF:
        PlotPRPSD = True
        PlotSNR = True
    else:
        PlotPRPST = False
        PlotSNR = False


    T, RGB, FS= process_video(VideoFile)
    
    #Detrend & ICA
    NyquistF = 1/2*FS
    BGRNorm = np.zeros(RGB.shape)
    Lambda = 100
?
    for c in range(3):
        BGRDetrend = utils.detrend(RGB[:,c],Lambda)
        BGRNorm[:,c] = (BGRDetrend-np.mean(BGRDetrend))/np.std(BGRDetrend)
    W,S = ica(np.mat(BGRNorm).H,3)

    #select BVP Source
    MaxPx = np.zeros((1,3))
    for c in range(3):
        FF = np.fft.fft(S[c,:])
        F = np.arange(0,FF.shape[1])/FF.shape[1]*FS*60;
        FF= FF[:,1:]
        FF = FF[0]
        N = FF.shape[0]
    
        Px   = np.abs(FF[:math.floor(N/2)])
        Px = np.multiply(Px,Px)
        Fx = np.arange(0,N/2)/(N/2)*NyquistF
        Px = Px/np.sum(Px,axis=0)
        MaxPx[0,c] = np.max(Px)
    M = np.max(MaxPx,axis=0)
    MaxComp = np.argmax(MaxPx)
    BVP_I = S[MaxComp,:]


    #Filter,Normalize

    B,A = signal.butter(3,[LPF/NyquistF,HPF/NyquistF],'bandpass')
    BVP_F = signal.filtfilt(B,A,BVP_I.astype(np.double))



    BVP = BVP_F

    #
    # BVP_mat = scio.loadmat("BVP_ica.mat")["BVP"]
    # print(np.sqrt(mean_squared_error(BVP_mat, BVP)))

    PR = utils.prpsd(BVP[0],FS,40,240,False)

    # HR_ECG = utils.parse_ECG(ECGFile,StartTime,Duration)
    # PR_PPG = utils.parse_PPG(PPGFile,StartTime,Duration)


    # SNR = utils.bvpsnr(BVP[0], FS, HR_ECG, PlotSNR)
    
    # plot the iPPG
    if PlotTF:
        plt.plot(BVP)
        plt.ylabel("BVP")
        plt.title("iPPG")
        plt.show()
    return BVP,PR

    #Ground Truth HR


def process_video(VideoFile):
    #Standard:
    VidObj = cv2.VideoCapture(VideoFile)
    FrameRate = VidObj.get(cv2.CAP_PROP_FPS)
    # FrameCount = math.ceil(VidObj.get(cv2.CAP_PROP_FRAME_COUNT))
    # Duration = FrameCount/FrameRate
    
    T = []
    RGB = []
    FN = 0
    CurrentTime = VidObj.get(cv2.CAP_PROP_POS_MSEC)
    success, frame = VidObj.read()
    
    while(success):
        T.append(CurrentTime)
        frame = cv2.cvtColor(np.array(frame).astype('float32'), cv2.COLOR_BGR2RGB)
        frame = np.asarray(frame)
        sum = np.sum(np.sum(frame,axis=0),axis=0)
        RGB.append(sum)
        success, frame = VidObj.read()
        CurrentTime = VidObj.get(cv2.CAP_PROP_POS_MSEC)
        FN+=1  
    return np.asarray(T),np.asarray(RGB),FrameRate

def ica(X,Nsources,Wprev=0):
    nRows = X.shape[0]
    nCols = X.shape[1]
    if nRows > nCols:
        print("Warning - The number of rows is cannot be greater than the number of columns.")
        print("Please transpose input.")

    if Nsources > min(nRows,nCols):
        Nsources = min(nRows,nCols)
        print('Warning - The number of soures cannot exceed number of observation channels.')
        print('The number of sources will be reduced to the number of observation channels ', Nsources)

    Winv,Zhat = jade(X,Nsources,Wprev)
    W = np.linalg.pinv(Winv)
    return W,Zhat

def jade(X,m,Wprev):
    n = X.shape[0]
    T = X.shape[1]

    nem = m
    seuil = 1/math.sqrt(T)/100

    #Whiten the matrix
    if m<n:
        D,U = np.linalg.eig(np.matmul(X,np.mat(X).H)/T)
        Diag = D
        k = np.argsort(Diag)
        pu = Diag[k]
        ibl = np.sqrt(pu[n-m:n]-np.mean(pu[0:n-m]))
        bl = np.true_divide(np.ones(m,1),ibl)
        W = np.matmul(np.diag(bl),np.transpose(U[0:n,k[n-m:n]]))
        IW = np.matmul(U[0:n,k[n-m:n]],np.diag(ibl))
    else:
        IW = linalg.sqrtm(np.matmul(X,X.H)/T)
        W = np.linalg.inv(IW)

    Y = np.mat(np.matmul(W,X))
    R = np.matmul(Y, Y.H) / T
    C = np.matmul(Y,Y.T)/T
    Q = np.zeros((m*m*m*m,1))
    index= 0

    for lx in range(m):
        Y1 = Y[lx,:]
        for kx in range(m):
            Yk1 = np.multiply(Y1,np.conj(Y[kx,:]))
            for jx in range(m):
                Yjk1 = np.multiply(Yk1,np.conj(Y[jx,:]))
                for ix in range(m):
                    Q[index] = np.matmul(Yjk1/math.sqrt(T),Y[ix,:].T/math.sqrt(T))-R[ix,jx]*R[lx,kx]-R[ix,kx]*R[lx,jx]-C[ix,lx]*np.conj(C[jx,kx])
                    index +=1
    #Compute and Reshape the significant Eigen
    D,U = np.linalg.eig(Q.reshape(m*m,m*m))
    Diag = abs(D)
    K = np.argsort(Diag)
    la = Diag[K]
    M = np.zeros((m,nem*m),dtype=complex)
    Z = np.zeros(m)
    h = m*m-1
    
    for u in range(0,nem*m,m):
        Z = U[:,K[h]].reshape((m,m))
        M[:,u:u+m] = la[h]*Z

        # if(u == m):
        #     M[:, u:u + m] = -la[h] * Z
        h = h-1


    #Approximate the Diagonalization of the Eigen Matrices:

    B = np.array([[1,0,0],[0,1,1],[0,0-1j,0+1j]])
    Bt = np.mat(B).H


    encore = 1
    if(Wprev == 0):
        V = np.eye(m).astype(complex)
    else:
        V = np.linalg.inv(Wprev)
    #Main Loop:
    while encore:
        encore = 0
        for p in range(m-1):
            for q in range(p+1,m):
                Ip = np.arange(p,nem*m,m)
                Iq = np.arange(q,nem*m,m)
                #Computing the Givens Angles
                g = np.mat([M[p,Ip]-M[q,Iq],M[p,Iq],M[q,Ip]])
                temp1 = np.matmul(g,g.H)
                temp2 = np.matmul(B,temp1)
                temp = np.matmul(temp2,Bt)
                D,vcp = np.linalg.eig(np.real(temp))
                #different with
                K = np.argsort(D)
                la = D[K]
                angles = vcp[:,K[2]]
                if(angles[0,0]<0):
                    angles = -angles
                c = np.sqrt(0.5+angles[0,0]/2)
                s = 0.5*(angles[1,0]-1j*angles[2,0])/c

                if(abs(s) > seuil):
                    encore = 1
                    pair = [p,q]
                    G = np.mat([[c,-np.conj(s)],[s,c]])
                    V[:,pair] = np.matmul(V[:,pair],G)
                    M[pair,:] = np.matmul(G.H,M[pair,:])
                    temp1 = c*M[:,Ip]+s*M[:,Iq]
                    temp2 = -np.conj(s)*M[:,Ip]+c*M[:,Iq]
                    temp = np.concatenate((temp1,temp2),axis=1)
                    Ipair = [Ip,Iq]
                    M[:,Ip] = temp1
                    M[:,Iq] = temp2


    #Whiten the Matrix
    #Estimation of the Mixing Matrix and Signal Separation
    #Different V
    # V =scio.loadmat("V.mat")["V"]
    A =  np.matmul(IW,V)
    S = np.matmul(np.mat(V).H,Y)
    # return A,S
    return A,S

# def preprocess_raw_video(videoFilePath, dim=36):
#
#     #########################################################################
#     # set up
#     t = []
#     i = 0
#     vidObj = cv2.VideoCapture(videoFilePath)
#     totalFrames = int(vidObj.get(cv2.CAP_PROP_FRAME_COUNT))  # get total frame size
#     Xsub = np.zeros((totalFrames, dim, dim, 3), dtype=np.float32)
#     height = vidObj.get(cv2.CAP_PROP_FRAME_HEIGHT)
#     width = vidObj.get(cv2.CAP_PROP_FRAME_WIDTH)
#     success, img = vidObj.read()
#     dims = img.shape
#     T = np.zeros((totalFrames, 1))
#     BGR = np.zeros((totalFrames, 3))
#     print("Orignal Height", height)
#     print("Original width", width)
#     #########################################################################
#     # Crop each frame size into dim x dim
#     while success:
#         t.append(vidObj.get(cv2.CAP_PROP_POS_MSEC))  # current timestamp in milisecond
#         vidLxL = cv2.resize(
#             img_as_float(img[:, int(width / 2) - int(height / 2 + 1):int(height / 2) + int(width / 2), :]),
#             (dim, dim), interpolation=cv2.INTER_AREA)
#         # vidLxL = cv2.rotate(vidLxL, cv2.ROTATE_90_CLOCKWISE)  # rotate 90 degree
#         vidLxL = cv2.cvtColor(vidLxL.astype('float32'), cv2.COLOR_BGR2RGB)
#         vidLxL[vidLxL > 1] = 1
#         vidLxL[vidLxL < (1 / 255)] = 1 / 255
#         Xsub[i, :, :, :] = vidLxL
#         success, img = vidObj.read()  # read the next one
#         i = i + 1
#
#     #########################################################################
#     # Normalized Frames in the motion branch
#     normalized_len = len(t) - 1
#     dXsub = np.zeros((normalized_len, dim, dim, 3), dtype=np.float32)
#     for j in range(normalized_len - 1):
#         dXsub[j, :, :, :] = (Xsub[j + 1, :, :, :] - Xsub[j, :, :, :]) / (Xsub[j + 1, :, :, :] + Xsub[j, :, :, :])
#     dXsub = dXsub / np.std(dXsub)
#     #########################################################################
#     # Normalize raw frames in the apperance branch
#     Xsub = Xsub - np.mean(Xsub)
#     Xsub = Xsub / np.std(Xsub)
#     Xsub = Xsub[:totalFrames - 1, :, :, :]
#     #########################################################################
#     # Plot an example of data after preprocess
#     dXsub = np.concatenate((dXsub, Xsub), axis=3);
#     return dXsub
#


    #return BVP,PR,HR_ECG,PR_PPG,SNR
# DataDirectory           = 'test_data\\'
# VideoFile               = DataDirectory+ 'video_example3.avi'
# FS                      = 120
# StartTime               = 0
# Duration                = 60
# ECGFile                 = DataDirectory+ 'ECGData.mat'
# PPGFile                 = DataDirectory+ 'PPGData.mat'
# PlotTF                  = False
#
