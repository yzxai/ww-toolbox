#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <unordered_map>
#include <vector>
#include <string>
#include <cmath>
#include <tuple>
#include <map>
#include <list>

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

namespace std {
    template <>
    struct hash<EchoProfile> {
        std::size_t operator()(const EchoProfile& p) const {
            std::size_t h = std::hash<int>()(p.level);
            for (const auto& kv : p.values) {
                h ^= std::hash<std::string>()(kv.first) + std::hash<int>()(int(std::round(kv.second * 10)));
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

double get_expected_wasted_exp(
    const EchoProfile& profile,
    const EntryCoef& coef,
    double score_thres,
    const DiscardScheduler& scheduler,
    const py::dict& stat_data
) {
    static std::vector<int> exp = {0, 400, 1000, 1900, 3000, 4400, 6100, 8100, 10500, 13300, 16500, 20100, 
        24200, 28800, 33900, 39600, 46000, 53100, 60900, 69600, 79100, 89600, 101100, 113700, 127500, 142600};

    static LRUCache<CacheKey, std::unordered_map<EchoProfile, double>, CacheKeyHash> waste_exp_cache(5);
    CacheKey current_key{coef, score_thres, scheduler};

    auto& stored_expectations = waste_exp_cache[current_key];

    std::function<double(const EchoProfile&)> solve = [&](const EchoProfile& p) -> double {
        std::unordered_map<EchoProfile, double>::const_iterator it = stored_expectations.find(p);
        if (it != stored_expectations.end()) return it->second;

        double score = get_score(p, coef);
        if (score >= score_thres) return 0;

        if (p.level == 25) return exp[25];

        double prob = prob_above_score(p, coef, score_thres, stat_data);
        double discard_thres = scheduler.get_threshold_for_level(p.level);
        if (prob < discard_thres) return exp[p.level];

        double expected_wasted_exp = 0.0;
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
                expected_wasted_exp += solve(new_p) * pprob / m;
            }
        }
        int useless_keys = m - (int)avail_keys.size();
        EchoProfile new_p = p;
        new_p.level = next_level;
        expected_wasted_exp += solve(new_p) * ((double)useless_keys / m);

        stored_expectations[p] = expected_wasted_exp;
        return expected_wasted_exp;
    };

    EchoProfile p = profile;
    for (std::unordered_map<std::string, double>::const_iterator it = coef.values.begin(); it != coef.values.end(); ++it) {
        if (std::abs(it->second) < 1e-5) p.values[it->first] = 0.0;
    }
    return solve(p);
}

double prob_above_threshold_with_discard(
    const EchoProfile& profile,
    const EntryCoef& coef,
    double score_thres,
    const DiscardScheduler& scheduler,
    const py::dict& stat_data
) {
    static std::unordered_map<CacheKey, std::unordered_map<EchoProfile, double>, CacheKeyHash> prob_cache;
    CacheKey current_key{coef, score_thres, scheduler};

    auto& stored_expectations = prob_cache[current_key];

    std::function<double(const EchoProfile&)> solve = [&](const EchoProfile& p) -> double {
        std::unordered_map<EchoProfile, double>::const_iterator it = stored_expectations.find(p);
        if (it != stored_expectations.end()) return it->second;

        double score = get_score(p, coef);
        if (score >= score_thres) return 1;

        if (p.level == 25) return 0;

        double prob = prob_above_score(p, coef, score_thres, stat_data);
        double discard_thres = scheduler.get_threshold_for_level(p.level);
        if (prob < discard_thres) return 0;

        double expected_num_tries = 0.0;
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
                expected_num_tries += solve(new_p) * pprob / m;
            }
        }
        int useless_keys = m - (int)avail_keys.size();
        EchoProfile new_p = p;
        new_p.level = next_level;
        expected_num_tries += solve(new_p) * ((double)useless_keys / m);

        stored_expectations[p] = expected_num_tries;
        return expected_num_tries;
    };

    EchoProfile p = profile;
    for (std::unordered_map<std::string, double>::const_iterator it = coef.values.begin(); it != coef.values.end(); ++it) {
        if (std::abs(it->second) < 1e-5) p.values[it->first] = 0.0;
    }
    return solve(p);
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

    m.def("prob_above_score", &prob_above_score, "C++ version of prob_above_score");
    m.def("get_expected_wasted_exp", &get_expected_wasted_exp, "C++ version of get_expected_wasted_exp");
    m.def("prob_above_threshold_with_discard", &prob_above_threshold_with_discard, "C++ version of prob_above_threshold_with_discard");
}