import numpy as np
# import os.path
# import elevation
from math import factorial
from numpy.linalg import cholesky, det
from scipy.linalg import lu
# from scipy import interpolate
# from osgeo import gdal
# import scipy.io as sio


# Kernel Function definition
def kerFunc(x1,x2,sigmaF,L):
    nL = len(L)
    sum=0.0
    for i in range(nL):
        sum = sum + ((x1[0, i]-x2[0, i])**2)/(2*float(L[i])**2)
    K = sigmaF**2 * np.exp(-sum)
    return K


# This calculates all the terms of a n-dimensional polynomial of degree d, recursively
def basisTerms(x,remDeg,res,terms):
    if remDeg==0 or x.size==0:
      terms = terms + [[res]]
      return terms
    else:
        for i in range(remDeg+1):
            new_res = res * x[0, 0]**i
            terms = basisTerms(x[0, 1:],remDeg-i,new_res,terms)
        return terms


# This calculates number of possible combinations of k objects chosen from n objects or n-choose-k
def nchoosek(n, k):
    return factorial(n) / factorial(k) / factorial(n - k)


# This calculates the logarithm of the determinant function directly and more efficiently
def logdet(M, isPosDef=False):

    assert( M.ndim == 2 and M.shape[0] == M.shape[1]),'The matrix should be a 2D square matrix.'

    if isPosDef:
        return 2 * np.sum(np.log((cholesky(M)).diagonal()))
    else:
        P, L, U = lu(M)
        P=np.matrix(P)
        U=np.matrix(U)
        L=np.matrix(L)
        du = U.diagonal()
        c = det(P) * np.prod(np.sign(du))
        return np.log(c) + np.sum(np.log(abs(du)))


def longLat2Km(lng, lat, longOrigin, latOrigin):
    lng = np.matrix(lng)
    lat = np.matrix(lat)
    # converting the lat degrees to km
    print('lat for mean')
    print(lat)
    meanLat = lat.mean()*np.pi/180.0
    #minLat = lat.min()
    #latDiff = lat-minLat
    latDiff = lat-latOrigin
    xv = latDiff*(111132.954 - 559.822 * np.cos(2*meanLat) + 1.175*np.cos(4*meanLat))
    # converting the lat degrees to km
    #minLong = long.min()
    #longDiff = long-minLong
    longDiff = lng-longOrigin
    a = 6378137.0
    b = 6356752.3142
    psi = np.arctan((b/a) * np.tan(lat*np.pi/180.0))
    xh = np.multiply(longDiff , (np.pi/180.0)* a * np.cos(psi) )

    return [xh/1000., xv/1000.]

# def longLat2Elevation(long,lat):
#     if not os.path.isfile('elevation_map/SLC-DEM.tif'):
#         elevation.clip(bounds=(-112.5, 40.5, -111.5, 41), output='elevation_map/SLC-DEM.tif')
#         elevation.clear()
#
#     gdal.UseExceptions()
#     elevData = gdal.Open('elevation_map/SLC-DEM.tif')
#     band = elevData.GetRasterBand(1)
#     elevs = band.ReadAsArray()
#     dataInfo = elevData.GetGeoTransform()
#     initLong = dataInfo[0]
#     initLat = dataInfo[3]
#     dLong = dataInfo[1]
#     dLat = dataInfo[5]
#     nLat = elevs.shape[0]
#     nLong = elevs.shape[1]
#     gridLongs = [initLong+dLong*i for i in range(nLong)]
#     gridLats = [initLat+dLat*i for i in range(nLat)]
#     f = interpolate.interp2d(gridLongs, gridLats, elevs, kind='linear')
#     endLong = initLong + (nLong-1)* dLong
#     endLat = initLat + (nLat-1)* dLat
# #    sio.savemat('elevationMap.mat', {'elevs':elevs,'gridLongs':gridLongs,'gridLats':gridLats,'initLong':initLong,'initLat':initLat,'endLong':endLong,'endLat':endLat})
#     el = []
#     for i in range(long.shape[0]):
#         lo = long[i, 0]
#         la = lat[i, 0]
#         assert(lo>=initLong and lo<=endLong), "The longitude is out of bound for elevation look-up!"
#         assert(la<=initLat and la>=endLat), "The latitude is out of bound for elevation look-up!"
#         el += [f(lo, la)[0]]
#
#     return (np.matrix(el).T)/1000.


def calibrate(x, models):
    assert(np.shape(x)[1]==len(models)), 'You need to provide a model name for each column of the data matrix.'
    xCalibrated = x.copy()
    for i, model in enumerate(models):
        if (model=='PMS5003'):
            xCalibrated[:,i] = 0.7778*x[:,i]+2.6536
            #xCalibrated[:,i] = -67.0241*log(-0.00985*x[:,i]+0.973658)
        elif (model=='PMS1003'):
            xCalibrated[:,i] = 0.5431*x[:,i]+1.0607
        #   xCalibrated[:,i] = -54.9149*log(-0.00765*x[:,i]+0.981971)
        elif (model=='H1.1'):
            xCalibrated[:,i] = 0.4528*x[:,i]+3.526
    return xCalibrated
