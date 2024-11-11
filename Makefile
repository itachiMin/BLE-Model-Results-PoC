.PHONY: all run expcode_make

all: run

expcode_make:
	make -C ExpCode high

run: expcode_make
	@echo "Running verifier.py..."
	@cp -r ./ExpCode/cases ./ExpRun
	@cd ./ExpRun && { time python3 verifier.py;} 2> ../runtime_verifier.log
	@echo "Running crawler.py..."
	@cd ./ExpRun && { time python3 crawler.py;} 2> ../runtime_crawler.log

clean:
	rm -rf ExpCode/cases
	rm -rf runtime_verifier.log
	rm -rf runtime_crawler.log