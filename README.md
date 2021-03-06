## Dependencies
+ [Docker](https://www.docker.com/)
+ NVIDIA 346.46 driver

## Quick run on the toy data
We prepare some toy data and toy model [here](https://github.com/gifford-lab/Keras-genomics/blob/master/example/). To perform a quick run on them:

```
for dtype in 'train' 'valid' 'test'
do
	paste - - -d' ' < example/$dtype.fa > tmp.tsv
	python embedH5.py tmp.tsv example/$dtype.target expt1/trial2.$dtype.h5
done

docker pull haoyangz/keras-genomics
docker run --rm --device /dev/nvidiactl --device /dev/nvidia-uvm --device /dev/nvidia0 \
    -v $(pwd)/example:/modeldir -v $(pwd)/expt1:/datadir haoyangz/keras-genomics \
	    python main.py -d /datadir -c trial2 -m /modeldir/model.py -s 1001 -y -t -e
```

## Data preparation
User needs to prepare [sequence file](https://github.com/gifford-lab/Keras-genomics/blob/master/example/train.fa) in [FASTA](https://en.wikipedia.org/wiki/FASTA_format) format and [target file](https://github.com/gifford-lab/Keras-genomics/blob/master/example/train.target) for training,validation and test set. Refer to the [toy data](https://github.com/gifford-lab/Keras-genomics/blob/master/example/) we provided for more examples.

Then run the following to embed each set into HDF5 format.
```
paste - - -d' ' < FASTA_FILE > tmp.tsv
python $REPO_HOME/embedH5.py tmp.tsv TARGET_FILE DATA_TOPDIR/DATA_CODE.SET_NAME.h5  -b BATCHSIZE
```
+ `FASTA_FILE`: sequence in FASTA format 
+ `TARGET_FILE`: targets (labels or real values) corresponding to the sequences (in the same order)
+ `DATA_TOPDIR`: the *absolute path* of the output directory 
+ `DATA_CODE`: the prefix of all the output HDF5 files
+ `SET_NAME`: 'train','valid',or 'test' for corresponding dataset. The main code below will search for training, validation and test data by this naming convention.
+ `BATCHSIZE`: optional and the default is 5000. Save every this number of samples to a separate file `DATA_CODE.h5.batchX` where X is the corresponding batch index.

## Model preparation
Change the `model` function in the [template](https://github.com/gifford-lab/Keras-genomics/blob/master/example/model.py) provided to implement your favorite network. Refer to [here](https://github.com/maxpumperla/hyperas) for instructions and examples of specifying hyper-parameters to tune.

## Perform hyper-parameter tuning, training and testing
We use Docker to free users from spending hours configuring the environment. But as the trade-off, it takes a long time to compile the model every time, although it won't affect the actual training time much. So below we provide instructions for running with and without Docker. 

#### Run with Docker (off-the-shelf)
```
docker pull haoyangz/keras-genomics
docker run --rm --device /dev/nvidiactl --device /dev/nvidia-uvm MOREDEVICE \
	-v MODEL_TOPDIR:/modeldir -v DATA_TOPDIR:/datadir haoyangz/keras-genomics \
	python main.py -d /datadir -c DATA_CODE -m /modeldir/MODEL_FILE_NAME -s SEQ_SIZE ORDER
```

+ `MODEL_TOPDIR`: the *absolute path* of the model file directory
+ `MODEL_FILE_NAME`: the filename of the model file
+ `DATA_TOPDIR`: same as above
+ `DATA_CODE`: same as above
+ `SEQ_SIZE`: the length of the genomic sequences
+ `ORDER`: actions to take. Multiple ones can be used and they will be executed in order.
	+ `-y`: hyper-parameter tuning. Use `-hi` to change the number of hyper-parameter combinations to try (default:9)
	+ `-t`: train. Use `-te` to change the number of epochs to train for.
	+ `-e`: evaluate the model on the test set.
	+ `-p`: predict on new data. Specifiy the data file with `-i`
+ `MOREDEVICE`: For each of the GPU device available on your machine, append one "--device /dev/nvidiaNUM" where NUM is the device index. For hsf1/hsf2 in  Gifford Lab, since there are three GPUs, it should be :
	
	```
		--device /dev/nvidia0 --device /dev/nvidia1 --device /dev/nvidia2
	```

#### Run without Docker (need to manually install packages)
Please refer to [here](https://github.com/gifford-lab/Keras-genomics/blob/master/Dockerfile)  and [here](https://hub.docker.com/r/haoyangz/keras-docker/~/dockerfile/) to configure your enviroment.
```
python $REPO_HOME/main.py -d DATA_TOPDIR -c DATA_CODE -m MODEL_TOPDIR/MODEL_FILE_NAME -s SEQ_SIZE ORDER
```

