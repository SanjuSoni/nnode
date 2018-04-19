#!/usr/bin/env python

# Use a neural network to solve a 2-variable, 2nd-order PDE BVP with
# Dirichlet BC. Note that any 2-variable 2nd-order PDE BVP can be
# mapped to a corresponding BVP of this type, so this is the only
# solution form needed.

# The general form of such equations is, for Y = Y(x,y):

# G(x[], Y, delY[], del2Y[]) = 0

# Notation notes:

# 1. Names that end in 'f' are usually functions, or containers of functions.

# 2. Underscores separate the numerator and denominator in a name
# which represents a derivative.

# 3. Names beginning with 'del' are gradients of another function, in
# the form of function lists.

#********************************************************************************

# Import external modules, using standard shorthand.

import argparse
from importlib import import_module
from math import sqrt
import numpy as np
from sigma import sigma, dsigma_dz, d2sigma_dz2, d3sigma_dz3

#********************************************************************************

# Default values for program parameters
default_debug = False
default_eta = 0.01
default_maxepochs = 1000
default_nhid = 10
default_ntrain = 10
default_pde = 'pde02bvp'
default_seed = 0
default_verbose = False

# Default ranges for weights and biases
w_min = -1
w_max = 1
u_min = -1
u_max = 1
v_min = -1
v_max = 1

#********************************************************************************

# The domain of the trial solution is assumed to be [[0, 1], [0, 1]].

# Define the coefficient functions for the trial solution, and their derivatives.
def Af(xy, bcf):
    (x, y) = xy
    ((f0f, g0f), (f1f, g1f)) = bcf
    A = (
        (1 - x)*f0f(y) + x*f1f(y)
        + (1 - y)*(g0f(x) - (1 - x)*g0f(0) - x*g0f(1))
        + y*(g1f(x) - (1 - x)*g1f(0) - x*g1f(1))
    )
    return A

def dA_dxf(xy, bcf, bcdf):
    (x, y) = xy
    ((f0f, g0f), (f1f, g1f)) = bcf
    ((df0_dyf, dg0_dxf), (df1_dyf, dg1_dxf)) = bcdf
    dA_dx = (
        -f0f(y) + f1f(y) + (1 - y)*(dg0_dxf(x) + g0f(0) - g0f(1))
        + y*(dg1_dxf(x) + g1f(0) - g1f(1))
        )
    return dA_dx

def dA_dyf(xy, bcf, bcdf):
    (x, y) = xy
    ((f0f, g0f), (f1f, g1f)) = bcf
    ((df0_dyf, dg0_dxf), (df1_dyf, dg1_dxf)) = bcdf
    dA_dy = (
        (1 - x)*df0_dyf(y) + x*df1_dyf(y)
        - (g0f(x) - (1 - x)*g0f(0) - x*g0f(1))
        + (g1f(x) - (1 - x)*g1f(0) + x*g1f(1))
    )
    return dA_dy

delAf = (dA_dxf, dA_dyf)

def d2A_dxdxf(xy, bcf, bcdf, bcd2f):
    (x, y) = xy
    ((f0f, g0f), (f1f, g1f)) = bcf
    ((df0_dyf, dg0_dxf), (df1_dyf, dg1_dxf)) = bcdf
    ((d2f0_dy2f, d2g0_dx2f), (d2f1_dy2f, d2g1_dx2f)) = bcd2f
    return (1 - y)*d2g0_dx2f(x) + y*d2g1_dx2f(x)

def d2A_dxdyf(xy, bcf, bcdf, bcd2f):
    (x, y) = xy
    ((f0f, g0f), (f1f, g1f)) = bcf
    ((df0_dyf, dg0_dxf), (df1_dyf, dg1_dxf)) = bcdf
    ((d2f0_dy2f, d2g0_dx2f), (d2f1_dy2f, d2g1_dx2f)) = bcd2f
    return (
        -df0_dyf(y) + df1_dyf(y) - dg0_dxf(x) + dg1_dxf(x) -
        g0f(0) + g0f(1) + g1f(0) - g1f(1)
    )

def d2A_dydxf(xy, bcf, bcdf, bcd2f):
    (x, y) = xy
    ((f0f, g0f), (f1f, g1f)) = bcf
    ((df0_dyf, dg0_dxf), (df1_dyf, dg1_dxf)) = bcdf
    ((d2f0_dy2f, d2g0_dx2f), (d2f1_dy2f, d2g1_dx2f)) = bcd2f
    return (
        -df0_dyf(y) + df1_dyf(y) - dg0_dxf(x) + dg1_dxf(x) -
        g0f(0) + g0f(1) + g1f(0) - g1f(1)
    )

def d2A_dydyf(xy, bcf, bcdf, bcd2f):
    (x, y) = xy
    ((f0f, g0f), (f1f, g1f)) = bcf
    ((df0_dyf, dg0_dxf), (df1_dyf, dg1_dxf)) = bcdf
    ((d2f0_dy2f, d2g0_dx2f), (d2f1_dy2f, d2g1_dx2f)) = bcd2f
    return (1 - x)*d2f0_dy2f(y) + y*d2f1_dy2f(y)

deldelAf = ((d2A_dxdxf, d2A_dxdyf),
            (d2A_dydxf, d2A_dydyf))

def Pf(xy):
    (x, y) = xy
    P = x*(1 - x)*y*(1 - y)
    return P

def dP_dxf(xy):
    (x, y) = xy
    dP_dx = (1 - 2*x)*y*(1 - y)
    return dP_dx

def dP_dyf(xy):
    (x, y) = xy
    dP_dy = x*(1 - x)*(1 - 2*y)
    return dP_dy

delPf = (dP_dxf, dP_dyf)

def d2P_dxdxf(xy):
    (x, y) = xy
    return -2*y*(1 - y)

def d2P_dxdyf(xy):
    (x, y) = xy
    return (1 - 2*x)*(1 - 2*y)

def d2P_dydxf(xy):
    (x, y) = xy
    return (1 - 2*x)*(1 - 2*y)

def d2P_dydyf(xy):
    (x, y) = xy
    return -2*y*(1 - y)

deldelPf = ((d2P_dxdxf, d2P_dxdyf),
            (d2P_dydxf, d2P_dydyf))

# Define the trial solution.
def Ytf(xy, N, bcf):
    A = Af(xy, bcf)
    P = Pf(xy)
    Yt = A + P*N
    return Yt

#********************************************************************************

# Function to solve a 2-variable, 2nd-order PDE BVP with Dirichlet BC,
# using a single-hidden-layer feedforward neural network with 2 input
# nodes and a single output node.

def nnpde2bvp(
        Gf,                            # 2-variable, 2nd-order PDE BVP
        dG_dYf,                        # Partial of G wrt Y
        dG_ddelYf,                     # Partials of G wrt del Y
        dG_ddeldelYf,                  # Partials of G wrt del del Y
        bcf,                           # BC functions
        bcdf,                          # BC function derivatives
        bcd2f,                         # BC function 2nd derivatives
        x,                             # Training points as pairs
        nhid = default_nhid,           # Node count in hidden layer
        maxepochs = default_maxepochs, # Max training epochs
        eta = default_eta,             # Learning rate
        debug = default_debug,
        verbose = default_verbose
):
    if debug: print('Gf =', Gf)
    if debug: print('dG_dYf =', dG_dYf)
    if debug: print('dG_ddelYf =', dG_ddelYf)
    if debug: print('dG_ddeldelYf =', dG_ddeldelYf)
    if debug: print('bcf =', bcf)
    if debug: print('bcdf =', bcdf)
    if debug: print('bcd2f =', bcd2f)
    if debug: print('x =', x)
    if debug: print('nhid =', nhid)
    if debug: print('maxepochs =', maxepochs)
    if debug: print('eta =', eta)
    if debug: print('debug =', debug)
    if debug: print('verbose =', verbose)

    # Sanity-check arguments. UPDATE THESE CHECKS!
    assert Gf
    assert dG_dYf
    assert len(dG_ddelYf) > 0
    ndim = len(dG_ddelYf)
    assert len(dG_ddeldelYf) == ndim
    for j in range(ndim):
        assert len(dG_ddeldelYf[j]) == ndim
    assert len(bcf) == ndim
    for j in range(ndim):
        assert len(bcf[j]) == 2  # 0 and 1
    assert len(bcdf) == ndim
    for j in range(ndim):
        assert len(bcdf[j]) == 2  # 0 and 1
    assert len(bcd2f) == ndim
    for j in range(ndim):
        assert len(bcd2f[j]) == 2  # 0 and 1

    # <HACK> ndim must be 2!
    assert ndim == 2
    # </HACK>

    #----------------------------------------------------------------------------

    # Determine the number of training points.
    n = len(x)
    if debug: print('n =', n)

    # Change notation for convenience.
    m = ndim
    if debug: print('m =', m)  # Will always be 2 in this code.
    H = nhid
    if debug: print('H =', H)

    #----------------------------------------------------------------------------

    # Create the network.

    # Create an array to hold the weights connecting the 2 input nodes
    # to the hidden nodes. The weights are initialized with a uniform
    # random distribution.
    w = np.random.uniform(w_min, w_max, (m, H))
    if debug: print('w =', w)

    # Create an array to hold the biases for the hidden nodes. The
    # biases are initialized with a uniform random distribution.
    u = np.random.uniform(u_min, u_max, H)
    if debug: print('u =', u)

    # Create an array to hold the weights connecting the hidden nodes
    # to the output node. The weights are initialized with a uniform
    # random distribution.
    v = np.random.uniform(v_min, v_max, H)
    if debug: print('v =', v)

    #----------------------------------------------------------------------------

    # 0 <= i < n (n = # of sample points)
    # 0 <= j < m (m = # independent variables)
    # 0 <= k < H (H = # hidden nodes)

    # Run the network.
    for epoch in range(maxepochs):
        if debug: print('Starting epoch %d.' % epoch)

        # Compute the net input, the sigmoid function and its derivatives,
        # for each hidden node and each training point.
        z =  np.zeros((n, H))
        s =  np.zeros((n, H))
        s1 = np.zeros((n, H))
        s2 = np.zeros((n, H))
        s3 = np.zeros((n, H))
        for i in range(n):
            for k in range(H):
                z[i,k] = u[k]
                for j in range(m):
                    z[i,k] += w[j,k]*x[i,j]
                s[i,k] = sigma(z[i,k])
                s1[i,k] = dsigma_dz(z[i,k])
                s2[i,k] = d2sigma_dz2(z[i,k])
                s3[i,k] = d3sigma_dz3(z[i,k])
        if debug: print('z =', z)
        if debug: print('s =', s)
        if debug: print('s1 =', s1)
        if debug: print('s2 =', s2)
        if debug: print('s3 =', s3)

        #------------------------------------------------------------------------

        # Compute the network output and its derivatives, for each
        # training point.
        N = np.zeros(n)
        dN_dx = np.zeros((n, m))
        dN_dv = np.zeros((n, H))
        dN_du = np.zeros((n, H))
        dN_dw = np.zeros((n, m, H))
        d2N_dvdx = np.zeros((n, m, H))
        d2N_dudx = np.zeros((n, m, H))
        d2N_dwdx = np.zeros((n, m, H))
        d2N_dxdy = np.zeros((n, m, m))
        d3N_dvdxdy = np.zeros((n, m, m, H))
        d3N_dudxdy = np.zeros((n, m, m, H))
        d3N_dwdxdy = np.zeros((n, m, m, H))
        for i in range(n):
            for k in range(H):
                N[i] += v[k]*s[i,k]
                dN_dv[i,k] = s[i,k]
                dN_du[i,k] = v[k]*s1[i,k]
                for j in range(m):
                    dN_dx[i,j] += v[k]*s1[i,k]*w[j,k]
                    dN_dw[i,j,k] = v[k]*s1[i,k]*x[i,j]
                    d2N_dvdx[i,j,k] = s1[i,k]*w[j,k]
                    d2N_dudx[i,j,k] = v[k]*s2[i,k]*w[j,k]
                    d2N_dwdx[i,j,k] = v[k]*(s1[i,k] + s2[i,k]*w[j,k]*x[i,j])
                    for jj in range(m):
                        d2N_dxdy[i,j,jj] += v[k]*s2[i,k]*w[jj,k]*w[j,k]
                        d3N_dvdxdy[i,j,jj,k] = s2[i,k]*w[j,k]*w[jj,k]
                        d3N_dudxdy[i,j,jj,k] = v[k]*s3[i,k]*w[j,k]*w[jj,k]
                        d3N_dwdxdy[i,j,jj,k] = (
                            v[k]*s2[i,k]*(w[j,k] + w[jj,k]) +
                            v[k]*s3[i,k]*w[j,k]*w[jj,k]*x[i,j]
                        )
        if debug: print('N =', N)
        if debug: print('dN_dx =', dN_dx)
        if debug: print('dN_dv =', dN_dv)
        if debug: print('dN_du =', dN_du)
        if debug: print('dN_dw =', dN_dw)
        if debug: print('d2N_dvdx =', d2N_dvdx)
        if debug: print('d2N_dudx =', d2N_dudx)
        if debug: print('d2N_dwdx =', d2N_dwdx)
        if debug: print('d2N_dxdy =', d2N_dxdy)
        if debug: print('d3N_dvdxdy =', d3N_dvdxdy)
        if debug: print('d3N_dudxdy =', d3N_dudxdy)
        if debug: print('d3N_dwdxdy =', d3N_dwdxdy)

        #------------------------------------------------------------------------

        # Compute the value of the trial solution and its derivatives,
        # for each training point.
        A = np.zeros(n)
        dA_dx = np.zeros((n, m))
        d2A_dxdy = np.zeros((n, m, m))
        P = np.zeros(n)
        dP_dx = np.zeros((n, m))
        d2P_dxdy = np.zeros((n, m, m))
        Yt = np.zeros(n)
        dYt_dx = np.zeros((n, m))
        dYt_dv = np.zeros((n, H))
        dYt_du = np.zeros((n, H))
        dYt_dw = np.zeros((n, m, H))
        d2Yt_dvdx = np.zeros((n, m, H))
        d2Yt_dudx = np.zeros((n, m, H))
        d2Yt_dwdx = np.zeros((n, m, H))
        d2Yt_dxdy = np.zeros((n, m, m))
        d3Yt_dvdxdy = np.zeros((n, m, m, H))
        d3Yt_dudxdy = np.zeros((n, m, m, H))
        d3Yt_dwdxdy = np.zeros((n, m, m, H))
        for i in range(n):
            A[i] = Af(x[i], bcf)
            P[i] = Pf(x[i])
            Yt[i] = Ytf(x[i], N[i], bcf)
            for j in range(m):
                dA_dx[i,j] = delAf[j](x[i], bcf, bcdf)
                dP_dx[i,j] = delPf[j](x[i])
                dYt_dx[i,j] = dA_dx[i,j] + P[i]*dN_dx[i,j] + dP_dx[i,j]*N[i]
                for jj in range(m):
                    d2A_dxdy[i,j,jj] = deldelAf[j][jj](x[i], bcf, bcdf, bcd2f)
                    d2P_dxdy[i,j,jj] = deldelPf[j][jj](x[i])
                    d2Yt_dxdy[i,j,jj] = (
                        d2A_dxdy[i,j,jj] +
                        P[i]*d2N_dxdy[i,j,jj] +
                        dP_dx[i,jj]*dN_dx[i,j] +
                        dP_dx[i,j]*dN_dx[i,jj] +
                        d2P_dxdy[i,j,jj]*N[i]
                    )
            for k in range(H):
                dYt_dv[i,k] = P[i]*dN_dv[i,k]
                dYt_du[i,k] = P[i]*dN_du[i,k]
                for j in range(m):
                    dYt_dw[i,j,k] = P[i]*dN_dw[i,j,k]
                    d2Yt_dvdx[i,j,k] = (
                        P[i]*d2N_dvdx[i,j,k] + dP_dx[i,j]*dN_dv[i,k]
                    )
                    d2Yt_dudx[i,j,k] = (
                        P[i]*d2N_dudx[i,j,k] + dP_dx[i,j]*dN_du[i,k]
                    )
                    d2Yt_dwdx[i,j,k] = (
                        P[i]*d2N_dwdx[i,j,k] + dP_dx[i,j]*dN_dw[i,j,k]
                    )
                    for jj in range(m):
                        d3Yt_dvdxdy[i,j,jj,k] = (
                            P[i]*d3N_dvdxdy[i,j,jj,k] +
                            dP_dx[i,jj]*d2N_dvdx[i,j,k] +
                            dP_dx[i,jj]*d2N_dvdx[i,jj,k] +
                            d2P_dxdy[i,j,jj]*dN_dv[i,k]
                        )
                        d3Yt_dudxdy[i,j,jj,k] = (
                            P[i]*d3N_dudxdy[i,j,jj,k] +
                            dP_dx[i,jj]*d2N_dudx[i,j,k] +
                            dP_dx[i,jj]*d2N_dudx[i,jj,k] +
                            d2P_dxdy[i,j,jj]*dN_du[i,k]
                        )
                        d3Yt_dwdxdy[i,j,jj,k] = ( # Is this right?
                            P[i]*d3N_dwdxdy[i,j,jj,k] +
                            dP_dx[i,jj]*d2N_dwdx[i,j,k] +
                            dP_dx[i,jj]*d2N_dwdx[i,jj,k] +
                            d2P_dxdy[i,j,jj]*dN_dw[i,j,k]
                        )
        if debug: print('A =', A)
        if debug: print('dA_dx =', dA_dx)
        if debug: print('d2A_dxdy =', d2A_dxdy)
        if debug: print('P =', P)
        if debug: print('dP_dx =', dP_dx)
        if debug: print('d2P_dxdy =', d2P_dxdy)
        if debug: print('Yt =', Yt)
        if debug: print('dYt_dx =', dYt_dx)
        if debug: print('dYt_dv =', dYt_dv)
        if debug: print('dYt_du =', dYt_du)
        if debug: print('dYt_dw =', dYt_dw)
        if debug: print('d2Yt_dvdx =', d2Yt_dvdx)
        if debug: print('d2Yt_dudx =', d2Yt_dudx)
        if debug: print('d2Yt_dwdx =', d2Yt_dwdx)
        if debug: print('d2Yt_dxdy =', d2Yt_dxdy)
        if debug: print('d3Yt_dvdxdy =', d3Yt_dvdxdy)
        if debug: print('d3Yt_dudxdy =', d3Yt_dudxdy)
        if debug: print('d3Yt_dwdxdy =', d3Yt_dwdxdy)

        #------------------------------------------------------------------------

        # Compute the value of the original differential equation
        # for each training point, and its derivatives.
        G = np.zeros(n)
        dG_dYt = np.zeros(n)
        dG_ddelYt = np.zeros((n, m))
        dG_ddeldelYt = np.zeros((n, m, m))
        dG_dv = np.zeros((n, H))
        dG_du = np.zeros((n, H))
        dG_dw = np.zeros((n, m, H))
        for i in range(n):
            G[i] = Gf(x[i], Yt[i], dYt_dx[i], d2Yt_dxdy[i])
            dG_dYt[i] = dG_dYf(x[i], Yt[i], dYt_dx[i], d2Yt_dxdy[i])
            for j in range(m):
                dG_ddelYt[i,j] = dG_ddelYf[j](x[i], Yt[i],
                                              dYt_dx[i], d2Yt_dxdy[i])
                for jj in range(m):
                    dG_ddeldelYt[i,j,jj] = dG_ddeldelYf[j][jj](x[i], Yt[i],
                                                               dYt_dx[i],
                                                               d2Yt_dxdy[i])
            for k in range(H):
                dG_dv[i,k] = dG_dYt[i]*dYt_dv[i,k]
                dG_du[i,k] = dG_dYt[i]*dYt_du[i,k]
                dG_dw[i,j,k] = dG_dYt[i]*dYt_dw[i,j,k]
                for j in range(m):
                    dG_dv[i,k] += dG_ddelYt[i,j]*d2Yt_dvdx[i,j,k]
                    dG_du[i,k] += dG_ddelYt[i,j]*d2Yt_dudx[i,j,k]
                    dG_dw[i,j,k] += dG_ddelYt[i,j]*d2Yt_dwdx[i,j,k]
                    for jj in range(m):
                        dG_dv[i,k] += dG_ddeldelYt[i,j,jj]*d3Yt_dvdxdy[i,j,jj,k]
                        dG_du[i,k] += dG_ddeldelYt[i,j,jj]*d3Yt_dudxdy[i,j,jj,k]
                        dG_dw[i,j,k] += (
                            dG_ddeldelYt[i,j,jj]*d3Yt_dwdxdy[i,j,jj,k]
                        )
        if debug: print('G =', G)
        if debug: print('dG_dYt =', dG_dYt)
        if debug: print('dG_ddelYt =', dG_ddelYt)
        if debug: print('dG_ddeldelYt =', dG_ddeldelYt)
        if debug: print('dG_dv =', dG_dv)
        if debug: print('dG_du =', dG_du)
        if debug: print('dG_dw =', dG_dw)

        #------------------------------------------------------------------------

        # Compute the error function for this pass.
        E = sum(G**2)
        if debug: print('E =', E)

        # Compute the partial derivatives of the error with respect to the
        # network parameters.
        dE_dv = np.zeros(H)
        dE_du = np.zeros(H)
        dE_dw = np.zeros((m, H))
        for k in range(H):
            for i in range(n):
                dE_dv[k] += 2*G[i]*dG_dv[i,k]
                dE_du[k] += 2*G[i]*dG_du[i,k]
            for j in range(m):
                for i in range(n):
                    dE_dw[j,k] += 2*G[i]*dG_dw[i,j,k]
        if debug: print('dE_dv =', dE_dv)
        if debug: print('dE_du =', dE_du)
        if debug: print('dE_dw =', dE_dw)

        #------------------------------------------------------------------------

        # Compute the new values of the network parameters.
        v_new = np.zeros(H)
        u_new = np.zeros(H)
        w_new = np.zeros((m, H))
        for k in range(H):
            v_new[k] = v[k] - eta*dE_dv[k]
            u_new[k] = u[k] - eta*dE_du[k]
            for j in range(m):
                w_new[j,k] = w[j,k] - eta*dE_dw[j,k]
        if debug: print('v_new =', v_new)
        if debug: print('u_new =', u_new)
        if debug: print('w_new =', w_new)

        if verbose: print(epoch, sqrt(E/n))

        # Save the new weights and biases.
        v = v_new
        u = u_new
        w = w_new

    # Return the final solution.
    return (Yt, dYt_dx, d2Yt_dxdy)

#--------------------------------------------------------------------------------

# Begin main program.

if __name__ == '__main__':

    # Create the argument parser.
    parser = argparse.ArgumentParser(
        description = 'Solve a 2-variable, 2nd-order PDE BVP with a neural net',
        formatter_class = argparse.ArgumentDefaultsHelpFormatter,
        epilog = 'Experiment with the settings to find what works.'
    )
    # print('parser =', parser)

    # Add command-line options.
    parser.add_argument('--debug', '-d',
                        action = 'store_true',
                        default = default_debug,
                        help = 'Produce debugging output')
    parser.add_argument('--eta', type = float,
                        default = default_eta,
                        help = 'Learning rate for parameter adjustment')
    parser.add_argument('--maxepochs', type = int,
                        default = default_maxepochs,
                        help = 'Maximum number of training epochs')
    parser.add_argument('--nhid', type = int,
                        default = default_nhid,
                        help = 'Number of hidden-layer nodes to use')
    parser.add_argument('--ntrain', type = int,
                        default = default_ntrain,
                        help = 'Number of evenly-spaced training points to use along each dimension')
    parser.add_argument('--pde', type = str,
                        default = default_pde,
                        help = 'Name of module containing PDE to solve')
    parser.add_argument('--seed', type = int,
                        default = default_seed,
                        help = 'Random number generator seed')
    parser.add_argument('--verbose', '-v',
                        action = 'store_true',
                        default = default_verbose,
                        help = 'Produce verbose output')
    parser.add_argument('--version', action = 'version',
                        version = '%(prog)s 0.0')

    # Fetch and process the arguments from the command line.
    args = parser.parse_args()
    if args.debug: print('args =', args)

    # Extract the processed options.
    debug = args.debug
    eta = args.eta
    maxepochs = args.maxepochs
    nhid = args.nhid
    ntrain = args.ntrain
    pde = args.pde
    seed = args.seed
    verbose = args.verbose
    if debug: print('debug =', debug)
    if debug: print('eta =', eta)
    if debug: print('maxepochs =', maxepochs)
    if debug: print('nhid =', nhid)
    if debug: print('ntrain =', ntrain)
    if debug: print('pde =', pde)
    if debug: print('seed =', seed)
    if debug: print('verbose =', verbose)

    # Perform basic sanity checks on the command-line options.
    assert eta > 0
    assert maxepochs > 0
    assert nhid > 0
    assert ntrain > 0
    assert pde
    assert seed >= 0

    #----------------------------------------------------------------------------

    # Initialize the random number generator to ensure repeatable results.
    if verbose: print('Seeding random number generator with value %d.' % seed)
    np.random.seed(seed)

    # Import the specified PDE module.
    if verbose:
        print('Importing PDE module %s.' % pde)
    pdemod = import_module(pde)

    # Validate the module contents.
    assert pdemod.Gf
    assert pdemod.dG_dYf
    assert len(pdemod.dG_ddelYf) > 0
    ndim = len(pdemod.dG_ddelYf)
    assert len(pdemod.dG_ddeldelYf) == ndim
    for j in range(ndim):
        assert len(pdemod.dG_ddeldelYf[j]) == ndim
    assert len(pdemod.bcf) == ndim
    for j in range(ndim):
        assert len(pdemod.bcf[j]) == 2  # 0 and 1
    assert len(pdemod.bcdf) == ndim
    for j in range(ndim):
        assert len(pdemod.bcdf[j]) == 2  # 0 and 1
    assert len(pdemod.bcd2f) == ndim
    for j in range(ndim):
        assert len(pdemod.bcd2f[j]) == 2  # 0 and 1
    assert pdemod.Yaf
    assert len(pdemod.delYaf) == ndim
    assert len(pdemod.deldelYaf) == ndim
    for j in range(ndim):
        assert len(pdemod.deldelYaf[j]) == ndim

    # <HACK> ndim must be 2!
    assert ndim == 2
    # </HACK>

    # Create the array of evenly-spaced training points. Use the same
    # values of the training points for each dimension.
    if verbose: print('Computing training points in [[0,1],[0,1]].')
    xt = np.linspace(0, 1, ntrain)
    if debug: print('xt =', xt)
    yt = xt
    if debug: print('yt =', yt)

    # Compute the total number of training points, replacing ntrain.
    nxt = len(xt)
    if debug: print('nxt =', nxt)
    nyt = len(yt)
    if debug: print('nyt =', nyt)
    ntrain = nxt*nyt
    if debug: print('ntrain =', ntrain)

    # Create the list of training points.
    #((x0,y0),(x1,y0),(x2,y0),...
    # (x0,y1),(x1,y1),(x2,y1),...
    x = np.zeros((ntrain, ndim))
    for j in range(nyt):
        for i in range(nxt):
            k = j*nxt + i
            x[k,0] = xt[i]
            x[k,1] = yt[j]
    if debug: print('x =', x)

    #----------------------------------------------------------------------------

    # Compute the 2nd-order PDE solution using the neural network.
    (Yt, delYt, deldelYt) = nnpde2bvp(
        pdemod.Gf,             # 2-variable, 2nd-order PDE BVP to solve
        pdemod.dG_dYf,         # Partial of G wrt Y
        pdemod.dG_ddelYf,      # Partials of G wrt del Y (wrt gradient)
        pdemod.dG_ddeldelYf,   # Partials of G wrt del del Y (wrt Hessian)
        pdemod.bcf,            # BC functions
        pdemod.bcdf,           # BC function derivatives
        pdemod.bcd2f,          # BC function 2nd derivatives
        x,                     # Training points as pairs
        nhid = nhid,           # Node count in hidden layer
        maxepochs = maxepochs, # Max training epochs
        eta = eta,             # Learning rate
        debug = debug,
        verbose = verbose
    )

    #----------------------------------------------------------------------------

    # Compute the analytical solution at the training points.
    Ya = np.zeros(ntrain)
    for i in range(ntrain):
        Ya[i] = pdemod.Yaf(x[i])
    if debug: print('Ya =', Ya)

    # Compute the analytical gradient at the training points.
    delYa = np.zeros((ntrain, len(x[1])))
    for i in range(ntrain):
        for j in range(ndim):
            delYa[i,j] = pdemod.delYaf[j](x[i])
    if debug: print('delYa =', delYa)

    # Compute the analytical Hessian at the training points.
    deldelYa = np.zeros((ntrain, len(x[1]), len(x[1])))
    for i in range(ntrain):
        for j in range(ndim):
            for jj in range(ndim):
                deldelYa[i,j, jj] = pdemod.deldelYaf[j][jj](x[i])
    if debug: print('deldelYa =', deldelYa)

    # Compute the RMSE of the trial solution.
    Yerr = Yt - Ya
    if debug: print('Yerr =', Yerr)
    rmseY = sqrt(sum(Yerr**2)/ntrain)
    if debug: print('rmseY =', rmseY)

    # Compute the RMSEs of the gradient.
    delYerr = delYt - delYa
    if debug: print('delYerr =', delYerr)
    rmsedelY = np.zeros(ndim)
    e2sum = np.zeros(ndim)
    for j in range(ndim):
        for i in range(ntrain):
            e2sum[j] += delYerr[i,j]**2
        rmsedelY[j] = sqrt(e2sum[j]/ntrain)
    if debug: print('rmsedelY =', rmsedelY)

    # Compute the RMSEs of the Hessian.
    # del2Yerr = del2Yt - del2Ya
    # if debug: print('del2Yerr =', del2Yerr)
    # rmsedel2Y = np.zeros(ndim)
    # e2sum = np.zeros(ndim)
    # for j in range(ndim):
    #     for i in range(ntrain):
    #         e2sum[j] += del2Yerr[i,j]**2
    #     rmsedel2Y[j] = sqrt(e2sum[j]/ntrain)
    # if debug: print('rmsedel2Y =', rmsedel2Y)

    # Print the report.
    print('    x        y       Ya       Yt     dYa_dx   dYt_dx   dYa_dy   dYt_dy  d2Ya_dxdx d2Yt_dxdx d2Ya_dxdy d2Yt_dxdy d2Ya_dydx d2Ya_dydy')
    for i in range(len(Ya)):
    #     print('%.6f %.6f|%.6f %.6f|%.6f %.6f|%.6f %.6f|%.6f %.6f|%.6f %.6f' %
    #           (x[i,0], x[i,1],
    #            Ya[i], Yt[i],
    #            delYa[i,0], delYt[i,0], delYa[i,1], delYt[i,1],
    #            del2Ya[i,0], del2Yt[i,0], del2Ya[i,1], del2Yt[i,1]
    #           )
    # )
        print('%.6f %.6f|%.6f %.6f|%.6f %.6f|%.6f %.6f|%.6f %.6f|%.6f %.6f|%.6f %.6f|%.6f %.6f' %
              (x[i,0], x[i,1],
               Ya[i], Yt[i],
               delYa[i,0], delYt[i,0],
               delYa[i,1], delYt[i,1],
               deldelYa[i,0,0], deldelYt[i,0,0],
               deldelYa[i,0,1], deldelYt[i,0,1],
               deldelYa[i,1,0], deldelYt[i,1,0],
               deldelYa[i,1,1], deldelYt[i,1,1]
              ))
    # print('RMSE                       %f          %f          %f          %f          %f' %
    #       (rmseY, rmsedelY[0], rmsedelY[1], rmsedel2Y[0], rmsedel2Y[1]))
    print('RMSE                       %f          %f          %f' %
          (rmseY, rmsedelY[0], rmsedelY[1])
    )
