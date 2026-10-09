CXX ?= g++
CXXFLAGS ?= -O3 -std=c++17 -Wall -Wextra -Wpedantic

.PHONY: check clean
check: build/finite_volume_test
	./build/finite_volume_test

build/finite_volume_test: tests/finite_volume.cpp src/finite_volume.hpp
	mkdir -p build
	$(CXX) $(CXXFLAGS) -Isrc $< -o $@

clean:
	rm -rf build
