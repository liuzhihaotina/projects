#include <iostream>
#include <algorithm>  // std::ranges::sort
#include <vector>     // std::vector
#include <string>     // std::string
#include <functional> // std::greater
#include <cstdlib>    // std::abs

int main() {
    // 示例1：按字符串长度降序排序
    std::vector<std::string> words = {"apple", "pie", "banana", "cat"};
    std::ranges::sort(
        words,
        std::greater<>(),
        [](const std::string& s) { return s.size(); }
    );

    std::cout << "按长度降序: ";
    for (const auto& w : words) {
        std::cout << w << " ";
    }
    std::cout << '\n';

    // 示例2：按绝对值降序排序
    std::vector<int> nums = {-5, 3, -8, 2, -1};
    std::ranges::sort(
        nums,
        std::greater<>(),
        [](int x) { return std::abs(x); }
    );

    std::cout << "按绝对值降序: ";
    for (int x : nums) {
        std::cout << x << " ";
    }
    std::cout << '\n';

    return 0;
}