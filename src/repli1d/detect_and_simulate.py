# detect peak


from repli1d.analyse_RFD import detect_peaks, compare, smooth, mapboth, get_codire, cut_larger_than
from repli1d.profile_generation import  generate_slow_background, generate_group_genes
from repli1d.fast_sim import get_fast_MRT_RFDs
from repli1d.expeData import replication_data
from repli1d.single_mol_analysis import compute_info, compute_real_inter_ori ,compute_mean_activated_ori
from repli1d.retrieve_marks import norm2
import sys
from repli1d.visu_browser import plotly_blocks
import pylab
import numpy as np
import pandas as pd
from scipy import stats
import pickle
import os
import json

import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--start', type=int, default=5000)
parser.add_argument('--end', type=int, default=120000)
parser.add_argument('--ch', type=int, default=1)
parser.add_argument('--resolution', type=int, default=5)
parser.add_argument('--resolutionpol', type=int, default=5)
parser.add_argument('--ndiff', type=float, default=60)
parser.add_argument('--dori', type=float, default=20)
parser.add_argument('--percentile', type=int, default=82)
parser.add_argument('--cell', type=str, default="K562")
parser.add_argument('--cellseq', type=str, default=None)
parser.add_argument('--visu', action="store_true")
parser.add_argument('--name', type=str, default="tmp.html")
parser.add_argument('--nsim', type=int, default=200)
parser.add_argument('--gsmooth', type=int, default=5)
parser.add_argument('--smoothpeak', type=int, default=5)
# parser.add_argument('--dataroot', type=str, default="ROOT = "../DNaseI/notebooks/exploratory/"")

parser.add_argument('--signal', type=str, default="peak")
parser.add_argument('--input', action="store_true")
parser.add_argument('--correct', action="store_true")
parser.add_argument('--continuous', action="store_true")
parser.add_argument('--cascade', action="store_true")
parser.add_argument('--single', action="store_true")
parser.add_argument('--noise', type=float, default=.1)
parser.add_argument('--kon', type=float, default=.005)
parser.add_argument('--fsmooth', type=int, default=1)
parser.add_argument('--n_jobs', type=int, default=8)
parser.add_argument('--exp_factor', type=int, default=4)
parser.add_argument('--nMRT', type=int, default=6)


parser.add_argument('--smoothw', type=int, default=None)

parser.add_argument('--fspeed', type=float, default=.3)  # time to go on one bin
parser.add_argument('--comp', type=str, default=None)
parser.add_argument('--recomp', action="store_true")
parser.add_argument('--wholecell', action="store_true")
parser.add_argument('--dec', type=int, default=None)
parser.add_argument('--experimental',  action="store_true")
parser.add_argument('--nntest',  action="store_true")
parser.add_argument('--save',  action="store_true")
parser.add_argument('--only_one',  action="store_true")  # Onli visu ch1

parser.add_argument("--cutholes",type=int,default=None) #In Mb
parser.add_argument('--maxch', type=int, default=None)  #To test whole cell
parser.add_argument('--forkseq',  action="store_true")
parser.add_argument('--stalling',type=str,default=None)
parser.add_argument('--expbg',  action="store_true")
parser.add_argument('--randomlarge',  action="store_true")
parser.add_argument('--filter_termination',type=int,default=None)
parser.add_argument('--introduction_time',type=int,default=None)
parser.add_argument('--randomprofile', type=float, default=0)  # time to go on one bin
parser.add_argument('--reverse_profile',  action="store_true")
parser.add_argument('--extra_param',type=str,default=None)






# Cell is use to get signal
# comp is use to compare

args = parser.parse_args()

start = args.start
end = args.end
ch = args.ch
cell = args.cell
resolution_polarity = args.resolutionpol
resolution = args.resolution
exp_factor = args.exp_factor
percentile = args.percentile
fork_speed = args.fspeed
kon = args.kon
ndiff = args.ndiff
nsim = args.nsim
comp = args.comp
noise = args.noise

if args.extra_param != None:
    with open(args.extra_param,"r") as f:
        param = json.load(f)
        ndiff = param["ndiff"]
        noise = param["noise"]

        print("Extra",ndiff,noise)


if comp is None:
    comp = cell

if args.cellseq is None:
    cellseq = comp
else:
    cellseq = args.cellseq

expRFD = "OKSeq"
if args.forkseq:
    expRFD = "ForkSeq"



tot_diff = 0
if not args.wholecell:
    list_task = [[start, end, ch, int(ndiff)]]
    tot_diff += list_task[0][-1]
else:

    if "Yeast" not in cell:
        chromlength = [248956422, 242193529, 198295559, 190214555, 181538259,
                       170805979, 159345973, 145138636, 138394717,
                       133797422, 135086622, 133275309, 114364328, 107043718,
                       101991189, 90338345, 83257441,
                       80373285, 58617616, 64444167, 46709983, 50818468]
    if "Yeast" in cell:
        index = pd.read_csv("../DNaseI/data/external/Yeast-MCM/1kb/index.csv",sep="\t")
        chromlength = [np.sum(index.chrom == "chr%i" %i)*1000 for i in range(1,17)]
        print(chromlength)
    chn = range(1, len(chromlength) + 1)
    if args.nntest:
        chromlength = chromlength[-2:]
        chn = chn[-2:]
    list_task = []
    for ich,(ch, l) in enumerate(zip(chn, chromlength)):
        print(ch, l)
        Start = 0
        End = l//1000
        list_task.append([Start, End, ch, int(ndiff*End/1000)])

        tot_diff += list_task[ich][-1]
        if args.maxch is not None and ich >= args.maxch -1:
            break


print(noise)

GData = []

ldatg = []
gMRT = []
gRFD = []
gMRTe = []
gRFDe = []
codire = []
d3pl = []

dir = os.path.split(args.name)[0]
if dir != '':
    os.makedirs(dir, exist_ok=True)

for start, end, ch, ndiff in list_task:

    name_w = args.name+"_%i_%i_%i" % (ch, start, end)

    if args.signal in ["peak","peakRFDonly"]:
        print("Percentile", percentile, args.recomp, args.gsmooth, args.dec, args.smoothpeak)
        rfd_only=False
        if args.signal == "peakRFDonly":
            rfd_only=True
        x, d3p = detect_peaks(start, end, ch,
                              resolution_polarity=resolution_polarity,
                              exp_factor=exp_factor,
                              percentile=percentile, cell=cell, cellMRT=comp, cellRFD=cellseq, nanpolate=True,
                              recomp=args.recomp, gsmooth=args.gsmooth, dec=args.dec, fsmooth=args.smoothpeak,
                              expRFD=expRFD,rfd_only=rfd_only)

        if resolution != resolution_polarity:
            x, d3p0 = detect_peaks(start, end, ch,
                                   resolution_polarity=resolution,
                                   exp_factor=exp_factor,
                                   percentile=percentile, cell=cell, cellMRT=comp, cellRFD=cellseq, nanpolate=True,
                                   recomp=args.recomp, gsmooth=args.gsmooth)

            f = resolution // resolution_polarity
            #ext = mapboth(d3p0, d3p, f)
            #d3p[ext == 0] = 0

            for i in range(len(d3p0)):
                d3p0[i] = sum(d3p[i*f:min(i*f+1, len(d3p))])

            d3p = d3p0

        if args.correct:
            x, DNaseI = replication_data(cell, "DNaseI", chromosome=ch,
                                         start=start, end=end,
                                         resolution=resolution, raw=False)
            x, CNV = replication_data(cell, "CNV", chromosome=ch,
                                      start=start, end=end,
                                      resolution=resolution, raw=False)
            CNV[CNV == 0] = 2
            DNaseI[np.isnan(DNaseI)] = 0
            DNaseI /= CNV

            DNaseIsm = smooth(DNaseI, 100)
            DNaseIsm /= np.mean(DNaseIsm)

            d3p *= DNaseIsm

            d3p[np.isnan(d3p)] = 0
            d3p[np.isinf(d3p)] = 0
            print(np.sum(np.isnan(d3p)))
            # pylab.plot(d3p)
            # pylab.show()

    elif args.signal == "ARSpeak":

        x, d3p = replication_data(cell, "ARS", chromosome=ch,
                                  start=start, end=end,
                                  resolution=resolution, raw=False, smoothf=args.smoothw)

        if args.correct:
            x, CNV = replication_data(cell, "CNV", chromosome=ch,
                                      start=start, end=end,
                                      resolution=resolution, raw=False)
            CNV[CNV == 0] = 2
            d3p /= CNV
        d3p[np.isnan(d3p)] = 0

        x, d3peak = detect_peaks(start, end, ch,
                              resolution_polarity=resolution_polarity,
                              exp_factor=exp_factor,
                              percentile=percentile, cell=cell, cellMRT=comp, cellRFD=cellseq, nanpolate=True,
                              recomp=args.recomp, gsmooth=args.gsmooth, dec=args.dec, fsmooth=args.smoothpeak,
                              expRFD=expRFD)

        d3p = d3p*d3peak


    elif args.signal == "DNaseIRandom":

        x, d3p0 = replication_data(cell, "DNaseI", chromosome=ch,
                                  start=start, end=end,
                                  resolution=resolution, raw=False, smoothf=args.smoothw)



        d3p = np.zeros_like(d3p0)

        for iv,v in enumerate(d3p0):
            if v != 0 and ~np.isnan(v):
                pos = np.random.randint(max(0,iv-40),min(iv+40,len(d3p)-1))

                d3p[pos] = v

    elif args.signal == "DNaseIFlat":

        x, d3p0 = replication_data(cell, "DNaseI", chromosome=ch,
                                  start=start, end=end,
                                  resolution=resolution, raw=False, smoothf=args.smoothw)



        d3p0[np.isnan(d3p0)] = 0

        d3p = d3p0/(np.cos(2*np.pi*np.arange(len(d3p0))/5000)+1.1)
        #d3p[len(d3p)//2:] = d3p[len(d3p)//2:]/100
        """
        for iv,v in enumerate(d3p0):
            if v != 0 and ~np.isnan(v):
                #pos = np.random.randint(max(0,iv-40),min(iv+40,len(d3p)-1))

                d3p[iv] = d3p0[iv] /np.nansum(d3p0[max(0,iv-40):min(iv+40,len(d3p)-1)])"""




    else:
        x, d3p = replication_data(cell, args.signal, chromosome=ch,
                                  start=start, end=end,
                                  resolution=resolution, raw=False, smoothf=args.smoothw)

        if args.correct:

            x, CNV = replication_data(cell, "CNV", chromosome=ch,
                                      start=start, end=end,
                                      resolution=resolution, raw=False)
            CNV[CNV == 0] = 2
            d3p /= CNV
        d3p[np.isnan(d3p)] = 0

    d3p /= np.mean(d3p[d3p != 0])
    std = np.std(d3p[d3p != 0])
    if std == 0:
        std = 1
    d3p = norm2(d3p, mean=1, std=std, cut=15)[0]



    if args.expbg:
        _, mrt_tmp = replication_data(cell, "MRT", chromosome=ch,

                                  start=start, end=end,
                                  resolution=10, raw=False)
        mrt_tmp[np.isnan(mrt_tmp)] = 0
        mrte = mapboth(mrt_tmp,d3p,2,pad=True)
        assert mrte.shape == d3p.shape
        mrte[np.isnan(mrte)] = 1
        #print( mrte.shape,d3p.shape)
        #exit()
        bg = np.exp(-mrte/2)
        bg /= np.sum(bg)
        #print("Sum",np.sum(d3p ) , np.sum( np.sum(d3p) * bg * 0.1))
        d3p =  d3p + np.sum(d3p) * bg * 0.1
        #d3p = mrte

        #print(d3p.shape)
        #exit()


    if args.randomlarge:
        _, mrt_tmp = replication_data(cell, "MRT", chromosome=ch,

                                  start=start, end=end,
                                  resolution=10, raw=False)

        mrt_tmp[np.isnan(mrt_tmp)] = 0
        #mrte = mapboth(mrt_tmp,d3p,2,pad=True)
        #mrte[mrte > 0.6] = 1
        #mrte[mrte <= 0.6] = 0
        """
        _, rfd_tmp = replication_data(cell, "OKSeq", chromosome=ch,

                                  start=start, end=end,
                                  resolution=5, raw=False)
        rfd_tmp[np.isnan(rfd_tmp)]=0
        rfd_tmp = smooth(rfd_tmp,10)
        rfd_tmp[rfd_tmp<=0] = 0
        d3p = mrte * rfd_tmp"""


        #zone = np.nonzero(mrte)[0]

        meanp = np.mean(d3p[d3p!=0])
        from scipy import signal
        #d3p = np.zeros_like(d3p)
        for i in np.random.choice(range(len(d3p)),10):
            size = np.random.randint(20,30)
            print("Adding")
            d3p[i-size:i+size] +=  signal.gaussian(2*size,std=size//3)  *meanp*np.random.rand()


    if args.randomprofile != 0:

        bg = generate_slow_background(np.arange(len(d3p)))
        d3p = generate_group_genes(bg, coverage=args.randomprofile)



    stall = args.stalling
    if stall is not None:

        """
        if "random" in stall:
            p = int(stall.split("_")[1])
            stallp = np.ones_like(d3p,dtype=np.int)
            #print(np.random.randint(0,len(d3p),int(len(d3p)*p)))
            tot = int(len(d3p)*p*0.01)
            if tot > 1:
                for pos in  np.random.randint(0,len(d3p),tot):
                    stallp[pos] = np.random.randint(1,5)
        """
        stallp = np.ones_like(d3p, dtype=np.int)
        _, stall = replication_data(cell, "G4", chromosome=ch,

                                      start=start, end=end,
                                      resolution=5, raw=False)
        stall[np.isnan(stall)] = 0

        stall = np.array(stall, dtype=np.int)
        print("SumSTall",np.sum(stall))
        stallp += stall

    else:
        stallp = []



    d3pl.append([x, d3p,stallp])


if "Yeast" not in cell:
    mrt_res = 10
    masking = 200
    propagateNan = False
    #ok_seq_res = resolution

else:
    mrt_res = resolution
    masking = 25
    propagateNan = False
    #ok_seq_res = resolution

lres = []

Masks_cut = []
Segments = []



print(d3pl,len(d3pl[0][1]))

if args.cutholes:
    #Get masks and recompute ndiffs:
    tot_diff = 0

    for i,((start,end,ch,diff),(x,d3p,stallp)) in enumerate(zip(list_task,d3pl)):

        #To get masks
        MRTpearson, MRTstd, MRT, [mask_MRT, l] = compare(
            d3p[::mrt_res // resolution], "MRT", comp, res=mrt_res, ch=ch, start=start, end=end, return_exp=True, trunc=True,
            pad=True, return_mask=True,masking=masking,propagateNan=propagateNan)

        RFDpearson, RFDstd, RFD, [mask_RFD, l] = compare(d3p, expRFD, cellseq, res=resolution, ch=ch,
                                                         start=start, end=end, return_exp=True, rescale=1 / resolution,
                                                         trunc=True, pad=True, return_mask=True, smoothf=args.fsmooth,
                                                         masking=masking,propagateNan=propagateNan)

        mask_MRTh = mapboth(mask_MRT,mask_RFD,2,pad=True)

        whole_mask = mask_MRTh & mask_RFD

        segment = cut_larger_than(whole_mask,args.cutholes//resolution)
        Segments.append(segment)
        #print(i,segment)

        proportion_false = 0

        for start_seg, end_seg, keep in zip(segment["start"], segment["end"], segment["keep"]):
            if not keep:
                proportion_false += end_seg-start_seg
        proportion_false /= len(d3p)
        #print("Ndiff",list_task[i][-1])
        list_task[i][-1] = int(list_task[i][-1] * (1-proportion_false)) # Ndiff proportion

        tot_diff += list_task[i][-1]

print("Total number of ff ",tot_diff)

if args.cascade:
    cascade = { "infl":100,"amount":1000,
                "down":1,"damount":1 / 10000.}
else:
    cascade = args.cascade

if not args.experimental:
    # Independent simulation for each chromosome
    from repli1d.fast_sim import get_fast_MRT_RFDs

    for (start, end, ch, ndiff), [x, d3p,stallp] in zip(list_task, d3pl):

            # simulate
        lres.append(get_fast_MRT_RFDs(
            nsim, d3p+np.ones_like(d3p)*np.sum(d3p)*noise/len(d3p), ndiff, kon=kon,
            fork_speed=fork_speed, dori=args.dori*5/resolution, single_mol_exp=args.single, continuous=args.continuous, cascade=cascade))
    #print("check", np.sum(d3p), np.sum(np.ones_like(d3p)*np.sum(d3p)*0.1/len(d3p)))

        print("End Simeeeeuuuuuuuuuuuuuuuuuuuu")
else:
    from repli1d.fast_sim_break import get_fast_MRT_RFDs

    #print(d3p)
    if args.cutholes is None:

        bigch = np.concatenate([d3p for x, d3p,stallp in d3pl])



        if stall is not None:
            bigstallp = np.concatenate([stallp for x, d3p,stallp in d3pl])
        else:
            bigstallp = []




        breaks = []
        shift = 0
        tot_diff = 0
        sp = []  # To split the result
        for (start, end, ch, ndiff), [x, d3p,stallp] in zip(list_task, d3pl):
            breaks.append([shift, shift+len(d3p)])
            sp.append(shift+len(d3p))

            shift += len(d3p)
            tot_diff += ndiff
    else:
        bigch = []
        bigstallp = []

        breaks = []
        shift = 0
        tot_diff = 0
        sp = []  # To split the result
        split_ch = []
        for index_ch,((start, end, ch, ndiff), [x, d3p,stallp],segment) in enumerate(zip(list_task, d3pl,Segments)):
            for start_seg, end_seg, keep in zip(segment["start"], segment["end"], segment["keep"]):
                size_seg = end_seg-start_seg
                if keep:
                    breaks.append([shift, shift + size_seg])
                    sp.append(shift + size_seg)
                    shift += size_seg
                    bigch.append(d3p[start_seg:end_seg])
                    if stall is not None:
                        bigstallp.append(stallp[start_seg:end_seg])

                    split_ch.append([start_seg, end_seg,index_ch])
            tot_diff += ndiff

            lres.append([np.zeros_like(d3p)+np.nan,
                         np.zeros_like(d3p)+np.nan,
                         np.zeros_like(d3p)+np.nan,None,[],[],[],
                         np.zeros_like(d3p)+np.nan,
                         np.zeros_like(d3p)+np.nan,[],
                         np.zeros_like(d3p)+np.nan])
        bigch = np.concatenate(bigch)
        if stall is not None:
            bigstallp = np.concatenate(bigstallp)

    print(bigstallp)

    if args.reverse_profile:
        bigch = np.max(bigch) - bigch


    d3p = bigch
    res = get_fast_MRT_RFDs(
        nsim, d3p+np.ones_like(d3p)*np.sum(d3p)*noise/len(d3p), tot_diff, kon=kon,
        fork_speed=fork_speed, dori=args.dori*5/resolution,
        single_mol_exp=args.single, continuous=args.continuous,
        cascade=cascade, breaks=breaks, n_jobs=args.n_jobs,
        binsize=resolution,timespend=bigstallp,nMRT=args.nMRT,
        filter_termination=args.filter_termination,introduction_time=args.introduction_time)
    from IPython.core.debugger import set_trace

    MRTp_big, MRTs_big, RFDs_big, Rept_time, single_mol_exp, pos_time_activated_ori, It , Pa, Pt ,Time,MRTstd = res

    print("Sum",np.sum(Pt))
    if args.cutholes is None:
        for MRTp, MRTs, RFDs,Pas,Pts, [x, d3ps,stallp],MRTstds in zip(np.split(MRTp_big, sp), np.split(MRTs_big, sp), np.split(RFDs_big, sp),
                                               np.split(Pa,sp),np.split(Pt,sp), d3pl,np.split(MRTstd,sp)):
            lres.append([MRTp, MRTs, RFDs, Rept_time, single_mol_exp, pos_time_activated_ori, It,Pas,Pts,Time,MRTstds])
    else:

        for MRTp, MRTs, RFDs,Pas,Pt, split, MRTstds in zip(np.split(MRTp_big, sp), np.split(MRTs_big, sp), np.split(RFDs_big, sp),
                                               np.split(Pa,sp),np.split(Pt,sp),
                                               split_ch,np.split(MRTstd,sp)):
            start_seg, end_seg, ch = split

            lres[ch ][0][start_seg:end_seg] = MRTp
            lres[ch ][1][start_seg:end_seg] = MRTs
            lres[ch ][2][start_seg:end_seg] = RFDs
            lres[ch][7][start_seg:end_seg] = Pas
            lres[ch][8][start_seg:end_seg] = Pt
            lres[ch][10][start_seg:end_seg] = MRTstds
            if lres[ch][3] is None:
                # first peace:
                lres[ch][3] = Rept_time
                lres[ch][5] = pos_time_activated_ori
                lres[ch][6] = It
                lres[ch][9] = Time

                #print(len(single_mol_exp))
                #print(len(single_mol_exp[0]))

                lres[ch][4] = [ [[single[0],single[1],single[2],[single[3][start_seg:end_seg]]] for single in simu] for simu in single_mol_exp]
            else:
                for isim,sim in enumerate(single_mol_exp):
                    for i, single in enumerate(sim):
                        lres[ch][4][isim][i][-1].append(single[3][start_seg:end_seg])

        #Redefine full d3p:
        d3p = np.concatenate([d3p for x, d3p,stallp in d3pl])
        stallp = np.concatenate([stallp for x, d3p, stallp in d3pl])
            #.append([MRTp, MRTs, RFDs, Rept_time, single_mol_exp, pos_time_activated_ori, It])
        #print(len(MRTp), len(RFDs), len(d3ps))
        # set_trace()
        #

for (start, end, ch, ndiff), [x, d3ps,stallps], res in zip(list_task, d3pl, lres):
    name_w = args.name+"_%i_%i_%i" % (ch, start, end)

    MRTp, MRTs, RFDs, Rept_time, single_mol_exp, pos_time_activated_ori, It , Pa, Pt,Time,MRTstdx = res
    if args.save:
        with open(name_w+"alldat.pick", "wb") as f:
            pickle.dump([MRTp, MRTs, RFDs, Rept_time, single_mol_exp, Time, It], f)

    if args.fsmooth != None:
        RFDs = smooth(RFDs, args.fsmooth)
    # Compare to exp data



    MRTpearson, MRTstd, MRT, [mask_MRT, l] = compare(
        MRTp[::mrt_res // resolution], "MRT", comp, res=mrt_res, ch=ch, start=start,
        end=end, return_exp=True, trunc=True,
        pad=True, return_mask=True,masking=masking,propagateNan=propagateNan)
    print(len(MRT), len(MRTp[::mrt_res // resolution]), "LEN")
    gMRT.append(MRTp[::mrt_res // resolution][:l][mask_MRT])
    gMRTe.append(MRT[:l][mask_MRT])
    RFDpearson, RFDstd, RFD, [mask_RFD, l] = compare(RFDs, expRFD, cellseq, res=resolution, ch=ch,
                                                     start=start, end=end, return_exp=True, rescale=1 / resolution,
                                                     trunc=True, pad=True, return_mask=True, smoothf=args.fsmooth,
                                                     masking=masking,propagateNan=propagateNan)

    codire.append(get_codire(RFDs, cell, ch, start, end, resolution, min_expre=1))
    gRFD.append(RFDs[mask_RFD][:l])
    gRFDe.append(RFD[mask_RFD][:l])


    """
    if cell != "Cerevisae":
            MRTpearson, MRTstd, MRT, [mask_MRT, l] = compare(
                MRTp[::10//resolution], "MRT", comp, res=10, ch=ch, start=start, end=end, return_exp=True, trunc=True, pad=True, return_mask=True)
            print(len(MRT), len(MRTp[::10//resolution]), "LEN")
            gMRT.append(MRTp[::10//resolution][:l][mask_MRT])
            gMRTe.append(MRT[:l][mask_MRT])
            RFDpearson, RFDstd, RFD, [mask_RFD, l] = compare(RFDs, "OKSeq", cellseq, res=resolution, ch=ch,
                                                             start=start, end=end, return_exp=True, rescale=1/resolution,
                                                             trunc=True, pad=True, return_mask=True, smoothf=args.fsmooth)
    
            codire.append(get_codire(RFDs, cell, ch, start, end, resolution, min_expre=1))
            gRFD.append(RFDs[mask_RFD][:l])
            gRFDe.append(RFD[mask_RFD][:l])
        else:
            
            MRTpearson, MRTstd, MRT = compare(
                MRTp, "MRT", comp, res=1, ch=ch, start=start, end=end, return_exp=True, trunc=True, pad=True)
            RFDpearson, RFDstd, RFD = compare(RFDs, "OKSeq", cellseq, res=1, ch=ch,
                                              start=start, end=end, return_exp=True, rescale=1, nanpolate=True, fsmooth=args.fsmooth, trunc=True, pad=True)
    """
    if len(stallp) ==0:
        stallps = np.ones_like(d3ps)

    if type(GData) == list:
        MRT = mapboth(MRT, MRTp, int(mrt_res/resolution), pad=True)

        ml = np.min([len(x), len(RFD), len(RFDs), len(MRT), len(MRTs)])
        #print(ml,len(Pa),len(MRT),len(MRTs),len(RFDs))
        GData = pd.DataFrame({"chrom": ["chrom%i" % ch]*ml, "chromStart": x[:ml], "chromEnd": x[:ml], "RFDe": RFD[:ml],
                              "RFDs": RFDs[:ml], "MRTe": MRT[:ml], "MRTs": MRTp[:ml],"Pa":Pa[:ml],
                              "Pt":Pt[:ml],"Stall":stallps[:ml],"Init":d3ps[:ml],"MRTstd":MRTstdx[:ml]})
    else:
        MRT = mapboth(MRT, MRTp, int(mrt_res/resolution), pad=True)
        ml = np.min([len(x), len(RFD), len(RFDs), len(MRT), len(MRTp)])
        GDatab = pd.DataFrame({"chrom": ["chrom%i" % ch]*ml, "chromStart": x[:ml], "chromEnd": x[:ml], "RFDe": RFD[:ml],
                               "RFDs": RFDs[:ml], "MRTe": MRT[:ml], "MRTs": MRTp[:ml],"Pa":Pa[:ml],
                               "Pt":Pt[:ml],"Stall":stallps[:ml],"Init":d3ps[:ml],"MRTstd":MRTstdx[:ml]})

        GData = pd.concat([GData, GDatab], axis=0)

    print(MRTpearson, MRTstd, RFDpearson, RFDstd)
    print("Rep time (h)", np.mean(Rept_time)/60)

    mean_activated_ori = compute_mean_activated_ori(pos_time_activated_ori)
    print("mean nuber of activated ori", mean_activated_ori)


    def trunc2(v):
        try:
            return float("%.2e" % v)
        except:
            return v
    Res = {"marks": [args.signal], "Diff": [ndiff], "Random": [noise], "Dori": [args.dori*5/resolution],
                         "MRTp": [[trunc2(MRTpearson[0]),MRTpearson[1]]], "RFDp": [[trunc2(RFDpearson[0]),RFDpearson[1]]],
                         "MRTstd": [trunc2(MRTstd)], "RFDstd": [trunc2(RFDstd)], "RepTime": [trunc2(np.median(Rept_time))], "ch": [ch],
                         "lenMRT": [len(mask_MRT)], "MRTkeep": [sum(mask_MRT)], "lenRFD": [len(mask_RFD)],
                         "RFDkeep": [sum(mask_RFD)], "codire": [trunc2(codire[-1])],"NactiOri":mean_activated_ori,}

    if args.single:
        # print(single_mol_exp)
        Deltas0 = compute_info(Sme=single_mol_exp, size_single_mol=int(
            200/resolution), n_sample=200)
        # print(Deltas0)


        Res["Fiber200meaninterdist"] = trunc2(np.mean(np.concatenate(Deltas0["dist_ori"])*resolution))

        print("Mean inter ori distance", np.mean(np.concatenate(Deltas0["dist_ori"])*resolution))
        Deltas = compute_real_inter_ori(pos_time_activated_ori)
        print("Mean real inter ori distance", np.mean(Deltas)*resolution)

        Res["Realinterdist"] = trunc2(np.mean(Deltas)*resolution)


        nfork_per_fiber = np.array([len(di) for di in Deltas0["size_forks"]])
        # hist(nfork_per_fiber,range=[0,5],bins=6,normed=True)
        for i in range(5):
            print("Nfork %i, percent %.2f" % (i, np.sum(nfork_per_fiber == i)/len(nfork_per_fiber)))

            Res["Fiber200_percent_%i_Forks" % i] = trunc2(np.sum(nfork_per_fiber == i)/len(nfork_per_fiber))

        print("Mean number of fork / fiber having forks",
              np.mean(nfork_per_fiber[nfork_per_fiber != 0]))

        Res["Nforkperfibrwithfork"] = trunc2(np.mean(nfork_per_fiber[nfork_per_fiber != 0]))




    ldat = pd.DataFrame(Res)

    ldat.to_csv(name_w + ".csv")

    if type(ldatg) == list:
        ldatg = ldat
    else:
        ldatg = pd.concat([ldatg, ldat], axis=0)

    # print(Deltas)

    if args.visu:

        mask_MRT = mapboth(mask_MRT, MRT, int(mrt_res/resolution), pad=True)
        if "Yeast" in  cell:
            #print("La")
            ToSee = [[[1-MRTp, "MRT"], [x, 1 - MRT, "MRTexp"]],
                     [[RFD, "RFDExp"], [RFDs, "RFDsim"]]]
        else:
            ToSee = [[[1-MRTp, "MRT"], [x, 1 - MRT, "MRTexp"]],
                     [[RFD, "RFDExp"], [RFDs, "RFDsim"]], [[smooth(np.abs(RFD-RFDs), 250), "deltasmooth"]]]
        ToSee += [[[x, mask_MRT, "MaskMRT"], [np.array(mask_RFD, dtype=np.int), "MaskRFD"]]]
        # print(len(mask_RFD))
        # print(mask_RFD)
        if args.input:
            ToSee += [[[d3ps,"initiation"]]]
            if "Yeast" in cell:
                _,tere = replication_data(cell, "ter", chromosome=ch,

                                 start=start, end=end,
                                 resolution=1, raw=False)
                #print(tere)
                ToSee += [[[tere*20,"TerExp"],[Pt,"ProbaTer"]]]
            ToSee += [[[stallp,"stalling"]]]
        if not args.only_one or (args.only_one and ch == 1):
            plotly_blocks(x, ToSee, name=name_w+".html", default="lines")

print(len(GData),len(d3p))
GData["signal"] = d3p
GData.to_csv(args.name+"global_profiles.csv", index=False, float_format="%.2f")
ldatg.to_csv(args.name+"global_scores.csv", index=False)

pRFD = stats.pearsonr(np.concatenate(gRFD), np.concatenate(gRFDe)),
sRFD = np.std(np.concatenate(gRFD) - np.concatenate(gRFDe))

pMRT = stats.pearsonr(np.concatenate(gMRT), np.concatenate(gMRTe)),
sMRT = np.std(np.concatenate(gMRT) - np.concatenate(gMRTe))
meanCodire = np.mean(codire)
print(args.name+"global_corre.csv")
glob = pd.DataFrame({"marks": [args.signal],  "Random": [noise], "Dori": [args.dori*5/resolution],
                     "MRTp": pMRT, "RFDp": pRFD,
                     "MRTstd": [sMRT], "RFDstd": [sRFD],
                     "RepTime": [np.median(Rept_time)], "codire": [meanCodire]}).to_csv(args.name+"global_corre.csv", index=False)

# pylab.plot(np.concatenate(gMRT))
# pylab.plot(np.concatenate(gMRTe))
# pylab.show()
# print(ldatg)
