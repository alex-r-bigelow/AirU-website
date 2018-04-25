import logging

import numpy as np
# import matplotlib.pyplot as pl
# from NegLLGradient import gradLOONLL
from negativeLogLikelihood import marginalNegLL  # looNegLL
from NegLLGradient import gradMNLL
from gradDescent import gradDescent
from utility_tools import kerFunc, basisTerms, nchoosek

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


def gpRegression(x, y, xQuery, x_tr, y_tr, sigmaF, optSigmaF, L, optL, sigmaN, optSigmaN, basisFnDeg, isARD, isSpatIsot, learnRate, tol, maxIt, effOpt, center, doRegression):
    # assert(y.shape[0]>=y.shape[1]),'The observed values shold be in a column vector'
    assert(x.shape[0] >= x.shape[1]), 'The independent variables should be in the columns, and the observations in the rows'
    # assert(y_tr.shape[0]>=y_tr.shape[1]),'The observed values shold be in a column vector'
    assert(x_tr.shape[0] >= x_tr.shape[1]), 'The independent variables should be in the columns, and the observations in the rows'
    assert(xQuery.shape[0] >= xQuery.shape[1]), 'The independent variables should be in the columns, and the tests in the rows'

    nL = len(L)
    # conditioning related to ARD mode and/or spatially isotropic case
    if isARD:
        if isSpatIsot:
            assert(nL == x.shape[1] - 1), 'The number of length scales should be the same as the independent variables minus 1 in spatially isotropic ARD mode'
            L = [L[0], L[0]] + L[1:]
            nL = len(L)
        else:
            assert(nL == x.shape[1]), 'The number of length scales should be the same as the independent variables in ARD mode'
    else:
        assert(nL == 1), 'If the mode is not ARD you just need one length scale for all the independent variables'

    # data preprocessing
    nObs = x.shape[0]
    nQuery = xQuery.shape[0]
    if basisFnDeg < 0:
        yMean = np.mean(y)
        yMean_tr = np.mean(y_tr, 0)
        if (center):
            y_tr = y_tr - np.matrix(np.ones((y_tr.shape[0], 1))) * yMean_tr
            y = y - yMean

    # Model Selection
#    if (optL or optSigmaF or optSigmaN):
#        if (optL and not optSigmaF and not optSigmaN):
#            print 'Finding The optimized model parameter L...'
#            logFun = lambda theta: looNegLL(x_tr,y_tr,theta[0:nL],sigmaF,sigmaN,effOpt,basisFnDeg,isARD,isSpatIsot)
#            theta0 = [L]
#            # using gradient descent
#            gradLogFun = lambda theta: gradLOONLL(x_tr,y_tr,theta[0:nL],sigmaF,sigmaN,optL,optSigmaF,optSigmaN,basisFnDeg,isARD,isSpatIsot)
#            theta = gradDescent(gradLogFun,logFun,theta0,[optL]*nL+[optSigmaF, optSigmaN],tol,learnRate,maxIt,True)
#            L=np.ndarray.tolist(abs(np.array(theta[0:nL])))
#        elif (not optL and optSigmaF and not optSigmaN):
#            print 'Finding The optimized model parameter sigma_F...'
#            logFun = lambda theta: looNegLL(x_tr,y_tr,L,theta[0],sigmaN,effOpt,isARD,basisFnDeg,isSpatIsot)
#            theta0 = [sigmaF]
#            # using gradient descent
#            gradLogFun = lambda theta: gradLOONLL(x_tr,y_tr,L,theta[0],sigmaN,optL,optSigmaF,optSigmaN,basisFnDeg,isARD,isSpatIsot)
#            theta = gradDescent(gradLogFun,logFun,theta0,[optL]*nL+[optSigmaF, optSigmaN],tol,learnRate,maxIt,True)
#            sigmaF=abs(theta[0])
#        elif (optL and optSigmaF and not optSigmaN):
#            print 'Finding The optimized model parameters L and sigma_F...'
#            #logFun = lambda theta: looNegLL(x_tr,y_tr,theta[0:nL],theta[nL],sigmaN,effOpt,basisFnDeg,isARD,isSpatIsot)
#            logFun = lambda theta: marginalNegLL(x_tr,y_tr,theta[0:nL],theta[nL],sigmaN,basisFnDeg,isARD,isSpatIsot)
#            theta0 = [L,sigmaF]
#            # using gradient descent
#            # gradLogFun = lambda theta: gradLOONLL(x_tr,y_tr,theta[0:nL],theta[nL],sigmaN,optL,optSigmaF,optSigmaN,basisFnDeg,isARD,isSpatIsot)
#            gradLogFun = lambda theta: gradMNLL(x,y,theta[0:nL],theta[nL],sigmaN,optL,optSigmaF,optSigmaN,basisFnDeg,isARD,isSpatIsot)
#            theta = gradDescent(gradLogFun,logFun,theta0,[optL]*nL+[optSigmaF, optSigmaN],tol,learnRate,maxIt,True)
#            # using SGD
#            # gradLogFun = lambda theta,x,y: gradLOONLL(x,y,theta[0:nL],theta[nL],sigmaN,optL,optSigmaF,optSigmaN,isARD,isSpatIsot)
#            # gradLogFun = lambda theta,x,y: gradMNLL(x,y,theta[0:nL],theta[nL],sigmaN,optL,optSigmaF,optSigmaN,isARD,isSpatIsot)
#            # theta = SGD(gradLogFun,logFun,x_tr,y_tr,theta0,[optL]*nL+[optSigmaF, optSigmaN],5,tol,learnRate,maxIt,True)
#            L=np.ndarray.tolist(abs(np.array(theta[0:nL])))
#            sigmaF=abs(theta[nL])
#        elif (optL and optSigmaF and optSigmaN):
#            print 'Finding The optimized model parameters L, sigma_F and sigma_N...'
#            logFun = lambda theta: looNegLL(x_tr,y_tr,theta[0:nL],theta[nL],theta[nL+1],effOpt,basisFnDeg,isARD,isSpatIsot)
#            theta0 = [L,sigmaF,sigmaN]
#            # using gradient descent
#            gradLogFun = lambda theta: gradLOONLL(x_tr,y_tr,theta[0:nL],theta[nL],theta[nL+1],optL,optSigmaF,optSigmaN,basisFnDeg,isARD,isSpatIsot)
#            theta = gradDescent(gradLogFun,logFun,theta0,[optL]*nL+[optSigmaF, optSigmaN],tol,learnRate,maxIt,True)
#
#            L=np.ndarray.tolist(abs(np.array(theta[0:nL])))
#            sigmaF=abs(theta[nL])
#            sigmaN=abs(theta[nL+1])
#        else:
#            sys.exit('ERROR: This combination is not supported for optimization; optimize ('\
#            +optL*'L'+(optL and (optSigmaF or optSigmaN))*', '+optSigmaF*'sigmaF'+(optSigmaF and optSigmaN)*', '\
#            +optSigmaN*'sigmaN'+') and do not optimize ('+ (not optL)*'L'+(not optL and (not optSigmaF or not optSigmaN))*', '\
#            +(not optSigmaF)*'sigmaF'+(not optSigmaF and not optSigmaN)*', '+(not optSigmaN)*'sigmaN'+')')

    if (optL or optSigmaF or optSigmaN):
        print 'Finding The optimized model parameters ' + optL * 'L' + (optL and optSigmaF and optSigmaN) * ', ' + \
              (optL and (optSigmaF or optSigmaN) and not(optSigmaF and optSigmaN)) * ' and ' + optSigmaF * 'sigmaF' + \
              (optSigmaF and optSigmaN) * ' and ' + optSigmaN * 'sigmaN' + '...'

        theta0 = L + [sigmaF, sigmaN]
        # logFun = lambda theta: looNegLL(x_tr,y_tr,theta[0:nL],theta[nL],theta[nL+1],effOpt,basisFnDeg,isARD,isSpatIsot)
        logFun = lambda theta: marginalNegLL(x_tr, y_tr, theta[0:nL], theta[nL], theta[nL + 1], basisFnDeg, isARD)
        # using gradient descent
        # gradLogFun = lambda theta: gradLOONLL(x_tr,y_tr,theta[0:nL],theta[nL],theta[nL+1],optL,optSigmaF,optSigmaN,basisFnDeg,isARD,isSpatIsot)
        gradLogFun = lambda theta: gradMNLL(x, y, theta[0:nL], theta[nL], theta[nL + 1], optL, optSigmaF, optSigmaN, basisFnDeg, isARD, isSpatIsot)
        theta = gradDescent(gradLogFun, logFun, theta0, [optL] * nL + [optSigmaF, optSigmaN], tol, learnRate, maxIt, True)
        # using SGD
        # gradLogFun = lambda theta,x,y: gradLOONLL(x,y,theta[0:nL],theta[nL],theta[nL+1],optL,optSigmaF,optSigmaN,isARD,isSpatIsot)
        # gradLogFun = lambda theta,x,y: gradMNLL(x,y,theta[0:nL],theta[nL],theta[nL+1],optL,optSigmaF,optSigmaN,isARD,isSpatIsot)
        # theta = SGD(gradLogFun,logFun,x_tr,y_tr,theta0,[optL]*nL+[optSigmaF, optSigmaN],5,tol,learnRate,maxIt,True)
        L = np.ndarray.tolist(abs(np.array(theta[0:nL])))
        sigmaF = abs(theta[nL])
        sigmaN = abs(theta[nL + 1])
        print L
        print sigmaF
        print sigmaN

    if doRegression:
        # print 'Applying the regression model...'
        LOGGER.info('Applying the regression model...')
        K = np.matrix(np.zeros((nObs, nObs)))
        KStar = np.matrix(np.zeros((nQuery, nObs)))
        Kss = np.matrix(np.zeros((nQuery, 1)))
        delta = np.matrix(np.identity(nObs))
        if basisFnDeg >= 0:
            nIvar = x.shape[1]
            nBasis = int(nchoosek(basisFnDeg + nIvar, basisFnDeg))
            H = np.matrix(np.zeros((nBasis, nObs)))
            HStar = np.matrix(np.zeros((nBasis, nQuery)))

        for i in range(nObs):
            for j in range(nObs):
                K[i, j] = kerFunc(x[i, :], x[j, :], sigmaF, L) + sigmaN**2 * delta[i, j]
            for j in range(nQuery):
                KStar[j, i] = kerFunc(xQuery[j, :], x[i, :], sigmaF, L)
            if basisFnDeg >= 0:
                H[:, i] = basisTerms(x[i, :], basisFnDeg, 1, [])

        for i in range(nQuery):
            Kss[i, 0] = kerFunc(xQuery[i, :], xQuery[i, :], sigmaF, L)  # + sigmaN^2;

            if basisFnDeg >= 0:
                HStar[:, i] = basisTerms(xQuery[i, :], basisFnDeg, 1, [])

        invK = K.I
        invKy = invK * y
        yPred = KStar * invKy
        invKKsTr = invK * KStar.T
        if basisFnDeg < 0:
            if center:
                yPred = yPred + yMean
        else:
            invKH = invK * H.T
            R = HStar - H * invKKsTr
            Beta = (H * invKH).I * (H * invKy)
            yPred = yPred + R.T * Beta
            tmpTerm = (H * invKH).I * R

        yVar = np.matrix(np.zeros((nQuery, 1)))
        for i in range(nQuery):
            yVar[i, 0] = Kss[i, 0] - KStar[i, :] * invKKsTr[:, i]
        # yVar = Kss - (KStar * invKKsTr).diagonal()

        if basisFnDeg >= 0:
            for i in range(nQuery):
                yVar[i, 0] = yVar[i, 0] + R[:, i].T * tmpTerm[:, i]

            # yVar = yVar + (R.T*((H*invKH).I * R)).diagonal()

        # print "The program terminates after closing the plots..."
        # pl.show()
    if (optL or optSigmaF or optSigmaN) and doRegression:
        return [yPred, yVar, L, sigmaF, sigmaN]
    elif (optL or optSigmaF or optSigmaN):
        return [L, sigmaF, sigmaN]
    elif doRegression:
        return [yPred, yVar]
    else:
        print "You should do either training, applying the regression or both, otherwise the Gussian Processing Regression does nothing..!"
        return -1
