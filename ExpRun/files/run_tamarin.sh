export LC_ALL=C.UTF-8
nohup socat TCP-LISTEN:3002,fork TCP:127.0.0.1:3001 > /dev/null 2>&1 &
mkdir -p /tmp/results/
cp /results/$2 /tmp/results/$2
tamarin-prover interactive --derivcheck-timeout=0 --image-format=$1 /tmp/results/
