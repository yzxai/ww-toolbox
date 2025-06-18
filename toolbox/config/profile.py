import re
import yaml
import profile_cpp

from dataclasses import dataclass, field
from pathlib import Path
from PIL import Image
from copy import deepcopy
from toolbox.utils.ocr import ocr

stat_file = Path(__file__).parent / "entry_stats.yml"
coef_file = Path(__file__).parent / "entry_coef.yml"

with open(stat_file, "r", encoding="utf-8") as f:
    stat_data = yaml.safe_load(f)

with open(coef_file, "r", encoding="utf-8") as f:
    coef_data = yaml.safe_load(f)

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
    
    def from_image(self, image: Image.Image) -> "EchoProfile":
        text = ocr(image)

        def extract_number(line: str) -> float | None:
            numbers = re.findall(r"\d+\.?\d+", line)
            if numbers:
                return float(numbers[0])
            return None
        
        for line in text.split("\n"):
            line = line.strip()
            if "+" in line:
                level = extract_number(line)
                if level:
                    self.level = round(level)

            for key, entry in stat_data.items():
                if entry["name"] in line:
                    if (entry["type"] == "percentage") != ("%" in line):
                        continue
                    number = extract_number(line)
                    if number:
                        setattr(self, key, number)

        return self
    
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
            if curr_value != 0:
                expected_value = 0
                for entry in stat_data[key]["distribution"]:
                    expected_value += entry["value"] * entry["probability"]
                possible_entries.append(key)
                tmp_profile.setattr(key, expected_value)
        
        for key in possible_entries:
            setattr(tmp_profile, key, getattr(tmp_profile, key) * remain_slots / len(possible_entries))
        
        return tmp_profile.get_score(coef)
    
    def to_cpp(self):
        return profile_cpp.EchoProfile(self.level, {k: float(v) for k, v in self.__dict__.items() if k != "level"})

    def prob_above_score(self, coef: 'EntryCoef', threshold: float) -> float:
        return profile_cpp.prob_above_score(self.to_cpp(), coef.to_cpp(), threshold, stat_data)

    def get_expected_wasted_exp(self, coef: 'EntryCoef', score_thres: float, discard_thres: float) -> float:
        return profile_cpp.get_expected_wasted_exp(self.to_cpp(), coef.to_cpp(), score_thres, discard_thres, stat_data)
    
    def prob_above_threshold_with_discard(self, coef: 'EntryCoef', score_thres: float, discard_thres: float) -> float:
        return profile_cpp.prob_above_threshold_with_discard(self.to_cpp(), coef.to_cpp(), score_thres, discard_thres, stat_data)
    

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

    discard_thres = 0.1119
    expected_wasted_exp = init_profile.get_expected_wasted_exp(coef, threshold_score, discard_thres)
    print(f"expected wasted exp: {expected_wasted_exp}")
    prob_above_threshold = init_profile.prob_above_threshold_with_discard(coef, threshold_score, discard_thres)
    print(f"probability to get at least {threshold_score} score with discard: {prob_above_threshold}")

    print(f"expected total wasted exp (with discard): {expected_wasted_exp / prob_above_threshold}")
