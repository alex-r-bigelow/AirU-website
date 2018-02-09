import numpy as np
import matplotlib.pyplot as pl

def gradDescent(gradFun,Fun,theta0,optList,tol,gamma0,maxIt,plotObj):
# Finds the theta values that minimizes the objective function Fun
# 
# gradFun: a function that calculates gradients of the objective functions with respect to theta and stores it in a 1D numpy matrix
# Fun: a function that calculates the objective 
# theta0: initial values for theta
# optList: a boolean list that defines which dimensions of theta to be optimized
# tol: the convergence tolerance
# gamma0: initial learning rate
# maxit: the maximum number of iterations allowed
# plotObj: a flag for plotting the objective values as the algorithm iterates

    theta = np.array([theta0])
    err=1
    it = 0

    obj = Fun(theta0)
    print 'Objective = ' + str(obj)

    if plotObj:
#        pl.ion()
        pl.xlabel('#iterations')
        pl.ylabel('objective value')
        pl.plot(it,obj,'bo',markersize=8)
        pl.pause(0.05)
#        fig.canvas.draw()
#        pl.show()


    while err>tol and it<=maxIt:
        it += 1
        gamma = gamma0
        grad  = gradFun(theta.tolist()[0])
        # theta[0] = theta[0]
        # theta[1] = theta[1] - gamma * grad[1]
        theta = theta - gamma * np.select([optList], [grad.T])
        obj_n = Fun(theta.tolist()[0])
        if plotObj:
            pl.plot(it,obj_n,'bo',markersize=8)
            pl.pause(0.05)
#            fig.canvas.draw()

        
        err = abs(obj-obj_n)
        obj = obj_n
        print 'it #'+str(it)+ ': Objective change = ' + str(err)

    return theta.tolist()[0]
