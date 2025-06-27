import re
import json
import yaml
import profile_cpp

from dataclasses import dataclass, field
from pathlib import Path
from PIL import Image
from copy import deepcopy
from toolbox.utils.generic import get_config_dir, get_assets_dir
from toolbox.utils.ocr import ocr
from toolbox.utils.logger import logger

stat_file = get_config_dir() / "entry_stats.yml"
coef_file = get_config_dir() / "entry_coef.yml"
echo_file = get_assets_dir() / "echo.json"

with open(stat_file, "r", encoding="utf-8") as f:
    stat_data = yaml.safe_load(f)

with open(coef_file, "r", encoding="utf-8") as f:
    coef_data = yaml.safe_load(f)

with open(echo_file, "r", encoding="utf-8") as f:
    echo_data = json.load(f)

@dataclass
class DiscardScheduler:
    level_5_9: float = field(default=0.0)
    level_10_14: float = field(default=0.0)
    level_15_19: float = field(default=0.0)
    level_20_24: float = field(default=0.0)

    def to_cpp(self):
        thresholds = [self.level_5_9, self.level_10_14, self.level_15_19, self.level_20_24]
        return profile_cpp.DiscardScheduler(thresholds)

@dataclass 
class EntryCoef:
    atk_rate: float = field(default=0.0)
    atk_num: int = field(default=0)
    def_rate: float = field(default=0.0)
    def_num: int = field(default=0)
    hp_rate: float = field(default=0.0)
    hp_num: int = field(default=0)
    cri_rate: float = field(default=0.0)
    cri_dmg: float = field(default=0.0)
    normal_dmg: float = field(default=0.0)
    charged_atk: float = field(default=0.0)
    resonance_skill: float = field(default=0.0)
    resonance_burst: float = field(default=0.0)
    resonance_eff: float = field(default=0.0)

    def __init__(self, char_name: str = None):
        self.atk_rate = 0.0
        self.atk_num = 0
        self.def_rate = 0.0
        self.def_num = 0
        self.hp_rate = 0.0
        self.hp_num = 0
        self.cri_rate = 0.0
        self.cri_dmg = 0.0
        self.normal_dmg = 0.0
        self.charged_atk = 0.0
        self.resonance_skill = 0.0
        self.resonance_burst = 0.0
        self.resonance_eff = 0.0
        
        for key, value in coef_data["Default"]["coef"].items():
            setattr(self, key, value)
        
        if char_name is not None:
            self.set_char(char_name)

    def set_char(self, char_name: str):
        if char_name not in coef_data:
            raise ValueError(f"Character {char_name} not found in coef data")
        
        match coef_data[char_name]["dmg_source"]:
            case "hp":
                self.hp_num = 0.00676
                self.hp_rate = 1
            case "atk":
                self.atk_num = 0.1
                self.atk_rate = 1
            case "def":
                self.def_num = 0.1
                self.def_rate = 1
        
        for key, value in coef_data[char_name]["coef"].items():
            setattr(self, key, value)

    def to_cpp(self):
        return profile_cpp.EntryCoef({k: float(v) for k, v in self.__dict__.items()})

@dataclass
class EchoProfile:
    level: int = field(default=0)
    name: str = field(default="")
    atk_rate: float = field(default=0.0)
    atk_num: int = field(default=0)
    def_rate: float = field(default=0.0)
    def_num: int = field(default=0)
    hp_rate: float = field(default=0.0)
    hp_num: int = field(default=0)
    cri_rate: float = field(default=0.0)
    cri_dmg: float = field(default=0.0)
    normal_dmg: float = field(default=0.0)
    charged_atk: float = field(default=0.0)
    resonance_skill: float = field(default=0.0)
    resonance_burst: float = field(default=0.0)
    resonance_eff: float = field(default=0.0)

    def from_dict(self, data: dict) -> "EchoProfile":
        for key, value in data.items():
            setattr(self, key, value)
        return self
    
    def __hash__(self):
        return hash(tuple([(k, v) for k, v in self.__dict__.items() if k not in ["name"]]))
    
    def validate(self) -> bool:
        if not 0 <= self.level <= 25:
            logger.warning(f"Validation failed due to invalid level: {self.level}")
            return False
        
        if self.name not in echo_data.keys():
            if self.name == "":
                logger.warning("Validation failed at name identification")
            else:
                logger.warning(f"Validation failed due to invalid name: {self.name}")
            return False
        
        # check the number of non-zero entries
        num_non_zero = sum(1 for key, value in self.__dict__.items() if value != 0 and key not in ["level", "name"])
        if num_non_zero != self.level // 5:
            logger.warning(f"Validation failed due to invalid number of non-zero entries: {num_non_zero} != {self.level // 5}")
            logger.warning(f"Profile: {self}")
            return False
        
        # ensure all non-zero entries are valid
        for key, value in self.__dict__.items():
            if key in ["level", "name"] or value == 0:
                continue 

            matched = False
            for entry in stat_data[key]["distribution"]:
                if entry["value"] == value:
                    matched = True 
                    break 
            
            if not matched:
                logger.warning(f"Validation failed due to invalid entry {key}: {value}")
                return False
            
        return True
    
    def _extract_number(self, line: str) -> float | None:
        numbers = re.findall(r"\d+\.?\d?", line)
        if numbers:
            return float(numbers[0])
        return None
    
    def _extract_entry(self, line: str) -> str | None:
        longest_entry_name, longest_entry_key = "", ""
        for key, entry in stat_data.items():
            if entry["name"] in line:
                if ("%" in line) != (entry["type"] == "percentage"):
                    continue
                
                if len(entry["name"]) > len(longest_entry_name):
                    longest_entry_name = entry["name"]
                    longest_entry_key = key
        
        if longest_entry_name:
            return longest_entry_key
        return None
    
    def from_image(self, image: Image.Image) -> "EchoProfile":
        text = ocr(image)
        lines_to_skip = 0
        
        for line in text.split("\n"):
            line = line.strip()

            logger.debug(f"line: {line}")

            if "声骸技能" in line:
                break

            if "+" in line:
                level = self._extract_number(line)
                if level is not None:
                    self.level = round(level)
                    lines_to_skip = 2 
                continue

            if self.name == "" and self.level == 0:
                matched_longest_name = ""
                for name in echo_data.keys():
                    # create a regex pattern for the name to ignore rare characters 
                    # and match the line with the pattern
                    rare_chars = ['魇', '·', '螯', '獠', '鬃', '翎']

                    substituted_name = name

                    for rare_char in rare_chars:
                        substituted_name = substituted_name.replace(rare_char, ".?")
                    pattern = re.compile(substituted_name)

                    if re.search(pattern, line):
                        if len(name) > len(matched_longest_name):
                            matched_longest_name = name
                            self.name = name
                continue

            if lines_to_skip > 0:
                lines_to_skip -= 1
                continue

            # find longest entry name appear in the line 
            longest_entry_key = self._extract_entry(line)

            if longest_entry_key:
                number = self._extract_number(line)
                if number:
                    setattr(self, longest_entry_key, number)

        return self
    
    def upgrade(self, level: int, new_entry: str):
        longest_entry_key = self._extract_entry(new_entry)

        if longest_entry_key is None:
            logger.warning(f"Invalid entry: {new_entry}")
            return None
        
        tmp_profile = deepcopy(self)
        tmp_profile.level = level
        
        if longest_entry_key:
            number = self._extract_number(new_entry)
            if number:
                setattr(tmp_profile, longest_entry_key, number)
        
        if tmp_profile.validate():
            return tmp_profile
        return None
    
    def get_score(self, coef: EntryCoef) -> float:
        total_score = 0
        for key, value in coef.__dict__.items():
            total_score += getattr(self, key) * value
        return total_score

    def get_expected_score(self, coef: EntryCoef) -> float:
        tmp_profile = deepcopy(self)
        remain_slots = (25 - self.level) // 5

        possible_entries = []

        for key in coef.__dict__.keys():
            curr_value = getattr(self, key)
            if curr_value == 0:
                expected_value = 0
                for entry in stat_data[key]["distribution"]:
                    expected_value += entry["value"] * entry["probability"]
                possible_entries.append(key)
                setattr(tmp_profile, key, expected_value)
        
        for key in possible_entries:
            setattr(tmp_profile, key, getattr(tmp_profile, key) * remain_slots / len(possible_entries))
        
        return tmp_profile.get_score(coef)
    
    def to_cpp(self):
        return profile_cpp.EchoProfile(self.level, {k: float(v) for k, v in self.__dict__.items() if k != "level" and k != "name"})

    def prob_above_score(self, coef: 'EntryCoef', threshold: float) -> float:
        return profile_cpp.prob_above_score(self.to_cpp(), coef.to_cpp(), threshold, stat_data)

    def get_expected_wasted_exp(self, coef: 'EntryCoef', score_thres: float, scheduler: DiscardScheduler) -> float:
        return profile_cpp.get_expected_wasted_exp(self.to_cpp(), coef.to_cpp(), score_thres, scheduler.to_cpp(), stat_data)
    
    def prob_above_threshold_with_discard(self, coef: 'EntryCoef', score_thres: float, scheduler: DiscardScheduler) -> float:
        return profile_cpp.prob_above_threshold_with_discard(self.to_cpp(), coef.to_cpp(), score_thres, scheduler.to_cpp(), stat_data)
    

def test():
    image = Image.open("test.png")

    profile = EchoProfile().from_image(image)

    print(f"{profile=}")

    threshold_profile = EchoProfile(
        level=25,
        hp_rate=9.4,
        hp_num=430,
        normal_dmg=8.6,
        resonance_eff=8.4,
        resonance_burst=7.1,
    )
    coef = EntryCoef("Cartethyia")

    threshold_score = threshold_profile.get_score(coef)
    print(f"{threshold_score=}")
    print(f"score of profile: {profile.get_score(coef)}")

    init_profile = EchoProfile()
    print(f"probability to get at least {threshold_score} score: {init_profile.prob_above_score(coef, threshold_score)}")

    scheduler = DiscardScheduler(level_5_9=0.1119, level_10_14=0.1119, level_15_19=0.1119, level_20_24=0.1119)
    expected_wasted_exp = init_profile.get_expected_wasted_exp(coef, threshold_score, scheduler)
    print(f"expected wasted exp: {expected_wasted_exp}")
    prob_above_threshold = init_profile.prob_above_threshold_with_discard(coef, threshold_score, scheduler)
    print(f"probability to get at least {threshold_score} score with discard: {prob_above_threshold}")

    print(f"expected total wasted exp (with discard): {expected_wasted_exp / prob_above_threshold}")
