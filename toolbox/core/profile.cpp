#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <unordered_map>
#include <vector>
#include <string>
#include <cmath>
#include <tuple>
#include <map>
#include <list>
#include <algorithm>
#include <optional>

namespace py = pybind11;

struct EntryCoef {
    std::unordered_map<std::string, double> values;
    EntryCoef() = default;
    EntryCoef(const std::unordered_map<std::string, double>& v) : values(v) {}

    bool operator==(const EntryCoef& other) const {
        if (values.size() != other.values.size()) return false;
        for (const auto& kv : values) {
            double v1 = std::round(kv.second * 10) / 10.0;
            double v2 = std::round(other.values.at(kv.first) * 10) / 10.0;
            if (std::abs(v1 - v2) > 1e-6) return false;
        }
        return true;
    }
};

struct EchoProfile {
    int level = 0;
    std::unordered_map<std::string, double> values;
    EchoProfile() = default;
    EchoProfile(int lvl, const std::unordered_map<std::string, double>& v) : level(lvl), values(v) {}

    bool operator==(const EchoProfile& other) const {
        if (level != other.level) return false;
        for (const auto& kv : values) {
            double v1 = std::round(kv.second * 10) / 10.0;
            double v2 = std::round(other.values.at(kv.first) * 10) / 10.0;
            if (std::abs(v1 - v2) > 1e-6) return false;
        }
        return true;
    }
};

struct MemoKey {
    int level;
    std::vector<std::string> non_zero_keys;
    double score_rounded;

    bool operator==(const MemoKey& other) const {
        return level == other.level &&
               score_rounded == other.score_rounded &&
               non_zero_keys == other.non_zero_keys;
    }
};

double get_score(const EchoProfile& profile, const EntryCoef& coef) {
    double total = 0.0;
    for (std::unordered_map<std::string, double>::const_iterator it = coef.values.begin(); it != coef.values.end(); ++it) {
        double v = 0.0;
        std::unordered_map<std::string, double>::const_iterator it2 = profile.values.find(it->first);
        if (it2 != profile.values.end()) v = it2->second;
        total += v * it->second;
    }
    return total;
}

namespace std {
    template <>
    struct hash<MemoKey> {
        std::size_t operator()(const MemoKey& k) const {
            std::size_t h = std::hash<int>()(k.level);
            h ^= std::hash<double>()(k.score_rounded) + 0x9e3779b9 + (h << 6) + (h >> 2);
            for (const auto& key_str : k.non_zero_keys) {
                h ^= std::hash<std::string>()(key_str) + 0x9e3779b9 + (h << 6) + (h >> 2);
            }
            return h;
        }
    };
}

struct DiscardScheduler {
    std::vector<double> thresholds;

    DiscardScheduler() : thresholds(4, 0.0) {}
    DiscardScheduler(const std::vector<double>& t) : thresholds(t) {
        if (t.size() != 4) throw std::runtime_error("DiscardScheduler needs 4 thresholds");
    }

    bool operator==(const DiscardScheduler& other) const {
        if (thresholds.size() != other.thresholds.size()) return false;
        for (size_t i = 0; i < thresholds.size(); ++i) {
            if (std::abs(thresholds[i] - other.thresholds[i]) > 1e-6) return false;
        }
        return true;
    }

    double get_threshold_for_level(int level) const {
        if (level >= 5 && level <= 9) return thresholds[0];
        if (level >= 10 && level <= 14) return thresholds[1];
        if (level >= 15 && level <= 19) return thresholds[2];
        if (level >= 20 && level <= 24) return thresholds[3];
        return 0.0;
    }
};

double prob_above_score(
    const EchoProfile& profile,
    const EntryCoef& coef,
    double threshold,
    const py::dict& stat_data
) {
    std::vector<std::string> keys;
    for (std::unordered_map<std::string, double>::const_iterator it = coef.values.begin(); it != coef.values.end(); ++it) keys.push_back(it->first);
    int remain_slots = (25 - profile.level) / 5;
    double init_score = std::round(get_score(profile, coef) * 10) / 10.0;

    std::vector<std::string> avail_keys;
    for (size_t i = 0; i < keys.size(); ++i) {
        double v = 0.0;
        std::unordered_map<std::string, double>::const_iterator it = profile.values.find(keys[i]);
        if (it != profile.values.end()) v = it->second;
        if (std::abs(v) < 1e-5) avail_keys.push_back(keys[i]);
    }
    int m = (int)avail_keys.size();

    typedef std::map<double, double> ScoreMap;
    std::vector<std::vector<ScoreMap>> dp(m + 1, std::vector<ScoreMap>(remain_slots + 1));
    dp[0][remain_slots][init_score] = 1.0;

    for (int i = 0; i < m; ++i) {
        const std::string& key = avail_keys[i];
        py::list dist = stat_data[key.c_str()].attr("get")("distribution", py::list());
        int max_j = std::min(m - i, remain_slots);
        for (int j = 0; j <= max_j; ++j) {
            double appear_prob = (m - i == 0) ? 0.0 : double(j) / (m - i);
            for (ScoreMap::const_iterator it = dp[i][j].begin(); it != dp[i][j].end(); ++it) {
                double score = it->first;
                double prob = it->second;
                dp[i + 1][j][score] += prob * (1 - appear_prob);
                if (j > 0 && py::len(dist) > 0) {
                    for (auto entry : dist) {
                        double value = py::float_(entry["value"]);
                        double p = py::float_(entry["probability"]);
                        double add_score = value * coef.values.at(key);
                        double new_score = std::round((score + add_score) * 10) / 10.0;
                        dp[i + 1][j - 1][new_score] += prob * appear_prob * p;
                    }
                }
            }
        }
    }
    double result = 0.0;
    for (ScoreMap::const_iterator it = dp[m][0].begin(); it != dp[m][0].end(); ++it) {
        double score = it->first;
        double prob = it->second;
        if (score >= threshold) result += prob;
    }
    return result;
}

struct CacheKey {
    EntryCoef coef;
    double score_thres;
    DiscardScheduler scheduler;

    bool operator==(const CacheKey& other) const {
        return coef == other.coef && 
                std::abs(score_thres - other.score_thres) < 1e-6 &&
                scheduler == other.scheduler;
    }
};

struct CacheKeyHash {
    std::size_t operator()(const CacheKey& key) const {
        std::size_t h = 0;
        for (const auto& kv : key.coef.values) {
            h ^= std::hash<std::string>()(kv.first) + 
                    std::hash<int>()(int(std::round(kv.second * 10)));
        }
        h ^= std::hash<int>()(int(std::round(key.score_thres * 10)));
        for (const auto& threshold : key.scheduler.thresholds) {
            h ^= std::hash<int>()(int(std::round(threshold * 1000)));
        }
        return h;
    }
};

template<typename Key, typename Value, typename Hasher>
class LRUCache {
public:
    LRUCache(size_t max_size) : max_size_(max_size) {}

    Value& operator[](const Key& key) {
        auto it = map_.find(key);

        if (it != map_.end()) {
            // Key found, move to front (most recently used)
            list_.splice(list_.begin(), list_, it->second.second);
            return it->second.first;
        }

        // Key not found, must insert
        if (map_.size() >= max_size_ && !list_.empty()) {
            // Cache is full, evict least recently used
            Key lru_key = list_.back();
            list_.pop_back();
            map_.erase(lru_key);
        }

        // Insert new element
        list_.push_front(key);
        auto& entry = map_[key];
        entry.second = list_.begin();
        return entry.first;
    }

private:
    using ListIterator = typename std::list<Key>::iterator;
    using CacheEntry = std::pair<Value, ListIterator>;
    size_t max_size_;
    std::list<Key> list_;
    std::unordered_map<Key, CacheEntry, Hasher> map_;
};

struct Result {
    double prob_above_threshold_with_discard;
    double expected_wasted_exp;
    double expected_wasted_tuner; 

    Result() : prob_above_threshold_with_discard(0.0), expected_wasted_exp(0.0), expected_wasted_tuner(0.0) {}
    Result(double prob, double exp, double tuner) : prob_above_threshold_with_discard(prob), expected_wasted_exp(exp), expected_wasted_tuner(tuner) {}

    Result operator+(const Result& other) const {
        return Result(
            prob_above_threshold_with_discard + other.prob_above_threshold_with_discard,
            expected_wasted_exp + other.expected_wasted_exp,
            expected_wasted_tuner + other.expected_wasted_tuner
        );
    }

    Result operator+=(const Result& other) {
        *this = *this + other;
        return *this;
    }

    Result operator*(double factor) const {
        return Result(
            prob_above_threshold_with_discard * factor,
            expected_wasted_exp * factor,
            expected_wasted_tuner * factor
        );
    }
};

Result get_statistics(
    const EchoProfile& profile,
    const EntryCoef& coef,
    double score_thres,
    const DiscardScheduler& scheduler,
    const py::dict& stat_data
) {
    static std::vector<int> exp = {0, 400, 1000, 1900, 3000, 4400, 6100, 8100, 10500, 13300, 16500, 20100, 
        24200, 28800, 33900, 39600, 46000, 53100, 60900, 69600, 79100, 89600, 101100, 113700, 127500, 142600};

    static LRUCache<CacheKey, std::unordered_map<MemoKey, Result>, CacheKeyHash> waste_exp_cache(20);
    CacheKey current_key{coef, score_thres, scheduler};

    auto& stored_expectations = waste_exp_cache[current_key];

    std::function<Result(const EchoProfile&)> solve = [&](const EchoProfile& p) -> Result {
        MemoKey key;
        key.level = p.level;
        for (const auto& kv : p.values) {
            if (std::abs(kv.second) > 1e-5) {
                key.non_zero_keys.push_back(kv.first);
            }
        }
        std::sort(key.non_zero_keys.begin(), key.non_zero_keys.end());

        double score = get_score(p, coef);
        key.score_rounded = std::round(score * 10) / 10.0;

        auto it = stored_expectations.find(key);
        if (it != stored_expectations.end()) return it->second;

        if (score >= score_thres) {
            return stored_expectations[key] = Result(1.0, 0.0, 0.0);
        }

        if (p.level == 25) {
            return stored_expectations[key] = Result(0.0, exp[25], 50);
        }

        double prob = prob_above_score(p, coef, score_thres, stat_data);
        double discard_thres = scheduler.get_threshold_for_level(p.level);
        if (prob < discard_thres) {
            return stored_expectations[key] = Result(0.0, exp[p.level], p.level / 5 * 10);
        }

        Result result(0.0, 0.0, 0.0);
        std::vector<std::string> avail_keys;
        for (std::unordered_map<std::string, double>::const_iterator it2 = coef.values.begin(); it2 != coef.values.end(); ++it2) {
            if (std::abs(it2->second) < 1e-5) continue;
            double v = 0.0;
            std::unordered_map<std::string, double>::const_iterator it3 = p.values.find(it2->first);
            if (it3 != p.values.end()) v = it3->second;
            if (std::abs(v) < 1e-5) avail_keys.push_back(it2->first);
        }
        int m = (int)coef.values.size() - (p.level / 5);
        int next_level = ((p.level / 5) + 1) * 5;
        for (size_t i = 0; i < avail_keys.size(); ++i) {
            const std::string& key = avail_keys[i];
            EchoProfile new_p = p;
            new_p.level = next_level;
            py::list dist = stat_data[key.c_str()].attr("get")("distribution", py::list());
            for (auto entry : dist) {
                double value = py::float_(entry["value"]);
                double pprob = py::float_(entry["probability"]);
                new_p.values[key] = value;
                result += solve(new_p) * (pprob / m);
            }
        }
        int useless_keys = m - (int)avail_keys.size();
        EchoProfile new_p = p;
        new_p.level = next_level;
        result += solve(new_p) * ((double)useless_keys / m);

        stored_expectations[key] = result;
        return result;
    };

    EchoProfile p = profile;
    for (std::unordered_map<std::string, double>::const_iterator it = coef.values.begin(); it != coef.values.end(); ++it) {
        if (std::abs(it->second) < 1e-5) p.values[it->first] = 0.0;
    }
    return solve(p);
}

EchoProfile get_example_profile_above_threshold(
    int level,
    double prob_above_threshold,
    const EntryCoef& coef, 
    double score_thres,
    const py::dict& stat_data
) {
    static std::map<double, EchoProfile> example_profiles[5];
    static std::optional<CacheKey> last_key;

    std::vector<std::string> keys;
    for (std::unordered_map<std::string, double>::const_iterator it = coef.values.begin(); it != coef.values.end(); ++it) keys.push_back(it->first);

    std::function<double(const EchoProfile&)> statistic_significance = [&](const EchoProfile& p) -> double {
        double result = 0.0;
        for (const auto& kv : p.values) {
            if (std::abs(kv.second) < 1e-5) continue;
            py::list dist = stat_data[kv.first.c_str()].attr("get")("distribution", py::list());
            for (auto entry : dist) {
                double value = py::float_(entry["value"]);
                double pprob = py::float_(entry["probability"]);
                if (std::abs(value - kv.second) < 1e-5) result += log(pprob);
            }
        }
        return result;
    };

    CacheKey key{coef, score_thres, DiscardScheduler()};

    if (!last_key || !(*last_key == key)) {
        last_key = key;
        for (int i = 0; i < 5; ++i) example_profiles[i].clear();
        example_profiles[0][0.0] = EchoProfile();
        for (int i = 0; i < 4; ++i) {
            for (const auto& kv : example_profiles[i]) {
                EchoProfile p = kv.second;
                std::vector<std::string> avail_keys;
                for (const auto& kv2 : coef.values) {
                    double v = 0.0;
                    std::unordered_map<std::string, double>::const_iterator it3 = p.values.find(kv2.first);
                    if (it3 != p.values.end()) v = it3->second;
                    if (std::abs(v) < 1e-5) avail_keys.push_back(kv2.first);
                }
                for (const auto& key : avail_keys) {
                    EchoProfile new_p = p;
                    new_p.level = (i + 1) * 5;
                    py::list dist = stat_data[key.c_str()].attr("get")("distribution", py::list());
                    for (auto entry : dist) {
                        double value = py::float_(entry["value"]);
                        new_p.values[key] = value;

                        double stat_sig = statistic_significance(new_p);
                        double score_rounded = std::round(get_score(new_p, coef) * 10) / 10.0;

                        if (example_profiles[i + 1].count(score_rounded) == 0) {
                            example_profiles[i + 1][score_rounded] = new_p;
                        } else if (statistic_significance(example_profiles[i + 1][score_rounded]) < stat_sig) {
                            example_profiles[i + 1][score_rounded] = new_p;
                        }
                    }
                }
            }
        }
    }

    double min_prob = 2.0;
    EchoProfile best_profile;
    for (const auto& p : example_profiles[level / 5]) {
        double prob = prob_above_score(p.second, coef, score_thres, stat_data);
        if (prob >= prob_above_threshold && prob < min_prob) {
            min_prob = prob;
            best_profile = p.second;
        }
    }

    return best_profile;
}

PYBIND11_MODULE(profile_cpp, m) {
    py::class_<EntryCoef>(m, "EntryCoef")
        .def(py::init<>())
        .def(py::init<const std::unordered_map<std::string, double>&>())
        .def_readwrite("values", &EntryCoef::values);

    py::class_<EchoProfile>(m, "EchoProfile")
        .def(py::init<>())
        .def(py::init<int, const std::unordered_map<std::string, double>&>())
        .def_readwrite("level", &EchoProfile::level)
        .def_readwrite("values", &EchoProfile::values);

    py::class_<DiscardScheduler>(m, "DiscardScheduler")
        .def(py::init<>())
        .def(py::init<const std::vector<double>&>())
        .def_readwrite("thresholds", &DiscardScheduler::thresholds);

    py::class_<Result>(m, "Result")
        .def(py::init<>())
        .def(py::init<double, double, double>())
        .def_readwrite("prob_above_threshold_with_discard", &Result::prob_above_threshold_with_discard)
        .def_readwrite("expected_wasted_exp", &Result::expected_wasted_exp)
        .def_readwrite("expected_wasted_tuner", &Result::expected_wasted_tuner);

    m.def("prob_above_score", &prob_above_score, "C++ version of prob_above_score");
    m.def("get_statistics", &get_statistics, "C++ version of get_statistics");
    m.def("get_example_profile_above_threshold", &get_example_profile_above_threshold, "Get an example profile with a similar probability to reach the threshold");
}