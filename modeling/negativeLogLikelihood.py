import numpy as np
from math import log, pi
from numpy.linalg import matrix_rank, det
from utility_tools import kerFunc, basisTerms, nchoosek, logdet


def marginalNegLL(x,y,L,sigmaF,sigmaN,optL,optSigmaF,optSigmaN,basisFnDeg,isARD,isSpatIsot,kerType='EXP',calcGrad=True):

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

    if calcGrad: # gradient is required to be calculated
        nL = len(L);
        dKdSF = np.matrix(np.zeros((nObs, nObs)))
        dKdL = np.zeros((nObs,nObs,nL))
        dKdSN = np.matrix(np.zeros((nObs, nObs)))
    for i in range(nObs):
        for j in range(nObs):
            K[i,j] = kerFunc(x[i,:],x[j,:],sigmaF,Lnew,kerType) + sigmaN**2 * delta[i,j]
            if calcGrad: # gradient is required to be calculated
                if isARD:
                    L3 = [Li**(-3) for Li in L]
                    sum=0.0
                    for l in range(len(Lnew)):
                        sum = sum + ((x[i, l]-x[j, l])**2)/(2*float(Lnew[l])**2)
                    if isSpatIsot:
                        if optL:
                            dKdL[i,j,0] = sigmaF**2 * np.exp(-sum) * (((x[i,0]-x[j,0])**(2)+(x[i,1]-x[j,1])**(2)) *L3[0])
                            dKdL[i,j,1] = dKdL[i,j,0];
                            for k in range(2,nL):
                                dKdL[i,j,k] = sigmaF**2 * np.exp(-sum) * (((x[i,k]-x[j,k])**2)*L3[k])
                        if optSigmaF:
                            dKdSF[i,j] = 2*sigmaF * np.exp(-sum)
                        if optSigmaN:
                            dKdSN[i,j] = 2*sigmaN * delta[i,j]
                    else:
                        if optL:
                            for l in range(len(L3)):
                                dKdL[i,j,l] = sigmaF**2 * np.exp(-sum) * (x[i,l]-x[j,l])**(2)*L3[l]
                        if optSigmaF:
                            dKdSF[i,j] = 2*sigmaF * np.exp(-sum)
                        if optSigmaN:
                            dKdSN[i,j] = 2*sigmaN * delta[i,j]
                else:
                    d2=0.0
                    for l in range(x.shape[1]):
                        d2 = d2 + ((x[i, l]-x[j, l])**2)
                    if optL:
                        dKdL[i,j,0] = sigmaF**2 * np.exp(-d2/(2*L[0]**2)) * (d2/L[0]**3)
                    if optSigmaF:
                        dKdSF[i,j] = 2*sigmaF * np.exp(-d2/(2*L[0]**2))
                    if optSigmaN:
                        dKdSN[i,j] = 2*sigmaN * delta[i,j]
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
        if calcGrad: # gradient is required to be calculated
            invA = A.I
            invAH = invA * H
            HinvA = H.T * invA
    if calcGrad: # gradient is required to be calculated
        gradNLL = np.matrix(np.zeros((nL+2,1)))
    NLL=0
    for t in range(nts):
        NLL = NLL + 0.5*(y[:,t].T*invKy[:,t] + logdet(K,True) + nObs*log(2*pi))
        if basisFnDeg>=0:
            NLL = NLL - 0.5*( y[:,t].T*C*y[:,t] - log(det(A)) + m*log(2*pi))
        if calcGrad: # gradient is required to be calculated
            term = invKy[:,t]*invKy[:,t].T-invK
            if optL:
                for j in range(nL):
                    gradNLL[j,0] = gradNLL[j,0] - 0.5*np.trace(term*dKdL[:,:,j])
                    if basisFnDeg>=0:
                        gradNLL[j,0] = gradNLL[j, 0]\
                        - basisFnGradTerms(invAH,HinvA,np.matrix(dKdL[:,:,j]),invKy[:,t],invKH,invA)
            if optSigmaF:
                gradNLL[nL,0] = gradNLL[nL,0] - 0.5*np.trace(term*dKdSF)
                if basisFnDeg>=0:
                    gradNLL[nL,0] = gradNLL[nL,0]\
                    - basisFnGradTerms(invAH,HinvA,dKdSF,invKy[:,t],invKH,invA)
            if optSigmaN:
                gradNLL[nL+1,0] = gradNLL[nL+1,0] - 0.5*np.trace(term*dKdSN)
                if basisFnDeg>=0:
                    gradNLL[nL+1,0] = gradNLL[nL+1,0]\
                    - basisFnGradTerms(invAH,HinvA,dKdSN,invKy[:,t],invKH,invA)
    
    return NLL, gradNLL

def basisFnGradTerms(invAH,HinvA,dKdTheta,invKy,invKH,invA):
    bFnGrTerms = 0.5*(np.trace(invA*invKH.T*dKdTheta*invKH)\
    - invKy.T * \
    (dKdTheta*invKH*invAH\
    - HinvA*invKH.T*dKdTheta*invKH*invAH
    + HinvA*invKH.T*dKdTheta)*\
    invKy)
    
    return bFnGrTerms    
