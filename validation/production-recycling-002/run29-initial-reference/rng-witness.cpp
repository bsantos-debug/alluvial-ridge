// RNG witness only: no model headers, state initialization, or PDE evolution.
#include <cmath>
#include <iomanip>
#include <iostream>
#include <random>

int main() {
    std::mt19937 raw(2018), engine(2018);
    std::uniform_real_distribution<double> noise(-std::sqrt(3.), std::sqrt(3.));
    std::cout << "index,word0,word1,noise_hex,noise_decimal\n";
    for (int i = 0; i < 287; ++i) {
        auto a = raw(), b = raw();
        double value = noise(engine);
        std::cout << i << ',' << a << ',' << b << ',' << std::hexfloat << value
                  << ',' << std::defaultfloat << std::setprecision(17) << value << '\n';
    }
}
