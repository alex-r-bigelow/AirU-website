import numpy as np
from math import log, pi
from numpy.linalg import matrix_rank, det
from utility_tools import kerFunc, basisTerms, nchoosek, logdet


def marginalNegLL(x,y,L,sigmaF,sigmaN,basisFnDeg,isARD):

    if isARD:
        assert(len(L)==x.shape[1]),'The number of length scales should be the same as the independent variables in ARD mode'
    else:
        assert(len(L)==1),'If the ARD mode is off, you just need one length scale for all the independent variables'

    nObs = x.shape[0]
    nts = y.shape[1]

    if basisFnDeg>=0:
        nIvar  = x.shape[1]
        nBasis = nchoosek(basisFnDeg+nIvar,basisFnDeg)
        H      = np.matrix(np.zeros((nBasis,nObs)))

    delta = np.matrix(np.identity(nObs))
    K = np.matrix(np.zeros((nObs, nObs)))
    if not isARD:
        Lnew = [L[0] for i in range(x.shape[1])]
    else:
        Lnew = L

    for i in range(nObs):
        for j in range(nObs):
            K[i,j] = kerFunc(x[i,:],x[j,:],sigmaF,Lnew) + sigmaN**2 * delta[i,j]
        if basisFnDeg>=0:
            H[:,i] = basisTerms(x[i,:],basisFnDeg,1, [])
    
    invK  = K.I
    invKy = invK * y

    if basisFnDeg>=0:
        m = matrix_rank(H)

    if basisFnDeg>=0:
        invKH = invK * H.T
        A = H * invKH
        C = invKH * A.I * invKH.T

    NLL=0
    for t in range(nts):
        NLL = NLL + 0.5*(y[:,t].T*invKy[:,t] + logdet(K,True) + nObs*log(2*pi))
        if basisFnDeg>=0:
            NLL = NLL - 0.5*( y[:,t].T*C*y[:,t] - log(det(A)) + m*log(2*pi))
    
    return NLL

    
