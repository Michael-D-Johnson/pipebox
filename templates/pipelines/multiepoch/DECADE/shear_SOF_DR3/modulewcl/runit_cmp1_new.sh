setup -v MEPipeline Y5A1dev+26

# Get FoF
run_fitvd-make-fofs \
 --meds_list lists//DES0226-1958_r5055p01_MEDS-mof.list \
 --band g \
 --output fofs/DES0226-1958_r5055p01_MEDS-fofs.list \
 --conf fitvd-shred-test05.yaml \
 --plot DES0226-1958_r5055p01_MEDS-fofs-plot.png


# Step2 -- mof run, for this example we are using 50 chunks ($NRAGES=50) and we spun 50 jobs
# This step need to be done using multi-processing in the framework.
NRANGES=50
for WRANGE in $(seq 1 $NRANGES)
do
 CHUNK=$(printf %02d $WRANGE)
 # This is the call that needs to be done.
 run_fitvd  \
     --nranges $NRANGES \
     --wrange $WRANGE \
     --tilename DES0125-4748 \
     --meds_list  lists/DES0226-1958_r5055p01_MEDS-mof.list \
     --bands g,r,i,z \
     --fofs fofs/DES0226-1958_r5055p01_MEDS-fofs.list \
     --config fitvd-shred-test05.yaml \
     --model-pars shredx/DES0226-1958_r5082p47_shredx.fits \
     --output mof/DES0226-1958_r5055p01_MEDS_mof-chunk-$CHUNK.fits > chunk_$CHUNK.log  2>&1 &
 echo "# Launching chunk $CHUNK ..."
 echo "# Sleeping 5s ..."
 # For this example I wait 5s between launching jobs
 sleep 5
 done

# Step 3 -- collate all chunks and write a single file
# We can use any of the meds file for this, in this example I used the i-band.
output="collated/DES0226-1958_r5055p01_MEDS_mof.fits"
flist=DES0226-1958_r5055p01_MEDS_chunk.list
# We create the filelist containg all of the chunk fits files
ls mof/DES0226-1958_r5055p01_MEDS_mof-chunk-*.fits > $flist

# Collate
run_fitvd-collate \
    --meds_list lists/DES0226-1958_r5055p01_MEDS-mof.list \
    --band g \
    --output=$output \
    -F $flist
