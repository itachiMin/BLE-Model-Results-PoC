.PHONY: all run subset

all: subset

ExpRun/cases:
	@echo "Generate all cases..."
	make -C ExpCode high
	@mv ./ExpCode/cases ./ExpRun

run: ExpRun/cases
	@echo "Running verifier.py..."
	@cd ./ExpRun && { time python3 verifier.py;} 2> ../runtime_verifier.log
	@echo "Running crawler.py..."
	@cd ./ExpRun && { time python3 crawler.py;} 2> ../runtime_crawler.log

subset:
	@echo "Generate a small subset of all cases..."
	@cd ./ExpSubset && python3 ./subset_generate.py
	@cp -r ./ExpCode/cases ./ExpRun
	@echo "Running verifier.py..."
	@cd ./ExpRun && { time python3 verifier.py;} 2> ../runtime_verifier.log

clean:
	rm -rf ExpRun/cases
	rm -rf ExpRun/results
	rm -rf ExpRun/*.log
	rm -rf runtime_verifier.log
	rm -rf runtime_crawler.log