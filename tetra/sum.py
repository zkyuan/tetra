import sys
from math import fsum
import time
from tetra.ksample import OptimizeGs, MakeEks, MakeXks
from tetra.submesh import MakeSubmesh, MakeTetra
from tetra.fermi import FindFermi
from tetra.weights import Weights
from tetra.numstates import NumStates

clock_start = None

def SumFn(n, Efn, Xfn, R, num_electrons, tolerance=None):
    '''Calculate the expectation value of Xfn over the Brillouin zone
    using the tetrahedron method. Returns the expectation value, as well as
    the submesh density n used to achieve the specified tolerance and the
    integration weights used (for use in additional summations by SumMesh).

    n = Brillouin zone submesh density (the total number of k-points sampled
    is (n+1)**3).

    Efn = a function E(k) which returns a list of the band energies at the
    Brillouin zone point k, with the returned list sorted in ascending order;
    k is expressed in the reciprocal lattice basis.

    Xfn = a function X(k) which returns a list of the values of the matrix
    elements of the operator X at k; the returned values are ordered in the
    same way as the band energies and k is expressed in the reciprocal
    lattice basis.

    R = a numpy matrix with rows given by the reciprocal lattice vectors.

    tolerance = summation error tolerance. If tolerance != None, the value
    of n is repeatedly doubled (starting from the given value) until the
    difference between iterations is less than tolerance.
    '''
    # Calculate the expectation value for a particular n.
    def doSum(this_n):
        G_order, G_neg, submesh, Eks, ws = _sum_setup(this_n, Efn, R, num_electrons)
        # Sample X.
        Xks = MakeXks(Xfn, submesh, G_order, G_neg)
        # Calculate sum.
        result = _SumByWeights(ws, Xks)
        return result, ws
    # Refine n until tolerance is met.
    return _sum_until_tol(doSum, n, tolerance)

def _sum_setup(n, Efn, R, num_electrons):
    '''Setup for summation common to SumFn and SumEnergy.
    '''
    # Get optimal reciprocal lattice orientation.
    G_order, G_neg = OptimizeGs(R)
    # Generate submesh and tetrahedra.
    submesh = MakeSubmesh(n)
    tetras = MakeTetra(n)
    tetras_size = sys.getsizeof(tetras)
    for t_i in range(len(tetras)):
        tetras_size += sys.getsizeof(tetras[t_i])
    #print("size of tetras = {}".format(str(tetras_size)))
    #print("size of tetras per submesh cell = {}".format(str(tetras_size / n**3)))
    submesh_size = sys.getsizeof(submesh)
    #print("size of submesh = {}".format(str(submesh_size)))
    #print("size of submesh per submesh cell = {}".format(str(submesh_size / n**3)))
    # Sample E.
    Eks = MakeEks(Efn, submesh, G_order, G_neg)
    print("In tetra.sum, at n = {} finished submesh sample; time = {}".format(str(n), str(time.time() - clock_start)))
    Eks_size = sys.getsizeof(Eks)
    for E_i in range(len(Eks)):
        Eks_size += sys.getsizeof(Eks[E_i])
    #print("size of Eks = {}".format(str(Eks_size)))
    #print("size of Eks per submesh cell = {}".format(str(Eks_size / n**3)))
    # Get Fermi energy by n(E_F) = num_electrons.
    E_Fermi = FindFermi(num_electrons, tetras, Eks)
    print("In tetra.sum, at n = {} got E_Fermi = {}; time = {}".format(str(n), str(E_Fermi), str(time.time() - clock_start)))
    # Get integration weights.
    ws = Weights(E_Fermi, tetras, Eks)
    ws_size = sys.getsizeof(ws)
    for w_i in range(len(ws)):
        ws_size += sys.getsizeof(ws[w_i])
    #print("size of ws = {}".format(str(ws_size)))
    #print("size of ws per submesh cell = {}".format(str(ws_size / n**3)))
    print(len(ws))
    print(len(ws[0]))
    return G_order, G_neg, submesh, Eks, ws

def _sum_until_tol(doSum, n, tolerance):
    last_result = None
    result, ws = doSum(n)
    if tolerance == None:
        return result, n, ws
    print("In tetra.sum, at n = {} got result = {}; time = {}".format(str(n), str(result), str(time.time() - clock_start)))
    try_n = 2*n
    while not _sum_finished(result, last_result, tolerance):
        last_result = result
        result, ws = doSum(try_n)
        print("In tetra.sum, at n = {} got result = {}; time = {}".format(str(try_n), str(result), str(time.time() - clock_start)))
        try_n = 2*try_n
    return result, try_n/2, ws

def _sum_finished(result, last_result, tolerance):
    if last_result == None:
        return False
    elif abs(result - last_result) > tolerance:
        return False
    else:
        return True

def _SumByWeights(weights, Xks):
    '''Calculate the expectation value <X> over the Brillouin zone
    using the tetrahedron method, given precalculated (k,n) integration
    weights and sampled values of X_n(k).

    weights = a list of integration weights w[n][j].

    Xks = a list of matrix elements X[j][n], with band indices ordered in the
    same way as the eigenstate energies. Xks can be generated by
    ksample.MakeXks.
    '''
    num_bands = len(weights)
    num_ks = len(weights[0])
    mult_vals = []
    # Accumulate list of values and then sum to take advantage of
    # floating-point error correction in fsum.
    for j in range(num_ks):
        for n in range(num_bands):
            mult_vals.append(Xks[j][n]*weights[n][j])
    return fsum(mult_vals)

def SumEnergy(n, Efn, R, num_electrons, tolerance=None):
    '''Calculate the expectation value of the energy over the Brillouin zone
    using the tetrahedron method. Returns the expectation value, as well as
    the submesh density n used to achieve the specified tolerance and the
    integration weights used (for use in additional summations by SumMesh).

    n = Brillouin zone submesh density (the total number of k-points sampled
    is (n+1)**3).

    Efn = a function E(k) which returns a list of the band energies at the
    Brillouin zone point k, with the returned list sorted in ascending order;
    k is expressed in the reciprocal lattice basis.

    R = a numpy matrix with rows given by the reciprocal lattice vectors.

    tolerance = summation error tolerance. If tolerance != None, the value
    of n is repeatedly doubled (starting from the given value) until the
    difference between iterations is less than tolerance.
    '''
    # Calculate the expectation value for a particular n.
    def doSum(this_n):
        G_order, G_neg, submesh, Eks, ws = _sum_setup(this_n, Efn, R, num_electrons)
        # Calculate sum.
        result = _SumByWeights(ws, Eks)
        return result, ws
    # Refine n until tolerance is met.
    global clock_start
    clock_start = time.time()
    return _sum_until_tol(doSum, n, tolerance)

def SumMesh(weights, n, Xfn, R):
    '''Calculate the expectation value <X> over the Brillouin zone
    using the tetrahedron method, given precalculated (k,n) integration
    weights.

    weights = a list of integration weights w_{nj}.

    n = Brillouin zone submesh density (the total number of k-points sampled
    is (n+1)**3).

    Xfn = a function X(k) which returns a list of the values of the matrix
    elements of the operator X at k; the returned values are ordered in the
    same way as the band energies and k is expressed in the reciprocal
    lattice basis.

    R = a numpy matrix with rows given by the reciprocal lattice vectors.

    The expectation value is given by:
        <X> = \sum_{j, n} X_n(k_j) w_{nj}
    (BJA94 Eq. 4).
    '''
    # Get optimal reciprocal lattice orientation.
    G_order, G_neg = OptimizeGs(R)
    # Generate submesh.
    submesh = MakeSubmesh(n)
    # Sample X.
    Xks = MakeXks(Xfn, submesh, G_order, G_neg)
    # Calculate sum.
    result = _SumByWeights(ws, Xks)
    return result
