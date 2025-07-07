#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <unordered_map>
#include <vector>
#include <string>
#include <cmath>
#include <iostream>
#include <algorithm>

namespace py = pybind11;

struct EntryCoef {
    std::unordered_map<std::string, double> values;
    EntryCoef() = default;
    EntryCoef(const std::unordered_map<std::string, double>& v) : values(v) {}

    bool operator==(const EntryCoef& other) const {
        if (values.size() != other.values.size()) return false;
        for (const auto& kv : values) {
            auto it = other.values.find(kv.first);
            if (it == other.values.end()) return false;
            double v1 = std::round(kv.second * 10) / 10.0;
            double v2 = std::round(it->second * 10) / 10.0;
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
        if (values.size() != other.values.size()) return false;
        for (const auto& kv : values) {
            auto it = other.values.find(kv.first);
            if (it == other.values.end()) return false;
            double v1 = std::round(kv.second * 10) / 10.0;
            double v2 = std::round(it->second * 10) / 10.0;
            if (std::abs(v1 - v2) > 1e-6) return false;
        }
        return true;
    }
};

struct MemoKey {
    int level;
    std::vector<std::string> non_zero_keys;
    double score, score_rounded;

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

typedef std::vector<std::string> LockedKeys;

struct CacheKey {
    EntryCoef coef;
    double score_thres;
    DiscardScheduler scheduler;
    LockedKeys locked_keys;

    bool operator==(const CacheKey& other) const {
        return coef == other.coef && 
                std::abs(score_thres - other.score_thres) < 1e-6 &&
                scheduler == other.scheduler &&
                locked_keys == other.locked_keys;
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
        for (const auto& locked_key : key.locked_keys) {
            h ^= std::hash<std::string>()(locked_key) + 0x9e3779b9 + (h << 6) + (h >> 2);
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

MemoKey get_memo_key(const EchoProfile& profile, const EntryCoef& coef) {
    MemoKey key;
    key.level = profile.level;
    for (const auto& kv : profile.values) {
        if (std::abs(kv.second) > 1e-5) {
            key.non_zero_keys.push_back(kv.first);
        }
    }
    std::sort(key.non_zero_keys.begin(), key.non_zero_keys.end());
    key.score = get_score(profile, coef);
    key.score_rounded = std::round(key.score * 30) / 30.0;
    return key;
}

std::vector<std::string> get_avail_keys(const EchoProfile& profile, const EntryCoef& coef, bool include_non_effective = false) {
    std::vector<std::string> avail_keys;
    for (std::unordered_map<std::string, double>::const_iterator it2 = coef.values.begin(); it2 != coef.values.end(); ++it2) {
        if (std::abs(it2->second) < 1e-5 && !include_non_effective) continue;
        double v = 0.0;
        std::unordered_map<std::string, double>::const_iterator it3 = profile.values.find(it2->first);
        if (it3 != profile.values.end()) v = it3->second;
        if (std::abs(v) < 1e-5) avail_keys.push_back(it2->first);
    }
    return avail_keys;
}

using StatDataCpp = std::unordered_map<std::string, std::vector<std::pair<double, double>>>;

StatDataCpp pre_process_stat_data(const EntryCoef& coef, const py::dict& stat_data_py) {
    StatDataCpp stat_data;
    for (const auto& kv : coef.values) {
        const std::string& key = kv.first;
        if (stat_data_py.contains(key.c_str())) {
            py::object stat_info = stat_data_py[key.c_str()];
            py::list dist_py = stat_info.attr("get")("distribution", py::list());
            if (!dist_py.empty()) {
                std::vector<std::pair<double, double>> dist;
                dist.reserve(dist_py.size());
                for (auto entry_py : dist_py) {
                    dist.emplace_back(py::float_(entry_py["value"]), py::float_(entry_py["probability"]));
                }
                stat_data[key] = std::move(dist);
            }
        }
    }
    return stat_data;
}

bool satisfies_locked_keys(const EchoProfile& profile, const LockedKeys& locked_keys) {
    for (const auto& key : locked_keys) {
        auto it = profile.values.find(key);
        if (it == profile.values.end() || std::abs(it->second) < 1e-5) {
            return false;
        }
    }
    return true;
}

double _prob_above_score(
    const MemoKey& profile_key,
    const EntryCoef& coef,
    double threshold,
    const LockedKeys& locked_keys,
    const StatDataCpp& stat_data
) {
    std::vector<std::string> keys;
    for (std::unordered_map<std::string, double>::const_iterator it = coef.values.begin(); it != coef.values.end(); ++it) keys.push_back(it->first);
    int remain_slots = (25 - profile_key.level) / 5;
    double init_score = profile_key.score;

    std::vector<std::string> avail_keys;
    for (std::unordered_map<std::string, double>::const_iterator it = coef.values.begin(); it != coef.values.end(); ++it) {
        if (std::abs(it->second) < 1e-5) continue;
        if (std::find(profile_key.non_zero_keys.begin(), profile_key.non_zero_keys.end(), it->first) == profile_key.non_zero_keys.end()) {
            avail_keys.push_back(it->first);
        }
    }

    typedef std::map<double, double> ScoreMap;
    int num_avail_keys = (int)avail_keys.size();
    std::vector<std::vector<ScoreMap>> dp(num_avail_keys + 1, std::vector<ScoreMap>(remain_slots + 1));
    dp[0][remain_slots][init_score] = 1.0;

    int m = (int)keys.size() - (profile_key.level / 5);

    for (int i = 0; i < num_avail_keys; ++i) {
        const std::string& key = avail_keys[i];
        auto it_dist = stat_data.find(key);
        int max_j = std::min(m - i, remain_slots);
        for (int j = 0; j <= max_j; ++j) {
            double appear_prob = double(j) / (m - i);
            for (ScoreMap::const_iterator it = dp[i][j].begin(); it != dp[i][j].end(); ++it) {
                double score = it->first;
                double prob = it->second;
                if (std::find(locked_keys.begin(), locked_keys.end(), key) == locked_keys.end()) {
                    dp[i + 1][j][score] += prob * (1 - appear_prob);
                }
                if (j > 0 && it_dist != stat_data.end()) {
                    const auto& dist = it_dist->second;
                    for (const auto& entry : dist) {
                        double value = entry.first;
                        double p = entry.second;
                        double add_score = value * coef.values.at(key);
                        double new_score = std::round((score + add_score) * 20) / 20.0;
                        dp[i + 1][j - 1][new_score] += prob * appear_prob * p;
                    }
                }
            }
        }
    }

    double result = 0.0;

    for (auto& score_map: dp[num_avail_keys]) {
        for (auto& [score, prob] : score_map) if (score >= threshold) result += prob;
    }
    
    return result;
}

double prob_above_score(
    const EchoProfile& profile,
    const EntryCoef& coef,
    double threshold,
    const LockedKeys& locked_keys,
    const py::dict& stat_data_py
) {
    StatDataCpp stat_data = pre_process_stat_data(coef, stat_data_py);
    return _prob_above_score(get_memo_key(profile, coef), coef, threshold, locked_keys, stat_data);
}

static std::vector<int> echo_exp = {0, 400, 1000, 1900, 3000, 4400, 6100, 8100, 10500, 13300, 16500, 20100, 
    24200, 28800, 33900, 39600, 46000, 53100, 60900, 69600, 79100, 89600, 101100, 113700, 127500, 142600};

Result _get_statistics_internal(
    const EchoProfile& profile,
    const EntryCoef& coef,
    double score_thres,
    const LockedKeys& locked_keys,
    const DiscardScheduler& scheduler,
    const StatDataCpp& stat_data
) {
    static LRUCache<CacheKey, std::unordered_map<MemoKey, Result>, CacheKeyHash> waste_exp_cache(20);
    CacheKey current_key{coef, score_thres, scheduler, locked_keys};

    auto& stored_expectations = waste_exp_cache[current_key];

    std::function<Result(const EchoProfile&)> solve = [&](const EchoProfile& p) -> Result {
        MemoKey key = get_memo_key(p, coef);

        double score = key.score;

        auto it = stored_expectations.find(key);
        if (it != stored_expectations.end()) return it->second;

        if (score >= score_thres && satisfies_locked_keys(p, locked_keys)) {
            return stored_expectations[key] = Result(1.0, 0.0, 0.0);
        }

        if (p.level == 25) {
            return stored_expectations[key] = Result(0.0, echo_exp[25], 50);
        }

        double prob = _prob_above_score(get_memo_key(p, coef), coef, score_thres, locked_keys, stat_data);
        double discard_thres = scheduler.get_threshold_for_level(p.level);
        if (prob < discard_thres) {
            return stored_expectations[key] = Result(0.0, echo_exp[p.level], p.level / 5 * 10);
        }

        Result result(0.0, 0.0, 0.0);
        std::vector<std::string> avail_keys = get_avail_keys(p, coef, false);
        int m = (int)coef.values.size() - (p.level / 5);
        int next_level = ((p.level / 5) + 1) * 5;
        for (size_t i = 0; i < avail_keys.size(); ++i) {
            const std::string& key_str = avail_keys[i];
            EchoProfile new_p = p;
            new_p.level = next_level;
            
            auto it_dist = stat_data.find(key_str);
            if (it_dist != stat_data.end()) {
                const auto& dist = it_dist->second;
                for (const auto& entry : dist) {
                    double value = entry.first;
                    double pprob = entry.second;
                    new_p.values[key_str] = value;
                    result += solve(new_p) * (pprob / m);
                }
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

Result get_statistics(
    const EchoProfile& profile,
    const EntryCoef& coef,
    double score_thres,
    const LockedKeys& locked_keys,
    const DiscardScheduler& scheduler,
    const py::dict& stat_data_py
) {
    StatDataCpp stat_data = pre_process_stat_data(coef, stat_data_py);
    return _get_statistics_internal(profile, coef, score_thres, locked_keys, scheduler, stat_data);
}

EchoProfile _get_example_profile_above_threshold_internal(
    int level,
    double prob_above_threshold,
    const EntryCoef& coef, 
    double score_thres,
    const LockedKeys& locked_keys,
    const StatDataCpp& stat_data
) {
    static std::map<double, EchoProfile> example_profiles[5];
    static std::optional<CacheKey> last_key;

    std::vector<std::string> keys;
    for (std::unordered_map<std::string, double>::const_iterator it = coef.values.begin(); it != coef.values.end(); ++it) keys.push_back(it->first);

    std::function<double(const EchoProfile&)> statistic_significance = [&](const EchoProfile& p) -> double {
        double result = 0.0;
        for (const auto& kv : p.values) {
            if (std::abs(kv.second) < 1e-5) continue;
            auto it_dist = stat_data.find(kv.first);
            if (it_dist != stat_data.end()) {
                const auto& dist = it_dist->second;
                for (const auto& entry : dist) {
                    double value = entry.first;
                    double pprob = entry.second;
                    if (std::abs(value - kv.second) < 1e-5) result += log(pprob);
                }
            }
        }
        return result;
    };

    CacheKey key{coef, score_thres, DiscardScheduler(), locked_keys};

    if (!last_key || !(*last_key == key)) {
        last_key = key;
        for (int i = 0; i < 5; ++i) example_profiles[i].clear();
        example_profiles[0][0.0] = EchoProfile();
        for (int i = 0; i < 4; ++i) {
            for (const auto& kv : example_profiles[i]) {
                EchoProfile p = kv.second;
                std::vector<std::string> avail_keys = get_avail_keys(p, coef, true);
                for (const auto& key_str : avail_keys) {
                    EchoProfile new_p = p;
                    new_p.level = (i + 1) * 5;
                    auto it_dist = stat_data.find(key_str);
                    if (it_dist != stat_data.end()) {
                        const auto& dist = it_dist->second;
                        for (const auto& entry : dist) {
                            double value = entry.first;
                            new_p.values[key_str] = value;

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
    }

    double min_prob = 2.0;
    EchoProfile best_profile;
    for (const auto& p : example_profiles[level / 5]) {
        double prob = _prob_above_score(get_memo_key(p.second, coef), coef, score_thres, locked_keys, stat_data);
        if (prob >= prob_above_threshold && prob < min_prob) {
            min_prob = prob;
            best_profile = p.second;
        }
    }

    return best_profile;
}

EchoProfile get_example_profile_above_threshold(
    int level,
    double prob_above_threshold,
    const EntryCoef& coef, 
    double score_thres,
    const LockedKeys& locked_keys,
    const py::dict& stat_data_py
) {
    StatDataCpp stat_data = pre_process_stat_data(coef, stat_data_py);
    return _get_example_profile_above_threshold_internal(level, prob_above_threshold, coef, score_thres, locked_keys, stat_data);
}

DiscardScheduler _get_optimal_scheduler_internal(
    double num_echo_weight,
    double exp_weight,
    double tuner_weight,
    const EntryCoef& coef,
    double score_thres,
    const LockedKeys& locked_keys,
    const StatDataCpp& stat_data,
    int iterations = 20
) {
    double sum_weights = num_echo_weight + exp_weight + tuner_weight;
    num_echo_weight /= sum_weights, exp_weight /= sum_weights, tuner_weight /= sum_weights;

    Result default_result = _get_statistics_internal(EchoProfile(), coef, score_thres, locked_keys, DiscardScheduler(), stat_data);

    struct Resource {
        double num_echo, exp, tuner;

        Resource() : num_echo(0.0), exp(0.0), tuner(0.0) {}
        Resource(double num_echo, double exp, double tuner) : num_echo(num_echo), exp(exp), tuner(tuner) {}

        Resource operator+(const Resource& other) const {
            return Resource(num_echo + other.num_echo, exp + other.exp, tuner + other.tuner);
        }

        Resource operator-(const Resource& other) const {
            return Resource(num_echo - other.num_echo, exp - other.exp, tuner - other.tuner);
        }
        
        Resource operator*(double factor) const {
            return Resource(num_echo * factor, exp * factor, tuner * factor);
        }
    };

    Resource current_resource = Resource(
        (1.0 / default_result.prob_above_threshold_with_discard) - 1,
        default_result.expected_wasted_exp / default_result.prob_above_threshold_with_discard,
        default_result.expected_wasted_tuner / default_result.prob_above_threshold_with_discard
    );

    std::function<double(const Resource&)> get_resource_score = [&](const Resource& resource) -> double {
        return num_echo_weight * 10 * resource.num_echo 
            + exp_weight / 1200 * resource.exp 
            + tuner_weight * resource.tuner;
    };

    std::unordered_map<MemoKey, bool> strategies;

    // This iterative algorithm is inspired by Shallea's post https://bbs.nga.cn/read.php?tid=44508135

    Resource lower_bound = Resource(0.0, 0.0, 0.0), upper_bound = current_resource;
    for (int i = 0; i < 2 * iterations; ++i) {
        if (i < iterations) current_resource = (lower_bound + upper_bound) * 0.5;
        std::unordered_map<MemoKey, Resource> resource_cache;
        std::function<Resource(const EchoProfile&)> solve = [&](const EchoProfile& profile) -> Resource {
            double score = get_score(profile, coef);
            if (score >= score_thres && satisfies_locked_keys(profile, locked_keys)) return Resource(0.0, 0.0, 0.0);
            if (profile.level == 25) return current_resource + Resource(1.0, 0.0, 0.0);

            MemoKey key = get_memo_key(profile, coef);
            auto it = resource_cache.find(key);
            if (it != resource_cache.end()) return it->second;

            std::vector<std::string> avail_keys = get_avail_keys(profile, coef, false);
            int m = (int)coef.values.size() - (profile.level / 5);
            int next_level = ((profile.level / 5) + 1) * 5;

            Resource result(0.0, echo_exp[next_level] - echo_exp[profile.level], 10);
            for (size_t i = 0; i < avail_keys.size(); ++i) {
                const std::string& key_str = avail_keys[i];
                EchoProfile new_p = profile;
                new_p.level = next_level;
                auto it_dist = stat_data.find(key_str);
                if (it_dist != stat_data.end()) {
                    const auto& dist = it_dist->second;
                    for (const auto& entry : dist) {
                        double value = entry.first;
                        double pprob = entry.second;
                        new_p.values[key_str] = value;
                        result = result + solve(new_p) * (pprob / m);
                    }
                }
            }

            int useless_keys = m - (int)avail_keys.size();
            EchoProfile new_p = profile;
            new_p.level = next_level;
            result = result + solve(new_p) * ((double)useless_keys / m);
            Resource resource_if_discard = Resource(1.0, 0.0, 0.0) + current_resource;

            bool discard = get_resource_score(result) > get_resource_score(resource_if_discard);
            strategies[key] = discard;
            resource_cache[key] = discard ? resource_if_discard : result;
            return resource_cache[key];
        };

        Resource resource_after_iterate = solve(EchoProfile());
        if (get_resource_score(resource_after_iterate) >= get_resource_score(current_resource)) {
            lower_bound = current_resource;
        } else {
            upper_bound = current_resource;
        }
        if (i >= iterations) current_resource = current_resource + (resource_after_iterate - current_resource) * 10;
    }

    DiscardScheduler scheduler(std::vector<double>(4, 1.0));
    for (auto& [key, discard] : strategies) if (!discard) {
        if (5 <= key.level && key.level <= 20) {
            double prob = _prob_above_score(key, coef, score_thres, locked_keys, stat_data);
            scheduler.thresholds[key.level / 5 - 1] = std::min(scheduler.thresholds[key.level / 5 - 1], prob);
        }
    }

    return scheduler;
}

DiscardScheduler get_optimal_scheduler(
    double num_echo_weight,
    double exp_weight,
    double tuner_weight,
    const EntryCoef& coef,
    double score_thres,
    const LockedKeys& locked_keys,
    const py::dict& stat_data_py,
    int iterations = 20
) {
    StatDataCpp stat_data = pre_process_stat_data(coef, stat_data_py);
    return _get_optimal_scheduler_internal(num_echo_weight, exp_weight, tuner_weight, coef, score_thres, locked_keys, stat_data, iterations);
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

    m.def("prob_above_score", &prob_above_score, "C++ version of prob_above_score",
        py::arg("profile"), py::arg("coef"), py::arg("threshold"), py::arg("locked_keys"), py::arg("stat_data"));
    m.def("get_statistics", &get_statistics, "C++ version of get_statistics",
        py::arg("profile"), py::arg("coef"), py::arg("score_thres"), py::arg("locked_keys"), py::arg("scheduler"), py::arg("stat_data"));
    m.def("get_example_profile_above_threshold", &get_example_profile_above_threshold, "Get an example profile with a similar probability to reach the threshold",
        py::arg("level"), py::arg("prob_above_threshold"), py::arg("coef"), py::arg("score_thres"), py::arg("locked_keys"), py::arg("stat_data"));
    m.def("get_optimal_scheduler", &get_optimal_scheduler, "C++ version of get_optimal_scheduler",
        py::arg("num_echo_weight"), py::arg("exp_weight"), py::arg("tuner_weight"), py::arg("coef"), py::arg("score_thres"), py::arg("locked_keys"), py::arg("stat_data"), py::arg("iterations")=20);
}