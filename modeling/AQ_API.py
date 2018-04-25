import logging

import numpy as np
from GPR import gpRegression
from utility_tools import longLat2Km  # longLat2Elevation

# LOGGER = logging.getLogger(__name__)
# LOGGER.setLevel(logging.INFO)


def AQGPR(xQuery, x_tr, y_tr, sigmaF0=8.3779, L0=[4.7273, 7.5732], sigmaN=5.81, basisFnDeg=1, isTrain=False, isRegression=True):
    # LOGGER.info('logging in AQGPR')
    assert(isTrain or isRegression), "You should do either training, applying the regression or both!"
    assert(len(x_tr) == len(y_tr)), "Number of the points in the independent variables must be equal to the number of the points in the measurments!"
    if isRegression:
        assert(len(xQuery[0]) == len(x_tr[0])), "Dimension of the query data should be the same as the dimension of the data being used for regression."
    xQuery = np.matrix(xQuery)
    x_tr = np.matrix(x_tr)
    lat = xQuery[:, 0]
    long = xQuery[:, 1]
    time = xQuery[:, 2]
    lat_tr = x_tr[:, 0]
    long_tr = x_tr[:, 1]
    time_tr = x_tr[:, 2]
    longOrigin = long_tr.min()
    latOrigin = lat_tr.min()
    [xh_tr, xv_tr] = longLat2Km(long_tr, lat_tr, longOrigin, latOrigin)
    [xh, xv] = longLat2Km(long, lat, longOrigin, latOrigin)

#    elev_tr = longLat2Elevation(long_tr,lat_tr)
#    elev = longLat2Elevation(long,lat)
#    print elev_tr
#    print elev
#    xQuery = np.concatenate((xh, xv, elev, time),axis=1)
#    x_tr = np.concatenate((xh_tr, xv_tr, elev_tr, time_tr),axis=1)
    xQuery = np.concatenate((xh, xv, time), axis=1)
    x_tr = np.concatenate((xh_tr, xv_tr, time_tr), axis=1)

#    # Applying the model
    sigmaN = 5.81
    isARD = True
    isSpatIsot = True
    effOpt = True
    center = True
    learnRate = 1e-3
    tol = 1e-5
    maxIt = 400
    if isTrain and isRegression:
        optSigmaF = True
        optL = True
        optSigmaN = False
        [yPred, yVar, L, sigmaF, sigmaN] = gpRegression(x_tr,y_tr,xQuery,x_tr,y_tr,sigmaF0,optSigmaF,L0,optL,sigmaN,optSigmaN,basisFnDeg,isARD,isSpatIsot,learnRate,tol,maxIt,effOpt,center, isRegression)
        return [yPred, yVar, L, sigmaF, sigmaN]
    elif isTrain:
        optSigmaF = True
        optL = True
        optSigmaN = False
        [L, sigmaF, sigmaN] = gpRegression(x_tr,y_tr,xQuery,x_tr,y_tr,sigmaF0,optSigmaF,L0,optL,sigmaN,optSigmaN,basisFnDeg,isARD,isSpatIsot,learnRate,tol,maxIt,effOpt,center, isRegression)
        return [L, sigmaF, sigmaN]
    else:
        optSigmaF = False
        optL = False
        optSigmaN = False
        [yPred, yVar] = gpRegression(x_tr,y_tr,xQuery,x_tr,y_tr,sigmaF0,optSigmaF,L0,optL,sigmaN,optSigmaN,basisFnDeg,isARD,isSpatIsot,learnRate,tol,maxIt,effOpt,center, isRegression)

        return [yPred, yVar]
