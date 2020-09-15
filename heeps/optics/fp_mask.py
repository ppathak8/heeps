from .lens import lens
from .vortex_init import vortex_init
import os.path
import numpy as np
from heeps.util.img_processing import resize_img, pad_img
from astropy.io import fits
import proper

def fp_mask(wf, conf, verbose=False):

    # case 1: vortex coronagraphs
    if conf['mode'] in ['CVC', 'RAVC'] and conf['vc_charge'] != 0:
        if verbose is True:
            print('Apply Vortex phase mask')                        
        # load vortex calibration files
        beam_ratio = conf['npupil']/conf['ngrid']*(conf['diam_ext']/conf['pupil_img_size'])
        calib = '%s_%s_%3.4f'%(conf['vc_charge'], conf['ngrid'], beam_ratio)
        if conf.get('vortex_calib') != calib:
            conf = vortex_init(conf, calib=calib, verbose=verbose)
        # propagate to vortex
        lens(wf, conf['focal'])
        # apply vortex
        scale_psf = wf._wfarr[0,0]/conf['psf_num'][0,0]
        wf_corr = (conf['psf_num']*conf['vvc'] - conf['perf_num'])*scale_psf
        wf._wfarr = wf._wfarr*conf['vvc'] - wf_corr
        # propagate to lyot stop
        lens(wf, conf['focal'])
        if verbose is True:
            print('   charge=%s, ngrid=%s, beam_ratio=%3.4f'%\
                (conf['vc_charge'], conf['ngrid'], beam_ratio))
            print('')

    # TODO: cleanup CLC
    
    # case 2: classical Lyot
    elif conf['mode'] in ['CLC']:
        if verbose is True:
            print('Apply Classical Lyot mask\n')        
        f_lens = conf['focal']
        beam_ratio = conf['beam_ratio']
        CLC_diam = conf['CLC_diam'] # classical lyot diam in lam/D (default to 4)
        gridsize = conf['gridsize']
        tmp_dir = conf['temp_dir']
        
        # propagate to lyot mask
        lens(wf, conf['focal'])
        
        # create or load the classical Lyot mask
        calib = str(CLC_diam)+str('_')+str(int(beam_ratio*100))+str('_')+str(gridsize)
        my_file = os.path.join(tmp_dir, 'clc_'+calib+'.fits')
        if not os.path.isfile(my_file):
            # calculate exact size of Lyot mask diameter, in pixels
            Dmask = CLC_diam/beam_ratio
            # oversample the Lyot mask (round up)
            samp = 100
            ndisk = int(samp*np.ceil(Dmask))
            ndisk = ndisk + 1 if not ndisk % 2 else ndisk # must be odd
            # find center
            cdisk = int((ndisk - 1)/2)
            # calculate the distances to center
            xy = range(-cdisk, cdisk + 1)
            x,y = np.meshgrid(xy, xy)
            dist = np.sqrt(x**2 + y**2)
            # create the Lyot mask
            mask = np.zeros((ndisk, ndisk))
            mask[np.where(dist > samp*Dmask/2)] = 1
            # resize to Lyot mask real size, and pad with ones
            mask = resize_img(mask, int(ndisk/samp))
            mask = pad_img(mask, gridsize, 1)
            # write mask
            fits.writeto(my_file, mask)
        else:
            mask = fits.getdata(my_file)
        
        # apply lyot mask
        mask = proper.prop_shift_center(mask)
        wf._wfarr.real *= mask
        
        # propagate to lyot stop
        lens(wf, conf['focal'])

    return wf