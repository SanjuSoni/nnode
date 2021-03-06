"""
1-D diffusion PDE

The equation is defined on the domain [[0,1],[0,1]]. The initial
profile is flat (Y(x,0)=1), and the BC at x=0,1 are fixed at
Y(0,t)=Y(1,t)=1. The analytical solution is the same as the starting
profile.

The analytical form of the equation is:
  G(x,t,Y,delY,deldelY) = dY_dt - D*d2Y_dx2 = 0
"""


from inspect import getsource
import numpy as np


# Diffusion coefficient
D = 1


def Gf(xt, Y, delY, deldelY):
    """Code for differential equation"""
    (x, t) = xt
    (dY_dx, dY_dt) = delY
    ((d2Y_dxdx, d2Y_dxdt), (d2Y_dtdx, d2Y_dtdt)) = deldelY
    return dY_dt - D*d2Y_dxdx


def dG_dYf(xt, Y, delY, deldelY):
    """Partial of PDE wrt Y"""
    (x, t) = xt
    (dY_dx, dY_dt) = delY
    ((d2Y_dxdx, d2Y_dxdt), (d2Y_dtdx, d2Y_dtdt)) = deldelY
    return 0


def dG_dY_dxf(xt, Y, delY, deldelY):
    """Partial of PDE wrt dY/dx"""
    (x, t) = xt
    (dY_dx, dY_dt) = delY
    ((d2Y_dxdx, d2Y_dxdt), (d2Y_dtdx, d2Y_dtdt)) = deldelY
    return 0


def dG_dY_dtf(xt, Y, delY, deldelY):
    """Partial of PDE wrt dY/dt"""
    (x, t) = xt
    (dY_dx, dY_dt) = delY
    ((d2Y_dxdx, d2Y_dxdt), (d2Y_dtdx, d2Y_dtdt)) = deldelY
    return 1


dG_ddelYf = (dG_dY_dxf, dG_dY_dtf)


def dG_d2Y_dxdxf(xt, Y, delY, deldelY):
    """Partial of PDE wrt d2Y/dx2"""
    (x, t) = xt
    (dY_dx, dY_dt) = delY
    ((d2Y_dxdx, d2Y_dxdt), (d2Y_dtdx, d2Y_dtdt)) = deldelY
    return -D


def dG_d2Y_dxdtf(xt, Y, delY, deldelY):
    """Partial of PDE wrt d2Y/dxdt"""
    (x, t) = xt
    (dY_dx, dY_dt) = delY
    ((d2Y_dxdx, d2Y_dxdt), (d2Y_dtdx, d2Y_dtdt)) = deldelY
    return 0


def dG_d2Y_dtdxf(xt, Y, delY, deldelY):
    """Partial of PDE wrt d2Y/dtdx"""
    (x, t) = xt
    (dY_dx, dY_dt) = delY
    ((d2Y_dxdx, d2Y_dxdt), (d2Y_dtdx, d2Y_dtdt)) = deldelY
    return 0


def dG_d2Y_dtdtf(xt, Y, delY, deldelY):
    """Partial of PDE wrt d2Y/dt2"""
    (x, t) = xt
    (dY_dx, dY_dt) = delY
    ((d2Y_dxdx, d2Y_dxdt), (d2Y_dtdx, d2Y_dtdt)) = deldelY
    return 0


dG_ddeldelYf = ((dG_d2Y_dxdxf, dG_d2Y_dxdtf),
                (dG_d2Y_dtdxf, dG_d2Y_dtdtf))


def f0f(t):
    """Boundary condition at (x,t) = (0,t)"""
    return 1


def f1f(t):
    """Boundary condition at (x,t) = (1,t)"""
    return 1


def g0f(x):
    """Boundary condition at (x,t) = (x,0)"""
    return 1


def g1f(x):
    """Boundary condition at (x,t) = (x,1) NOT USED"""
    return None


bcf = ((f0f, f1f), (g0f, g1f))


def df0_dtf(t):
    """1st derivative of BC function at (x,t) = (0,t)"""
    return 0


def df1_dtf(t):
    """1st derivative of BC function at (x,t) = (1,t)"""
    return 0


def dg0_dxf(x):
    """1st derivative of BC function at (x,t) = (x,0)"""
    return 0


def dg1_dxf(x):
    """1st derivative of BC function at (x,t) = (x,0) NOT USED"""
    return None


bcdf = ((df0_dtf, df1_dtf), (dg0_dxf, dg1_dxf))


def d2f0_dt2f(t):
    """2nd derivative of BC function at (x,t) = (0,t)"""
    return 0


def d2f1_dt2f(t):
    """2nd derivative of BC function at (x,t) = (1,t)"""
    return 0


def d2g0_dx2f(x):
    """2nd derivative of BC function at (x,t) = (x,0)"""
    return 0


def d2g1_dx2f(x):
    """2nd derivative of BC function at (x,t) = (x,1)  NOT USED"""
    return None


bcd2f = ((d2f0_dt2f, d2f1_dt2f), (d2g0_dx2f, d2g1_dx2f))


def Yaf(xt):
    """Analytical solution"""
    (x, t) = xt
    return 1


def dYa_dxf(xt):
    """Analytical 1st partial wrt x"""
    return 0


def dYa_dtf(xt):
    """Analytical 1st partial wrt t"""
    return 0


delYaf = (dYa_dxf, dYa_dtf)


def d2Ya_dxdxf(xt):
    """Analytical d2Y/dxdx"""
    return 0


def d2Ya_dxdtf(xt):
    """Analytical d2Y/dxdt"""
    return 0


def d2Ya_dtdxf(xt):
    """Analytical d2Y/dtdx"""
    return 0


def d2Ya_dtdtf(xt):
    """Analytical d2Y/dtdt"""
    return 0


deldelYaf = ((d2Ya_dxdxf, d2Ya_dxdtf), (d2Ya_dtdxf, d2Ya_dtdtf))


if __name__ == '__main__':
    print(getsource(Gf))
    print('Gf([0, 0], 0, [0, 0], [[0, 0], [0, 0]]) = ',
          Gf([0, 0], 0, [0, 0], [[0, 0], [0, 0]]))
    print()
    print(getsource(dG_dYf))
    print('dG_dYf([0, 0], 0, [0, 0], [[0, 0], [0, 0]]) = ',
          dG_dYf([0, 0], 0, [0, 0], [[0, 0], [0, 0]]))
    print()
    print(getsource(dG_dY_dxf))
    print('dG_dY_dxf([0, 0], 0, [0, 0], [[0, 0], [0, 0]]) = ',
          dG_dY_dxf([0, 0], 0, [0, 0], [[0, 0], [0, 0]]))
    print()
    print(getsource(dG_dY_dtf))
    print('dG_dY_dtf([0, 0], 0, [0, 0], [[0, 0], [0, 0]]) = ',
          dG_dY_dtf([0, 0], 0, [0, 0], [[0, 0], [0, 0]]))
    print()
    print(getsource(dG_d2Y_dxdxf))
    print('dG_d2Y_dxdxf([0, 0], 0, [0, 0], [[0, 0], [0, 0]]) = ',
          dG_d2Y_dxdxf([0, 0], 0, [0, 0], [[0, 0], [0, 0]]))
    print()
    print(getsource(dG_d2Y_dxdtf))
    print('dG_d2Y_dxdtf([0, 0], 0, [0, 0], [[0, 0], [0, 0]]) = ',
          dG_d2Y_dxdtf([0, 0], 0, [0, 0], [[0, 0], [0, 0]]))
    print()
    print(getsource(dG_d2Y_dtdxf))
    print('dG_d2Y_dtdxf([0, 0], 0, [0, 0], [[0, 0], [0, 0]]) = ',
          dG_d2Y_dtdxf([0, 0], 0, [0, 0], [[0, 0], [0, 0]]))
    print()
    print(getsource(dG_d2Y_dtdtf))
    print('dG_d2Y_dtdtf([0, 0], 0, [0, 0], [[0, 0], [0, 0]]) = ',
          dG_d2Y_dtdtf([0, 0], 0, [0, 0], [[0, 0], [0, 0]]))
    print()
    print(getsource(f0f))
    print('f0f(0) = ', f0f(0))
    print()
    print(getsource(f1f))
    print('f1f(0) = ', f1f(0))
    print()
    print(getsource(g0f))
    print('g0f(0) = ', g0f(0))
    print()
    print(getsource(g1f))
    print('g1f(0) = ', g1f(0))
    print()
    print(getsource(df0_dtf))
    print('df0_dtf(0) = ', df0_dtf(0))
    print()
    print(getsource(df1_dtf))
    print('df1_dtf(0) = ', df1_dtf(0))
    print()
    print(getsource(dg0_dxf))
    print('dg0_dxf(0) = ', dg0_dxf(0))
    print()
    print(getsource(dg1_dxf))
    print('dg1_dxf(0) = ', dg1_dxf(0))
    print()
    print(getsource(d2f0_dt2f))
    print('d2f0_dt2f(0) = ', d2f0_dt2f(0))
    print()
    print(getsource(d2f1_dt2f))
    print('d2f1_dt2f(0) = ', d2f1_dt2f(0))
    print()
    print(getsource(d2g0_dx2f))
    print('d2g0_dx2f(0) = ', d2g0_dx2f(0))
    print()
    print(getsource(d2g1_dx2f))
    print('d2g1_dx2f(0) = ', d2g1_dx2f(0))
    print()
    print(getsource(Yaf))
    print('Yaf([0, 0]) = ', Yaf([0, 0]))
    print()
    print(getsource(dYa_dxf))
    print('dYa_dxf([0, 0]) = ', dYa_dxf([0, 0]))
    print()
    print(getsource(dYa_dtf))
    print('dYa_dtf([0, 0]) = ', dYa_dtf([0, 0]))
    print()
    print(getsource(d2Ya_dxdxf))
    print('d2a_dxdxf([0, 0]) = ', d2Ya_dxdxf([0, 0]))
    print()
    print(getsource(d2Ya_dxdtf))
    print('d2a_dxdtf([0, 0]) = ', d2Ya_dxdtf([0, 0]))
    print()
    print(getsource(d2Ya_dtdxf))
    print('d2a_dtdxf([0, 0]) = ', d2Ya_dtdxf([0, 0]))
    print()
    print(getsource(d2Ya_dtdtf))
    print('d2a_dtdtf([0, 0]) = ', d2Ya_dtdtf([0, 0]))

    assert np.isclose(f0f(0), g0f(0))
    assert np.isclose(f1f(0), g0f(1))
    assert np.isclose(Yaf([0, 0]), f0f(0))
    assert np.isclose(Yaf([0, 1]), f0f(1))
    assert np.isclose(Yaf([1, 0]), f1f(0))
    assert np.isclose(Yaf([1, 1]), f1f(1))
    assert np.isclose(Yaf([0.5, 0]), g0f(0.5))
