CXX ?= g++
CXXFLAGS ?= -O3 -std=c++17 -Wall -Wextra -Wpedantic
LDLIBS ?= -lstdc++fs

.PHONY: all check clean
all: build/ridge
check: build/ridge build/finite_volume_test build/sediment_test build/migration_test build/migration_linear_test build/coupled_test build/remap_test
	./build/finite_volume_test
	./build/sediment_test
	./build/migration_test
	./build/migration_linear_test
	./build/coupled_test
	./build/remap_test
	python3 tests/restart.py

build/ridge: src/main.cpp src/model.hpp src/finite_volume.hpp src/sediment.hpp src/migration.hpp
	mkdir -p build
	$(CXX) $(CXXFLAGS) -Isrc $< -o $@ $(LDLIBS)

build/%_test: tests/%.cpp src/finite_volume.hpp src/sediment.hpp src/migration.hpp src/model.hpp
	mkdir -p build
	$(CXX) $(CXXFLAGS) -Isrc $< -o $@ $(LDLIBS)

clean:
	rm -rf build
