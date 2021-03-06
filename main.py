from __future__ import print_function
import theano,time,numpy as np,sys,h5py,cPickle,argparse,subprocess
from hyperopt import Trials, STATUS_OK, tpe
from hyperas import optim
from os.path import join,dirname,basename,exists,realpath
from os import system,chdir,getcwd,makedirs
from keras.models import model_from_json
from tempfile import mkdtemp
from keras.callbacks import ModelCheckpoint
from sklearn.metrics import accuracy_score,roc_auc_score

cwd = dirname(realpath(__file__))

def parse_args():
    parser = argparse.ArgumentParser(description="Launch a list of commands on EC2.")
    parser.add_argument("-y", "--hyper", dest="hyper", default=False, action='store_true',help="")
    parser.add_argument("-t", "--train", dest="train", default=False, action='store_true',help="")
    parser.add_argument("-e", "--eval", dest="eval", default=False, action='store_true',help="")
    parser.add_argument("-p", "--predit", dest="predict", default=False, action='store_true',help="")
    parser.add_argument("-i", "--infile", dest="infile", default='',help="")
    parser.add_argument("-d", "--topdir", dest="topdir",help="")
    parser.add_argument("-s", "--datasize", dest="datasize",help="")
    parser.add_argument("-c", "--datacode", dest="datacode",default='data',help="")
    parser.add_argument("-m", "--model", dest="model",help="")
    parser.add_argument("-o", "--outfile", dest="outfile",default='',help="")
    parser.add_argument("-x", "--prefix", dest="prefix",default='',help="")
    parser.add_argument("-hi", "--hyperiter", dest="hyperiter",default=9,type=int,help="")
    parser.add_argument("-te", "--trainepoch",default=20,type=int,help="")
    parser.add_argument("-bs", "--batchsize",default=100,type=int,help="")
    return parser.parse_args()

def probedata(dataprefix):
    allfiles = subprocess.check_output('ls '+dataprefix+'*', shell=True).split('\n')[:-1]
    cnt = 0
    samplecnt = 0
    for x in allfiles:
        if  x.split(dataprefix)[1].isdigit():
            cnt += 1
            data = h5py.File(x,'r')
            samplecnt += len(data['label'])
    return (cnt,samplecnt)

if __name__ == "__main__":

    args = parse_args()
    topdir = args.topdir
    model_arch = basename(args.model)
    model_arch = model_arch[:-3] if model_arch[-3:] == '.py' else model_arch
    data_code = args.datacode

    outdir = join(topdir,model_arch)
    if not exists(outdir):
        makedirs(outdir)

    architecture_file = join(outdir,model_arch+'_best_archit.json')
    optimizer_file = join(outdir,model_arch+'_best_optimer.pkl')
    weight_file = join(outdir,model_arch+'_bestmodel_weights.h5')
    data1prefix = join(topdir,data_code+args.prefix)
    evalout = join(outdir,model_arch+'_eval.txt')

    tmpdir = mkdtemp()
    with open(args.model) as f,open(join(tmpdir,'mymodel.py'),'w') as fout:
        for x in f:
            newline = x.replace('DATACODE',data_code)
            newline = newline.replace('TOPDIR',topdir)
            newline = newline.replace('DATASIZE',str(args.datasize))
            newline = newline.replace('MODEL_ARCH',model_arch)
            newline = newline.replace('PREFIX',args.prefix)
            fout.write(newline)

    sys.path.append(tmpdir)
    from mymodel import *
    import mymodel

    if args.hyper:
        ## Hyper-parameter tuning
        best_run, best_model = optim.minimize(model=mymodel.model,data=mymodel.data,algo=tpe.suggest,max_evals=int(args.hyperiter),trials=Trials())
        best_archit,best_optim,best_lossfunc = best_model
        open(architecture_file, 'w').write(best_archit)
        cPickle.dump((best_optim,best_lossfunc),open(optimizer_file,'wb') )

    if args.train:
        ### Training
        model = model_from_json(open(architecture_file).read())
        best_optim,best_lossfunc = cPickle.load(open(optimizer_file,'rb'))
        model.compile(loss=best_lossfunc, optimizer=best_optim,metrics=['accuracy'])

        checkpointer = ModelCheckpoint(filepath=weight_file, verbose=1, save_best_only=True)
        trainbatch_num,train_size = probedata(data1prefix+'.train.h5.batch')
        validbatch_num,valid_size = probedata(data1prefix+'.valid.h5.batch')
        history_callback = model.fit_generator(mymodel.BatchGenerator2(args.batchsize,trainbatch_num,'train',topdir,data_code)\
        		    ,train_size,args.trainepoch,validation_data=mymodel.BatchGenerator2(args.batchsize,validbatch_num,'valid',topdir,data_code)\
        			    ,nb_val_samples=valid_size,callbacks = [checkpointer])

        system('touch '+join(outdir,model_arch+'.traindone'))
        myhist = history_callback.history
        all_hist = np.asarray([myhist["loss"],myhist["acc"],myhist["val_loss"],myhist["val_acc"]]).transpose()
        np.savetxt(join(outdir,model_arch+".training_history.txt"), all_hist,delimiter = "\t",header='loss\tacc\tval_loss\tval_acc')

    if args.eval:
        ## Evaluate
        model = model_from_json(open(architecture_file).read())
        model.load_weights(weight_file)
        best_optim,best_lossfunc = cPickle.load(open(optimizer_file,'rb'))
        model.compile(loss=best_lossfunc, optimizer=best_optim,metrics=['accuracy'])

        pred = np.asarray([])
        y_true = np.asarray([])
        testbatch_num = int(subprocess.check_output('ls '+data1prefix+'.test.h5.batch* | wc -l', shell=True).split()[0])
        for X1_train,Y_train in mymodel.BatchGenerator(testbatch_num,'test',topdir,data_code):
            pred = np.append(pred,[x[0] for x in model.predict(X1_train)])
            y_true = np.append(y_true,[x[0] for x in Y_train])

        t_auc = roc_auc_score(y_true,pred)
        t_acc = accuracy_score(y_true,[1 if x>0.5 else 0 for x in pred])
        print('Test AUC:',t_auc)
        print('Test accuracy:',t_acc)
        np.savetxt(evalout,[t_auc,t_acc])

    if args.predict:
        ## Predict on new data
        model = model_from_json(open(architecture_file).read())
        model.load_weights(weight_file)
        best_optim = cPickle.load(open(optimizer_file,'rb'))
        model.compile(loss='binary_crossentropy', optimizer=best_optim,metrics=['accuracy'])

        predict_batch_num = int(subprocess.check_output('ls '+args.infile+'* | wc -l', shell=True).split()[0])
        print('Total number of batch to predict:',predict_batch_num)

        outfile = join(dirname(args.infile),'pred.'+basename(args.infile)) if args.outfile == '' else args.outfile
        if not exists(dirname(outfile)):
            makedirs(dirname(outfile))

        with open(outfile,'w') as f:
            for i in range(predict_batch_num):
                print(i)
                data1f = h5py.File(args.infile+str(i+1),'r')
                data1 = data1f['data']
                time1 = time.time()
                pred = model.predict(data1,batch_size=1280)
                time2 = time.time()
                print('predict took %0.3f ms' % ((time2-time1)*1000.0))
                for x in pred:
                    f.write('%f\n' % x[0])

    system('rm -r ' + tmpdir)
