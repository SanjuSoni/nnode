"""
NNPDE2DIFF1D - Class to solve 1-D diffusion problems using a neural network

This module provides the functionality to solve 1-D diffusion problems using
a neural network.

Example:
    Create an empty NNPDE2DIFF1D object.
        net = NNPDE2DIFF1D()
    Create an NNPDE2DIFF1D object for a PDE2DIFF1D object.
        net = NNPDE2DIFF1D(pde2diff1d_obj)
    Create an NNPDE2DIFF1D object for a PDE2DIFF1D object, with 20 hidden
              nodes.
        net = NNPDE2DIFF1D(pde2diff1d_obj, nhid=20)

Attributes:
    None

Methods:
    train
    run
    run_gradient
    run_hessian

Todo:
    * Expand base functionality.
"""


from math import sqrt
import numpy as np
from scipy.optimize import minimize

from kdelta import kdelta
from pde2diff1d_orig import PDE2DIFF1D
from sigma import sigma, dsigma_dz, d2sigma_dz2, d3sigma_dz3
from slffnn import SLFFNN


# Default values for method parameters
DEFAULT_DEBUG = False
DEFAULT_ETA = 0.01
DEFAULT_MAXEPOCHS = 1000
DEFAULT_NHID = 10
DEFAULT_TRAINALG = 'delta'
DEFAULT_UMAX = 1
DEFAULT_UMIN = -1
DEFAULT_VERBOSE = False
DEFAULT_VMAX = 1
DEFAULT_VMIN = -1
DEFAULT_WMAX = 1
DEFAULT_WMIN = -1
DEFAULT_OPTS = {
    'debug':     DEFAULT_DEBUG,
    'eta':       DEFAULT_ETA,
    'maxepochs': DEFAULT_MAXEPOCHS,
    'nhid':      DEFAULT_NHID,
    'umax':      DEFAULT_UMAX,
    'umin':      DEFAULT_UMIN,
    'verbose':   DEFAULT_VERBOSE,
    'vmax':      DEFAULT_VMAX,
    'vmin':      DEFAULT_VMIN,
    'wmax':      DEFAULT_WMAX,
    'wmin':      DEFAULT_WMIN
    }


# Vectorize sigma functions for speed.
sigma_v = np.vectorize(sigma)
dsigma_dz_v = np.vectorize(dsigma_dz)
d2sigma_dz2_v = np.vectorize(d2sigma_dz2)
d3sigma_dz3_v = np.vectorize(d3sigma_dz3)


class NNPDE2DIFF1D(SLFFNN):
    """Solve a 1-D diffusion problem with a neural network"""


    # Public methods


    def train(self, x, trainalg=DEFAULT_TRAINALG, opts=DEFAULT_OPTS,
              options=None):
        """Train the network to solve a 1-D diffusion problem"""
        my_opts = dict(DEFAULT_OPTS)
        my_opts.update(opts)

        if trainalg == 'delta':
            self.__train_delta(x, opts=my_opts)
        elif trainalg in ('Nelder-Mead', 'Powell', 'CG', 'BFGS', 'Newton-CG'):
            self.__train_minimize(x, trainalg, opts=my_opts, options=options)
        else:
            print('ERROR: Invalid training algorithm (%s)!' % trainalg)
            exit(1)

    def run(self, x):
        """Compute the trained solution."""

        # Fetch the number n of input points at which to calculate the
        # output, and the number m of components of each point.
        n = len(x)
        m = len(x[0])

        # Fetch the number of hidden nodes in the neural network.
        H = len(self.w[0])

        # Get references to the network parameters for convenience.
        w = self.w
        u = self.u
        v = self.v

        # Compute the activation for each input point and hidden node.
        z = np.dot(x, w) + u

        # Compute the sigma function for each input point and hidden node.
        s = sigma_v(z)

        # Compute the network output for each input point.
        N = np.dot(s, v)

        # Compute the value of the trial function for each input point.
        Yt = np.zeros(n)
        for i in range(n):
            Yt[i] = self.__Ytf(x[i], N[i])

        # Return the trial function values for each input point.
        return Yt

    def run_debug(self, x):
        """Compute the trained solution (debug version)."""

        # Fetch the number n of input points at which to calculate the
        # output, and the number m of components of each point.
        n = len(x)
        m = len(x[0])

        # Fetch the number of hidden nodes in the neural network.
        H = len(self.w[0])

        # Get references to the network parameters for convenience.
        w = self.w
        u = self.u
        v = self.v

        # Compute the activation for each input point and hidden node.
        z = np.zeros((n, H))
        for i in range(n):
            for k in range(H):
                z[i, k] = u[k]
                for j in range(m):
                    z[i, k] += w[j, k]*x[i, j]

        # Compute the sigma function for each input point and hidden node.
        s = np.zeros((n, H))
        for i in range(n):
            for k in range(H):
                s[i, k] = sigma(z[i, k])

        # Compute the network output for each input point.
        N = np.zeros(n)
        for i in range(n):
            for k in range(H):
                N[i] += v[k]*s[i, k]

        # Compute the value of the trial function for each input point.
        Yt = np.zeros(n)
        for i in range(n):
            Yt[i] = self.__Ytf(x[i], N[i])

        # Return the trial function values for each input point.
        return Yt

    def run_gradient(self, x):
        """Compute the trained gradient."""

        # Fetch the number n of input points at which to calculate the
        # output, and the number m of components of each point.
        n = len(x)
        m = len(x[0])

        # Fetch the number of hidden nodes in the neural network.
        H = len(self.w[0])

        # Get references to the network parameters for convenience.
        w = self.w
        u = self.u
        v = self.v

        # Compute the activation for each input point and hidden node.
        z = np.dot(x, w) + u

        # Compute the sigma function for each input point and hidden node.
        s = sigma_v(z)

        # Compute the sigma function 1st derivative for each input point
        # and hidden node.
        s1 = dsigma_dz_v(z)

        # Compute the network output for each input point.
        N = np.dot(s, v)

        # Compute the network output gradient for each input point.
        delN = np.dot(s1, (v*w).T)

        # Compute the gradient of the booundary condition function for each
        # input point.
        delA = np.zeros((n, m))
        for i in range(n):
            for j in range(m):
                delA[i, j] = self.delAf[j](x[i])

        # Compute the network coefficient function for each input point.
        P = np.zeros(n)
        for i in range(n):
            P[i] = self.__Pf(x[i])

        # Compute the gradient of the network coefficient function for each
        # input point.
        delP = np.zeros((n, m))
        for i in range(n):
            for j in range(m):
                delP[i, j] = self.delPf[j](x[i])

        # Compute the gradient of the trial solution for each input point.
        delYt = np.zeros((n, m))
        for i in range(n):
            for j in range(m):
                delYt[i, j] = delA[i, j] + P[i]*delN[i, j] + \
                    delP[i, j]*N[i]

        return delYt

    def run_gradient_debug(self, x):
        """Compute the trained gradient (debug version)."""

        # Fetch the number n of input points at which to calculate the
        # output, and the number m of components of each point.
        n = len(x)
        m = len(x[0])

        # Fetch the number of hidden nodes in the neural network.
        H = len(self.w[0])

        # Get references to the network parameters for convenience.
        w = self.w
        u = self.u
        v = self.v

        z = np.zeros((n, H))
        for i in range(n):
            for k in range(H):
                z[i, k] = u[k]
                for j in range(m):
                    z[i, k] += w[j, k]*x[i, j]

        s = np.zeros((n, H))
        for i in range(n):
            for k in range(H):
                s[i, k] = sigma(z[i, k])

        s1 = np.zeros((n, H))
        for i in range(n):
            for k in range(H):
                s1[i, k] = dsigma_dz(z[i, k])

        N = np.zeros(n)
        for i in range(n):
            for k in range(H):
                N[i] += v[k]*s[i, k]

        delN = np.zeros((n, m))
        for i in range(n):
            for j in range(m):
                for k in range(H):
                    delN[i, j] += v[k]*s1[i, k]*w[j, k]

        delA = np.zeros((n, m))
        for i in range(n):
            for j in range(m):
                delA[i, j] = self.delAf[j](x[i])

        P = np.zeros(n)
        for i in range(n):
            P[i] = self.__Pf(x[i])

        delP = np.zeros((n, m))
        for i in range(n):
            for j in range(m):
                delP[i, j] = self.delPf[j](x[i])

        delYt = np.zeros((n, m))
        for i in range(n):
            for j in range(m):
                delYt[i, j] = delA[i, j] + P[i]*delN[i, j] + \
                    delP[i, j]*N[i]

        return delYt

    def run_hessian(self, x):
        """Compute the trained Hessian."""

        # Fetch the number n of input points at which to calculate the
        # output, and the number m of components of each point.
        n = len(x)
        m = len(x[0])

        # Fetch the number of hidden nodes in the neural network.
        H = len(self.w[0])

        # Get references to the network parameters for convenience.
        w = self.w
        u = self.u
        v = self.v

        # Compute the activation for each input point and hidden node.
        z = np.dot(x, w) + u

        # Compute the sigma function for each input point and hidden node.
        s = sigma_v(z)

        # Compute the sigma function 1st derivative for each input point
        # and hidden node.
        s1 = dsigma_dz_v(z)

        # Compute the sigma function 2nd derivative for each input point
        # and hidden node.
        s2 = d2sigma_dz2_v(z)

        # Compute the network output for each input point.
        N = np.dot(s, v)

        # Compute the network output gradient for each input point.
        delN = np.dot(s1, (v*w).T)

        # Compute the network output Hessian for each input point.
        deldelN = np.zeros((n, m, m))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    deldelN[i, j, jj] = np.dot(v, s2[i]*w[j]*w[jj])

        # Compute the Hessian of the boundary condition function
        # for each input point.
        deldelA = np.zeros((n, m, m))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    deldelA[i, j, jj] = self.deldelAf[j][jj](x[i])

        # Compute the network coefficient function for each input point.
        P = np.zeros(n)
        for i in range(n):
            P[i] = self.__Pf(x[i])

        # Compute the gradient of the network coefficient function for each
        # input point.
        delP = np.zeros((n, m))
        for i in range(n):
            for j in range(m):
                delP[i, j] = self.delPf[j](x[i])

        # Compute the Hessian of the network coefficient function for each
        # input point.
        deldelP = np.zeros((n, m, m))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    deldelP[i, j, jj] = self.deldelPf[j][jj](x[i])

        # Compute the Hessian of the trial solution for each
        # input point.
        deldelYt = np.zeros((n, m, m))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    deldelYt[i, j, jj] = deldelA[i, j, jj] + \
                        P[i]*deldelN[i, j, jj] + delP[i, jj]*delN[i, j] + \
                        delP[i, j]*delN[i, jj] + deldelP[i, j, jj]*N[i]

        return deldelYt

    def run_hessian_debug(self, x):
        """Compute the trained Hessian (debug version)."""
        n = len(x)
        m = len(x[0])
        H = len(self.w[0])
        w = self.w
        u = self.u
        v = self.v

        z = np.zeros((n, H))
        for i in range(n):
            for k in range(H):
                z[i, k] = u[k]
                for j in range(m):
                    z[i, k] += w[j, k]*x[i, j]

        s = np.zeros((n, H))
        for i in range(n):
            for k in range(H):
                s[i, k] = sigma(z[i, k])

        s1 = np.zeros((n, H))
        for i in range(n):
            for k in range(H):
                s1[i, k] = dsigma_dz(z[i, k])

        s2 = np.zeros((n, H))
        for i in range(n):
            for k in range(H):
                s2[i, k] = d2sigma_dz2(z[i, k])

        N = np.zeros(n)
        for i in range(n):
            for k in range(H):
                N[i] += v[k]*s[i, k]

        delN = np.zeros((n, m))
        for i in range(n):
            for j in range(m):
                for k in range(H):
                    delN[i, j] += v[k]*s1[i, k]*w[j, k]

        deldelN = np.zeros((n, m, m))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    for k in range(H):
                        deldelN[i, j, jj] += v[k]*s2[i, k]*w[j, k]*w[jj, k]

        deldelA = np.zeros((n, m, m))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    deldelA[i, j, jj] = self.deldelAf[j][jj](x[i])

        P = np.zeros(n)
        for i in range(n):
            P[i] = self.__Pf(x[i])

        delP = np.zeros((n, m))
        for i in range(n):
            for j in range(m):
                delP[i, j] = self.delPf[j](x[i])

        deldelP = np.zeros((n, m, m))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    deldelP[i, j, jj] = self.deldelPf[j][jj](x[i])

        deldelYt = np.zeros((n, m, m))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    deldelYt[i, j, jj] = deldelA[i, j, jj] + \
                        P[i]*deldelN[i, j, jj] + delP[i, jj]*delN[i, j] + \
                        delP[i, j]*delN[i, jj] + deldelP[i, j, jj]*N[i]

        return deldelYt


    # Internal methods below this point


    def __init__(self, eq, nhid=DEFAULT_NHID):
        super().__init__()
        self.eq = eq
        m = 2
        self.w = np.zeros((m, nhid))
        self.u = np.zeros(nhid)
        self.v = np.zeros(nhid)

        # Pre-vectorize functions for efficiency.

        # Gather trial function derivatives.
        self.delAf = (self.__dA_dxf, self.__dA_dtf)
        self.deldelAf = ((self.__d2A_dxdxf, self.__d2A_dxdtf),
                         (self.__d2A_dtdxf, self.__d2A_dtdtf))
        self.delPf = (self.__dP_dxf, self.__dP_dtf)
        self.deldelPf = ((self.__d2P_dxdxf, self.__d2P_dxdtf),
                         (self.__d2P_dtdxf, self.__d2P_dtdtf))

        # <HACK>
        self.nit = 0
        self.res = None
        # </HACK>

    def __str__(self):
        s = ''
        s += "NNPDEDIFF1D:\n"
        s += "%s\n" % self.eq
        s += "w = %s\n" % self.w
        s += "u = %s\n" % self.u
        s += "v = %s\n" % self.v
        return s.rstrip()

    def __Af(self, xt):
        """BC function for trial solution"""
        (x, t) = xt
        ((f0, f1), (g0, g1)) = self.eq.bcf
        return (1 - x)*f0(t) + x*f1(t) + \
            (1 - t)*(g0(x) - (1 - x)*g0(0) - x*g0(1))

    def __dA_dxf(self, xt):
        """BC function x-derivative for trial solution"""
        (x, t) = xt
        ((f0, f1), (g0, g1)) = self.eq.bcf
        ((df0_dt, df1_dt), (dg0_dx, dg1_dx)) = self.eq.bcdf
        return f1(t) - f0(t) + (1 - t)*(g0(0) - g0(1) + dg0_dx(x))

    def __dA_dtf(self, xt):
        """BC function t-derivative for trial solution"""
        (x, t) = xt
        ((f0, f1), (g0, g1)) = self.eq.bcf
        ((df0_dt, df1_dt), (dg0_dx, dg1_dx)) = self.eq.bcdf
        return g0(0)*(1 - x) + x*g0(1) - g0(x) + (1 - x)*df0_dt(t) + \
            x*df1_dt(t)

    def __d2A_dxdxf(self, xt):
        """BC function xx-derivative for trial solution"""
        (x, t) = xt
        ((f0, f1), (g0, g1)) = self.eq.bcf
        ((df0_dt, df1_dt), (dg0_dx, dg1_dx)) = self.eq.bcdf
        ((d2f0_dt2, d2f1_dt2), (d2g0_dx2, d2g1_dx2)) = self.eq.bcd2f
        return (1 - t)*d2g0_dx2(x)

    def __d2A_dxdtf(self, xt):
        """BC function xt-derivative for trial solution"""
        (x, t) = xt
        ((f0, f1), (g0, g1)) = self.eq.bcf
        ((df0_dt, df1_dt), (dg0_dx, dg1_dx)) = self.eq.bcdf
        ((d2f0_dt2, d2f1_dt2), (d2g0_dx2, d2g1_dx2)) = self.eq.bcd2f
        return g0(1) - g0(0) + df1_dt(t) - df0_dt(t) - dg0_dx(x)

    def __d2A_dtdxf(self, xt):
        """BC function tx-derivative for trial solution"""
        (x, t) = xt
        ((f0, f1), (g0, g1)) = self.eq.bcf
        ((df0_dt, df1_dt), (dg0_dx, dg1_dx)) = self.eq.bcdf
        ((d2f0_dt2, d2f1_dt2), (d2g0_dx2, d2g1_dx2)) = self.eq.bcd2f
        return g0(1) - g0(0) + df1_dt(t) - df0_dt(t) - dg0_dx(x)

    def __d2A_dtdtf(self, xt):
        """BC function tt-derivative for trial solution"""
        (x, t) = xt
        ((f0, f1), (g0, g1)) = self.eq.bcf
        ((df0_dt, df1_dt), (dg0_dx, dg1_dx)) = self.eq.bcdf
        ((d2f0_dt2, d2f1_dt2), (d2g0_dx2, d2g1_dx2)) = self.eq.bcd2f
        return (1 - x)*d2f0_dt2(t) + x*d2f1_dt2(t)

    def __Pf(self, xt):
        """Coefficient function for trial solution"""
        (x, t) = xt
        return x*(1 - x)*t

    def __dP_dxf(self, xt):
        """Coefficient function x-derivative for trial solution"""
        (x, t) = xt
        return (1 - 2*x)*t

    def __dP_dtf(self, xt):
        """Coefficient function t-derivative for trial solution"""
        (x, t) = xt
        return x*(1 - x)

    def __d2P_dxdxf(self, xt):
        """Coefficient function xx-derivative for trial solution"""
        (x, t) = xt
        return -2*t

    def __d2P_dxdtf(self, xt):
        """Coefficient function xt-derivative for trial solution"""
        (x, t) = xt
        return 1 - 2*x

    def __d2P_dtdxf(self, xt):
        """Coefficient function tx-derivative for trial solution"""
        (x, t) = xt
        return 1 - 2*x

    def __d2P_dtdtf(self, xt):
        """Coefficient function tt-derivative for trial solution"""
        (x, t) = xt
        return 0

    def __Ytf(self, xt, N):
        """Trial solution"""
        return self.__Af(xt) + self.__Pf(xt)*N

    def __train_delta_debug(self, x, opts=DEFAULT_OPTS):
        """Train using the delta method."""

        my_opts = dict(DEFAULT_OPTS)
        my_opts.update(opts)

        # Sanity-check arguments.
        assert x.any()
        assert my_opts['maxepochs'] > 0
        assert my_opts['eta'] > 0
        assert my_opts['vmin'] < my_opts['vmax']
        assert my_opts['wmin'] < my_opts['wmax']
        assert my_opts['umin'] < my_opts['umax']

        # Determine the number of training points, and change notation for
        # convenience.
        n = len(x)
        m = len(self.eq.dG_ddelYf)
        assert m == 2  # <HACK>
        H = my_opts['nhid']
        # debug = my_opts['debug']
        verbose = my_opts['verbose']
        eta = my_opts['eta']
        maxepochs = my_opts['maxepochs']
        wmin = my_opts['wmin']
        wmax = my_opts['wmax']
        umin = my_opts['umin']
        umax = my_opts['umax']
        vmin = my_opts['vmin']
        vmax = my_opts['vmax']

        # Create the hidden node weights, biases, and output node weights.
        w = np.random.uniform(wmin, wmax, (m, H))
        u = np.random.uniform(umin, umax, H)
        v = np.random.uniform(vmin, vmax, H)

        # Initial parameter deltas are 0.
        dE_dw = np.zeros((m, H))
        dE_du = np.zeros(H)
        dE_dv = np.zeros(H)

        # Train the network.
        for epoch in range(maxepochs):
            if verbose:
                print('Starting epoch %d.' % epoch)

            # Compute the new values of the network parameters.
            for j in range(m):
                for k in range(H):
                    w[j, k] -= eta*dE_dw[j, k]

            for k in range(H):
                u[k] -= eta*dE_du[k]

            for k in range(H):
                v[k] -= eta*dE_dv[k]

            # Compute the net input, the sigmoid function and its derivatives,
            # for each hidden node and each training point.
            z = np.zeros((n, H))
            for i in range(n):
                for k in range(H):
                    z[i, k] = u[k]
                    for j in range(m):
                        z[i, k] += w[j, k]*x[i, j]

            s = np.zeros((n, H))
            for i in range(n):
                for k in range(H):
                    s[i, k] = sigma(z[i, k])

            s1 = np.zeros((n, H))
            for i in range(n):
                for k in range(H):
                    s1[i, k] = dsigma_dz(z[i, k])

            s2 = np.zeros((n, H))
            for i in range(n):
                for k in range(H):
                    s2[i, k] = d2sigma_dz2(z[i, k])

            s3 = np.zeros((n, H))
            for i in range(n):
                for k in range(H):
                    s3[i, k] = d3sigma_dz3(z[i, k])

            # Compute the network output and its derivatives, for each
            # training point.
            N = np.zeros(n)
            for i in range(n):
                for k in range(H):
                    N[i] += v[k]*s[i, k]

            delN = np.zeros((n, m))
            for i in range(n):
                for j in range(m):
                    for k in range(H):
                        delN[i, j] += v[k]*s1[i, k]*w[j, k]

            deldelN = np.zeros((n, m, m))
            for i in range(n):
                for j in range(m):
                    for jj in range(m):
                        for k in range(H):
                            deldelN[i, j, jj] += v[k]*s2[i, k]*w[j, k]*w[jj, k]

            dN_dw = np.zeros((n, m, H))
            for i in range(n):
                for j in range(m):
                    for k in range(H):
                        dN_dw[i, j, k] = v[k]*s1[i, k]*x[i, j]

            dN_du = np.zeros((n, H))
            for i in range(n):
                for k in range(H):
                    dN_du[i, k] = v[k]*s1[i, k]

            dN_dv = np.zeros((n, H))
            for i in range(n):
                for k in range(H):
                    dN_dv[i, k] = s[i, k]

            d2N_dwdx = np.zeros((n, m, m, H))
            for i in range(n):
                for j in range(m):
                    for jj in range(m):
                        for k in range(H):
                            d2N_dwdx[i, j, jj, k] = v[k] * \
                                (s1[i, k]*kdelta(j, jj) + s2[i, k] *
                                 w[jj, k]*x[i, j])

            d2N_dudx = np.zeros((n, m, H))
            for i in range(n):
                for j in range(m):
                    for k in range(H):
                        d2N_dudx[i, j, k] = v[k]*s2[i, k]*w[j, k]

            d2N_dvdx = np.zeros((n, m, H))
            for i in range(n):
                for j in range(m):
                    for k in range(H):
                        d2N_dvdx[i, j, k] = s1[i, k]*w[j, k]

            d3N_dwdxdy = np.zeros((n, m, m, m, H))
            for i in range(n):
                for j in range(m):
                    for jj in range(m):
                        for jjj in range(m):
                            for k in range(H):
                                d3N_dwdxdy[i, j, jj, jjj, k] = v[k] * \
                                    (s2[i, k]*(w[jjj, k]*kdelta(j, jj) +
                                               w[jj, k]*kdelta(j, jjj)) +
                                     s3[i, k]*w[jj, k]*w[jjj, k]*x[i, j])

            d3N_dudxdy = np.zeros((n, m, m, H))
            for i in range(n):
                for j in range(m):
                    for jj in range(m):
                        for k in range(H):
                            d3N_dudxdy[i, j, jj, k] = \
                                v[k]*s3[i, k]*w[j, k]*w[jj, k]

            d3N_dvdxdy = np.zeros((n, m, m, H))
            for i in range(n):
                for j in range(m):
                    for jj in range(m):
                        for k in range(H):
                            d3N_dvdxdy[i, j, jj, k] = \
                                s2[i, k]*w[j, k]*w[jj, k]

            # Compute the value of the trial solution and its derivatives,
            # for each training point.
            A = np.zeros(n)
            for i in range(n):
                A[i] = self.__Af(x[i])

            delA = np.zeros((n, m))
            for i in range(n):
                for j in range(m):
                    delA[i, j] = self.delAf[j](x[i])

            deldelA = np.zeros((n, m, m))
            for i in range(n):
                for j in range(m):
                    for jj in range(m):
                        deldelA[i, j, jj] = self.deldelAf[j][jj](x[i])

            P = np.zeros(n)
            for i in range(n):
                P[i] = self.__Pf(x[i])

            delP = np.zeros((n, m))
            for i in range(n):
                for j in range(m):
                    delP[i, j] = self.delPf[j](x[i])

            deldelP = np.zeros((n, m, m))
            for i in range(n):
                for j in range(m):
                    for jj in range(m):
                        deldelP[i, j, jj] = self.deldelPf[j][jj](x[i])

            Yt = np.zeros(n)
            for i in range(n):
                Yt[i] = self.__Ytf(x[i], N[i])

            delYt = np.zeros((n, m))
            for i in range(n):
                for j in range(m):
                    delYt[i, j] = delA[i, j] + P[i]*delN[i, j] + \
                        delP[i, j]*N[i]

            deldelYt = np.zeros((n, m, m))
            for i in range(n):
                for j in range(m):
                    for jj in range(m):
                        deldelYt[i, j, jj] = deldelA[i, j, jj] + \
                            P[i]*deldelN[i, j, jj] + delP[i, jj]*delN[i, j] + \
                            delP[i, j]*delN[i, jj] + deldelP[i, j, jj]*N[i]

            dYt_dw = np.zeros((n, m, H))
            for i in range(n):
                for j in range(m):
                    for k in range(H):
                        dYt_dw[i, j, k] = P[i]*dN_dw[i, j, k]

            dYt_du = np.zeros((n, H))
            for i in range(n):
                for k in range(H):
                    dYt_du[i, k] = P[i]*dN_du[i, k]

            dYt_dv = np.zeros((n, H))
            for i in range(n):
                for k in range(H):
                    dYt_dv[i, k] = P[i]*dN_dv[i, k]

            d2Yt_dwdx = np.zeros((n, m, m, H))
            for i in range(n):
                for j in range(m):
                    for jj in range(m):
                        for k in range(H):
                            d2Yt_dwdx[i, j, jj, k] = P[i] * \
                                d2N_dwdx[i, j, jj, k] + \
                                delP[i, jj]*dN_dw[i, j, k]

            d2Yt_dudx = np.zeros((n, m, H))
            for i in range(n):
                for j in range(m):
                    for k in range(H):
                        d2Yt_dudx[i, j, k] = P[i]*d2N_dudx[i, j, k] + \
                            delP[i, j]*dN_du[i, k]

            d2Yt_dvdx = np.zeros((n, m, H))
            for i in range(n):
                for j in range(m):
                    for k in range(H):
                        d2Yt_dvdx[i, j, k] = P[i]*d2N_dvdx[i, j, k] + \
                            delP[i, j]*dN_dv[i, k]

            d3Yt_dwdxdy = np.zeros((n, m, m, m, H))
            for i in range(n):
                for j in range(m):
                    for jj in range(m):
                        for jjj in range(m):
                            for k in range(H):
                                d3Yt_dwdxdy[i, j, jj, jjj, k] = \
                                    P[i]*d3N_dwdxdy[i, j, jj, jjj, k] + \
                                    delP[i, jjj]*d2N_dwdx[i, j, jj, k] + \
                                    delP[i, jj]*d2N_dwdx[i, j, jjj, k] + \
                                    deldelP[i, jj, jjj]*dN_dw[i, j, k]

            d3Yt_dudxdy = np.zeros((n, m, m, H))
            for i in range(n):
                for j in range(m):
                    for jj in range(m):
                        for k in range(H):
                            d3Yt_dudxdy[i, j, jj, k] = \
                                P[i]*d3N_dudxdy[i, j, jj, k] + \
                                delP[i, j]*d2N_dudx[i, jj, k] + \
                                delP[i, jj]*d2N_dudx[i, j, k] + \
                                deldelP[i, j, jj]*dN_du[i, k]

            d3Yt_dvdxdy = np.zeros((n, m, m, H))
            for i in range(n):
                for j in range(m):
                    for jj in range(m):
                        for k in range(H):
                            d3Yt_dvdxdy[i, j, jj, k] = \
                                P[i]*d3N_dvdxdy[i, j, jj, k] + \
                                delP[i, j]*d2N_dvdx[i, jj, k] + \
                                delP[i, jj]*d2N_dvdx[i, j, k] + \
                                deldelP[i, j, jj]*dN_dv[i, k]

            # Compute the value of the original differential equation
            # for each training point, and its derivatives.
            G = np.zeros(n)
            for i in range(n):
                G[i] = self.eq.Gf(x[i], Yt[i], delYt[i], deldelYt[i])

            dG_dYt = np.zeros(n)
            for i in range(n):
                dG_dYt[i] = self.eq.dG_dYf(x[i], Yt[i], delYt[i], deldelYt[i])

            dG_ddelYt = np.zeros((n, m))
            for i in range(n):
                for j in range(m):
                    dG_ddelYt[i, j] = \
                        self.eq.dG_ddelYf[j](x[i], Yt[i], delYt[i],
                                             deldelYt[i])

            dG_ddeldelYt = np.zeros((n, m, m))
            for i in range(n):
                for j in range(m):
                    for jj in range(m):
                        dG_ddeldelYt[i, j, jj] = \
                            self.eq.dG_ddeldelYf[j][jj](x[i], Yt[i], delYt[i],
                                                        deldelYt[i])

            dG_dw = np.zeros((n, m, H))
            for i in range(n):
                for j in range(m):
                    for k in range(H):
                        dG_dw[i, j, k] = dG_dYt[i]*dYt_dw[i, j, k]
                        for jj in range(m):
                            dG_dw[i, j, k] += \
                                dG_ddelYt[i, jj]*d2Yt_dwdx[i, j, jj, k]
                            for jjj in range(m):
                                dG_dw[i, j, k] += dG_ddeldelYt[i, jj, jjj] * \
                                    d3Yt_dwdxdy[i, j, jj, jjj, k]

            dG_du = np.zeros((n, H))
            for i in range(n):
                for k in range(H):
                    dG_du[i, k] = dG_dYt[i]*dYt_du[i, k]
                    for j in range(m):
                        dG_du[i, k] += dG_ddelYt[i, j]*d2Yt_dudx[i, j, k]
                        for jj in range(m):
                            dG_du[i, k] += dG_ddeldelYt[i, j, jj] * \
                                d3Yt_dudxdy[i, j, jj, k]

            dG_dv = np.zeros((n, H))
            for i in range(n):
                for k in range(H):
                    dG_dv[i, k] = dG_dYt[i]*dYt_dv[i, k]
                    for j in range(m):
                        dG_dv[i, k] += dG_ddelYt[i, j]*d2Yt_dvdx[i, j, k]
                        for jj in range(m):
                            dG_dv[i, k] += dG_ddeldelYt[i, j, jj] * \
                                d3Yt_dvdxdy[i, j, jj, k]

            # Compute the partial derivatives of the error with respect to the
            # network parameters.
            dE_dw = np.zeros((m, H))
            for j in range(m):
                for k in range(H):
                    for i in range(n):
                        dE_dw[j, k] += 2*G[i]*dG_dw[i, j, k]

            dE_du = np.zeros(H)
            for k in range(H):
                for i in range(n):
                    dE_du[k] += 2*G[i]*dG_du[i, k]

            dE_dv = np.zeros(H)
            for k in range(H):
                for i in range(n):
                    dE_dv[k] += 2*G[i]*dG_dv[i, k]

            # Compute the RMS error for this epoch.
            E2 = 0
            for i in range(n):
                E2 += G[i]**2
            if verbose:
                rmse = sqrt(E2/n)
                print(epoch, rmse)

        # Save the optimized parameters.
        self.w = w
        self.u = u
        self.v = v

    def __train_delta(self, x, opts=DEFAULT_OPTS):
        """Train using the delta method, improved with numpy vector ops."""

        my_opts = dict(DEFAULT_OPTS)
        my_opts.update(opts)

        # Sanity-check arguments.
        assert x.any()
        assert my_opts['maxepochs'] > 0
        assert my_opts['eta'] > 0
        assert my_opts['vmin'] < my_opts['vmax']
        assert my_opts['wmin'] < my_opts['wmax']
        assert my_opts['umin'] < my_opts['umax']

        # ---------------------------------------------------------------------

        # Change notation for convenience.
        n = len(x)
        m = 2  # <HACK>
        H = my_opts['nhid']

        # Create the hidden node weights, biases, and output node weights.
        self.w = np.random.uniform(my_opts['wmin'], my_opts['wmax'], (m, H))
        self.u = np.random.uniform(my_opts['umin'], my_opts['umax'], H)
        self.v = np.random.uniform(my_opts['vmin'], my_opts['vmax'], H)

        # Initial parameter deltas are 0.
        dE_dw = np.zeros((m, H))
        dE_du = np.zeros(H)
        dE_dv = np.zeros(H)

        # Create local references to the parameter arrays for convenience.
        # THESE ARE REFERENCES, NOT COPIES.
        w = self.w
        u = self.u
        v = self.v

        # Train the network.
        for epoch in range(my_opts['maxepochs']):
            if my_opts['debug']:
                print('Starting epoch %d.' % epoch)

            # Compute the new values of the network parameters.
            w -= my_opts['eta']*dE_dw
            u -= my_opts['eta']*dE_du
            v -= my_opts['eta']*dE_dv

            # Compute the net input, the sigmoid function and its derivatives,
            # for each hidden node and each training point.
            z = np.dot(x, w) + u
            s = sigma_v(z)
            s1 = dsigma_dz_v(z)
            s2 = d2sigma_dz2_v(z)
            s3 = d3sigma_dz3_v(z)

            # Compute the network output and its derivatives, for each
            # training point.
            N = np.dot(s, v)
            delN = np.dot(s1, (v*w).T)

            deldelN = np.zeros((n, m, m))
            for i in range(n):
                for j in range(m):
                    for jj in range(m):
                        deldelN[i, j, jj] = np.dot(v, s2[i]*w[j]*w[jj])

            dN_dw = v[np.newaxis, np.newaxis, :] * \
                    s1[:, np.newaxis, :]*x[:, :, np.newaxis]
            dN_du = v*s1
            dN_dv = np.copy(s)

            d2N_dwdx = np.zeros((n, m, m, H))
            for i in range(n):
                for j in range(m):
                    for jj in range(m):
                        d2N_dwdx[i, j, jj] = v*(s1[i]*kdelta(j, jj) +
                                                s2[i]*w[jj]*x[i, j])

            d2N_dudx = v[np.newaxis, np.newaxis, :] * \
                       s2[:, np.newaxis, :]*w[np.newaxis, :, :]
            d2N_dvdx = s1[:, np.newaxis, :]*w[np.newaxis, :, :]

            d3N_dwdxdy = np.zeros((n, m, m, m, H))
            for i in range(n):
                for j in range(m):
                    for jj in range(m):
                        for jjj in range(m):
                            d3N_dwdxdy[i, j, jj, jjj] = \
                            v * (s2[i]*(w[jjj]*kdelta(j, jj) + \
                                 w[jj]*kdelta(j, jjj)) + \
                                 s3[i]*w[jj]*w[jjj]*x[i, j])

            d3N_dudxdy = np.zeros((n, m, m, H))
            for i in range(n):
                for j in range(m):
                    for jj in range(m):
                        d3N_dudxdy[i, j, jj] = v*s3[i]*w[j]*w[jj]

            d3N_dvdxdy = np.zeros((n, m, m, H))
            for i in range(n):
                for j in range(m):
                    for jj in range(m):
                        d3N_dvdxdy[i, j, jj] = s2[i]*w[j]*w[jj]

            # Compute the value of the trial solution and its derivatives,
            # for each training point.
            A = np.zeros(n)
            for i in range(n):
                A[i] = self.__Af(x[i])

            delA = np.zeros((n, m))
            for i in range(n):
                for j in range(m):
                    delA[i, j] = self.delAf[j](x[i])

            deldelA = np.zeros((n, m, m))
            for i in range(n):
                for j in range(m):
                    for jj in range(m):
                        deldelA[i, j, jj] = self.deldelAf[j][jj](x[i])

            P = np.zeros(n)
            for i in range(n):
                P[i] = self.__Pf(x[i])

            delP = np.zeros((n, m))
            for i in range(n):
                for j in range(m):
                    delP[i, j] = self.delPf[j](x[i])

            deldelP = np.zeros((n, m, m))
            for i in range(n):
                for j in range(m):
                    for jj in range(m):
                        deldelP[i, j, jj] = self.deldelPf[j][jj](x[i])

            Yt = np.zeros(n)
            for i in range(n):
                Yt[i] = self.__Ytf(x[i], N[i])

            delYt = delA + P[:, np.newaxis]*delN + N[:, np.newaxis]*delP

            deldelYt = np.zeros((n, m, m))
            for j in range(m):
                for jj in range(m):
                    deldelYt[:, j, jj] = deldelA[:, j, jj] + \
                        P*deldelN[:, j, jj] + delP[:, jj]*delN[:, j] + \
                        delP[:, j]*delN[:, jj] + deldelP[:, j, jj]*N

            dYt_dw = P[:, np.newaxis, np.newaxis]*dN_dw
            dYt_du = P[:, np.newaxis]*dN_du
            dYt_dv = P[:, np.newaxis]*dN_dv

            d2Yt_dwdx = np.zeros((n, m, m, H))
            for i in range(n):
                for j in range(m):
                    for jj in range(m):
                        d2Yt_dwdx[i, j, jj] = P[i] * d2N_dwdx[i, j, jj] + \
                            delP[i, jj]*dN_dw[i, j]

            d2Yt_dudx = P[:, np.newaxis, np.newaxis]*d2N_dudx + \
                        delP[:, :, np.newaxis]*dN_du[:, np.newaxis, :]
            d2Yt_dvdx = P[:, np.newaxis, np.newaxis]*d2N_dvdx + \
                        delP[:, :, np.newaxis]*dN_dv[:, np.newaxis, :]

            d3Yt_dwdxdy = np.zeros((n, m, m, m, H))
            for i in range(n):
                for j in range(m):
                    for jj in range(m):
                        for jjj in range(m):
                            for k in range(H):
                                d3Yt_dwdxdy[i, j, jj, jjj, k] = \
                                    P[i]*d3N_dwdxdy[i, j, jj, jjj, k] + \
                                    delP[i, jjj]*d2N_dwdx[i, j, jj, k] + \
                                    delP[i, jj]*d2N_dwdx[i, j, jjj, k] + \
                                    deldelP[i, jj, jjj]*dN_dw[i, j, k]

            d3Yt_dudxdy = np.zeros((n, m, m, H))
            for i in range(n):
                for j in range(m):
                    for jj in range(m):
                        for k in range(H):
                            d3Yt_dudxdy[i, j, jj, k] = \
                                P[i]*d3N_dudxdy[i, j, jj, k] + \
                                delP[i, j]*d2N_dudx[i, jj, k] + \
                                delP[i, jj]*d2N_dudx[i, j, k] + \
                                deldelP[i, j, jj]*dN_du[i, k]

            d3Yt_dvdxdy = np.zeros((n, m, m, H))
            for i in range(n):
                for j in range(m):
                    for jj in range(m):
                        for k in range(H):
                            d3Yt_dvdxdy[i, j, jj, k] = \
                                P[i]*d3N_dvdxdy[i, j, jj, k] + \
                                delP[i, j]*d2N_dvdx[i, jj, k] + \
                                delP[i, jj]*d2N_dvdx[i, j, k] + \
                                deldelP[i, j, jj]*dN_dv[i, k]

            # Compute the value of the original differential equation
            # for each training point, and its derivatives.
            G = np.zeros(n)
            for i in range(n):
                G[i] = self.eq.Gf(x[i], Yt[i], delYt[i], deldelYt[i])

            dG_dYt = np.zeros(n)
            for i in range(n):
                dG_dYt[i] = self.eq.dG_dYf(x[i], Yt[i], delYt[i], deldelYt[i])

            dG_ddelYt = np.zeros((n, m))
            for i in range(n):
                for j in range(m):
                    dG_ddelYt[i, j] = \
                        self.eq.dG_ddelYf[j](x[i], Yt[i], delYt[i],
                                             deldelYt[i])

            dG_ddeldelYt = np.zeros((n, m, m))
            for i in range(n):
                for j in range(m):
                    for jj in range(m):
                        dG_ddeldelYt[i, j, jj] = \
                            self.eq.dG_ddeldelYf[j][jj](x[i], Yt[i], delYt[i],
                                                        deldelYt[i])

            dG_dw = np.zeros((n, m, H))
            for i in range(n):
                for j in range(m):
                    for k in range(H):
                        dG_dw[i, j, k] = dG_dYt[i]*dYt_dw[i, j, k]
                        for jj in range(m):
                            dG_dw[i, j, k] += \
                                dG_ddelYt[i, jj]*d2Yt_dwdx[i, j, jj, k]
                            for jjj in range(m):
                                dG_dw[i, j, k] += dG_ddeldelYt[i, jj, jjj] * \
                                    d3Yt_dwdxdy[i, j, jj, jjj, k]

            dG_du = np.zeros((n, H))
            for i in range(n):
                for k in range(H):
                    dG_du[i, k] = dG_dYt[i]*dYt_du[i, k]
                    for j in range(m):
                        dG_du[i, k] += dG_ddelYt[i, j]*d2Yt_dudx[i, j, k]
                        for jj in range(m):
                            dG_du[i, k] += dG_ddeldelYt[i, j, jj] * \
                                d3Yt_dudxdy[i, j, jj, k]

            dG_dv = np.zeros((n, H))
            for i in range(n):
                for k in range(H):
                    dG_dv[i, k] = dG_dYt[i]*dYt_dv[i, k]
                    for j in range(m):
                        dG_dv[i, k] += dG_ddelYt[i, j]*d2Yt_dvdx[i, j, k]
                        for jj in range(m):
                            dG_dv[i, k] += dG_ddeldelYt[i, j, jj] * \
                                d3Yt_dvdxdy[i, j, jj, k]

            # Compute the partial derivatives of the error with respect to the
            # network parameters.
            dE_dw = np.zeros((m, H))
            for j in range(m):
                for k in range(H):
                    for i in range(n):
                        dE_dw[j, k] += 2*G[i]*dG_dw[i, j, k]

            dE_du = np.zeros(H)
            for k in range(H):
                for i in range(n):
                    dE_du[k] += 2*G[i]*dG_du[i, k]

            dE_dv = np.zeros(H)
            for k in range(H):
                for i in range(n):
                    dE_dv[k] += 2*G[i]*dG_dv[i, k]

            # Compute the error function for this epoch.
            E = np.sum(G**2)
            if my_opts['verbose']:
                rmse = sqrt(E/n)
                print(epoch, rmse)

    def __train_minimize(self, x, trainalg, opts=DEFAULT_OPTS, options=None):
        """Train using the scipy minimize() function"""

        my_opts = dict(DEFAULT_OPTS)
        my_opts.update(opts)

        # Sanity-check arguments.
        assert x.any()
        assert opts['vmin'] < opts['vmax']
        assert opts['wmin'] < opts['wmax']
        assert opts['umin'] < opts['umax']

        callback = None
        if my_opts['verbose']:
            callback = self.__print_progress

        # ---------------------------------------------------------------------

        # Create the hidden node weights, biases, and output node weights.
        m = 2
        H = my_opts['nhid']
        self.w = np.random.uniform(my_opts['wmin'], my_opts['wmax'], (m, H))
        self.u = np.random.uniform(my_opts['umin'], my_opts['umax'], H)
        self.v = np.random.uniform(my_opts['vmin'], my_opts['vmax'], H)

        # Assemble the network parameters into a single 1-D vector for
        # use by the minimize() method.
        p = np.hstack((self.w[0], self.w[1], self.u, self.v))

        # Use Jacobian for relevant methods.
        # jac = None
        # if trainalg in ('CG', 'BFGS', 'Newton-CG'):
        #     jac = self.__compute_error_gradient
        # res = minimize(self.__compute_error, p, method=trainalg, args=(x),
        #                jac=jac, options=options, callback=callback)

        jac = True
        res = minimize(self.__compute_error_and_jacobian, p, method=trainalg,
                       args=(x), jac=jac, options=options, callback=callback)

        if my_opts['verbose']:
            print('res =', res)
        self.res = res

        # Unpack the optimized network parameters.
        self.w[0] = res.x[0:H]
        self.w[1] = res.x[H:2*H]
        self.u = res.x[2*H:3*H]
        self.v = res.x[3*H:4*H]

    def __compute_error(self, p, x):
        """Compute the current error in the trained solution."""

        # Unpack the network parameters.
        n = len(x)
        m = len(x[0])
        H = int(len(p)/(m + 2))  # HACK!
        w = np.zeros((m, H))
        (w[0], w[1], u, v) = np.hsplit(p, 4)

        # Compute the forward pass through the network.

        # Weighted inputs and transfer functions and derivatives.
        z = np.dot(x, w) + u
        s = sigma_v(z)
        s1 = dsigma_dz_v(z)
        s2 = d2sigma_dz2_v(z)

        # Network output and derivatives.
        N = np.dot(s, v)
        delN = np.dot(s1, (v*w).T)

        deldelN = np.zeros((n, m, m))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    deldelN[i, j, jj] = np.dot(v, s2[i]*w[j]*w[jj])

        # Trial function BC term and derivatives
        A = np.zeros(n)
        for i in range(n):
            A[i] = self.__Af(x[i])

        delA = np.zeros((n, m))
        for i in range(n):
            for j in range(m):
                delA[i, j] = self.delAf[j](x[i])

        deldelA = np.zeros((n, m, m))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    deldelA[i, j, jj] = self.deldelAf[j][jj](x[i])

        # Trial function coefficient term and derivatives
        P = np.zeros(n)
        for i in range(n):
            P[i] = self.__Pf(x[i])

        delP = np.zeros((n, m))
        for i in range(n):
            for j in range(m):
                delP[i, j] = self.delPf[j](x[i])

        deldelP = np.zeros((n, m, m))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    deldelP[i, j, jj] = self.deldelPf[j][jj](x[i])

        # Trial function and derivatives
        Yt = np.zeros(n)
        for i in range(n):
            Yt[i] = self.__Ytf(x[i], N[i])

        delYt = delA + P[:, np.newaxis]*delN + N[:, np.newaxis]*delP

        deldelYt = np.zeros((n, m, m))
        for j in range(m):
            for jj in range(m):
                deldelYt[:, j, jj] = deldelA[:, j, jj] + \
                    P*deldelN[:, j, jj] + delP[:, jj]*delN[:, j] + \
                    delP[:, j]*delN[:, jj] + deldelP[:, j, jj]*N

        # Differential equation
        G = np.zeros(n)
        for i in range(n):
            G[i] = self.eq.Gf(x[i], Yt[i], delYt[i], deldelYt[i])

        # Sum of squared error
        E = np.sum(G**2)
        return E

    def __compute_error_debug(self, p, x):
        """Compute the current error in the trained solution."""

        # Unpack the network parameters.
        n = len(x)
        m = len(x[0])
        H = int(len(p)/(m + 2))  # HACK!
        w = np.zeros((m, H))
        w[0] = p[0:H]
        w[1] = p[H:2*H]
        u = p[2*H:3*H]
        v = p[3*H:4*H]

        # Compute the forward pass through the network.

        # Weighted inputs and tranafer functions and derivatives.
        z = np.zeros((n, H))
        for i in range(n):
            for k in range(H):
                z[i, k] = u[k]
                for j in range(m):
                    z[i, k] += w[j, k]*x[i, j]

        s = np.zeros((n, H))
        for i in range(n):
            for k in range(H):
                s[i, k] = sigma(z[i, k])

        s1 = np.zeros((n, H))
        for i in range(n):
            for k in range(H):
                s1[i, k] = dsigma_dz(z[i, k])

        s2 = np.zeros((n, H))
        for i in range(n):
            for k in range(H):
                s2[i, k] = d2sigma_dz2(z[i, k])

        # Network output and derivatives.
        N = np.zeros(n)
        for i in range(n):
            for k in range(H):
                N[i] += v[k]*s[i, k]

        delN = np.zeros((n, m))
        for i in range(n):
            for j in range(m):
                for k in range(H):
                    delN[i, j] += v[k]*s1[i, k]*w[j, k]

        deldelN = np.zeros((n, m, m))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    for k in range(H):
                        deldelN[i, j, jj] += v[k]*s2[i, k]*w[j, k]*w[jj, k]

        # Trial function BC term and derivatives
        A = np.zeros(n)
        for i in range(n):
            A[i] = self.__Af(x[i])

        delA = np.zeros((n, m))
        for i in range(n):
            for j in range(m):
                delA[i, j] = self.delAf[j](x[i])

        deldelA = np.zeros((n, m, m))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    deldelA[i, j, jj] = self.deldelAf[j][jj](x[i])

        # Trial function coefficient term and derivatives
        P = np.zeros(n)
        for i in range(n):
            P[i] = self.__Pf(x[i])

        delP = np.zeros((n, m))
        for i in range(n):
            for j in range(m):
                delP[i, j] = self.delPf[j](x[i])

        deldelP = np.zeros((n, m, m))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    deldelP[i, j, jj] = self.deldelPf[j][jj](x[i])

        # Trial function and derivatives
        Yt = np.zeros(n)
        for i in range(n):
            Yt[i] = self.__Ytf(x[i], N[i])

        delYt = np.zeros((n, m))
        for i in range(n):
            for j in range(m):
                delYt[i, j] = delA[i, j] + P[i]*delN[i, j] + \
                    delP[i, j]*N[i]

        deldelYt = np.zeros((n, m, m))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    deldelYt[i, j, jj] = deldelA[i, j, jj] + \
                        P[i]*deldelN[i, j, jj] + delP[i, jj]*delN[i, j] + \
                        delP[i, j]*delN[i, jj] + deldelP[i, j, jj]*N[i]

        # Differential equation
        G = np.zeros(n)
        for i in range(n):
            G[i] = self.eq.Gf(x[i], Yt[i], delYt[i], deldelYt[i])

        # Sum of squared error
        E2 = 0
        for i in range(n):
            E2 += G[i]**2
        return E2

    def __compute_error_gradient(self, p, x):
        """Compute the error gradient in the trained solution."""

        # Unpack the network parameters.
        n = len(x)
        m = len(x[0])
        H = int(len(p)/(m + 2))  # HACK!
        w = np.zeros((m, H))
        (w[0], w[1], u, v) = np.hsplit(p, 4)

        # Compute the forward pass through the network.

        # Weighted inputs and transfer functions and derivatives.
        z = np.dot(x, w) + u
        s = sigma_v(z)
        s1 = dsigma_dz_v(z)
        s2 = d2sigma_dz2_v(z)
        s3 = d3sigma_dz3_v(z)

        # Network output and derivatives.
        N = np.dot(s, v)
        delN = np.dot(s1, (v*w).T)
        dN_dw = v[np.newaxis, np.newaxis, :] * \
                s1[:, np.newaxis, :]*x[:, :, np.newaxis]

        deldelN = np.zeros((n, m, m))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    deldelN[i, j, jj] = np.dot(v, s2[i]*w[j]*w[jj])

        dN_dw = v[np.newaxis, np.newaxis, :] * \
                s1[:, np.newaxis, :]*x[:, :, np.newaxis]
        dN_du = v*s1
        dN_dv = np.copy(s)

        d2N_dwdx = np.zeros((n, m, m, H))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    d2N_dwdx[i, j, jj] = v*(s1[i]*kdelta(j, jj) +
                                            s2[i]*w[jj]*x[i, j])

        d2N_dudx = v[np.newaxis, np.newaxis, :] * \
                    s2[:, np.newaxis, :]*w[np.newaxis, :, :]
        d2N_dvdx = s1[:, np.newaxis, :]*w[np.newaxis, :, :]

        d3N_dwdxdy = np.zeros((n, m, m, m, H))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    for jjj in range(m):
                        d3N_dwdxdy[i, j, jj, jjj] = \
                        v * (s2[i]*(w[jjj]*kdelta(j, jj) + \
                                w[jj]*kdelta(j, jjj)) + \
                                s3[i]*w[jj]*w[jjj]*x[i, j])

        d3N_dudxdy = np.zeros((n, m, m, H))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    d3N_dudxdy[i, j, jj] = v*s3[i]*w[j]*w[jj]

        d3N_dvdxdy = np.zeros((n, m, m, H))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    d3N_dvdxdy[i, j, jj] = s2[i]*w[j]*w[jj]


        delA = np.zeros((n, m))
        for i in range(n):
            for j in range(m):
                delA[i, j] = self.delAf[j](x[i])

        deldelA = np.zeros((n, m, m))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    deldelA[i, j, jj] = self.deldelAf[j][jj](x[i])

        P = np.zeros(n)
        for i in range(n):
            P[i] = self.__Pf(x[i])

        delP = np.zeros((n, m))
        for i in range(n):
            for j in range(m):
                delP[i, j] = self.delPf[j](x[i])

        deldelP = np.zeros((n, m, m))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    deldelP[i, j, jj] = self.deldelPf[j][jj](x[i])

        Yt = np.zeros(n)
        for i in range(n):
            Yt[i] = self.__Ytf(x[i], N[i])

        delYt = delA + P[:, np.newaxis]*delN + N[:, np.newaxis]*delP

        deldelYt = np.zeros((n, m, m))
        for j in range(m):
            for jj in range(m):
                deldelYt[:, j, jj] = deldelA[:, j, jj] + \
                    P*deldelN[:, j, jj] + delP[:, jj]*delN[:, j] + \
                    delP[:, j]*delN[:, jj] + deldelP[:, j, jj]*N

        dYt_dw = P[:, np.newaxis, np.newaxis]*dN_dw
        dYt_du = P[:, np.newaxis]*dN_du
        dYt_dv = P[:, np.newaxis]*dN_dv

        d2Yt_dwdx = np.zeros((n, m, m, H))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    d2Yt_dwdx[i, j, jj] = P[i] * d2N_dwdx[i, j, jj] + \
                        delP[i, jj]*dN_dw[i, j]

        d2Yt_dudx = P[:, np.newaxis, np.newaxis]*d2N_dudx + \
                    delP[:, :, np.newaxis]*dN_du[:, np.newaxis, :]
        d2Yt_dvdx = P[:, np.newaxis, np.newaxis]*d2N_dvdx + \
                    delP[:, :, np.newaxis]*dN_dv[:, np.newaxis, :]

        d3Yt_dwdxdy = np.zeros((n, m, m, m, H))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    for jjj in range(m):
                        for k in range(H):
                            d3Yt_dwdxdy[i, j, jj, jjj, k] = \
                                P[i]*d3N_dwdxdy[i, j, jj, jjj, k] + \
                                delP[i, jjj]*d2N_dwdx[i, j, jj, k] + \
                                delP[i, jj]*d2N_dwdx[i, j, jjj, k] + \
                                deldelP[i, jj, jjj]*dN_dw[i, j, k]

        d3Yt_dudxdy = np.zeros((n, m, m, H))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    for k in range(H):
                        d3Yt_dudxdy[i, j, jj, k] = \
                            P[i]*d3N_dudxdy[i, j, jj, k] + \
                            delP[i, j]*d2N_dudx[i, jj, k] + \
                            delP[i, jj]*d2N_dudx[i, j, k] + \
                            deldelP[i, j, jj]*dN_du[i, k]

        d3Yt_dvdxdy = np.zeros((n, m, m, H))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    for k in range(H):
                        d3Yt_dvdxdy[i, j, jj, k] = \
                            P[i]*d3N_dvdxdy[i, j, jj, k] + \
                            delP[i, j]*d2N_dvdx[i, jj, k] + \
                            delP[i, jj]*d2N_dvdx[i, j, k] + \
                            deldelP[i, j, jj]*dN_dv[i, k]

        G = np.zeros(n)
        for i in range(n):
            G[i] = self.eq.Gf(x[i], Yt[i], delYt[i], deldelYt[i])

        dG_dYt = np.zeros(n)
        for i in range(n):
            dG_dYt[i] = self.eq.dG_dYf(x[i], Yt[i], delYt[i], deldelYt[i])

        dG_ddelYt = np.zeros((n, m))
        for i in range(n):
            for j in range(m):
                dG_ddelYt[i, j] = \
                    self.eq.dG_ddelYf[j](x[i], Yt[i], delYt[i],
                                         deldelYt[i])

        dG_ddeldelYt = np.zeros((n, m, m))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    dG_ddeldelYt[i, j, jj] = \
                        self.eq.dG_ddeldelYf[j][jj](x[i], Yt[i], delYt[i],
                                                    deldelYt[i])

        dG_dw = np.zeros((n, m, H))
        for i in range(n):
            for j in range(m):
                for k in range(H):
                    dG_dw[i, j, k] = dG_dYt[i]*dYt_dw[i, j, k]
                    for jj in range(m):
                        dG_dw[i, j, k] += \
                            dG_ddelYt[i, jj]*d2Yt_dwdx[i, j, jj, k]
                        for jjj in range(m):
                            dG_dw[i, j, k] += dG_ddeldelYt[i, jj, jjj] * \
                                d3Yt_dwdxdy[i, j, jj, jjj, k]

        dG_du = np.zeros((n, H))
        for i in range(n):
            for k in range(H):
                dG_du[i, k] = dG_dYt[i]*dYt_du[i, k]
                for j in range(m):
                    dG_du[i, k] += dG_ddelYt[i, j]*d2Yt_dudx[i, j, k]
                    for jj in range(m):
                        dG_du[i, k] += dG_ddeldelYt[i, j, jj] * \
                            d3Yt_dudxdy[i, j, jj, k]

        dG_dv = np.zeros((n, H))
        for i in range(n):
            for k in range(H):
                dG_dv[i, k] = dG_dYt[i]*dYt_dv[i, k]
                for j in range(m):
                    dG_dv[i, k] += dG_ddelYt[i, j]*d2Yt_dvdx[i, j, k]
                    for jj in range(m):
                        dG_dv[i, k] += dG_ddeldelYt[i, j, jj] * \
                            d3Yt_dvdxdy[i, j, jj, k]

        dE_dw = np.zeros((m, H))
        for j in range(m):
            for k in range(H):
                for i in range(n):
                    dE_dw[j, k] += 2*G[i]*dG_dw[i, j, k]

        dE_du = np.zeros(H)
        for k in range(H):
            for i in range(n):
                dE_du[k] += 2*G[i]*dG_du[i, k]

        dE_dv = np.zeros(H)
        for k in range(H):
            for i in range(n):
                dE_dv[k] += 2*G[i]*dG_dv[i, k]

        jac = np.hstack((dE_dw[0], dE_dw[1], dE_du, dE_dv))
        return jac

    def __compute_error_gradient_debug(self, p, x):
        """Compute the error gradient in the trained solution."""

        # Unpack the network parameters.
        n = len(x)
        m = len(x[0])
        H = int(len(p)/(m + 2))  # HACK!
        w = np.zeros((m, H))
        w[0] = p[0:H]
        w[1] = p[H:2*H]
        u = p[2*H:3*H]
        v = p[3*H:4*H]

        z = np.zeros((n, H))
        for i in range(n):
            for k in range(H):
                z[i, k] = u[k]
                for j in range(m):
                    z[i, k] += w[j, k]*x[i, j]

        s = np.zeros((n, H))
        for i in range(n):
            for k in range(H):
                s[i, k] = sigma(z[i, k])

        s1 = np.zeros((n, H))
        for i in range(n):
            for k in range(H):
                s1[i, k] = dsigma_dz(z[i, k])

        s2 = np.zeros((n, H))
        for i in range(n):
            for k in range(H):
                s2[i, k] = d2sigma_dz2(z[i, k])

        s3 = np.zeros((n, H))
        for i in range(n):
            for k in range(H):
                s3[i, k] = d3sigma_dz3(z[i, k])

        N = np.zeros(n)
        for i in range(n):
            for k in range(H):
                N[i] += v[k]*s[i, k]

        delN = np.zeros((n, m))
        for i in range(n):
            for j in range(m):
                for k in range(H):
                    delN[i, j] += v[k]*s1[i, k]*w[j, k]

        deldelN = np.zeros((n, m, m))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    for k in range(H):
                        deldelN[i, j, jj] += v[k]*s2[i, k]*w[j, k]*w[jj, k]

        dN_dw = np.zeros((n, m, H))
        for i in range(n):
            for j in range(m):
                for k in range(H):
                    dN_dw[i, j, k] = v[k]*s1[i, k]*x[i, j]

        dN_du = np.zeros((n, H))
        for i in range(n):
            for k in range(H):
                dN_du[i, k] = v[k]*s1[i, k]

        dN_dv = np.zeros((n, H))
        for i in range(n):
            for k in range(H):
                dN_dv[i, k] = s[i, k]

        d2N_dwdx = np.zeros((n, m, m, H))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    for k in range(H):
                        d2N_dwdx[i, j, jj, k] = v[k] * \
                            (s1[i, k]*kdelta(j, jj) + s2[i, k] *
                             w[jj, k]*x[i, j])

        d2N_dudx = np.zeros((n, m, H))
        for i in range(n):
            for j in range(m):
                for k in range(H):
                    d2N_dudx[i, j, k] = v[k]*s2[i, k]*w[j, k]

        d2N_dvdx = np.zeros((n, m, H))
        for i in range(n):
            for j in range(m):
                for k in range(H):
                    d2N_dvdx[i, j, k] = s1[i, k]*w[j, k]

        d3N_dwdxdy = np.zeros((n, m, m, m, H))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    for jjj in range(m):
                        for k in range(H):
                            d3N_dwdxdy[i, j, jj, jjj, k] = v[k] * \
                                (s2[i, k]*(w[jjj, k]*kdelta(j, jj) +
                                           w[jj, k]*kdelta(j, jjj)) +
                                 s3[i, k]*w[jj, k]*w[jjj, k]*x[i, j])

        d3N_dudxdy = np.zeros((n, m, m, H))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    for k in range(H):
                        d3N_dudxdy[i, j, jj, k] = \
                            v[k]*s3[i, k]*w[j, k]*w[jj, k]

        d3N_dvdxdy = np.zeros((n, m, m, H))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    for k in range(H):
                        d3N_dvdxdy[i, j, jj, k] = \
                            s2[i, k]*w[j, k]*w[jj, k]

        delA = np.zeros((n, m))
        for i in range(n):
            for j in range(m):
                delA[i, j] = self.delAf[j](x[i])

        deldelA = np.zeros((n, m, m))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    deldelA[i, j, jj] = self.deldelAf[j][jj](x[i])

        P = np.zeros(n)
        for i in range(n):
            P[i] = self.__Pf(x[i])

        delP = np.zeros((n, m))
        for i in range(n):
            for j in range(m):
                delP[i, j] = self.delPf[j](x[i])

        deldelP = np.zeros((n, m, m))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    deldelP[i, j, jj] = self.deldelPf[j][jj](x[i])

        Yt = np.zeros(n)
        for i in range(n):
            Yt[i] = self.__Ytf(x[i], N[i])

        delYt = np.zeros((n, m))
        for i in range(n):
            for j in range(m):
                delYt[i, j] = delA[i, j] + P[i]*delN[i, j] + \
                    delP[i, j]*N[i]

        deldelYt = np.zeros((n, m, m))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    deldelYt[i, j, jj] = deldelA[i, j, jj] + \
                        P[i]*deldelN[i, j, jj] + delP[i, jj]*delN[i, j] + \
                        delP[i, j]*delN[i, jj] + deldelP[i, j, jj]*N[i]

        dYt_dw = np.zeros((n, m, H))
        for i in range(n):
            for j in range(m):
                for k in range(H):
                    dYt_dw[i, j, k] = P[i]*dN_dw[i, j, k]

        dYt_du = np.zeros((n, H))
        for i in range(n):
            for k in range(H):
                dYt_du[i, k] = P[i]*dN_du[i, k]

        dYt_dv = np.zeros((n, H))
        for i in range(n):
            for k in range(H):
                dYt_dv[i, k] = P[i]*dN_dv[i, k]

        d2Yt_dwdx = np.zeros((n, m, m, H))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    for k in range(H):
                        d2Yt_dwdx[i, j, jj, k] = P[i] * \
                            d2N_dwdx[i, j, jj, k] + \
                            delP[i, jj]*dN_dw[i, j, k]

        d2Yt_dudx = np.zeros((n, m, H))
        for i in range(n):
            for j in range(m):
                for k in range(H):
                    d2Yt_dudx[i, j, k] = P[i]*d2N_dudx[i, j, k] + \
                        delP[i, j]*dN_du[i, k]

        d2Yt_dvdx = np.zeros((n, m, H))
        for i in range(n):
            for j in range(m):
                for k in range(H):
                    d2Yt_dvdx[i, j, k] = P[i]*d2N_dvdx[i, j, k] + \
                        delP[i, j]*dN_dv[i, k]

        d3Yt_dwdxdy = np.zeros((n, m, m, m, H))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    for jjj in range(m):
                        for k in range(H):
                            d3Yt_dwdxdy[i, j, jj, jjj, k] = \
                                P[i]*d3N_dwdxdy[i, j, jj, jjj, k] + \
                                delP[i, jjj]*d2N_dwdx[i, j, jj, k] + \
                                delP[i, jj]*d2N_dwdx[i, j, jjj, k] + \
                                deldelP[i, jj, jjj]*dN_dw[i, j, k]

        d3Yt_dudxdy = np.zeros((n, m, m, H))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    for k in range(H):
                        d3Yt_dudxdy[i, j, jj, k] = \
                            P[i]*d3N_dudxdy[i, j, jj, k] + \
                            delP[i, j]*d2N_dudx[i, jj, k] + \
                            delP[i, jj]*d2N_dudx[i, j, k] + \
                            deldelP[i, j, jj]*dN_du[i, k]

        d3Yt_dvdxdy = np.zeros((n, m, m, H))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    for k in range(H):
                        d3Yt_dvdxdy[i, j, jj, k] = \
                            P[i]*d3N_dvdxdy[i, j, jj, k] + \
                            delP[i, j]*d2N_dvdx[i, jj, k] + \
                            delP[i, jj]*d2N_dvdx[i, j, k] + \
                            deldelP[i, j, jj]*dN_dv[i, k]

        G = np.zeros(n)
        for i in range(n):
            G[i] = self.eq.Gf(x[i], Yt[i], delYt[i], deldelYt[i])

        dG_dYt = np.zeros(n)
        for i in range(n):
            dG_dYt[i] = self.eq.dG_dYf(x[i], Yt[i], delYt[i], deldelYt[i])

        dG_ddelYt = np.zeros((n, m))
        for i in range(n):
            for j in range(m):
                dG_ddelYt[i, j] = \
                    self.eq.dG_ddelYf[j](x[i], Yt[i], delYt[i],
                                         deldelYt[i])

        dG_ddeldelYt = np.zeros((n, m, m))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    dG_ddeldelYt[i, j, jj] = \
                        self.eq.dG_ddeldelYf[j][jj](x[i], Yt[i], delYt[i],
                                                    deldelYt[i])

        dG_dw = np.zeros((n, m, H))
        for i in range(n):
            for j in range(m):
                for k in range(H):
                    dG_dw[i, j, k] = dG_dYt[i]*dYt_dw[i, j, k]
                    for jj in range(m):
                        dG_dw[i, j, k] += \
                            dG_ddelYt[i, jj]*d2Yt_dwdx[i, j, jj, k]
                        for jjj in range(m):
                            dG_dw[i, j, k] += dG_ddeldelYt[i, jj, jjj] * \
                                d3Yt_dwdxdy[i, j, jj, jjj, k]

        dG_du = np.zeros((n, H))
        for i in range(n):
            for k in range(H):
                dG_du[i, k] = dG_dYt[i]*dYt_du[i, k]
                for j in range(m):
                    dG_du[i, k] += dG_ddelYt[i, j]*d2Yt_dudx[i, j, k]
                    for jj in range(m):
                        dG_du[i, k] += dG_ddeldelYt[i, j, jj] * \
                            d3Yt_dudxdy[i, j, jj, k]

        dG_dv = np.zeros((n, H))
        for i in range(n):
            for k in range(H):
                dG_dv[i, k] = dG_dYt[i]*dYt_dv[i, k]
                for j in range(m):
                    dG_dv[i, k] += dG_ddelYt[i, j]*d2Yt_dvdx[i, j, k]
                    for jj in range(m):
                        dG_dv[i, k] += dG_ddeldelYt[i, j, jj] * \
                            d3Yt_dvdxdy[i, j, jj, k]

        dE_dw = np.zeros((m, H))
        for j in range(m):
            for k in range(H):
                for i in range(n):
                    dE_dw[j, k] += 2*G[i]*dG_dw[i, j, k]

        dE_du = np.zeros(H)
        for k in range(H):
            for i in range(n):
                dE_du[k] += 2*G[i]*dG_du[i, k]

        dE_dv = np.zeros(H)
        for k in range(H):
            for i in range(n):
                dE_dv[k] += 2*G[i]*dG_dv[i, k]

        jac = np.hstack((dE_dw[0], dE_dw[1], dE_du, dE_dv))
        return jac

    def __compute_error_and_jacobian(self, p, x):
        """Compute the squared error and its gradient (Jacobian)."""

        # Unpack the network parameters.
        n = len(x)
        m = len(x[0])
        H = int(len(p)/(m + 2))  # HACK!
        w = np.zeros((m, H))
        (w[0], w[1], u, v) = np.hsplit(p, 4)

        # Compute the forward pass through the network.

        # Weighted inputs and transfer functions and derivatives.
        z = np.dot(x, w) + u
        s = sigma_v(z)
        s1 = dsigma_dz_v(z)
        s2 = d2sigma_dz2_v(z)
        s3 = d3sigma_dz3_v(z)

        # Network output and derivatives.
        N = np.dot(s, v)
        delN = np.dot(s1, (v*w).T)
        dN_dw = v[np.newaxis, np.newaxis, :] * \
                s1[:, np.newaxis, :]*x[:, :, np.newaxis]

        deldelN = np.zeros((n, m, m))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    deldelN[i, j, jj] = np.dot(v, s2[i]*w[j]*w[jj])

        dN_dw = v[np.newaxis, np.newaxis, :] * \
                s1[:, np.newaxis, :]*x[:, :, np.newaxis]
        dN_du = v*s1
        dN_dv = np.copy(s)

        d2N_dwdx = np.zeros((n, m, m, H))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    d2N_dwdx[i, j, jj] = v*(s1[i]*kdelta(j, jj) +
                                            s2[i]*w[jj]*x[i, j])

        d2N_dudx = v[np.newaxis, np.newaxis, :] * \
                    s2[:, np.newaxis, :]*w[np.newaxis, :, :]
        d2N_dvdx = s1[:, np.newaxis, :]*w[np.newaxis, :, :]

        d3N_dwdxdy = np.zeros((n, m, m, m, H))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    for jjj in range(m):
                        d3N_dwdxdy[i, j, jj, jjj] = \
                        v * (s2[i]*(w[jjj]*kdelta(j, jj) + \
                                w[jj]*kdelta(j, jjj)) + \
                                s3[i]*w[jj]*w[jjj]*x[i, j])

        d3N_dudxdy = np.zeros((n, m, m, H))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    d3N_dudxdy[i, j, jj] = v*s3[i]*w[j]*w[jj]

        d3N_dvdxdy = np.zeros((n, m, m, H))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    d3N_dvdxdy[i, j, jj] = s2[i]*w[j]*w[jj]


        delA = np.zeros((n, m))
        for i in range(n):
            for j in range(m):
                delA[i, j] = self.delAf[j](x[i])

        deldelA = np.zeros((n, m, m))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    deldelA[i, j, jj] = self.deldelAf[j][jj](x[i])

        P = np.zeros(n)
        for i in range(n):
            P[i] = self.__Pf(x[i])

        delP = np.zeros((n, m))
        for i in range(n):
            for j in range(m):
                delP[i, j] = self.delPf[j](x[i])

        deldelP = np.zeros((n, m, m))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    deldelP[i, j, jj] = self.deldelPf[j][jj](x[i])

        Yt = np.zeros(n)
        for i in range(n):
            Yt[i] = self.__Ytf(x[i], N[i])

        delYt = delA + P[:, np.newaxis]*delN + N[:, np.newaxis]*delP

        deldelYt = np.zeros((n, m, m))
        for j in range(m):
            for jj in range(m):
                deldelYt[:, j, jj] = deldelA[:, j, jj] + \
                    P*deldelN[:, j, jj] + delP[:, jj]*delN[:, j] + \
                    delP[:, j]*delN[:, jj] + deldelP[:, j, jj]*N

        dYt_dw = P[:, np.newaxis, np.newaxis]*dN_dw
        dYt_du = P[:, np.newaxis]*dN_du
        dYt_dv = P[:, np.newaxis]*dN_dv

        d2Yt_dwdx = np.zeros((n, m, m, H))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    d2Yt_dwdx[i, j, jj] = P[i] * d2N_dwdx[i, j, jj] + \
                        delP[i, jj]*dN_dw[i, j]

        d2Yt_dudx = P[:, np.newaxis, np.newaxis]*d2N_dudx + \
                    delP[:, :, np.newaxis]*dN_du[:, np.newaxis, :]
        d2Yt_dvdx = P[:, np.newaxis, np.newaxis]*d2N_dvdx + \
                    delP[:, :, np.newaxis]*dN_dv[:, np.newaxis, :]

        d3Yt_dwdxdy = np.zeros((n, m, m, m, H))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    for jjj in range(m):
                        for k in range(H):
                            d3Yt_dwdxdy[i, j, jj, jjj, k] = \
                                P[i]*d3N_dwdxdy[i, j, jj, jjj, k] + \
                                delP[i, jjj]*d2N_dwdx[i, j, jj, k] + \
                                delP[i, jj]*d2N_dwdx[i, j, jjj, k] + \
                                deldelP[i, jj, jjj]*dN_dw[i, j, k]

        d3Yt_dudxdy = np.zeros((n, m, m, H))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    for k in range(H):
                        d3Yt_dudxdy[i, j, jj, k] = \
                            P[i]*d3N_dudxdy[i, j, jj, k] + \
                            delP[i, j]*d2N_dudx[i, jj, k] + \
                            delP[i, jj]*d2N_dudx[i, j, k] + \
                            deldelP[i, j, jj]*dN_du[i, k]

        d3Yt_dvdxdy = np.zeros((n, m, m, H))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    for k in range(H):
                        d3Yt_dvdxdy[i, j, jj, k] = \
                            P[i]*d3N_dvdxdy[i, j, jj, k] + \
                            delP[i, j]*d2N_dvdx[i, jj, k] + \
                            delP[i, jj]*d2N_dvdx[i, j, k] + \
                            deldelP[i, j, jj]*dN_dv[i, k]

        G = np.zeros(n)
        for i in range(n):
            G[i] = self.eq.Gf(x[i], Yt[i], delYt[i], deldelYt[i])

        E2 = np.sum(G**2)

        dG_dYt = np.zeros(n)
        for i in range(n):
            dG_dYt[i] = self.eq.dG_dYf(x[i], Yt[i], delYt[i], deldelYt[i])

        dG_ddelYt = np.zeros((n, m))
        for i in range(n):
            for j in range(m):
                dG_ddelYt[i, j] = \
                    self.eq.dG_ddelYf[j](x[i], Yt[i], delYt[i],
                                         deldelYt[i])

        dG_ddeldelYt = np.zeros((n, m, m))
        for i in range(n):
            for j in range(m):
                for jj in range(m):
                    dG_ddeldelYt[i, j, jj] = \
                        self.eq.dG_ddeldelYf[j][jj](x[i], Yt[i], delYt[i],
                                                    deldelYt[i])

        dG_dw = np.zeros((n, m, H))
        for i in range(n):
            for j in range(m):
                for k in range(H):
                    dG_dw[i, j, k] = dG_dYt[i]*dYt_dw[i, j, k]
                    for jj in range(m):
                        dG_dw[i, j, k] += \
                            dG_ddelYt[i, jj]*d2Yt_dwdx[i, j, jj, k]
                        for jjj in range(m):
                            dG_dw[i, j, k] += dG_ddeldelYt[i, jj, jjj] * \
                                d3Yt_dwdxdy[i, j, jj, jjj, k]

        dG_du = np.zeros((n, H))
        for i in range(n):
            for k in range(H):
                dG_du[i, k] = dG_dYt[i]*dYt_du[i, k]
                for j in range(m):
                    dG_du[i, k] += dG_ddelYt[i, j]*d2Yt_dudx[i, j, k]
                    for jj in range(m):
                        dG_du[i, k] += dG_ddeldelYt[i, j, jj] * \
                            d3Yt_dudxdy[i, j, jj, k]

        dG_dv = np.zeros((n, H))
        for i in range(n):
            for k in range(H):
                dG_dv[i, k] = dG_dYt[i]*dYt_dv[i, k]
                for j in range(m):
                    dG_dv[i, k] += dG_ddelYt[i, j]*d2Yt_dvdx[i, j, k]
                    for jj in range(m):
                        dG_dv[i, k] += dG_ddeldelYt[i, j, jj] * \
                            d3Yt_dvdxdy[i, j, jj, k]

        dE_dw = np.zeros((m, H))
        for j in range(m):
            for k in range(H):
                for i in range(n):
                    dE_dw[j, k] += 2*G[i]*dG_dw[i, j, k]

        dE_du = np.zeros(H)
        for k in range(H):
            for i in range(n):
                dE_du[k] += 2*G[i]*dG_du[i, k]

        dE_dv = np.zeros(H)
        for k in range(H):
            for i in range(n):
                dE_dv[k] += 2*G[i]*dG_dv[i, k]

        jac = np.hstack((dE_dw[0], dE_dw[1], dE_du, dE_dv))
        return E2, jac

    def __print_progress(self, xk):
        """Callback to print progress message from optimizer"""
        print('nit =', self.nit)
        self.nit += 1
        #    print('xk =', xk)


if __name__ == '__main__':

    # Create training data.
    nx = 11
    nt = 11
    # print('nx =', nx)
    # print('nt =', nt)
    xt = np.linspace(0, 1, nx)
    tt = np.linspace(0, 1, nt)
    # print('xt =', xt)
    # print('tt =', tt)
    x_train = np.array(list(zip(np.tile(xt, nt), np.repeat(tt, nx))))
    # print('x_train =', x_train)  # Each point is (x,t).
    n = len(x_train)
    # print('n =', n)

    # Options for minimize()
    options = {}
    # Set for convergence report.
    options['disp'] = True
    # print('options =', options)

    # Options for training
    opts = {}
    opts['debug'] = True
    opts['verbose'] = True
    # print('opts =', opts)

    # Test each training algorithm on each equation.
    # for pde in (
    #     'diff1d_0', 'diff1d_1',
    #     'diff1d_decrease_linear', 'diff1d_decrease',
    #     'diff1d_flat', 'diff1d_flat+decrease_linear', 'diff1d_flat+decrease',
    #     'diff1d_flat+increase_linear', 'diff1d_flat+increase',
    #     'diff1d_flat+sine_D1e-1', 'diff1d_flat+sine', 'diff1d_flat+slowincrease',
    #     'diff1d_increase_linear', 'diff1d_increase_sympy', 'diff1d_increase',
    #     'diff1d_rampdown', 'diff1d_rampup', 'diff1d_sine', 'diff1d_sinewave',
    #     'diff1d_triangle'
    #     ):
    for pde in ('diff1d_sine_orig',):
        print('Examining %s.' % pde)
        pde2diff1d = PDE2DIFF1D(pde)
        print(pde2diff1d)
        # m = 2
        net = NNPDE2DIFF1D(pde2diff1d)
        print(net)
        # Can't vectorize a function with a tuple argument.
        Ya = np.zeros(n)
        for i in range(n):
            Ya[i] = net.eq.Yaf(x_train[i])
        print('The analytical solution is:')
        print('Ya =', Ya.reshape(nt, nx))
        print()
        # if net.eq.delYaf is not None:
        #     delYa = np.zeros((n, m))
        #     for i in range(n):
        #         for j in range(m):
        #             delYa[i, j] = net.eq.delYaf[j](x_train[i])
        #     print('The analytical gradient is:')
        #     print('delYa =', delYa.reshape(nt, nx, m))
        #     print()
        # if net.eq.deldelYaf is not None:
        #     deldelYa = np.zeros((n, m, m))
        #     for i in range(n):
        #         for j in range(m):
        #             for jj in range(m):
        #                 deldelYa[i, j] = net.eq.deldelYaf[j][jj](x_train[i])
        #     print('The analytical Hessian is:')
        #     print('deldelYa =', deldelYa.reshape(nt, nx, m, m))
        #     print()
        # for trainalg in ('delta', 'Nelder-Mead', 'Powell',
        #                  'CG', 'BFGS', 'Newton-CG'):
        for trainalg in ('delta', ):
            print('Training using %s algorithm.' % trainalg)
            np.random.seed(0)
            try:
                net.train(x_train, trainalg=trainalg, opts=opts,
                          options=options)
            except (OverflowError, ValueError) as e:
                print('Error using %s algorithm on %s!' % (trainalg, pde))
                print(e)
                print()
                continue
            Yt = net.run(x_train)
            print('The trained solution is:')
            print('Yt =', Yt.reshape(nt, nx))
            print()
            print('The error in the trained solution is:')
            print('Yt - Ya =', (Yt - Ya).reshape(nt, nx))
            # print()
            # if net.eq.delYaf is not None:
            #     delYt = net.run_gradient(x_train)
            #     print('The trained gradient is:')
            #     print('delYt =', delYt.reshape(nt, nx, m))
            #     print()
            #     print('The error in the trained gradient is:')
            #     print('delYt - delYa =', (delYt - delYa).reshape(nt, nx, m))
            #     print()
            # if net.eq.deldelYaf is not None:
            #     deldelYt = net.run_hessian(x_train)
            #     print('The trained Hessian is:')
            #     print('deldelYt =', deldelYt.reshape(nt, nx, m, m))
            #     print()
            #     print('The error in the trained Hessian is:')
            #     print('deldelYt - deldelYa =',
            #           (deldelYt - deldelYa).reshape(nt, nx, m, m))
