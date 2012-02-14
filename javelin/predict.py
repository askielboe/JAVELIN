from gp import Mean, Covariance, observe, Realization, GPutils
from gp import NearlyFullRankCovariance, FullRankCovariance
from cholesky_utils import cholesky, trisolve, chosolve, chodet, chosolve_from_tri, chodet_from_tri
import numpy as np
from numpy.random import normal, multivariate_normal
from cov import get_covfunc_dict
from spear import spear


""" Generate random realizations based on the covariance function.
"""

class PredictRmap(object):
    """ Predict light curves for spear.
    """
    def __init__(self, zydata=None, **covparams):
        self.zydata = zydata
        self.covparams = covparams
        self.jd = self.zydata.jarr
        # has to be the true mean instead of the samle mean
        self.md = self.zydata.marr
        self.id = self.zydata.iarr
        self.vd = np.power(self.zydata.earr, 2.)
        # preparation
        self._get_covmat()
        self._get_cholesky()
        self._get_cplusninvdoty()

    def generate(self, zylclist) :
        """ presumably zylclist has our input j, e, and i, and the values in m
         should be the mean."""
        nlc = len(zylclist)
        jlist = []
        mlist = []
        elist = []
        ilist = []
        for ilc, lclist in enumerate(zylclist):
            if (len(lclist) == 3):
                jsubarr, msubarr, esubarr = [np.array(l) for l in lclist]
                if (np.min(msubarr) != np.max(msubarr)) : 
                    print("WARNING: input zylclist has inequal m elements in\
                           light curve %d, please make sure the m elements\
                           are filled with the desired mean of the mock\
                           light curves, now reset to zero"%ilc)
                    msubarr = msubarr * 0.0
                nptlc = len(jsubarr)
                # sort the date, safety
                p = jsubarr.argsort()
                jlist.append(jsubarr[p])
                mlist.append(msubarr[p])
                elist.append(esubarr[p])
                ilist.append(np.zeros(nptlc, dtype="int")+ilc+1)
        for ilc in xrange(nlc) :
            m, v = self.mve_var(jlist[ilc], ilist[ilc])
            ediag = np.diag(e*e)
            temp1 = np.repeat(e, nwant).reshape(nwant,nwant)
            temp2 = (temp1*temp1.T - ediag)*errcov
            ecovmat = ediag + temp2
            mlist[ilc] = mlist[ilc] + multivariate_normal(np.zeros(nwant), ecovmat)
            #FIXME

        pass

    def mve_var(self, jwant, iwant):
        return(self._fastpredict(jwant, iwant)

    def _get_covmat(self) :
        self.cmatrix = spear(self.jd,self.jd,self.id,self.id, **self.covparams)
        print("covariance matrix calculated")

    def _get_cholesky(self) :
        self.U = cholesky(self.cmatrix, nugget=self.vd, inplace=True, raiseinfo=True)
        print("covariance matrix decomposed and updated by U")

    def _get_cplusninvdoty(self) :
        # now we want cpnmatrix^(-1)*mag = x, which is the same as
        #    mag = cpnmatrix*x, so we solve this equation for x
        self.cplusninvdoty = chosolve_from_tri(self.U, self.md, nugget=None, inplace=False)

    def _fastpredict(self, jw, iw) :
        """ jw : jwant
            iw : iwant
        """
        mw = np.zeros_like(jw)
        vw = np.zeros_like(jw)
        for i, (jwant, iwant) in enumerate(zip(jw, iw)):
            covar = spear(jwant,self.jd,iwant,self.id, **self.covparams)
            cplusninvdotcovar = chosolve_from_tri(self.U, covar, nugget=None, inplace=False)
            vw[i] = spear(jwant, jwant, iwant, iwant, **self.covparams)
            mw[i] = np.dot(covar, cplusninvdoty)
            vw[i] = vw[i] - np.dot(covar, cplusninvdotcovar)
        return(mw, vw)



        




class Predict(object):
    """
    Predict light curves at given input epoches in two possible scenarios.
    1) random realizations of the underlying process defined by both 
    mean and covariance.
    2) constrained realizations of the underlying process defined by 
    both mean and covariance, and observed data points.
    """
    def __init__(self, lcmean=0.0, jdata=None, mdata=None, edata=None,
            covfunc="pow_exp", rank="Full", **covparams):
        try :
            const = float(lcmean)
            meanfunc = lambda x: const*(x*0.0+1.0)
            self.M = Mean(meanfunc)
        except ValueError:
            if isinstance(lcmean, Mean):
                self.M = lcmean
            else:
                raise RuntimeError("lcmean is neither a Mean obj or a const")
        
        covfunc_dict = get_covfunc_dict(covfunc, **covparams)
        if rank is "Full" :
            self.C  = FullRankCovariance(**covfunc_dict)
        elif rank is "NearlyFull" :
            self.C  = NearlyFullRankCovariance(**covfunc_dict)

        if ((jdata is not None) and (mdata is not None) and (edata is not None)):
            print("Constrained Realization...")
            observe(self.M, self.C, obs_mesh=jdata, obs_V = edata, obs_vals = mdata)
        else:
            print("No Data Input or Some of jdata/mdata/edata Are None")
            print("Unconstrained Realization...")

    def generate(self, jwant, ewant=0.0, nlc=1, errcov=0.0):
        if (np.min(ewant) < 0.0):
            raise RuntimeError("ewant should be either 0  or postive")
        elif np.alltrue(ewant==0.0):
            set_error_on_mocklc = False
        else:
            set_error_on_mocklc = True

        nwant = len(jwant)

        if np.isscalar(ewant):
            e = np.zeros(nwant) + ewant
        elif len(ewant) == nwant:
            e = ewant
        else:
            raise RuntimeError("ewant should be either a const or array with same shape as jwant")

        ediag = np.diag(e*e)
        temp1 = np.repeat(e, nwant).reshape(nwant,nwant)
        temp2 = (temp1*temp1.T - ediag)*errcov
        ecovmat = ediag + temp2

        if nlc == 1:
            f = Realization(self.M, self.C)
            mwant = f(jwant)
            if set_error_on_mocklc:
                mwant = mwant + multivariate_normal(np.zeros(nwant), ecovmat)
            return(mwant)
        else:
            mwant_list = []
            for i in xrange(nlc):
                f = Realization(self.M, self.C)
                mwant = f(jwant)
                mwant = mwant + multivariate_normal(np.zeros(nwant), ecovmat)
                mwant_list.append(mwant)
            return(mwant_list)

    def mve_var(self, jwant):
        m, v = GPutils.point_eval(self.M, self.C, jwant)
        return(m,v)




def test_Predict():
    from pylab import fill, plot, show
    jdata = np.array([25., 100, 175.])
    mdata = np.array([0.7, 0.1, 0.4])
    edata = np.array([0.07, 0.02, 0.05])
    j = np.arange(0, 200, 1)
    P = Predict(jdata=jdata, mdata=mdata, edata=edata, covfunc="pow_exp",
            tau=10.0, sigma=0.2, nu=1.0)
    mve, var = P.mve_var(j)
    sig = np.sqrt(var)
    x=np.concatenate((j, j[::-1]))
    y=np.concatenate((mve-sig, (mve+sig)[::-1]))
    fill(x,y,facecolor='.8',edgecolor='1.')
    plot(j, mve, 'k-.')
    mlist = P.generate(j, nlc=3, ewant=0.0)
    for m in mlist:
        plot(j, m)
    show()

def test_simlc():
    covfunc = "kepler_exp"
    tau, sigma, nu = (10.0, 2.0, 0.2)
    j = np.linspace(0., 200, 256)
    lcmean = 10.0
    emean  = lcmean*0.05
    print("observed light curve mean mag is %10.3f"%lcmean)
    print("observed light curve mean err is %10.3f"%emean)
    P = Predict(lcmean=lcmean, covfunc=covfunc, tau=tau, sigma=sigma, nu=nu)
    ewant = emean*np.ones_like(j)
    mwant = P.generate(j, nlc=1, ewant=ewant, errcov=0.0)
    np.savetxt("mock.dat", np.vstack((j, mwant, ewant)).T)

if __name__ == "__main__":    
#    test_simlc()
    test_Predict()
