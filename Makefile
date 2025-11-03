.PHONY: all run subset

all: run

ExpRun/cases:
	@echo "Generate all cases..."
	make -C ExpCode high
	@mv ./ExpCode/cases ./ExpRun

run: ExpRun/cases
	@echo "Running verifier.py..."
	@cd ./ExpRun && python3 verifier.py
	@echo "Running crawler.py..."
	@cd ./ExpRun && python3 crawler.py

subset:
	@echo "Generate a small subset of all cases..."
	@cd ./ExpSubset && python3 ./subset_generate.py
	@mv ./ExpCode/cases ./ExpRun
	@echo "Running verifier.py..."
	@cd ./ExpRun && python3 verifier.py

clean:
	rm -rf ExpRun/cases
	rm -rf ExpRun/results
	rm -rf ExpRun/*.log
	rm -rf ExpRun/running.json
	rm -rf runtime_verifier.log
	rm -rf runtime_crawler.log