PY=python3
ICAP=KeyboardDisplay,NoOOB,AuthReq,KeyHigh
RCAP=KeyboardDisplay,NoOOB,AuthReq,KeyHigh
PROOF_LEMMA=testI*

# one: one.mid
# nolowkey: nolowkey.mid
# all: all.mid

all: main.m4 generate.py
	$(PY) ./generate.py \
		--io NoInputNoOutput,DisplayOnly,KeyboardOnly,DisplayYesNo,KeyboardDisplay \
		--oob OOBSendRev,OOBSend,OOBRev,NoOOB \
		--auth AuthReq,NoAuthReq \
		--keysize KeyHigh,KeyLow \
		--outdir cases --templete main.m4 

high: main.m4 generate.py
	$(PY) ./generate.py \
		--io NoInputNoOutput,DisplayOnly,KeyboardOnly,DisplayYesNo,KeyboardDisplay \
		--oob OOBSendRev,OOBSend,OOBRev,NoOOB \
		--auth AuthReq,NoAuthReq \
		--keysize KeyHigh \
		--outdir cases --templete main.m4 

one:
	$(PY) ./generate.py \
		--io DisplayOnly \
		--oob NoOOB \
		--auth AuthReq \
		--keysize KeyHigh \
		--outdir cases --templete main.m4 

test.mid:
	$(PY) ./generate.py \
		--device-i $(ICAP) \
		--device-r $(RCAP) \
		--outdir cases --templete main.m4 \
		--middle $@

test: test.mid
	$(PY) ./verify.py \
		-m test.mid \
		--lemma $(PROOF_LEMMA) \
		--interactive

test-all: all.mid
	$(PY) ./verify.py \
		-m all.mid \
		--lemma $(PROOF_LEMMA)

test-nolowkey: nolowkey.mid
	$(PY) ./verify.py \
		-m nolowkey.mid \
		--lemma $(PROOF_LEMMA)

# test: all

# test-one: one.mid cases/$(ONEFILE)
# 	mkdir -p proofs
# 	./test.sh cases/$(ONEFILE) testI* proofs/proof_$(ONEFILE)

clean:
	rm -rf cases
	rm -f *.mid

tamarin:
	docker run -it --rm -v $(pwd):/work -w /work --name tamarin_ble_verify -p 3001:3002 tamarin-container:1.8.0 ./test/test.sh